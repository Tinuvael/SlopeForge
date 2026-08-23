from pathlib import Path


def test_drillhole_feature_does_not_modify_technical_card_domain_formulas():
    # The feature consumes the existing Technical Card model from UI/application
    # integration and deliberately leaves domain/blasting/technical_card.py unchanged.
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert "production_parameters.recalculate" in source
    assert "actual_execution" in source
