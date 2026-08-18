from __future__ import annotations

import re
from datetime import date

import pytest

from application.services.assessment_areas import AssessmentAreaService
from application.services.blast_events import BlastEventService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.entity_ids import generate_entity_id
from domain.geometry.types import PlanPoint, PlanPolygon
from tests.assessment_boundary_fixtures import boundary_from_polygon


ID_PATTERNS = {
    "block": re.compile(r"^BL-[0-9A-F]{8}$"),
    "contour": re.compile(r"^CB-[0-9A-F]{8}$"),
    "assessment": re.compile(r"^AA-[0-9A-F]{8}$"),
}


def test_shared_generator_uses_product_prefixes_and_uppercase_hex() -> None:
    assert generate_entity_id("block", token_factory=lambda: "7f3a91c2deadbeef") == "BL-7F3A91C2"
    assert generate_entity_id("contour", token_factory=lambda: "5d21c8a4deadbeef") == "CB-5D21C8A4"
    assert generate_entity_id("assessment", token_factory=lambda: "0b84f2d1deadbeef") == "AA-0B84F2D1"


def test_generator_retries_collision_deterministically() -> None:
    tokens = iter(("11111111aaaaaaaa", "22222222bbbbbbbb"))
    generated = generate_entity_id(
        "block", {"BL-11111111"}, token_factory=lambda: next(tokens)
    )
    assert generated == "BL-22222222"


def test_generator_rejects_invalid_type_and_bad_token() -> None:
    with pytest.raises(ValueError, match="Unsupported entity ID type"):
        generate_entity_id("unknown")
    with pytest.raises(ValueError, match="hexadecimal"):
        generate_entity_id("block", token_factory=lambda: "not-hex")


def test_generator_fails_cleanly_after_repeated_collisions() -> None:
    with pytest.raises(RuntimeError, match="Could not generate a unique BL identifier"):
        generate_entity_id(
            "block",
            {"BL-AAAAAAAA"},
            token_factory=lambda: "aaaaaaaa12345678",
            max_attempts=2,
        )


def _production_csv(path) -> None:
    path.write_text(
        "XP,YP,ZP,SID,PTN\n"
        "0,0,620,top,1\n"
        "10,0,620,top,2\n"
        "10,10,620,top,3\n"
        "0,0,620,top,4\n",
        encoding="utf-8",
    )


def _contour_csv(path) -> None:
    path.write_text(
        "XP,YP,ZP,SID,PTN\n"
        "0,0,630,h1,1\n"
        "0,0,600,h1,2\n"
        "10,0,632,h2,1\n"
        "10,0,600,h2,2\n",
        encoding="utf-8",
    )


def test_blast_event_creation_generates_type_specific_ids_and_round_trips(tmp_path) -> None:
    production_path = tmp_path / "production.csv"
    contour_path = tmp_path / "contour.csv"
    _production_csv(production_path)
    _contour_csv(contour_path)
    state = AssessmentDomainState()
    service = BlastEventService(state)

    production = service.create_event(
        name="P-1", event_type="production", event_date=date(2026, 8, 18),
        elevation=620, csv_path=production_path,
    )
    contour = service.create_event(
        name="C-1", event_type="contour", event_date=date(2026, 8, 18),
        elevation=630, csv_path=contour_path,
    )

    assert ID_PATTERNS["block"].fullmatch(production.id)
    assert ID_PATTERNS["contour"].fullmatch(contour.id)
    restored = AssessmentDomainState.from_dict(state.to_dict())
    assert [event.id for event in restored.blast_events] == [production.id, contour.id]


def test_assessment_creation_generates_random_aa_id_and_revisions_keep_identity() -> None:
    polygon = PlanPolygon((
        PlanPoint(0, 0), PlanPoint(10, 0), PlanPoint(10, 10),
        PlanPoint(0, 10), PlanPoint(0, 0),
    ))
    state = AssessmentDomainState()
    service = AssessmentAreaService(state)
    area = service.create_area(
        name="North wall",
        assessment_date=date(2026, 8, 18),
        boundary=boundary_from_polygon(polygon, minimum=600, maximum=620),
    )
    original_id = area.id

    assert ID_PATTERNS["assessment"].fullmatch(original_id)
    assert area.active_geometry_revision().id == f"{original_id}-R001"

    service.revise_area(
        area,
        boundary=boundary_from_polygon(polygon, minimum=600, maximum=620),
        change_reason="Boundary check",
    )
    assert area.id == original_id
    assert area.active_geometry_revision().id == f"{original_id}-R002"
    restored = AssessmentDomainState.from_dict(state.to_dict())
    assert restored.assessment_areas[0].id == original_id
