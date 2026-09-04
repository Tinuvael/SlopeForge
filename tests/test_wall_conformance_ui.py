from __future__ import annotations

import os
from dataclasses import replace
from math import hypot
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget
from PySide6.QtCore import QRectF

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from ui.pages import wall_conformance_tab as module
from application.services.wall_conformance import (
    DesignSemanticInspection, SurfaceAttributeValueCount,
)
from domain.wall_conformance import AlignmentPlacementDiagnostic, SurfaceRoleMapping
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


def test_profile_plot_keeps_equal_scale_but_allocates_spare_u_range_rightward() -> None:
    u_min, u_max, z_min, z_max = module.WallProfilePlot._equal_aspect_bounds(
        QRectF(0.0, 0.0, 400.0, 200.0), 0.0, 10.0, 0.0, 10.0
    )

    assert 400.0 / (u_max - u_min) == pytest.approx(200.0 / (z_max - z_min))
    assert abs(u_min) < abs(u_max - 10.0)


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
    angle = 65.0 if role == "face" else None
    return RepresentativeElement(
        role, start_u, start_dz, end_u, end_dz, width, width, (width, width),
        height, (height, height), angle, (angle, angle) if angle is not None else None,
    )


def test_representative_plot_and_schedule_show_context_separately(monkeypatch) -> None:
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
    tab._show_representative_details()
    assert tab.variant_selector.currentText() == "Road context"
    assert tab.details_title.text() == "Representative Design"
    detail_text = [label.text() for label in tab.details_content.findChildren(module.QLabel)]
    assert "Upstream Road" in detail_text
    assert "W 12.0 m" in detail_text
    assert "H / A" in detail_text
    assert any("H 10.0 m · A 65.0°" in text for text in detail_text)
    assert "Lower toe" in detail_text
    assert tab.details_metadata.toolTip() == "FACE"
    tab.deleteLater()
    plot.deleteLater()


def test_profile_schedule_uses_compact_design_geometry_rows(monkeypatch) -> None:
    _app()
    origin = SurfaceVertex(0.0, 0.0, 20.0)
    crest = SectionPoint(0.0, 20.0, 0.0, 0.0)
    berm_end = SectionPoint(3.0, 20.0, 3.0, 0.0)
    toe = SectionPoint(8.0, 10.0, 8.0, 0.0)
    profile = TransverseProfile(
        WallAlignmentSample(71.7, origin, (1.0, 0.0), (0.0, 1.0)),
        (),
        (),
        DesignSection(
            (
                DesignSectionElement("berm", crest, berm_end, (1,)),
                DesignSectionElement("face", berm_end, toe, (2,)),
            )
        ),
    )
    tab = _tab(monkeypatch)
    tab.profile_selector.addItem("Profile 1")
    tab.profile_selector.setCurrentIndex(1)
    tab._show_profile_details(profile)

    labels = [label.text() for label in tab.details_content.findChildren(module.QLabel)]
    assert "Design" in labels
    assert "Berm 1" in labels
    assert "Face 1" in labels
    assert "H / A" in labels
    assert "Lower toe" in labels
    assert "Chainage" not in labels
    assert "Assessment span" not in labels
    assert any("H 10.0 m · A" in label for label in labels)
    assert any("U 8.0 m · Z 10.0 m" in label for label in labels)
    assert tab.details_rows.rowStretch(tab._detail_stretch_row) == 1
    assert all(
        tab.details_rows.rowStretch(row) == 0
        for row in range(tab._detail_stretch_row)
    )
    tab.deleteLater()


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
    assert tab.details_title.text() == "Profile 2"
    assert tab.details_metadata.text().startswith("Ch.")
    assert "Design" in [label.text() for label in tab.details_content.findChildren(module.QLabel)]
    assert tab.plan._direction_annotation is not None
    assert tab.plan.view._direction_annotation is not None
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
    assert tab.profile_legend.wordWrap()
    assert tab.profile_legend.sizePolicy().horizontalPolicy().name == "Ignored"
    assert "Skipped station" not in tab.plan.legend.text()
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
    assert tab.set_alignment_button.text() == "Edit Wall Alignment"
    assert "2 vertices" in tab.alignment_metadata.text()
    assert tab.calculate_button.isEnabled()
    tab.calculate()
    assert tab.result is not None
    tab._clear_wall_alignment()
    assert tab.plan.wall_alignment is None
    assert tab.result is None
    assert not tab.calculate_button.isEnabled()
    assert tab.set_alignment_button.text() == "Set Wall Alignment"
    assert tab.plan._area_item is not None
    tab.deleteLater()
    _app().sendPostedEvents()


def test_two_pane_workspace_uses_matching_canvas_hosts_and_wider_plan(monkeypatch):
    tab = _tab(monkeypatch)
    tab.resize(1600, 860)
    tab.show()
    _app().processEvents()

    assert tab.splitter.count() == 2
    assert tab.plan.minimumWidth() == 480
    assert tab.plan.maximumWidth() == 720
    assert tab.splitter.sizes()[0] in range(580, 641)
    assert tab.splitter.sizes()[1] > tab.splitter.sizes()[0]
    assert isinstance(tab.plan.plan_canvas, module.WallCanvasHost)
    assert isinstance(tab.profile_canvas, module.WallCanvasHost)
    assert tab.plan.legend.parentWidget() is tab.plan.plan_header
    assert tab.profile_legend.parentWidget() is tab.profile_header
    assert tab.plan.plan_header.parentWidget() is tab.plan.plan_canvas
    assert tab.profile_header.parentWidget() is tab.profile_canvas
    assert tab.details_schedule.parentWidget() is tab.profile_canvas.drawing_body
    assert tab.details_schedule.isHidden()
    tab.deleteLater()
    _app().sendPostedEvents()


def test_result_status_variant_elision_and_representative_schedule(monkeypatch):
    tab = _tab(monkeypatch)
    tab.resize(1600, 860)
    tab.show()
    _complete_alignment(tab)
    tab.calculate()
    _app().processEvents()

    assert "profiles" in tab.status.text()
    assert "coverage" in tab.status.text()
    assert "FACE-BERM" not in tab.variant_selector.currentText()
    assert tab.variant_selector.itemData(0, module.Qt.ItemDataRole.ToolTipRole)
    assert tab.details_title.text() == "Representative Design"
    assert not tab.details_schedule.isHidden()
    assert 260 <= tab.details_schedule.width() <= 320
    assert tab.profile_canvas.drawing_body.layout().count() == 2
    assert tab.profile_canvas.drawing_body.layout().itemAt(0).widget() is tab.profile_plot
    assert tab.profile_canvas.drawing_body.layout().itemAt(1).widget() is tab.details_schedule
    assert tab.details_schedule.x() == tab.profile_plot.geometry().right() + 1
    assert tab.details_schedule.height() == tab.profile_plot.height()
    assert (
        tab.details_scroll.verticalScrollBarPolicy()
        == module.Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert (
        tab.details_scroll.horizontalScrollBarPolicy()
        == module.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert not tab.findChildren(QTableWidget)
    bounds = tab.profile_plot._equal_aspect_bounds(
        tab.profile_plot.plot_rect(), 0.0, 10.0, 0.0, 20.0
    )
    assert tab.profile_plot.plot_rect().width() / (bounds[1] - bounds[0]) == pytest.approx(
        tab.profile_plot.plot_rect().height() / (bounds[3] - bounds[2])
    )
    assert tab.details_schedule.background_color() == tab.profile_plot._colors()["background"]
    tab.deleteLater()
    _app().sendPostedEvents()


def test_profile_schedule_visibility_changes_only_the_drawing_body_width(monkeypatch):
    tab = _tab(monkeypatch)
    tab.resize(1600, 860)
    tab.show()
    _complete_alignment(tab)
    tab.calculate()
    _app().processEvents()

    before = tab.profile_plot.geometry()
    tab._clear_details()
    _app().processEvents()
    assert tab.profile_plot.width() > before.width()
    tab._show_representative_details()
    _app().processEvents()
    assert tab.profile_plot.width() == before.width()
    assert tab.profile_canvas.canvas is tab.profile_canvas.drawing_body
    assert tab.profile_canvas.drawing_body.profile_plot is tab.profile_plot
    tab.deleteLater()
    _app().sendPostedEvents()


def test_profile_legend_is_a_widget_and_selected_u_annotation_does_not_fit_scene(monkeypatch):
    tab = _tab(monkeypatch)
    tab.resize(1600, 860)
    tab.show()
    _complete_alignment(tab)
    tab.calculate()
    _app().processEvents()

    assert "DESIGN" in tab.profile_legend.text()
    assert "ACTUAL" in tab.profile_legend.text()
    assert tab.profile_legend.parentWidget() is tab.profile_header
    assert not hasattr(module.WallProfilePlot, "_draw_legend_row")
    before = tab.plan.scene.itemsBoundingRect()
    before_scrollbars = (
        tab.plan.view.horizontalScrollBar().minimum(),
        tab.plan.view.horizontalScrollBar().maximum(),
        tab.plan.view.verticalScrollBar().minimum(),
        tab.plan.view.verticalScrollBar().maximum(),
    )
    tab._select_profile(1)
    after = tab.plan.scene.itemsBoundingRect()
    assert tab.plan._direction_annotation is not None
    assert after == before
    assert (
        tab.plan.view.horizontalScrollBar().minimum(),
        tab.plan.view.horizontalScrollBar().maximum(),
        tab.plan.view.verticalScrollBar().minimum(),
        tab.plan.view.verticalScrollBar().maximum(),
    ) == before_scrollbars
    first_start, first_end = tab.plan.view.direction_annotation_screen_points()
    first_length = hypot(first_end.x() - first_start.x(), first_end.y() - first_start.y())
    tab.plan.view.scale(1.6, 1.6)
    second_start, second_end = tab.plan.view.direction_annotation_screen_points()
    second_length = hypot(second_end.x() - second_start.x(), second_end.y() - second_start.y())
    assert first_length == pytest.approx(22.0, abs=1.0)
    assert second_length == pytest.approx(first_length, abs=1.0)
    tab.deleteLater()
    _app().sendPostedEvents()


def test_profile_annotation_does_not_change_equal_aspect_framing():
    plot = module.WallProfilePlot()
    full = QRectF(0.0, 0.0, 900.0, 500.0)
    bounds = plot._equal_aspect_bounds(full, 0.0, 10.0, 0.0, 20.0)

    assert full.width() / (bounds[1] - bounds[0]) == pytest.approx(
        full.height() / (bounds[3] - bounds[2])
    )
    assert bounds[0] <= 0.0 <= bounds[1]
    assert bounds[0] <= 10.0 <= bounds[1]
    assert bounds[2] <= 0.0 <= bounds[3]
    assert bounds[2] <= 20.0 <= bounds[3]
    plot.deleteLater()


def test_profile_schedule_stays_beside_plot_after_resize(monkeypatch):
    tab = _tab(monkeypatch)
    tab.resize(1366, 768)
    tab.show()
    _complete_alignment(tab)
    tab.calculate()
    tab._select_profile(1)
    _app().processEvents()

    assert tab.details_title.text() == "Profile 1"
    first = tab.details_schedule.geometry()
    tab.resize(1920, 1080)
    _app().processEvents()
    second = tab.details_schedule.geometry()
    assert second.x() == tab.profile_plot.geometry().right() + 1
    assert second.top() == tab.profile_plot.geometry().top()
    assert second.bottom() == tab.profile_plot.geometry().bottom()
    assert second.x() >= first.x()
    tab.deleteLater()
    _app().sendPostedEvents()


def test_skipped_station_marker_and_tooltip_are_presentation_only(monkeypatch):
    tab = _tab(monkeypatch)
    _complete_alignment(tab)
    tab.calculate()
    before_extent = tab.plan.scene.itemsBoundingRect()
    diagnostic = AlignmentPlacementDiagnostic(
        "insufficient_face_support", "Insufficient Design Face support", 1, 5.0
    )
    tab.result = replace(tab.result, diagnostics=(diagnostic,))
    tab.plan.set_result(tab.result)

    assert len(tab.plan._skipped_annotations) == 1
    assert "Profile skipped" in tab.plan._skipped_annotations[0][1]
    assert tab.plan.scene.itemsBoundingRect() == before_extent
    assert "Skipped station" in tab.plan.legend.text()
    assert "1 skipped" in tab._result_status_text()
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
