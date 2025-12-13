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
from typing import Dict, Any, List, Optional
from datetime import date, datetime
from decimal import Decimal

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

    def __init__(self):
        self.company_name = "dotMac Limited"  # Can be made configurable

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

        return pdf_bytes

    def _write_trial_balance_csv(self, writer: csv.writer, data: Dict[str, Any]) -> None:
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

    def _write_balance_sheet_csv(self, writer: csv.writer, data: Dict[str, Any]) -> None:
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

    def _write_income_statement_csv(self, writer: csv.writer, data: Dict[str, Any]) -> None:
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

    def _write_general_ledger_csv(self, writer: csv.writer, data: Dict[str, Any]) -> None:
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

    def _write_aging_csv(self, writer: csv.writer, data: Dict[str, Any], report_name: str) -> None:
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
        """Generate HTML for PDF export."""
        if report_type == "trial_balance":
            return self._trial_balance_html(data)
        elif report_type == "balance_sheet":
            return self._balance_sheet_html(data)
        elif report_type == "income_statement":
            return self._income_statement_html(data)
        elif report_type == "general_ledger":
            return self._general_ledger_html(data)
        elif report_type in ("receivables_aging", "payables_aging"):
            return self._aging_html(data, report_type)
        else:
            raise ExportError(f"Unknown report type: {report_type}")

    def _trial_balance_html(self, data: Dict[str, Any]) -> str:
        """Generate HTML for trial balance PDF."""
        rows = ""
        for acc in data.get("accounts", []):
            rows += f"""
            <tr>
                <td>{acc.get('account_name', '')}</td>
                <td>{acc.get('root_type', '')}</td>
                <td class="number">{self._format_number(acc.get('debit', 0))}</td>
                <td class="number">{self._format_number(acc.get('credit', 0))}</td>
                <td class="number">{self._format_number(acc.get('balance', 0))}</td>
            </tr>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Trial Balance</title>
        </head>
        <body>
            <div class="header">
                <h1>{self.company_name}</h1>
                <h2>Trial Balance</h2>
                <p>As of {data.get('as_of_date', '')}</p>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Account</th>
                        <th>Root Type</th>
                        <th>Debit</th>
                        <th>Credit</th>
                        <th>Balance</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
                <tfoot>
                    <tr class="total">
                        <td colspan="2">TOTAL</td>
                        <td class="number">{self._format_number(data.get('total_debit', 0))}</td>
                        <td class="number">{self._format_number(data.get('total_credit', 0))}</td>
                        <td class="number">{self._format_number(data.get('difference', 0))}</td>
                    </tr>
                </tfoot>
            </table>
            <div class="footer">
                <p>Balanced: {'Yes' if data.get('is_balanced') else 'No'}</p>
                <p class="generated">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        </body>
        </html>
        """

    def _balance_sheet_html(self, data: Dict[str, Any]) -> str:
        """Generate HTML for balance sheet PDF."""
        def section_rows(section_data: Dict, section_name: str) -> str:
            rows = f'<tr class="section-header"><td colspan="2">{section_name}</td></tr>'
            for acc in section_data.get("accounts", []):
                rows += f"""
                <tr>
                    <td class="indent">{acc.get('account', '')}</td>
                    <td class="number">{self._format_number(acc.get('balance', 0))}</td>
                </tr>
                """
            rows += f"""
            <tr class="subtotal">
                <td>Total {section_name}</td>
                <td class="number">{self._format_number(section_data.get('total', 0))}</td>
            </tr>
            """
            return rows

        assets_rows = section_rows(data.get("assets", {}), "Assets")
        liab_rows = section_rows(data.get("liabilities", {}), "Liabilities")
        equity_rows = section_rows(data.get("equity", {}), "Equity")

        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Balance Sheet</title></head>
        <body>
            <div class="header">
                <h1>{self.company_name}</h1>
                <h2>Balance Sheet</h2>
                <p>As of {data.get('as_of_date', '')}</p>
            </div>
            <table>
                <tbody>
                    {assets_rows}
                    <tr class="spacer"><td colspan="2"></td></tr>
                    {liab_rows}
                    <tr class="spacer"><td colspan="2"></td></tr>
                    {equity_rows}
                    <tr>
                        <td class="indent">Retained Earnings</td>
                        <td class="number">{self._format_number(data.get('retained_earnings', 0))}</td>
                    </tr>
                </tbody>
                <tfoot>
                    <tr class="total">
                        <td>Total Assets</td>
                        <td class="number">{self._format_number(data.get('total_assets', 0))}</td>
                    </tr>
                    <tr class="total">
                        <td>Total Liabilities + Equity</td>
                        <td class="number">{self._format_number(data.get('total_liabilities_equity', 0))}</td>
                    </tr>
                </tfoot>
            </table>
            <div class="footer">
                <p>Balanced: {'Yes' if data.get('is_balanced') else 'No'}</p>
                <p class="generated">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        </body>
        </html>
        """

    def _income_statement_html(self, data: Dict[str, Any]) -> str:
        """Generate HTML for income statement PDF."""
        period = data.get("period", {})

        def section_rows(section_data: Dict, section_name: str) -> str:
            rows = f'<tr class="section-header"><td colspan="2">{section_name}</td></tr>'
            for acc in section_data.get("accounts", []):
                rows += f"""
                <tr>
                    <td class="indent">{acc.get('account', '')}</td>
                    <td class="number">{self._format_number(acc.get('amount', 0))}</td>
                </tr>
                """
            rows += f"""
            <tr class="subtotal">
                <td>Total {section_name}</td>
                <td class="number">{self._format_number(section_data.get('total', 0))}</td>
            </tr>
            """
            return rows

        income_rows = section_rows(data.get("income", {}), "Income")
        expense_rows = section_rows(data.get("expenses", {}), "Expenses")

        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Income Statement</title></head>
        <body>
            <div class="header">
                <h1>{self.company_name}</h1>
                <h2>Income Statement</h2>
                <p>Period: {period.get('start_date', '')} to {period.get('end_date', '')}</p>
                <p>Basis: {data.get('basis', 'Accrual').title()}</p>
            </div>
            <table>
                <tbody>
                    {income_rows}
                    <tr class="spacer"><td colspan="2"></td></tr>
                    {expense_rows}
                </tbody>
                <tfoot>
                    <tr class="total">
                        <td>Gross Profit</td>
                        <td class="number">{self._format_number(data.get('gross_profit', 0))}</td>
                    </tr>
                    <tr class="total highlight">
                        <td>Net Income</td>
                        <td class="number">{self._format_number(data.get('net_income', 0))}</td>
                    </tr>
                    <tr>
                        <td>Profit Margin</td>
                        <td class="number">{data.get('profit_margin', 0):.2f}%</td>
                    </tr>
                </tfoot>
            </table>
            <div class="footer">
                <p class="generated">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        </body>
        </html>
        """

    def _general_ledger_html(self, data: Dict[str, Any]) -> str:
        """Generate HTML for general ledger PDF."""
        rows = ""
        for entry in data.get("entries", [])[:500]:  # Limit for PDF
            rows += f"""
            <tr>
                <td>{entry.get('posting_date', '')}</td>
                <td>{entry.get('account', '')[:30]}</td>
                <td>{entry.get('party', '') or ''}</td>
                <td class="number">{self._format_number(entry.get('debit', 0))}</td>
                <td class="number">{self._format_number(entry.get('credit', 0))}</td>
                <td>{entry.get('voucher_no', '')}</td>
            </tr>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>General Ledger</title></head>
        <body>
            <div class="header">
                <h1>{self.company_name}</h1>
                <h2>General Ledger</h2>
            </div>
            <table class="small-text">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Account</th>
                        <th>Party</th>
                        <th>Debit</th>
                        <th>Credit</th>
                        <th>Voucher</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
            <div class="footer">
                <p>Total Records: {data.get('total', 0)}</p>
                <p class="generated">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        </body>
        </html>
        """

    def _aging_html(self, data: Dict[str, Any], report_type: str) -> str:
        """Generate HTML for aging report PDF."""
        report_name = "Receivables" if "receivables" in report_type else "Payables"
        buckets = data.get("buckets", ["Current", "1-30", "31-60", "61-90", "90+"])

        header_cells = "".join(f"<th>{b}</th>" for b in buckets)

        rows = ""
        for row in data.get("rows", []):
            cells = "".join(f'<td class="number">{self._format_number(row.get(b, 0))}</td>' for b in buckets)
            rows += f"""
            <tr>
                <td>{row.get('party', '')}</td>
                {cells}
                <td class="number total-col">{self._format_number(row.get('total', 0))}</td>
            </tr>
            """

        summary = data.get("summary", {})
        summary_cells = "".join(f'<td class="number">{self._format_number(summary.get(b, 0))}</td>' for b in buckets)

        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>{report_name} Aging</title></head>
        <body>
            <div class="header">
                <h1>{self.company_name}</h1>
                <h2>{report_name} Aging Report</h2>
                <p>As of {data.get('as_of_date', '')}</p>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Party</th>
                        {header_cells}
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
                <tfoot>
                    <tr class="total">
                        <td>TOTAL</td>
                        {summary_cells}
                        <td class="number">{self._format_number(summary.get('total', 0))}</td>
                    </tr>
                </tfoot>
            </table>
            <div class="footer">
                <p class="generated">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        </body>
        </html>
        """

    def _get_report_css(self) -> str:
        """Get CSS styles for PDF reports."""
        return """
        @page {
            size: A4;
            margin: 1.5cm;
        }
        body {
            font-family: Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.4;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }
        .header h1 {
            font-size: 18pt;
            margin: 0 0 5px 0;
        }
        .header h2 {
            font-size: 14pt;
            margin: 0 0 5px 0;
            color: #555;
        }
        .header p {
            margin: 2px 0;
            color: #666;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            padding: 6px 8px;
            border: 1px solid #ddd;
            text-align: left;
        }
        th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        .number {
            text-align: right;
            font-family: 'Courier New', monospace;
        }
        .indent {
            padding-left: 20px;
        }
        .section-header {
            background-color: #e8e8e8;
            font-weight: bold;
        }
        .subtotal {
            font-weight: bold;
            background-color: #f9f9f9;
        }
        .total {
            font-weight: bold;
            background-color: #eee;
        }
        .highlight {
            background-color: #d4edda;
        }
        .spacer td {
            height: 10px;
            border: none;
        }
        .small-text {
            font-size: 8pt;
        }
        .footer {
            margin-top: 20px;
            border-top: 1px solid #ddd;
            padding-top: 10px;
        }
        .footer p {
            margin: 5px 0;
        }
        .generated {
            color: #999;
            font-size: 8pt;
            text-align: right;
        }
        .total-col {
            font-weight: bold;
        }
        """

    def _format_number(self, value: Any) -> str:
        """Format number for display."""
        if value is None:
            return "0.00"
        if isinstance(value, (int, float, Decimal)):
            return f"{float(value):,.2f}"
        return str(value)
