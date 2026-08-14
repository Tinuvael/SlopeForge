"""Application-level errors safe to present to users."""


class DomainConcurrencyConflict(RuntimeError):
    """A focused Domain command was based on an obsolete snapshot."""

    def __init__(self) -> None:
        super().__init__(
            "This Domain changed after it was opened. Reload or reopen it and try again."
        )


class DomainNameConflict(ValueError):
    """The requested display name is already used in the same Project."""

    def __init__(self) -> None:
        super().__init__("A Domain with this name already exists in this Project.")


class CatalogueConflictError(ValueError):
    """A catalogue write conflicts with existing shared data."""
