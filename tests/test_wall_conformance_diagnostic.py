from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.services.wall_conformance import (
    WallConformanceDiagnosticService,
    WallConformanceDiagnosticSettings,
    WallConformanceUnavailableError,
)
from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon


def _bench(dx: float = 0.0) -> TriangleSurface:
    vertices = (
        SurfaceVertex(-5 + dx, 0, 10),
        SurfaceVertex(0 + dx, 0, 10),
        SurfaceVertex(-5 + dx, 20, 10),
        SurfaceVertex(0 + dx, 20, 10),
        SurfaceVertex(5 + dx, 0, 0),
        SurfaceVertex(5 + dx, 20, 0),
        SurfaceVertex(10 + dx, 0, 0),
        SurfaceVertex(10 + dx, 20, 0),
    )
    specifications = (
        ((0, 1, 2), 5),
        ((1, 3, 2), 5),
        ((1, 4, 3), 2),
        ((4, 5, 3), 2),
        ((4, 6, 5), 3),
        ((6, 7, 5), 3),
    )
    return TriangleSurface(
        vertices,
        tuple(
            SurfaceTriangle(indices, source_attributes={"COLOUR": colour})
            for indices, colour in specifications
        ),
    )


def _area() -> PlanPolygon:
    return PlanPolygon(
        (
            PlanPoint(-2, 4),
            PlanPoint(8, 4),
            PlanPoint(8, 16),
            PlanPoint(-2, 16),
            PlanPoint(-2, 4),
        )
    )


class FakeSurfaceService:
    def __init__(self, *, storage_available=True, design=True, actual=True):
        self.storage_available = storage_available
        self.design = (
            SimpleNamespace(
                logical_id="DESIGN-1",
                revision_number=2,
                source_format="datamine",
                triangle_count=6,
            )
            if design
            else None
        )
        self.actual = (
            SimpleNamespace(
                logical_id="ACTUAL-1",
                revision_number=7,
                source_format="datamine",
                triangle_count=6,
            )
            if actual
            else None
        )

    def current(self, _site_id, dataset_kind):
        return self.design if dataset_kind == "design" else self.actual

    def load_dataset(self, _site_id, logical_id):
        if logical_id == "DESIGN-1":
            return self.design, SimpleNamespace(surface=_bench())
        if logical_id == "ACTUAL-1":
            return self.actual, SimpleNamespace(surface=_bench(dx=1.0))
        raise AssertionError(logical_id)


def test_diagnostic_service_loads_active_project_surfaces_and_builds_profiles() -> None:
    service = WallConformanceDiagnosticService(FakeSurfaceService())

    result = service.calculate_current(
        1,
        _area(),
        WallConformanceDiagnosticSettings(
            spacing_m=5.0,
            tangent_window_m=4.0,
        ),
    )

    assert result.design_dataset.logical_id == "DESIGN-1"
    assert result.actual_dataset.logical_id == "ACTUAL-1"
    assert result.profile_set.profiles
    profile = result.profile_set.profiles[0]
    design_points = {
        (round(point.u, 6), round(point.z, 6))
        for segment in profile.design_segments
        for point in (segment.start, segment.end)
    }
    actual_points = {
        (round(point.u, 6), round(point.z, 6))
        for segment in profile.actual_segments
        for point in (segment.start, segment.end)
    }
    assert (0.0, 10.0) in design_points
    assert (1.0, 10.0) in actual_points


def test_diagnostic_service_refuses_database_only_storage_mode() -> None:
    service = WallConformanceDiagnosticService(
        FakeSurfaceService(storage_available=False)
    )

    with pytest.raises(WallConformanceUnavailableError, match="Shared file storage"):
        service.calculate_current(1, _area())


def test_diagnostic_service_reports_missing_active_surface() -> None:
    service = WallConformanceDiagnosticService(FakeSurfaceService(actual=False))

    with pytest.raises(WallConformanceUnavailableError, match="Actual survey"):
        service.calculate_current(1, _area())


class FakeButton:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)

    def isEnabled(self):
        return self.enabled


class FakeLabel:
    def __init__(self, text=""):
        self._text = text

    def setText(self, text):
        self._text = str(text)

    def text(self):
        return self._text


class FakeTabs:
    def __init__(self, entries):
        self.entries = list(entries)

    def indexOf(self, widget):
        try:
            return self.entries.index(widget)
        except ValueError:
            return -1

    def count(self):
        return len(self.entries)

    def insertTab(self, index, widget, label):
        self.entries.insert(index, widget)
        return index

    def tabText(self, index):
        return getattr(self.entries[index], "_tab_label", None)


def _fake_tab_class(surface_service):
    class FakeWallConformanceTab:
        def __init__(self, context, site_id, polygon, parent=None):
            self.context = context
            self.site_id = site_id
            self.polygon = polygon
            self.parent = parent
            self.service = WallConformanceDiagnosticService(surface_service)
            self.calculate_button = FakeButton()
            self.status = FakeLabel("Ready to calculate.")

    return FakeWallConformanceTab


def _fake_assessment_page():
    assessment_tab = object()
    overview = SimpleNamespace(_tab_label="Overview")
    assessment = assessment_tab
    linked = SimpleNamespace(_tab_label="Linked events")
    page = SimpleNamespace(
        context=object(),
        controller=SimpleNamespace(site_id=42),
        area=SimpleNamespace(
            active_geometry_revision=lambda: SimpleNamespace(
                final_geometry_frozen=_area()
            )
        ),
        assessment_tab=assessment_tab,
        tabs=FakeTabs([overview, assessment, linked]),
    )
    return page


def test_installer_places_wall_conformance_after_assessment(monkeypatch) -> None:
    import ui.pages.wall_conformance_install as installer

    monkeypatch.setattr(installer, "set_status_role", lambda label, role: label)
    monkeypatch.setattr(
        installer,
        "WallConformanceTab",
        _fake_tab_class(FakeSurfaceService()),
    )
    page = _fake_assessment_page()

    tab = installer.install_wall_conformance_tab(page)
    tab._tab_label = "Wall conformance"

    assert page.tabs.indexOf(tab) == 2
    assert page.tabs.tabText(2) == "Wall conformance"
    assert page.wall_conformance_tab is tab
    assert tab.site_id == 42
    assert tab.calculate_button.isEnabled()


def test_installer_disables_calculation_when_actual_surface_is_missing(monkeypatch) -> None:
    import ui.pages.wall_conformance_install as installer

    monkeypatch.setattr(installer, "set_status_role", lambda label, role: label)
    monkeypatch.setattr(
        installer,
        "WallConformanceTab",
        _fake_tab_class(FakeSurfaceService(actual=False)),
    )
    page = _fake_assessment_page()

    tab = installer.install_wall_conformance_tab(page)

    assert not tab.calculate_button.isEnabled()
    assert "Actual survey" in tab.status.text()
