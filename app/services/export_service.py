"""
Export Service

Provides CSV and PDF export functionality for accounting reports:
- Trial Balance
- Balance Sheet
- Income Statement
- General Ledger
- Aging Reports (Receivables/Payables)
"""
import csv
import io
from typing import Dict, Any, List, Optional, cast
from datetime import date, datetime
from decimal import Decimal

from app.templates.environment import get_template_env

# Optional PDF support - gracefully handle if WeasyPrint is not installed
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


class ExportError(Exception):
    """Exception raised for export-related errors."""
    pass


class ExportService:
    """Service for exporting reports to CSV and PDF formats."""

    # Template mapping for report types
    TEMPLATE_MAP = {
        "trial_balance": "reports/trial_balance.html.j2",
        "balance_sheet": "reports/balance_sheet.html.j2",
        "income_statement": "reports/income_statement.html.j2",
        "general_ledger": "reports/general_ledger.html.j2",
        "receivables_aging": "reports/receivables_aging.html.j2",
        "payables_aging": "reports/payables_aging.html.j2",
    }

    def __init__(self):
        self.company_name = "dotMac Limited"  # Can be made configurable
        self.template_env = get_template_env()

    def export_csv(self, data: Dict[str, Any], report_type: str) -> str:
        """
        Export report data to CSV format.

        Args:
            data: Report data dictionary
            report_type: Type of report (trial_balance, balance_sheet, income_statement, etc.)

        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "trial_balance":
            self._write_trial_balance_csv(writer, data)
        elif report_type == "balance_sheet":
            self._write_balance_sheet_csv(writer, data)
        elif report_type == "income_statement":
            self._write_income_statement_csv(writer, data)
        elif report_type == "general_ledger":
            self._write_general_ledger_csv(writer, data)
        elif report_type == "receivables_aging":
            self._write_aging_csv(writer, data, "Receivables")
        elif report_type == "payables_aging":
            self._write_aging_csv(writer, data, "Payables")
        else:
            raise ExportError(f"Unknown report type: {report_type}")

        return output.getvalue()

    def export_pdf(self, data: Dict[str, Any], report_type: str) -> bytes:
        """
        Export report data to PDF format.

        Args:
            data: Report data dictionary
            report_type: Type of report

        Returns:
            PDF bytes
        """
        if not WEASYPRINT_AVAILABLE:
            raise ExportError(
                "PDF export is not available. Install WeasyPrint: pip install weasyprint"
            )

        html_content = self._generate_html(data, report_type)
        css = self._get_report_css()

        html = HTML(string=html_content)
        pdf_bytes = html.write_pdf(stylesheets=[CSS(string=css)])

        if pdf_bytes is None:
            raise ExportError("PDF generation failed - no output produced")
        return cast(bytes, pdf_bytes)

    def _write_trial_balance_csv(self, writer: Any, data: Dict[str, Any]) -> None:
        """Write trial balance to CSV."""
        writer.writerow([f"Trial Balance as of {data.get('as_of_date', '')}"])
        writer.writerow([])
        writer.writerow(["Account", "Account Name", "Root Type", "Debit", "Credit", "Balance"])

        for acc in data.get("accounts", []):
            writer.writerow([
                acc.get("account", ""),
                acc.get("account_name", ""),
                acc.get("root_type", ""),
                self._format_number(acc.get("debit", 0)),
                self._format_number(acc.get("credit", 0)),
                self._format_number(acc.get("balance", 0)),
            ])

        writer.writerow([])
        writer.writerow([
            "TOTAL", "", "",
            self._format_number(data.get("total_debit", 0)),
            self._format_number(data.get("total_credit", 0)),
            self._format_number(data.get("difference", 0)),
        ])
        writer.writerow(["Balanced:", "Yes" if data.get("is_balanced") else "No"])

    def _write_balance_sheet_csv(self, writer: Any, data: Dict[str, Any]) -> None:
        """Write balance sheet to CSV."""
        writer.writerow([f"Balance Sheet as of {data.get('as_of_date', '')}"])
        writer.writerow([])

        # Assets
        writer.writerow(["ASSETS"])
        writer.writerow(["Account", "Account Type", "Balance"])
        for acc in data.get("assets", {}).get("accounts", []):
            writer.writerow([
                acc.get("account", ""),
                acc.get("account_type", ""),
                self._format_number(acc.get("balance", 0)),
            ])
        writer.writerow(["Total Assets", "", self._format_number(data.get("assets", {}).get("total", 0))])
        writer.writerow([])

        # Liabilities
        writer.writerow(["LIABILITIES"])
        writer.writerow(["Account", "Account Type", "Balance"])
        for acc in data.get("liabilities", {}).get("accounts", []):
            writer.writerow([
                acc.get("account", ""),
                acc.get("account_type", ""),
                self._format_number(acc.get("balance", 0)),
            ])
        writer.writerow(["Total Liabilities", "", self._format_number(data.get("liabilities", {}).get("total", 0))])
        writer.writerow([])

        # Equity
        writer.writerow(["EQUITY"])
        writer.writerow(["Account", "Account Type", "Balance"])
        for acc in data.get("equity", {}).get("accounts", []):
            writer.writerow([
                acc.get("account", ""),
                acc.get("account_type", ""),
                self._format_number(acc.get("balance", 0)),
            ])
        writer.writerow(["Retained Earnings", "", self._format_number(data.get("retained_earnings", 0))])
        writer.writerow(["Total Equity", "", self._format_number(data.get("equity", {}).get("total", 0))])
        writer.writerow([])

        # Summary
        writer.writerow(["SUMMARY"])
        writer.writerow(["Total Assets", self._format_number(data.get("total_assets", 0))])
        writer.writerow(["Total Liabilities + Equity", self._format_number(data.get("total_liabilities_equity", 0))])
        writer.writerow(["Balanced:", "Yes" if data.get("is_balanced") else "No"])

    def _write_income_statement_csv(self, writer: Any, data: Dict[str, Any]) -> None:
        """Write income statement to CSV."""
        period = data.get("period", {})
        writer.writerow([f"Income Statement"])
        writer.writerow([f"Period: {period.get('start_date', '')} to {period.get('end_date', '')}"])
        writer.writerow([f"Basis: {data.get('basis', 'accrual').title()}"])
        writer.writerow([])

        # Income
        writer.writerow(["INCOME"])
        writer.writerow(["Account", "Account Type", "Amount"])
        for acc in data.get("income", {}).get("accounts", []):
            writer.writerow([
                acc.get("account", ""),
                acc.get("account_type", ""),
                self._format_number(acc.get("amount", 0)),
            ])
        writer.writerow(["Total Income", "", self._format_number(data.get("income", {}).get("total", 0))])
        writer.writerow([])

        # Expenses
        writer.writerow(["EXPENSES"])
        writer.writerow(["Account", "Account Type", "Amount"])
        for acc in data.get("expenses", {}).get("accounts", []):
            writer.writerow([
                acc.get("account", ""),
                acc.get("account_type", ""),
                self._format_number(acc.get("amount", 0)),
            ])
        writer.writerow(["Total Expenses", "", self._format_number(data.get("expenses", {}).get("total", 0))])
        writer.writerow([])

        # Summary
        writer.writerow(["SUMMARY"])
        writer.writerow(["Gross Profit", self._format_number(data.get("gross_profit", 0))])
        writer.writerow(["Net Income", self._format_number(data.get("net_income", 0))])
        writer.writerow(["Profit Margin", f"{data.get('profit_margin', 0):.2f}%"])

    def _write_general_ledger_csv(self, writer: Any, data: Dict[str, Any]) -> None:
        """Write general ledger to CSV."""
        writer.writerow(["General Ledger"])
        writer.writerow([])
        writer.writerow([
            "Posting Date", "Account", "Party Type", "Party",
            "Debit", "Credit", "Balance", "Voucher Type", "Voucher No", "Remarks"
        ])

        for entry in data.get("entries", []):
            writer.writerow([
                entry.get("posting_date", ""),
                entry.get("account", ""),
                entry.get("party_type", ""),
                entry.get("party", ""),
                self._format_number(entry.get("debit", 0)),
                self._format_number(entry.get("credit", 0)),
                self._format_number(entry.get("balance", 0)),
                entry.get("voucher_type", ""),
                entry.get("voucher_no", ""),
                entry.get("remarks", ""),
            ])

        writer.writerow([])
        writer.writerow(["Total Records:", data.get("total", 0)])

    def _write_aging_csv(self, writer: Any, data: Dict[str, Any], report_name: str) -> None:
        """Write aging report to CSV."""
        writer.writerow([f"{report_name} Aging Report"])
        writer.writerow([f"As of: {data.get('as_of_date', '')}"])
        writer.writerow([])

        # Headers depend on aging buckets
        buckets = data.get("buckets", ["Current", "1-30", "31-60", "61-90", "90+"])
        writer.writerow(["Party"] + buckets + ["Total"])

        for row in data.get("rows", []):
            amounts = [self._format_number(row.get(b, 0)) for b in buckets]
            writer.writerow([row.get("party", "")] + amounts + [self._format_number(row.get("total", 0))])

        writer.writerow([])
        # Summary row
        summary = data.get("summary", {})
        summary_amounts = [self._format_number(summary.get(b, 0)) for b in buckets]
        writer.writerow(["TOTAL"] + summary_amounts + [self._format_number(summary.get("total", 0))])

    def _generate_html(self, data: Dict[str, Any], report_type: str) -> str:
        """Generate HTML for PDF export using Jinja2 templates."""
        template_name = self.TEMPLATE_MAP.get(report_type)
        if not template_name:
            raise ExportError(f"Unknown report type: {report_type}")

        template = self.template_env.get_template(template_name)
        return template.render(
            data=data,
            company_name=self.company_name,
            now=datetime.now(),
        )

    def _format_number(self, value: Any) -> str:
        """Format number for display."""
        if value is None:
            return "0.00"
        if isinstance(value, (int, float, Decimal)):
            return f"{float(value):,.2f}"
        return str(value)
