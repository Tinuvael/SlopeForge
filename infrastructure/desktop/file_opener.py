"""Qt desktop URL adapter kept outside domain and application."""
from pathlib import Path


def open_local_path(path: Path) -> bool:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
