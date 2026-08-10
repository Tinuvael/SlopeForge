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


def test_completed_initial_result_uses_stored_values_then_live_edit_recalculates(monkeypatch):
    app()
    from copy import deepcopy
    from tests.test_wall_assessment_persistence_ui import make_state,filled_draft
    import ui.editors.assessment_evaluation_editor as module
    state,area=make_state(); evaluation,draft=filled_draft(state,area); saved=evaluation.save_revision(draft,"completed"); historical=deepcopy(saved)
    original=module.calculate_revision; calls=[]; allow=False
    def tracked(revision,*args,**kwargs):
        calls.append(revision)
        if not allow:raise AssertionError("completed revision was recalculated during initial display")
        return original(revision,*args,**kwargs)
    monkeypatch.setattr(module,"calculate_revision",tracked)
    dialog=module.AssessmentAreaEvaluationDialog(area,evaluation,saved,lambda *_:None)
    assert calls==[] and "DAI: 1.000" in dialog.summary.text()
    assert f"FCI: {saved.face_condition_index:.3f}" in dialog.summary.text()
    assert saved.result_label in dialog.summary.text()
    allow=True; dialog.inspector.setText("Changed inspector")
    assert calls and dialog._preview is not saved
    assert saved.to_dict()==historical.to_dict() and len(evaluation.revisions)==1
    dialog._allow_close=True; dialog.close()


def test_cancelled_attachment_selection_does_not_ensure_owner(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    service=SimpleNamespace(list_for_owner=lambda *_:[]); ensured=[]
    manager=module.EntityAttachmentManagerWidget(service,"assessment_evaluation",None,"document",ensure_owner=lambda:ensured.append(True))
    monkeypatch.setattr(module.QFileDialog,"getOpenFileNames",lambda *_:([],"")); manager.add()
    assert ensured==[] and manager.owner_id is None


def test_cancelled_attachment_metadata_does_not_ensure_owner(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    service=SimpleNamespace(list_for_owner=lambda *_:[]); ensured=[]
    manager=module.EntityAttachmentManagerWidget(service,"assessment_evaluation",None,"document",ensure_owner=lambda:ensured.append(True))
    monkeypatch.setattr(module.QFileDialog,"getOpenFileNames",lambda *_:(["known.pdf"],"Documents (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip)"))
    monkeypatch.setattr(module.AttachmentMetadataDialog,"exec",lambda *_:module.QDialog.DialogCode.Rejected); manager.add()
    assert ensured==[] and manager.owner_id is None


def test_successful_attachment_ensures_owner_once(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    added=[]
    service=SimpleNamespace(list_for_owner=lambda *_:[],add_files=lambda *args:added.append(args)); owners=[]
    def ensure():owners.append(True); return SimpleNamespace(id="E-1")
    manager=module.EntityAttachmentManagerWidget(service,"assessment_evaluation",None,"document",ensure_owner=ensure)
    monkeypatch.setattr(module.QFileDialog,"getOpenFileNames",lambda *_:(["known.pdf"],"Documents (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip)")); monkeypatch.setattr(module.AttachmentMetadataDialog,"exec",lambda *_:module.QDialog.DialogCode.Accepted); monkeypatch.setattr(module.AttachmentMetadataDialog,"values",lambda *_:{})
    manager.add(); assert len(owners)==1 and len(added)==1 and manager.owner_id=="E-1"


def test_unknown_document_warning_can_cancel_without_owner(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    service=SimpleNamespace(list_for_owner=lambda *_:[]); ensured=[]
    manager=module.EntityAttachmentManagerWidget(service,"assessment_evaluation",None,"document",ensure_owner=lambda:ensured.append(True))
    monkeypatch.setattr(module.QFileDialog,"getOpenFileNames",lambda *_:(["unknown.bin"],"All files (*)")); questions=[]; monkeypatch.setattr(module.QMessageBox,"question",lambda *args:questions.append(args[2]) or module.QMessageBox.StandardButton.No)
    manager.add(); assert questions==["SlopeForge may not be able to preview this file. Add it anyway?"] and ensured==[]


def test_failed_add_rolls_back_only_newly_prepared_owner(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    rolled_back=[]
    service=SimpleNamespace(list_for_owner=lambda *_:[],add_files=lambda *_:(_ for _ in ()).throw(RuntimeError("copy failed")))
    owner=SimpleNamespace(id="E-new")
    manager=module.EntityAttachmentManagerWidget(service,"assessment_evaluation",None,"document",
        ensure_owner=lambda:(owner,lambda:rolled_back.append(owner)))
    monkeypatch.setattr(module.QFileDialog,"getOpenFileNames",lambda *_:(['report.pdf'],"Documents (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip)"))
    monkeypatch.setattr(module.AttachmentMetadataDialog,"exec",lambda *_:module.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(module.AttachmentMetadataDialog,"values",lambda *_:{})
    errors=[]; monkeypatch.setattr(module.QMessageBox,"critical",lambda *args:errors.append(args[2]))
    manager.add()
    assert rolled_back==[owner] and manager.owner_id is None and errors


def test_failed_add_never_rolls_back_existing_owner(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    service=SimpleNamespace(list_for_owner=lambda *_:[],add_files=lambda *_:(_ for _ in ()).throw(RuntimeError("copy failed")))
    ensured=[]
    manager=module.EntityAttachmentManagerWidget(service,"assessment_evaluation","E-existing","document",
        ensure_owner=lambda:ensured.append(True))
    monkeypatch.setattr(module.QFileDialog,"getOpenFileNames",lambda *_:(['report.pdf'],"Documents (*.pdf *.doc *.docx *.xls *.xlsx *.csv *.txt *.dxf *.dwg *.zip)"))
    monkeypatch.setattr(module.AttachmentMetadataDialog,"exec",lambda *_:module.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(module.AttachmentMetadataDialog,"values",lambda *_:{})
    monkeypatch.setattr(module.QMessageBox,"critical",lambda *_:None)
    manager.add()
    assert manager.owner_id=="E-existing" and ensured==[]


def _attachment():
    return SimpleNamespace(id="ATT-1",title="Report",file_date=date(2026,8,1),subtype="other",
        custom_subtype="",original_filename="report.pdf",description="",file_size_bytes=3)


def test_edit_error_is_reported_without_refresh_or_changed(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    item=_attachment(); service=SimpleNamespace(list_for_owner=lambda *_:[item],is_missing=lambda *_:False,
        update_metadata=lambda *_args,**_kwargs:(_ for _ in ()).throw(RuntimeError("save failed")))
    manager=module.EntityAttachmentManagerWidget(service,"blast_event","BE-1","document"); manager.table.selectRow(0)
    monkeypatch.setattr(module.AttachmentMetadataDialog,"exec",lambda *_:module.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(module.AttachmentMetadataDialog,"values",lambda *_:{"title":"New","file_date":date.today(),"subtype":"other","description":"","custom_subtype":""})
    refreshed=[]; manager.refresh=lambda:refreshed.append(True); changes=[]; manager.changed.connect(lambda:changes.append(True))
    errors=[]; monkeypatch.setattr(module.QMessageBox,"critical",lambda *args:errors.append(args[2]))
    manager.edit()
    assert errors==["save failed"] and refreshed==[] and changes==[]


def test_delete_error_is_reported_without_refresh_or_changed(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    item=_attachment(); service=SimpleNamespace(list_for_owner=lambda *_:[item],is_missing=lambda *_:False,
        delete_attachment=lambda *_:(_ for _ in ()).throw(RuntimeError("delete failed")))
    manager=module.EntityAttachmentManagerWidget(service,"blast_event","BE-1","document"); manager.table.selectRow(0)
    class Box:
        class Icon:Warning=1
        class ButtonRole:DestructiveRole=1; RejectRole=2
        def __init__(self,*_args,**_kwargs):self.delete=None
        def addButton(self,_text,role):
            button=object()
            if role==self.ButtonRole.DestructiveRole:self.delete=button
            return button
        def exec(self):return 0
        def clickedButton(self):return self.delete
        @staticmethod
        def critical(*args):errors.append(args[2])
    errors=[]; monkeypatch.setattr(module,"QMessageBox",Box)
    refreshed=[]; manager.refresh=lambda:refreshed.append(True); changes=[]; manager.changed.connect(lambda:changes.append(True))
    manager.delete()
    assert errors==["delete failed"] and refreshed==[] and changes==[]


def test_delete_cleanup_warning_still_refreshes_and_emits_changed(monkeypatch):
    app(); import ui.dialogs.entity_attachment_dialog as module
    item=_attachment(); items=[item]
    def delete(_id):
        items.clear()
        return SimpleNamespace(cleanup_warning="report.pdf.slopeforge-delete-ID.tmp: locked")
    service=SimpleNamespace(list_for_owner=lambda *_:list(items),is_missing=lambda *_:False,
        delete_attachment=delete)
    manager=module.EntityAttachmentManagerWidget(service,"blast_event","BE-1","document"); manager.table.selectRow(0)
    warnings=[]; critical=[]
    class Box:
        class Icon:Warning=1
        class ButtonRole:DestructiveRole=1; RejectRole=2
        def __init__(self,*_args,**_kwargs):self.delete=None
        def addButton(self,_text,role):
            button=object()
            if role==self.ButtonRole.DestructiveRole:self.delete=button
            return button
        def exec(self):return 0
        def clickedButton(self):return self.delete
        @staticmethod
        def warning(*args):warnings.append(args[2])
        @staticmethod
        def critical(*args):critical.append(args[2])
    monkeypatch.setattr(module,"QMessageBox",Box)
    changes=[]; manager.changed.connect(lambda:changes.append(True))

    manager.delete()

    assert manager.table.rowCount()==0 and changes==[True]
    assert len(warnings)==1 and "temporary file could not be removed" in warnings[0]
    assert critical==[]

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
