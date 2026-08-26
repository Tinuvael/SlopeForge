from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from ui.pages import wall_conformance_tab as module


_APP = None


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
    tab.spacing.setValue(5.0)
    tab.calculate()
    assert tab.profile_selector.count() > 1
    tab.plan.profile_selected.emit(1)
    assert tab.profile_selector.currentIndex() == 1
    assert tab.plan._selected_index == 1
    assert "Profile 2" in tab.profile_summary.text()
    assert "Chainage" in tab.profile_summary.text()
    assert "T (" in tab.profile_vectors.toolTip()
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
