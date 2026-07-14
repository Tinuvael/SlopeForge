import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from database.app_context import AppContext
from database.startup import StartupError, initialize_database_runtime
from services.auth_service import AuthService
from ui.auth_dialogs import FirstAdminDialog, LoginDialog
from ui.main_window import MainWindow

logging.basicConfig(filename="slopeforge.log", level=logging.INFO)


def show_startup_error(message: str, server: str | None) -> None:
    details = [message]
    if server:
        details.append(f"Сервер/база: {server}")
    details.extend([
        "Проверьте DATABASE_URL в переменных окружения или .env.",
        "Выполните миграции: python -m database.cli migrate",
        "Если базы ещё нет: python -m database.cli prepare-db",
    ])
    QMessageBox.critical(None, "PostgreSQL недоступен", "\n\n".join(details))


def main():
    app = QApplication(sys.argv)
    try:
        _settings, _engine, session_factory = initialize_database_runtime()
        auth_service = AuthService(session_factory)
        if auth_service.has_users():
            dialog = LoginDialog(auth_service)
        else:
            dialog = FirstAdminDialog(auth_service)
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.current_user is None:
            return 0
        window = MainWindow(AppContext(session_factory=session_factory, current_user=dialog.current_user))
        window.showMaximized()
        return app.exec()
    except StartupError as exc:
        logging.exception("Startup failed")
        show_startup_error(str(exc), exc.server)
        return 1
    except Exception:
        logging.exception("Unexpected startup failure")
        QMessageBox.critical(None, "Ошибка запуска", "Неожиданная ошибка запуска. Подробности записаны в slopeforge.log.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
