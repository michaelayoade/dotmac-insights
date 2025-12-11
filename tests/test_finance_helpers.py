"""Unit tests for finance helper utilities (currency resolution and date parsing)."""

import pytest
from fastapi import HTTPException
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.api import finance


def make_mock_session(distinct_values):
    """Create a fake SQLAlchemy session whose query().filter().all() returns distinct_values."""
    query = MagicMock()
    query.filter.return_value = query
    query.all.return_value = [(v,) for v in distinct_values]
    session = MagicMock()
    session.query.return_value = query
    return session


class TestParseIsoUtc:
    def test_parses_z_suffix_and_makes_aware(self):
        dt = finance._parse_iso_utc("2024-01-01T10:00:00Z", "start_date")
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None
        assert dt.tzinfo.utcoffset(dt) == timezone.utc.utcoffset(dt)

    def test_parses_naive_and_sets_utc(self):
        dt = finance._parse_iso_utc("2024-01-01T10:00:00", "start_date")
        assert dt.tzinfo is not None

    def test_invalid_date_raises_http_400(self):
        with pytest.raises(HTTPException) as exc:
            finance._parse_iso_utc("not-a-date", "start_date")
        assert exc.value.status_code == 400


class TestResolveCurrencyOrRaise:
    def test_returns_requested_currency_without_querying(self):
        session = MagicMock()
        result = finance._resolve_currency_or_raise(session, MagicMock(), "NGN")
        assert result == "NGN"
        session.query.assert_not_called()

    def test_returns_single_currency_when_only_one_present(self):
        session = make_mock_session(["NGN"])
        result = finance._resolve_currency_or_raise(session, MagicMock(), None)
        assert result == "NGN"

    def test_raises_when_multiple_currencies_without_param(self):
        session = make_mock_session(["NGN", "USD"])
        with pytest.raises(HTTPException) as exc:
            finance._resolve_currency_or_raise(session, MagicMock(), None)
        assert exc.value.status_code == 400
        assert "Multiple currencies detected" in exc.value.detail

