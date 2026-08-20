from PySide6.QtWidgets import QComboBox, QDialog, QLineEdit, QMessageBox

from app.localization import tr
from infrastructure.services.production_blast_service import PermissionDenied, ProductionBlastInput, ValidationError
from ui.widgets.design_system import configure_standard_dialog, create_form_section, standard_dialog_actions


class BlockDialog(QDialog):
    """Metadata editor for an existing production BlastEvent shown as a Block."""

    def __init__(self, service, domain_repo, user, domain_id=None, block=None,
                 read_only=False, expected_version=None):
        super().__init__()
        if block is None:
            raise ValueError("Blocks are created through Add blast event")
        self.service = service
        self.domain_repo = domain_repo
        self.user = user
        self.block = block
        self.saved_block_id = None
        self.read_only = read_only or not user.can_edit
        self.setWindowTitle(tr("Edit Block"))
        root = configure_standard_dialog(self, minimum_width=480)
        general, form = create_form_section("General", self)
        self.domain = QComboBox()
        self.block_number = QLineEdit()
        self.horizon = QLineEdit()
        selected = block.domain_id
        domain = domain_repo.get(selected)
        if domain:
            for item in domain_repo.selectable_for_site(domain.site_id):
                self.domain.addItem(item.domain_name, (item.domain_id, item.version))
            self.domain.setCurrentIndex(next(
                (index for index in range(self.domain.count())
                 if self.domain.itemData(index)[0] == selected), 0,
            ))
            # Keep the established selectable-Domain/read-only behavior.
            self.domain.setEnabled(self.domain.count()>1 and not self.read_only)
        form.addRow(tr("Block number"), self.block_number)
        form.addRow(tr("Domain"), self.domain)
        form.addRow(tr("Horizon, m"), self.horizon)
        root.addWidget(general)
        self.expected_version = expected_version
        self.block_number.setText(block.block_number)
        self.horizon.setText(str(block.horizon_m))
        self.block_number.setReadOnly(self.read_only)
        self.horizon.setReadOnly(self.read_only)
        actions, self.cancel_button, self.save_button = standard_dialog_actions(
            self, "Save", accept=self._save,
        )
        self.save_button.setVisible(not self.read_only)
        root.addWidget(actions)

    def _input(self):
        data = self.domain.currentData()
        domain_id = data[0] if isinstance(data, tuple) else data
        return ProductionBlastInput(
            domain_id, self.block_number.text(), self.horizon.text(), self.block.comment,
        )

    def _save(self):
        try:
            data = self._input()
            selected = self.domain.currentData()
            target_version = selected[1]
            frozen = self.service.active_geometry_elevation(self.block.id)
            try:
                new_horizon = float(data.horizon_text.replace(",", "."))
            except ValueError:
                new_horizon = None
            if frozen is not None and new_horizon is not None and abs(new_horizon - float(frozen)) > 0.01:
                warning = tr(
                    "The new Horizon differs from the active imported geometry elevation. "
                    "Existing geometry revisions will remain unchanged.\n\nContinue?"
                )
                if QMessageBox.question(self, tr("Frozen geometry"), warning) != QMessageBox.Yes:
                    return
            self.saved_block_id = self.service.update_metadata(
                self.block.id, domain_id=data.domain_id, block_number=data.block_number,
                horizon_text=data.horizon_text, user=self.user,
                expected_version=self.expected_version, target_expected_version=target_version,
            )
            self.accept()
        except (ValidationError, PermissionDenied, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, tr("Could not save block"), str(exc))
