import pytest


def test_embedded_technical_card_sections_expand_without_outer_policy_changes():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.technical_card_widgets import BlastDesignEditorWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    page = widgets.QLabel("technical card page")
    section = BlastDesignEditorWidget(page)

    assert section.minimumHeight() == 0
    assert section.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert page.minimumHeight() == 0
    assert page.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert section.layout().contentsMargins().top() == 0
    assert section.layout().stretch(0) == 1

    section.close()
    app.processEvents()
