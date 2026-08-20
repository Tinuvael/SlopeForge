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
    "Browse...": "Обзор...",
    "Create Domain": "Создать домен",
    "Create Project": "Создать проект",
    "Domain name": "Название домена",
    "Edit Assessment Area": "Изменить участок оценки",
    "Edit Block": "Изменить блок",
    "Edit Contour Blast": "Изменить контурный взрыв",
    "Horizon, m *": "Горизонт, м *",
    "No file selected": "Файл не выбран",
    "Project Lines can also be imported later from the Project dashboard.":
        "Линии проекта также можно импортировать позже на странице проекта.",
    "Project Lines file": "Файл линий проекта",
    "Save & complete": "Сохранить и завершить",
    "Enabled": "Включено",
    "Search projects, domains and entities…": "Поиск проектов, доменов и объектов…",
    "No users found.": "Пользователи не найдены.",
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
    "The file will be removed from the database and disk.": "Файл будет удалён из базы данных и диска.",
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
    "No geomechanics data yet": "Данных геомеханики пока нет",
    "Open section": "Открыть раздел",
    # Compact Project/Domain dashboards (#69).
    "Project overview": "Обзор проекта",
    "Domain overview": "Обзор домена",
    "Plan / assessment areas": "План / участки оценки",
    "Import / Update Project Lines": "Импорт / обновить проектные линии",
    "Import Project Lines": "Импортировать проектные линии",
    "Update Project Lines": "Обновить проектные линии",
    "No Project Lines": "Проектные линии не загружены",
    "Import lines": "Импортировать линии",
    "Update lines": "Обновить линии",
    "Import": "Импортировать",
    "Assessment result distribution": "Распределение результатов оценки",
    "Attention required": "Требуют внимания",
    "No areas require attention": "Нет участков, требующих внимания",
    "Assessment progress": "Прогресс оценки",
    "Completed: %1  ·  Draft: %2  ·  Not evaluated: %3": "Завершено: %1  ·  Черновики: %2  ·  Не оценено: %3",
    "Domain summary": "Сводка по доменам",
    "No Domains yet": "Доменов пока нет",
    "Blast events: %1 • Production: %2 • Contour: %3": "Взрывные события: %1 • Производственные: %2 • Контурные: %3",
    "Production: %1 • Contour: %2": "Производственные: %1 • Контурные: %2",
    "Production: %1  ·  Contour: %2": "Производственные: %1  ·  Контурные: %2",
    "Elevation intervals": "Интервалы высот",
    "Assessment areas: %1 • Evaluated: %2": "Участки оценки: %1 • Оценено: %2",
    "Latest assessments": "Последние оценки",
    "No completed assessments yet": "Завершённых оценок пока нет",
    "Blast activity": "Взрывная активность",
    "No dated Blast Events yet": "Взрывных событий с датой пока нет",
    "Latest blast": "Последний взрыв",
    "No Domain geometry defined": "Геометрия домена не задана",
    "No Domain geometry": "Геометрия домена не задана",
    "No Assessment Areas yet": "Участков оценки пока нет",
    "No completed assessment": "Нет завершённой оценки",
    "Geometry achieved, condition insufficient": "Геометрия достигнута, состояние борта недостаточно",
    "Good results": "Хорошие результаты",
    "Unacceptable results": "Неприемлемые результаты",
    "Condition good, geometry unacceptable": "Состояние борта хорошее, геометрия неприемлема",
    "DAI / FCI over time": "DAI / FCI во времени",
    "Daily average · all completed assessments": "Среднее за день · все завершённые оценки",
    "No completed data": "Нет завершённых данных",
    "Assessment Area": "Участок оценки",
    "Created": "Создано",
    "Updated": "Обновлено",
    "Assessment completed": "Оценка завершена",
    "Assessment draft saved": "Черновик оценки сохранён",
    "Imported": "Импортировано",
    "Clear": "Очистить",
    # Connection setup/settings (#110). Keep source UI English; #64 will fold
    # these temporary fallbacks into the maintained TS catalogue.
    "Connection": "Подключение",
    "Connection settings": "Настройки подключения",
    "Connection configuration error": "Ошибка настройки подключения",
    "Enter the connection settings again.": "Введите настройки подключения заново.",
    "PostgreSQL server": "Сервер PostgreSQL",
    "Server / Host": "Сервер / Хост",
    "Port": "Порт",
    "Database": "База данных",
    "Password": "Пароль",
    "File storage": "Хранилище файлов",
    "Use a folder that all SlopeForge users can access.": "Используйте папку, доступную всем пользователям SlopeForge.",
    "Browse…": "Обзор…",
    "Select file storage folder": "Выберите папку хранилища файлов",
    "Testing PostgreSQL and file storage…": "Проверка PostgreSQL и хранилища файлов…",
    "Connection test failed": "Проверка подключения не выполнена",
    "Connection and file storage are available.": "Подключение и хранилище файлов доступны.",
    "SlopeForge connection setup": "Настройка подключения SlopeForge",
    "Connect SlopeForge": "Подключение SlopeForge",
    "Configure the PostgreSQL server and shared file storage before signing in.": "Настройте сервер PostgreSQL и общее хранилище файлов перед входом.",
    "Test connection": "Проверить подключение",
    "Save and continue": "Сохранить и продолжить",
    "Edit the PostgreSQL server and shared file storage used on the next SlopeForge start.": "Измените сервер PostgreSQL и общее хранилище файлов для следующего запуска SlopeForge.",
    "DATABASE_URL and STORAGE_ROOT currently override saved connection settings.": "DATABASE_URL и STORAGE_ROOT сейчас переопределяют сохранённые настройки подключения.",
    "Save changes": "Сохранить изменения",
    "Connection settings saved": "Настройки подключения сохранены",
    "Restart SlopeForge to use the new connection and file storage settings.": "Перезапустите SlopeForge, чтобы использовать новые настройки подключения и хранилища файлов.",
}

_STANDARD_BUTTON_SOURCES = {
    "OK": "OK", "Save": "Save", "Cancel": "Cancel", "Yes": "Yes",
    "No": "No", "Close": "Close", "Discard": "Discard", "Restore": "Restore",
}


class TsTranslator(QTranslator):
    def __init__(self, parent: QCoreApplication | None = None):
        super().__init__(parent)
        self._messages: dict[tuple[str, str], str] = {}

    def load(self, filename: str | Path, *args, **kwargs) -> bool:  # noqa: ARG002
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
        del disambiguation, n
        translated = self._messages.get((context, source_text), "")
        if translated:
            return translated
        if context == "SlopeForge" and source_text in RUSSIAN_RUNTIME_FALLBACKS:
            return RUSSIAN_RUNTIME_FALLBACKS[source_text]
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
    translated = QCoreApplication.translate("SlopeForge", source, disambiguation, n)
    return translated or source
