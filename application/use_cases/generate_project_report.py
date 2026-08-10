from dataclasses import dataclass
from datetime import date
from pathlib import Path

from application.ports.project_report import ProjectReportQuery, ProjectReportWriter


@dataclass(frozen=True)
class GenerateProjectReportCommand:
    site_id: int
    from_date: date
    to_date: date
    output_path: str | Path


@dataclass(frozen=True)
class GenerateProjectReportResult:
    output_path: Path


class GenerateProjectReport:
    def __init__(self, query: ProjectReportQuery, writer: ProjectReportWriter):
        self._query, self._writer = query, writer

    def execute(self, command: GenerateProjectReportCommand) -> GenerateProjectReportResult:
        if command.from_date > command.to_date:
            raise ValueError("From date must not be after To date")
        output = Path(command.output_path)
        report = self._query.collect(command.site_id, command.from_date, command.to_date)
        self._writer.write(report, output)
        return GenerateProjectReportResult(output.resolve())
