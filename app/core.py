from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Iterable


MAX_ARCHIVE_FILES = 1_000
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
PANDOC_TIMEOUT_SECONDS = 120


class ConversionError(RuntimeError):
    """A user-facing conversion failure."""


class DocumentFormat(str, Enum):
    DOCX = "docx"
    MARKDOWN = "markdown"
    LATEX = "latex"


EXTENSIONS: dict[DocumentFormat, tuple[str, ...]] = {
    DocumentFormat.DOCX: (".docx",),
    DocumentFormat.MARKDOWN: (".md", ".markdown"),
    DocumentFormat.LATEX: (".tex", ".latex"),
}

OUTPUT_EXTENSION: dict[DocumentFormat, str] = {
    DocumentFormat.DOCX: ".docx",
    DocumentFormat.MARKDOWN: ".md",
    DocumentFormat.LATEX: ".tex",
}

PANDOC_FORMAT: dict[DocumentFormat, str] = {
    DocumentFormat.DOCX: "docx",
    DocumentFormat.MARKDOWN: "markdown+yaml_metadata_block+tex_math_dollars+fenced_divs+bracketed_spans",
    DocumentFormat.LATEX: "latex",
}

MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown; charset=utf-8",
    ".tex": "application/x-tex; charset=utf-8",
    ".zip": "application/zip",
}


@dataclass(slots=True)
class PreparedSource:
    main_path: Path
    root: Path
    source_format: DocumentFormat
    was_archive: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConversionResult:
    path: Path
    download_name: str
    media_type: str
    warnings: list[str] = field(default_factory=list)


def parse_format(value: str | DocumentFormat) -> DocumentFormat:
    if isinstance(value, DocumentFormat):
        return value
    aliases = {
        "md": DocumentFormat.MARKDOWN,
        "markdown": DocumentFormat.MARKDOWN,
        "tex": DocumentFormat.LATEX,
        "latex": DocumentFormat.LATEX,
        "word": DocumentFormat.DOCX,
        "docx": DocumentFormat.DOCX,
    }
    try:
        return aliases[value.strip().lower()]
    except KeyError as exc:
        raise ConversionError(f"不支持的文档格式：{value}") from exc


def detect_format(path: Path) -> DocumentFormat:
    suffix = path.suffix.lower()
    for document_format, extensions in EXTENSIONS.items():
        if suffix in extensions:
            return document_format
    if suffix == ".zip":
        formats: set[DocumentFormat] = set()
        try:
            with zipfile.ZipFile(path) as archive:
                for item in archive.infolist():
                    item_suffix = Path(item.filename).suffix.lower()
                    for document_format in (DocumentFormat.MARKDOWN, DocumentFormat.LATEX):
                        if item_suffix in EXTENSIONS[document_format]:
                            formats.add(document_format)
        except zipfile.BadZipFile as exc:
            raise ConversionError("上传的文件不是有效的 ZIP 压缩包。") from exc
        if len(formats) == 1:
            return formats.pop()
        if not formats:
            raise ConversionError("ZIP 中没有找到 .md、.markdown、.tex 或 .latex 主文档。")
        raise ConversionError("ZIP 同时包含 Markdown 与 LaTeX，请手动选择输入格式。")
    raise ConversionError("无法识别输入格式；请选择 DOCX、Markdown、LaTeX 或项目 ZIP。")


def _safe_member_name(filename: str) -> PurePosixPath:
    normalized = filename.replace("\\", "/")
    if "\x00" in normalized:
        raise ConversionError("ZIP 中含有非法文件名。")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ConversionError("ZIP 中含有不安全的文件路径。")
    if re.match(r"^[A-Za-z]:", normalized):
        raise ConversionError("ZIP 中含有不安全的绝对路径。")
    return path


def safe_extract_zip(archive_path: Path, destination: Path) -> None:
    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as exc:
        raise ConversionError("上传的文件不是有效的 ZIP 压缩包。") from exc

    with archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_FILES:
            raise ConversionError(f"ZIP 文件数超过限制（最多 {MAX_ARCHIVE_FILES} 个）。")

        total_size = sum(item.file_size for item in members)
        if total_size > MAX_ARCHIVE_BYTES:
            raise ConversionError("ZIP 解压后的总体积超过 100 MB。")

        for item in members:
            relative = _safe_member_name(item.filename)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ConversionError("ZIP 中不能包含符号链接。")
            target = destination.joinpath(*relative.parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def _candidate_score(path: Path, document_format: DocumentFormat, root: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    preferred = {
        DocumentFormat.LATEX: ("main.tex", "index.tex", "document.tex"),
        DocumentFormat.MARKDOWN: ("index.md", "readme.md", "main.md"),
    }[document_format]
    score = 0
    if name in preferred:
        score += 100 - preferred.index(name)
    try:
        sample = path.read_text(encoding="utf-8", errors="ignore")[:200_000]
    except OSError:
        sample = ""
    if document_format is DocumentFormat.LATEX:
        if "\\documentclass" in sample:
            score += 80
        if "\\begin{document}" in sample:
            score += 40
    else:
        if sample.startswith("---\n"):
            score += 15
        if re.search(r"^#\s+\S", sample, flags=re.MULTILINE):
            score += 10
    depth = len(path.relative_to(root).parts)
    return score, -depth, path.as_posix()


def find_main_file(root: Path, document_format: DocumentFormat, requested: str | None = None) -> tuple[Path, list[str]]:
    if document_format is DocumentFormat.DOCX:
        extensions = EXTENSIONS[DocumentFormat.DOCX]
    else:
        extensions = EXTENSIONS[document_format]

    if requested:
        relative = _safe_member_name(requested)
        candidate = root.joinpath(*relative.parts)
        if not candidate.is_file() or candidate.suffix.lower() not in extensions:
            raise ConversionError("指定的主文档不存在，或扩展名与输入格式不匹配。")
        return candidate, []

    candidates = [
        item for item in root.rglob("*")
        if item.is_file()
        and item.suffix.lower() in extensions
        and not any(part.startswith(".") or part == "__MACOSX" for part in item.relative_to(root).parts)
    ]
    if not candidates:
        shown = "、".join(extensions)
        raise ConversionError(f"项目中没有找到 {shown} 文档。")
    ranked = sorted(candidates, key=lambda item: _candidate_score(item, document_format, root), reverse=True)
    warnings: list[str] = []
    if len(candidates) > 1:
        chosen = ranked[0].relative_to(root).as_posix()
        warnings.append(f"项目含多个候选文档，已自动选择 {chosen}；如不正确，请在高级选项中指定主文档。")
    return ranked[0], warnings


def _clean_stem(name: str) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w\-.\u4e00-\u9fff]+", "-", stem, flags=re.UNICODE).strip("-._")
    return cleaned[:80] or "document"


def _zip_directory(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in sorted(source.rglob("*")):
            if item.is_file():
                archive.write(item, item.relative_to(source).as_posix())


def resolve_pandoc() -> str:
    configured = os.environ.get("DOCUMENT_BRIDGE_PANDOC")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise ConversionError("DOCUMENT_BRIDGE_PANDOC 指向的 Pandoc 不可执行。")

    system_path = shutil.which("pandoc")
    if system_path:
        return system_path

    try:
        import pypandoc

        return pypandoc.get_pandoc_path()
    except Exception as exc:  # pragma: no cover - depends on installation state
        raise ConversionError("未找到 Pandoc。请先运行 pip install -r requirements.txt。") from exc


class PandocConverter:
    def __init__(self, pandoc_path: str | None = None) -> None:
        self.pandoc_path = pandoc_path or resolve_pandoc()

    def version(self) -> str:
        try:
            completed = subprocess.run(
                [self.pandoc_path, "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConversionError("Pandoc 无法启动。") from exc
        return completed.stdout.splitlines()[0].strip()

    def prepare(
        self,
        input_path: Path,
        source_format: str | DocumentFormat,
        workspace: Path,
        main_file: str | None = None,
    ) -> PreparedSource:
        detected = detect_format(input_path) if str(source_format).lower() == "auto" else parse_format(source_format)
        if input_path.suffix.lower() != ".zip":
            if input_path.suffix.lower() not in EXTENSIONS[detected]:
                expected = "、".join(EXTENSIONS[detected])
                raise ConversionError(f"输入扩展名与所选格式不匹配，应为 {expected}。")
            return PreparedSource(input_path, input_path.parent, detected)

        if detected is DocumentFormat.DOCX:
            raise ConversionError("Word 输入请直接上传 .docx，不需要压缩为 ZIP。")
        extracted = workspace / "project"
        extracted.mkdir(parents=True, exist_ok=True)
        safe_extract_zip(input_path, extracted)
        main_path, warnings = find_main_file(extracted, detected, main_file)
        return PreparedSource(main_path, extracted, detected, True, warnings)

    def convert(
        self,
        input_path: Path,
        source_format: str | DocumentFormat,
        target_format: str | DocumentFormat,
        workspace: Path,
        main_file: str | None = None,
    ) -> ConversionResult:
        target = parse_format(target_format)
        prepared = self.prepare(input_path, source_format, workspace, main_file)
        if prepared.source_format is target:
            raise ConversionError("输入与输出格式相同，无需转换。")

        generated = workspace / "generated"
        generated.mkdir(parents=True, exist_ok=True)
        base_name = _clean_stem(prepared.main_path.name)
        output_extension = OUTPUT_EXTENSION[target]
        generated_output = generated / f"{base_name}{output_extension}"

        command = [
            self.pandoc_path,
            str(prepared.main_path.resolve()),
            f"--from={PANDOC_FORMAT[prepared.source_format]}",
            f"--to={PANDOC_FORMAT[target]}",
            f"--output={generated_output.resolve()}",
            f"--resource-path={prepared.main_path.parent.resolve()}{os.pathsep}{prepared.root.resolve()}",
        ]
        if target is DocumentFormat.LATEX:
            command.extend(["--standalone", "--wrap=preserve"])
        elif target is DocumentFormat.MARKDOWN:
            command.append("--wrap=none")
        if prepared.source_format is DocumentFormat.DOCX and target is not DocumentFormat.DOCX:
            command.append("--extract-media=assets")

        run_directory = generated if prepared.source_format is DocumentFormat.DOCX else prepared.main_path.parent
        try:
            completed = subprocess.run(
                command,
                cwd=run_directory,
                capture_output=True,
                text=True,
                timeout=PANDOC_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConversionError("转换超过 120 秒，已停止。请尝试缩小文档或项目。") from exc
        except OSError as exc:
            raise ConversionError("无法启动 Pandoc 转换进程。") from exc

        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            details = stderr.splitlines()[-1] if stderr else "Pandoc 未提供详细错误。"
            raise ConversionError(f"转换失败：{details}")
        if not generated_output.is_file():
            raise ConversionError("转换完成，但没有生成输出文件。")

        warnings = list(prepared.warnings)
        if stderr:
            warnings.extend(line.strip() for line in stderr.splitlines() if line.strip())

        if target is DocumentFormat.DOCX:
            return ConversionResult(
                generated_output,
                generated_output.name,
                MEDIA_TYPES[output_extension],
                warnings,
            )

        if prepared.was_archive:
            package = workspace / "package"
            shutil.copytree(prepared.root, package)
            relative_main = prepared.main_path.relative_to(prepared.root)
            packaged_output = package / relative_main.with_suffix(output_extension)
            packaged_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(generated_output, packaged_output)
            archive_output = workspace / f"{base_name}-to-{target.value}.zip"
            _zip_directory(package, archive_output)
            return ConversionResult(archive_output, archive_output.name, MEDIA_TYPES[".zip"], warnings)

        assets = generated / "assets"
        if assets.is_dir() and any(item.is_file() for item in assets.rglob("*")):
            package = workspace / "package"
            package.mkdir(parents=True, exist_ok=True)
            shutil.copy2(generated_output, package / generated_output.name)
            shutil.copytree(assets, package / "assets")
            archive_output = workspace / f"{base_name}-to-{target.value}.zip"
            _zip_directory(package, archive_output)
            return ConversionResult(archive_output, archive_output.name, MEDIA_TYPES[".zip"], warnings)

        return ConversionResult(
            generated_output,
            generated_output.name,
            MEDIA_TYPES[output_extension],
            warnings,
        )


def supported_conversions() -> Iterable[tuple[DocumentFormat, DocumentFormat]]:
    for source in DocumentFormat:
        for target in DocumentFormat:
            if source is not target:
                yield source, target

