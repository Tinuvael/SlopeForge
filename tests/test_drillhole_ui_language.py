from pathlib import Path


def test_new_drillhole_ui_uses_product_english_labels():
    sources = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "ui/dialogs/blast_event_dialog.py",
            "ui/dialogs/drillhole_group_assignment_dialog.py",
            "ui/pages/drillhole_dataset_widgets.py",
        )
    )
    for label in ("Design drillholes", "As-drilled holes", "Assign drillholes", "Select by polygon"):
        assert label in sources
