from pathlib import Path


def source(path):
    return Path(path).read_text(encoding="utf-8")


def test_wizard_uses_persistent_three_column_shell_and_single_navigation_path():
    page = source("ui/pages/assessment_area_creation_page.py")
    stepper = source("ui/widgets/assessment_wizard_stepper.py")
    assert "QStackedWidget" not in page
    assert page.count("AssessmentGeometryEditorWidget(") == 1
    assert all(name in page for name in ("assessmentInfoCard", "assessmentPlanCard", "assessmentContextCard", "assessmentFooter"))
    assert "Back / Close" not in page
    assert page.count("self.back = QPushButton") == 1
    assert page.count("self.cancel = QPushButton") == 1
    assert "step_nodes" in stepper
    assert '("General information", "Boundary", "Linked events", "Review", "Save")' in stepper
    assert "→" not in stepper


def test_map_is_owned_by_the_persistent_plan_card():
    page = source("ui/pages/assessment_area_creation_page.py")
    assert "plan_layout.addWidget(self.editor, 1)" in page
    assert "self.current_step = self.BOUNDARY if edit_area_id else self.GENERAL" in page
