"""Application-level errors safe to present to users."""


class DomainConcurrencyConflict(RuntimeError):
    """A focused Domain command was based on an obsolete snapshot."""

    def __init__(self) -> None:
        super().__init__(
            "This Domain changed after it was opened. Reload or reopen it and try again."
        )
