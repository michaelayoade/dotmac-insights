"""
Common dependencies for Nigerian tax endpoints.

We run single-tenant, so company context is fixed and not user-provided.
"""

from app.auth import Require

# Single-tenant company identifier. Could be extended to read from env/config.
SINGLE_COMPANY = "default"


async def get_single_company() -> str:
  """Return the fixed company scope for the single-tenant deployment."""
  return SINGLE_COMPANY


def require_tax_read():
  """Convenience dependency for read access."""
  return Require("books:read")


def require_tax_write():
  """Convenience dependency for write access."""
  return Require("books:write")
