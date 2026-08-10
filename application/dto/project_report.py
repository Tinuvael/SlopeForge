from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BlastReportRow:
    report_date: date; event_date: date | None; actual_blast_date: date | None
    domain: str; event_type: str; name: str; block_number: str | None
    horizon: float; archived: bool; technical_card_status: str | None
    actual_volume_m3: float | None; actual_explosive_mass_kg: float | None
    actual_drilling_length_m: float | None


@dataclass(frozen=True)
class AssessmentReportRow:
    name: str; domain: str; assessment_date: date; elevation_interval: str
    geometry_revision: int; evaluation_status: str | None; dai: float | None
    fci: float | None; quadrant: str | None; production_blocks: tuple[str, ...]
    contour_blasts: tuple[str, ...]


@dataclass(frozen=True)
class ProjectReport:
    project: str; from_date: date; to_date: date
    blasts: tuple[BlastReportRow, ...]; assessments: tuple[AssessmentReportRow, ...]

    @property
    def completed_assessments(self):
        return sum(row.evaluation_status == "completed" for row in self.assessments)

    @property
    def average_dai(self):
        values = [row.dai for row in self.assessments if row.evaluation_status == "completed" and row.dai is not None]
        return sum(values) / len(values) if values else None

    @property
    def average_fci(self):
        values = [row.fci for row in self.assessments if row.evaluation_status == "completed" and row.fci is not None]
        return sum(values) / len(values) if values else None
