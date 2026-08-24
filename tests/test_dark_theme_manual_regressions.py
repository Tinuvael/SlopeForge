from pathlib import Path


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_dark_assessment_selection_uses_one_full_row_indicator() -> None:
    compat = source("ui/theme_compat.py")
    assessment = source("ui/pages/assessment_area_page.py")

    # Assessment rows already own the full-card selection border. The QListWidget
    # must not paint a second native current/selected marker (the blue left strip
    # seen during the Windows dark-theme smoke).
    assert "QListWidget::item:selected" in compat
    assert "QListWidget::item:focus" in compat
    assert "background: transparent" in compat
    assert "border: 0" in compat
    assert "owner.currentItem() is item" in compat
    assert 'background, accent, width = "#243f57", "#79b9ee", 2' in compat

    # Light keeps the same full-card interaction model through the existing row
    # renderer; only the theme colours differ.
    assert 'border = "#2563a6" if selected else accent' in assessment
    assert "width = 2 if selected else 1" in assessment


def test_dark_complex_inputs_cover_reported_windows_contexts() -> None:
    compat = source("ui/theme_compat.py")
    blast_dialog = source("ui/dialogs/blast_event_dialog.py")
    technical_card = source("ui/editors/technical_card_editor.py")

    # The compatibility pass is deliberately scoped to the three places reported
    # by the manual smoke: standard create/edit dialogs, Blast design and
    # Geomechanics. It must not turn into a generic page-by-page theme rewrite.
    for context in (
        '"StandardEntityDialog"',
        '"EngineeringWorkspace"',
        '"geomechanicsWorkspace"',
    ):
        assert context in compat
    assert "QLineEdit, QTextEdit, QComboBox, QDateEdit" in compat
    assert "background-color: #202630" in compat
    assert "background-color: #252c36" in compat
    assert "QComboBox QAbstractItemView" in compat
    assert "QComboBox::drop-down, QDateEdit::drop-down" in compat

    # Ground the regression in the actual active widgets from the user report.
    assert "self.kind = QComboBox()" in blast_dialog
    assert "self.date = QDateEdit" in blast_dialog
    assert "self.add_group_combo = QComboBox()" in technical_card
    assert 'combo.setObjectName("chargePresetCombo")' in technical_card
    assert "self.lithology = QLineEdit" in technical_card
    assert "self.jn" in technical_card and "self.jr" in technical_card

    # Geomechanics still carries a historical light-only local stylesheet; the
    # bridge must explicitly neutralise that ancestor instead of letting it beat
    # the application dark QSS by specificity.
    assert 'widget.objectName() == "geomechanicsWorkspace"' in compat
    assert 'widget.setStyleSheet("")' in compat
    assert "background: white" in technical_card


def test_theme_compat_repolish_is_coalesced_after_qt_style_traversal() -> None:
    compat = source("ui/theme_compat.py")

    # Windows QStyle must not be mutated recursively while QApplication is walking
    # its descendants for setPalette()/setStyleSheet(). One deferred app-wide pass
    # queries only the widgets that still exist at execution time.
    assert "self._application_refresh_pending" in compat
    assert "QTimer.singleShot(0, self._sync_all_widgets)" in compat
    assert "for widget in tuple(app.allWidgets())" in compat
    assert "isValid(widget)" in compat
    assert "_defer_widget_theme_sync" not in compat
