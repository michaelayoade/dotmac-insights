"""Nigerian Compliance Module.

Implements Nigerian statutory deduction calculations:
- PAYE (Pay As You Earn) - Personal Income Tax
- PENSION - Contributory Pension Scheme
- NHF (National Housing Fund)
- NHIS (National Health Insurance Scheme)
- NSITF (Nigeria Social Insurance Trust Fund)
- ITF (Industrial Training Fund)
"""
from app.services.hr.compliance.ng.module import NigerianComplianceModule

__all__ = ["NigerianComplianceModule"]
