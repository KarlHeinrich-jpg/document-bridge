from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from app import __version__


def _configure_bundled_pandoc() -> None:
    """Point the converter at Pandoc when running from a frozen bundle."""
    if os.environ.get("DOCUMENT_BRIDGE_PANDOC"):
        return

    executable_name = "pandoc.exe" if os.name == "nt" else "pandoc"
    bases = [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).resolve().parent]
    candidates: list[Path] = []
    for base in bases:
        if not str(base):
            continue
        candidates.extend(
            [
                base / "pypandoc" / "files" / executable_name,
                base / "_internal" / "pypandoc" / "files" / executable_name,
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            os.environ["DOCUMENT_BRIDGE_PANDOC"] = str(candidate)
            return


def _available_port(host: str, preferred: int) -> int:
    """Use the preferred port, falling back to an ephemeral local port."""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return int(probe.getsockname()[1])
    raise RuntimeError("没有可用的本地端口。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="启动文桥本地文档转换工具。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=8765, help="首选端口（默认 8765）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    parser.add_argument("--version", action="version", version=f"Document Bridge {__version__}")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _configure_bundled_pandoc()

    from app.main import app, get_converter

    try:
        engine = get_converter().version()
    except Exception as exc:
        print(f"转换引擎启动失败：{exc}", file=sys.stderr)
        return 1

    port = _available_port(args.host, args.port)
    browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{browser_host}:{port}"
    print(f"文桥 {__version__} · {engine}")
    print(f"访问地址：{url}")
    print("按 Ctrl+C 停止服务。")

    if not args.no_browser:
        timer = threading.Timer(1.0, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()

    uvicorn.run(app, host=args.host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
