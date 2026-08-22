from pathlib import Path

from app import runtime_paths


def test_windows_log_path_uses_local_app_data(monkeypatch):
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\engineer\AppData\Local")

    assert runtime_paths.runtime_log_path() == Path(
        r"C:\Users\engineer\AppData\Local"
    ) / "SlopeForge" / "logs" / "slopeforge.log"


def test_non_windows_log_path_uses_user_state_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_paths.sys, "platform", "linux")
    monkeypatch.setattr(runtime_paths.Path, "home", lambda: tmp_path)

    assert runtime_paths.runtime_log_path() == (
        tmp_path / ".local" / "state" / "SlopeForge" / "logs" / "slopeforge.log"
    )


def test_windows_log_path_has_a_home_directory_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(runtime_paths.Path, "home", lambda: tmp_path)

    assert runtime_paths.runtime_log_path() == (
        tmp_path / "AppData" / "Local" / "SlopeForge" / "logs" / "slopeforge.log"
    )
