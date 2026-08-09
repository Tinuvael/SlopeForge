"""English presentation labels for stable domain IDs and legacy snapshots.

The keys stored in the database/domain snapshots are deliberately not changed.
"""

import re

from app.localization import tr

TECHNICAL_GROUP_LABELS = {
    "main_pattern": "Main pattern",
    "inner_buffer": "Inner buffer row",
    "outer_buffer": "Outer buffer row",
    "buffer": "Buffer holes",
    "cut_opening": "Cut / opening holes",
    "crest": "Crest holes",
    "toe": "Toe holes",
    "relief": "Relief holes",
    "auxiliary": "Auxiliary holes",
    "contour_line": "Contour row",
    "presplit_line": "Presplit line",
    "midsplit_line": "Midsplit line",
    "postsplit_line": "Postsplit line",
    "line_drilling": "Line drilling",
    "trim_row": "Trim row",
    "other": "Other type",
}

CONTROLLED_BLASTING_LABELS = {
    "buffer_cushion": "Buffer / cushion blasting",
    "trim": "Trim blasting",
    "presplit": "Presplitting",
    "midsplit": "Midsplitting",
    "postsplit": "Postsplitting",
    "line_drilling": "Uncharged line drilling",
    "other": "Other method",
}

MATRIX_LABELS = {
    "controlled_blasting_v1": "With contour drilling",
    "no_controlled_blasting_v1": "Without contour drilling",
}

CRITERION_LABELS = {
    "bench_angle": "Bench face angle shortfall from design, °",
    "berm_width": "Berm width deficit from design, m",
    "toe_position": "Actual toe deviation from design, m",
    "crest_loss": "Crest loss / damage, m",
    "open_cracks": "Open blast-induced cracks",
    "damage": "Blast damage features in previously intact rock, count/m²",
    "visible_drillhole_traces": "Visible contour drillhole traces, %",
    "loose_blocks": "Loose blocks and unstable fragments on the face",
    "face_profile": "Actual face profile",
}

CRITERION_HELP = {
    "bench_angle": "max(design angle − actual angle, 0)",
    "toe_position": "Enter the absolute distance between actual and design toe positions.",
    "crest_loss": "Enter the width of actual crest loss relative to the design position.",
    "damage": "Estimate visible crushed zones, opened discontinuities, or other damage features per 1 m². Values from 1 to 5 require an expert score and reason.",
    "visible_drillhole_traces": "Estimated share of preserved visible contour drillhole traces across the assessed area.",
}

OPTION_LABELS = {
    "closed": "All cracks closed / no cracks",
    "many_open": "Many open cracks",
    "none": "None",
    "several_small": "Several small blocks",
    "large": "Large blocks",
    "many": "Many blocks",
    "straight": "Straight profile",
    "hard_toe": "Hard toe",
    "hanging_crest": "Hanging rock at crest",
    "hanging_face": "Hanging rock on face",
    "irregular": "Irregular face surface",
}

RESULT_LABELS = {
    "Хорошие результаты": "Good results",
    "Геометрическая форма достигнута, верхняя и нижняя бровки соответствуют": "Geometry achieved, face condition insufficient",
    "Хорошее состояние борта. Геометрическая форма неприемлема, верхняя и нижняя бровки не соответствуют": "Face condition good, geometry unacceptable",
    "Неприемлемые результаты": "Unacceptable results",
}

DOMAIN_MESSAGES = {
    "Нет фактических групп": "No actual groups",
    "Не указана фактическая дата взрыва": "Actual blast date is missing",
    "Не указано число фактических скважин": "Actual hole count is missing",
    "Не указан фактический метраж бурения": "Actual drilling length is missing",
    "Добавьте группу бурения": "Add a drilling group",
    "Заполните минимальное геомеханическое описание": "Complete the minimum geomechanical description",
    "Выберите метод контурного взрывания": "Select a controlled blasting method",
    "Нельзя удалить последнюю основную сеть": "The last main pattern cannot be deleted",
    "Ручной балл вне допустимого диапазона": "Manual score is outside the allowed range",
    "Для ручного балла укажите причину": "Provide a reason for the manual score",
    "Неизвестный числовой критерий": "Unknown numeric criterion",
    "Для диапазона 1–5 укажите явное решение и причину": "For the range 1–5, provide an explicit score and reason",
    "Архивная Assessment Area доступна только для чтения": "Archived Assessment Areas are read-only",
    "Для ручного выбора матрицы укажите причину": "Provide a reason for manual matrix selection",
    "Сначала загрузите и выберите активный Dataset": "Load and select an active dataset first",
    "На одной отметке можно выбрать только один фрагмент": "Select only one fragment at each elevation",
    "Выберите фрагменты минимум на двух разных отметках": "Select fragments at least at two different elevations",
    "Нет активного Dataset": "There is no active dataset",
    "Сначала восстановите Assessment Area из архива": "Restore the Assessment Area before editing it",
    "Архивное событие или событие без геометрии нельзя связать": "Archived events and events without geometry cannot be linked",
    "Это событие уже связано с активной ревизией Assessment Area": "This event is already linked to the active Assessment Area revision",
    "Связь активной ревизии не найдена": "The active-revision link was not found",
    "Связи архивной Assessment Area доступны только для чтения": "Links of an archived Assessment Area are read-only",
    "Полигон должен содержать минимум три различные вершины": "The polygon must contain at least three distinct vertices",
    "Соседние вершины полигона совпадают": "Adjacent polygon vertices must not coincide",
    "Площадь полигона равна нулю": "The polygon area is zero",
    "Границы полигона пересекают сами себя": "The polygon boundary intersects itself",
    "Укажите название события": "Enter a blast event name",
    "Выберите тип события: production или contour": "Select the blast event type: production or contour",
    "Укажите горизонт события": "Enter the blast event horizon",
    "Не удалось прочитать файл как UTF-8. Сохраните CSV в UTF-8 или UTF-8 BOM.": "Could not read the file as UTF-8. Save the CSV as UTF-8 or UTF-8 BOM.",
    "Curved DXF polyline segments are not supported. Convert them to straight polyline segments before import.": "Curved DXF polyline segments are not supported. Convert them to straight polyline segments before import.",
    "ezdxf is required to import DXF geometry": "ezdxf is required to import DXF geometry",
    "Файл геометрии не содержит валидных контурных скважин": "Geometry file contains no valid contour drillholes",
    "Файл геометрии не содержит подходящих линий": "Geometry file contains no suitable lines",
    "Неизвестный тип владельца файла": "Unknown attachment owner type",
    "Некорректный ID владельца": "Invalid attachment owner ID",
    "Неизвестный тип файла": "Unknown attachment kind",
    "Путь файла выходит за каталог данных": "The attachment path is outside the data directory",
}

TECHNICAL_TEXT_LABELS = {
    "Скважины": "Holes", "Диаметр": "Diameter", "Средняя глубина": "Average depth",
    "Перебур": "Subdrill", "ЛНС / расстояние между рядами": "Burden / row spacing",
    "Шаг скважин в ряду": "Hole spacing in row", "Метраж бурения": "Drilling length",
    "Масса заряда на скважину": "Charge mass per hole", "Общая масса заряда": "Total charge mass",
    "Забойка": "Stemming", "Замедление": "Delay", "Всего скважин": "Total holes",
    "Общий метраж бурения": "Total drilling length", "Общая масса ВВ": "Total explosive mass",
    "Объём": "Volume", "Выход горной массы": "Rock yield", "Удельное бурение": "Specific drilling",
    "Удельный расход ВВ": "Powder factor", "ИТОГО": "TOTAL",
    "шт": "count", "мм": "mm", "м": "m", "кг": "kg", "мс": "ms",
    "м³": "m³", "м³/м": "m³/m", "м/м³": "m/m³", "кг/м³": "kg/m³",
}


def technical_group_label(key: str, fallback: str = "") -> str:
    return tr(TECHNICAL_GROUP_LABELS.get(key, fallback or key))


def matrix_label(matrix_id: str, fallback: str = "") -> str:
    return tr(MATRIX_LABELS.get(matrix_id, fallback or matrix_id))


def criterion_label(criterion_id: str, fallback: str = "") -> str:
    return tr(CRITERION_LABELS.get(criterion_id, fallback or criterion_id))


def option_label(option_id: str, fallback: str = "") -> str:
    return tr(OPTION_LABELS.get(option_id, fallback or option_id))


def result_label(value: str | None) -> str:
    return tr(RESULT_LABELS.get(value or "", value or ""))


def domain_message(value: str) -> str:
    """Translate known domain validation text without altering domain values.

    Prefix handling keeps useful dynamic details (IDs, column names and nested
    exceptions) while ensuring normal UI error paths remain English.
    """
    exact = DOMAIN_MESSAGES.get(value)
    if exact is not None:
        return tr(exact)
    if value.startswith("Could not read DXF: "):
        return tr("Could not read DXF: %1").replace("%1", value.removeprefix("Could not read DXF: "))
    unsupported = re.fullmatch(r"Unsupported geometry file extension (.+)\. Use \.csv or \.dxf\.", value)
    if unsupported:
        return tr("Unsupported geometry file extension %1. Use .csv or .dxf.").replace("%1", unsupported.group(1))
    prefixes = {
        "Не заполнено: ": "Missing required fields: ",
        "Не удалось импортировать CSV: ": "Could not import CSV: ",
        "Не удалось импортировать файл геометрии: ": "Could not import geometry file: ",
        "Не удалось прочитать CSV: ": "Could not read CSV: ",
        "Не сопоставлены обязательные колонки: ": "Required columns are not mapped: ",
        "Перенесён старый фактический метраж группы ": "Migrated legacy actual drilling length for group ",
    }
    for prefix, translated in prefixes.items():
        if value.startswith(prefix):
            detail = value[len(prefix):]
            if prefix == "Не заполнено: ":
                fields = {
                    "Дата оценки": "Assessment date", "Инспектор": "Inspector",
                    "Недобор угла относительно проекта, °": CRITERION_LABELS["bench_angle"],
                    "Уменьшение ширины относительно проекта, м": CRITERION_LABELS["berm_width"],
                    "Отклонение фактической подошвы от проектной, м": CRITERION_LABELS["toe_position"],
                    "Потеря / разрушение бровки, м": CRITERION_LABELS["crest_loss"],
                    "Открытые трещины взрывного происхождения": CRITERION_LABELS["open_cracks"],
                    "Признаки взрывного повреждения ранее ненарушенной породы, шт/м²": CRITERION_LABELS["damage"],
                    "Видимые следы контурных скважин, %": CRITERION_LABELS["visible_drillhole_traces"],
                    "Свободные блоки и неустойчивые обломки на откосе": CRITERION_LABELS["loose_blocks"],
                    "Фактический профиль откоса": CRITERION_LABELS["face_profile"],
                }
                for source in sorted(fields, key=len, reverse=True):
                    detail = detail.replace(source, tr(fields[source]))
            else:
                detail = domain_message(detail)
            return tr(translated) + detail
    if value.startswith("Dataset ") and value.endswith(" не найден"):
        return value[:-len(" не найден")] + tr(" was not found")
    if value.startswith("BlastEvent ") and value.endswith(" не найден"):
        return value[:-len(" не найден")] + tr(" was not found")
    if "; " in value:
        parts = [domain_message(part) for part in value.split("; ")]
        if all(not re.search(r"[А-Яа-яЁё]", part) for part in parts):
            return "; ".join(parts)
    if re.search(r"[А-Яа-яЁё]", value):
        return tr("Validation failed. Check the entered data.")
    return value


def import_summary_text(summary) -> str:
    """Render the active Datamine import summary without domain-localized text."""
    if getattr(summary, "format", None) == "DXF":
        return "\n".join((
            tr("File: %1").replace("%1", summary.file_name),
            tr("Format: DXF"),
            tr("Imported polylines: %1").replace("%1", str(summary.line_count)),
            tr("2D polylines: %1").replace("%1", str(summary.polyline_2d_count)),
            tr("3D polylines: %1").replace("%1", str(summary.polyline_3d_count)),
            tr("LWPOLYLINE entities: %1").replace("%1", str(summary.lwpolyline_count)),
            tr("Imported vertices: %1").replace("%1", str(summary.total_vertices)),
            tr("Skipped unsupported entities: %1").replace("%1", str(summary.skipped_unsupported_entity_count)),
            tr("Layers: %1").replace("%1", ", ".join(summary.layers) or "—"),
        ))
    delimiter = tr({",": "comma", ";": "semicolon", "\t": "tab"}.get(summary.delimiter, summary.delimiter))
    return "\n".join((
        tr("File: %1").replace("%1", summary.file_name),
        tr("Delimiter: %1").replace("%1", delimiter),
        tr("Encoding: %1").replace("%1", summary.encoding),
        tr("Rows: %1").replace("%1", str(summary.total_rows)),
        tr("Valid points: %1").replace("%1", str(summary.valid_points)),
        tr("Skipped rows: %1").replace("%1", str(summary.skipped_rows)),
        tr("Failed rows: %1").replace("%1", str(summary.failed_rows)),
        tr("Lines: %1").replace("%1", str(summary.line_count)),
    ))


def technical_text(value: str) -> str:
    return tr(TECHNICAL_TEXT_LABELS.get(value, value))
