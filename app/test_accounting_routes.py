"""Test accounting routes import."""
import sys
sys.path.insert(0, '/app')

# Test importing just the accounting routes module
try:
    from app.modules.accounting.routes._deps import templates, RequireAccountingRead
    print("_deps imports: OK")
except Exception as e:
    print(f"_deps imports: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.invoices import router as invoices_router
    print(f"invoices.py: OK ({len(invoices_router.routes)} routes)")
except Exception as e:
    print(f"invoices.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.payments import router as payments_router
    print(f"payments.py: OK ({len(payments_router.routes)} routes)")
except Exception as e:
    print(f"payments.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.accounts import router as accounts_router
    print(f"accounts.py: OK ({len(accounts_router.routes)} routes)")
except Exception as e:
    print(f"accounts.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.journal_entries import router as je_router
    print(f"journal_entries.py: OK ({len(je_router.routes)} routes)")
except Exception as e:
    print(f"journal_entries.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.general_ledger import router as gl_router
    print(f"general_ledger.py: OK ({len(gl_router.routes)} routes)")
except Exception as e:
    print(f"general_ledger.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.reports import router as reports_router
    print(f"reports.py: OK ({len(reports_router.routes)} routes)")
except Exception as e:
    print(f"reports.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.bank_accounts import router as bank_router
    print(f"bank_accounts.py: OK ({len(bank_router.routes)} routes)")
except Exception as e:
    print(f"bank_accounts.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.fiscal_periods import router as fp_router
    print(f"fiscal_periods.py: OK ({len(fp_router.routes)} routes)")
except Exception as e:
    print(f"fiscal_periods.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.aging import router as aging_router
    print(f"aging.py: OK ({len(aging_router.routes)} routes)")
except Exception as e:
    print(f"aging.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.suppliers import router as suppliers_router
    print(f"suppliers.py: OK ({len(suppliers_router.routes)} routes)")
except Exception as e:
    print(f"suppliers.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.cost_centers import router as cc_router
    print(f"cost_centers.py: OK ({len(cc_router.routes)} routes)")
except Exception as e:
    print(f"cost_centers.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.audit_log import router as audit_router
    print(f"audit_log.py: OK ({len(audit_router.routes)} routes)")
except Exception as e:
    print(f"audit_log.py: FAILED - {e}")
    sys.exit(1)

try:
    from app.modules.accounting.routes.approvals import router as approvals_router
    print(f"approvals.py: OK ({len(approvals_router.routes)} routes)")
except Exception as e:
    print(f"approvals.py: FAILED - {e}")
    sys.exit(1)

# Test the aggregator
try:
    from app.modules.accounting.routes import router
    print(f"\n__init__.py aggregator: OK (total {len(router.routes)} routes)")
except Exception as e:
    print(f"\n__init__.py aggregator: FAILED - {e}")
    sys.exit(1)

print("\nAll accounting routes modules imported successfully!")
