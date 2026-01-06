from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Sequence

from app.templates.environment import get_template_env

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


class AnalyticsExportError(Exception):
    """Exception raised for analytics export-related errors."""


class AnalyticsExportService:
    """Export analytics reports to CSV and PDF."""

    def __init__(self) -> None:
        self.template_env = get_template_env()

    def export_csv(self, title: str, sections: List[Dict[str, Any]]) -> str:
        """Export analytics report sections to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([title])
        writer.writerow([f"Generated at: {datetime.utcnow().isoformat()}Z"])
        writer.writerow([])

        for section in sections:
            writer.writerow([section.get("title", "Section")])
            columns: Sequence[str] = section.get("columns", [])
            if columns:
                writer.writerow(list(columns))
            for row in section.get("rows", []):
                if isinstance(row, dict):
                    writer.writerow([row.get(col, "") for col in columns])
                else:
                    writer.writerow(list(row))
            writer.writerow([])

        return output.getvalue()

    def export_pdf(self, title: str, sections: List[Dict[str, Any]]) -> bytes:
        """Export analytics report sections to PDF format."""
        if not WEASYPRINT_AVAILABLE:
            raise AnalyticsExportError(
                "PDF export is not available. Install WeasyPrint: pip install weasyprint"
            )

        template = self.template_env.get_template("reports/analytics_report.html.j2")
        html_content = template.render(
            title=title,
            generated_at=datetime.utcnow().isoformat() + "Z",
            sections=sections,
        )
        css = self._get_report_css()

        html = HTML(string=html_content)
        pdf_bytes = html.write_pdf(stylesheets=[CSS(string=css)])
        if pdf_bytes is None:
            raise AnalyticsExportError("PDF generation failed - no output produced")
        return pdf_bytes

    def _get_report_css(self) -> str:
        """Return base CSS for analytics PDFs."""
        return """
        @page { size: A4; margin: 24mm 18mm; }
        body { font-family: Arial, sans-serif; color: #0f172a; font-size: 12px; }
        h1 { font-size: 20px; margin: 0 0 6px; }
        h2 { font-size: 14px; margin: 18px 0 8px; color: #111827; }
        .meta { color: #64748b; font-size: 11px; margin-bottom: 16px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
        th, td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }
        th { background: #f8fafc; font-size: 11px; text-transform: uppercase; letter-spacing: 0.02em; }
        td { font-size: 11px; }
        .section { margin-bottom: 16px; }
        """
