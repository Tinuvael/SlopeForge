from datetime import date, datetime, timezone
from math import sqrt
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from ui.pages.assessment_area_page import AssessmentAreaPage, AssessmentLinkListItem
    from ui.pages.plan_geometry_widget import PlanGeometryWidget
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

from application.services.assessment_event_links import AssessmentEventLinkService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.assessment.entities import AssessmentArea
from domain.blasting.entities import BlastEvent
from domain.geometry.types import PlanPoint, PlanPolygon
from tests.assessment_boundary_fixtures import geometry_revision


def polygon(*coordinates):
    points = tuple(PlanPoint(*xy) for xy in coordinates)
    return PlanPolygon(points + (points[0],))


def scenario():
    area_geometry = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    area_revision = geometry_revision("AA-R1", "AA", 1, datetime(2026, 1, 1, tzinfo=timezone.utc), area_geometry, dataset_id="D-1", minimum=600, maximum=630)
    area = AssessmentArea("AA", "Area", date(2026, 1, 1), [area_revision], area_revision.id)
    r1_geometry = polygon((1, 1), (3, 1), (3, 3), (1, 3))
    event = BlastEvent("BE", "Blast", "production", None, 610)
    event.add_geometry_revision(source_file_name="r1.csv", source_geometry=[], plan_geometry=r1_geometry, elevation=610)
    project_line = SimpleNamespace(points=(PlanPoint(-200, 0), PlanPoint(200, 0)))
    dataset = SimpleNamespace(id="D-1", lines=[project_line])
    state = AssessmentDomainState(blast_events=[event], assessment_areas=[area], datasets=[dataset])
    links = AssessmentEventLinkService(state); links.refresh_suggestions(area)
    return state, links, area, event, area.event_links[0], area_geometry, r1_geometry, project_line


class LabelStub:
    def setText(self, value): self.text = value
    def clear(self): self.text = ""
    def hide(self): self.visible = False
    def setVisible(self, value): self.visible = value


def fake_page(state, links, area, link):
    received=[]
    preview=SimpleNamespace(set_comparison_geometry=lambda *args,**kwargs:received.append((args,kwargs)))
    label=LabelStub()
    page=SimpleNamespace(_selected_link=lambda:link,controller=SimpleNamespace(links=links,state=state),area=area,link_preview=preview,_link_preview_initialized=True,link_event_name=label,link_event_detail=LabelStub(),link_event_type=LabelStub(),link_status_line=LabelStub(),link_warning=LabelStub())
    return page,received


def test_linked_events_uses_compact_master_detail_list_not_table():
    source=Path("ui/pages/assessment_area_page.py").read_text(encoding="utf-8")
    block=source[source.index("    def _linked_events"):source.index("    def _attachment_tab")]
    assert "QListWidget" in block and "links_list" in block
    assert "QTableWidget" not in block and "setHorizontalHeaderLabels" not in block
    assert "setMaximumWidth(380)" in block
    assert "setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)" in block
    assert "setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)" in block
    assert "detail_layout.addWidget(legend)" not in block
    assert "self.link_preview.set_context(legend)" in block


@pytest.mark.parametrize("status,expected_color",[("suggested","#fff8e6"),("confirmed","#edf8f0"),("excluded","#f3f4f6")])
def test_link_item_has_distinct_workflow_presentation(status,expected_color):
    app=QApplication.instance() or QApplication([]); _=app
    state,links,area,event,link,*_=scenario(); link.status=status
    widget=AssessmentLinkListItem(event,link,stale=True)
    assert widget.workflow_status==status and widget.is_stale
    assert expected_color in widget.styleSheet()
    assert "StaleBadge" in widget.styleSheet()
    widget.set_selected(True)
    assert "#2563a6" in widget.styleSheet()


def test_preview_keeps_frozen_revision_stale_state_and_project_lines():
    state,links,area,event,link,area_geometry,r1_geometry,project_line=scenario(); r1_id=link.geometry_revision_id
    event.add_geometry_revision(source_file_name="r2.csv",source_geometry=[],plan_geometry=polygon((6,6),(8,6),(8,8),(6,8)),elevation=610)
    page,received=fake_page(state,links,area,link)
    AssessmentAreaPage.refresh_link_preview(page)
    args,kwargs=received[0]
    assert args[:3]==(area_geometry,r1_geometry,[project_line])
    assert kwargs["recenter"] is False and kwargs["focus_geometry"]==area_geometry
    assert r1_id in page.link_event_detail.text
    assert "Suggested" in page.link_status_line.text and "Stale" in page.link_status_line.text


def test_missing_frozen_revision_never_substitutes_current_geometry():
    state,links,area,event,link,area_geometry,_r1,project_line=scenario(); current=event.active_geometry_revision().plan_geometry; link.geometry_revision_id="MISSING"
    page,received=fake_page(state,links,area,link); AssessmentAreaPage.refresh_link_preview(page)
    args,_kwargs=received[0]
    assert args[:3]==(area_geometry,None,[project_line]) and args[1]!=current
    assert page.link_warning.visible and "not substituted" in page.link_warning.text


def test_comparison_overlay_update_preserves_camera_and_center_restores_focus():
    app=QApplication.instance() or QApplication([]); widget=PlanGeometryWidget(); widget.resize(800,500); widget.show(); app.processEvents()
    area=polygon((0,0),(10,0),(10,10),(0,10)); event1=polygon((2,2),(4,2),(4,4),(2,4)); event2=polygon((7,7),(9,7),(9,9),(7,9)); far_line=SimpleNamespace(points=(PlanPoint(-200,0),PlanPoint(200,0)))
    widget.use_center_control(); widget.set_comparison_geometry(area,event1,[far_line],focus_geometry=area,recenter=True)
    canonical=widget.canonical_focus_rect
    assert canonical.width()==pytest.approx(10*sqrt(2)) and canonical.height()==pytest.approx(10*sqrt(2))
    assert len(widget._project_items)==1
    assert abs(abs(widget.view.transform().m11())-abs(widget.view.transform().m22()))<1e-9
    widget.view.scale(1.7,1.7); widget.view.centerOn(80,40); before=widget.view.transform(); center_before=widget.view.mapToScene(widget.view.viewport().rect().center())
    widget.set_comparison_geometry(area,event2,[far_line],focus_geometry=area,recenter=False); center_after=widget.view.mapToScene(widget.view.viewport().rect().center())
    assert widget.view.transform()==before
    assert center_after.x()==pytest.approx(center_before.x(),abs=.5) and center_after.y()==pytest.approx(center_before.y(),abs=.5)
    widget.center_on_focus()
    assert abs(abs(widget.view.transform().m11())-abs(widget.view.transform().m22()))<1e-9
    visible=widget.view.mapToScene(widget.view.viewport().rect()).boundingRect()
    assert visible.contains(canonical.center()) and visible.width()<100


def test_assessment_overview_uses_centered_focus_geometry():
    source=Path("ui/pages/assessment_area_page.py").read_text(encoding="utf-8")
    overview=source[source.index("    def _overview"):source.index("    def _refresh_overview")]
    assert "use_center_control()" in overview
    assert "focus_geometry=rev.final_geometry_frozen" in overview


def test_read_only_only_disables_mutations_not_list_or_center():
    source=Path("ui/pages/assessment_area_page.py").read_text(encoding="utf-8")
    block=source[source.index("    def _linked_events"):source.index("    def refresh_links")]
    assert "self.links_list.setEnabled(False)" not in block
    assert "self.link_preview.use_center_control()" in block
    assert "button.setEnabled(not self.read_only)" in block


def test_show_on_plan_navigation_contract_is_removed():
    assert not hasattr(AssessmentAreaPage,"show_link_on_plan")
