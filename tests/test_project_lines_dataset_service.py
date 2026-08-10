from types import SimpleNamespace

import pytest

from application.state.assessment_domain_state import AssessmentDomainState
from domain.geometry.types import DatamineLine, DataminePoint
from application.services.project_lines import (
    ProjectLinesDatasetService,
    ProjectLinesImportError,
)


def line(identifier, point_count):
    points = [DataminePoint(float(index), 0.0, 610.0, index + 1) for index in range(point_count)]
    return DatamineLine(identifier, points)


def test_degenerate_lines_do_not_create_temporary_dataset(monkeypatch):
    state = AssessmentDomainState()
    monkeypatch.setattr(
        "application.services.project_lines.import_line_geometry",
        lambda *args, **kwargs: SimpleNamespace(lines=[line("empty", 0), line("single", 1)]),
    )
    with pytest.raises(ProjectLinesImportError, match="no suitable lines"):
        ProjectLinesDatasetService(state).import_dataset("degenerate.dxf")
    assert state.datasets == []


def test_mixed_import_keeps_only_drawable_lines(monkeypatch):
    state = AssessmentDomainState()
    imported = [line("single", 1), line("valid", 2)]
    monkeypatch.setattr(
        "application.services.project_lines.import_line_geometry",
        lambda *args, **kwargs: SimpleNamespace(lines=imported),
    )
    dataset, result = ProjectLinesDatasetService(state).import_dataset("mixed.dxf")
    assert result.lines == imported
    assert [item.source_id for item in dataset.lines] == ["valid"]
    assert state.datasets == [dataset]
