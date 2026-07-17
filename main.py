import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.platform import set_windows_app_user_model_id
from app.qt import apply_application_icon
from app.splash import SlopeForgeSplash
from database.app_context import AppContext
from database.startup import StartupError, initialize_database_runtime
from services.auth_service import AuthService
<<<<<<< HEAD
from services.session_service import RememberTokenService
=======
>>>>>>> origin/main
from ui.auth_dialogs import FirstAdminDialog, LoginDialog
from ui.main_window import MainWindow

logging.basicConfig(filename="slopeforge.log", level=logging.INFO)


def show_startup_error(message: str, server: str | None) -> None:
    details = [message]
    if server:
        details.append(f"Server/database: {server}")
    details.extend([
        "Check DATABASE_URL in environment variables or .env.",
        "Run migrations: python -m database.cli migrate",
        "If the database does not exist yet: python -m database.cli prepare-db",
    ])
    QMessageBox.critical(None, "PostgreSQL unavailable", "\n\n".join(details))


def main():
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    apply_application_icon(app)
    splash = SlopeForgeSplash()
    splash.show()
    splash.show_status("Loading application…")
    try:
        splash.show_status("Connecting to database…")
        _settings, _engine, session_factory = initialize_database_runtime()
        splash.show_status("Checking database schema…")
        auth_service = AuthService(session_factory)
<<<<<<< HEAD
        remember_service = RememberTokenService(session_factory)
        remembered = remember_service.authenticate_local() if auth_service.has_users() else None
        current_user = remembered.current_user if remembered else None
        if current_user is None:
            if auth_service.has_users():
                dialog = LoginDialog(auth_service)
            else:
                dialog = FirstAdminDialog(auth_service)
            splash.close_with_fade()
            if dialog.exec() != dialog.DialogCode.Accepted or dialog.current_user is None:
                return 0
            current_user = dialog.current_user
            if isinstance(dialog, LoginDialog) and dialog.remember_requested:
                remember_service.create_for_user(current_user.id, current_user.username)
        else:
            splash.close_with_fade()
        splash.show_status("Initializing interface…") if splash.isVisible() else None
        window = MainWindow(AppContext(session_factory=session_factory, current_user=current_user))
=======
        if auth_service.has_users():
            dialog = LoginDialog(auth_service)
        else:
            dialog = FirstAdminDialog(auth_service)
        splash.close_with_fade()
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.current_user is None:
            return 0
        splash.show_status("Initializing interface…") if splash.isVisible() else None
        window = MainWindow(AppContext(session_factory=session_factory, current_user=dialog.current_user))
>>>>>>> origin/main
        window.showMaximized()
        return app.exec()
    except StartupError as exc:
        logging.exception("Startup failed")
        splash.close_with_fade()
        show_startup_error(str(exc), exc.server)
        return 1
    except Exception:
        logging.exception("Unexpected startup failure")
        splash.close_with_fade()
        QMessageBox.critical(None, "Startup error", "Unexpected startup error. Details were written to slopeforge.log.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
