"""
Marketing OAuth integration tests.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.database import Base
from app.services.marketing.integration_service import IntegrationService
from app.integrations.marketing import MetaBusinessClient, TwitterClient, LinkedInClient


pytestmark = [pytest.mark.integration, pytest.mark.marketing]


@pytest.fixture
def marketing_write_client(auth_client):
    return auth_client(["marketing:read", "marketing:write"])


@pytest.fixture
def ensure_marketing_tables(integration_db):
    Base.metadata.create_all(bind=integration_db.get_bind())
    return integration_db


@pytest.fixture
def integration_service(ensure_marketing_tables):
    return IntegrationService(ensure_marketing_tables)


def test_oauth_start_meta(marketing_write_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "meta_app_id", "meta-app")
    monkeypatch.setattr(settings, "meta_redirect_uri", "https://example.com/callback")

    response = marketing_write_client.post(
        "/api/v1/marketing/integrations/meta/oauth/start",
        json={"scopes": ["pages_show_list"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "authorization_url" in payload
    assert "facebook.com" in payload["authorization_url"]
    assert payload["state"]


def test_oauth_start_twitter_requires_challenge(marketing_write_client, ensure_marketing_tables, monkeypatch):
    monkeypatch.setattr(settings, "twitter_client_id", "tw-app")
    monkeypatch.setattr(settings, "twitter_redirect_uri", "https://example.com/callback")

    response = marketing_write_client.post(
        "/api/v1/marketing/integrations/twitter/oauth/start",
        json={},
    )
    assert response.status_code == 400

    response = marketing_write_client.post(
        "/api/v1/marketing/integrations/twitter/oauth/start",
        json={"code_challenge": "challenge"},
    )
    assert response.status_code == 200


def test_oauth_callback_meta_stores_credentials(
    marketing_write_client,
    integration_service,
    monkeypatch,
):
    monkeypatch.setattr(settings, "meta_app_id", "meta-app")
    monkeypatch.setattr(settings, "meta_app_secret", "meta-secret")
    monkeypatch.setattr(settings, "meta_redirect_uri", "https://example.com/callback")

    async def fake_exchange_code(self, code, redirect_uri=None):
        return {"access_token": "meta-token", "refresh_token": "meta-refresh", "expires_in": 3600}

    monkeypatch.setattr(MetaBusinessClient, "exchange_code", fake_exchange_code)

    start = marketing_write_client.post(
        "/api/v1/marketing/integrations/meta/oauth/start",
        json={},
    )
    assert start.status_code == 200
    state = start.json()["state"]

    response = marketing_write_client.post(
        "/api/v1/marketing/integrations/meta/oauth/callback",
        json={"code": "abc", "state": state},
    )
    assert response.status_code == 200

    integration = integration_service.get_or_create_by_type("meta")
    creds = integration_service.get_credentials(integration)
    assert creds.get("access_token") == "meta-token"


def test_oauth_refresh_meta_updates_credentials(
    marketing_write_client,
    integration_service,
    monkeypatch,
):
    monkeypatch.setattr(settings, "meta_app_id", "meta-app")
    monkeypatch.setattr(settings, "meta_app_secret", "meta-secret")
    monkeypatch.setattr(settings, "meta_redirect_uri", "https://example.com/callback")

    async def fake_refresh_access_token(self, access_token):
        return {"access_token": "new-token", "expires_in": 3600}

    monkeypatch.setattr(MetaBusinessClient, "refresh_access_token", fake_refresh_access_token)

    integration = integration_service.get_or_create_by_type("meta")
    integration_service.store_credentials(integration, {"access_token": "old-token"})

    response = marketing_write_client.post(
        "/api/v1/marketing/integrations/meta/oauth/refresh",
        json={"access_token": "old-token"},
    )
    assert response.status_code == 200

    creds = integration_service.get_credentials(integration)
    assert creds.get("access_token") == "new-token"


def test_oauth_callback_linkedin_stores_credentials(
    marketing_write_client,
    integration_service,
    monkeypatch,
):
    monkeypatch.setattr(settings, "linkedin_client_id", "li-app")
    monkeypatch.setattr(settings, "linkedin_client_secret", "li-secret")
    monkeypatch.setattr(settings, "linkedin_redirect_uri", "https://example.com/callback")

    async def fake_exchange_code(self, code, redirect_uri=None):
        return {"access_token": "li-token", "refresh_token": "li-refresh", "expires_in": 3600}

    monkeypatch.setattr(LinkedInClient, "exchange_code", fake_exchange_code)

    start = marketing_write_client.post(
        "/api/v1/marketing/integrations/linkedin/oauth/start",
        json={},
    )
    assert start.status_code == 200
    state = start.json()["state"]

    response = marketing_write_client.post(
        "/api/v1/marketing/integrations/linkedin/oauth/callback",
        json={"code": "abc", "state": state},
    )
    assert response.status_code == 200

    integration = integration_service.get_or_create_by_type("linkedin")
    creds = integration_service.get_credentials(integration)
    assert creds.get("access_token") == "li-token"


def test_oauth_callback_twitter_requires_verifier(
    marketing_write_client,
    ensure_marketing_tables,
    monkeypatch,
):
    monkeypatch.setattr(settings, "twitter_client_id", "tw-app")
    monkeypatch.setattr(settings, "twitter_client_secret", "tw-secret")
    monkeypatch.setattr(settings, "twitter_redirect_uri", "https://example.com/callback")

    async def fake_exchange_code(self, code, redirect_uri=None, code_verifier=None):
        return {"access_token": "tw-token", "refresh_token": "tw-refresh", "expires_in": 3600}

    monkeypatch.setattr(TwitterClient, "exchange_code", fake_exchange_code)

    start = marketing_write_client.post(
        "/api/v1/marketing/integrations/twitter/oauth/start",
        json={"code_challenge": "challenge"},
    )
    assert start.status_code == 200
    state = start.json()["state"]

    response = marketing_write_client.post(
        "/api/v1/marketing/integrations/twitter/oauth/callback",
        json={"code": "abc", "state": state},
    )
    assert response.status_code == 400
