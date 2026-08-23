from pathlib import Path


def test_drillhole_assignment_reuses_existing_technical_card_groups():
    domain = Path("domain/blasting/technical_card.py").read_text(encoding="utf-8")
    widgets = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert '"main_pattern"' in domain and '"buffer"' in domain and '"toe"' in domain
    assert "group: BlastDrillingGroup" in widgets
    assert "engineering_group_id == group.id" in widgets
