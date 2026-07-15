# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

project_root = Path.cwd()
icon_path = project_root / "app" / "icons" / "slopeforge_icon.ico"

# Keep runtime assets available for resource_path() both from source and PyInstaller.
datas = [
    (str(project_root / "app" / "icons"), "app/icons"),
]

if (project_root / "data").exists():
    datas.append((str(project_root / "data"), "data"))


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

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SlopeForge",
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
    name="SlopeForge",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SlopeForge.app",
        icon=str(project_root / "app" / "icons" / "slopeforge_icon.icns"),
        bundle_identifier="com.tinuvael.slopeforge",
    )
