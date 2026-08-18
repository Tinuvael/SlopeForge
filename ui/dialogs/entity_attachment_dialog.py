"""Reusable photo/document manager for BlastEvents and evaluations."""
from __future__ import annotations

from app.localization import tr
from ui.presentation_labels import domain_message

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QFileInfo, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImageReader, QKeySequence, QPainter, QPainterPath, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFileIconProvider,
    QFormLayout,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from application.services.attachments import ATTACHMENT_CATEGORIES, PHOTO_EXTENSIONS


ATTACHMENT_WORKSPACE_COLOR = QColor("#f3f4f6")


def _load_photo_pixmap(path: str | Path) -> QPixmap:
    """Load a photo with EXIF orientation applied, matching normal Windows viewers."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


def _apply_workspace_palette(widget: QWidget) -> None:
    """Give attachment workspaces one neutral background without styling native controls."""
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, ATTACHMENT_WORKSPACE_COLOR)
    palette.setColor(QPalette.ColorRole.Base, ATTACHMENT_WORKSPACE_COLOR)
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)


class AttachmentMetadataDialog(QDialog):
    def __init__(self, owner_type, kind, attachment=None, parent=None, *, source_path=None,
                 batch_index: int | None = None, batch_count: int | None = None):
        super().__init__(parent)
        title = tr("Photo details") if kind == "photo" and source_path else tr("File details")
        if batch_index is not None and batch_count and batch_count > 1:
            title = f"{title} — {batch_index}/{batch_count}"
        self.setWindowTitle(title)
        self.setMinimumWidth(520 if kind == "photo" and source_path else 420)
        root = QVBoxLayout(self)

        if kind == "photo" and source_path:
            preview = QLabel()
            preview.setObjectName("PhotoImportPreview")
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setMinimumHeight(260)
            preview.setStyleSheet("background:#f3f4f6;border:1px solid #dfe3ea;border-radius:6px;")
            pixmap = _load_photo_pixmap(source_path)
            if not pixmap.isNull():
                preview.setPixmap(pixmap.scaled(480, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))
            else:
                preview.setText(tr("Preview is not available"))
            root.addWidget(preview)

        form = QFormLayout()
        automatic_title = Path(source_path).stem if source_path else ""
        self.title = QLineEdit(attachment.title if attachment else automatic_title)
        if source_path:
            self.title.setToolTip(tr("Filled automatically from the file name."))
        self.file_date = QDateEdit(); self.file_date.setCalendarPopup(True)
        value = attachment.file_date if attachment else date.today()
        self.file_date.setDate(QDate(value.year, value.month, value.day))
        self.category = QComboBox()
        for code, label in ATTACHMENT_CATEGORIES[(owner_type, kind)]:
            self.category.addItem(label, code)
        if attachment:
            self.category.setCurrentIndex(max(0, self.category.findData(attachment.subtype)))
        self.custom = QLineEdit(attachment.custom_subtype if attachment else "")
        self.custom.setPlaceholderText(tr("Custom category"))
        self.description = QTextEdit(attachment.description if attachment else "")
        self.description.setMaximumHeight(90)
        self.category.currentIndexChanged.connect(
            lambda: self.custom.setVisible(self.category.currentData() == "other")
        )
        form.addRow(tr("Title"), self.title)
        form.addRow(tr("Date"), self.file_date)
        form.addRow(tr("Category"), self.category)
        form.addRow(tr("Custom category"), self.custom)
        form.addRow(tr("Description"), self.description)
        root.addLayout(form)

        buttons = QHBoxLayout()
        ok = QPushButton(tr("Save")); cancel = QPushButton(tr("Cancel"))
        ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        buttons.addStretch(); buttons.addWidget(ok); buttons.addWidget(cancel)
        root.addLayout(buttons)
        self.custom.setVisible(self.category.currentData() == "other")

    def values(self):
        qdate = self.file_date.date()
        return dict(
            title=self.title.text().strip(),
            file_date=date(qdate.year(), qdate.month(), qdate.day()),
            subtype=self.category.currentData(),
            custom_subtype=self.custom.text().strip(),
            description=self.description.toPlainText().strip(),
        )


class DocumentBatchDialog(QDialog):
    """Review one or many documents without forcing one modal per file."""
    def __init__(self, owner_type: str, source_paths, parent=None):
        super().__init__(parent)
        self.owner_type = owner_type
        self.source_paths = [Path(path) for path in source_paths]
        self.row_editors = []
        self.setWindowTitle(tr("Add documents"))
        self.resize(960, min(700, 250 + 52 * max(1, len(self.source_paths))))
        root = QVBoxLayout(self)

        count = len(self.source_paths)
        heading = QLabel(f"{count} {tr('document') if count == 1 else tr('documents')} {tr('selected')}")
        heading.setStyleSheet("font-size:16px;font-weight:600;color:#111827;")
        helper = QLabel(tr("Titles are filled automatically from file names. Review categories and dates before importing."))
        helper.setWordWrap(True); helper.setStyleSheet("color:#6b7280;")
        root.addWidget(heading); root.addWidget(helper)

        bulk = QFrame(); bulk.setObjectName("DocumentBatchBulk")
        bulk.setStyleSheet("QFrame#DocumentBatchBulk{background:#f8fafc;border:1px solid #dfe3ea;border-radius:8px;}")
        bulk_layout = QHBoxLayout(bulk); bulk_layout.setContentsMargins(10, 8, 10, 8)
        bulk_layout.addWidget(QLabel(tr("Apply to all:")))
        self.bulk_category = self._category_combo()
        apply_category = QPushButton(tr("Apply category")); apply_category.clicked.connect(self._apply_category)
        self.bulk_date = QDateEdit(); self.bulk_date.setCalendarPopup(True); self.bulk_date.setDisplayFormat("dd.MM.yyyy"); self.bulk_date.setDate(QDate.currentDate())
        apply_date = QPushButton(tr("Apply date")); apply_date.clicked.connect(self._apply_date)
        bulk_layout.addWidget(self.bulk_category); bulk_layout.addWidget(apply_category)
        bulk_layout.addSpacing(12); bulk_layout.addWidget(self.bulk_date); bulk_layout.addWidget(apply_date); bulk_layout.addStretch()
        root.addWidget(bulk)

        self.table = QTableWidget(len(self.source_paths), 4)
        self.table.setHorizontalHeaderLabels([tr("File"), tr("Title"), tr("Category"), tr("Date")])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet("QTableWidget{background:white;border:1px solid #dfe3ea;border-radius:7px;} QHeaderView::section{background:#f8fafc;border:0;border-bottom:1px solid #dfe3ea;padding:7px;font-weight:600;} QTableWidget::item{border-bottom:1px solid #edf0f4;}")

        for row, path in enumerate(self.source_paths):
            self.table.setRowHeight(row, 46)
            file_label = QLabel(path.name); file_label.setToolTip(str(path)); file_label.setStyleSheet("padding-left:6px;color:#374151;")
            title = QLineEdit(path.stem)
            category = self._category_combo()
            file_date = QDateEdit(); file_date.setCalendarPopup(True); file_date.setDisplayFormat("dd.MM.yyyy")
            try:
                value = date.fromtimestamp(path.stat().st_mtime)
            except OSError:
                value = date.today()
            file_date.setDate(QDate(value.year, value.month, value.day))
            self.table.setCellWidget(row, 0, file_label)
            self.table.setCellWidget(row, 1, title)
            self.table.setCellWidget(row, 2, category)
            self.table.setCellWidget(row, 3, file_date)
            self.row_editors.append((path, title, category, file_date))
        root.addWidget(self.table, 1)

        buttons = QHBoxLayout(); cancel = QPushButton(tr("Cancel")); add = QPushButton(tr("Add documents"))
        cancel.clicked.connect(self.reject); add.clicked.connect(self.accept)
        buttons.addStretch(); buttons.addWidget(cancel); buttons.addWidget(add); root.addLayout(buttons)

    def _category_combo(self):
        combo = QComboBox()
        for code, label in ATTACHMENT_CATEGORIES[(self.owner_type, "document")]:
            combo.addItem(label, code)
        return combo

    def _apply_category(self):
        code = self.bulk_category.currentData()
        for _path, _title, category, _file_date in self.row_editors:
            index = category.findData(code)
            if index >= 0:
                category.setCurrentIndex(index)

    def _apply_date(self):
        qdate = self.bulk_date.date()
        for _path, _title, _category, file_date in self.row_editors:
            file_date.setDate(qdate)

    def entries(self):
        result = []
        for path, title, category, file_date in self.row_editors:
            qdate = file_date.date()
            result.append((path, dict(
                title=title.text().strip() or path.stem,
                file_date=date(qdate.year(), qdate.month(), qdate.day()),
                subtype=category.currentData(),
                custom_subtype="",
                description="",
            )))
        return result


class PhotoGraphicsView(QGraphicsView):
    """Contained photo viewer with mouse-wheel zoom and drag panning."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self._has_photo = False
        self._fit_mode = True
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(Qt.GlobalColor.black)
        self.setMinimumSize(480, 360)

    def set_photo(self, pixmap: QPixmap):
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(self._item.boundingRect())
        self._has_photo = not pixmap.isNull()
        self.fit_photo()

    def fit_photo(self):
        if not self._has_photo:
            return
        self.resetTransform()
        self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
        self._fit_mode = True

    def wheelEvent(self, event):
        if not self._has_photo:
            return super().wheelEvent(event)
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        current = self.transform().m11()
        target = current * factor
        if 0.05 <= target <= 20:
            self.scale(factor, factor)
            self._fit_mode = False
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit_photo()


class PhotoViewer(QDialog):
    """Legacy compatibility viewer retained for callers outside entity pages."""
    def __init__(self, service, photos, current=0, parent=None):
        super().__init__(parent)
        self.service, self.photos, self.current = service, photos, current
        self.resize(900, 650)
        root = QVBoxLayout(self)
        actions = QHBoxLayout()
        for text, slot in (("Previous", self.previous), ("Next", self.next), ("Fit", self.fit)):
            button = QPushButton(tr(text)); button.clicked.connect(slot); actions.addWidget(button)
        actions.addStretch(); root.addLayout(actions)
        self.view = PhotoGraphicsView(); root.addWidget(self.view)
        self.show_photo()

    def show_photo(self):
        if not self.photos:
            return
        attachment = self.photos[self.current]
        self.setWindowTitle(attachment.title)
        self.view.set_photo(_load_photo_pixmap(self.service.resolve_path(attachment)))

    def fit(self): self.view.fit_photo()
    def previous(self): self.current = (self.current - 1) % len(self.photos); self.show_photo()
    def next(self): self.current = (self.current + 1) % len(self.photos); self.show_photo()


class EntityAttachmentManagerWidget(QWidget):
    """Embeddable manager for exactly one attachment kind."""
    changed = Signal()

    def __init__(self, service, owner_type, owner_id, kind, parent=None, read_only=False,
                 unsaved=False, ensure_owner=None):
        super().__init__(parent)
        self.service, self.owner_type, self.owner_id, self.kind = service, owner_type, owner_id, kind
        self.read_only, self.unsaved, self.ensure_owner = read_only, unsaved, ensure_owner
        self.current_attachment_id = None
        self._gallery_layout_signature = None
        self._gallery_reflow_pending = False
        self._file_icon_provider = QFileIconProvider() if kind == "document" else None
        _apply_workspace_palette(self)
        # Normal entity pages embed the manager in a plain tab-page QWidget with
        # the default QVBoxLayout margins. Those margins are outside this widget,
        # so they must use the same workspace palette too; otherwise Contour and
        # Assessment expose a white frame while Block happens to blend with its
        # styled QTabWidget pane. Keep compatibility dialogs untouched.
        if isinstance(parent, QWidget) and not isinstance(parent, QDialog):
            _apply_workspace_palette(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        sort = QHBoxLayout(); sort.addWidget(QLabel(tr("Sort by:")))
        self.sort_combo = QComboBox(); self.sort_combo.addItems([tr("Date"), tr("Title"), tr("Category"), tr("Size")])
        self.sort_combo.currentIndexChanged.connect(self.refresh); sort.addWidget(self.sort_combo); sort.addStretch()
        root.addLayout(sort)

        self.table = None
        self.stack = None
        self.mutation_buttons = []
        self._build_attachment_actions(root)
        if self.kind == "photo":
            self._build_photo_pages(root)
        else:
            self._build_document_table(root)
        self.refresh()

    def _build_attachment_actions(self, root):
        """Keep Photos and Documents controls in the same place and order."""
        actions = QHBoxLayout()
        for text_, handler, mutation in (
            ("Add", self.add, True),
            ("Open", self.open_selected, False),
            ("Open folder", self.open_folder, False),
            ("Edit metadata", self.edit, True),
            ("Delete", self.delete, True),
        ):
            button = QPushButton(tr(text_)); button.clicked.connect(handler)
            button.setEnabled(not mutation or (not self.read_only and not self.unsaved))
            if text_ == "Edit metadata":
                actions.addStretch()
            actions.addWidget(button)
            if mutation:
                self.mutation_buttons.append(button)
        root.addLayout(actions)

    def _build_document_table(self, root):
        self.table = QTableWidget(); self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([tr("Document"), tr("Category"), tr("Date"), tr("Size")])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda row, _col: self.open_selected(row))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet("QTableWidget{background:white;border:1px solid #dfe3ea;border-radius:7px;outline:0;} QHeaderView::section{background:#f8fafc;border:0;border-bottom:1px solid #dfe3ea;padding:8px;font-weight:600;color:#374151;} QTableWidget::item{border-bottom:1px solid #edf0f4;padding:8px;} QTableWidget::item:selected{background:#eef4fb;color:#111827;}")
        root.addWidget(self.table, 1)

    def _build_photo_pages(self, root):
        self.stack = QStackedWidget()
        _apply_workspace_palette(self.stack)
        self.gallery_page = QWidget(); _apply_workspace_palette(self.gallery_page); gallery_root = QVBoxLayout(self.gallery_page)
        gallery_root.setContentsMargins(0, 0, 0, 0)
        self.gallery_scroll = QScrollArea(); self.gallery_scroll.setWidgetResizable(True); self.gallery_scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Do not set a palette or stylesheet on QScrollArea itself. On Windows
        # that can alter how its native scrollbars are drawn. Only the viewport
        # and content need the neutral workspace background.
        _apply_workspace_palette(self.gallery_scroll.viewport())
        self.gallery_content = QWidget(); _apply_workspace_palette(self.gallery_content); self.gallery_grid = QGridLayout(self.gallery_content)
        self.gallery_grid.setContentsMargins(4, 6, 4, 6)
        self.gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.gallery_grid.setHorizontalSpacing(16); self.gallery_grid.setVerticalSpacing(16)
        self.gallery_scroll.setWidget(self.gallery_content)
        self.gallery_scroll.viewport().installEventFilter(self)
        gallery_root.addWidget(self.gallery_scroll)
        self.stack.addWidget(self.gallery_page)

        self.viewer_page = QWidget(); _apply_workspace_palette(self.viewer_page); viewer_root = QVBoxLayout(self.viewer_page); viewer_root.setContentsMargins(0, 0, 0, 0)
        viewer_header = QHBoxLayout()
        self.back_button = QPushButton(tr("Back")); self.back_button.clicked.connect(self._show_gallery)
        self.viewer_title = QLabel(); self.viewer_title.setObjectName("PhotoViewerTitle")
        self.viewer_title.setStyleSheet("font-size:16px;font-weight:600;color:#111827;")
        fit_button = QPushButton(tr("Fit")); fit_button.clicked.connect(lambda: self.photo_view.fit_photo())
        viewer_header.addWidget(self.back_button); viewer_header.addWidget(self.viewer_title); viewer_header.addStretch(); viewer_header.addWidget(fit_button)
        viewer_root.addLayout(viewer_header)

        viewer_body = QHBoxLayout(); viewer_body.setSpacing(14)
        self.photo_view = PhotoGraphicsView(); viewer_body.addWidget(self.photo_view, 1)
        side = QWidget(); _apply_workspace_palette(side); side.setFixedWidth(235); side_layout = QVBoxLayout(side); side_layout.setContentsMargins(0, 0, 0, 0); side_layout.setSpacing(10)
        self.viewer_metadata = QFrame(); self.viewer_metadata.setObjectName("PhotoMetadataCard")
        self.viewer_metadata.setStyleSheet("QFrame#PhotoMetadataCard{background:#f8fafc;border:1px solid #dfe3ea;border-radius:8px;} QLabel#PhotoMetadataLabel{color:#6b7280;font-size:11px;} QLabel#PhotoMetadataValue{color:#111827;font-weight:500;}")
        metadata = QGridLayout(self.viewer_metadata); metadata.setContentsMargins(10, 9, 10, 9); metadata.setHorizontalSpacing(8); metadata.setVerticalSpacing(5); metadata.setColumnStretch(1,1)
        self.viewer_category = QLabel(); self.viewer_category.setWordWrap(True)
        self.viewer_date = QLabel(); self.viewer_file = QLabel(); self.viewer_file.setWordWrap(True)
        for row, (caption, value) in enumerate((("Category", self.viewer_category), ("Date", self.viewer_date), ("File", self.viewer_file))):
            label = QLabel(tr(caption)); label.setObjectName("PhotoMetadataLabel"); value.setObjectName("PhotoMetadataValue")
            metadata.addWidget(label, row, 0, Qt.AlignmentFlag.AlignTop); metadata.addWidget(value, row, 1)
        side_layout.addWidget(self.viewer_metadata)
        self.thumb_scroll = QScrollArea(); self.thumb_scroll.setWidgetResizable(True); self.thumb_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.thumb_content = QWidget(); self.thumb_layout = QVBoxLayout(self.thumb_content); self.thumb_layout.setContentsMargins(0, 0, 0, 0); self.thumb_layout.setSpacing(8); self.thumb_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.thumb_scroll.setWidget(self.thumb_content); side_layout.addWidget(self.thumb_scroll, 1)
        viewer_body.addWidget(side)
        viewer_root.addLayout(viewer_body, 1)
        self.stack.addWidget(self.viewer_page)
        root.addWidget(self.stack, 1)
        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.escape_shortcut.activated.connect(self._show_gallery)

    def eventFilter(self, watched, event):
        if (self.kind == "photo" and hasattr(self, "gallery_scroll")
                and watched is self.gallery_scroll.viewport()
                and event.type() == QEvent.Type.Resize):
            self._schedule_gallery_reflow()
        return super().eventFilter(watched, event)

    def _schedule_gallery_reflow(self):
        if self._gallery_reflow_pending:
            return
        self._gallery_reflow_pending = True
        QTimer.singleShot(0, self._reflow_photo_gallery)

    def _reflow_photo_gallery(self):
        self._gallery_reflow_pending = False
        if self.kind != "photo" or not self.stack or self.stack.currentWidget() is not self.gallery_page:
            return
        signature = self._gallery_metrics()
        if signature != self._gallery_layout_signature:
            self._refresh_photo_gallery()

    def _gallery_metrics(self):
        margins = self.gallery_grid.contentsMargins()
        spacing = max(0, self.gallery_grid.horizontalSpacing())
        available = max(1, self.gallery_scroll.viewport().width() - margins.left() - margins.right())
        minimum = 185
        columns = max(1, int((available + spacing) // (minimum + spacing)))
        tile_width = max(150, int((available - spacing * (columns - 1)) / columns))
        image_height = max(96, int(tile_width * 0.63))
        wrapper_height = image_height + 30
        return columns, tile_width, image_height, wrapper_height

    def _items(self):
        if not self.owner_id:
            return []
        values = self.service.list_for_owner(self.owner_type, self.owner_id, self.kind)
        key = self.sort_combo.currentIndex()
        if key == 1: return sorted(values, key=lambda a: a.title.casefold())
        if key == 2: return sorted(values, key=lambda a: (a.subtype, a.title.casefold()))
        if key == 3: return sorted(values, key=lambda a: (-a.file_size_bytes, a.title.casefold()))
        return values

    def refresh(self):
        if self.kind == "photo":
            self._refresh_photo_gallery()
        else:
            self._refresh_document_table()

    def _document_name_widget(self, item):
        wrapper = QWidget(); wrapper.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(wrapper); layout.setContentsMargins(7, 4, 7, 4); layout.setSpacing(10)
        icon_label = QLabel(); icon_label.setFixedSize(38, 38); icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = self.service.resolve_path(item)
        icon = self._file_icon_provider.icon(QFileInfo(str(path if path.exists() else item.original_filename)))
        icon_label.setPixmap(icon.pixmap(32, 32))
        text = QVBoxLayout(); text.setContentsMargins(0, 0, 0, 0); text.setSpacing(1)
        title = QLabel(item.title or Path(item.original_filename).stem); title.setStyleSheet("font-weight:600;color:#111827;")
        filename = QLabel(item.original_filename); filename.setStyleSheet("color:#6b7280;font-size:11px;")
        text.addWidget(title); text.addWidget(filename); layout.addWidget(icon_label); layout.addLayout(text, 1)
        if item.description:
            wrapper.setToolTip(item.description)
        return wrapper

    def _refresh_document_table(self):
        items = self._items(); self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setRowHeight(row, 58)
            id_cell = QTableWidgetItem(); id_cell.setData(Qt.ItemDataRole.UserRole, item.id)
            self.table.setItem(row, 0, id_cell); self.table.setCellWidget(row, 0, self._document_name_widget(item))
            category = self._category_label(item)
            for column, value in ((1, category), (2, item.file_date.strftime("%d.%m.%Y")), (3, self._size(item.file_size_bytes))):
                cell = QTableWidgetItem(value); cell.setData(Qt.ItemDataRole.UserRole, item.id)
                if column in (2, 3): cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, cell)
        if items and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    @staticmethod
    def _rounded_cover(pixmap: QPixmap, size: QSize, radius: float = 10.0) -> QPixmap:
        if pixmap.isNull():
            return QPixmap()
        scaled = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - size.width()) // 2)
        y = max(0, (scaled.height() - size.height()) // 2)
        cropped = scaled.copy(x, y, size.width(), size.height())
        output = QPixmap(size); output.fill(Qt.GlobalColor.transparent)
        painter = QPainter(output); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), radius, radius)
        painter.setClipPath(path); painter.drawPixmap(0, 0, cropped); painter.end()
        return output

    def _thumbnail(self, item, size: QSize, *, cover=False) -> QIcon:
        if self.service.is_missing(item):
            return QIcon()
        pixmap = _load_photo_pixmap(self.service.resolve_path(item))
        if pixmap.isNull():
            return QIcon()
        if cover:
            return QIcon(self._rounded_cover(pixmap, size))
        return QIcon(pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation))

    def _photo_tile(self, item, tile_width, image_height, wrapper_height):
        wrapper = QWidget(); wrapper.setFixedSize(tile_width, wrapper_height)
        layout = QVBoxLayout(wrapper); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6)
        title = QLabel(item.title or Path(item.original_filename).stem)
        title.setObjectName("PhotoTileTitle"); title.setToolTip(item.original_filename)
        title.setStyleSheet("color:#374151;font-weight:500;")
        layout.addWidget(title)
        tile = QToolButton(); tile.setObjectName("PhotoTile"); tile.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tile.setFixedSize(tile_width, image_height)
        icon_size = QSize(max(1, tile_width - 4), max(1, image_height - 4))
        tile.setIconSize(icon_size); tile.setIcon(self._thumbnail(item, icon_size, cover=True))
        tile.setStyleSheet("QToolButton#PhotoTile{background:transparent;border:0;padding:0;margin:0;} QToolButton#PhotoTile:hover{background:#eef4fb;border:2px solid #9bc2ea;border-radius:11px;}")
        tile.setToolTip(item.original_filename)
        tile.clicked.connect(lambda _checked=False, ident=item.id: self._open_photo_id(ident))
        layout.addWidget(tile)
        return wrapper

    def _refresh_photo_gallery(self):
        items = self._items(); self._clear_layout(self.gallery_grid)
        columns, tile_width, image_height, wrapper_height = self._gallery_metrics()
        self._gallery_layout_signature = (columns, tile_width, image_height, wrapper_height)
        if not items:
            empty = QLabel(tr("No photos yet")); empty.setObjectName("MutedText")
            self.gallery_grid.addWidget(empty, 0, 0)
            self.current_attachment_id = None
            self._show_gallery()
            return
        ids = {item.id for item in items}
        if self.current_attachment_id not in ids:
            self.current_attachment_id = items[0].id
        for index, item in enumerate(items):
            self.gallery_grid.addWidget(
                self._photo_tile(item, tile_width, image_height, wrapper_height),
                index // columns, index % columns,
            )
        if self.stack.currentWidget() is self.viewer_page:
            self._show_photo(self.current_attachment_id)

    @staticmethod
    def _size(value):
        return f"{value/1024:.1f} KB" if value < 1024**2 else f"{value/1024**2:.1f} MB"

    def _selected(self, row=None):
        if self.kind == "photo":
            return next((a for a in self._items() if a.id == self.current_attachment_id), None)
        row = self.table.currentRow() if row is None or isinstance(row, bool) else row
        if row < 0 or not self.table.item(row, 0):
            return None
        ident = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next((a for a in self._items() if a.id == ident), None)

    def _ensure_owner(self):
        if self.owner_id:
            return True, None
        if not self.ensure_owner:
            return False, None
        prepared = self.ensure_owner()
        owner, rollback = prepared if isinstance(prepared, tuple) else (prepared, None)
        self.owner_id = getattr(owner, "id", owner)
        return bool(self.owner_id), rollback

    def add(self, _checked=False):
        filters = ("Photos (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)" if self.kind == "photo"
                   else "Documents (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip);;All files (*)")
        paths, selected_filter = QFileDialog.getOpenFileNames(self, tr("Add files"), "", filters)
        if not paths:
            return
        if self.kind == "photo" and any(Path(p).suffix.lower() not in PHOTO_EXTENSIONS for p in paths):
            QMessageBox.warning(self, tr("Format"), tr("The selected photo format is not supported.")); return
        if self.kind == "document" and selected_filter == "All files (*)" and QMessageBox.question(
                self, tr("Other format"), tr("SlopeForge may not be able to preview this file. Add it anyway?")) != QMessageBox.StandardButton.Yes:
            return

        if self.kind == "photo":
            reviewed = []
            for index, path in enumerate(paths, 1):
                editor = AttachmentMetadataDialog(
                    self.owner_type, self.kind, parent=self, source_path=path,
                    batch_index=index, batch_count=len(paths),
                )
                if editor.exec() != QDialog.DialogCode.Accepted:
                    return
                values = editor.values(); values["title"] = values["title"] or Path(path).stem
                reviewed.append((path, values))
        else:
            editor = DocumentBatchDialog(self.owner_type, paths, self)
            if editor.exec() != QDialog.DialogCode.Accepted:
                return
            reviewed = editor.entries()

        try:
            ready, rollback_owner = self._ensure_owner()
        except Exception as exc:
            QMessageBox.critical(self, tr("Copy error"), domain_message(str(exc))); return
        if not ready:
            return
        try:
            add_per_file = getattr(self.service, "add_files_with_metadata", None)
            if add_per_file:
                added = add_per_file(self.owner_type, self.owner_id, self.kind, reviewed)
            else:
                if len(reviewed) > 1:
                    raise RuntimeError("Attachment service does not support reviewed batches")
                added = self.service.add_files(
                    self.owner_type, self.owner_id, self.kind,
                    [path for path, _metadata in reviewed], reviewed[0][1],
                )
        except Exception as exc:
            if rollback_owner:
                try:
                    rollback_owner(); self.owner_id = None
                except Exception as rollback_exc:
                    QMessageBox.critical(self, tr("Copy error"), domain_message(
                        f"{exc}; owner rollback failed: {rollback_exc}")); return
            QMessageBox.critical(self, tr("Copy error"), domain_message(str(exc))); return
        if self.kind == "photo" and added:
            self.current_attachment_id = added[-1].id
        self.refresh(); self.changed.emit()

    def _show_gallery(self):
        if self.kind == "photo" and self.stack:
            self.stack.setCurrentWidget(self.gallery_page)
            self._schedule_gallery_reflow()

    def _open_photo_id(self, attachment_id):
        self.current_attachment_id = attachment_id
        self._show_photo(attachment_id)
        self.stack.setCurrentWidget(self.viewer_page)

    def _category_label(self, item):
        labels = dict(ATTACHMENT_CATEGORIES.get((self.owner_type, self.kind), []))
        if item.subtype == "other" and item.custom_subtype:
            return item.custom_subtype
        return labels.get(item.subtype, item.subtype or "—")

    def _show_photo(self, attachment_id):
        items = [a for a in self._items() if not self.service.is_missing(a)]
        item = next((a for a in items if a.id == attachment_id), None)
        if item is None:
            self._show_gallery(); return
        self.current_attachment_id = item.id
        self.viewer_title.setText(item.title or Path(item.original_filename).stem)
        self.viewer_category.setText(self._category_label(item))
        self.viewer_date.setText(item.file_date.strftime("%d.%m.%Y"))
        self.viewer_file.setText(item.original_filename)
        self.photo_view.set_photo(_load_photo_pixmap(self.service.resolve_path(item)))
        self._clear_layout(self.thumb_layout)
        for photo in items:
            thumb = QToolButton(); thumb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            thumb.setIcon(self._thumbnail(photo, QSize(198, 118), cover=True)); thumb.setIconSize(QSize(198, 118)); thumb.setFixedSize(204, 124)
            thumb.setToolTip(photo.title or photo.original_filename)
            border = "2px solid #0b63ce" if photo.id == item.id else "1px solid transparent"
            thumb.setStyleSheet(f"border:{border};border-radius:10px;padding:2px;background:transparent;")
            thumb.clicked.connect(lambda _checked=False, ident=photo.id: self._show_photo(ident))
            self.thumb_layout.addWidget(thumb)

    def open_selected(self, row=None):
        item = self._selected(row)
        if not item:
            return
        if self.service.is_missing(item):
            QMessageBox.warning(self, tr("File is missing"), tr("The file is missing from disk.")); return
        if self.kind == "photo":
            self._open_photo_id(item.id)
        else:
            self.service.open_file(item)

    def open_folder(self, _checked=False):
        if not self.owner_id:
            return
        opener = getattr(self.service, "open_attachment_folder", None)
        if opener is not None:
            opener(self.owner_type, self.owner_id, self.kind)
        else:
            self.service.open_owner_folder(self.owner_type, self.owner_id)

    def edit(self, _checked=False):
        item = self._selected()
        if not item:
            return
        dialog = AttachmentMetadataDialog(self.owner_type, self.kind, item, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.service.update_metadata(item.id, **dialog.values())
        except Exception as exc:
            QMessageBox.critical(self, tr("Edit error"), domain_message(str(exc))); return
        self.refresh(); self.changed.emit()

    def delete(self, _checked=False):
        item = self._selected()
        if not item:
            return
        box = QMessageBox(QMessageBox.Icon.Warning, tr("Delete"),
                          tr("The file will be removed from the database and disk."), parent=self)
        delete = box.addButton(tr("Delete"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole); box.exec()
        if box.clickedButton() is not delete:
            return
        try:
            result = self.service.delete_attachment(item.id)
        except Exception as exc:
            QMessageBox.critical(self, tr("Delete error"), domain_message(str(exc))); return
        if self.kind == "photo":
            self.current_attachment_id = None; self._show_gallery()
        self.refresh(); self.changed.emit()
        cleanup_warning = getattr(result, "cleanup_warning", None)
        if cleanup_warning:
            QMessageBox.warning(
                self, tr("Cleanup warning"),
                f"{tr('The attachment was deleted, but a temporary file could not be removed.')}\n\n{cleanup_warning}"
            )


class EntityAttachmentDialog(QDialog):
    """Compatibility wrapper retained for legacy callers."""
    def __init__(self, service, owner_type, owner_id, parent=None, read_only=False, unsaved=False):
        super().__init__(parent)
        self.setWindowTitle(tr("Photos and documents")); self.resize(1000, 600)
        root = QVBoxLayout(self); self.tabs = QTabWidget(); self.tables = {}; self.mutation_buttons = []
        for kind, caption in (("photo", tr("Photos")), ("document", tr("Documents"))):
            manager = EntityAttachmentManagerWidget(service, owner_type, owner_id, kind, self, read_only, unsaved)
            self.tabs.addTab(manager, caption); self.tables[kind] = manager.table
            self.mutation_buttons.extend(manager.mutation_buttons)
        root.addWidget(self.tabs); close = QPushButton(tr("Close")); close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def refresh(self):
        for i in range(self.tabs.count()):
            self.tabs.widget(i).refresh()
