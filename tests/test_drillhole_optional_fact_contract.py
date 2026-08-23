from pathlib import Path


def test_as_drilled_dataset_is_optional_until_user_imports_it():
    source = Path("application/services/drillhole_datasets.py").read_text(encoding="utf-8")
    widgets = Path("ui/pages/drillhole_dataset_widgets.py").read_text(encoding="utf-8")
    assert 'dataset_kind not in {"design", "actual"}' in source
    assert 'tr("No dataset loaded")' in widgets
