from datetime import date
from pathlib import Path
from typing import Protocol

from application.dto.project_report import ProjectReport


class ProjectReportQuery(Protocol):
    def collect(self, site_id: int, from_date: date, to_date: date) -> ProjectReport: ...


class ProjectReportWriter(Protocol):
    def write(self, report: ProjectReport, output_path: str | Path) -> None: ...
