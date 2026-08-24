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
    from PySide6.QtWidgets import QAbstractSpinBox, QFrame, QLabel, QLineEdit, QListWidget, QWidget

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

        @staticmethod
        def _spin_ancestor(widget):
            current = widget
            while current is not None:
                if isinstance(current, QAbstractSpinBox):
                    return current
                current = current.parentWidget() if isinstance(current, QWidget) else None
            return None

        def _sync_score_state(self, editor: QLineEdit) -> None:
            spin = self._spin_ancestor(editor)
            if spin is None:
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

        @staticmethod
        def _list_for_item_widget(widget):
            current = widget.parentWidget()
            while current is not None:
                if isinstance(current, QListWidget):
                    return current
                current = current.parentWidget()
            return None

        def _sync_assessment_link_item(self, widget: QFrame) -> None:
            if widget.objectName() != "AssessmentLinkItem" or not self._dark_theme():
                return
            status = str(getattr(widget, "workflow_status", "suggested") or "suggested")
            colors = {
                "suggested": ("#493b21", "#725c2e"),
                "confirmed": ("#213c2b", "#386449"),
                "excluded": ("#2b323d", "#46515f"),
            }
            background, accent = colors.get(status, colors["suggested"])
            selected = False
            owner = self._list_for_item_widget(widget)
            if owner is not None:
                for index in range(owner.count()):
                    item = owner.item(index)
                    if owner.itemWidget(item) is widget:
                        selected = item.isSelected()
                        break
            if selected:
                background, accent, width = "#243f57", "#79b9ee", 2
            else:
                width = 1
            desired = (
                f"QFrame#AssessmentLinkItem{{background:{background};border:{width}px solid {accent};border-radius:5px}}"
                "QFrame#AssessmentLinkItem QLabel{background:transparent;color:#f2f5f8;border:0}"
                "QFrame#AssessmentLinkItem QLabel#MutedText{color:#c5ced8}"
                "QFrame#AssessmentLinkItem QLabel#LinkStatusBadge{font-weight:600;color:#d5dbe3}"
                "QFrame#AssessmentLinkItem QLabel#StaleBadge{background:#493b21;color:#f0c66e;border:1px solid #725c2e;border-radius:4px;padding:1px 4px}"
            )
            if widget.styleSheet() != desired:
                widget.setProperty("slopeforgeThemeSync", True)
                widget.setStyleSheet(desired)
                widget.setProperty("slopeforgeThemeSync", False)

        def _sync_inline_link_badges(self, label: QLabel) -> None:
            if not self._dark_theme():
                return
            text = label.text()
            if "background:#eef2f7" in text and "border:1px solid #d5dbe3" in text:
                dark_text = (
                    text.replace("background:#eef2f7", "background:#2b3440")
                    .replace("border:1px solid #d5dbe3", "border:1px solid #4a5665")
                    .replace("<span style='", "<span style='color:#d5dbe3;", 1)
                )
                if dark_text != text:
                    label.setProperty("slopeforgeThemeSync", True)
                    label.setText(dark_text)
                    label.setProperty("slopeforgeThemeSync", False)

            style = label.styleSheet()
            compact = style.replace(" ", "") if style else ""
            if "background:#fff8e6" in compact and "color:#8a5a00" in compact:
                desired = (
                    "background:#493b21;color:#f0c66e;border:1px solid #725c2e;"
                    "border-radius:4px;padding:5px"
                )
                if style != desired:
                    label.setProperty("slopeforgeThemeSync", True)
                    label.setStyleSheet(desired)
                    label.setProperty("slopeforgeThemeSync", False)

        @staticmethod
        def _spin_mouse_target(watched, event):
            if isinstance(watched, QAbstractSpinBox):
                return watched, event.position().toPoint()
            if isinstance(watched, QLineEdit):
                spin = LegacyEntityPageThemeFilter._spin_ancestor(watched)
                if spin is not None:
                    return spin, watched.mapTo(spin, event.position().toPoint())
            return None, None

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
                    if isinstance(watched, QFrame):
                        self._sync_assessment_link_item(watched)
                    if isinstance(watched, QLabel):
                        self._sync_inline_link_badges(watched)

            # If a Windows style routes the painted upper-arrow region to the
            # embedded line edit, intercept that child event as well. This keeps
            # the visible dark controls behaving exactly like their Light/native
            # counterparts instead of selecting the editor when Up is clicked.
            if self._dark_theme() and event_type == QEvent.Type.MouseButtonPress:
                spin, point = self._spin_mouse_target(watched, event)
                if (
                    spin is not None
                    and spin.isEnabled()
                    and not spin.isReadOnly()
                    and event.button() == Qt.MouseButton.LeftButton
                    and point.x() >= spin.width() - 24
                ):
                    if point.y() < spin.height() / 2:
                        spin.stepUp()
                    else:
                        spin.stepDown()
                    event.accept()
                    return True

            return False

    _filter = LegacyEntityPageThemeFilter(app)
    app.installEventFilter(_filter)
