from __future__ import annotations

import base64
import tempfile
import zipfile
from pathlib import Path

from app.core import DocumentFormat, PandocConverter, supported_conversions


SAMPLE = """---
title: 文桥测试文档
author: Codex
---

# 第一节

这是一段包含 **粗体**、*斜体* 与行内公式 $E = mc^2$ 的文字。

$$
\\int_0^1 x^2 \\, dx = \\frac{1}{3}
$$

| 项目 | 数值 |
|---|---:|
| Alpha | 42 |

- 列表一
- 列表二
"""

ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def main() -> int:
    converter = PandocConverter()
    with tempfile.TemporaryDirectory(prefix="document-bridge-smoke-") as temp:
        root = Path(temp)
        fixtures = root / "fixtures"
        fixtures.mkdir()
        markdown = fixtures / "sample.md"
        markdown.write_text(SAMPLE, encoding="utf-8")

        seeds: dict[DocumentFormat, Path] = {DocumentFormat.MARKDOWN: markdown}
        for target in (DocumentFormat.DOCX, DocumentFormat.LATEX):
            workspace = root / f"seed-{target.value}"
            workspace.mkdir()
            result = converter.convert(markdown, DocumentFormat.MARKDOWN, target, workspace)
            seeded = fixtures / result.download_name
            seeded.write_bytes(result.path.read_bytes())
            seeds[target] = seeded

        completed = []
        for source, target in supported_conversions():
            workspace = root / f"{source.value}-to-{target.value}"
            workspace.mkdir()
            result = converter.convert(seeds[source], source, target, workspace)
            if not result.path.is_file() or result.path.stat().st_size == 0:
                raise RuntimeError(f"Empty output for {source.value} -> {target.value}")
            completed.append(f"{source.value} -> {target.value}: {result.path.name} ({result.path.stat().st_size} bytes)")

        image_fixture = fixtures / "with-image"
        image_fixture.mkdir()
        (image_fixture / "pixel.png").write_bytes(ONE_PIXEL_PNG)
        image_markdown = image_fixture / "image.md"
        image_markdown.write_text("# Image test\n\n![pixel](pixel.png)\n", encoding="utf-8")
        image_docx_workspace = root / "image-to-docx"
        image_docx_workspace.mkdir()
        image_docx_result = converter.convert(
            image_markdown,
            DocumentFormat.MARKDOWN,
            DocumentFormat.DOCX,
            image_docx_workspace,
        )
        image_docx = fixtures / "image.docx"
        image_docx.write_bytes(image_docx_result.path.read_bytes())
        extracted_workspace = root / "image-from-docx"
        extracted_workspace.mkdir()
        extracted_result = converter.convert(
            image_docx,
            DocumentFormat.DOCX,
            DocumentFormat.MARKDOWN,
            extracted_workspace,
        )
        if extracted_result.path.suffix != ".zip":
            raise RuntimeError("DOCX with an image should produce a ZIP for text output")
        with zipfile.ZipFile(extracted_result.path) as archive:
            names = archive.namelist()
            if "image.md" not in names or not any(name.startswith("assets/") for name in names):
                raise RuntimeError(f"Extracted media package is incomplete: {names}")
        completed.append(f"docx media package: {extracted_result.path.name}")

        latex_project = root / "latex-project.zip"
        with zipfile.ZipFile(latex_project, "w") as archive:
            archive.writestr(
                "paper/main.tex",
                "\\documentclass{article}\n\\begin{document}\nHello project.\n\\end{document}\n",
            )
            archive.writestr("paper/refs.bib", "@book{test, title={Test}}\n")
        project_workspace = root / "latex-project-output"
        project_workspace.mkdir()
        project_result = converter.convert(
            latex_project,
            DocumentFormat.LATEX,
            DocumentFormat.MARKDOWN,
            project_workspace,
        )
        with zipfile.ZipFile(project_result.path) as archive:
            names = archive.namelist()
            if "paper/main.md" not in names or "paper/refs.bib" not in names:
                raise RuntimeError(f"Project package is incomplete: {names}")
        completed.append(f"latex project package: {project_result.path.name}")

    print(f"{converter.version()}\n" + "\n".join(completed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
