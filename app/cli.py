from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from .core import ConversionError, PandocConverter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="document-bridge",
        description="在 Word (.docx)、LaTeX (.tex) 与 Markdown (.md) 之间转换。",
    )
    parser.add_argument("input", type=Path, help="输入文档或项目 ZIP")
    parser.add_argument("--to", required=True, choices=("docx", "markdown", "latex"), help="输出格式")
    parser.add_argument(
        "--from",
        dest="source_format",
        default="auto",
        choices=("auto", "docx", "markdown", "latex"),
        help="输入格式（默认自动识别）",
    )
    parser.add_argument("-o", "--output", type=Path, help="输出文件路径")
    parser.add_argument("--main-file", help="ZIP 项目中的主文档相对路径")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        print(f"错误：找不到输入文件 {input_path}")
        return 2

    workspace = Path(tempfile.mkdtemp(prefix="document-bridge-cli-"))
    try:
        result = PandocConverter().convert(
            input_path,
            args.source_format,
            args.to,
            workspace,
            args.main_file,
        )
        destination = args.output.expanduser().resolve() if args.output else Path.cwd() / result.download_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result.path, destination)
        print(f"已生成：{destination}")
        for warning in result.warnings:
            print(f"警告：{warning}")
        return 0
    except ConversionError as exc:
        print(f"错误：{exc}")
        return 1
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

