"""
Unit tests for marketing background tasks.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.database import Base, SessionLocal, engine
from app.models.marketing import (
    CustomerJourney,
    EmailCampaign,
    EmailCampaignStatus,
    EmailSend,
    EmailSendStatus,
    EmailTemplate,
    JourneyEnrollment,
    JourneyEnrollmentStatus,
    JourneyStatus,
    JourneyStep,
    JourneyStepType,
    SocialAccount,
    SocialPlatform,
    SocialPost,
    SocialPostStatus,
)
from app.models.party import Party, PartyStatus, PartyType
from app.tasks.marketing_tasks import (
    process_journey_steps,
    publish_scheduled_posts,
    refresh_audience_segments,
    send_email_campaign_batch,
    sync_social_account_tokens,
    sync_social_metrics,
)


pytestmark = [pytest.mark.marketing]


@pytest.fixture(scope="module", autouse=True)
def setup_marketing_tables():
    Base.metadata.create_all(bind=engine)
    yield


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _create_party(db, name: str = "Test Party") -> Party:
    party = Party(
        type=PartyType.PERSON.value,
        status=PartyStatus.ACTIVE.value,
        name=name,
        primary_email="party@example.com",
    )
    db.add(party)
    db.commit()
    db.refresh(party)
    return party


def test_process_journey_steps_advances_enrollment():
    db = SessionLocal()
    party = _create_party(db, "Journey Party")

    journey = CustomerJourney(name="Test Journey", status=JourneyStatus.ACTIVE)
    db.add(journey)
    db.commit()
    db.refresh(journey)

    step_one = JourneyStep(
        journey_id=journey.id,
        step_order=1,
        step_type=JourneyStepType.EMAIL,
        delay_minutes=0,
    )
    step_two = JourneyStep(
        journey_id=journey.id,
        step_order=2,
        step_type=JourneyStepType.WAIT,
        delay_minutes=15,
    )
    db.add_all([step_one, step_two])
    db.commit()
    db.refresh(step_one)
    db.refresh(step_two)

    enrollment = JourneyEnrollment(
        journey_id=journey.id,
        party_id=party.id,
        status=JourneyEnrollmentStatus.ACTIVE,
        next_action_at=_utc_now() - timedelta(minutes=5),
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    db.close()

    result = process_journey_steps(batch_size=10)
    assert result["status"] == "success"

    db = SessionLocal()
    updated = db.query(JourneyEnrollment).filter(JourneyEnrollment.id == enrollment.id).first()
    assert updated.current_step_id == step_one.id
    assert updated.next_action_at is not None
    db.close()


def test_process_journey_steps_completes_final_step():
    db = SessionLocal()
    party = _create_party(db, "Journey Party 2")

    journey = CustomerJourney(name="Final Journey", status=JourneyStatus.ACTIVE)
    db.add(journey)
    db.commit()
    db.refresh(journey)

    step = JourneyStep(
        journey_id=journey.id,
        step_order=1,
        step_type=JourneyStepType.EMAIL,
        delay_minutes=0,
    )
    db.add(step)
    db.commit()
    db.refresh(step)

    enrollment = JourneyEnrollment(
        journey_id=journey.id,
        party_id=party.id,
        status=JourneyEnrollmentStatus.ACTIVE,
        current_step_id=step.id,
        next_action_at=_utc_now() - timedelta(minutes=1),
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    db.close()

    result = process_journey_steps(batch_size=10)
    assert result["status"] == "success"

    db = SessionLocal()
    updated = db.query(JourneyEnrollment).filter(JourneyEnrollment.id == enrollment.id).first()
    assert updated.status == JourneyEnrollmentStatus.COMPLETED
    assert updated.next_action_at is None
    db.close()


def test_publish_scheduled_posts_updates_status():
    db = SessionLocal()
    account = SocialAccount(
        platform=SocialPlatform.FACEBOOK,
        account_id="fb-001",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    post = SocialPost(
        account_id=account.id,
        content="Scheduled post",
        status=SocialPostStatus.SCHEDULED,
        scheduled_at=_utc_now() - timedelta(minutes=10),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    db.close()

    result = publish_scheduled_posts(batch_size=10)
    assert result["status"] == "success"

    db = SessionLocal()
    updated = db.query(SocialPost).filter(SocialPost.id == post.id).first()
    assert updated.status == SocialPostStatus.PUBLISHED
    assert updated.published_at is not None
    db.close()


def test_send_email_campaign_batch_marks_sent():
    db = SessionLocal()
    party = _create_party(db, "Email Party")

    template = EmailTemplate(name="Template", subject="Subject")
    db.add(template)
    db.commit()
    db.refresh(template)

    campaign = EmailCampaign(
        name="Email Campaign",
        template_id=template.id,
        status=EmailCampaignStatus.SCHEDULED,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    send = EmailSend(
        campaign_id=campaign.id,
        party_id=party.id,
        status=EmailSendStatus.QUEUED,
    )
    db.add(send)
    db.commit()
    db.refresh(send)
    db.close()

    result = send_email_campaign_batch(campaign_id=campaign.id, batch_size=10)
    assert result["status"] == "success"

    db = SessionLocal()
    updated_send = db.query(EmailSend).filter(EmailSend.id == send.id).first()
    updated_campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign.id).first()
    assert updated_send.status == EmailSendStatus.SENT
    assert updated_campaign.status == EmailCampaignStatus.SENDING
    db.close()


def test_sync_social_metrics_updates_timestamp():
    db = SessionLocal()
    account = SocialAccount(
        platform=SocialPlatform.TWITTER,
        account_id="tw-001",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    post = SocialPost(
        account_id=account.id,
        content="Published post",
        status=SocialPostStatus.PUBLISHED,
        published_at=_utc_now() - timedelta(minutes=5),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    db.close()

    result = sync_social_metrics(batch_size=10)
    assert result["status"] == "success"

    db = SessionLocal()
    updated = db.query(SocialPost).filter(SocialPost.id == post.id).first()
    assert updated.metrics.get("last_synced_at")
    db.close()


def test_refresh_audience_segments_returns_success():
    result = refresh_audience_segments()
    assert result["status"] == "success"


def test_sync_social_account_tokens_refreshes_expired():
    db = SessionLocal()
    account = SocialAccount(
        platform=SocialPlatform.LINKEDIN,
        account_id="li-001",
        token_expires_at=_utc_now() - timedelta(hours=1),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    db.close()


def test_send_email_campaign_batch_respects_send_window():
    db = SessionLocal()
    party = _create_party(db, "Window Party")

    template = EmailTemplate(name="Window Template", subject="Subject")
    db.add(template)
    db.commit()
    db.refresh(template)

    now = _utc_now()
    window_start = (now.hour + 1) % 24
    window_end = (now.hour + 2) % 24

    campaign = EmailCampaign(
        name="Window Campaign",
        template_id=template.id,
        status=EmailCampaignStatus.SCHEDULED,
        timezone="UTC",
        send_window_start=window_start,
        send_window_end=window_end,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    send = EmailSend(
        campaign_id=campaign.id,
        party_id=party.id,
        status=EmailSendStatus.QUEUED,
    )
    db.add(send)
    db.commit()
    db.refresh(send)
    db.close()

    result = send_email_campaign_batch(campaign_id=campaign.id, batch_size=10)
    assert result["status"] == "success"

    db = SessionLocal()
    updated = db.query(EmailSend).filter(EmailSend.id == send.id).first()
    assert updated.status == EmailSendStatus.QUEUED
    db.close()

    result = sync_social_account_tokens(batch_size=10)
    assert result["status"] == "success"

    db = SessionLocal()
    updated = db.query(SocialAccount).filter(SocialAccount.id == account.id).first()
    assert updated.token_expires_at is not None
    assert updated.token_expires_at > _utc_now()
    db.close()
