from __future__ import annotations

import sys

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from app.platform import set_windows_app_user_model_id
from app.qt import apply_application_icon
from ui.application_theme import initialize_application_theme
from ui.updater_window import SlopeForgeUpdaterWindow


class UpdaterMainWindow(SlopeForgeUpdaterWindow):
    """Keep the process alive while backup or schema maintenance is running."""

    def closeEvent(self, event) -> None:
        if self._busy:
            QMessageBox.warning(
                self,
                "Operation in progress",
                "Wait for the current backup or database operation to finish before closing SlopeForge Updater.",
            )
            event.ignore()
            return
        super().closeEvent(event)


def _polish_disabled_upgrade_action(window: UpdaterMainWindow) -> None:
    """Keep the gated primary action readable in both light and dark themes."""
    palette = window.palette()
    disabled = QPalette.ColorGroup.Disabled
    text = palette.color(disabled, QPalette.ColorRole.ButtonText).name()
    background = palette.color(disabled, QPalette.ColorRole.Button).name()
    border = palette.color(disabled, QPalette.ColorRole.Mid).name()
    window.upgrade_button.setStyleSheet(
        "QPushButton:disabled {"
        f"color: {text}; background: {background}; border: 1px solid {border};"
        "}"
    )


def main() -> int:
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName("SlopeForge Updater")
    apply_application_icon(app)
    initialize_application_theme(app)
    window = UpdaterMainWindow()
    _polish_disabled_upgrade_action(window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
