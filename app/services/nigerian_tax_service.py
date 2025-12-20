"""
Nigerian Tax Administration Service Layer

Business logic for Nigerian tax compliance including:
- VAT tracking and filing
- WHT deduction and certificate generation
- PAYE calculation with progressive bands
- CIT assessment computation
- E-invoice generation (FIRS BIS 3.0)
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple, Any, cast
import uuid

from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tax_ng import (
    TaxSettings,
    NigerianTaxRate,
    VATTransaction,
    VATTransactionType,
    WHTTransaction,
    WHTCertificate,
    WHTPaymentType,
    PAYECalculation,
    CITAssessment,
    CITCompanySize,
    EInvoice,
    EInvoiceLine,
    EInvoiceStatus,
    TaxJurisdiction,
    NigerianTaxType,
)
from app.api.tax.helpers import (
    VAT_RATE,
    calculate_vat,
    get_vat_filing_deadline,
    get_wht_rate,
    calculate_wht,
    get_wht_remittance_deadline,
    calculate_cra,
    calculate_paye,
    calculate_employee_paye,
    get_cit_rate,
    calculate_cit,
    get_tax_filing_calendar,
    validate_tin,
)


class NigerianTaxService:
    """Service class for Nigerian tax operations."""

    def __init__(self, db: Session):
        self.db = db

    # ============= TAX SETTINGS =============

    def get_settings(self, company: str) -> Optional[TaxSettings]:
        """Get tax settings for a company."""
        return self.db.query(TaxSettings).filter(TaxSettings.company == company).first()

    def create_settings(self, data: Dict) -> TaxSettings:
        """Create tax settings for a company."""
        settings = TaxSettings(**data)
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update_settings(self, company: str, data: Dict) -> Optional[TaxSettings]:
        """Update tax settings."""
        settings = self.get_settings(company)
        if not settings:
            return None

        for key, value in data.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)

        self.db.commit()
        self.db.refresh(settings)
        return settings

    # ============= VAT OPERATIONS =============

    def _generate_vat_reference(self) -> str:
        """Generate unique VAT reference number."""
        today = date.today()
        unique_suffix = uuid.uuid4().hex[:8].upper()
        return f"VAT-{today.strftime('%Y%m%d')}-{unique_suffix}"

    def record_output_vat(
        self,
        company: str,
        transaction_date: date,
        party_name: str,
        party_tin: Optional[str],
        source_doctype: str,
        source_docname: str,
        taxable_amount: Decimal,
        vat_rate: Optional[Decimal] = None,
        party_id: Optional[int] = None,
        party_vat_number: Optional[str] = None,
        currency: str = "NGN",
        exchange_rate: Decimal = Decimal("1"),
        is_exempt: bool = False,
        is_zero_rated: bool = False,
        exemption_reason: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> VATTransaction:
        """Record output VAT (sales)."""
        rate = vat_rate or VAT_RATE
        if is_exempt or is_zero_rated:
            rate = Decimal("0")
            vat_amount = Decimal("0")
            total_amount = taxable_amount
        else:
            vat_amount, total_amount = calculate_vat(taxable_amount, rate)

        # Determine filing period
        filing_period = transaction_date.strftime("%Y-%m")

        transaction = VATTransaction(
            reference_number=self._generate_vat_reference(),
            transaction_type=VATTransactionType.OUTPUT,
            transaction_date=transaction_date,
            party_type="customer",
            party_id=party_id,
            party_name=party_name,
            party_tin=party_tin,
            party_vat_number=party_vat_number,
            source_doctype=source_doctype,
            source_docname=source_docname,
            taxable_amount=taxable_amount,
            vat_rate=rate,
            vat_amount=vat_amount,
            total_amount=total_amount,
            currency=currency,
            exchange_rate=exchange_rate,
            filing_period=filing_period,
            is_exempt=is_exempt,
            is_zero_rated=is_zero_rated,
            exemption_reason=exemption_reason,
            company=company,
            created_by_id=created_by_id,
        )

        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def record_input_vat(
        self,
        company: str,
        transaction_date: date,
        party_name: str,
        party_tin: Optional[str],
        source_doctype: str,
        source_docname: str,
        taxable_amount: Decimal,
        vat_rate: Optional[Decimal] = None,
        party_id: Optional[int] = None,
        party_vat_number: Optional[str] = None,
        currency: str = "NGN",
        exchange_rate: Decimal = Decimal("1"),
        is_exempt: bool = False,
        exemption_reason: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> VATTransaction:
        """Record input VAT (purchases)."""
        rate = vat_rate or VAT_RATE
        if is_exempt:
            rate = Decimal("0")
            vat_amount = Decimal("0")
            total_amount = taxable_amount
        else:
            vat_amount, total_amount = calculate_vat(taxable_amount, rate)

        filing_period = transaction_date.strftime("%Y-%m")

        transaction = VATTransaction(
            reference_number=self._generate_vat_reference(),
            transaction_type=VATTransactionType.INPUT,
            transaction_date=transaction_date,
            party_type="supplier",
            party_id=party_id,
            party_name=party_name,
            party_tin=party_tin,
            party_vat_number=party_vat_number,
            source_doctype=source_doctype,
            source_docname=source_docname,
            taxable_amount=taxable_amount,
            vat_rate=rate,
            vat_amount=vat_amount,
            total_amount=total_amount,
            currency=currency,
            exchange_rate=exchange_rate,
            filing_period=filing_period,
            is_exempt=is_exempt,
            exemption_reason=exemption_reason,
            company=company,
            created_by_id=created_by_id,
        )

        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def get_vat_transactions(
        self,
        company: str,
        period: Optional[str] = None,
        transaction_type: Optional[VATTransactionType] = None,
        is_filed: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[VATTransaction], int]:
        """Get VAT transactions with filters."""
        query = self.db.query(VATTransaction).filter(VATTransaction.company == company)

        if period:
            query = query.filter(VATTransaction.filing_period == period)
        if transaction_type:
            query = query.filter(VATTransaction.transaction_type == transaction_type)
        if is_filed is not None:
            query = query.filter(VATTransaction.is_filed == is_filed)

        total = query.count()
        transactions = query.order_by(VATTransaction.transaction_date.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()

        return transactions, total

    def get_vat_summary(self, company: str, period: str) -> Dict:
        """Get VAT summary for a period."""
        # Get output VAT (sales)
        output_result = self.db.query(
            func.coalesce(func.sum(VATTransaction.vat_amount), Decimal("0")).label("total"),
            func.count(VATTransaction.id).label("count")
        ).filter(
            VATTransaction.company == company,
            VATTransaction.filing_period == period,
            VATTransaction.transaction_type == VATTransactionType.OUTPUT,
            VATTransaction.is_exempt == False,
        ).first()

        # Get input VAT (purchases)
        input_result = self.db.query(
            func.coalesce(func.sum(VATTransaction.vat_amount), Decimal("0")).label("total"),
            func.count(VATTransaction.id).label("count")
        ).filter(
            VATTransaction.company == company,
            VATTransaction.filing_period == period,
            VATTransaction.transaction_type == VATTransactionType.INPUT,
            VATTransaction.is_exempt == False,
        ).first()

        output_vat = cast(Decimal, output_result._mapping["total"]) if output_result else Decimal("0")
        input_vat = cast(Decimal, input_result._mapping["total"]) if input_result else Decimal("0")
        output_count = int(output_result._mapping["count"]) if output_result else 0
        input_count = int(input_result._mapping["count"]) if input_result else 0

        # Check if filed
        filed_count = self.db.query(VATTransaction).filter(
            VATTransaction.company == company,
            VATTransaction.filing_period == period,
            VATTransaction.is_filed == True
        ).count()

        # Parse period for dates
        year, month = map(int, period.split("-"))
        from calendar import monthrange
        _, last_day = monthrange(year, month)

        return {
            "period": period,
            "period_start": date(year, month, 1),
            "period_end": date(year, month, last_day),
            "due_date": get_vat_filing_deadline(period),
            "output_vat": output_vat,
            "input_vat": input_vat,
            "net_vat_payable": output_vat - input_vat,
            "transaction_count": output_count + input_count,
            "is_filed": filed_count > 0,
            "company": company,
        }

    # ============= WHT OPERATIONS =============

    def _generate_wht_reference(self, suffix: Optional[str] = None) -> str:
        """Generate unique WHT reference number."""
        today = date.today()
        count = self.db.query(WHTTransaction).filter(
            func.date(WHTTransaction.created_at) == today
        ).count()
        base = f"WHT-{today.strftime('%Y%m%d')}-{count + 1:04d}"
        return f"{base}-{suffix}" if suffix else base

    def record_wht_deduction(
        self,
        company: str,
        transaction_date: date,
        payment_type: WHTPaymentType,
        supplier_name: str,
        gross_amount: Decimal,
        source_doctype: str,
        source_docname: str,
        supplier_id: Optional[int] = None,
        supplier_tin: Optional[str] = None,
        supplier_is_corporate: bool = True,
        jurisdiction: TaxJurisdiction = TaxJurisdiction.FEDERAL,
        currency: str = "NGN",
        exchange_rate: Decimal = Decimal("1"),
        created_by_id: Optional[int] = None,
    ) -> WHTTransaction:
        """Record WHT deduction from payment."""
        # Validate TIN if provided
        has_valid_tin = bool(supplier_tin and validate_tin(supplier_tin))

        # Get settings to check if TIN penalty applies
        settings = self.get_settings(company)
        apply_penalty = settings.apply_tin_penalty if settings else True

        # Calculate WHT
        rate, wht_amount, net_amount = calculate_wht(
            gross_amount,
            payment_type,
            supplier_is_corporate,
            has_valid_tin or not apply_penalty
        )

        # Get standard rate (without penalty)
        standard_rate = get_wht_rate(payment_type, supplier_is_corporate, True)

        # Calculate remittance deadline
        remittance_due = get_wht_remittance_deadline(transaction_date, jurisdiction)

        payload = {
            "transaction_date": transaction_date,
            "payment_type": payment_type,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_tin": supplier_tin,
            "supplier_is_corporate": supplier_is_corporate,
            "has_valid_tin": has_valid_tin,
            "source_doctype": source_doctype,
            "source_docname": source_docname,
            "gross_amount": gross_amount,
            "standard_rate": standard_rate,
            "wht_rate": rate,
            "wht_amount": wht_amount,
            "net_amount": net_amount,
            "currency": currency,
            "exchange_rate": exchange_rate,
            "jurisdiction": jurisdiction,
            "remittance_due_date": remittance_due,
            "company": company,
            "created_by_id": created_by_id,
        }

        for attempt in range(5):
            suffix = None if attempt == 0 else uuid.uuid4().hex[:6].upper()
            transaction = WHTTransaction(
                reference_number=self._generate_wht_reference(suffix),
                **payload,
            )
            self.db.add(transaction)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                continue
            self.db.refresh(transaction)
            return transaction

        raise ValueError("Unable to generate a unique WHT reference number")

    def get_wht_transactions(
        self,
        company: str,
        supplier_id: Optional[int] = None,
        is_remitted: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[WHTTransaction], int]:
        """Get WHT transactions with filters."""
        query = self.db.query(WHTTransaction).filter(WHTTransaction.company == company)

        if supplier_id:
            query = query.filter(WHTTransaction.supplier_id == supplier_id)
        if is_remitted is not None:
            query = query.filter(WHTTransaction.is_remitted == is_remitted)

        total = query.count()
        transactions = query.order_by(WHTTransaction.transaction_date.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()

        return transactions, total

    def get_supplier_wht_summary(self, company: str, supplier_id: int) -> Dict:
        """Get WHT summary for a supplier."""
        result = self.db.query(
            func.coalesce(func.sum(WHTTransaction.gross_amount), Decimal("0")).label("total_gross"),
            func.coalesce(func.sum(WHTTransaction.wht_amount), Decimal("0")).label("total_wht"),
            func.coalesce(func.sum(WHTTransaction.net_amount), Decimal("0")).label("total_net"),
            func.count(WHTTransaction.id).label("count"),
        ).filter(
            WHTTransaction.company == company,
            WHTTransaction.supplier_id == supplier_id,
        ).first()

        # Get supplier info
        supplier_txn = self.db.query(WHTTransaction).filter(
            WHTTransaction.company == company,
            WHTTransaction.supplier_id == supplier_id,
        ).first()

        # Count certificates
        cert_count = self.db.query(WHTCertificate).filter(
            WHTCertificate.company == company,
            WHTCertificate.supplier_id == supplier_id,
            WHTCertificate.is_issued == True,
        ).count()

        # Get uncertified amount
        uncertified = self.db.query(
            func.coalesce(func.sum(WHTTransaction.wht_amount), Decimal("0"))
        ).filter(
            WHTTransaction.company == company,
            WHTTransaction.supplier_id == supplier_id,
            WHTTransaction.certificate_id == None,
        ).scalar()

        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier_txn.supplier_name if supplier_txn else "",
            "supplier_tin": supplier_txn.supplier_tin if supplier_txn else None,
            "total_gross_amount": result.total_gross if result else Decimal("0"),
            "total_wht_deducted": result.total_wht if result else Decimal("0"),
            "total_net_paid": result.total_net if result else Decimal("0"),
            "transaction_count": result.count if result else 0,
            "certificates_issued": cert_count,
            "pending_certificate_amount": uncertified or Decimal("0"),
        }

    def get_wht_remittance_due(self, company: str) -> Dict:
        """Get pending WHT remittances."""
        today = date.today()
        week_from_now = today + __import__('datetime').timedelta(days=7)

        # Get all unremitted transactions
        transactions = self.db.query(WHTTransaction).filter(
            WHTTransaction.company == company,
            WHTTransaction.is_remitted == False,
        ).order_by(WHTTransaction.remittance_due_date).all()

        total_amount = sum(t.wht_amount for t in transactions)
        overdue = [t for t in transactions if t.remittance_due_date < today]
        due_this_week = [t for t in transactions if today <= t.remittance_due_date <= week_from_now]

        return {
            "transactions": transactions,
            "total_amount": total_amount,
            "overdue_count": len(overdue),
            "overdue_amount": sum(t.wht_amount for t in overdue),
            "due_this_week": len(due_this_week),
            "due_this_week_amount": sum(t.wht_amount for t in due_this_week),
        }

    def _generate_certificate_number(self, suffix: Optional[str] = None) -> str:
        """Generate unique WHT certificate number."""
        today = date.today()
        count = self.db.query(WHTCertificate).filter(
            func.extract('year', WHTCertificate.created_at) == today.year
        ).count()
        base = f"WHTC-{today.year}-{count + 1:06d}"
        return f"{base}-{suffix}" if suffix else base

    def generate_wht_certificate(
        self,
        company: str,
        supplier_id: int,
        period_start: date,
        period_end: date,
        created_by_id: Optional[int] = None,
    ) -> WHTCertificate:
        """Generate WHT credit certificate for supplier."""
        # Get uncertified transactions in period
        transactions = self.db.query(WHTTransaction).filter(
            WHTTransaction.company == company,
            WHTTransaction.supplier_id == supplier_id,
            WHTTransaction.certificate_id == None,
            WHTTransaction.transaction_date >= period_start,
            WHTTransaction.transaction_date <= period_end,
        ).all()

        if not transactions:
            raise ValueError("No uncertified transactions found for this period")

        # Calculate totals
        total_gross = sum(t.gross_amount for t in transactions)
        total_wht = sum(t.wht_amount for t in transactions)

        # Get settings for company details
        settings = self.get_settings(company)

        # Create certificate
        payload = {
            "issue_date": date.today(),
            "supplier_id": supplier_id,
            "supplier_name": transactions[0].supplier_name,
            "supplier_tin": transactions[0].supplier_tin,
            "period_start": period_start,
            "period_end": period_end,
            "total_gross_amount": total_gross,
            "total_wht_amount": total_wht,
            "transaction_count": len(transactions),
            "company": company,
            "company_tin": settings.tin if settings else None,
            "created_by_id": created_by_id,
        }

        for attempt in range(5):
            suffix = None if attempt == 0 else uuid.uuid4().hex[:6].upper()
            certificate = WHTCertificate(
                certificate_number=self._generate_certificate_number(suffix),
                **payload,
            )
            self.db.add(certificate)
            self.db.flush()

            for txn in transactions:
                txn.certificate_id = certificate.id

            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                continue
            self.db.refresh(certificate)
            return certificate

        raise ValueError("Unable to generate a unique WHT certificate number")

    # ============= PAYE OPERATIONS =============

    def calculate_employee_paye_full(
        self,
        company: str,
        employee_id: int,
        employee_name: str,
        payroll_period: str,
        period_start: date,
        period_end: date,
        basic_salary: Decimal,
        housing_allowance: Decimal = Decimal("0"),
        transport_allowance: Decimal = Decimal("0"),
        other_allowances: Decimal = Decimal("0"),
        bonus: Decimal = Decimal("0"),
        pension_contribution: Optional[Decimal] = None,
        nhf_contribution: Optional[Decimal] = None,
        life_assurance: Decimal = Decimal("0"),
        other_reliefs: Decimal = Decimal("0"),
        employee_tin: Optional[str] = None,
        state_of_residence: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> PAYECalculation:
        """Calculate and record PAYE for an employee."""
        # Calculate using helper
        result = calculate_employee_paye(
            basic_salary=basic_salary,
            housing_allowance=housing_allowance,
            transport_allowance=transport_allowance,
            other_allowances=other_allowances,
            bonus=bonus,
            pension_contribution=pension_contribution,
            nhf_contribution=nhf_contribution,
            life_assurance=life_assurance,
            other_reliefs=other_reliefs,
            tax_date=period_start,
        )

        gross_income = basic_salary + housing_allowance + transport_allowance + other_allowances + bonus
        annual_gross = gross_income * 12

        # Parse results
        reliefs = result["reliefs"]
        tax_calc = result["tax_calculation"]

        calculation = PAYECalculation(
            employee_id=employee_id,
            employee_name=employee_name,
            employee_tin=employee_tin,
            payroll_period=payroll_period,
            period_start=period_start,
            period_end=period_end,
            basic_salary=basic_salary,
            housing_allowance=housing_allowance,
            transport_allowance=transport_allowance,
            other_allowances=other_allowances,
            bonus=bonus,
            gross_income=gross_income,
            annual_gross_income=annual_gross,
            cra_fixed=Decimal(reliefs["cra_fixed"]),
            cra_percentage=Decimal(reliefs["cra_variable"]),
            total_cra=Decimal(reliefs["total_cra"]),
            pension_contribution=Decimal(reliefs["pension_contribution"]) / 12,
            nhf_contribution=Decimal(reliefs["nhf_contribution"]) / 12,
            life_assurance=life_assurance,
            other_reliefs=other_reliefs,
            total_reliefs=Decimal(reliefs["total_reliefs"]),
            annual_taxable_income=Decimal(tax_calc["annual_taxable_income"]),
            tax_bands_breakdown=tax_calc["tax_bands_breakdown"],
            annual_tax=Decimal(tax_calc["annual_tax"]),
            monthly_tax=Decimal(tax_calc["monthly_tax"]),
            effective_rate=Decimal(tax_calc["effective_rate"]),
            state_of_residence=state_of_residence,
            company=company,
            created_by_id=created_by_id,
        )

        self.db.add(calculation)
        self.db.commit()
        self.db.refresh(calculation)
        return calculation

    def get_paye_calculations(
        self,
        company: str,
        period: Optional[str] = None,
        employee_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[PAYECalculation], int]:
        """Get PAYE calculations with filters."""
        query = self.db.query(PAYECalculation).filter(PAYECalculation.company == company)

        if period:
            query = query.filter(PAYECalculation.payroll_period == period)
        if employee_id:
            query = query.filter(PAYECalculation.employee_id == employee_id)

        total = query.count()
        calculations = query.order_by(PAYECalculation.payroll_period.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()

        return calculations, total

    def get_paye_summary(self, company: str, period: str) -> Dict:
        """Get PAYE summary for a period."""
        result = self.db.query(
            func.count(PAYECalculation.id).label("count"),
            func.coalesce(func.sum(PAYECalculation.gross_income), Decimal("0")).label("total_gross"),
            func.coalesce(func.sum(PAYECalculation.monthly_tax), Decimal("0")).label("total_tax"),
        ).filter(
            PAYECalculation.company == company,
            PAYECalculation.payroll_period == period,
        ).first()

        filed_count = self.db.query(PAYECalculation).filter(
            PAYECalculation.company == company,
            PAYECalculation.payroll_period == period,
            PAYECalculation.is_filed == True,
        ).count()

        # Parse period for dates
        year, month = map(int, period.split("-"))
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        from app.api.tax.helpers import get_paye_filing_deadline

        return {
            "period": period,
            "period_start": date(year, month, 1),
            "period_end": date(year, month, last_day),
            "due_date": get_paye_filing_deadline(period),
            "employee_count": result.count if result else 0,
            "total_gross_income": result.total_gross if result else Decimal("0"),
            "total_tax": result.total_tax if result else Decimal("0"),
            "is_filed": filed_count > 0 and (result is not None and filed_count == result.count),
            "company": company,
        }

    # ============= CIT OPERATIONS =============

    def _generate_cit_assessment_number(self, fiscal_year: str, suffix: Optional[str] = None) -> str:
        """Generate CIT assessment number."""
        count = self.db.query(CITAssessment).filter(
            CITAssessment.fiscal_year == fiscal_year
        ).count()
        base = f"CIT-{fiscal_year}-{count + 1:04d}"
        return f"{base}-{suffix}" if suffix else base

    def create_cit_assessment(
        self,
        company: str,
        fiscal_year: str,
        period_start: date,
        period_end: date,
        gross_turnover: Decimal,
        gross_profit: Decimal,
        disallowed_expenses: Decimal = Decimal("0"),
        capital_allowances: Decimal = Decimal("0"),
        loss_brought_forward: Decimal = Decimal("0"),
        investment_allowances: Decimal = Decimal("0"),
        company_tin: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> CITAssessment:
        """Create CIT assessment."""
        # Determine company size
        cit_rate, company_size = get_cit_rate(gross_turnover)

        # Calculate adjusted profit
        adjusted_profit = gross_profit + disallowed_expenses - capital_allowances - investment_allowances
        assessable_profit = max(adjusted_profit - loss_brought_forward, Decimal("0"))

        # Calculate taxes
        _, cit_amount, tet_amount, total_tax, is_minimum_tax = calculate_cit(
            assessable_profit, gross_turnover
        )

        # Minimum tax
        from app.api.tax.helpers import MINIMUM_TAX_RATE
        minimum_tax = (gross_turnover * MINIMUM_TAX_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Due date (6 months after year end)
        due_date = date(period_end.year + 1, period_end.month, period_end.day)
        if due_date.month > 6:
            due_date = date(due_date.year + 1, due_date.month - 6, min(due_date.day, 28))
        else:
            due_date = date(due_date.year, due_date.month + 6, min(due_date.day, 28))

        payload = {
            "fiscal_year": fiscal_year,
            "period_start": period_start,
            "period_end": period_end,
            "company_size": company_size,
            "gross_turnover": gross_turnover,
            "gross_profit": gross_profit,
            "disallowed_expenses": disallowed_expenses,
            "capital_allowances": capital_allowances,
            "loss_brought_forward": loss_brought_forward,
            "investment_allowances": investment_allowances,
            "adjusted_profit": adjusted_profit,
            "assessable_profit": assessable_profit,
            "cit_rate": cit_rate,
            "cit_amount": cit_amount,
            "tet_rate": Decimal("0.03"),
            "tet_amount": tet_amount,
            "minimum_tax": minimum_tax,
            "is_minimum_tax_applicable": is_minimum_tax,
            "total_tax_liability": total_tax,
            "balance_due": total_tax,
            "due_date": due_date,
            "company": company,
            "company_tin": company_tin,
            "created_by_id": created_by_id,
        }

        for attempt in range(5):
            suffix = None if attempt == 0 else uuid.uuid4().hex[:6].upper()
            assessment = CITAssessment(
                assessment_number=self._generate_cit_assessment_number(fiscal_year, suffix),
                **payload,
            )
            self.db.add(assessment)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                continue
            self.db.refresh(assessment)
            return assessment

        raise ValueError("Unable to generate a unique CIT assessment number")

    def get_cit_assessments(
        self,
        company: str,
        fiscal_year: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[CITAssessment], int]:
        """Get CIT assessments."""
        query = self.db.query(CITAssessment).filter(CITAssessment.company == company)

        if fiscal_year:
            query = query.filter(CITAssessment.fiscal_year == fiscal_year)

        total = query.count()
        assessments = query.order_by(CITAssessment.fiscal_year.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()

        return assessments, total

    # ============= E-INVOICE OPERATIONS =============

    def _generate_invoice_uuid(self) -> str:
        """Generate UUID for e-invoice."""
        return str(uuid.uuid4())

    def _generate_invoice_number(self, company: str, suffix: Optional[str] = None) -> str:
        """Generate e-invoice number."""
        today = date.today()
        count = self.db.query(EInvoice).filter(
            EInvoice.company == company,
            func.extract('year', EInvoice.created_at) == today.year
        ).count()
        base = f"EINV-{today.year}-{count + 1:08d}"
        return f"{base}-{suffix}" if suffix else base

    def create_einvoice(
        self,
        company: str,
        source_doctype: str,
        source_docname: str,
        issue_date: date,
        supplier_name: str,
        customer_name: str,
        lines: List[Dict],
        due_date: Optional[date] = None,
        supplier_tin: Optional[str] = None,
        supplier_vat_number: Optional[str] = None,
        supplier_street: Optional[str] = None,
        supplier_city: Optional[str] = None,
        supplier_state: Optional[str] = None,
        supplier_phone: Optional[str] = None,
        supplier_email: Optional[str] = None,
        customer_tin: Optional[str] = None,
        customer_street: Optional[str] = None,
        customer_city: Optional[str] = None,
        customer_state: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        payment_means_code: Optional[str] = None,
        payment_terms: Optional[str] = None,
        note: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> EInvoice:
        """Create e-invoice for FIRS BIS 3.0 compliance."""
        # Calculate line totals
        line_extension = Decimal("0")
        total_tax = Decimal("0")

        invoice_lines = []
        for idx, line_data in enumerate(lines, 1):
            quantity = Decimal(str(line_data["quantity"]))
            unit_price = Decimal(str(line_data["unit_price"]))
            tax_rate = Decimal(str(line_data.get("tax_rate", "0.0750")))
            allowance = Decimal(str(line_data.get("allowance_amount", "0")))
            charge = Decimal(str(line_data.get("charge_amount", "0")))

            line_amount = (quantity * unit_price) - allowance + charge
            line_tax = (line_amount * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_total = line_amount + line_tax

            line_extension += line_amount
            total_tax += line_tax

            invoice_lines.append({
                "line_id": str(idx),
                "item_name": line_data["item_name"],
                "item_description": line_data.get("item_description"),
                "item_code": line_data.get("item_code"),
                "quantity": quantity,
                "unit_code": line_data.get("unit_code", "EA"),
                "unit_price": unit_price,
                "line_extension_amount": line_amount,
                "allowance_amount": allowance,
                "charge_amount": charge,
                "tax_rate": tax_rate,
                "tax_amount": line_tax,
                "total_amount": line_total,
            })

        tax_exclusive = line_extension
        tax_inclusive = line_extension + total_tax
        payable = tax_inclusive

        payload = {
            "issue_date": issue_date,
            "due_date": due_date,
            "source_doctype": source_doctype,
            "source_docname": source_docname,
            "supplier_name": supplier_name,
            "supplier_tin": supplier_tin,
            "supplier_vat_number": supplier_vat_number,
            "supplier_street": supplier_street,
            "supplier_city": supplier_city,
            "supplier_state": supplier_state,
            "supplier_phone": supplier_phone,
            "supplier_email": supplier_email,
            "customer_name": customer_name,
            "customer_tin": customer_tin,
            "customer_street": customer_street,
            "customer_city": customer_city,
            "customer_state": customer_state,
            "customer_phone": customer_phone,
            "customer_email": customer_email,
            "payment_means_code": payment_means_code,
            "payment_terms": payment_terms,
            "line_extension_amount": line_extension,
            "tax_exclusive_amount": tax_exclusive,
            "tax_inclusive_amount": tax_inclusive,
            "tax_amount": total_tax,
            "payable_amount": payable,
            "note": note,
            "company": company,
            "created_by_id": created_by_id,
        }

        for attempt in range(5):
            suffix = None if attempt == 0 else uuid.uuid4().hex[:6].upper()
            einvoice = EInvoice(
                invoice_number=self._generate_invoice_number(company, suffix),
                uuid=self._generate_invoice_uuid(),
                **payload,
            )

            self.db.add(einvoice)
            self.db.flush()

            for line_data in invoice_lines:
                line = EInvoiceLine(
                    einvoice_id=einvoice.id,
                    **line_data
                )
                self.db.add(line)

            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                continue
            self.db.refresh(einvoice)
            return einvoice

        raise ValueError("Unable to generate a unique e-invoice number")

    def validate_einvoice(self, einvoice_id: int) -> Dict:
        """Validate e-invoice against BIS 3.0 requirements."""
        einvoice = self.db.query(EInvoice).filter(EInvoice.id == einvoice_id).first()
        if not einvoice:
            raise ValueError("E-invoice not found")

        errors = []
        warnings = []

        # Required fields validation
        required_fields = [
            ("invoice_number", "Invoice number"),
            ("issue_date", "Issue date"),
            ("supplier_name", "Supplier name"),
            ("customer_name", "Customer name"),
        ]

        for field, label in required_fields:
            if not getattr(einvoice, field):
                errors.append({"field": field, "message": f"{label} is required"})

        # TIN validation
        if einvoice.supplier_tin and not validate_tin(einvoice.supplier_tin):
            errors.append({"field": "supplier_tin", "message": "Invalid supplier TIN format"})
        if einvoice.customer_tin and not validate_tin(einvoice.customer_tin):
            errors.append({"field": "customer_tin", "message": "Invalid customer TIN format"})

        # Line items validation
        if not einvoice.lines:
            errors.append({"field": "lines", "message": "At least one line item is required"})

        # Warnings
        if not einvoice.supplier_tin:
            warnings.append({"field": "supplier_tin", "message": "Supplier TIN is recommended"})
        if not einvoice.customer_tin:
            warnings.append({"field": "customer_tin", "message": "Customer TIN is recommended"})
        if not einvoice.supplier_vat_number:
            warnings.append({"field": "supplier_vat_number", "message": "VAT registration number is recommended"})

        is_valid = len(errors) == 0

        # Update status
        if is_valid:
            einvoice.status = EInvoiceStatus.VALIDATED
            einvoice.validated_at = datetime.utcnow()
        einvoice.validation_errors = errors if errors else None

        self.db.commit()

        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
        }

    def get_einvoice_ubl(self, einvoice_id: int) -> Dict:
        """Generate UBL XML structure for e-invoice."""
        einvoice = self.db.query(EInvoice).filter(EInvoice.id == einvoice_id).first()
        if not einvoice:
            raise ValueError("E-invoice not found")

        # Generate simple UBL structure (placeholder - full implementation would use proper XML library)
        ubl_structure = {
            "UBLVersionID": einvoice.ubl_version_id,
            "CustomizationID": einvoice.customization_id,
            "ProfileID": einvoice.profile_id,
            "ID": einvoice.invoice_number,
            "UUID": einvoice.uuid,
            "IssueDate": einvoice.issue_date.isoformat(),
            "DueDate": einvoice.due_date.isoformat() if einvoice.due_date else None,
            "InvoiceTypeCode": einvoice.invoice_type_code,
            "DocumentCurrencyCode": einvoice.document_currency_code,
            "AccountingSupplierParty": {
                "PartyName": einvoice.supplier_name,
                "PartyTaxScheme": {
                    "CompanyID": einvoice.supplier_tin,
                    "TaxScheme": {"ID": "VAT"}
                },
                "PostalAddress": {
                    "StreetName": einvoice.supplier_street,
                    "CityName": einvoice.supplier_city,
                    "CountrySubentity": einvoice.supplier_state,
                    "Country": {"IdentificationCode": einvoice.supplier_country_code}
                }
            },
            "AccountingCustomerParty": {
                "PartyName": einvoice.customer_name,
                "PartyTaxScheme": {
                    "CompanyID": einvoice.customer_tin,
                    "TaxScheme": {"ID": "VAT"}
                },
                "PostalAddress": {
                    "StreetName": einvoice.customer_street,
                    "CityName": einvoice.customer_city,
                    "CountrySubentity": einvoice.customer_state,
                    "Country": {"IdentificationCode": einvoice.customer_country_code}
                }
            },
            "TaxTotal": {
                "TaxAmount": str(einvoice.tax_amount),
                "TaxSubtotal": {
                    "TaxableAmount": str(einvoice.line_extension_amount),
                    "TaxAmount": str(einvoice.tax_amount),
                    "TaxCategory": {
                        "ID": einvoice.tax_category_code,
                        "Percent": str(einvoice.tax_rate * 100)
                    }
                }
            },
            "LegalMonetaryTotal": {
                "LineExtensionAmount": str(einvoice.line_extension_amount),
                "TaxExclusiveAmount": str(einvoice.tax_exclusive_amount),
                "TaxInclusiveAmount": str(einvoice.tax_inclusive_amount),
                "PayableAmount": str(einvoice.payable_amount)
            },
            "InvoiceLine": [
                {
                    "ID": line.line_id,
                    "InvoicedQuantity": str(line.quantity),
                    "LineExtensionAmount": str(line.line_extension_amount),
                    "Item": {
                        "Name": line.item_name,
                        "Description": line.item_description
                    },
                    "Price": {
                        "PriceAmount": str(line.unit_price)
                    }
                }
                for line in einvoice.lines
            ]
        }

        # Convert to XML string (simplified)
        import json
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
    <!-- FIRS BIS 3.0 E-Invoice -->
    <!-- Full UBL structure: {json.dumps(ubl_structure)} -->
</Invoice>"""

        return {
            "invoice_number": einvoice.invoice_number,
            "ubl_version": einvoice.ubl_version_id,
            "xml_content": xml_content,
            "qr_code_data": einvoice.qr_code_data,
        }

    # ============= DASHBOARD =============

    def get_dashboard_summary(self, company: str, period: str) -> Dict:
        """Get tax dashboard summary."""
        today = date.today()

        # VAT Summary
        vat_summary = self.get_vat_summary(company, period)

        # WHT Summary
        wht_result = self.db.query(
            func.coalesce(func.sum(WHTTransaction.wht_amount), Decimal("0"))
        ).filter(
            WHTTransaction.company == company,
            func.to_char(WHTTransaction.transaction_date, 'YYYY-MM') == period,
        ).scalar()

        wht_remitted = self.db.query(
            func.coalesce(func.sum(WHTTransaction.wht_amount), Decimal("0"))
        ).filter(
            WHTTransaction.company == company,
            func.to_char(WHTTransaction.transaction_date, 'YYYY-MM') == period,
            WHTTransaction.is_remitted == True,
        ).scalar()

        wht_overdue = self.db.query(WHTTransaction).filter(
            WHTTransaction.company == company,
            WHTTransaction.is_remitted == False,
            WHTTransaction.remittance_due_date < today,
        ).count()

        # PAYE Summary
        paye_summary = self.get_paye_summary(company, period)

        # CIT Summary (current year)
        year = period.split("-")[0]
        cit = self.db.query(CITAssessment).filter(
            CITAssessment.company == company,
            CITAssessment.fiscal_year == year,
        ).first()

        # Upcoming deadlines
        year_int = int(year)
        calendar = get_tax_filing_calendar(year_int)
        upcoming = [e for e in calendar if e["due_date"] >= today]
        next_deadline = upcoming[0]["due_date"] if upcoming else None
        month_int = int(period.split("-")[1])
        deadlines_this_month = len([
            e for e in calendar
            if e["due_date"].month == month_int and e["due_date"].year == year_int
        ])

        return {
            "company": company,
            "period": period,
            "vat_output": vat_summary["output_vat"],
            "vat_input": vat_summary["input_vat"],
            "vat_payable": vat_summary["net_vat_payable"],
            "vat_status": "filed" if vat_summary["is_filed"] else "pending",
            "wht_deducted": wht_result or Decimal("0"),
            "wht_remitted": wht_remitted or Decimal("0"),
            "wht_pending": (wht_result or Decimal("0")) - (wht_remitted or Decimal("0")),
            "wht_overdue_count": wht_overdue,
            "paye_calculated": paye_summary["total_tax"],
            "paye_remitted": Decimal("0"),  # Would need payment tracking
            "paye_pending": paye_summary["total_tax"],
            "employee_count": paye_summary["employee_count"],
            "cit_liability": cit.total_tax_liability if cit else None,
            "cit_paid": cit.amount_paid if cit else None,
            "cit_status": "filed" if cit and cit.is_filed else "pending" if cit else None,
            "next_deadline": next_deadline,
            "deadlines_this_month": deadlines_this_month,
        }
