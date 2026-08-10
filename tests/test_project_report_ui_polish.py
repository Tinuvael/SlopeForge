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
        page=dialog.take_tab(title); target.addTab(page,title); pages.append(page)
    assert all(page.parent() is not dialog.tabs for page in pages)
    assert all(page.findChildren(QtWidgets.QWidget) for page in pages)
    assert dialog.summary.text() and "DAI: 1.000" in dialog.summary.text()
    dialog._allow_close=True; dialog.close(); target.close()



def test_assessment_page_nested_tabs_have_exclusive_initial_visibility(monkeypatch):
    application=app()
    from tests.test_wall_assessment_persistence_ui import make_state,filled_draft
    from prototype_2d.assessment_event_link_service import AssessmentEventLinkService
    from prototype_2d.wall_assessment import AssessmentAreaEvaluationService
    import ui.pages.assessment_area_page as module

    state,area=make_state(); evaluation,draft=filled_draft(state,area)
    evaluation.save_revision(draft,"completed"); state.evaluations.append(evaluation)

    class Attachments:
        def list_for_owner(self,*_args):return []
    class Controller:
        def __init__(self,*_args):
            self.state=state; self.attachments=Attachments(); self.links=AssessmentEventLinkService(state)
        def area(self,_id):return area
        def evaluation_draft(self,_area):return evaluation,evaluation.active_revision()
        def save_evaluation(self,*_args):raise AssertionError("construction must not save")
        def ensure_evaluation_owner(self,*_args):raise AssertionError("opening must not create an owner")
        def save(self):raise AssertionError("construction must not persist")
    monkeypatch.setattr(module,"EntityPageController",Controller)
    context=SimpleNamespace(current_user=SimpleNamespace(can_edit=True))
    before=len(evaluation.revisions); page=module.AssessmentAreaPage(context,1,"Domain",area.id)
    page.show(); page.tabs.setCurrentWidget(page.assessment_tab); application.processEvents()
    sections=page.assessment_sections
    general,geometry,condition=(sections.widget(i) for i in range(3))
    assert sections.currentIndex()==0
    assert general.isVisible() and not geometry.isVisible() and not condition.isVisible()
    assert general.findChildren(QtWidgets.QWidget) and geometry.findChildren(QtWidgets.QWidget) and condition.findChildren(QtWidgets.QWidget)
    assert page.save_evaluation_button.isVisible() and page.complete_evaluation_button.isVisible()
    assert page.evaluation_editor.summary.text() and "DAI: 1.000" in page.evaluation_editor.summary.text()
    for index,visible in ((1,geometry),(2,condition),(0,general)):
        sections.setCurrentIndex(index); application.processEvents()
        assert visible.isVisible()
        assert all(not sections.widget(other).isVisible() for other in range(3) if other!=index)
    assert len(evaluation.revisions)==before
    page.close()

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
