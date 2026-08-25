from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QMessageBox
from sqlalchemy.engine import make_url

from app.connection_settings import (
    DATABASE_ONLY,
    FULL_STORAGE,
    ConnectionProfile,
    ConnectionSettingsError,
    ConnectionSettingsStore,
    environment_profile,
)
from app.context import AppContext
from app.localization import tr
from database.settings import Settings
from database.startup import StartupError, initialize_database_runtime
from infrastructure.services.auth_service import AuthService
from infrastructure.services.session_service import RememberTokenService
from ui.auth_dialogs import FirstAdminDialog, LoginDialog
from ui.connection_dialog import ServerSelectionDialog
from ui.main_window import MainWindow

logger = logging.getLogger(__name__)

_CHANGE_CONNECTION = "change_connection"
_RETRY = "retry"


@dataclass(frozen=True)
class RuntimeTarget:
    profile: ConnectionProfile
    settings: Settings
    source: str
    update_auto_preference: bool = False
    auto_connect_requested: bool = False


@dataclass
class ActiveDesktopRuntime:
    target: RuntimeTarget
    settings: Settings
    engine: object
    session_factory: object
    window: MainWindow


class DesktopRuntimeController:
    """Own exactly one DB-bound desktop runtime and replace it atomically on switch."""

    def __init__(
        self,
        app,
        connection_store: ConnectionSettingsStore,
        *,
        startup_error_handler: Callable[[StartupError], str],
        splash_factory: Callable[[], object],
    ):
        self.app = app
        self.connection_store = connection_store
        self.startup_error_handler = startup_error_handler
        self.splash_factory = splash_factory
        self.current: ActiveDesktopRuntime | None = None
        about_to_quit = getattr(app, "aboutToQuit", None)
        if about_to_quit is not None and hasattr(about_to_quit, "connect"):
            about_to_quit.connect(self.dispose_current)

    @staticmethod
    def _environment_scope(settings: Settings) -> str:
        url = make_url(settings.database_url)
        identity = "|".join(
            (
                str(url.username or ""),
                str(url.host or "localhost"),
                str(url.port or 5432),
                str(url.database or ""),
            )
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        return f"environment-{digest}"

    @staticmethod
    def _profile_mode(profile: ConnectionProfile, settings: Settings) -> str:
        if profile.mode in {FULL_STORAGE, DATABASE_ONLY}:
            return profile.mode
        return DATABASE_ONLY if settings.storage_root is None else FULL_STORAGE

    def _target_from_profile(
        self,
        profile: ConnectionProfile,
        *,
        source: str = "saved",
        update_auto_preference: bool = False,
        auto_connect_requested: bool = False,
    ) -> RuntimeTarget:
        return RuntimeTarget(
            profile=profile,
            settings=profile.to_settings(),
            source=source,
            update_auto_preference=update_auto_preference,
            auto_connect_requested=auto_connect_requested,
        )

    def _select_saved_target(
        self,
        *,
        parent=None,
        current_profile_id: str | None = None,
        title: str = "Select server",
    ) -> RuntimeTarget | None:
        dialog = ServerSelectionDialog(
            self.connection_store,
            parent,
            title=title,
            current_profile_id=current_profile_id,
        )
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.selected_profile is None:
            return None
        return self._target_from_profile(
            dialog.selected_profile,
            update_auto_preference=True,
            auto_connect_requested=bool(dialog.skip_selection.isChecked()),
        )

    def initial_target(self) -> RuntimeTarget | None:
        env = environment_profile()
        if env is not None:
            return self._target_from_profile(env, source="environment")

        auto_id = self.connection_store.auto_connect_profile_id()
        if auto_id:
            try:
                profile = self.connection_store.runtime_profile(auto_id)
                return self._target_from_profile(profile)
            except (ConnectionSettingsError, KeyError):
                self.connection_store.set_auto_connect_profile(None)

        # Selection is deliberately shown even when only one profile exists.
        return self._select_saved_target()

    def start(self) -> bool:
        try:
            target = self.initial_target()
        except ConnectionSettingsError as exc:
            QMessageBox.warning(None, tr("Connection settings"), str(exc))
            return False
        if target is None:
            return False
        active = self._build_runtime(target, allow_change=True)
        if active is None:
            return False
        self._commit_runtime(active, previous=None)
        return True

    def _build_runtime(
        self,
        target: RuntimeTarget,
        *,
        allow_change: bool,
    ) -> ActiveDesktopRuntime | None:
        while True:
            splash = self.splash_factory()
            try:
                splash.show_status(tr("Connecting to database…"))
                settings, engine, session_factory = initialize_database_runtime(
                    target.settings
                )
            except StartupError as exc:
                logger.exception("Database initialization failed")
                splash.close()
                action = self.startup_error_handler(exc)
                if action == _RETRY:
                    continue
                if action == _CHANGE_CONNECTION and allow_change:
                    if target.source == "environment":
                        QMessageBox.information(
                            None,
                            tr("Connection managed by environment"),
                            tr("This SlopeForge installation is pinned by DATABASE_URL. Change the environment configuration to use another server."),
                        )
                        return None
                    replacement = self._select_saved_target(
                        current_profile_id=target.profile.profile_id,
                    )
                    if replacement is None:
                        return None
                    target = replacement
                    continue
                return None
            except Exception:
                splash.close()
                raise

            current_user = self._authenticate(
                session_factory,
                target,
                splash,
            )
            if current_user is None:
                engine.dispose()
                return None

            scope_id = (
                target.profile.profile_id
                if target.source == "saved"
                else self._environment_scope(settings)
            )
            context = AppContext(
                session_factory=session_factory,
                current_user=current_user,
                storage_root=settings.storage_root,
                connection_profile_id=(
                    target.profile.profile_id if target.source == "saved" else ""
                ),
                connection_profile_name=target.profile.display_name,
                connection_mode=self._profile_mode(target.profile, settings),
                session_scope_id=scope_id,
                runtime_control=self,
            )
            try:
                window = MainWindow(context)
            except Exception:
                engine.dispose()
                raise
            return ActiveDesktopRuntime(
                target=target,
                settings=settings,
                engine=engine,
                session_factory=session_factory,
                window=window,
            )

    def _authenticate(self, session_factory, target: RuntimeTarget, splash):
        splash.show_status(tr("Checking database schema…"))
        auth_service = AuthService(session_factory)
        scope_id = (
            target.profile.profile_id
            if target.source == "saved"
            else self._environment_scope(target.settings)
        )
        remember_service = RememberTokenService(
            session_factory,
            scope_id=scope_id,
            migrate_legacy=True,
        )
        remembered = (
            remember_service.authenticate_local() if auth_service.has_users() else None
        )
        current_user = remembered.current_user if remembered else None
        if current_user is not None:
            splash.close_with_fade()
            return current_user

        if auth_service.has_users():
            dialog = LoginDialog(auth_service)
        else:
            dialog = FirstAdminDialog(auth_service)
        splash.close_with_fade()
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.current_user is None:
            return None
        current_user = dialog.current_user
        if isinstance(dialog, LoginDialog) and dialog.remember_requested:
            remember_service.create_for_user(current_user.id, current_user.username)
        return current_user

    def _persist_successful_selection(self, target: RuntimeTarget) -> None:
        if target.source != "saved" or not target.profile.profile_id:
            return
        self.connection_store.mark_used(target.profile.profile_id)
        if target.update_auto_preference:
            self.connection_store.set_auto_connect_profile(
                target.profile.profile_id if target.auto_connect_requested else None
            )

    def _commit_runtime(
        self,
        active: ActiveDesktopRuntime,
        *,
        previous: ActiveDesktopRuntime | None,
    ) -> None:
        self._persist_successful_selection(active.target)
        self.current = active
        active.window.showMaximized()
        if previous is not None:
            previous.window.close()
            previous.window.deleteLater()
            try:
                previous.engine.dispose()
            except Exception:
                logger.exception("Could not dispose previous database engine")

    def request_switch(self, profile_id: str | None = None, *, parent=None) -> bool:
        previous = self.current
        if previous is None:
            return False
        if previous.target.source == "environment":
            QMessageBox.information(
                parent,
                tr("Connection managed by environment"),
                tr("Runtime server switching is disabled while DATABASE_URL pins this installation."),
            )
            return False

        guard = getattr(previous.window, "_guard_leave", None)
        if callable(guard) and not guard():
            return False

        try:
            if profile_id:
                profile = self.connection_store.runtime_profile(profile_id)
                target = self._target_from_profile(profile)
            else:
                target = self._select_saved_target(
                    parent=parent,
                    current_profile_id=previous.target.profile.profile_id,
                    title="Switch server",
                )
        except (ConnectionSettingsError, KeyError) as exc:
            QMessageBox.warning(parent, tr("Connection settings"), str(exc))
            return False
        if target is None:
            return False

        if target.profile.profile_id == previous.target.profile.profile_id:
            if target.update_auto_preference:
                self._persist_successful_selection(target)
            return True

        active = self._build_runtime(target, allow_change=True)
        if active is None:
            return False
        self._commit_runtime(active, previous=previous)
        return True

    def dispose_current(self) -> None:
        active = self.current
        self.current = None
        if active is None:
            return
        try:
            active.engine.dispose()
        except Exception:
            logger.exception("Could not dispose database engine during shutdown")
