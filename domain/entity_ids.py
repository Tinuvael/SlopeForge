from __future__ import annotations

from collections.abc import Callable, Collection
from uuid import uuid4

ENTITY_ID_PREFIXES = {
    "block": "BL",
    "contour": "CB",
    "assessment": "AA",
}


def generate_entity_id(
    entity_type: str,
    existing_ids: Collection[str] = (),
    *,
    token_factory: Callable[[], str] | None = None,
    max_attempts: int = 32,
) -> str:
    """Generate one stable compact user-facing ID.

    IDs use a shared ``<TYPE>-<8 HEX>`` principle while database primary keys
    remain internal.  ``existing_ids`` provides deterministic collision handling
    for the current in-memory/project state before persistence uniqueness checks.
    """
    try:
        prefix = ENTITY_ID_PREFIXES[entity_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported entity ID type: {entity_type!r}") from exc

    factory = token_factory or (lambda: uuid4().hex)
    occupied = set(existing_ids)
    for _ in range(max_attempts):
        raw = factory().replace("-", "").upper()
        if len(raw) < 8 or any(ch not in "0123456789ABCDEF" for ch in raw[:8]):
            raise ValueError("Entity ID token factory must provide at least 8 hexadecimal characters")
        candidate = f"{prefix}-{raw[:8]}"
        if candidate not in occupied:
            return candidate
    raise RuntimeError(f"Could not generate a unique {prefix} identifier after {max_attempts} attempts")
