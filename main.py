import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from app.platform import set_windows_app_user_model_id
from app.qt import apply_application_icon
from app.splash import SlopeForgeSplash
from database.app_context import AppContext
from database.startup import StartupError, initialize_database_runtime
from services.auth_service import AuthService
from services.session_service import RememberTokenService
from ui.auth_dialogs import FirstAdminDialog, LoginDialog
from ui.main_window import MainWindow

LOG_PATH = Path("slopeforge.log").resolve()
logging.basicConfig(filename=LOG_PATH, level=logging.INFO)
logger = logging.getLogger(__name__)


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
    startup_stage = "application bootstrap"
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    apply_application_icon(app)
    splash = SlopeForgeSplash()
    splash.show()
    splash.show_status("Loading application…")
    try:
        startup_stage = "database initialization"
        logger.info("Startup stage: %s", startup_stage)
        splash.show_status("Connecting to database…")
        settings, _engine, session_factory = initialize_database_runtime()
        startup_stage = "authentication initialization"
        logger.info("Startup stage: %s", startup_stage)
        splash.show_status("Checking database schema…")
        auth_service = AuthService(session_factory)
        remember_service = RememberTokenService(session_factory)
        startup_stage = "remembered-session lookup"
        logger.info("Startup stage: %s", startup_stage)
        remembered = remember_service.authenticate_local() if auth_service.has_users() else None
        current_user = remembered.current_user if remembered else None
        if current_user is None:
            startup_stage = "login/first-admin dialog"
            logger.info("Startup stage: %s", startup_stage)
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
        startup_stage = "MainWindow construction"
        logger.info("Startup stage: %s", startup_stage)
        splash.show_status("Initializing interface…") if splash.isVisible() else None
        window = MainWindow(AppContext(
            session_factory=session_factory,
            current_user=current_user,
            storage_root=settings.storage_root,
        ))
        window.showMaximized()
        return app.exec()
    except StartupError as exc:
        logging.exception("Startup failed during stage: %s", startup_stage)
        splash.close_with_fade()
        show_startup_error(str(exc), exc.server)
        return 1
    except Exception:
        logging.exception("Unexpected startup failure during stage: %s", startup_stage)
        splash.close_with_fade()
        QMessageBox.critical(None, "Startup error", f"Unexpected startup error. Details were written to {LOG_PATH}.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
