from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from domain.geometry.types import PlanMultiPoint, PlanPoint, PlanPolygon
from domain.blasting.entities import BlastEvent, BlastEventGeometryRevision
from application.state.assessment_domain_state import AssessmentDomainState
from domain.blasting.technical_card import (BARTON_JA_VALUES, BARTON_JN_VALUES, BARTON_JR_VALUES,
    BARTON_JW_VALUES, BlastDrillingGroup, ContourParameters, GeomechanicalParameters,
    JointSetOrientation, TechnicalCardService, new_technical_card, polygon_area_m2)


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
    p.average_hole_depth_m=12; p.subdrill_m=2; p.design_bench_height_m=10
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
    assert first.production_parameters.powder_factor_kg_per_m3 == 0
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


@pytest.mark.parametrize("values,complete", [
    ({}, False), ({"ucs_mpa": 100}, False), ({"ucs_mpa": 100, "q_value": 2}, False),
    ({"ucs_mpa": 100, "rqd_percent": 50}, True), ({"ucs_mpa": 100, "gsi": 40}, True),
    ({"ucs_mpa": 100, "ff": 8}, True), ({"q_value": 2, "rqd_percent": 50, "gsi": 40}, False),
])
def test_geomechanics_minimum_complete(values, complete):
    assert GeomechanicalParameters(**values).minimum_complete() is complete


def test_joint_set_count_and_orientation_validation():
    five = [JointSetOrientation(index * 10, index * 50) for index in range(5)]
    assert GeomechanicalParameters(joint_sets=five).joint_sets == five
    with pytest.raises(ValueError, match="five joint sets"):
        GeomechanicalParameters(joint_sets=five + [JointSetOrientation(1, 1)])
    for dip in (0, 90):
        assert JointSetOrientation(dip, 0).dip_deg == dip
    for dip in (-0.001, 90.001):
        with pytest.raises(ValueError, match="dip must"):
            JointSetOrientation(dip, 0)
    for direction in (0, 359.999):
        assert JointSetOrientation(45, direction).dip_direction_deg == direction
    with pytest.raises(ValueError, match="direction"):
        JointSetOrientation(45, 360)


def test_geomechanics_barton_catalogue_gsi_ff_and_ucs_validation():
    assert GeomechanicalParameters(gsi=1, ff=0, ucs_mpa=0).gsi == 1
    assert GeomechanicalParameters(gsi=100, ff=12, ucs_mpa=250).ff == 12
    for value in (0, 101):
        with pytest.raises(ValueError, match="GSI"):
            GeomechanicalParameters(gsi=value)
    with pytest.raises(ValueError, match="FF"):
        GeomechanicalParameters(ff=-1)
    with pytest.raises(ValueError, match="UCS"):
        GeomechanicalParameters(ucs_mpa=-1)

    for name, allowed in (("jn", BARTON_JN_VALUES), ("jr", BARTON_JR_VALUES),
                          ("ja", BARTON_JA_VALUES), ("jw", BARTON_JW_VALUES)):
        for value in allowed:
            assert getattr(GeomechanicalParameters(**{name: value}), name) == value
        with pytest.raises(ValueError, match=name.title()):
            GeomechanicalParameters(**{name: 999})


def test_legacy_geomechanics_payload_uses_only_representative_fallbacks():
    blast = event(); card, draft = new_technical_card(blast); card.save_revision(draft)
    payload = card.to_dict(); payload["revisions"][0]["geomechanical_parameters"] = {
        "lithology": "Granite", "geotechnical_domain": "Legacy zone",
        "rock_strength_class_text": "Strong", "representative_ucs_mpa": 125,
        "ucs_min_mpa": 80, "ucs_max_mpa": 160, "rqd_representative_percent": 72,
        "rqd_min_percent": 40, "rqd_max_percent": 95,
        "rock_mass_properties_text": "...", "fracturing_description": "...",
        "water_condition": "Wet", "geomechanical_notes": "Legacy note",
    }
    geo = type(card).from_dict(payload).active_revision().geomechanical_parameters
    assert (geo.lithology, geo.ucs_mpa, geo.rqd_percent, geo.notes) == ("Granite", 125, 72, "Legacy note")
    assert geo.q_value is None and geo.gsi is None and geo.ff is None and geo.jw is None and geo.joint_sets == []
    assert not hasattr(geo, "geotechnical_domain")


def test_new_geomechanics_payload_round_trip_and_precedence():
    blast = event(); card, draft = new_technical_card(blast)
    draft.geomechanical_parameters = GeomechanicalParameters(
        lithology="Granodiorite", ucs_mpa=145, q_value=6.5, rqd_percent=78,
        gsi=62, ff=9, joint_sets=[JointSetOrientation(70, 110), JointSetOrientation(45, 250)],
        jw=0.66, notes="Moderately jointed")
    card.save_revision(draft); payload = json.loads(json.dumps(card.to_dict()))
    payload["revisions"][0]["geomechanical_parameters"].update(
        representative_ucs_mpa=1, rqd_representative_percent=2, geomechanical_notes="old")
    geo = type(card).from_dict(payload).active_revision().geomechanical_parameters
    assert (geo.lithology, geo.ucs_mpa, geo.q_value, geo.rqd_percent, geo.gsi, geo.ff, geo.jw, geo.notes) == (
        "Granodiorite", 145, None, 78, 62, 9, 0.66, "Moderately jointed")
    assert geo.joint_sets == [JointSetOrientation(70, 110), JointSetOrientation(45, 250)]
    assert all(isinstance(item, JointSetOrientation) for item in geo.joint_sets)


def test_q_system_sources_round_trip_without_persisting_manual_q():
    blast = event(); card, draft = new_technical_card(blast)
    draft.geomechanical_parameters = GeomechanicalParameters(
        rqd_percent=72, ff=10, jn=6, jr=3, ja=2, jw=0.66, q_value=99)
    card.save_revision(draft)
    payload = card.to_dict()["revisions"][0]["geomechanical_parameters"]
    assert (payload["rqd_percent"], payload["ff"], payload["jn"], payload["jr"], payload["ja"], payload["jw"]) == (
        72, 10, 6, 3, 2, 0.66)
    assert "q_value" not in payload


def test_invalid_free_form_barton_values_from_brief_pr_draft_load_as_missing():
    blast = event(); card, draft = new_technical_card(blast); card.save_revision(draft)
    payload = card.to_dict(); geo = payload["revisions"][0]["geomechanical_parameters"]
    geo.update(jn=23, jr=23, ja=8, jw=0.8)
    restored = type(card).from_dict(payload).active_revision().geomechanical_parameters
    assert (restored.jn, restored.jr, restored.ja, restored.jw) == (None, None, None, None)


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
    blast = event()
    state = AssessmentDomainState(blast_events=[blast]); service = TechnicalCardService(state)
    card, draft = service.edit_or_create(blast)
    embedded = TechnicalCardEditorWidget(blast, card, draft,
        lambda saved_card, revision, status, _date: saved_card.save_revision(revision, status=status),
        domain_name="North")
    assert embedded.isHidden()
    assert embedded.maximumWidth() == 0 and embedded.maximumHeight() == 0
    extracted = embedded.take_tab("Drilling and charging")
    host = widgets.QWidget(); layout = widgets.QVBoxLayout(host); layout.addWidget(extracted)
    host.show(); app.processEvents()
    assert extracted.isVisibleTo(host)
    assert embedded.editor.lithology.isVisibleTo(embedded.editor) is False  # dialog is intentionally not shown
    assert embedded.editor.ucs is not None
    assert embedded.editor.group_cards_layout.count() >= 1
    assert embedded.editor.completion_status is not None
    embedded.editor.ucs.setValue(123); embedded.editor.ff.setValue(8); embedded.editor.rqd.setValue(72)
    for combo, value in ((embedded.editor.jn, 6), (embedded.editor.jr, 3), (embedded.editor.ja, 2)):
        combo.setCurrentIndex(combo.findData(float(value)))
    assert embedded.save_draft() is True
    restored = AssessmentDomainState.from_dict(json.loads(json.dumps(state.to_dict())))
    geo = restored.technical_cards[0].active_revision().geomechanical_parameters
    assert (geo.ucs_mpa, geo.ff, geo.rqd_percent, geo.jn, geo.jr, geo.ja) == (123, 8, 72, 6, 3, 2)
    host.close(); embedded.deleteLater(); app.processEvents()


def test_visible_technical_card_save_is_one_draft_qpushbutton(monkeypatch):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    test = pytest.importorskip("PySide6.QtTest", exc_type=ImportError)
    core = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from ui.pages.technical_card_widgets import TechnicalCardEditorWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast); statuses = []; warnings = []
    assert draft.validate_completion() == ["Заполните минимальное геомеханическое описание"]
    embedded = TechnicalCardEditorWidget(
        blast, card, draft,
        lambda _card, _revision, status, _date: statuses.append(status),
    )
    monkeypatch.setattr(
        "ui.editors.technical_card_editor.QMessageBox.warning",
        lambda *args: warnings.append(args),
    )
    save = embedded.editor.save_button
    assert isinstance(save, widgets.QPushButton)
    assert save.text() == "Save"
    assert embedded.editor.findChild(widgets.QToolButton, "SplitSaveMenuButton") is None
    assert all(
        action.text() != "Save & complete"
        for menu in embedded.editor.findChildren(widgets.QMenu)
        for action in menu.actions()
    )
    test.QTest.mouseClick(save, core.Qt.MouseButton.LeftButton)
    app.processEvents()
    assert statuses == ["draft"]
    assert warnings == []
    embedded.deleteLater(); app.processEvents()


def test_draft_design_save_preserves_untouched_incomplete_geomechanics(monkeypatch):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast); calls = []; warnings = []
    original_geo = draft.geomechanical_parameters
    dialog = TechnicalCardDialog(blast, card, draft,
        lambda _card, revision, status, _date: calls.append((revision, status)))
    dialog.group_cards.findChild(widgets.QDoubleSpinBox, "spacing_m").setValue(4.5)
    monkeypatch.setattr("ui.editors.technical_card_editor.QMessageBox.warning", lambda *args: warnings.append(args))
    assert dialog._save("draft") is True
    assert calls and calls[0][1] == "draft"
    assert draft.geomechanical_parameters is original_geo
    assert warnings == []
    dialog.deleteLater(); app.processEvents()


def test_draft_execution_save_preserves_untouched_incomplete_geomechanics(monkeypatch):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast); calls = []; warnings = []
    original_geo = draft.geomechanical_parameters
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_args: calls.append(True))
    dialog.execution_notes.setPlainText("Execution checked")
    monkeypatch.setattr("ui.editors.technical_card_editor.QMessageBox.warning", lambda *args: warnings.append(args))
    assert dialog._save("draft") is True
    assert calls == [True]
    assert draft.geomechanical_parameters is original_geo
    assert warnings == []
    dialog.deleteLater(); app.processEvents()


def test_dirty_invalid_geomechanics_still_blocks_draft_save(monkeypatch):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast); calls = []; warnings = []
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_args: calls.append(True))
    dip, direction, _spacing, _persistence = dialog.joint_set_rows[0]
    dip.setValue(45); direction.setValue(direction.minimum())
    monkeypatch.setattr("ui.editors.technical_card_editor.QMessageBox.warning", lambda *args: warnings.append(args))
    assert dialog._geomechanics_dirty is True
    assert dialog._save("draft") is False
    assert calls == [] and warnings
    dialog.close(); app.processEvents()


def test_visible_contour_design_edits_canonical_method_and_spacing():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.technical_card_widgets import TechnicalCardEditorWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event("contour"); card, draft = new_technical_card(blast)
    embedded = TechnicalCardEditorWidget(blast, card, draft, lambda *_: None)
    design_page = embedded.take_tab("Contour drilling")
    host = widgets.QWidget(); layout = widgets.QVBoxLayout(host); layout.addWidget(design_page)
    host.show(); app.processEvents()
    method = design_page.findChild(widgets.QComboBox)
    method = next(combo for combo in design_page.findChildren(widgets.QComboBox)
                  if combo.findData("presplit") >= 0)
    assert method.isVisibleTo(host)
    planned = design_page.findChild(widgets.QGroupBox, "EngineeringCard")
    assert planned is not None and planned.isAncestorOf(method)
    assert design_page.findChild(widgets.QGroupBox, "controlledBlastingMethodPanel") is None
    workspace = design_page.findChild(widgets.QWidget, "EngineeringWorkspace")
    assert workspace.layout().spacing() == 8
    assert embedded.editor.group_cards_layout.spacing() == 8
    method.setCurrentIndex(method.findData("presplit"))
    assert draft.contour_parameters.controlled_blasting_method == "presplit"
    assert draft.validate_completion() == []
    spacing = design_page.findChild(widgets.QDoubleSpinBox, "spacing_m")
    assert spacing is not None and spacing.isVisibleTo(host)
    spacing.setValue(.2); app.processEvents()
    assert draft.drilling_groups[0].spacing_m == .2
    host.close(); embedded.deleteLater(); app.processEvents()


def test_production_design_keeps_existing_spacing_presentation():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)
    spacing = dialog.group_cards.findChild(widgets.QDoubleSpinBox, "spacing_m")
    assert spacing is not None
    spacing.setValue(4.5); assert draft.drilling_groups[0].spacing_m == 4.5
    dialog.close(); app.processEvents()


def test_drilling_summary_ignores_qt_numeric_signal_arguments():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog

    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)
    group = draft.drilling_groups[0]
    controls = {
        name: dialog.group_cards.findChild(
            widgets.QSpinBox if name == "hole_count" else widgets.QDoubleSpinBox,
            name,
        )
        for name in ("hole_count", "diameter_mm", "average_depth_m", "subdrill_m")
    }
    assert all(controls.values())
    controls["average_depth_m"].setValue(12)
    controls["hole_count"].setValue(7)
    controls["diameter_mm"].setValue(102)
    controls["subdrill_m"].setValue(1.5)
    app.processEvents()

    summary = dialog.group_cards.findChild(widgets.QLabel, "drillingChargeSummary")
    assert group.drilling_length() == 84
    assert "Drilling length: 84.000 m" in summary.text()
    assert (group.hole_count, group.diameter_mm, group.subdrill_m) == (7, 102, 1.5)
    dialog.close(); app.processEvents()


def test_drilling_group_uses_explicit_enabled_checkbox():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    group = draft.drilling_groups[0]
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)
    checkbox = dialog.findChild(widgets.QCheckBox, "drillingGroupEnabled")
    assert checkbox is not None and checkbox.text() == "Enabled"
    assert checkbox.isChecked() == group.included
    checkbox.setChecked(not group.included)
    assert group.included == checkbox.isChecked()
    content = dialog.findChild(widgets.QWidget, "drillingGroupContent")
    assert not content.isEnabled() and checkbox.isEnabled()
    checkbox.setChecked(True)
    assert content.isEnabled()
    read_only = TechnicalCardDialog(blast, card, draft, lambda *_: None, read_only=True)
    assert not read_only.findChild(widgets.QCheckBox, "drillingGroupEnabled").isEnabled()
    dialog.close(); read_only.close(); app.processEvents()


def test_actual_group_uses_enabled_checkbox_and_content_host():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    draft.actual_execution.copy_from_design(draft.drilling_groups, draft.id or None, "replace")
    group = draft.actual_execution.actual_drilling_groups[0]
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)
    checkbox = dialog.findChild(widgets.QCheckBox, "actualDrillingGroupEnabled")
    content = dialog.findChild(widgets.QWidget, "actualDrillingGroupContent")
    assert checkbox is not None and content is not None
    checkbox.setChecked(False)
    assert group.included is False and not content.isEnabled() and checkbox.isEnabled()
    checkbox.setChecked(True)
    assert group.included is True and content.isEnabled()
    assert not dialog.findChild(widgets.QGroupBox, "actualDrillingGroupCard").isCheckable()
    read_only = TechnicalCardDialog(blast, card, draft, lambda *_: None, read_only=True)
    assert not read_only.findChild(widgets.QCheckBox, "actualDrillingGroupEnabled").isEnabled()
    dialog.close(); read_only.close(); app.processEvents()


def test_real_geomechanics_ui_is_compact_and_domain_is_read_only():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None, domain_name="North")
    labels = {item.text() for item in dialog.findChildren(widgets.QLabel)}
    required = {"Lithology", "Domain", "UCS", "FF", "RQD", "GSI", "Jn", "Jr", "Ja", "Jw", "Q′",
                "Set", "Dip, °", "Dip direction, °", "North"}
    assert required <= labels
    assert len(dialog.joint_set_rows) == 5
    assert isinstance(dialog.domain_value, widgets.QLabel)
    workspace = dialog.findChild(widgets.QWidget, "geomechanicsWorkspace")
    assert workspace is not None and not isinstance(workspace, widgets.QScrollArea)
    assert dialog.findChild(widgets.QSpinBox, "rockMassFF") is dialog.ff
    assert dialog.findChild(widgets.QSpinBox, "qSystemRQD") is dialog.rqd
    assert not hasattr(dialog, "q_value")
    removed = {"Geotechnical domain", "Local strength class", "Representative UCS",
        "Minimum UCS", "Maximum UCS", "Representative RQD", "Minimum RQD", "Maximum RQD",
        "Rock mass description", "Fracturing", "Water conditions"}
    assert removed.isdisjoint(labels)
    dialog.close(); app.processEvents()


def test_geomechanics_ui_uses_integer_ranges_and_barton_catalogues():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.editors.technical_card_editor import TechnicalCardDialog
    app = widgets.QApplication.instance() or widgets.QApplication([])
    blast = event(); card, draft = new_technical_card(blast)
    dialog = TechnicalCardDialog(blast, card, draft, lambda *_: None)

    assert isinstance(dialog.ucs, widgets.QSpinBox)
    assert isinstance(dialog.ff, widgets.QSpinBox)
    assert isinstance(dialog.gsi, widgets.QSpinBox)
    assert isinstance(dialog.rqd, widgets.QSpinBox)
    assert dialog.gsi.minimum() == 0 and dialog.gsi.maximum() == 100  # 0 is the empty sentinel
    assert dialog.rqd.minimum() == -1 and dialog.rqd.maximum() == 100
    assert dialog.gsi.buttonSymbols() == widgets.QAbstractSpinBox.ButtonSymbols.UpDownArrows

    dip, direction, spacing, persistence = dialog.joint_set_rows[0]
    assert isinstance(dip, widgets.QSpinBox) and (dip.minimum(), dip.maximum()) == (-1, 90)
    assert isinstance(direction, widgets.QSpinBox) and (direction.minimum(), direction.maximum()) == (-1, 359)
    assert isinstance(spacing, widgets.QDoubleSpinBox)
    assert isinstance(persistence, widgets.QDoubleSpinBox)
    dip.setValue(45); direction.setValue(120); spacing.setValue(1.25); persistence.setValue(8.5)
    restored_set = dialog._geomechanics_from_form().joint_sets[0]
    assert (restored_set.spacing_m, restored_set.persistence_m) == (1.25, 8.5)
    dip.setValue(118); direction.setValue(500)
    assert (dip.value(), direction.value()) == (90, 359)

    for combo, allowed in ((dialog.jn, BARTON_JN_VALUES), (dialog.jr, BARTON_JR_VALUES),
                           (dialog.ja, BARTON_JA_VALUES), (dialog.jw, BARTON_JW_VALUES)):
        assert isinstance(combo, widgets.QComboBox)
        assert [combo.itemData(i) for i in range(1, combo.count())] == list(allowed)
        assert combo.itemData(0) is None

    dip.setValue(45); direction.setValue(direction.minimum())
    with pytest.raises(ValueError, match="requires both"):
        dialog._geomechanics_from_form()
    dialog.close(); app.processEvents()
