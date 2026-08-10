from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from domain.project.project_lines import ProjectLinesDataset
from domain.blasting.entities import BlastEvent
from domain.assessment.entities import AssessmentArea
from domain.attachments.entities import EntityAttachment
from domain.blasting.technical_card import BlastEventTechnicalCard
from domain.assessment.evaluation import AssessmentAreaEvaluation

@dataclass
class AssessmentDomainState:
    datasets: list[ProjectLinesDataset] = field(default_factory=list)
    blast_events: list[BlastEvent] = field(default_factory=list)
    assessment_areas: list[AssessmentArea] = field(default_factory=list)
    technical_cards: list[Any] = field(default_factory=list)
    evaluations: list[Any] = field(default_factory=list)
    attachments: list[EntityAttachment] = field(default_factory=list)

    def add_dataset(self, dataset: ProjectLinesDataset, make_active: bool = True) -> None:
        if any(item.id == dataset.id for item in self.datasets):
            raise ValueError(f"Dataset {dataset.id!r} already exists")
        if make_active:
            for item in self.datasets:
                item.is_active = False
            dataset.is_active = True
        self.datasets.append(dataset)

    def active_dataset(self) -> ProjectLinesDataset | None:
        return next((dataset for dataset in self.datasets if dataset.is_active), None)

    def active_blast_events(self) -> list[BlastEvent]:
        return [event for event in self.blast_events if not event.is_archived]

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasets": [dataset.to_dict() for dataset in self.datasets],
            "blast_events": [event.to_dict() for event in self.blast_events],
            "assessment_areas": [area.to_dict() for area in self.assessment_areas],
            "technical_cards": [card.to_dict() for card in self.technical_cards],
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssessmentDomainState":
        return cls(
            datasets=[ProjectLinesDataset.from_dict(item) for item in data.get("datasets", [])],
            blast_events=[BlastEvent.from_dict(item) for item in data.get("blast_events", [])],
            assessment_areas=[AssessmentArea.from_dict(item) for item in data.get("assessment_areas", [])],
            technical_cards=[BlastEventTechnicalCard.from_dict(item) for item in data.get("technical_cards", [])],
            evaluations=[AssessmentAreaEvaluation.from_dict(item) for item in data.get("evaluations", [])],
            attachments=[EntityAttachment.from_dict(item) for item in data.get("attachments", [])],
        )
