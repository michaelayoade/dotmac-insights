#!/usr/bin/env python3
"""
Nigeria Compliance Seeder Script

Seeds the generic payroll and tax configuration tables with Nigerian statutory
rules and rates. This script populates:

1. PayrollRegion - Nigeria region settings
2. DeductionRule - PAYE, Pension, NHF, NHIS, NSITF, ITF rules
3. TaxBand - PITA progressive tax bands (and NTA 2025 for future)
4. TaxRegion - Nigeria tax region
5. TaxCategory - VAT, WHT categories

Run this script AFTER:
- Migrations have been applied (alembic upgrade head)
- NIGERIA_COMPLIANCE_ENABLED feature flag is enabled for the tenant

Usage:
    python scripts/seed_nigeria_compliance.py [--dry-run]
"""

import sys
import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.payroll_config import (
    PayrollRegion,
    DeductionRule,
    TaxBand,
    CalcMethod,
    DeductionType,
    PayrollFrequency,
    RuleApplicability,
)
from app.models.tax_config import (
    TaxRegion,
    TaxCategory,
    TaxRate,
    TaxCategoryType,
    TaxFilingFrequency,
)


# ============= NIGERIA CONSTANTS =============

# Based on app/api/tax/helpers.py

# Pension rates (PFA 2014)
PENSION_EMPLOYEE_RATE = Decimal("0.08")  # 8%
PENSION_EMPLOYER_RATE = Decimal("0.10")  # 10%

# NHF (National Housing Fund)
NHF_RATE = Decimal("0.025")  # 2.5%

# NHIS (National Health Insurance Scheme)
NHIS_EMPLOYEE_RATE = Decimal("0.05")  # 5%
NHIS_EMPLOYER_RATE = Decimal("0.10")  # 10%

# NSITF (Nigeria Social Insurance Trust Fund)
NSITF_RATE = Decimal("0.01")  # 1%

# ITF (Industrial Training Fund)
ITF_RATE = Decimal("0.01")  # 1%

# VAT rate
VAT_RATE = Decimal("0.075")  # 7.5%

# WHT rates (corporate)
WHT_RATES = {
    "dividend": Decimal("0.10"),
    "interest": Decimal("0.10"),
    "rent": Decimal("0.10"),
    "royalty": Decimal("0.10"),
    "commission": Decimal("0.10"),
    "consultancy": Decimal("0.10"),
    "technical_service": Decimal("0.10"),
    "management_fee": Decimal("0.10"),
    "director_fee": Decimal("0.10"),
    "contract": Decimal("0.05"),
    "supply": Decimal("0.05"),
    "construction": Decimal("0.05"),
    "professional_fee": Decimal("0.05"),
    "hire_of_equipment": Decimal("0.10"),
}

# PAYE bands - PITA (current law until Dec 2025)
PAYE_BANDS_PITA = [
    (Decimal("0"), Decimal("300000"), Decimal("0.07")),       # First N300,000 @ 7%
    (Decimal("300000"), Decimal("600000"), Decimal("0.11")),  # Next N300,000 @ 11%
    (Decimal("600000"), Decimal("1100000"), Decimal("0.15")), # Next N500,000 @ 15%
    (Decimal("1100000"), Decimal("1600000"), Decimal("0.19")), # Next N500,000 @ 19%
    (Decimal("1600000"), Decimal("3200000"), Decimal("0.21")), # Next N1,600,000 @ 21%
    (Decimal("3200000"), None, Decimal("0.24")),              # Over N3,200,000 @ 24%
]

# PAYE bands - NTA 2025 (effective Jan 2026)
PAYE_BANDS_NTA_2025 = [
    (Decimal("0"), Decimal("800000"), Decimal("0.00")),        # First N800,000 @ 0% (tax-free)
    (Decimal("800000"), Decimal("1100000"), Decimal("0.15")),  # Next N300,000 @ 15%
    (Decimal("1100000"), Decimal("1600000"), Decimal("0.19")), # Next N500,000 @ 19%
    (Decimal("1600000"), Decimal("3200000"), Decimal("0.21")), # Next N1,600,000 @ 21%
    (Decimal("3200000"), None, Decimal("0.25")),              # Over N3,200,000 @ 25%
]


def seed_payroll_region(db: Session, dry_run: bool = False) -> PayrollRegion:
    """Seed Nigeria PayrollRegion."""
    existing = db.execute(
        select(PayrollRegion).where(PayrollRegion.code == "NG")
    ).scalar_one_or_none()

    if existing:
        print("  [SKIP] PayrollRegion 'NG' already exists")
        return existing

    region = PayrollRegion(
        code="NG",
        name="Nigeria",
        currency="NGN",
        default_pay_frequency=PayrollFrequency.MONTHLY,
        fiscal_year_start_month=1,
        payment_day=28,
        has_statutory_deductions=True,
        requires_compliance_addon=True,
        compliance_addon_code="NIGERIA_COMPLIANCE",
        tax_authority_name="Federal Inland Revenue Service (FIRS)",
        tax_id_label="TIN",
        tax_id_format=r"^\d{8,10}(-\d{4})?$",
        paye_filing_frequency="monthly",
        paye_filing_deadline_day=10,
        is_active=True,
    )

    if not dry_run:
        db.add(region)
        db.flush()
        print(f"  [CREATE] PayrollRegion 'NG' (id={region.id})")
    else:
        print("  [DRY-RUN] Would create PayrollRegion 'NG'")

    return region


def seed_deduction_rules(db: Session, region: PayrollRegion, dry_run: bool = False) -> list:
    """Seed Nigeria deduction rules."""
    rules = []
    effective_date = date(2020, 1, 1)  # Finance Act 2019 effective date

    rule_definitions = [
        # PAYE (Progressive tax)
        {
            "code": "PAYE",
            "name": "Pay As You Earn",
            "description": "Personal income tax calculated using progressive tax bands under PITA/NTA",
            "deduction_type": DeductionType.TAX,
            "applicability": RuleApplicability.EMPLOYEE,
            "is_statutory": True,
            "calc_method": CalcMethod.PROGRESSIVE,
            "base_components": ["basic", "housing", "transport", "other_allowances", "bonus"],
            "statutory_code": "PITA",
            "filing_frequency": "monthly",
            "remittance_deadline_days": 10,
            "display_order": 1,
        },
        # Pension Employee
        {
            "code": "PENSION_EE",
            "name": "Pension (Employee)",
            "description": "Employee pension contribution under Pension Reform Act 2014",
            "deduction_type": DeductionType.PENSION,
            "applicability": RuleApplicability.EMPLOYEE,
            "is_statutory": True,
            "calc_method": CalcMethod.PERCENTAGE,
            "rate": PENSION_EMPLOYEE_RATE,
            "base_components": ["basic", "housing", "transport"],
            "statutory_code": "PFA2014",
            "filing_frequency": "monthly",
            "remittance_deadline_days": 7,
            "display_order": 2,
        },
        # Pension Employer
        {
            "code": "PENSION_ER",
            "name": "Pension (Employer)",
            "description": "Employer pension contribution under Pension Reform Act 2014",
            "deduction_type": DeductionType.PENSION,
            "applicability": RuleApplicability.EMPLOYER,
            "is_statutory": True,
            "calc_method": CalcMethod.PERCENTAGE,
            "rate": PENSION_EMPLOYER_RATE,
            "base_components": ["basic", "housing", "transport"],
            "statutory_code": "PFA2014",
            "filing_frequency": "monthly",
            "remittance_deadline_days": 7,
            "display_order": 3,
        },
        # NHF
        {
            "code": "NHF",
            "name": "National Housing Fund",
            "description": "NHF contribution (voluntary for private sector)",
            "deduction_type": DeductionType.LEVY,
            "applicability": RuleApplicability.EMPLOYEE,
            "is_statutory": False,  # Voluntary for private sector
            "calc_method": CalcMethod.PERCENTAGE,
            "rate": NHF_RATE,
            "base_components": ["basic"],
            "statutory_code": "NHF_ACT",
            "filing_frequency": "monthly",
            "remittance_deadline_days": 10,
            "display_order": 4,
        },
        # NHIS Employee
        {
            "code": "NHIS_EE",
            "name": "NHIS (Employee)",
            "description": "National Health Insurance Scheme - Employee contribution",
            "deduction_type": DeductionType.INSURANCE,
            "applicability": RuleApplicability.EMPLOYEE,
            "is_statutory": True,
            "calc_method": CalcMethod.PERCENTAGE,
            "rate": NHIS_EMPLOYEE_RATE,
            "base_components": ["basic"],
            "statutory_code": "NHIS_ACT",
            "filing_frequency": "monthly",
            "remittance_deadline_days": 10,
            "display_order": 5,
        },
        # NHIS Employer
        {
            "code": "NHIS_ER",
            "name": "NHIS (Employer)",
            "description": "National Health Insurance Scheme - Employer contribution",
            "deduction_type": DeductionType.INSURANCE,
            "applicability": RuleApplicability.EMPLOYER,
            "is_statutory": True,
            "calc_method": CalcMethod.PERCENTAGE,
            "rate": NHIS_EMPLOYER_RATE,
            "base_components": ["basic"],
            "statutory_code": "NHIS_ACT",
            "filing_frequency": "monthly",
            "remittance_deadline_days": 10,
            "display_order": 6,
        },
        # NSITF
        {
            "code": "NSITF",
            "name": "NSITF (Employer)",
            "description": "Nigeria Social Insurance Trust Fund - Employer only",
            "deduction_type": DeductionType.INSURANCE,
            "applicability": RuleApplicability.EMPLOYER,
            "is_statutory": True,
            "calc_method": CalcMethod.PERCENTAGE,
            "rate": NSITF_RATE,
            "statutory_code": "NSITF_ACT",
            "filing_frequency": "monthly",
            "remittance_deadline_days": 10,
            "display_order": 7,
        },
        # ITF
        {
            "code": "ITF",
            "name": "Industrial Training Fund",
            "description": "ITF contribution - Employers with 5+ staff or N50M+ turnover",
            "deduction_type": DeductionType.LEVY,
            "applicability": RuleApplicability.EMPLOYER,
            "is_statutory": True,
            "calc_method": CalcMethod.PERCENTAGE,
            "rate": ITF_RATE,
            "statutory_code": "ITF_ACT",
            "filing_frequency": "annual",
            "remittance_deadline_days": 30,
            "display_order": 8,
        },
    ]

    for rule_def in rule_definitions:
        existing = db.execute(
            select(DeductionRule).where(
                DeductionRule.region_id == region.id,
                DeductionRule.code == rule_def["code"]
            )
        ).scalar_one_or_none()

        if existing:
            print(f"  [SKIP] DeductionRule '{rule_def['code']}' already exists")
            rules.append(existing)
            continue

        rule = DeductionRule(
            region_id=region.id,
            code=rule_def["code"],
            name=rule_def["name"],
            description=rule_def.get("description"),
            deduction_type=rule_def["deduction_type"],
            applicability=rule_def["applicability"],
            is_statutory=rule_def["is_statutory"],
            calc_method=rule_def["calc_method"],
            rate=rule_def.get("rate"),
            base_components=rule_def.get("base_components"),
            statutory_code=rule_def.get("statutory_code"),
            filing_frequency=rule_def.get("filing_frequency"),
            remittance_deadline_days=rule_def.get("remittance_deadline_days"),
            display_order=rule_def.get("display_order", 0),
            effective_from=effective_date,
            is_active=True,
        )

        if not dry_run:
            db.add(rule)
            db.flush()
            print(f"  [CREATE] DeductionRule '{rule_def['code']}' (id={rule.id})")
        else:
            print(f"  [DRY-RUN] Would create DeductionRule '{rule_def['code']}'")

        rules.append(rule)

    return rules


def seed_tax_bands(db: Session, paye_rule: DeductionRule, dry_run: bool = False) -> list:
    """Seed PITA progressive tax bands for PAYE."""
    bands = []

    # Check if bands already exist
    existing_count = db.execute(
        select(TaxBand).where(TaxBand.deduction_rule_id == paye_rule.id)
    ).scalars().all()

    if existing_count:
        print(f"  [SKIP] TaxBand entries already exist for PAYE rule (count={len(existing_count)})")
        return existing_count

    for idx, (lower, upper, rate) in enumerate(PAYE_BANDS_PITA):
        band = TaxBand(
            deduction_rule_id=paye_rule.id,
            lower_limit=lower,
            upper_limit=upper,
            rate=rate,
            band_order=idx,
        )

        if not dry_run:
            db.add(band)
            print(f"  [CREATE] TaxBand {lower}-{upper or 'unlimited'} @ {float(rate)*100:.0f}%")
        else:
            print(f"  [DRY-RUN] Would create TaxBand {lower}-{upper or 'unlimited'} @ {float(rate)*100:.0f}%")

        bands.append(band)

    if not dry_run:
        db.flush()

    return bands


def seed_tax_region(db: Session, dry_run: bool = False) -> TaxRegion:
    """Seed Nigeria TaxRegion."""
    existing = db.execute(
        select(TaxRegion).where(TaxRegion.code == "NG")
    ).scalar_one_or_none()

    if existing:
        print("  [SKIP] TaxRegion 'NG' already exists")
        return existing

    region = TaxRegion(
        code="NG",
        name="Nigeria",
        currency="NGN",
        tax_authority_name="Federal Inland Revenue Service (FIRS)",
        tax_authority_code="FIRS",
        tax_id_label="TIN",
        tax_id_format=r"^\d{8,10}(-\d{4})?$",
        default_sales_tax_rate=VAT_RATE,
        default_withholding_rate=Decimal("0.10"),  # Default WHT 10%
        default_filing_frequency=TaxFilingFrequency.MONTHLY,
        filing_deadline_day=21,  # VAT due 21st of following month
        fiscal_year_start_month=1,
        requires_compliance_addon=True,
        compliance_addon_code="NIGERIA_COMPLIANCE",
        is_active=True,
    )

    if not dry_run:
        db.add(region)
        db.flush()
        print(f"  [CREATE] TaxRegion 'NG' (id={region.id})")
    else:
        print("  [DRY-RUN] Would create TaxRegion 'NG'")

    return region


def seed_tax_categories(db: Session, region: TaxRegion, dry_run: bool = False) -> list:
    """Seed Nigeria tax categories (VAT, WHT)."""
    categories = []

    category_definitions = [
        {
            "code": "VAT",
            "name": "Value Added Tax",
            "description": "Nigerian VAT at 7.5% (effective Feb 2020)",
            "category_type": TaxCategoryType.SALES_TAX,
            "default_rate": VAT_RATE,
            "is_recoverable": True,
            "is_inclusive": False,
            "applies_to_purchases": True,
            "applies_to_sales": True,
            "filing_frequency": TaxFilingFrequency.MONTHLY,
            "filing_deadline_day": 21,
            "display_order": 1,
        },
        {
            "code": "WHT",
            "name": "Withholding Tax",
            "description": "Withholding tax deducted at source on qualifying payments",
            "category_type": TaxCategoryType.WITHHOLDING,
            "default_rate": Decimal("0.10"),  # Default 10%, varies by payment type
            "is_recoverable": False,
            "is_inclusive": False,
            "applies_to_purchases": True,
            "applies_to_sales": False,
            "filing_frequency": TaxFilingFrequency.MONTHLY,
            "filing_deadline_day": 21,
            "display_order": 2,
        },
        {
            "code": "CIT",
            "name": "Company Income Tax",
            "description": "Corporate income tax (0-30% based on turnover)",
            "category_type": TaxCategoryType.INCOME_TAX,
            "default_rate": Decimal("0.30"),  # Large company rate
            "is_recoverable": False,
            "is_inclusive": False,
            "applies_to_purchases": False,
            "applies_to_sales": False,
            "filing_frequency": TaxFilingFrequency.ANNUAL,
            "filing_deadline_day": 30,  # 6 months after year end
            "display_order": 3,
        },
        {
            "code": "STAMP_DUTY",
            "name": "Stamp Duty",
            "description": "Stamp duty on qualifying documents and transactions",
            "category_type": TaxCategoryType.STAMP_DUTY,
            "default_rate": Decimal("0.0075"),  # 0.75% for electronic transfers
            "is_recoverable": False,
            "is_inclusive": False,
            "applies_to_purchases": True,
            "applies_to_sales": True,
            "display_order": 4,
        },
    ]

    for cat_def in category_definitions:
        existing = db.execute(
            select(TaxCategory).where(
                TaxCategory.region_id == region.id,
                TaxCategory.code == cat_def["code"]
            )
        ).scalar_one_or_none()

        if existing:
            print(f"  [SKIP] TaxCategory '{cat_def['code']}' already exists")
            categories.append(existing)
            continue

        category = TaxCategory(
            region_id=region.id,
            code=cat_def["code"],
            name=cat_def["name"],
            description=cat_def.get("description"),
            category_type=cat_def["category_type"],
            default_rate=cat_def["default_rate"],
            is_recoverable=cat_def.get("is_recoverable", True),
            is_inclusive=cat_def.get("is_inclusive", False),
            applies_to_purchases=cat_def.get("applies_to_purchases", True),
            applies_to_sales=cat_def.get("applies_to_sales", True),
            filing_frequency=cat_def.get("filing_frequency"),
            filing_deadline_day=cat_def.get("filing_deadline_day"),
            display_order=cat_def.get("display_order", 0),
            is_active=True,
        )

        if not dry_run:
            db.add(category)
            db.flush()
            print(f"  [CREATE] TaxCategory '{cat_def['code']}' (id={category.id})")
        else:
            print(f"  [DRY-RUN] Would create TaxCategory '{cat_def['code']}'")

        categories.append(category)

    return categories


def seed_wht_rates(db: Session, wht_category: TaxCategory, dry_run: bool = False) -> list:
    """Seed WHT rate variations by payment type."""
    rates = []
    effective_date = date(2020, 1, 1)

    # Check if rates already exist
    existing = db.execute(
        select(TaxRate).where(TaxRate.category_id == wht_category.id)
    ).scalars().all()

    if existing:
        print(f"  [SKIP] TaxRate entries already exist for WHT category (count={len(existing)})")
        return existing

    for payment_type, rate in WHT_RATES.items():
        tax_rate = TaxRate(
            category_id=wht_category.id,
            code=f"WHT_{payment_type.upper()}",
            name=f"WHT - {payment_type.replace('_', ' ').title()}",
            rate=rate,
            conditions={"payment_type": payment_type, "is_corporate": True},
            effective_from=effective_date,
            is_active=True,
        )

        if not dry_run:
            db.add(tax_rate)
            print(f"  [CREATE] TaxRate WHT_{payment_type.upper()} @ {float(rate)*100:.0f}%")
        else:
            print(f"  [DRY-RUN] Would create TaxRate WHT_{payment_type.upper()} @ {float(rate)*100:.0f}%")

        rates.append(tax_rate)

    if not dry_run:
        db.flush()

    return rates


def main():
    parser = argparse.ArgumentParser(description="Seed Nigeria compliance data")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing")
    args = parser.parse_args()

    dry_run = args.dry_run

    print("=" * 60)
    print("Nigeria Compliance Seeder")
    print("=" * 60)

    if dry_run:
        print("\n[DRY-RUN MODE] No changes will be committed\n")

    db = SessionLocal()

    try:
        # 1. Seed PayrollRegion
        print("\n[1/6] Seeding PayrollRegion...")
        payroll_region = seed_payroll_region(db, dry_run)

        # 2. Seed DeductionRules
        print("\n[2/6] Seeding DeductionRules...")
        rules = seed_deduction_rules(db, payroll_region, dry_run)

        # 3. Seed TaxBands for PAYE
        print("\n[3/6] Seeding TaxBands (PITA)...")
        paye_rule = next((r for r in rules if r.code == "PAYE"), None)
        if paye_rule:
            seed_tax_bands(db, paye_rule, dry_run)
        else:
            print("  [ERROR] PAYE rule not found, skipping TaxBands")

        # 4. Seed TaxRegion
        print("\n[4/6] Seeding TaxRegion...")
        tax_region = seed_tax_region(db, dry_run)

        # 5. Seed TaxCategories
        print("\n[5/6] Seeding TaxCategories...")
        categories = seed_tax_categories(db, tax_region, dry_run)

        # 6. Seed WHT rates
        print("\n[6/6] Seeding WHT TaxRates...")
        wht_category = next((c for c in categories if c.code == "WHT"), None)
        if wht_category:
            seed_wht_rates(db, wht_category, dry_run)
        else:
            print("  [ERROR] WHT category not found, skipping TaxRates")

        if not dry_run:
            db.commit()
            print("\n" + "=" * 60)
            print("SUCCESS: Nigeria compliance data seeded successfully!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("DRY-RUN COMPLETE: Run without --dry-run to apply changes")
            print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
