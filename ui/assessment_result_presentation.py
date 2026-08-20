from __future__ import annotations

from dataclasses import dataclass

from app.localization import tr


@dataclass(frozen=True)
class AssessmentResultPresentation:
    label: str
    color: str
    severity: int
    requires_attention: bool


# These colours are the canonical four quadrants used by the Assessment matrix.
# Keep dashboards and the full assessment editor on this one presentation palette;
# scoring and thresholds remain owned by the domain/evaluation model.
ASSESSMENT_RESULT_PRESENTATIONS = {
    "geometry_achieved_condition_insufficient": AssessmentResultPresentation(
        "Geometry achieved, condition insufficient", "#f6df72", 2, True
    ),
    "good_results": AssessmentResultPresentation(
        "Good results", "#8bd17c", 0, False
    ),
    "unacceptable": AssessmentResultPresentation(
        "Unacceptable results", "#ef7770", 3, True
    ),
    "condition_good_geometry_unacceptable": AssessmentResultPresentation(
        "Condition good, geometry unacceptable", "#f2b764", 2, True
    ),
}

UNKNOWN_ASSESSMENT_RESULT = AssessmentResultPresentation(
    "No completed assessment", "#94a3b8", 0, False
)


def assessment_result_presentation(value: str | None) -> AssessmentResultPresentation:
    presentation = ASSESSMENT_RESULT_PRESENTATIONS.get(value)
    if presentation is None:
        if not value:
            return AssessmentResultPresentation(
                tr(UNKNOWN_ASSESSMENT_RESULT.label),
                UNKNOWN_ASSESSMENT_RESULT.color,
                UNKNOWN_ASSESSMENT_RESULT.severity,
                UNKNOWN_ASSESSMENT_RESULT.requires_attention,
            )
        label = str(value).replace("_", " ").title()
        return AssessmentResultPresentation(tr(label), "#94a3b8", 0, False)
    return AssessmentResultPresentation(
        tr(presentation.label),
        presentation.color,
        presentation.severity,
        presentation.requires_attention,
    )
