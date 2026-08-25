import logging
import sys
import webbrowser

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import APP_RELEASES_URL
from app.connection_settings import ConnectionProfile, ConnectionSettingsStore
from app.localization import install_selected_translator, tr
from app.platform import set_windows_app_user_model_id
from app.qt import apply_application_icon
from app.runtime_controller import DesktopRuntimeController
from app.runtime_paths import runtime_log_path
from app.splash import SlopeForgeSplash
from database.settings import Settings
from database.startup import StartupError
from ui.application_theme import initialize_application_theme
from ui.connection_dialog import ConnectionSetupDialog
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
        box.setInformativeText(
            _with_connection_context(
                tr("Update the database to a compatible version or contact your database administrator."),
                error,
            )
        )
        retry_button = box.addButton(tr("Try again"), QMessageBox.ButtonRole.AcceptRole)
    elif error.reason == "application_upgrade_required":
        box.setWindowTitle(tr("SlopeForge update required"))
        box.setText(
            tr("The selected database requires a newer version of SlopeForge.")
        )
        box.setInformativeText(
            _with_connection_context(
                tr("Update SlopeForge before opening this database."), error
            )
        )
        release_button = box.addButton(
            tr("Get latest release"), QMessageBox.ButtonRole.AcceptRole
        )
    elif error.reason == "database_version_incompatible":
        box.setWindowTitle(tr("Database version mismatch"))
        box.setText(
            tr("The selected database is not compatible with this version of SlopeForge.")
        )
        box.setInformativeText(
            _with_connection_context(
                tr("Contact your database administrator or use another database connection."),
                error,
            )
        )
    elif error.reason in {"connection_error", "database_revision_unreadable"}:
        box.setWindowTitle(tr("Database connection failed"))
        box.setText(
            tr("SlopeForge could not connect to the selected PostgreSQL database.")
        )
        box.setInformativeText(
            _with_connection_context(
                tr("Check the server address, network, credentials and database availability, or choose another connection."),
                error,
            )
        )
        retry_button = box.addButton(tr("Try again"), QMessageBox.ButtonRole.AcceptRole)
    else:
        box.setWindowTitle(tr("Database unavailable"))
        box.setText(tr("SlopeForge could not open the selected database."))
        box.setInformativeText(
            _with_connection_context(
                tr("Choose another connection or contact your database administrator."),
                error,
            )
        )
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
    """Compatibility helper retained for recovery tests and external callers."""
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
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    if callable(getattr(app, "styleHints", None)):
        initialize_application_theme(app)
        install_legacy_entity_page_theme_cleanup(app)
    install_selected_translator(app)
    apply_application_icon(app)

    try:
        controller = DesktopRuntimeController(
            app,
            ConnectionSettingsStore(),
            startup_error_handler=show_startup_error,
            splash_factory=_create_splash,
        )
        if not controller.start():
            return 0
        return app.exec()
    except Exception:
        logging.exception("Unexpected desktop startup failure")
        QMessageBox.critical(
            None,
            tr("Startup error"),
            f"{tr('Unexpected startup error. Details were written to')} {LOG_PATH}.",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())