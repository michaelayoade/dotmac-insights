"""
Marketing SSR route tests.
"""
from __future__ import annotations

import pytest

from app.database import Base


pytestmark = [pytest.mark.integration, pytest.mark.marketing]


@pytest.fixture
def marketing_read_client(auth_client):
    return auth_client(["marketing:read"])


@pytest.fixture
def ensure_marketing_tables(integration_db):
    Base.metadata.create_all(bind=integration_db.get_bind())
    return integration_db


def test_marketing_pages_render(marketing_read_client, ensure_marketing_tables):
    routes = [
        "/marketing",
        "/marketing/campaigns",
        "/marketing/journeys",
        "/marketing/journeys/templates",
        "/marketing/journeys/1/builder",
        "/marketing/social/calendar",
        "/marketing/social/compose",
        "/marketing/social/posts",
        "/marketing/social/accounts",
        "/marketing/email/campaigns",
        "/marketing/email/templates",
        "/marketing/email/analytics",
        "/marketing/audiences",
        "/marketing/integrations",
        "/marketing/consent",
    ]

    for route in routes:
        response = marketing_read_client.get(route)
        assert response.status_code in [200, 302, 307]


def test_public_unsubscribe_page_renders(unauthenticated_client, ensure_marketing_tables):
    response = unauthenticated_client.get("/marketing/consent/unsubscribe")
    assert response.status_code == 200
