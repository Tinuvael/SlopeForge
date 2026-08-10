from datetime import date
from types import SimpleNamespace
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import pytest

QtWidgets=pytest.importorskip("PySide6.QtWidgets",exc_type=ImportError)
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QMessageBox,QTabWidget


def app():return QApplication.instance() or QApplication([])


def test_assessment_editor_tabs_are_explicitly_detached_and_keep_content():
    app()
    from tests.test_wall_assessment_persistence_ui import make_state,filled_draft
    from ui.editors.assessment_evaluation_editor import AssessmentAreaEvaluationDialog
    state,area=make_state(); evaluation,draft=filled_draft(state,area); evaluation.save_revision(draft,"completed")
    dialog=AssessmentAreaEvaluationDialog(area,evaluation,evaluation.active_revision(),lambda *_:None)
    target=QTabWidget()
    pages=[]
    for title in ("General","Geometry","Face condition","Matrix"):
        page=dialog.take_tab(title); target.addTab(page,title); page.setVisible(True); pages.append(page)
    assert all(page.parent() is not dialog.tabs for page in pages)
    assert all(page.findChildren(QtWidgets.QWidget) for page in pages)
    assert dialog.summary.text() and "DAI: 1.000" in dialog.summary.text()
    dialog._allow_close=True; dialog.close(); target.close()


def test_russian_standard_buttons_are_never_blank(tmp_path):
    application=app()
    from app.localization import LANGUAGE_KEY,install_selected_translator
    store=QSettings(str(tmp_path/"settings.ini"),QSettings.Format.IniFormat); store.setValue(LANGUAGE_KEY,"ru")
    assert install_selected_translator(application,store)=="ru"
    box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
    assert box.button(QDialogButtonBox.StandardButton.Save).text()
    assert box.button(QDialogButtonBox.StandardButton.Cancel).text()
    message=QMessageBox(QMessageBox.Icon.Question,"Question","Continue?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
    assert message.button(QMessageBox.StandardButton.Yes).text()
    assert message.button(QMessageBox.StandardButton.No).text()
    ok=QMessageBox(QMessageBox.Icon.Information,"Done","Done",QMessageBox.StandardButton.Ok)
    assert ok.button(QMessageBox.StandardButton.Ok).text()


def test_report_saved_file_is_opened_without_success_modal(monkeypatch,tmp_path):
    app(); import ui.dialogs.project_report_dialog as module
    target=tmp_path/"report.xlsx"; context=SimpleNamespace(session_factory=object())
    dialog=module.ProjectReportDialog(context,1,"Project")
    monkeypatch.setattr(module.QFileDialog,"getSaveFileName",lambda *_:(str(target),"xlsx"))
    monkeypatch.setattr(module.ProjectReportService,"collect",lambda *_:object())
    monkeypatch.setattr(module,"write_project_report",lambda _report,path:target.write_bytes(b"xlsx"))
    opened=[]; monkeypatch.setattr(module.QDesktopServices,"openUrl",lambda url:opened.append(url.toLocalFile()) or True)
    monkeypatch.setattr(module.QMessageBox,"information",lambda *_:pytest.fail("success modal is redundant"))
    dialog.generate()
    assert opened==[str(target.resolve())] and dialog.result()==dialog.DialogCode.Accepted


def test_report_open_failure_warns_but_keeps_saved_file(monkeypatch,tmp_path):
    app(); import ui.dialogs.project_report_dialog as module
    target=tmp_path/"report.xlsx"; dialog=module.ProjectReportDialog(SimpleNamespace(session_factory=object()),1,"Project")
    monkeypatch.setattr(module.QFileDialog,"getSaveFileName",lambda *_:(str(target),"xlsx")); monkeypatch.setattr(module.ProjectReportService,"collect",lambda *_:object()); monkeypatch.setattr(module,"write_project_report",lambda _report,path:target.write_bytes(b"xlsx")); monkeypatch.setattr(module.QDesktopServices,"openUrl",lambda _url:False)
    warnings=[]; monkeypatch.setattr(module.QMessageBox,"warning",lambda *args:warnings.append(args[2]))
    dialog.generate()
    assert target.exists() and warnings==["The report was saved, but could not be opened automatically."]
