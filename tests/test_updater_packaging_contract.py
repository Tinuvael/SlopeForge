from pathlib import Path


def test_release_build_packages_updater_next_to_main_application() -> None:
    script = Path("build_release.bat").read_text(encoding="utf-8")
    assert "SlopeForgeUpdater.spec" in script
    assert 'dist\\SlopeForgeUpdater.exe' in script
    assert 'dist\\SlopeForge\\SlopeForgeUpdater.exe' in script


def test_payload_validator_requires_updater_executable() -> None:
    source = Path("tools/validate_windows_payload.py").read_text(encoding="utf-8")
    assert 'Path("SlopeForgeUpdater.exe")' in source


def test_installer_exposes_updater_start_menu_shortcut() -> None:
    source = Path("installer/SlopeForge.iss").read_text(encoding="utf-8")
    assert '#define UpdaterExeName "SlopeForgeUpdater.exe"' in source
    assert 'Name: "{group}\\SlopeForge Updater"' in source


def test_updater_pyinstaller_bundle_contains_alembic_graph() -> None:
    source = Path("SlopeForgeUpdater.spec").read_text(encoding="utf-8")
    assert 'updater_main.py' in source
    assert 'alembic.ini' in source
    assert 'root / "alembic"' in source
    assert 'name="SlopeForgeUpdater"' in source
