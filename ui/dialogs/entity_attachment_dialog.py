"""Reusable photo/document manager for BlastEvents and evaluations."""
from __future__ import annotations

from app.localization import tr
from ui.presentation_labels import domain_message

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
        super().__init__(parent); self.setWindowTitle(tr("File details"))
        form = QFormLayout(self); self.title = QLineEdit(attachment.title if attachment else "")
        self.file_date = QDateEdit(); self.file_date.setCalendarPopup(True)
        value = attachment.file_date if attachment else date.today(); self.file_date.setDate(QDate(value.year, value.month, value.day))
        self.category = QComboBox()
        for code, label in ATTACHMENT_CATEGORIES[(owner_type, kind)]: self.category.addItem(label, code)
        if attachment: self.category.setCurrentIndex(max(0, self.category.findData(attachment.subtype)))
        self.custom = QLineEdit(attachment.custom_subtype if attachment else ""); self.custom.setPlaceholderText(tr("Custom category"))
        self.description = QTextEdit(attachment.description if attachment else ""); self.description.setMaximumHeight(100)
        self.category.currentIndexChanged.connect(lambda: self.custom.setVisible(self.category.currentData() == "other"))
        form.addRow("Title", self.title); form.addRow("Date", self.file_date); form.addRow("Category", self.category); form.addRow("Custom category", self.custom); form.addRow("Description", self.description)
        buttons = QHBoxLayout(); ok = QPushButton(tr("Save")); cancel = QPushButton(tr("Cancel")); ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject); buttons.addStretch(); buttons.addWidget(ok); buttons.addWidget(cancel); form.addRow(buttons)
        self.custom.setVisible(self.category.currentData() == "other")

    def values(self):
        qdate = self.file_date.date()
        return dict(title=self.title.text().strip(), file_date=date(qdate.year(), qdate.month(), qdate.day()), subtype=self.category.currentData(), custom_subtype=self.custom.text().strip(), description=self.description.toPlainText().strip())


class PhotoViewer(QDialog):
    def __init__(self, service, photos, current=0, parent=None):
        super().__init__(parent); self.service, self.photos, self.current, self.scale = service, photos, current, 1.0
        self.resize(900, 650); root = QVBoxLayout(self); actions = QHBoxLayout()
        for text, slot in (("Previous", self.previous), ("Next", self.next), ("Fit", self.fit), ("Zoom in", lambda: self.zoom(1.25)), ("Zoom out", lambda: self.zoom(.8))):
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
        self.setWindowTitle(tr("Photos and documents")); self.resize(1000, 600); root = QVBoxLayout(self)
        if owner_type == "assessment_evaluation":
            info = QLabel(tr("Files belong to the assessment and are shared by all revisions.")); info.setStyleSheet("background:#eef5ff;padding:8px"); root.addWidget(info)
        if unsaved:
            warning = QLabel(tr("Save an assessment draft before adding files.")); warning.setStyleSheet("color:#9b5c00"); root.addWidget(warning)
        sort = QHBoxLayout(); sort.addWidget(QLabel(tr("Sort by:"))); self.sort_combo = QComboBox(); self.sort_combo.addItems(["Date", "Title", "Category", "Size"]); self.sort_combo.currentIndexChanged.connect(self.refresh); sort.addWidget(self.sort_combo); sort.addStretch(); root.addLayout(sort)
        self.tabs = QTabWidget(); root.addWidget(self.tabs)
        self.tables = {}
        self.mutation_buttons = []
        for kind, caption in (("photo", "Photos"), ("document", "Documents")):
            page = QWidget(); layout = QVBoxLayout(page); table = QTableWidget(); table.setColumnCount(7); table.setHorizontalHeaderLabels(["Preview", "Title", "Date", "Category", "Original file", "Description", "Size"]); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.cellDoubleClicked.connect(lambda row, _col, k=kind: self.open_selected(k, row)); layout.addWidget(table)
            actions = QHBoxLayout()
            for text, handler in (("Add", lambda _=False, k=kind: self.add(k)), ("Open", lambda _=False, k=kind: self.open_selected(k)), ("Open folder", self.open_folder), ("Edit metadata", lambda _=False, k=kind: self.edit(k)), ("Delete", lambda _=False, k=kind: self.delete(k))):
                button = QPushButton(text); button.clicked.connect(handler); actions.addWidget(button)
                if text in {"Add", "Edit metadata", "Delete"}:
                    button.setEnabled(not read_only and not unsaved)
                    self.mutation_buttons.append(button)
            actions.addStretch(); layout.addLayout(actions); self.tables[kind] = table; self.tabs.addTab(page, caption)
        close = QPushButton(tr("Close")); close.clicked.connect(self.accept); root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight); self.refresh()

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
                missing = self.service.is_missing(item); preview = QLabel(tr("File is missing") if missing else "")
                if kind == "photo" and not missing:
                    pix = QPixmap(str(self.service.resolve_path(item))); preview.setPixmap(pix.scaled(80, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                table.setCellWidget(row, 0, preview)
                category = item.custom_subtype if item.subtype == "other" and item.custom_subtype else labels.get(item.subtype, item.subtype)
                for column, value in enumerate((item.title, item.file_date.isoformat(), category, item.original_filename, item.description, self._size(item.file_size_bytes)), 1):
                    cell = QTableWidgetItem(value); cell.setData(Qt.ItemDataRole.UserRole, item.id); table.setItem(row, column, cell)
            table.resizeColumnsToContents()

    @staticmethod
    def _size(value): return f"{value / 1024:.1f} KB" if value < 1024 ** 2 else f"{value / 1024 ** 2:.1f} MB"
    def _selected(self, kind, row=None):
        table = self.tables[kind]; row = table.currentRow() if row is None else row
        if row < 0 or not table.item(row, 1): return None
        ident = table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        return next((a for a in self._items(kind) if a.id == ident), None)
    def add(self, kind):
        filters = "Photos (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)" if kind == "photo" else "Documents (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip);;All files (*)"
        paths, selected_filter = QFileDialog.getOpenFileNames(self, "Add files", "", filters)
        if not paths: return
        if kind == "photo" and any(Path(p).suffix.lower() not in PHOTO_EXTENSIONS for p in paths): QMessageBox.warning(self, "Format", "The selected photo format is not supported."); return
        if kind == "document" and selected_filter == "All files (*)" and QMessageBox.question(self, "Other format", "SlopeForge may not be able to preview this file. Add it anyway?") != QMessageBox.StandardButton.Yes: return
        editor = AttachmentMetadataDialog(self.owner_type, kind, parent=self)
        if editor.exec() != QDialog.DialogCode.Accepted: return
        try: self.service.add_files(self.owner_type, self.owner_id, kind, paths, editor.values()); self.refresh()
        except Exception as exc: QMessageBox.critical(self, "Copy error", domain_message(str(exc)))
    def open_selected(self, kind, row=None):
        item = self._selected(kind, row)
        if not item: return
        if self.service.is_missing(item): QMessageBox.warning(self, "File is missing", "The file is missing from disk."); return
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
        box = QMessageBox(QMessageBox.Icon.Warning, "Delete", "The file will be removed from the database and disk.", parent=self); delete = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole); box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole); box.exec()
        if box.clickedButton() is delete:
            try: self.service.delete_attachment(item.id); self.refresh()
            except Exception as exc: QMessageBox.critical(self, "Delete error", domain_message(str(exc)))
