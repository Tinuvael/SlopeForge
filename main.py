import logging
import sys
import webbrowser

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import APP_RELEASES_URL
from app.connection_settings import (
    ConnectionProfile,
    ConnectionSettingsError,
    ConnectionSettingsStore,
    MissingConnectionConfiguration,
    resolve_runtime_settings,
)
from app.context import AppContext
from app.localization import install_selected_translator, tr
from app.platform import set_windows_app_user_model_id
from app.qt import apply_application_icon
from app.runtime_paths import runtime_log_path
from app.splash import SlopeForgeSplash
from database.settings import ConfigurationError, Settings
from database.startup import StartupError, initialize_database_runtime
from infrastructure.services.auth_service import AuthService
from infrastructure.services.session_service import RememberTokenService
from ui.application_theme import initialize_application_theme
from ui.auth_dialogs import FirstAdminDialog, LoginDialog
from ui.connection_dialog import ConnectionSetupDialog
from ui.main_window import MainWindow
from ui.theme_compat import install_legacy_entity_page_theme_cleanup

LOG_PATH = runtime_log_path()
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO)
logger = logging.getLogger(__name__)

_CHANGE_CONNECTION = "change_connection"
_RETRY = "retry"
_CLOSE = "close"


def _with_connection_context(message: str, error: StartupError) -> str:
    if not error.server:
        return message
    return f"{message}\n\n{tr('Connection')}: {error.server}"


def show_startup_error(error: StartupError) -> str:
    """Show recoverable startup guidance without exposing migration internals."""
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Warning)

    release_button = None
    retry_button = None

    if error.reason == "database_upgrade_required":
        box.setWindowTitle(tr("Database update required"))
        box.setText(
            tr("The selected database is older than this version of SlopeForge.")
        )
        box.setInformativeText(_with_connection_context(
            tr("Update the database to a compatible version or contact your database administrator."),
            error,
        ))
        retry_button = box.addButton(tr("Try again"), QMessageBox.ButtonRole.AcceptRole)
    elif error.reason == "application_upgrade_required":
        box.setWindowTitle(tr("SlopeForge update required"))
        box.setText(
            tr("The selected database requires a newer version of SlopeForge.")
        )
        box.setInformativeText(_with_connection_context(
            tr("Update SlopeForge before opening this database."),
            error,
        ))
        release_button = box.addButton(
            tr("Get latest release"), QMessageBox.ButtonRole.AcceptRole
        )
    elif error.reason == "database_version_incompatible":
        box.setWindowTitle(tr("Database version mismatch"))
        box.setText(
            tr("The selected database is not compatible with this version of SlopeForge.")
        )
        box.setInformativeText(_with_connection_context(
            tr("Contact your database administrator or use another database connection."),
            error,
        ))
    elif error.reason in {"connection_error", "database_revision_unreadable"}:
        box.setWindowTitle(tr("Database connection failed"))
        box.setText(tr("SlopeForge could not connect to the selected PostgreSQL database."))
        box.setInformativeText(_with_connection_context(
            tr("Check the server address, network, credentials and database availability, or choose another connection."),
            error,
        ))
        retry_button = box.addButton(tr("Try again"), QMessageBox.ButtonRole.AcceptRole)
    else:
        box.setWindowTitle(tr("Database unavailable"))
        box.setText(tr("SlopeForge could not open the selected database."))
        box.setInformativeText(_with_connection_context(
            tr("Choose another connection or contact your database administrator."),
            error,
        ))
        retry_button = box.addButton(tr("Try again"), QMessageBox.ButtonRole.AcceptRole)

    change_button = box.addButton(
        tr("Change connection"), QMessageBox.ButtonRole.ActionRole
    )
    close_button = box.addButton(tr("Close"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(change_button)
    box.setEscapeButton(close_button)
    box.exec()

    clicked = box.clickedButton()
    if clicked is change_button:
        return _CHANGE_CONNECTION
    if retry_button is not None and clicked is retry_button:
        return _RETRY
    if release_button is not None and clicked is release_button:
        webbrowser.open(APP_RELEASES_URL)
    return _CLOSE


def _connection_setup(
    store: ConnectionSettingsStore,
    current_settings: Settings | None = None,
):
    initial_profile = (
        ConnectionProfile.from_settings(current_settings)
        if current_settings is not None
        else None
    )
    dialog = ConnectionSetupDialog(store, initial_profile=initial_profile)
    if dialog.exec() != dialog.DialogCode.Accepted:
        return None
    return dialog.runtime_settings


def _create_splash() -> SlopeForgeSplash:
    splash = SlopeForgeSplash()
    splash.show()
    splash.show_status(tr("Loading application…"))
    return splash


def main():
    startup_stage = "application bootstrap"
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    # Real QApplication always exposes styleHints(). Startup smoke tests use a
    # deliberately tiny QApplication stand-in, so only skip presentation setup
    # for that non-Qt test double; production startup always initializes theme.
    if callable(getattr(app, "styleHints", None)):
        initialize_application_theme(app)
        install_legacy_entity_page_theme_cleanup(app)
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

    splash = _create_splash()
    while True:
        try:
            startup_stage = "database initialization"
            logger.info("Startup stage: %s", startup_stage)
            splash.show_status(tr("Connecting to database…"))
            settings, _engine, session_factory = initialize_database_runtime(runtime_settings)
            break
        except StartupError as exc:
            logging.exception("Startup failed during stage: %s", startup_stage)
            splash.close()
            action = show_startup_error(exc)
            if action == _CHANGE_CONNECTION:
                replacement = _connection_setup(connection_store, runtime_settings)
                if replacement is None:
                    return 0
                runtime_settings = replacement
            elif action != _RETRY:
                return 1
            splash = _create_splash()

    try:
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
    except Exception:
        logging.exception("Unexpected startup failure during stage: %s", startup_stage)
        splash.close_with_fade()
        QMessageBox.critical(
            None,
            tr("Startup error"),
            f"{tr('Unexpected startup error. Details were written to')} {LOG_PATH}.",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
