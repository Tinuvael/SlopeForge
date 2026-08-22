from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings
import pytest

import app.localization as localization
from app.localization import LANGUAGE_KEY, TsTranslator, install_selected_translator, normalize_language, save_language, selected_language, tr
from ui.presentation_labels import criterion_label, domain_message, history_text, matrix_label, option_label, result_label, technical_group_label, technical_text

from application.services.blast_events import BlastEventService, BlastEventValidationError
from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def isolated_settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_default_persistence_and_unsupported_fallback(tmp_path):
    store = isolated_settings(tmp_path)
    assert selected_language(store) == "en"
    for language in ("en", "ru"):
        assert save_language(language, store) == language
        assert store.value(LANGUAGE_KEY) == language
    assert normalize_language("de") == "en"
    assert save_language("unsupported", store) == "en"


def test_ts_catalog_can_be_parsed_and_translates_representative_text(qapp):
    translator = TsTranslator(qapp)
    assert translator.load("translations/slopeforge_ru.ts")
    expected = {
        "Add": "Добавить", "Settings": "Настройки", "Project": "Проект",
        "Block": "Блок", "Photos": "Фото", "Documents": "Документы",
    }
    assert {source: translator.translate("SlopeForge", source) for source in expected} == expected
    assert translator.translate("SlopeForge", "Unknown source text") == ""
    assert translator.translate("QPlatformTheme", "&OK") == "ОК"
    assert translator.translate("QPlatformTheme", "&Yes") == "Да"
    assert translator.translate("QPlatformTheme", "&No") == "Нет"
    assert translator.translate("QDialogButtonBox", "Cancel") == "Отмена"


def test_russian_catalog_presentation_and_validation(qapp, tmp_path):
    store = isolated_settings(tmp_path)
    save_language("ru", store)
    assert install_selected_translator(qapp, store) == "ru"
    assert tr("Unknown source text") == "Unknown source text"
    assert technical_group_label("main_pattern") == "Основная сеть"
    assert matrix_label("controlled_blasting_v1") == "С контурным бурением"
    assert criterion_label("bench_angle") == "Отклонение угла откоса от проекта, °"
    assert option_label("none") == "Нет"
    assert result_label("Хорошие результаты") == "Хорошие результаты"
    assert technical_text("Скважины") == "Скважины"
    assert domain_message("Не заполнено: Дата оценки, Инспектор") == "Не заполнены обязательные поля: Дата оценки, Инспектор"
    assert history_text("Created production Block") == "Создан производственный блок"
    assert history_text("Created contour Blast Event") == "Создан контурный взрыв"
    assert "main_pattern" == "main_pattern"


def test_english_installs_no_russian_translator(qapp, tmp_path):
    store = isolated_settings(tmp_path)
    save_language("en", store)
    assert install_selected_translator(qapp, store) == "en"
    assert localization._translator is None
    assert tr("Add") == "Add"


def _presented_blast_error(call) -> str:
    with pytest.raises(BlastEventValidationError) as caught:
        call()
    return domain_message(str(caught.value))


@pytest.mark.parametrize(
    ("language", "expected"),
    (("en", "Enter a blast event name"), ("ru", "Укажите название взрывного события")),
)
def test_blast_event_validation_uses_selected_locale(qapp, tmp_path, language, expected):
    store = isolated_settings(tmp_path)
    save_language(language, store)
    assert install_selected_translator(qapp, store) == language
    service = BlastEventService(AssessmentDomainState())
    assert _presented_blast_error(lambda: service.create_event(
        name="", event_type="production", event_date=None, elevation=500, csv_path="unused.csv",
    )) == expected


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        ("en", "Geometry file contains no valid contour drillholes"),
        ("ru", "Файл геометрии не содержит допустимых контурных скважин"),
    ),
)
def test_empty_blast_geometry_error_uses_selected_locale(qapp, tmp_path, language, expected):
    store = isolated_settings(tmp_path)
    save_language(language, store)
    assert install_selected_translator(qapp, store) == language
    source = tmp_path / "empty.csv"
    source.write_text("XP,YP,ZP,SID,PTN\n", encoding="utf-8")
    service = BlastEventService(AssessmentDomainState())
    assert _presented_blast_error(
        lambda: service.inspect_event_geometry("contour", source)
    ) == expected


@pytest.mark.parametrize(
    ("language", "prefix"),
    (("en", "Could not import geometry file: "), ("ru", "Не удалось импортировать файл геометрии: ")),
)
def test_dynamic_geometry_import_detail_is_preserved(qapp, tmp_path, monkeypatch, language, prefix):
    store = isolated_settings(tmp_path)
    save_language(language, store)
    assert install_selected_translator(qapp, store) == language

    def invalid_geometry(*_args, **_kwargs):
        raise ValueError("invalid column XP")

    monkeypatch.setattr("application.services.blast_events.import_line_geometry", invalid_geometry)
    service = BlastEventService(AssessmentDomainState())
    assert _presented_blast_error(
        lambda: service.inspect_event_geometry("production", "lines.csv")
    ) == prefix + "invalid column XP"


@pytest.mark.parametrize(
    ("language", "expected"),
    (("en", "Dataset 'D-003' was not found"), ("ru", "Набор данных 'D-003' не найден")),
)
def test_dynamic_dataset_id_is_preserved(qapp, tmp_path, language, expected):
    store = isolated_settings(tmp_path)
    save_language(language, store)
    assert install_selected_translator(qapp, store) == language
    service = ProjectLinesDatasetService(AssessmentDomainState())
    with pytest.raises(ValueError) as caught:
        service.set_active("D-003")
    assert domain_message(str(caught.value)) == expected


def test_active_validation_producers_remain_canonical_english():
    for source in (
        "application/services/blast_events.py",
        "application/services/project_lines.py",
    ):
        text = Path(source).read_text(encoding="utf-8")
        assert not any("А" <= character <= "я" or character in "Ёё" for character in text)


@pytest.mark.parametrize("catalog_contents", [None, "<TS><broken>"])
def test_missing_or_malformed_ts_safely_falls_back(qapp, tmp_path, monkeypatch, catalog_contents):
    catalog = tmp_path / "bad.ts"
    if catalog_contents is not None:
        catalog.write_text(catalog_contents, encoding="utf-8")
    monkeypatch.setattr(localization, "resource_path", lambda _path: catalog if catalog.exists() else None)
    warnings = []
    monkeypatch.setattr(localization.logger, "warning", lambda message, *args, **kwargs: warnings.append(message))
    store = isolated_settings(tmp_path)
    save_language("ru", store)
    assert install_selected_translator(qapp, store) == "en"
    assert localization._translator is None
    assert tr("Add") == "Add"
    assert warnings and "falling back to English" in warnings[-1]


def test_unfinished_obsolete_and_empty_translations_are_ignored(qapp, tmp_path):
    catalog = tmp_path / "states.ts"
    catalog.write_text('''<?xml version="1.0" encoding="utf-8"?>
<TS><context><name>SlopeForge</name>
<message><source>Unfinished</source><translation type="unfinished">Черновик</translation></message>
<message type="vanished"><source>Vanished</source><translation>Исчез</translation></message>
<message><source>Empty</source><translation></translation></message>
</context></TS>''', encoding="utf-8")
    translator = TsTranslator(qapp)
    assert translator.load(catalog)
    assert translator.translate("SlopeForge", "Unfinished") == ""
    assert translator.translate("SlopeForge", "Vanished") == ""
    assert translator.translate("SlopeForge", "Empty") == ""
