from __future__ import annotations

from app.localization import tr
from ui.pages.wall_conformance_tab import WallConformanceTab


def install_wall_conformance_tab(assessment_page):
    """Compose the diagnostic tab into an already-built Assessment Area page."""
    revision = assessment_page.area.active_geometry_revision()
    tab = WallConformanceTab(
        assessment_page.context,
        assessment_page.controller.site_id,
        revision.final_geometry_frozen,
        assessment_page,
    )
    assessment_index = assessment_page.tabs.indexOf(assessment_page.assessment_tab)
    insert_index = assessment_index + 1 if assessment_index >= 0 else assessment_page.tabs.count()
    assessment_page.tabs.insertTab(insert_index, tab, tr("Wall conformance"))
    assessment_page.wall_conformance_tab = tab
    return tab
