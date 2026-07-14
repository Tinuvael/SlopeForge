from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel
)

from database import get_legacy_database

class ProjectTree(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Project"))

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        layout.addWidget(self.tree)

        self.load_data()


    def load_data(self):

        self.tree.clear()

        for deposit in get_legacy_database().get_deposits():

            self.tree.addTopLevelItem(
                QTreeWidgetItem([deposit["name"]]))