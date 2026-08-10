from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from domain.geometry.types import PlanMultiPoint, PlanPoint, PlanPolygon
from domain.blasting.entities import BlastEvent, BlastEventGeometryRevision
from application.state.assessment_domain_state import AssessmentDomainState
from domain.blasting.technical_card import (BlastDrillingGroup, ContourParameters,
    TechnicalCardService, new_technical_card, polygon_area_m2)


def event(kind="production"):
    geometry = (PlanPolygon((PlanPoint(0,0), PlanPoint(10,0), PlanPoint(10,5), PlanPoint(0,5), PlanPoint(0,0)))
                if kind == "production" else PlanMultiPoint((PlanPoint(0,0), PlanPoint(1,1))))
    blast = BlastEvent("BE-1", "Блок 1", kind, None, 620)
    blast.geometry_revisions.append(BlastEventGeometryRevision("G-1", blast.id, 1,
        datetime.now(timezone.utc), "source.csv", [], geometry, 620, True))
    blast.active_geometry_revision_id = "G-1"
    return blast


def test_polygon_area_uses_domain_coordinates():
    assert polygon_area_m2(event().active_geometry_revision().plan_geometry) == 50


def test_production_revision_calculations_and_immutability():
    blast = event(); card, draft = new_technical_card(blast); p = draft.production_parameters
    assert draft.geometry_revision_id == "G-1" and p.drilling_area_m2.calculated_value == 50
    assert draft.drilling_groups[0].group_type == "main_pattern"
    p.average_hole_depth_m=12; p.subdrill_m=2; p.design_bench_height_m=10; p.total_explosive_mass_kg=500
    draft.drilling_groups[0].hole_count=10; draft.drilling_groups[0].average_depth_m=12
    draft.drilling_groups.append(BlastDrillingGroup(group_type="buffer", name="Буфер", hole_count=2,
        average_depth_m=8, burden_m=5, spacing_m=4))
    first=card.save_revision(draft)
    assert p.average_depth_without_subdrill_m is None  # saved revision is a deep immutable copy
    assert first.production_parameters.average_depth_without_subdrill_m == 10
    assert first.production_parameters.block_volume_m3.calculated_value == 500
    assert first.production_parameters.total_hole_count == 12
    assert first.production_parameters.total_drilling_length_m.calculated_value == 136
    assert first.production_parameters.rock_yield_m3_per_drilling_m == pytest.approx(500/136)
    assert first.production_parameters.specific_drilling_m_per_m3 == pytest.approx(136/500)
    assert first.production_parameters.powder_factor_kg_per_m3 == 1
    edit=deepcopy(first); edit.drilling_groups[1].spacing_m=6; second=card.save_revision(edit)
    assert second.revision_number == 2 and first.drilling_groups[1].spacing_m == 4


def test_manual_overrides_retain_calculated_and_accepted_values():
    card,draft=new_technical_card(event()); p=draft.production_parameters
    p.drilling_area_m2.manual_value=60; p.design_bench_height_m=10
    p.block_volume_m3.manual_value=700; p.total_drilling_length_m.manual_value=140
    saved=card.save_revision(draft).production_parameters
    assert saved.drilling_area_m2.calculated_value == 50 and saved.drilling_area_m2.accepted_value == 60
    assert saved.block_volume_m3.calculated_value == 600 and saved.block_volume_m3.accepted_value == 700
    assert saved.total_drilling_length_m.accepted_value == 140


def test_zero_denominators_are_safe():
    card,draft=new_technical_card(event()); p=draft.production_parameters
    p.design_bench_height_m=0; p.total_explosive_mass_kg=10
    saved=card.save_revision(draft).production_parameters
    assert saved.rock_yield_m3_per_drilling_m is None
    assert saved.specific_drilling_m_per_m3 is None and saved.powder_factor_kg_per_m3 is None


def test_main_group_cannot_be_removed_and_duplicates_are_allowed():
    card,draft=new_technical_card(event())
    with pytest.raises(ValueError): card.remove_group(draft, draft.drilling_groups[0].id)
    a=BlastDrillingGroup(group_type="main_pattern", name="Основная сеть №2")
    b=BlastDrillingGroup(group_type="main_pattern", name="Основная сеть №3")
    draft.drilling_groups += [a,b]
    assert a.id != b.id
    card.remove_group(draft, a.id)


def test_custom_group_and_independent_patterns():
    _,draft=new_technical_card(event()); main=draft.drilling_groups[0]; main.burden_m=2.5
    custom=BlastDrillingGroup(group_type="other", custom_type_name="Опытный ряд", name="Опытный", burden_m=5)
    draft.drilling_groups.append(custom)
    assert main.burden_m != custom.burden_m and custom.custom_type_name


@pytest.mark.parametrize("method,unloaded,decoupled", [("line_drilling",True,False),("presplit",False,True),("midsplit",False,True)])
def test_contour_method_defaults(method, unloaded, decoupled):
    p=ContourParameters(); p.set_method(method)
    assert (p.unloaded_holes,p.decoupled_charge)==(unloaded,decoupled)


def test_production_and_contour_required_sections_differ():
    production_card,p=new_technical_card(event()); contour_card,c=new_technical_card(event("contour"))
    assert p.geomechanical_parameters is not None and c.geomechanical_parameters is None
    assert c.drilling_groups[0].group_type == "contour_line"
    assert "геомеханическое" in " ".join(p.validate_completion())
    c.contour_parameters.set_method("presplit")
    assert not c.validate_completion()


def test_text_strength_is_not_converted_to_ucs():
    _,draft=new_technical_card(event()); geo=draft.geomechanical_parameters
    geo.rock_strength_class_text="СМ 10–14"; geo.rock_mass_properties_text="RQD 20–45"
    assert geo.representative_ucs_mpa is None and geo.minimum_complete()


def test_json_roundtrip_and_old_json_compatibility():
    state=AssessmentDomainState(blast_events=[event()]); service=TechnicalCardService(state)
    card,draft=service.edit_or_create(state.blast_events[0]); card.save_revision(draft)
    restored=AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.technical_cards[0].active_revision().geometry_revision_id == "G-1"
    old=state.to_dict(); old.pop("technical_cards")
    assert AssessmentDomainState.from_dict(old).technical_cards == []


def test_revision_remains_on_historical_geometry_after_reimport():
    blast=event(); card,draft=new_technical_card(blast); old=card.save_revision(draft)
    blast.add_geometry_revision(source_file_name="new.csv",source_geometry=[],plan_geometry=blast.active_geometry_revision().plan_geometry,elevation=621)
    assert blast.active_geometry_revision_id != old.geometry_revision_id
    assert old.geometry_revision_id == "G-1"


def test_technical_card_dialog_does_not_shadow_qt_event_method():
    """Regression: assigning BlastEvent to QDialog.event broke every show()."""
    QApplication = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError).QApplication
    from ui.editors.technical_card_editor import TechnicalCardDialog

    app = QApplication.instance() or QApplication([])
    blast = event()
    card, draft = new_technical_card(blast)
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)

    assert callable(dialog.event)
    dialog.show()
    app.processEvents()
    assert dialog.isVisible()
    dialog.close()


def test_real_embedded_production_editor_controls_and_ucs_persistence():
    """Construct the same Qt editor used by BlockListPage, not a source-text fake."""
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.technical_card_widgets import TechnicalCardEditorWidget
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); blast.blast_block_id = 77
    state = AssessmentDomainState(blast_events=[blast]); service = TechnicalCardService(state)
    card, draft = service.edit_or_create(blast)
    embedded = TechnicalCardEditorWidget(blast, card, draft,
        lambda saved_card, revision, status: saved_card.save_revision(revision, status=status))
    assert embedded.editor.lithology.isVisibleTo(embedded.editor) is False  # dialog is intentionally not shown
    assert embedded.editor.ucs is not None
    assert embedded.editor.group_cards_layout.count() >= 1
    assert embedded.editor.completion_status is not None
    embedded.editor.ucs.setValue(123.0)
    assert embedded.save_draft() is True
    restored = AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored.technical_cards[0].active_revision().geomechanical_parameters.representative_ucs_mpa == 123.0
    embedded.deleteLater(); app.processEvents()
