"""Compatibility cleanup for legacy pages and Windows Qt style edge cases.

The application theme is authoritative. A few older pages still install
light-only descendant QSS, and Windows can also desynchronise painted complex
controls from the application palette after a stylesheet repolish. This bridge
stays presentation-only and intentionally imports Qt lazily so the lightweight
startup smoke harness can still import ``main``.
"""
from __future__ import annotations


_LEGACY_PAGE_CLASSES = {"BlockPage", "ContourEventPage", "AssessmentAreaPage"}
_filter = None


def install_legacy_entity_page_theme_cleanup(app) -> None:
    global _filter
    if _filter is not None:
        return

    from PySide6.QtCore import QEvent, QObject, Qt
    from PySide6.QtWidgets import (
        QAbstractSpinBox,
        QComboBox,
        QDateEdit,
        QFrame,
        QLabel,
        QLineEdit,
        QListWidget,
        QTextEdit,
        QWidget,
    )

    class LegacyEntityPageThemeFilter(QObject):
        _DARK_INPUT_STYLE = """
            QLineEdit, QTextEdit, QComboBox, QDateEdit {
                background-color: #202630;
                color: #f2f5f8;
                border: 1px solid #3b4654;
                border-radius: 5px;
                selection-background-color: #243f57;
                selection-color: #f2f5f8;
            }
            QLineEdit, QTextEdit { padding: 2px 6px; }
            QComboBox, QDateEdit { padding: 1px 26px 1px 7px; }
            QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled, QDateEdit:disabled {
                background-color: #252c36;
                color: #6f7a86;
                border-color: #3b4654;
            }
            QComboBox QAbstractItemView {
                background-color: #2b3440;
                color: #f2f5f8;
                border: 1px solid #3b4654;
                selection-background-color: #243f57;
                selection-color: #f2f5f8;
                outline: 0;
            }
            QComboBox::drop-down, QDateEdit::drop-down {
                background-color: #252c36;
                border-left: 1px solid #3b4654;
            }
        """
        _ASSESSMENT_LIST_STYLE = """
            QListWidget::item,
            QListWidget::item:selected,
            QListWidget::item:focus {
                background: transparent;
                border: 0;
                outline: 0;
            }
        """

        @staticmethod
        def _dark_theme() -> bool:
            return app.property("slopeforgeTheme") == "dark"

        @staticmethod
        def _clear_light_only_page_style(widget: QWidget) -> None:
            style = widget.styleSheet()
            compact = "".join(style.split()).lower() if style else ""
            if not style:
                return
            if widget.__class__.__name__ in _LEGACY_PAGE_CLASSES:
                if "#cardframe" in compact and (
                    "background:white" in compact
                    or "background:#ffffff" in compact
                ):
                    widget.setProperty("slopeforgeThemeSync", True)
                    widget.setStyleSheet("")
                    widget.setProperty("slopeforgeThemeSync", False)
                return
            if widget.objectName() == "geomechanicsWorkspace" and (
                "background:white" in compact or "background:#ffffff" in compact
            ):
                # The Geomechanics page still owns a small light-only style for
                # labels and text editors. Neutralise it regardless of whether
                # its own StyleChange event was observed before the page was lent
                # from the hidden TechnicalCardDialog into the entity page.
                widget.setProperty("slopeforgeThemeSync", True)
                widget.setStyleSheet("")
                widget.setProperty("slopeforgeThemeSync", False)

        def _clear_light_only_ancestor_styles(self, widget: QWidget) -> None:
            current = widget
            while current is not None:
                if isinstance(current, QWidget) and not current.property("slopeforgeThemeSync"):
                    self._clear_light_only_page_style(current)
                current = current.parentWidget()

        @staticmethod
        def _spin_ancestor(widget):
            current = widget
            while current is not None:
                if isinstance(current, QAbstractSpinBox):
                    return current
                current = current.parentWidget() if isinstance(current, QWidget) else None
            return None

        @staticmethod
        def _has_theme_managed_input_ancestor(widget: QWidget) -> bool:
            current = widget.parentWidget()
            while current is not None:
                if current.objectName() in {
                    "StandardEntityDialog",
                    "EngineeringWorkspace",
                    "geomechanicsWorkspace",
                }:
                    return True
                current = current.parentWidget()
            return False

        def _sync_complex_input(self, widget: QWidget) -> None:
            if not isinstance(widget, (QLineEdit, QTextEdit, QComboBox, QDateEdit)):
                return
            if isinstance(widget, QLineEdit) and self._spin_ancestor(widget) is not None:
                return
            managed = bool(widget.property("slopeforgeDarkInputManaged"))
            should_manage = self._dark_theme() and self._has_theme_managed_input_ancestor(widget)
            if should_manage and not managed:
                widget.setProperty("slopeforgeOriginalInputStyle", widget.styleSheet())
                widget.setProperty("slopeforgeDarkInputManaged", True)
                widget.setProperty("slopeforgeThemeSync", True)
                widget.setStyleSheet(self._DARK_INPUT_STYLE)
                widget.setProperty("slopeforgeThemeSync", False)
            elif not should_manage and managed:
                original = widget.property("slopeforgeOriginalInputStyle")
                widget.setProperty("slopeforgeThemeSync", True)
                widget.setStyleSheet(str(original or ""))
                widget.setProperty("slopeforgeThemeSync", False)
                widget.setProperty("slopeforgeDarkInputManaged", False)
                widget.setProperty("slopeforgeOriginalInputStyle", None)

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

        def _sync_score_frame(self, frame: QFrame) -> None:
            if frame.objectName() != "ScoreStateFrame":
                return
            spin = frame.findChild(QAbstractSpinBox)
            editor = spin.findChild(QLineEdit) if spin is not None else None
            if editor is not None:
                self._sync_score_state(editor)

        @staticmethod
        def _list_for_item_widget(widget):
            current = widget.parentWidget()
            while current is not None:
                if isinstance(current, QListWidget):
                    return current
                current = current.parentWidget()
            return None

        @staticmethod
        def _item_for_widget(owner: QListWidget, widget: QWidget):
            for index in range(owner.count()):
                item = owner.item(index)
                if owner.itemWidget(item) is widget:
                    return item
            return None

        def _ensure_assessment_link_list(self, owner: QListWidget) -> None:
            if owner.property("slopeforgeAssessmentSelectionHook"):
                return
            original = owner.styleSheet()
            owner.setProperty("slopeforgeAssessmentSelectionHook", True)
            owner.setProperty("slopeforgeThemeSync", True)
            owner.setStyleSheet(
                (original + "\n" if original else "") + self._ASSESSMENT_LIST_STYLE
            )
            owner.setProperty("slopeforgeThemeSync", False)
            owner.currentRowChanged.connect(
                lambda _row, target=owner: self._refresh_assessment_link_list(target)
            )

        def _refresh_assessment_link_list(self, owner: QListWidget) -> None:
            for index in range(owner.count()):
                item = owner.item(index)
                widget = owner.itemWidget(item)
                if isinstance(widget, QFrame) and widget.objectName() == "AssessmentLinkItem":
                    self._sync_assessment_link_item(widget, owner=owner)

        def _sync_assessment_link_item(
            self,
            widget: QFrame,
            *,
            owner: QListWidget | None = None,
        ) -> None:
            if widget.objectName() != "AssessmentLinkItem":
                return
            owner = owner or self._list_for_item_widget(widget)
            if owner is not None:
                self._ensure_assessment_link_list(owner)
            item = self._item_for_widget(owner, widget) if owner is not None else None
            selected = bool(owner is not None and item is not None and owner.currentItem() is item)

            if not self._dark_theme():
                setter = getattr(widget, "set_selected", None)
                if callable(setter):
                    widget.setProperty("slopeforgeThemeSync", True)
                    setter(selected)
                    widget.setProperty("slopeforgeThemeSync", False)
                return

            status = str(getattr(widget, "workflow_status", "suggested") or "suggested")
            colors = {
                "suggested": ("#493b21", "#725c2e"),
                "confirmed": ("#213c2b", "#386449"),
                "excluded": ("#2b323d", "#46515f"),
            }
            background, accent = colors.get(status, colors["suggested"])
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
                    self._clear_light_only_ancestor_styles(watched)
                    self._sync_complex_input(watched)
                    if isinstance(watched, QLineEdit):
                        self._sync_score_state(watched)
                    if isinstance(watched, QFrame):
                        self._sync_score_frame(watched)
                        self._sync_assessment_link_item(watched)
                    if isinstance(watched, QLabel):
                        self._sync_inline_link_badges(watched)

            # Rich-text status pills are rebuilt by AssessmentAreaPage.setText()
            # when the selected link changes, which does not emit StyleChange.
            # Normalize just those known legacy labels immediately before paint.
            if (
                isinstance(watched, QLabel)
                and event_type == QEvent.Type.Paint
                and not watched.property("slopeforgeThemeSync")
            ):
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
