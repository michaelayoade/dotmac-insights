"""
Nigerian Tax Administration Module

A comprehensive tax management module for Nigerian tax compliance including:
- VAT (Value Added Tax) - 7.5% standard rate
- WHT (Withholding Tax) - Variable rates by payment type
- PAYE (Pay As You Earn) - Progressive 7-24% bands
- CIT (Company Income Tax) - 0-30% based on company size
- E-Invoicing (FIRS BIS 3.0 UBL format)

Key Features:
- Automatic rate calculation based on Nigerian tax law
- TIN validation with 2x penalty for non-compliance
- Filing calendar and deadline tracking
- WHT certificate generation
- E-invoice preparation for FIRS compliance
"""

from fastapi import APIRouter, Depends
from app.api.tax.deps import require_tax_read

from app.api.tax.vat import router as vat_router
from app.api.tax.withholding import router as wht_router
from app.api.tax.paye import router as paye_router
from app.api.tax.cit import router as cit_router
from app.api.tax.filing import router as filing_router
from app.api.tax.dashboard import router as dashboard_router
from app.api.tax.certificates import router as certificates_router
from app.api.tax.einvoicing import router as einvoice_router
from app.api.tax.settings import router as settings_router
from app.api.tax.payroll_integration import router as payroll_tax_router

# Apply a base read guard to all tax endpoints
router = APIRouter(dependencies=[Depends(require_tax_read())])

# Include all sub-routers
router.include_router(vat_router)
router.include_router(wht_router)
router.include_router(paye_router)
router.include_router(cit_router)
router.include_router(filing_router)
router.include_router(dashboard_router)
router.include_router(certificates_router)
router.include_router(einvoice_router)
router.include_router(settings_router)
router.include_router(payroll_tax_router)  # HR payroll integration

__all__ = ["router"]
