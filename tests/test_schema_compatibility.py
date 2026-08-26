from database.schema_compatibility import (
    SchemaCompatibilityState,
    classify_schema_compatibility,
)


def _state(current, *, required="3", known=frozenset({"1", "2", "3"})):
    return classify_schema_compatibility(tuple(current), required, known).state


def test_exact_required_head_is_up_to_date() -> None:
    assert _state(("3",)) == SchemaCompatibilityState.UP_TO_DATE


def test_known_ancestor_requires_upgrade() -> None:
    assert _state(("1",)) == SchemaCompatibilityState.UPGRADE_REQUIRED
    assert _state(("2",)) == SchemaCompatibilityState.UPGRADE_REQUIRED


def test_numeric_revision_above_release_requires_newer_application() -> None:
    assert _state(("4",)) == SchemaCompatibilityState.NEWER_THAN_RELEASE


def test_unknown_or_divergent_revision_is_never_assumed_safe_to_migrate() -> None:
    assert _state(("legacy_dev_revision",)) == SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED
    assert _state(("0",)) == SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED
    assert _state(("02",)) == SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED


def test_missing_or_multiple_heads_are_unsupported() -> None:
    assert _state(()) == SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED
    assert _state(("2", "branch")) == SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED
