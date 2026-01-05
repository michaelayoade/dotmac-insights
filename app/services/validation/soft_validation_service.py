"""Soft validation service for finance records."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Type

from sqlalchemy.orm import Session

from app.models.validation import FinanceValidationIssue, SoftValidationMixin
from app.validation.soft_validation import ValidationWarning, validate_instance


class SoftValidationService:
    """Run non-blocking validation and persist issues."""

    def __init__(self, db: Session, scope: str = "finance") -> None:
        self.db = db
        self.scope = scope

    def validate_instance(self, instance: Any) -> List[ValidationWarning]:
        return validate_instance(self.db, instance)

    def validate_and_store(self, instance: Any) -> List[ValidationWarning]:
        warnings = self.validate_instance(instance)
        self._store_issues(instance, warnings)
        return warnings

    def validate_records(
        self,
        models: Sequence[Type[Any]],
        record_ids: Optional[Sequence[int]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        summary = {"validated": 0, "issues": 0, "models": {}}
        for model in models:
            query = self.db.query(model)
            if record_ids:
                query = query.filter(model.id.in_(record_ids))
            if limit:
                query = query.limit(limit)
            rows = query.all()
            model_name = model.__name__
            model_issues = 0
            for row in rows:
                warnings = self.validate_and_store(row)
                model_issues += len(warnings)
            summary["validated"] += len(rows)
            summary["issues"] += model_issues
            summary["models"][model_name] = {"validated": len(rows), "issues": model_issues}
        return summary

    def _store_issues(self, instance: Any, warnings: List[ValidationWarning]) -> None:
        model_name = instance.__class__.__name__
        record_id = getattr(instance, "id", None)
        if record_id is None:
            return

        issues_payload = []
        detected_at = datetime.now(timezone.utc)
        for warning in warnings:
            issues_payload.append(
                {
                    "severity": warning.severity,
                    "code": warning.code,
                    "message": warning.message,
                    "field": warning.field,
                    "detected_at": detected_at.isoformat(),
                }
            )

        existing = (
            self.db.query(FinanceValidationIssue)
            .filter(
                FinanceValidationIssue.model_name == model_name,
                FinanceValidationIssue.record_id == record_id,
            )
            .first()
        )
        if existing:
            existing.issues = issues_payload
            existing.detected_at = detected_at
            existing.scope = self._scope_for_instance(instance)
        else:
            self.db.add(
                FinanceValidationIssue(
                    model_name=model_name,
                    record_id=record_id,
                    scope=self._scope_for_instance(instance),
                    issues=issues_payload,
                    detected_at=detected_at,
                )
            )

    def _scope_for_instance(self, instance: Any) -> str:
        if isinstance(instance, SoftValidationMixin):
            return instance.validation_scope
        return self.scope


def finance_models() -> List[Type[Any]]:
    from app.models.accounting import (
        JournalEntry,
        JournalEntryItem,
        PurchaseInvoice,
        GLEntry,
        Account,
        BankTransaction,
        BankTransactionPayment,
        BankReconciliation,
    )
    from app.models.invoice import Invoice
    from app.models.document_lines import InvoiceLine, BillLine
    from app.models.credit_note import CreditNote
    from app.models.books_settings import DebitNote
    from app.models.payment import Payment
    from app.models.payment_allocation import PaymentAllocation
    from app.models.supplier_payment import SupplierPayment
    from app.models.accounting_ext import ExchangeRate, FiscalPeriod
    from app.models.gateway_transaction import GatewayTransaction
    from app.models.payment_subscription import PaymentSubscription
    from app.models.tax import (
        TaxCode,
        TaxCategory,
        SalesTaxTemplate,
        SalesTaxTemplateDetail,
        PurchaseTaxTemplate,
        PurchaseTaxTemplateDetail,
        ItemTaxTemplate,
        ItemTaxTemplateDetail,
        TaxWithholdingCategory,
        TaxRule,
        TaxFilingPeriod,
        TaxPayment,
    )
    from app.models.tax_ng import (
        TaxSettings,
        NigerianTaxRate,
        VATTransaction,
        WHTTransaction,
        WHTCertificate,
        PAYECalculation,
        CITAssessment,
        EInvoice,
        EInvoiceLine,
    )
    from app.models.asset import (
        AssetCategory,
        AssetCategoryFinanceBook,
        Asset,
        AssetFinanceBook,
        AssetDepreciationSchedule,
    )
    from app.models.asset_settings import AssetSettings
    from app.models.bank_transaction_split import BankTransactionSplit
    from app.models.inventory import (
        Warehouse,
        StockEntry,
        StockEntryDetail,
        StockLedgerEntry,
        LandedCostVoucher,
        LandedCostItem,
        LandedCostTax,
        StockReceipt,
        StockReceiptItem,
        StockIssue,
        StockIssueItem,
        TransferRequest,
        TransferRequestItem,
        Batch,
        SerialNumber,
    )
    from app.models.sales import Item, ItemGroup

    return [
        Invoice,
        InvoiceLine,
        PurchaseInvoice,
        BillLine,
        CreditNote,
        DebitNote,
        Payment,
        SupplierPayment,
        PaymentAllocation,
        BankTransaction,
        BankTransactionPayment,
        BankReconciliation,
        JournalEntry,
        JournalEntryItem,
        GLEntry,
        Account,
        ExchangeRate,
        FiscalPeriod,
        GatewayTransaction,
        PaymentSubscription,
        TaxCode,
        TaxCategory,
        SalesTaxTemplate,
        SalesTaxTemplateDetail,
        PurchaseTaxTemplate,
        PurchaseTaxTemplateDetail,
        ItemTaxTemplate,
        ItemTaxTemplateDetail,
        TaxWithholdingCategory,
        TaxRule,
        TaxFilingPeriod,
        TaxPayment,
        TaxSettings,
        NigerianTaxRate,
        VATTransaction,
        WHTTransaction,
        WHTCertificate,
        PAYECalculation,
        CITAssessment,
        EInvoice,
        EInvoiceLine,
        AssetCategory,
        AssetCategoryFinanceBook,
        Asset,
        AssetFinanceBook,
        AssetDepreciationSchedule,
        AssetSettings,
        BankTransactionSplit,
        Item,
        ItemGroup,
        Warehouse,
        StockEntry,
        StockEntryDetail,
        StockLedgerEntry,
        LandedCostVoucher,
        LandedCostItem,
        LandedCostTax,
        StockReceipt,
        StockReceiptItem,
        StockIssue,
        StockIssueItem,
        TransferRequest,
        TransferRequestItem,
        Batch,
        SerialNumber,
    ]


def omnichannel_models() -> List[Type[Any]]:
    from app.models.omni import (
        OmniChannel,
        OmniConversation,
        OmniParticipant,
        OmniMessage,
        OmniAttachment,
        OmniWebhookEvent,
        InboxRoutingRule,
        InboxContact,
    )

    return [
        OmniChannel,
        OmniConversation,
        OmniParticipant,
        OmniMessage,
        OmniAttachment,
        OmniWebhookEvent,
        InboxRoutingRule,
        InboxContact,
    ]


def marketing_models() -> List[Type[Any]]:
    from app.models.marketing import (
        MarketingCampaign,
        JourneyTemplate,
        CustomerJourney,
        JourneyStep,
        JourneyEnrollment,
        SocialAccount,
        SocialPost,
        EmailTemplate,
        EmailCampaign,
        EmailSend,
        MarketingAudience,
        MarketingIntegration,
        MarketingConsent,
        SuppressionEntry,
        MarketingWebhookEvent,
    )

    return [
        MarketingCampaign,
        JourneyTemplate,
        CustomerJourney,
        JourneyStep,
        JourneyEnrollment,
        SocialAccount,
        SocialPost,
        EmailTemplate,
        EmailCampaign,
        EmailSend,
        MarketingAudience,
        MarketingIntegration,
        MarketingConsent,
        SuppressionEntry,
        MarketingWebhookEvent,
    ]
