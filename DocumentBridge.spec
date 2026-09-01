# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import pypandoc
from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPEC).resolve().parent
pandoc_path = Path(pypandoc.get_pandoc_path())

hidden_imports = collect_submodules("uvicorn") + [
    "multipart",
    "pypandoc",
]

a = Analysis(
    [str(project_root / "app" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[(str(pandoc_path), "pypandoc/files")],
    datas=[(str(project_root / "app" / "static"), "app/static")],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DocumentBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DocumentBridge",
)

