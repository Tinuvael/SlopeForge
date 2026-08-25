# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


root = Path(SPEC).resolve().parent

datas = [
    (str(root / "app" / "icons"), "app/icons"),
    (str(root / "alembic.ini"), "."),
    (str(root / "alembic"), "alembic"),
]

hiddenimports = ["logging.config"]
try:
    import win32cred  # noqa: F401
except ImportError:
    pass
else:
    hiddenimports.extend(["win32cred", "pythoncom", "pywintypes"])


a = Analysis(
    [str(root / "updater_main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name="SlopeForgeUpdater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "app" / "icons" / "slopeforge_icon.ico"),
)
