"""Reusable photo/document manager for BlastEvents and evaluations."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from prototype_2d.entity_attachments import ATTACHMENT_CATEGORIES, PHOTO_EXTENSIONS


class AttachmentMetadataDialog(QDialog):
    def __init__(self, owner_type, kind, attachment=None, parent=None):
        super().__init__(parent); self.setWindowTitle("Данные файла")
        form = QFormLayout(self); self.title = QLineEdit(attachment.title if attachment else "")
        self.file_date = QDateEdit(); self.file_date.setCalendarPopup(True)
        value = attachment.file_date if attachment else date.today(); self.file_date.setDate(QDate(value.year, value.month, value.day))
        self.category = QComboBox()
        for code, label in ATTACHMENT_CATEGORIES[(owner_type, kind)]: self.category.addItem(label, code)
        if attachment: self.category.setCurrentIndex(max(0, self.category.findData(attachment.subtype)))
        self.custom = QLineEdit(attachment.custom_subtype if attachment else ""); self.custom.setPlaceholderText("Своя категория")
        self.description = QTextEdit(attachment.description if attachment else ""); self.description.setMaximumHeight(100)
        self.category.currentIndexChanged.connect(lambda: self.custom.setVisible(self.category.currentData() == "other"))
        form.addRow("Название", self.title); form.addRow("Дата", self.file_date); form.addRow("Категория", self.category); form.addRow("Своя категория", self.custom); form.addRow("Описание", self.description)
        buttons = QHBoxLayout(); ok = QPushButton("Сохранить"); cancel = QPushButton("Отмена"); ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject); buttons.addStretch(); buttons.addWidget(ok); buttons.addWidget(cancel); form.addRow(buttons)
        self.custom.setVisible(self.category.currentData() == "other")

    def values(self):
        qdate = self.file_date.date()
        return dict(title=self.title.text().strip(), file_date=date(qdate.year(), qdate.month(), qdate.day()), subtype=self.category.currentData(), custom_subtype=self.custom.text().strip(), description=self.description.toPlainText().strip())


class PhotoViewer(QDialog):
    def __init__(self, service, photos, current=0, parent=None):
        super().__init__(parent); self.service, self.photos, self.current, self.scale = service, photos, current, 1.0
        self.resize(900, 650); root = QVBoxLayout(self); actions = QHBoxLayout()
        for text, slot in (("Предыдущее", self.previous), ("Следующее", self.next), ("Вписать", self.fit), ("Увеличить", lambda: self.zoom(1.25)), ("Уменьшить", lambda: self.zoom(.8))):
            button = QPushButton(text); button.clicked.connect(slot); actions.addWidget(button)
        root.addLayout(actions); self.scroll = QScrollArea(); self.label = QLabel(); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.scroll.setWidget(self.label); self.scroll.setWidgetResizable(True); root.addWidget(self.scroll); self.show_photo()

    def show_photo(self):
        if not self.photos: return
        attachment = self.photos[self.current]; pixmap = QPixmap(str(self.service.resolve_path(attachment)))
        self._original = pixmap; self.setWindowTitle(attachment.title); self.fit()
    def fit(self):
        if hasattr(self, "_original"): self.label.setPixmap(self._original.scaled(self.scroll.viewport().size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    def zoom(self, factor):
        if hasattr(self, "_original"): self.scale *= factor; self.label.setPixmap(self._original.scaled(self._original.size() * self.scale, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    def previous(self): self.current = (self.current - 1) % len(self.photos); self.show_photo()
    def next(self): self.current = (self.current + 1) % len(self.photos); self.show_photo()


class EntityAttachmentDialog(QDialog):
    def __init__(self, service, owner_type, owner_id, parent=None, read_only=False, unsaved=False):
        super().__init__(parent); self.service, self.owner_type, self.owner_id = service, owner_type, owner_id
        self.read_only, self.unsaved = read_only, unsaved
        self.setWindowTitle("Фото и документы"); self.resize(1000, 600); root = QVBoxLayout(self)
        if owner_type == "assessment_evaluation":
            info = QLabel("Файлы относятся ко всей оценке и общие для всех её ревизий."); info.setStyleSheet("background:#eef5ff;padding:8px"); root.addWidget(info)
        if unsaved:
            warning = QLabel("Сначала сохраните черновик оценки, затем добавьте файлы."); warning.setStyleSheet("color:#9b5c00"); root.addWidget(warning)
        sort = QHBoxLayout(); sort.addWidget(QLabel("Сортировка:")); self.sort_combo = QComboBox(); self.sort_combo.addItems(["Дата", "Название", "Категория", "Размер"]); self.sort_combo.currentIndexChanged.connect(self.refresh); sort.addWidget(self.sort_combo); sort.addStretch(); root.addLayout(sort)
        self.tabs = QTabWidget(); root.addWidget(self.tabs)
        self.tables = {}
        for kind, caption in (("photo", "Фото"), ("document", "Документы")):
            page = QWidget(); layout = QVBoxLayout(page); table = QTableWidget(); table.setColumnCount(7); table.setHorizontalHeaderLabels(["Превью", "Название", "Дата", "Категория", "Исходный файл", "Описание", "Размер"]); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.cellDoubleClicked.connect(lambda row, _col, k=kind: self.open_selected(k, row)); layout.addWidget(table)
            actions = QHBoxLayout()
            for text, handler in (("Добавить", lambda _=False, k=kind: self.add(k)), ("Открыть", lambda _=False, k=kind: self.open_selected(k)), ("Открыть папку", self.open_folder), ("Изменить данные", lambda _=False, k=kind: self.edit(k)), ("Удалить файл", lambda _=False, k=kind: self.delete(k))):
                button = QPushButton(text); button.clicked.connect(handler); actions.addWidget(button)
                if text in {"Добавить", "Изменить данные", "Удалить файл"}: button.setEnabled(not read_only and not unsaved)
            actions.addStretch(); layout.addLayout(actions); self.tables[kind] = table; self.tabs.addTab(page, caption)
        close = QPushButton("Закрыть"); close.clicked.connect(self.accept); root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight); self.refresh()

    def _items(self, kind):
        values = self.service.list_for_owner(self.owner_type, self.owner_id, kind)
        key = self.sort_combo.currentIndex()
        if key == 1: return sorted(values, key=lambda a: a.title.casefold())
        if key == 2: return sorted(values, key=lambda a: (a.subtype, a.title.casefold()))
        if key == 3: return sorted(values, key=lambda a: (-a.file_size_bytes, a.title.casefold()))
        return values

    def refresh(self):
        labels = dict(sum(ATTACHMENT_CATEGORIES.values(), []))
        for kind, table in self.tables.items():
            items = self._items(kind); table.setRowCount(len(items))
            for row, item in enumerate(items):
                missing = self.service.is_missing(item); preview = QLabel("Файл отсутствует" if missing else "")
                if kind == "photo" and not missing:
                    pix = QPixmap(str(self.service.resolve_path(item))); preview.setPixmap(pix.scaled(80, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                table.setCellWidget(row, 0, preview)
                category = item.custom_subtype if item.subtype == "other" and item.custom_subtype else labels.get(item.subtype, item.subtype)
                for column, value in enumerate((item.title, item.file_date.isoformat(), category, item.original_filename, item.description, self._size(item.file_size_bytes)), 1):
                    cell = QTableWidgetItem(value); cell.setData(Qt.ItemDataRole.UserRole, item.id); table.setItem(row, column, cell)
            table.resizeColumnsToContents()

    @staticmethod
    def _size(value): return f"{value / 1024:.1f} КБ" if value < 1024 ** 2 else f"{value / 1024 ** 2:.1f} МБ"
    def _selected(self, kind, row=None):
        table = self.tables[kind]; row = table.currentRow() if row is None else row
        if row < 0 or not table.item(row, 1): return None
        ident = table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        return next((a for a in self._items(kind) if a.id == ident), None)
    def add(self, kind):
        filters = "Фото (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)" if kind == "photo" else "Документы (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip);;Все файлы (*)"
        paths, selected_filter = QFileDialog.getOpenFileNames(self, "Добавить файлы", "", filters)
        if not paths: return
        if kind == "photo" and any(Path(p).suffix.lower() not in PHOTO_EXTENSIONS for p in paths): QMessageBox.warning(self, "Формат", "Выбран неподдерживаемый формат фото"); return
        if kind == "document" and selected_filter == "Все файлы (*)" and QMessageBox.question(self, "Другой формат", "Приложение не сможет показать этот файл. Всё равно добавить?") != QMessageBox.StandardButton.Yes: return
        editor = AttachmentMetadataDialog(self.owner_type, kind, parent=self)
        if editor.exec() != QDialog.DialogCode.Accepted: return
        try: self.service.add_files(self.owner_type, self.owner_id, kind, paths, editor.values()); self.refresh()
        except Exception as exc: QMessageBox.critical(self, "Ошибка копирования", str(exc))
    def open_selected(self, kind, row=None):
        item = self._selected(kind, row)
        if not item: return
        if self.service.is_missing(item): QMessageBox.warning(self, "Файл отсутствует", "Файл отсутствует на диске."); return
        if kind == "photo": PhotoViewer(self.service, [a for a in self._items(kind) if not self.service.is_missing(a)], [a.id for a in self._items(kind) if not self.service.is_missing(a)].index(item.id), self).exec()
        else: self.service.open_file(item)
    def open_folder(self): self.service.open_owner_folder(self.owner_type, self.owner_id)
    def edit(self, kind):
        item = self._selected(kind)
        if not item: return
        dialog = AttachmentMetadataDialog(self.owner_type, kind, item, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.service.update_metadata(item.id, **dialog.values()); self.refresh()
    def delete(self, kind):
        item = self._selected(kind)
        if not item: return
        box = QMessageBox(QMessageBox.Icon.Warning, "Удалить файл", "Файл будет удалён из базы и физически удалён с диска.", parent=self); delete = box.addButton("Удалить", QMessageBox.ButtonRole.DestructiveRole); box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole); box.exec()
        if box.clickedButton() is delete:
            try: self.service.delete_attachment(item.id); self.refresh()
            except Exception as exc: QMessageBox.critical(self, "Ошибка удаления", str(exc))
