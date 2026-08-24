"""Compatibility cleanup for legacy pages and Windows Qt style edge cases.

The application theme is authoritative. A few older pages still install
light-only descendant QSS, and Windows can also desynchronise painted spin-box
arrow regions from their native hit rectangles after a stylesheet repolish.
This bridge stays presentation-only and intentionally imports Qt lazily so the
lightweight startup smoke harness can still import ``main``.
"""
from __future__ import annotations


_LEGACY_PAGE_CLASSES = {"BlockPage", "ContourEventPage", "AssessmentAreaPage"}
_filter = None


def install_legacy_entity_page_theme_cleanup(app) -> None:
    global _filter
    if _filter is not None:
        return

    from PySide6.QtCore import QEvent, QObject, Qt
    from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit, QSpinBox, QWidget

    class LegacyEntityPageThemeFilter(QObject):
        @staticmethod
        def _dark_theme() -> bool:
            return app.property("slopeforgeTheme") == "dark"

        @staticmethod
        def _clear_light_only_page_style(widget: QWidget) -> None:
            style = widget.styleSheet()
            compact = style.replace(" ", "") if style else ""
            if not style:
                return
            if widget.__class__.__name__ in _LEGACY_PAGE_CLASSES:
                if "#CardFrame" in style and (
                    "background:white" in compact
                    or "background:#ffffff" in compact
                ):
                    widget.setStyleSheet("")
                return
            if widget.objectName() == "geomechanicsWorkspace" and "background:white" in compact:
                # The Geomechanics page used to own a small light-only style for
                # section labels and QLineEdit/QTextEdit. Let the application
                # palette/QSS provide the same geometry with theme-correct colours.
                widget.setStyleSheet("")

        def _sync_score_state(self, editor: QLineEdit) -> None:
            spin = editor.parentWidget()
            if not isinstance(spin, (QSpinBox, QDoubleSpinBox)):
                return
            state = spin.objectName()
            if state not in {"ManualScore", "MissingScore"}:
                return
            if self._dark_theme():
                if state == "ManualScore":
                    background, border = "#493b21", "#725c2e"
                else:
                    background, border = "#46292b", "#754247"
                text = "#f2f5f8"
            else:
                background = "#fff4cc" if state == "ManualScore" else "#fff0f0"
                border = background
                text = "#111827"

            editor_style = f"background-color:{background};color:{text};"
            if editor.styleSheet() != editor_style:
                editor.setProperty("slopeforgeThemeSync", True)
                editor.setStyleSheet(editor_style)
                editor.setProperty("slopeforgeThemeSync", False)

            frame = spin.parentWidget()
            if frame is not None and frame.objectName() == "ScoreStateFrame":
                frame_style = (
                    f"#ScoreStateFrame{{background:{background};"
                    f"border:1px solid {border};border-radius:3px;}}"
                )
                if frame.styleSheet() != frame_style:
                    frame.setProperty("slopeforgeThemeSync", True)
                    frame.setStyleSheet(frame_style)
                    frame.setProperty("slopeforgeThemeSync", False)

        def eventFilter(self, watched, event):
            event_type = event.type()

            if isinstance(watched, QWidget) and event_type in (
                QEvent.Type.Polish,
                QEvent.Type.Show,
                QEvent.Type.StyleChange,
                QEvent.Type.PaletteChange,
            ):
                if not watched.property("slopeforgeThemeSync"):
                    self._clear_light_only_page_style(watched)
                    if isinstance(watched, QLineEdit):
                        self._sync_score_state(watched)

            # In Windows Qt styles a dark stylesheet can paint a spin-box button
            # strip whose native clickable subcontrols are offset. Preserve the
            # normal Light behaviour, but in Dark make the visible right-side
            # halves deterministically step up/down for every numeric spin box.
            if (
                self._dark_theme()
                and isinstance(watched, (QSpinBox, QDoubleSpinBox))
                and event_type == QEvent.Type.MouseButtonPress
                and watched.isEnabled()
                and not watched.isReadOnly()
                and event.button() == Qt.MouseButton.LeftButton
                and event.position().x() >= watched.width() - 24
            ):
                if event.position().y() < watched.height() / 2:
                    watched.stepUp()
                else:
                    watched.stepDown()
                event.accept()
                return True

            return False

    _filter = LegacyEntityPageThemeFilter(app)
    app.installEventFilter(_filter)
