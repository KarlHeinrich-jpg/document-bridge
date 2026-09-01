from __future__ import annotations

import json
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from . import __version__
from .core import ConversionError, PandocConverter


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = FastAPI(
    title="文桥 Document Bridge",
    description="在 Word、LaTeX 与 Markdown 之间进行本地转换。",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@lru_cache(maxsize=1)
def get_converter() -> PandocConverter:
    return PandocConverter()


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/status")
async def status() -> dict[str, str | bool]:
    try:
        converter = get_converter()
        version = await run_in_threadpool(converter.version)
        return {"ready": True, "engine": version, "app_version": __version__}
    except ConversionError as exc:
        return {"ready": False, "engine": str(exc), "app_version": __version__}


async def _save_upload(upload: UploadFile, destination: Path) -> int:
    total = 0
    with destination.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="文件超过 50 MB 上传限制。")
            output.write(chunk)
    return total


@app.post("/api/convert")
async def convert_document(
    file: UploadFile = File(...),
    source_format: str = Form("auto"),
    target_format: str = Form(...),
    main_file: str | None = Form(None),
) -> FileResponse:
    original_name = Path(file.filename or "document").name
    if not original_name or original_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="文件名无效。")

    workspace = Path(tempfile.mkdtemp(prefix="document-bridge-"))
    upload_path = workspace / "upload" / original_name
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await _save_upload(file, upload_path)
        converter = get_converter()
        result = await run_in_threadpool(
            converter.convert,
            upload_path,
            source_format,
            target_format,
            workspace,
            main_file.strip() if main_file and main_file.strip() else None,
        )
    except HTTPException:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
    except ConversionError as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        raise HTTPException(status_code=500, detail="转换时发生内部错误。") from exc
    finally:
        await file.close()

    headers = {
        "X-Document-Bridge-Warnings": json.dumps(result.warnings, ensure_ascii=True),
        "Cache-Control": "no-store",
    }
    return FileResponse(
        path=result.path,
        filename=result.download_name,
        media_type=result.media_type,
        headers=headers,
        background=BackgroundTask(shutil.rmtree, workspace, ignore_errors=True),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)

