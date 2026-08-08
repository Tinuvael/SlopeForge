"""Reusable embedded views backed by the existing TechnicalCardDialog editor."""
from PySide6.QtWidgets import QHBoxLayout,QPushButton,QVBoxLayout,QWidget
from ui.prototype_2d.technical_card_dialog import TechnicalCardDialog

class TechnicalCardEditorWidget(QWidget):
    """Hosts the proven revision editor without duplicating any editor logic."""
    def __init__(self,event,card,revision,save_callback,parent=None,read_only=False):
        super().__init__(parent); self.editor=TechnicalCardDialog(event,card,revision,save_callback,None,read_only)
        layout=QVBoxLayout(self); self.tabs=self.editor.tabs; self.tabs.setParent(self); layout.addWidget(self.tabs)
        actions=QHBoxLayout(); actions.addStretch(); self.draft=QPushButton("Сохранить черновик"); self.complete=QPushButton("Завершить")
        self.draft.clicked.connect(lambda:self.editor._save("draft")); self.complete.clicked.connect(lambda:self.editor._save("completed")); self.draft.setEnabled(not read_only); self.complete.setEnabled(not read_only); actions.addWidget(self.draft); actions.addWidget(self.complete); layout.addLayout(actions)
    def take_tab(self,title):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index)==title:
                page=self.tabs.widget(index); self.tabs.removeTab(index); return page
        return QWidget()
    def save_draft(self): return False if self.editor.read_only else self.editor._save("draft")
    def complete(self): return False if self.editor.read_only else self.editor._save("completed")

class _SectionWidget(QWidget):
    def __init__(self,page,parent=None):
        super().__init__(parent); self.page=page; page.setParent(self); QVBoxLayout(self).addWidget(page); page.setVisible(True)
class GeomechanicsEditorWidget(_SectionWidget): pass
class BlastDesignEditorWidget(_SectionWidget): pass
class ActualExecutionEditorWidget(_SectionWidget): pass
