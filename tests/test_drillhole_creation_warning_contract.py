from pathlib import Path


def test_main_window_surfaces_secondary_drillhole_creation_warning():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")
    assert 'getattr(result,"warning_text",None)' in source
    assert 'domain_message(result.warning_text)' in source
