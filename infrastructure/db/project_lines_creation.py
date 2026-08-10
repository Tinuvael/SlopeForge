from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from repositories.project_lines_repository import ProjectLinesRepository


class SqlAlchemyProjectLinesCreationSupport:
    def __init__(self, session_factory): self._repository = ProjectLinesRepository(session_factory)

    def prepare(self, source_path: str):
        dataset, _summary = ProjectLinesDatasetService(AssessmentDomainState()).import_dataset(source_path)
        return dataset

    def save_active(self, site_id: int, dataset) -> None:
        self._repository.import_dataset(site_id, dataset, make_active=True)
