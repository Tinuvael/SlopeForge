"""Reusable photo/document manager for BlastEvents and evaluations."""
from __future__ import annotations

from app.localization import tr
from ui.presentation_labels import domain_message

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
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
        form.addRow(tr("Title"), self.title); form.addRow(tr("Date"), self.file_date); form.addRow(tr("Category"), self.category); form.addRow(tr("Custom category"), self.custom); form.addRow(tr("Description"), self.description)
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


class EntityAttachmentManagerWidget(QWidget):
    """Embeddable manager for exactly one attachment kind."""
    changed = Signal()
    def __init__(self, service, owner_type, owner_id, kind, parent=None, read_only=False, unsaved=False, ensure_owner=None):
        super().__init__(parent); self.service, self.owner_type, self.owner_id, self.kind = service, owner_type, owner_id, kind
        self.read_only, self.unsaved, self.ensure_owner = read_only, unsaved, ensure_owner
        root=QVBoxLayout(self)
        sort=QHBoxLayout(); sort.addWidget(QLabel(tr("Sort by:"))); self.sort_combo=QComboBox(); self.sort_combo.addItems([tr("Date"),tr("Title"),tr("Category"),tr("Size")]); self.sort_combo.currentIndexChanged.connect(self.refresh); sort.addWidget(self.sort_combo); sort.addStretch(); root.addLayout(sort)
        self.table=QTableWidget(); self.table.setColumnCount(7); self.table.setHorizontalHeaderLabels([tr("Preview"),tr("Title"),tr("Date"),tr("Category"),tr("Original file"),tr("Description"),tr("Size")]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.cellDoubleClicked.connect(lambda row,_col:self.open_selected(row)); root.addWidget(self.table)
        actions=QHBoxLayout(); self.mutation_buttons=[]
        for text_,handler,mutation in (("Add",self.add,True),("Open",self.open_selected,False),("Open folder",self.open_folder,False),("Edit metadata",self.edit,True),("Delete",self.delete,True)):
            button=QPushButton(tr(text_)); button.clicked.connect(handler); button.setEnabled(not mutation or (not read_only and not unsaved)); actions.addWidget(button)
            if mutation:self.mutation_buttons.append(button)
        actions.addStretch(); root.addLayout(actions); self.refresh()
    def _items(self):
        if not self.owner_id:return []
        values=self.service.list_for_owner(self.owner_type,self.owner_id,self.kind); key=self.sort_combo.currentIndex()
        if key==1:return sorted(values,key=lambda a:a.title.casefold())
        if key==2:return sorted(values,key=lambda a:(a.subtype,a.title.casefold()))
        if key==3:return sorted(values,key=lambda a:(-a.file_size_bytes,a.title.casefold()))
        return values
    def refresh(self):
        labels=dict(sum(ATTACHMENT_CATEGORIES.values(),[])); items=self._items(); self.table.setRowCount(len(items))
        for row,item in enumerate(items):
            missing=self.service.is_missing(item); preview=QLabel(tr("File is missing") if missing else "")
            if self.kind=="photo" and not missing:preview.setPixmap(QPixmap(str(self.service.resolve_path(item))).scaled(80,60,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            self.table.setCellWidget(row,0,preview); category=item.custom_subtype if item.subtype=="other" and item.custom_subtype else labels.get(item.subtype,item.subtype)
            for column,value in enumerate((item.title,item.file_date.isoformat(),category,item.original_filename,item.description,self._size(item.file_size_bytes)),1):
                cell=QTableWidgetItem(value); cell.setData(Qt.ItemDataRole.UserRole,item.id); self.table.setItem(row,column,cell)
        self.table.resizeColumnsToContents()
    @staticmethod
    def _size(value):return f"{value/1024:.1f} KB" if value<1024**2 else f"{value/1024**2:.1f} MB"
    def _selected(self,row=None):
        row=self.table.currentRow() if row is None or isinstance(row,bool) else row
        if row<0 or not self.table.item(row,1):return None
        ident=self.table.item(row,1).data(Qt.ItemDataRole.UserRole); return next((a for a in self._items() if a.id==ident),None)
    def _ensure_owner(self):
        if self.owner_id:return True,None
        if not self.ensure_owner:return False,None
        prepared=self.ensure_owner()
        owner,rollback=prepared if isinstance(prepared,tuple) else (prepared,None)
        self.owner_id=getattr(owner,"id",owner)
        return bool(self.owner_id),rollback
    def add(self,_checked=False):
        filters="Photos (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)" if self.kind=="photo" else "Documents (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip);;All files (*)"
        paths,selected_filter=QFileDialog.getOpenFileNames(self,tr("Add files"),"",filters)
        if not paths:return
        if self.kind=="photo" and any(Path(p).suffix.lower() not in PHOTO_EXTENSIONS for p in paths):QMessageBox.warning(self,tr("Format"),tr("The selected photo format is not supported.")); return
        if self.kind=="document" and selected_filter=="All files (*)" and QMessageBox.question(self,tr("Other format"),tr("SlopeForge may not be able to preview this file. Add it anyway?"))!=QMessageBox.StandardButton.Yes:return
        editor=AttachmentMetadataDialog(self.owner_type,self.kind,parent=self)
        if editor.exec()!=QDialog.DialogCode.Accepted:return
        try:ready,rollback_owner=self._ensure_owner()
        except Exception as exc:
            QMessageBox.critical(self,tr("Copy error"),domain_message(str(exc))); return
        if not ready:return
        try:self.service.add_files(self.owner_type,self.owner_id,self.kind,paths,editor.values())
        except Exception as exc:
            if rollback_owner:
                try:rollback_owner(); self.owner_id=None
                except Exception as rollback_exc:
                    QMessageBox.critical(self,tr("Copy error"),domain_message(f"{exc}; owner rollback failed: {rollback_exc}")); return
            QMessageBox.critical(self,tr("Copy error"),domain_message(str(exc)))
            return
        self.refresh(); self.changed.emit()
    def open_selected(self,row=None):
        item=self._selected(row)
        if not item:return
        if self.service.is_missing(item):QMessageBox.warning(self,tr("File is missing"),tr("The file is missing from disk.")); return
        if self.kind=="photo":
            photos=[a for a in self._items() if not self.service.is_missing(a)]; PhotoViewer(self.service,photos,[a.id for a in photos].index(item.id),self).exec()
        else:self.service.open_file(item)
    def open_folder(self,_checked=False):
        if self.owner_id:self.service.open_owner_folder(self.owner_type,self.owner_id)
    def edit(self,_checked=False):
        item=self._selected()
        if not item:return
        dialog=AttachmentMetadataDialog(self.owner_type,self.kind,item,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:self.service.update_metadata(item.id,**dialog.values())
        except Exception as exc:
            QMessageBox.critical(self,tr("Edit error"),domain_message(str(exc))); return
        self.refresh(); self.changed.emit()
    def delete(self,_checked=False):
        item=self._selected()
        if not item:return
        box=QMessageBox(QMessageBox.Icon.Warning,tr("Delete"),tr("The file will be removed from the database and disk."),parent=self); delete=box.addButton(tr("Delete"),QMessageBox.ButtonRole.DestructiveRole); box.addButton(tr("Cancel"),QMessageBox.ButtonRole.RejectRole); box.exec()
        if box.clickedButton() is not delete:return
        try:result=self.service.delete_attachment(item.id)
        except Exception as exc:
            QMessageBox.critical(self,tr("Delete error"),domain_message(str(exc))); return
        self.refresh(); self.changed.emit()
        cleanup_warning=getattr(result,"cleanup_warning",None)
        if cleanup_warning:
            QMessageBox.warning(self,tr("Cleanup warning"),
                f"{tr('The attachment was deleted, but a temporary file could not be removed.')}\n\n{cleanup_warning}")

class EntityAttachmentDialog(QDialog):
    """Compatibility wrapper retained for legacy callers."""
    def __init__(self,service,owner_type,owner_id,parent=None,read_only=False,unsaved=False):
        super().__init__(parent); self.setWindowTitle(tr("Photos and documents")); self.resize(1000,600); root=QVBoxLayout(self); self.tabs=QTabWidget(); self.tables={}; self.mutation_buttons=[]
        for kind,caption in (("photo",tr("Photos")),("document",tr("Documents"))):
            manager=EntityAttachmentManagerWidget(service,owner_type,owner_id,kind,self,read_only,unsaved); self.tabs.addTab(manager,caption); self.tables[kind]=manager.table; self.mutation_buttons.extend(manager.mutation_buttons)
        root.addWidget(self.tabs); close=QPushButton(tr("Close")); close.clicked.connect(self.accept); root.addWidget(close,alignment=Qt.AlignmentFlag.AlignRight)
    def refresh(self):
        for i in range(self.tabs.count()):self.tabs.widget(i).refresh()
