
from app.localization import tr
"""Reusable embedded views backed by the existing TechnicalCardDialog editor."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu,QSizePolicy,QToolButton,QVBoxLayout,QWidget
from ui.editors.technical_card_editor import TechnicalCardDialog

class TechnicalCardSaveButton(QToolButton):
    """One save action with completion available from its native popup menu."""
    def __init__(self, save_draft, save_completed, parent=None):
        super().__init__(parent)
        self.setText(tr("Save"))
        self.setObjectName("TechnicalCardSaveButton")
        self.setProperty("role", "primary")
        self.setMinimumSize(124, 32)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu = QMenu(self)
        self.save_complete_action = menu.addAction(tr("Save & complete"))
        self.setMenu(menu)
        self.clicked.connect(save_draft)
        self.save_complete_action.triggered.connect(save_completed)

class TechnicalCardEditorWidget(QWidget):
    """Permanently hidden adapter that lends pages from the proven editor."""
    def __init__(self,event,card,revision,save_callback,parent=None,read_only=False,domain_name="",explosive_products=None,charge_presets=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setFixedSize(0, 0)
        self.hide()
        self.editor=TechnicalCardDialog(
            event,card,revision,save_callback,None,read_only,domain_name=domain_name,
            explosive_products=explosive_products,charge_presets=charge_presets)
        self.tabs=self.editor.tabs
    def take_tab(self,title):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index)==title:
                page=self.tabs.widget(index); self.tabs.removeTab(index)
                page.setProperty("blastEventType",self.editor.blast_event.event_type)
                return page
        return QWidget()
    def save_draft(self): return False if self.editor.read_only else self.editor._save("draft")
    def complete(self): return False if self.editor.read_only else self.editor._save("completed")

class _SectionWidget(QWidget):
    def __init__(self,page,parent=None):
        super().__init__(parent)
        self.page=page
        self.setMinimumHeight(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        page.setParent(self)
        page.setMinimumHeight(0)
        page.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(page,1)
        page.setVisible(True)
class GeomechanicsEditorWidget(_SectionWidget): pass
class BlastDesignEditorWidget(_SectionWidget): pass
class ActualExecutionEditorWidget(_SectionWidget):
    def __init__(self,page,parent=None):
        super().__init__(page,parent)
        # BoreholeChargeBuilder contains a 330 px minimum graphics viewport plus
        # its add-component row, legend, margins and spacing.  The editor-level
        # 350 px minimum is therefore too small: with several factual groups Qt
        # can compress the builder until the toe label and legend visually
        # collide.  Reserve the real content height for production Actual and let
        # the outer Execution fact scroll area grow instead of squeezing it.
        # The selector also applies to builders created later by Copy/Add/Replace.
        if page.property("blastEventType") == "production":
            self.setStyleSheet("""
                QWidget#actualBoreholeChargeBuilder {
                    min-height: 400px;
                }
            """)
