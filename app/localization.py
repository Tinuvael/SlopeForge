"""Qt localization and the machine-local language preference."""

from __future__ import annotations

import logging
from pathlib import Path
import xml.etree.ElementTree as ET

from PySide6.QtCore import QCoreApplication, QSettings, QTranslator

from app.resources import resource_path

ORGANIZATION_NAME = "Tinuvael"
APPLICATION_NAME = "SlopeForge"
LANGUAGE_KEY = "ui/language"
SUPPORTED_LANGUAGES = ("en", "ru")

logger = logging.getLogger(__name__)
_translator: QTranslator | None = None

# Small compatibility bridge for strings introduced after the current TS catalogue
# was frozen. Issue #64 will fold these back into the normal catalogue pass.
RUSSIAN_RUNTIME_FALLBACKS = {
    "Project tree": "Дерево проекта",
    "Collapse domains": "Свернуть домены",
    "Hide navigation": "Скрыть навигацию",
    "Show navigation": "Показать навигацию",
    "Analysis": "Анализ",
    "Analysis section is under development.": "Раздел анализа находится в разработке.",
}

# Qt asks the installed translator for platform-theme captions in contexts such
# as QPlatformTheme.  Returning an empty string there produces blank standard
# buttons on some Windows/PySide builds, instead of falling back to English.
_STANDARD_BUTTON_SOURCES = {
    "OK": "OK", "Save": "Save", "Cancel": "Cancel", "Yes": "Yes",
    "No": "No", "Close": "Close", "Discard": "Discard", "Restore": "Restore",
}


class TsTranslator(QTranslator):
    """Small Qt translator backed directly by a standard Linguist TS file."""

    def __init__(self, parent: QCoreApplication | None = None):
        super().__init__(parent)
        self._messages: dict[tuple[str, str], str] = {}

    def load(self, filename: str | Path, *args, **kwargs) -> bool:  # noqa: ARG002
        """Parse a TS catalogue, returning ``False`` for missing/malformed XML."""
        self._messages.clear()
        try:
            root = ET.parse(filename).getroot()
            if root.tag != "TS":
                return False
            for context_element in root.findall("context"):
                context = context_element.findtext("name", default="")
                for message in context_element.findall("message"):
                    if message.get("type") in {"obsolete", "vanished"}:
                        continue
                    source = message.findtext("source")
                    translation = message.find("translation")
                    if source is None or translation is None:
                        continue
                    if translation.get("type") in {"unfinished", "obsolete", "vanished"}:
                        continue
                    text = "".join(translation.itertext())
                    if text:
                        self._messages[(context, source)] = text
        except (OSError, ET.ParseError, ValueError):
            self._messages.clear()
            return False
        return True

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        """Return an empty string for Qt's normal English-source fallback."""
        del disambiguation, n
        translated = self._messages.get((context, source_text), "")
        if translated:
            return translated
        if context == "SlopeForge" and source_text in RUSSIAN_RUNTIME_FALLBACKS:
            return RUSSIAN_RUNTIME_FALLBACKS[source_text]
        # Platform captions may contain mnemonic markers or an ellipsis.
        normalized = source_text.replace("&", "").removesuffix("...")
        canonical = _STANDARD_BUTTON_SOURCES.get(normalized)
        if canonical:
            return self._messages.get(("SlopeForge", canonical), canonical)
        return ""


def settings() -> QSettings:
    return QSettings(ORGANIZATION_NAME, APPLICATION_NAME)


def normalize_language(value: object) -> str:
    code = str(value or "en").lower()
    return code if code in SUPPORTED_LANGUAGES else "en"


def selected_language(store: QSettings | None = None) -> str:
    return normalize_language((store or settings()).value(LANGUAGE_KEY, "en"))


def save_language(code: str, store: QSettings | None = None) -> str:
    normalized = normalize_language(code)
    target = store or settings()
    target.setValue(LANGUAGE_KEY, normalized)
    target.sync()
    return normalized


def install_selected_translator(app: QCoreApplication, store: QSettings | None = None) -> str:
    """Install Russian before any widgets are built; safely retain English on failure."""
    global _translator
    if _translator is not None:
        app.removeTranslator(_translator)
        _translator = None
    language = selected_language(store)
    if language == "en":
        _translator = None
        return "en"
    path = resource_path("translations/slopeforge_ru.ts")
    translator = TsTranslator(app)
    if path is None or not translator.load(str(path)):
        logger.warning("Could not load Russian TS translation; falling back to English")
        _translator = None
        return "en"
    app.installTranslator(translator)
    _translator = translator
    return "ru"


def tr(source: str, disambiguation: str | None = None, n: int = -1) -> str:
    """Translate canonical English presentation text in one stable context."""
    translated = QCoreApplication.translate("SlopeForge", source, disambiguation, n)
    return translated or source
