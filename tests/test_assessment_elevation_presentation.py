from pathlib import Path

from ui.presentation_labels import format_assessment_elevation_interval


def test_assessment_interval_rounds_for_display_only():
    minimum = 630.0
    maximum = 655.363961338486
    assert format_assessment_elevation_interval(minimum, maximum) == "630–655 m"
    assert format_assessment_elevation_interval(None, maximum) == "—"
    assert (minimum, maximum) == (630.0, 655.363961338486)


def test_normal_area_page_uses_canonical_formatter_for_displayed_interval():
    source = Path("ui/pages/assessment_area_page.py").read_text(encoding="utf-8")
    assert source.count("format_assessment_elevation_interval(") >= 1
    assert "interval = format_assessment_elevation_interval(rev.min_elevation, rev.max_elevation)" in source
    assert 'f"{tr(\'Interval\')}: {interval}"' in source
    assert "_value(rev.min_elevation)" not in source
    assert "_value(rev.max_elevation)" not in source
