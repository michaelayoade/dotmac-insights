"""Service wrappers for accounting route write operations."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.accounting import (
    ApprovalsService,
    ARPaymentService,
    DocumentAttachmentService,
    FiscalService,
    JournalEntryService,
    PaymentModeService,
    PayablesService,
    TaxService,
)
from app.services.accounting.approvals_types import (
    ControlsUpdateData,
    WorkflowCreateData,
    WorkflowStepCreateData,
    WorkflowUpdateData,
)
from app.services.accounting.ar_payment_types import AllocationData, PaymentCreateData, PaymentUpdateData
from app.services.accounting.fiscal_types import CostCenterCreateData, CostCenterUpdateData
from app.services.accounting.journal_entry_types import JECreateData
from app.services.accounting.payment_modes_types import PaymentModeCreateData, PaymentModeUpdateData
from app.services.accounting.payables_types import SupplierCreateData, SupplierUpdateData
from app.services.accounting.tax_types import (
    TaxCodeCreateData,
    TaxCodeUpdateData,
    TaxFilingCreateData,
    TaxPaymentCreateData,
)
from app.services.accounting.attachments_types import AttachmentUploadData
from app.services.accounting.banking_types import BankAccountCreateData, BankAccountUpdateData
from app.services.accounting.payment_terms_types import PaymentTermsCreateData, PaymentTermsUpdateData
from app.services.accounting import BankingService, LedgerService, PaymentTermsService
from app.services.accounting.ledger_types import AccountCreateData, AccountUpdateData
from app.services.period_manager import PeriodManager


class AccountingTaxWebService:
    def __init__(self, db: Session, service: TaxService):
        self.db = db
        self.service = service

    def create_filing_period(self, data: TaxFilingCreateData, user_id: int):
        period = self.service.create_filing_period(data, user_id=user_id)
        self.db.commit()
        return period

    def record_payment(self, period_id: int, data: TaxPaymentCreateData, user_id: int) -> None:
        self.service.record_payment(period_id, data, user_id=user_id)
        self.db.commit()

    def file_period(self, period_id: int, user_id: int):
        period = self.service.file_period(period_id, user_id=user_id)
        self.db.commit()
        return period

    def create_tax_code(self, data: TaxCodeCreateData, user_id: int):
        tax_code = self.service.create_tax_code(data, user_id=user_id)
        self.db.commit()
        return tax_code

    def update_tax_code(self, tax_code_id: int, data: TaxCodeUpdateData):
        tax_code = self.service.update_tax_code(tax_code_id, data)
        self.db.commit()
        return tax_code

    def deactivate_tax_code(self, tax_code_id: int):
        tax_code = self.service.deactivate_tax_code(tax_code_id)
        self.db.commit()
        return tax_code

    def rollback(self) -> None:
        self.db.rollback()


class AccountingSuppliersWebService:
    def __init__(self, db: Session, service: PayablesService):
        self.db = db
        self.service = service

    def create_supplier(self, data: SupplierCreateData):
        supplier = self.service.create_supplier(data)
        self.db.commit()
        return supplier

    def update_supplier(self, supplier_id: int, data: SupplierUpdateData) -> None:
        self.service.update_supplier(supplier_id, data)
        self.db.commit()


class AccountingApprovalsWebService:
    def __init__(self, db: Session, service: ApprovalsService):
        self.db = db
        self.service = service

    def approve_document(self, doctype: str, document_id: int, user_id: int, remarks: str) -> None:
        self.service.approve_document(doctype, document_id, user_id, remarks)
        self.db.commit()

    def reject_document(self, doctype: str, document_id: int, user_id: int, remarks: str) -> None:
        self.service.reject_document(doctype, document_id, user_id, remarks)
        self.db.commit()

    def create_workflow(self, data: WorkflowCreateData, user_id: int):
        workflow = self.service.create_workflow(data, user_id)
        self.db.commit()
        return workflow

    def update_workflow(self, workflow_id: int, data: WorkflowUpdateData):
        workflow = self.service.update_workflow(workflow_id, data)
        self.db.commit()
        return workflow

    def toggle_workflow(self, workflow_id: int):
        workflow = self.service.toggle_workflow(workflow_id)
        self.db.commit()
        return workflow

    def add_step(self, workflow_id: int, data: WorkflowStepCreateData):
        step = self.service.add_step(workflow_id, data)
        self.db.commit()
        return step

    def delete_step(self, workflow_id: int, step_id: int) -> None:
        self.service.delete_step(workflow_id, step_id)
        self.db.commit()

    def update_controls(self, data: ControlsUpdateData, user_id: int) -> None:
        self.service.update_controls(data, user_id)
        self.db.commit()


class AccountingPaymentsWebService:
    def __init__(self, db: Session, service: ARPaymentService):
        self.db = db
        self.service = service

    def create_payment(self, data: PaymentCreateData):
        payment = self.service.create_payment(data)
        self.db.commit()
        return payment

    def update_payment(self, payment_id: int, data: PaymentUpdateData):
        payment = self.service.update_payment(payment_id, data)
        self.db.commit()
        return payment

    def add_allocations(self, payment_id: int, allocations: list[AllocationData]) -> None:
        self.service.add_allocations(payment_id, allocations)
        self.db.commit()

    def approve_payment(self, payment_id: int):
        payment = self.service.approve_payment(payment_id)
        self.db.commit()
        return payment

    def post_payment(self, payment_id: int):
        payment = self.service.post_payment(payment_id)
        self.db.commit()
        return payment


class AccountingJournalEntriesWebService:
    def __init__(self, db: Session, service: JournalEntryService):
        self.db = db
        self.service = service

    def create_entry(self, data: JECreateData):
        entry = self.service.create_entry(data)
        self.db.commit()
        return entry

    def update_entry_with_lines(self, entry_id: int, data: JECreateData):
        entry = self.service.update_entry_with_lines(entry_id, data)
        self.db.commit()
        return entry

    def post_entry(self, entry_id: int):
        entry = self.service.post_entry(entry_id)
        self.db.commit()
        return entry


class AccountingCostCentersWebService:
    def __init__(self, db: Session, service: FiscalService):
        self.db = db
        self.service = service

    def create_cost_center(self, data: CostCenterCreateData):
        center = self.service.create_cost_center(data)
        self.db.commit()
        return center

    def update_cost_center(self, center_id: int, data: CostCenterUpdateData):
        center = self.service.update_cost_center(center_id, data)
        self.db.commit()
        return center


class AccountingFiscalPeriodsWebService:
    def __init__(self, db: Session, service: FiscalService):
        self.db = db
        self.service = service

    def close_period(self, period_id: int, user_id: int, soft_close: bool = True) -> None:
        manager = PeriodManager(self.db)
        manager.close_period(period_id, user_id, soft_close=soft_close)
        self.db.commit()

    def reopen_period(self, period_id: int, user_id: int) -> None:
        manager = PeriodManager(self.db)
        manager.reopen_period(period_id, user_id)
        self.db.commit()


class AccountingPaymentModesWebService:
    def __init__(self, db: Session, service: PaymentModeService):
        self.db = db
        self.service = service

    def create_payment_mode(self, data: PaymentModeCreateData):
        mode = self.service.create_payment_mode(data)
        self.db.commit()
        return mode

    def update_payment_mode(self, mode_id: int, data: PaymentModeUpdateData):
        mode = self.service.update_payment_mode(mode_id, data)
        self.db.commit()
        return mode

    def disable_payment_mode(self, mode_id: int) -> None:
        self.service.disable_payment_mode(mode_id)
        self.db.commit()

    def enable_payment_mode(self, mode_id: int) -> None:
        self.service.enable_payment_mode(mode_id)
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def toggle_payment_mode(self, mode_id: int, is_enabled: bool):
        mode = self.service.toggle_payment_mode(mode_id, is_enabled)
        self.db.commit()
        return mode


class AccountingAccountsWebService:
    def __init__(self, db: Session, service: LedgerService):
        self.db = db
        self.service = service

    def create_account(self, data: AccountCreateData):
        account = self.service.create_account(data)
        self.db.commit()
        return account

    def update_account(self, account_id: int, data: AccountUpdateData) -> None:
        self.service.update_account(account_id, data)
        self.db.commit()


class AccountingBankAccountsWebService:
    def __init__(self, db: Session, service: BankingService):
        self.db = db
        self.service = service

    def create_bank_account(self, data: BankAccountCreateData):
        account = self.service.create_bank_account(data)
        self.db.commit()
        return account

    def update_bank_account(self, account_id: int, data: BankAccountUpdateData):
        account = self.service.update_bank_account(account_id, data)
        self.db.commit()
        return account

    def mark_transactions_reconciled(self, transaction_ids: list[int]) -> int:
        count = self.service.mark_transactions_reconciled(transaction_ids)
        self.db.commit()
        return count


class AccountingPaymentTermsWebService:
    def __init__(self, db: Session, service: PaymentTermsService):
        self.db = db
        self.service = service

    def create_payment_terms(self, data: PaymentTermsCreateData):
        terms = self.service.create_payment_terms(data)
        self.db.commit()
        return terms

    def update_payment_terms(self, terms_id: int, data: PaymentTermsUpdateData):
        terms = self.service.update_payment_terms(terms_id, data)
        self.db.commit()
        return terms

    def delete_payment_terms(self, terms_id: int) -> None:
        self.service.delete_payment_terms(terms_id)
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class AccountingAttachmentsWebService:
    def __init__(self, db: Session, service: DocumentAttachmentService):
        self.db = db
        self.service = service

    def create_attachment(self, data: AttachmentUploadData) -> None:
        self.service.create_attachment(data)
        self.db.commit()

    def delete_attachment(self, attachment_id: int) -> str:
        path = self.service.delete_attachment(attachment_id)
        self.db.commit()
        return path

    def set_primary(self, attachment_id: int) -> None:
        self.service.set_primary(attachment_id)
        self.db.commit()
