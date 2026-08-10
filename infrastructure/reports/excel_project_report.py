from reports.excel_project_report import write_project_report


class OpenPyxlProjectReportWriter:
    def write(self, report, output_path) -> None:
        write_project_report(report, output_path)
