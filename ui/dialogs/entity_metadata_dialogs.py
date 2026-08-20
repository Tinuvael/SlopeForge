"""Compact identity/location editors; engineering facts live elsewhere."""
from PySide6.QtWidgets import QComboBox, QDialog, QLineEdit

from app.localization import tr
from ui.widgets.design_system import (
    ChevronDoubleSpinBox,
    configure_standard_dialog,
    create_form_section,
    standard_dialog_actions,
)


class EntityMetadataDialog(QDialog):
    def __init__(self, domains, current_domain_id, *, name, horizon=None, block=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit Block") if block else tr("Edit"))
        root = configure_standard_dialog(self, minimum_width=480)
        general, form = create_form_section("General", self)
        self.name = QLineEdit(name)
        self.name.setObjectName("block_number" if block else "name")
        self.domain = QComboBox()
        self.domain.setObjectName("domain")
        for item in domains:
            self.domain.addItem(item.domain_name, (item.domain_id, item.version))
        self.domain.setCurrentIndex(next(
            (index for index in range(self.domain.count())
             if self.domain.itemData(index)[0] == current_domain_id), 0,
        ))
        self.domain.setEnabled(self.domain.count() > 1)
        form.addRow(tr("Block number") if block else tr("Name"), self.name)
        form.addRow(tr("Domain"), self.domain)
        self.horizon = None
        if horizon is not None:
            self.horizon = ChevronDoubleSpinBox()
            self.horizon.setObjectName("horizon")
            self.horizon.setDecimals(3)
            self.horizon.setRange(-100000, 100000)
            self.horizon.setValue(float(horizon))
            form.addRow(tr("Horizon, m"), self.horizon)
        root.addWidget(general)
        actions, self.cancel_button, self.save_button = standard_dialog_actions(self, "Save")
        root.addWidget(actions)
        self.name.setFocus()

    @property
    def selected_domain(self):
        return self.domain.currentData()


class ContourMetadataDialog(EntityMetadataDialog):
    def __init__(self, domains, current_domain_id, name, horizon, parent=None):
        super().__init__(domains, current_domain_id, name=name, horizon=horizon, parent=parent)
        self.setWindowTitle(tr("Edit Contour Blast"))


class AssessmentAreaMetadataDialog(EntityMetadataDialog):
    def __init__(self, domains, current_domain_id, name, parent=None):
        super().__init__(domains, current_domain_id, name=name, parent=parent)
        self.setWindowTitle(tr("Edit Assessment Area"))
