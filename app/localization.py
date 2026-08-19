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
    "Parameter": "Параметр",
    "Actual": "Факт",
    "Add documents": "Добавить документы",
    "document": "документ",
    "documents": "документов",
    "selected": "выбрано",
    "Titles are filled automatically from file names. Review categories and dates before importing.": "Названия заполняются автоматически по именам файлов. Проверьте категории и даты перед импортом.",
    "Apply to all:": "Применить ко всем:",
    "Apply category": "Применить категорию",
    "Apply date": "Применить дату",
    "File": "Файл",
    "Title": "Название",
    "Category": "Категория",
    "Date": "Дата",
    "Document": "Документ",
    "Size": "Размер",
    "Sort by:": "Сортировка:",
    "Open folder": "Открыть папку",
    "Edit metadata": "Изменить метаданные",
    "Photo details": "Данные фото",
    "File details": "Данные файла",
    "Filled automatically from the file name.": "Заполняется автоматически по имени файла.",
    "Custom category": "Своя категория",
    "Description": "Описание",
    "Preview is not available": "Предпросмотр недоступен",
    "Back": "Назад",
    "Fit": "Вписать",
    "No photos yet": "Фото пока нет",
    "Add files": "Добавить файлы",
    "Other format": "Другой формат",
    "The selected photo format is not supported.": "Выбранный формат фото не поддерживается.",
    "SlopeForge may not be able to preview this file. Add it anyway?": "SlopeForge может не поддерживать предпросмотр этого файла. Всё равно добавить?",
    "File is missing": "Файл отсутствует",
    "The file is missing from disk.": "Файл отсутствует на диске.",
    "Copy error": "Ошибка копирования",
    "Edit error": "Ошибка изменения",
    "Delete error": "Ошибка удаления",
    "The file will be removed from the database and disk.": "Файл будет удалён из базы данных и с диска.",
    "Cleanup warning": "Предупреждение очистки",
    "The attachment was deleted, but a temporary file could not be removed.": "Вложение удалено, но временный файл удалить не удалось.",
    "Photos and documents": "Фото и документы",
    "Date & time": "Дата и время",
    "User": "Пользователь",
    "Change": "Изменение",
    "Details": "Подробности",
    "No history yet": "Истории пока нет",
    "Open revision": "Открыть ревизию",
    "Double-click to open this historical revision.": "Дважды щёлкните, чтобы открыть эту историческую ревизию.",
    "Assessment geometry": "Геометрия участка оценки",
    "Blast geometry": "Геометрия взрывного события",
    "Historical revision is read-only.": "Историческая ревизия доступна только для просмотра.",
    "Geometry & face condition": "Геометрия и состояние борта",
    # Unified entity Overview (#120). Keep these temporary until #64 folds them
    # into the normal Qt Linguist catalogue.
    "Project / Domain": "Проект / Домен",
    "Geometry rev.": "Ревизия геометрии",
    "Rev.": "Рев.",
    "Open ›": "Открыть ›",
    "History ›": "История ›",
    "Plan / geometry": "План / геометрия",
    "Recent activity": "Последние изменения",
    "Engineering summary": "Инженерная сводка",
    "Engineering notes": "Инженерные примечания",
    "Notes": "Примечания",
    "No notes": "Нет примечаний",
    "No data yet": "Данных пока нет",
    "Very unstable": "Весьма неустойчиво",
    "Unstable": "Неустойчиво",
    "Moderately stable": "Средней устойчивости",
    "Stable": "Устойчиво",
    "Not calculated": "Не рассчитано",
    "Stability": "Устойчивость",
    "Pattern": "Сетка",
    "Holes": "Скважины",
    "Blast date": "Дата взрыва",
    "Block area": "Площадь блока",
    "Bench height": "Высота уступа",
    "Geometry": "Геометрия",
    "Design": "Проект",
    "Technical Card": "Техническая карточка",
    "Source geometry": "Исходная геометрия",
    "Imported": "Импортировано",
    "Method": "Метод",
    "Line length": "Длина линии",
    "Azimuth": "Азимут",
    "Inclination": "Наклон",
    "Spacing": "Шаг",
    "Assessment area geometry": "Геометрия участка оценки",
    "Assessment summary": "Сводка оценки",
    "Geometry source": "Источник геометрии",
    "Revision reason": "Причина ревизии",
    "Free boundary": "Свободная граница",
    "Evaluation": "Ревизия оценки",
    "No recommendations": "Нет рекомендаций",
    "No assessment result yet": "Результата оценки пока нет",
    "Created by": "Создал",
    "Last updated": "Последнее обновление",
    "Geometry file": "Файл геометрии",
    "Geometry revision": "Ревизия геометрии",
    "Related assessment areas": "Связанные участки оценки",
    "No linked assessment areas": "Нет связанных участков оценки",
    "Related blast events": "Связанные взрывные события",
    "No linked blast events": "Нет связанных взрывных событий",
    "Assessment result": "Результат оценки",
    "Face condition": "Состояние борта",
    "Comments / recommendations": "Комментарии / рекомендации",
    "Inspector": "Инспектор",
    "Result": "Результат",
    "Drilling length": "Метраж бурения",
    "Diameter": "Диаметр",
    "Rejected": "Брак",
    "Wet": "Обводнённые",
    "Redrilled": "Перебуренные",
    "Uncharged": "Не заряженные",
    "No linked entities": "Нет связанных объектов",
    "Angle deviation": "Отклонение угла",
    "Berm deviation": "Отклонение бермы",
    "Toe deviation": "Отклонение подошвы",
    "No geometry assessment data yet": "Данных оценки геометрии пока нет",
    "Contour hole traces": "Следы контурных скважин",
    "Loose blocks": "Свободные блоки",
    "Face profile": "Профиль откоса",
    "Crest loss": "Потеря бровки",
    "Blast damage": "Взрывные повреждения",
    "Blast cracks": "Взрывные трещины",
    "No face-condition data yet": "Данных о состоянии борта пока нет",
    "Suggested": "Предложено",
    "Explosive": "ВВ",
    "No blast-design data yet": "Данных проекта БВР пока нет",
    "No execution data yet": "Фактических данных пока нет",
    "No geomechanics data yet": "Геомеханических данных пока нет",
    "Open section": "Открыть раздел",
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
