from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from ui.pages import wall_conformance_tab as module
from application.services.wall_conformance import (
    DesignSemanticInspection, SurfaceAttributeValueCount,
)
from domain.wall_conformance import SurfaceRoleMapping
from domain.wall_conformance.models import (
    DesignSection,
    DesignSectionElement,
    DesignVariant,
    RepresentativeElement,
    SectionPoint,
    SectionSegment,
    TransverseProfile,
    WallAlignmentSample,
)
from ui.dialogs.design_surface_semantics_dialog import DesignSurfaceSemanticsDialog


_APP = None


def test_profile_plot_uses_equal_metric_scale() -> None:
    bounds = module.WallProfilePlot._equal_aspect_bounds(
        QRectF(0.0, 0.0, 400.0, 200.0), 0.0, 10.0, 0.0, 10.0
    )
    u_min, u_max, z_min, z_max = bounds

    assert 400.0 / (u_max - u_min) == pytest.approx(
        200.0 / (z_max - z_min)
    )


def test_selected_profile_plot_prepends_display_only_upstream_context() -> None:
    _app()
    berm_start = SectionPoint(-2.0, 20.0, -2.0, 0.0)
    crest = SectionPoint(0.0, 20.0, 0.0, 0.0)
    toe = SectionPoint(4.0, 10.0, 4.0, 0.0)
    face = SectionSegment(crest, toe, 2, "face")
    profile = TransverseProfile(
        WallAlignmentSample(
            0.0, SurfaceVertex(0.0, 0.0, 20.0), (1.0, 0.0), (0.0, 1.0)
        ),
        (face,),
        (),
        DesignSection(
            (DesignSectionElement("face", crest, toe, (2,)),),
            DesignSectionElement("berm", berm_start, crest, (1,)),
        ),
        assessment_u_interval=(0.0, 4.0),
    )
    plot = module.WallProfilePlot()
    plot.set_profile(profile)

    design, actual = plot._geometry()

    assert [segment.semantic_role for segment in design] == ["berm", "face"]
    assert [(segment.start.u, segment.end.u) for segment in design] == [
        (-2.0, 0.0),
        (0.0, 4.0),
    ]
    assert actual == ()
    plot.deleteLater()


def _representative_element(role, start_u, end_u, start_dz, end_dz):
    width = abs(end_u - start_u)
    height = abs(end_dz - start_dz)
    return RepresentativeElement(
        role, start_u, start_dz, end_u, end_dz, width, width, (width, width),
        height, (height, height), None, None,
    )


def test_representative_plot_and_summary_show_context_separately(monkeypatch) -> None:
    _app()
    context = _representative_element("road", -12.0, 0.0, 1.0, 0.0)
    face = _representative_element("face", 0.0, 5.0, 0.0, -10.0)
    variant = DesignVariant("FACE", (0,), (face,), context)
    profile = TransverseProfile(
        WallAlignmentSample(
            0.0, SurfaceVertex(0.0, 0.0, 20.0), (1.0, 0.0), (0.0, 1.0)
        ),
        (), (), DesignSection(()), assessment_u_interval=(0.0, 5.0),
    )
    profile_set = SimpleNamespace(profiles=(profile,), design_variants=(variant,))
    plot = module.WallProfilePlot()
    plot.set_overview(profile_set)

    design, actual = plot._geometry()

    assert [segment.semantic_role for segment in design] == ["road", "face"]
    assert [(segment.start.u, segment.end.u) for segment in design] == [
        (-12.0, 0.0),
        (0.0, 5.0),
    ]
    assert actual == ()

    tab = _tab(monkeypatch)
    tab.result = SimpleNamespace(profile_sections=profile_set)
    tab.variant_selector.addItem(tab._variant_context_label(variant))
    tab._update_representative_summary()
    assert tab.variant_selector.currentText() == "Road context"
    assert "Upstream context · Road · Width 12.0 m" in tab.representative_summary.text()
    assert "Road 1" not in tab.representative_summary.text()
    tab.deleteLater()
    plot.deleteLater()


def _app():
    """Keep one explicit application owner for the whole test module."""
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _surface(dx=0.0):
    vertices = (
        SurfaceVertex(-5 + dx, 0, 10), SurfaceVertex(0 + dx, 0, 10),
        SurfaceVertex(-5 + dx, 20, 10), SurfaceVertex(0 + dx, 20, 10),
        SurfaceVertex(5 + dx, 0, 0), SurfaceVertex(5 + dx, 20, 0),
        SurfaceVertex(10 + dx, 0, 0), SurfaceVertex(10 + dx, 20, 0),
    )
    specs = (((0, 1, 2), 5), ((1, 3, 2), 5), ((1, 4, 3), 2),
             ((4, 5, 3), 2), ((4, 6, 5), 3), ((6, 7, 5), 3))
    return TriangleSurface(
        vertices,
        tuple(SurfaceTriangle(indices, source_attributes={"COLOUR": colour})
              for indices, colour in specs),
    )


def _area():
    return PlanPolygon((PlanPoint(-2, 4), PlanPoint(8, 4), PlanPoint(8, 16),
                        PlanPoint(-2, 16), PlanPoint(-2, 4)))


class _Surfaces:
    storage_available = True

    def __init__(self):
        self.design = SimpleNamespace(logical_id="D", revision_number=2,
                                      source_format="datamine", triangle_count=6)
        self.actual = SimpleNamespace(logical_id="A", revision_number=7,
                                      source_format="dxf", triangle_count=6)

    def current(self, _site_id, kind):
        return self.design if kind == "design" else self.actual

    def load_dataset(self, _site_id, logical_id):
        dataset = self.design if logical_id == "D" else self.actual
        return dataset, SimpleNamespace(surface=_surface(0 if logical_id == "D" else 1))


def _tab(monkeypatch):
    _app()
    monkeypatch.setattr(module, "create_project_surface_dataset_service", lambda _context: _Surfaces())
    return module.WallConformanceTab(object(), 1, _area())


def _complete_alignment(tab):
    tab._begin_alignment_drawing()
    tab.plan._handle_scene_click(0.0, 4.0)
    tab.plan._handle_scene_click(0.0, 16.0)
    assert tab.plan.complete_alignment_drawing() is not None


def test_dataset_metadata_is_separated_and_explicit(monkeypatch):
    tab = _tab(monkeypatch)
    assert tab.design_title.text() == "DESIGN"
    assert "R2" in tab.design_metadata.text()
    assert "DATAMINE" in tab.design_metadata.text()
    assert "6 triangles" in tab.design_metadata.text()
    assert "R7" in tab.actual_metadata.text()
    assert "DXF" in tab.actual_metadata.text()
    tab.deleteLater()
    _app().sendPostedEvents()


def test_calculation_and_plan_click_keep_selection_synchronized(monkeypatch):
    tab = _tab(monkeypatch)
    _complete_alignment(tab)
    tab.spacing.setValue(5.0)
    tab.calculate()
    assert tab.profile_selector.count() > 1
    tab.plan.profile_selected.emit(1)
    assert tab.profile_selector.currentIndex() == 2
    assert tab.plan._selected_index == 1
    assert "Profile 2" in tab.profile_summary.text()
    assert "Chainage" in tab.profile_summary.text()
    assert "+U / profile direction is Design-Face-derived" in tab.profile_vectors.toolTip()
    tab.deleteLater()
    _app().sendPostedEvents()


def test_empty_and_semantic_palette_states_are_explanatory(monkeypatch):
    tab = _tab(monkeypatch)
    assert tab.profile_plot.profile is None
    assert "Face" in tab.semantic_mapping.text()
    light = module.WallProfilePlot._colors()
    _app().setProperty("slopeforgeTheme", "dark")
    dark = module.WallProfilePlot._colors()
    assert light["background"] != dark["background"]
    assert {"face", "berm", "road"} <= dark.keys()
    _app().setProperty("slopeforgeTheme", "light")
    tab.deleteLater()
    _app().sendPostedEvents()


def test_calculated_plan_recolors_all_geometry_without_recalculation(monkeypatch):
    _app().setProperty("slopeforgeTheme", "light")
    tab = _tab(monkeypatch)
    _complete_alignment(tab)
    tab.calculate()
    result_before = tab.result
    light = module.WallConformancePlanWidget._colors()
    assert tab.plan._area_item.pen().color() == light["area"]
    assert tab.plan._alignment_item.pen().color() == light["alignment"]

    _app().setProperty("slopeforgeTheme", "dark")
    tab.plan._apply_theme()
    dark = module.WallConformancePlanWidget._colors()
    assert tab.result is result_before
    assert tab.plan._area_item.pen().color() == dark["area"]
    assert tab.plan._area_item.brush().color() == dark["area_fill"]
    assert tab.plan._alignment_item.pen().color() == dark["alignment"]
    assert all(
        item.pen().color() in (dark["profile"], dark["selected"])
        for item in tab.plan._profile_items
    )
    _app().setProperty("slopeforgeTheme", "light")
    tab.deleteLater()
    _app().sendPostedEvents()


def test_legends_render_at_compact_minimum_width(monkeypatch):
    tab = _tab(monkeypatch)
    _complete_alignment(tab)
    tab.calculate()
    tab.profile_plot.resize(tab.profile_plot.minimumWidth(), 300)
    tab.profile_plot.show()
    _app().processEvents()
    image = tab.profile_plot.grab().toImage()
    assert not image.isNull()
    assert tab.profile_plot.minimumWidth() == 340
    assert tab.plan.legend.wordWrap()
    assert tab.plan.legend.sizePolicy().horizontalPolicy().name == "Ignored"
    tab.deleteLater()
    _app().sendPostedEvents()


def test_semantics_dialog_lists_counts_and_saves_through_service():
    class Service:
        saved = None

        def inspect_design_semantics(self, _site_id):
            return DesignSemanticInspection(
                SimpleNamespace(logical_id="D", revision_number=4),
                {"COLOUR": (
                    SurfaceAttributeValueCount(2, 12_450),
                    SurfaceAttributeValueCount(5, 8_620),
                    SurfaceAttributeValueCount(7, 120),
                )},
                SurfaceRoleMapping("COLOUR", ((2, "face"), (5, "berm"))),
                False,
            )

        def save_design_semantics(self, site_id, logical_id, mapping):
            self.saved = (site_id, logical_id, mapping)

    service = Service()
    dialog = DesignSurfaceSemanticsDialog(service, 1)
    assert dialog.table.rowCount() == 3
    assert dialog.table.item(0, 1).text() == "12,450"
    assert "Unknown: 120" in dialog.summary.text()
    dialog._save()
    assert service.saved[:2] == (1, "D")
    assert service.saved[2].resolve({"COLOUR": 2}) == "face"
    dialog.deleteLater()
    _app().sendPostedEvents()


def test_engineering_parameter_labels_and_legend_contract(monkeypatch):
    tab = _tab(monkeypatch)
    labels = [label.text() for label in tab.findChildren(module.QLabel)]
    assert "Strike smoothing radius" not in labels
    assert "Section extent" not in labels
    assert not hasattr(tab, "tangent_window")
    settings = tab._settings()
    assert settings.spacing_m == tab.spacing.value()
    assert vars(settings) == {"spacing_m": tab.spacing.value()}
    _complete_alignment(tab)
    tab.calculate()
    tab._select_profile(1)
    design_entries, actual_entries = tab.profile_plot._legend_rows(
        tab.profile_plot.profile
    )
    assert [label for label, _ in design_entries] == ["Face", "Berm", "Road"]
    assert actual_entries == (("Survey", "actual"),)
    assert "Design" not in [label for label, _ in (*design_entries, *actual_entries)]
    tab.deleteLater()
    _app().sendPostedEvents()


def test_overview_selected_and_escape_modes_are_distinct(monkeypatch):
    from PySide6.QtTest import QTest

    tab = _tab(monkeypatch)
    _complete_alignment(tab)
    tab.calculate()
    assert tab.profile_plot.mode == "overview"
    assert tab.profile_plot.profile is None
    assert len(tab.profile_plot._geometry()[1]) > len(
        tab.result.profile_sections.profiles[0].actual_segments
    )
    assert "Actual coverage:" in tab.profile_summary.text()
    assert "dZ" in module.tr("dZ (m, local Design crest = 0)")

    tab._select_profile(1)
    exact = tab.result.profile_sections.profiles[0]
    assert tab.profile_plot.mode == "selected"
    assert tab.profile_plot.profile is exact
    assert tab.profile_plot._geometry() == (
        tuple(s for s in exact.design_segments if s.semantic_role != "ignore"),
        exact.actual_segments,
    )
    assert tab.plan._selected_index == 0

    tab.show()
    QTest.keyClick(tab, module.Qt.Key.Key_Escape)
    assert tab.profile_plot.mode == "overview"
    assert tab.plan._selected_index == -1
    assert tab.profile_selector.currentIndex() == 0

    for child in (tab.plan.view, tab.profile_selector, tab.profile_plot):
        tab._select_profile(1)
        child.setFocus()
        QTest.keyClick(child, module.Qt.Key.Key_Escape)
        assert tab.profile_plot.mode == "overview"
        assert tab.plan._selected_index == -1

    # Escape in Overview must not close or otherwise clear the calculated tab.
    tab.profile_selector.setFocus()
    QTest.keyClick(tab.profile_selector, module.Qt.Key.Key_Escape)
    assert tab.isVisible()
    assert tab.result is not None
    tab.deleteLater()
    _app().sendPostedEvents()


def test_mapping_summary_keeps_multiple_values_and_save_clears_stale_plan(monkeypatch):
    tab = _tab(monkeypatch)
    _complete_alignment(tab)
    tab.calculate()
    assert tab.plan.scene.items()
    tab.service.surface_service.design.semantic_mapping_json = {
        "attribute_name": "COLOUR",
        "assignments": [
            {"value": 9, "role": "face"}, {"value": 2, "role": "face"},
            {"value": 6, "role": "face"}, {"value": 5, "role": "berm"},
            {"value": 3, "role": "road"},
        ],
    }
    tab._refresh_dataset_metadata()
    assert "Face=2,6,9" in tab.semantic_mapping.text()
    tab.plan.clear_result()
    tab.result = None
    tab.profile_plot.set_profile(None)
    assert tab.plan._area_item is not None
    assert tab.plan._alignment_item is not None
    assert tab.profile_plot.mode == "empty"
    tab.deleteLater()
    _app().sendPostedEvents()


def test_initial_alignment_workflow_and_clear_preserve_assessment(monkeypatch):
    tab = _tab(monkeypatch)
    assert tab.plan._area_item is not None
    assert tab.plan.wall_alignment is None
    assert not tab.calculate_button.isEnabled()
    _complete_alignment(tab)
    assert tab.calculate_button.isEnabled()
    tab.calculate()
    assert tab.result is not None
    tab._clear_wall_alignment()
    assert tab.plan.wall_alignment is None
    assert tab.result is None
    assert not tab.calculate_button.isEnabled()
    assert tab.plan._area_item is not None
    tab.deleteLater()
    _app().sendPostedEvents()


def test_double_click_completes_alignment_and_escape_keeps_existing_alignment(monkeypatch):
    tab = _tab(monkeypatch)
    _complete_alignment(tab)
    existing = tab.plan.wall_alignment
    tab._begin_alignment_drawing()
    tab.plan._handle_scene_click(1.0, 4.0)
    tab.plan._complete_draft_from_double_click(1.0, 16.0)
    assert tab.plan.wall_alignment != existing
    replacement = tab.plan.wall_alignment
    tab._begin_alignment_drawing()
    tab.plan._handle_scene_click(2.0, 4.0)
    tab.plan.cancel_alignment_drawing()
    assert tab.plan.wall_alignment == replacement
    tab.deleteLater()
    _app().sendPostedEvents()
