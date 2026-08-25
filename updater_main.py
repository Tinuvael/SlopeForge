from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.platform import set_windows_app_user_model_id
from app.qt import apply_application_icon
from ui.application_theme import initialize_application_theme
from ui.updater_window import SlopeForgeUpdaterWindow


def main() -> int:
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName("SlopeForge Updater")
    apply_application_icon(app)
    initialize_application_theme(app)
    window = SlopeForgeUpdaterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
