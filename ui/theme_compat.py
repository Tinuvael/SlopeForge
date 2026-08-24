"""Compatibility cleanup for legacy entity pages with page-local light QSS.

The reusable application theme is now authoritative.  Block, Contour and
Assessment pages predate it and still install a descendant stylesheet containing
literal white cards and dark text.  A child/ancestor stylesheet outranks the
application stylesheet in Qt, so merely adding more global selectors cannot fix
those pages reliably.

Keep this bridge narrowly scoped to the three known page classes until their
large presentation blocks are removed during normal page cleanup.  It does not
change widget geometry, domain behavior or stylesheets belonging to editors.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget


_LEGACY_PAGE_CLASSES = {"BlockPage", "ContourEventPage", "AssessmentAreaPage"}
_LIGHT_ONLY_MARKERS = (
    "#CardFrame",
    "background:white",
    "background:#ffffff",
)


class LegacyEntityPageThemeFilter(QObject):
    def eventFilter(self, watched, event):
        if (
            isinstance(watched, QWidget)
            and watched.__class__.__name__ in _LEGACY_PAGE_CLASSES
            and event.type() in (QEvent.Type.Polish, QEvent.Type.Show, QEvent.Type.StyleChange)
        ):
            style = watched.styleSheet()
            if style and "#CardFrame" in style and any(
                marker in style.replace(" ", "") for marker in _LIGHT_ONLY_MARKERS[1:]
            ):
                watched.setStyleSheet("")
        return False


_filter: LegacyEntityPageThemeFilter | None = None


def install_legacy_entity_page_theme_cleanup(app: QApplication) -> None:
    global _filter
    if _filter is not None:
        return
    _filter = LegacyEntityPageThemeFilter(app)
    app.installEventFilter(_filter)
