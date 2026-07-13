# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys


project_root = Path.cwd()
icon_path = project_root / "app" / "icons" / "slopeforge.ico"

datas = []

if (project_root / "resources").exists():
    datas.append(("resources", "resources"))

if (project_root / "data").exists():
    datas.append(("data", "data"))



a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "tests",
    ],
    noarchive=False,
)


pyz = PYZ(
    a.pure,
    a.zipped_data,
)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SlopeForge"
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path) if icon_path.exists() else None,
)


coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StopeForge",
)


if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="StopeForge.app",
        icon=str(icon_path) if icon_path.exists() else None,
        bundle_identifier="com.slopeforge.app"
    )
