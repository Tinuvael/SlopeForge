"""Compatibility cleanup for legacy entity pages with page-local light QSS.

The reusable application theme is now authoritative. Block, Contour and
Assessment pages predate it and still install a descendant stylesheet containing
literal white cards and dark text. A child/ancestor stylesheet outranks the
application stylesheet in Qt, so merely adding more global selectors cannot fix
those pages reliably.

Keep this bridge narrowly scoped to the three known page classes until their
large presentation blocks are removed during normal page cleanup. The module
intentionally imports no Qt classes at import time so the lightweight startup
smoke harness can import ``main`` without implementing the complete Qt API.
"""
from __future__ import annotations


_LEGACY_PAGE_CLASSES = {"BlockPage", "ContourEventPage", "AssessmentAreaPage"}
_filter = None


def install_legacy_entity_page_theme_cleanup(app) -> None:
    global _filter
    if _filter is not None:
        return

    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QWidget

    class LegacyEntityPageThemeFilter(QObject):
        def eventFilter(self, watched, event):
            if (
                isinstance(watched, QWidget)
                and watched.__class__.__name__ in _LEGACY_PAGE_CLASSES
                and event.type()
                in (QEvent.Type.Polish, QEvent.Type.Show, QEvent.Type.StyleChange)
            ):
                style = watched.styleSheet()
                compact = style.replace(" ", "") if style else ""
                if "#CardFrame" in style and (
                    "background:white" in compact
                    or "background:#ffffff" in compact
                ):
                    watched.setStyleSheet("")
            return False

    _filter = LegacyEntityPageThemeFilter(app)
    app.installEventFilter(_filter)
