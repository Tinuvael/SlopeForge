from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QSettings
import pytest

import app.localization as localization
from app.localization import LANGUAGE_KEY, TsTranslator, install_selected_translator, normalize_language, save_language, selected_language, tr
from ui.presentation_labels import criterion_label, domain_message, matrix_label, option_label, result_label, technical_group_label, technical_text


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
    assert "main_pattern" == "main_pattern"


def test_english_installs_no_russian_translator(qapp, tmp_path):
    store = isolated_settings(tmp_path)
    save_language("en", store)
    assert install_selected_translator(qapp, store) == "en"
    assert localization._translator is None
    assert tr("Add") == "Add"


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