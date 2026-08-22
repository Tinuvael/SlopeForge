from app.localization import tr
import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.connection_settings import (
    ConnectionSettingsError,
    ConnectionSettingsStore,
    MissingConnectionConfiguration,
    resolve_runtime_settings,
)
from app.platform import set_windows_app_user_model_id
from app.runtime_paths import runtime_log_path
from app.qt import apply_application_icon
from app.localization import install_selected_translator, tr
from app.splash import SlopeForgeSplash
from app.context import AppContext
from database.settings import ConfigurationError
from database.startup import StartupError, initialize_database_runtime
from infrastructure.services.auth_service import AuthService
from infrastructure.services.session_service import RememberTokenService
from ui.auth_dialogs import FirstAdminDialog, LoginDialog
from ui.connection_dialog import ConnectionSetupDialog
from ui.main_window import MainWindow
from ui.theme import apply_theme

LOG_PATH = runtime_log_path()
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO)
logger = logging.getLogger(__name__)


def show_startup_error(error: StartupError) -> None:
    QMessageBox.critical(None, tr("PostgreSQL unavailable"), error.presentation())


def _connection_setup(store: ConnectionSettingsStore):
    dialog = ConnectionSetupDialog(store)
    if dialog.exec() != dialog.DialogCode.Accepted:
        return None
    return dialog.runtime_settings


def main():
    startup_stage = "application bootstrap"
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    apply_theme(app)
    install_selected_translator(app)
    apply_application_icon(app)

    connection_store = ConnectionSettingsStore()
    try:
        runtime_settings, _source = resolve_runtime_settings(connection_store)
    except MissingConnectionConfiguration:
        runtime_settings = _connection_setup(connection_store)
        if runtime_settings is None:
            return 0
    except ConnectionSettingsError as exc:
        QMessageBox.warning(
            None,
            tr("Connection settings"),
            f"{exc}\n\n{tr('Enter the connection settings again.')}",
        )
        runtime_settings = _connection_setup(connection_store)
        if runtime_settings is None:
            return 0
    except ConfigurationError as exc:
        QMessageBox.critical(None, tr("Connection configuration error"), str(exc))
        return 1

    splash = SlopeForgeSplash()
    splash.show()
    splash.show_status(tr("Loading application…"))
    try:
        startup_stage = "database initialization"
        logger.info("Startup stage: %s", startup_stage)
        splash.show_status(tr("Connecting to database…"))
        settings, _engine, session_factory = initialize_database_runtime(runtime_settings)
        startup_stage = "authentication initialization"
        logger.info("Startup stage: %s", startup_stage)
        splash.show_status(tr("Checking database schema…"))
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
        splash.show_status(tr("Initializing interface…")) if splash.isVisible() else None
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
        show_startup_error(exc)
        return 1
    except Exception:
        logging.exception("Unexpected startup failure during stage: %s", startup_stage)
        splash.close_with_fade()
        QMessageBox.critical(None, tr("Startup error"), f"Unexpected startup error. Details were written to {LOG_PATH}.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
