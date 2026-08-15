from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from domain.blasting.charge_design import ChargeForm, ExplosiveClass, ExplosiveProduct, ExplosiveProductKind
from app.localization import tr

CHARGE_FORM_LABELS={ChargeForm.BULK:"Bulk",ChargeForm.PUMPABLE:"Pumpable",ChargeForm.CARTRIDGED:"Cartridged"}
EXPLOSIVE_CLASS_LABELS={ExplosiveClass.ANFO:"ANFO / Igdanite",ExplosiveClass.EMULSION:"Emulsion explosive",
    ExplosiveClass.HEAVY_ANFO:"Heavy ANFO",ExplosiveClass.SLURRY:"Water gel / Slurry",
    ExplosiveClass.DYNAMITE:"Dynamite / gelatinous",ExplosiveClass.OTHER:"Other"}


class ExplosiveProductDialog(QDialog):
    def __init__(self, product: ExplosiveProduct | None = None, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(tr("Edit explosive product") if product else tr("Add explosive product"))
        form = QFormLayout(self)
        self.name_edit = QLineEdit(product.name if product else "")
        self.form_combo = QComboBox()
        self.form_combo.addItem(tr("Bulk"), ChargeForm.BULK)
        self.form_combo.addItem(tr("Pumpable"), ChargeForm.PUMPABLE)
        self.form_combo.addItem(tr("Cartridged"), ChargeForm.CARTRIDGED)
        if product:
            self.form_combo.setCurrentIndex(self._find_enum_index(
                self.form_combo, ChargeForm, product.charge_form))
        self.class_combo=QComboBox()
        for value,label in EXPLOSIVE_CLASS_LABELS.items(): self.class_combo.addItem(tr(label),value)
        if product:self.class_combo.setCurrentIndex(self._find_enum_index(self.class_combo,ExplosiveClass,product.explosive_class))
        color_row = QWidget(); color_layout = QHBoxLayout(color_row); color_layout.setContentsMargins(0, 0, 0, 0)
        self.color_edit = QLineEdit(product.display_color if product else "#000000")
        choose = QPushButton(tr("Choose color"))
        choose.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_edit); color_layout.addWidget(choose)
        self.density = self._number(product.density_kg_m3/1000 if product and product.density_kg_m3 is not None else None)
        self.diameter = self._number(product.cartridge_diameter_mm if product else None)
        self.mass = self._number(product.cartridge_mass_kg if product else None, decimals=4)
        self.length = self._number(product.cartridge_length_mm if product else None)
        self.pitch = self._number(product.default_pitch_m if product else None, decimals=4)
        form.addRow(tr("Name"), self.name_edit); form.addRow(tr("Charge form"), self.form_combo)
        form.addRow(tr("Explosive class"),self.class_combo)
        form.addRow(tr("Display color"), color_row)
        self.density_label = QLabel(tr("Density, g/cm³")); form.addRow(self.density_label, self.density)
        self.diameter_label = QLabel(tr("Cartridge diameter, mm")); form.addRow(self.diameter_label, self.diameter)
        self.mass_label = QLabel(tr("Cartridge mass, kg")); form.addRow(self.mass_label, self.mass)
        self.length_label=QLabel(tr("Cartridge length, mm (optional)")); form.addRow(self.length_label,self.length)
        self.pitch_label = QLabel(tr("Default pitch, m (optional)")); form.addRow(self.pitch_label, self.pitch)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.rejected.connect(self.reject); buttons.accepted.connect(self._validate_and_accept)
        form.addRow(buttons)
        self.form_combo.currentIndexChanged.connect(self._update_fields)
        self._update_fields()

    @staticmethod
    def _number(value, *, decimals=3):
        """Create a numeric input whose minimum is an explicit unset sentinel."""
        field = QDoubleSpinBox(); field.setDecimals(decimals); field.setMaximum(1_000_000_000)
        field.setMinimum(-1)
        field.setSpecialValueText(tr("Not set"))
        field.setValue(float(value) if value is not None else field.minimum())
        return field

    @staticmethod
    def _number_value(field: QDoubleSpinBox) -> float | None:
        """Never allow the UI-only unset sentinel to cross into the domain."""
        return None if field.value() == field.minimum() else field.value()

    @staticmethod
    def _find_enum_index(combo: QComboBox, enum_type, value) -> int:
        expected = enum_type(value)
        return next((index for index in range(combo.count())
                     if enum_type(combo.itemData(index)) == expected), -1)

    def _selected_charge_form(self) -> ChargeForm:
        """Normalize QVariant/string item data at the Qt boundary."""
        return ChargeForm(self.form_combo.currentData())

    def _selected_explosive_class(self)->ExplosiveClass:
        return ExplosiveClass(self.class_combo.currentData())

    def _update_fields(self):
        bulk = self._selected_charge_form() != ChargeForm.CARTRIDGED
        for widget in (self.density_label, self.density): widget.setVisible(bulk)
        for widget in (self.diameter_label, self.diameter, self.mass_label, self.mass,
                       self.length_label,self.length,self.pitch_label, self.pitch): widget.setVisible(not bulk)

    def _choose_color(self):
        color = QColorDialog.getColor(QColor(self.color_edit.text()), self)
        if color.isValid(): self.color_edit.setText(color.name().upper())

    def value(self) -> ExplosiveProduct:
        charge_form=self._selected_charge_form()
        kind=(ExplosiveProductKind.CARTRIDGE if charge_form==ChargeForm.CARTRIDGED else ExplosiveProductKind.BULK)
        return ExplosiveProduct(
            id=self.product.id if self.product else 0, name=self.name_edit.text(), kind=kind,
            display_color=self.color_edit.text(), enabled=self.product.enabled if self.product else True,
            density_kg_m3=(self._number_value(self.density)*1000 if kind == ExplosiveProductKind.BULK and self._number_value(self.density) is not None else None),
            cartridge_diameter_mm=self._number_value(self.diameter) if kind == ExplosiveProductKind.CARTRIDGE else None,
            cartridge_mass_kg=self._number_value(self.mass) if kind == ExplosiveProductKind.CARTRIDGE else None,
            default_pitch_m=self._number_value(self.pitch) if kind == ExplosiveProductKind.CARTRIDGE else None,
            charge_form=charge_form,explosive_class=self._selected_explosive_class(),
            cartridge_length_mm=self._number_value(self.length) if kind==ExplosiveProductKind.CARTRIDGE else None,
        )

    def _validate_and_accept(self):
        try: self.value()
        except ValueError as exc: QMessageBox.warning(self, tr("Invalid product"), str(exc))
        else: self.accept()


class EngineeringCataloguesPage(QWidget):
    HEADERS = ("Name", "Charge form", "Explosive class", "Color", "Density, kg/m³", "Cartridge diameter, mm",
               "Cartridge mass, kg", "Cartridge length, mm", "Default pitch, m", "Status")

    def __init__(self, catalogue, *, can_edit: bool, parent=None):
        super().__init__(parent); self.catalogue = catalogue; self.can_edit = can_edit
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{tr('Explosives / charge materials')}</b>"))
        self.empty_label = QLabel(tr("No explosive products configured."))
        layout.addWidget(self.empty_label)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels([tr(header) for header in self.HEADERS])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table)
        actions = QHBoxLayout(); self.add_button = QPushButton(tr("Add product"))
        self.edit_button = QPushButton(tr("Edit")); self.toggle_button = QPushButton(tr("Enable / Disable"))
        for button in (self.add_button, self.edit_button, self.toggle_button): actions.addWidget(button)
        actions.addStretch(); layout.addLayout(actions)
        self.add_button.clicked.connect(self._add); self.edit_button.clicked.connect(self._edit)
        self.toggle_button.clicked.connect(self._toggle)
        self.add_button.setEnabled(can_edit); self.reload()

    def reload(self):
        self.products = self.catalogue.list_products()
        self.table.setRowCount(len(self.products))
        for row, product in enumerate(self.products):
            values = (product.name, tr(CHARGE_FORM_LABELS[product.charge_form]),tr(EXPLOSIVE_CLASS_LABELS[product.explosive_class]),
                      product.display_color, product.density_kg_m3,
                      product.cartridge_diameter_mm, product.cartridge_mass_kg,
                      product.cartridge_length_mm,product.default_pitch_m, tr("Enabled") if product.enabled else tr("Disabled"))
            for column, value in enumerate(values):
                item = QTableWidgetItem("—" if value is None else str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, product.id)
                elif column == 3:
                    item.setBackground(QColor(product.display_color))
                self.table.setItem(row, column, item)
        self.empty_label.setVisible(not self.products); self.table.setVisible(bool(self.products))
        self.table.resizeColumnsToContents(); self._selection_changed()

    def _selected(self):
        row = self.table.currentRow()
        return self.products[row] if 0 <= row < len(self.products) else None

    def _selection_changed(self):
        enabled = self.can_edit and self._selected() is not None
        self.edit_button.setEnabled(enabled); self.toggle_button.setEnabled(enabled)

    def _run_dialog(self, product=None):
        dialog = ExplosiveProductDialog(product, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                if product: self.catalogue.update_product(dialog.value())
                else: self.catalogue.create_product(dialog.value())
            except (ValueError, LookupError) as exc:
                QMessageBox.warning(self, tr("Catalogue update failed"), str(exc)); return
            self.reload()

    def _add(self): self._run_dialog()
    def _edit(self):
        if self._selected(): self._run_dialog(self._selected())
    def _toggle(self):
        product = self._selected()
        if product:
            try: self.catalogue.set_product_enabled(product.id, not product.enabled)
            except (ValueError, LookupError) as exc: QMessageBox.warning(self, tr("Catalogue update failed"), str(exc))
            else: self.reload()
