"""English presentation labels for stable domain IDs and legacy snapshots.

The keys stored in the database/domain snapshots are deliberately not changed.
"""

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
    return TECHNICAL_GROUP_LABELS.get(key, fallback or key)


def matrix_label(matrix_id: str, fallback: str = "") -> str:
    return MATRIX_LABELS.get(matrix_id, fallback or matrix_id)


def criterion_label(criterion_id: str, fallback: str = "") -> str:
    return CRITERION_LABELS.get(criterion_id, fallback or criterion_id)


def option_label(option_id: str, fallback: str = "") -> str:
    return OPTION_LABELS.get(option_id, fallback or option_id)


def result_label(value: str | None) -> str:
    return RESULT_LABELS.get(value or "", value or "")


def domain_message(value: str) -> str:
    return DOMAIN_MESSAGES.get(value, value)


def technical_text(value: str) -> str:
    return TECHNICAL_TEXT_LABELS.get(value, value)
