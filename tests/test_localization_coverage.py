"""Focused static coverage checks for active user-interface localization."""
from __future__ import annotations

import ast
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = [ROOT / "main.py", *sorted((ROOT / "app").rglob("*.py")), *sorted((ROOT / "ui").rglob("*.py")), *sorted((ROOT / "widgets").rglob("*.py"))]
INVARIANTS = {"SlopeForge", "DAI", "FCI", "UCS", "RQD", "GSI", "FF", "Jn", "Jr", "Ja", "Jw", "Q′", "MPa", "m", "mm", "kg", "ms", "m²", "m³", "%", "—"}
UI_CALLS = {"QLabel", "QPushButton", "QCheckBox", "QGroupBox", "setText", "setWindowTitle", "setToolTip", "setPlaceholderText", "addAction", "addTab", "addRow", "setHorizontalHeaderLabels", "addItem"}
MESSAGE_BOX_CALLS = {"critical", "information", "question", "warning"}
SELF_READABLE_LANGUAGE_ITEMS = {"English", "Русский", "en", "ru"}


def tree(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def literal_tr_sources():
    found = set()
    for path in ACTIVE:
        for node in ast.walk(tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    found.add(node.args[0].value)
    return found


def russian_catalog():
    root = ET.parse(ROOT / "translations" / "slopeforge_ru.ts").getroot()
    messages = {}
    for context in root.findall("context"):
        if context.findtext("name") != "SlopeForge":
            continue
        for message in context.findall("message"):
            translation = message.find("translation")
            if translation is not None and translation.get("type") not in {"unfinished", "obsolete", "vanished"}:
                messages[message.findtext("source", "")] = "".join(translation.itertext())
    return messages


def test_every_literal_tr_call_has_finished_russian_translation():
    catalogue = russian_catalog()
    missing = sorted(source for source in literal_tr_sources()
                     if source not in INVARIANTS
                     and not catalogue.get(source))
    assert missing == []


def test_important_indirect_presentation_sources_are_in_catalogue():
    """Guard strings passed through translating helpers or runtime mappings."""
    required = {
        "Plan / assessment areas",
        "Import / Update Project Lines",
        "Assessment result distribution",
        "Domain summary",
        "Elevation intervals",
        "No completed assessment",
        "Geometry achieved, condition insufficient",
        "Good results",
        "Unacceptable results",
        "Condition good, geometry unacceptable",
        "No Project Lines",
        "Import lines",
        "Update lines",
        "Import",
        "No Domain geometry",
        "DAI / FCI over time",
        "Daily average · all completed assessments",
        "No completed data",
        "Assessment Area",
        "Created",
        "Updated",
        "Assessment completed",
        "Assessment draft saved",
        "Details", "Boundary", "Review", "Area details", "Area name",
        "Assessment date", "Context", "Domain", "Project Lines", "Source",
        "Geometry", "Elevation interval", "Traced spans", "Connectors", "Links",
        "Potential events", "Production", "Contour blast", "Getting started",
        "Enter Area details.", "Verify Domain and active Project Lines.",
        "Continue to Boundary.", "Click near a Project Line to snap.",
        "Follow the line to trace the boundary.", "Move away to create a connector.",
        "Close the boundary when finished.", "Traced Project Line", "Connector",
        "Snap point", "Linked-event preview unavailable", "Boundary valid",
        "Elevation summary derived", "Linked-event preview completed", "Total",
        "Project plan", "Define Assessment boundary", "Assessment footprint",
        "Planned", "In preparation", "Blasted", "Assessed", "Completed", "Draft",
        "Archived", "Active", "Inactive", "Enabled", "Disabled",
    }
    # Category labels are stable presentation text paired with canonical userData.
    from domain.attachments.policy import ATTACHMENT_CATEGORIES
    required.update(label for categories in ATTACHMENT_CATEGORIES.values()
                    for _key, label in categories)
    catalogue = russian_catalog()
    assert sorted(source for source in required if not catalogue.get(source)) == []


def test_obvious_widget_literals_do_not_bypass_translation():
    raw = []
    for path in ACTIVE:
        for node in ast.walk(tree(path)):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name not in UI_CALLS and name not in MESSAGE_BOX_CALLS:
                continue
            # Only display arguments are audited; later addItem arguments are stable userData.
            if name in MESSAGE_BOX_CALLS:
                arguments = node.args[1:]
            else:
                arguments = node.args if name == "setHorizontalHeaderLabels" else node.args[:1]
            for argument in arguments:
                values = argument.elts if isinstance(argument, (ast.List, ast.Tuple)) else [argument]
                for value in values:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and any(ch.isalpha() for ch in value.value):
                        if value.value not in SELF_READABLE_LANGUAGE_ITEMS and value.value not in INVARIANTS:
                            raw.append(f"{path.relative_to(ROOT)}:{node.lineno}: {value.value}")
    assert raw == []


def test_representative_active_screen_labels_are_translated():
    catalogue = russian_catalog()
    expected = {
        "General information": "Общая информация", "Geomechanics": "Геомеханика",
        "Blast design": "Проект БВР", "Execution fact": "Фактическое выполнение",
        "Overview": "Обзор", "Assessment": "Оценка", "Result": "Результат",
        "Design results": "Результаты достижения проектной геометрии",
        "Criterion": "Критерий", "Entered / selected": "Введено / выбрано",
        "Domains": "Домены", "Analytics": "Аналитика", "Map": "План",
        "Projects": "Проекты", "Blast events": "Взрывные события",
        "Archive": "Архивировать", "Add project": "Добавить проект",
        "Add domain": "Добавить домен", "Add blast event": "Добавить взрывное событие",
        "Add assessment area": "Добавить участок оценки",
        "Assessment areas": "Участки оценки", "Horizon": "Горизонт",
        "Interval": "Интервал", "Block": "Блок",
        "Contour blast": "Контурный взрыв",
    }
    assert {source: catalogue[source] for source in expected} == expected
    assert catalogue["Project tree"] == "Дерево проекта"


def test_active_ui_has_no_runtime_russian_fallback_bridge():
    source = (ROOT / "app" / "localization.py").read_text(encoding="utf-8")
    assert "RUSSIAN_RUNTIME_FALLBACKS" not in source


def test_event_type_selector_translates_display_but_keeps_canonical_user_data():
    source = (ROOT / "ui" / "dialogs" / "blast_event_dialog.py").read_text(encoding="utf-8")
    assert 'addItem(tr("Production"), "production")' in source
    assert 'addItem(tr("Contour blast"), "contour")' in source
    assert '"event_type": self.kind.currentData()' in source


def test_attachment_categories_translate_labels_but_keep_codes_as_user_data():
    source = (ROOT / "ui" / "dialogs" / "entity_attachment_dialog.py").read_text(encoding="utf-8")
    assert "addItem(tr(label), code)" in source
    assert "subtype=self.category.currentData()" in source
    assert "subtype=category.currentData()" in source


def test_internal_group_ids_are_not_rendered_in_technical_card():
    source = (ROOT / "ui" / "editors" / "technical_card_editor.py").read_text(encoding="utf-8")
    assert 'QGroupBox(f"{display_name} — {group.group_type}")' not in source
    assert 'QLabel(display_name)' in source


def test_header_tree_and_block_tabs_use_translated_presentation_labels():
    header = (ROOT / "ui" / "header.py").read_text(encoding="utf-8")
    tree_source = (ROOT / "ui" / "widgets" / "project_tree.py").read_text(encoding="utf-8")
    block = (ROOT / "ui" / "pages" / "block_page.py").read_text(encoding="utf-8")
    for label in ("Add project", "Add domain", "Add blast event", "Add assessment area", "Archive"):
        assert f'tr("{label}")' in header
    for label in ("Blast events", "Assessment areas", "Horizon", "Interval", "Block"):
        assert f"tr('{label}')" in tree_source or f'tr("{label}")' in tree_source
    for label in ("Geomechanics", "Blast design", "Execution fact"):
        assert f'tr("{label}")' in block
