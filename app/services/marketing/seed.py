"""Seed helpers for marketing defaults."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.marketing import EmailTemplate, JourneyTemplate


DEFAULT_JOURNEY_TEMPLATES = [
    {
        "name": "Welcome Onboarding",
        "category": "onboarding",
        "description": "Introduce new customers to key features and next steps.",
        "template_config": {
            "goal": "Activation",
            "steps": ["Welcome", "Tour", "Feature 1", "Feature 2", "Check-in"],
        },
    },
    {
        "name": "Lead Nurture",
        "category": "nurture",
        "description": "Educate leads and move them toward conversion.",
        "template_config": {
            "goal": "Conversion",
            "steps": ["Education", "Case Study", "Education 2", "Social Proof", "CTA"],
        },
    },
    {
        "name": "Re-engagement",
        "category": "reactivation",
        "description": "Bring inactive customers back with targeted offers.",
        "template_config": {
            "goal": "Reactivation",
            "steps": ["Miss You", "Special Offer", "Final Reminder"],
        },
    },
    {
        "name": "Feedback Collection",
        "category": "feedback",
        "description": "Request feedback and capture responses from customers.",
        "template_config": {
            "goal": "Feedback",
            "steps": ["Request", "Reminder", "Thank You"],
        },
    },
    {
        "name": "Upsell Sequence",
        "category": "promotional",
        "description": "Promote upgrades and drive repeat purchases.",
        "template_config": {
            "goal": "Upsell",
            "steps": ["Milestone", "Recommendation", "Offer", "Follow-up"],
        },
    },
]

DEFAULT_EMAIL_TEMPLATES = [
    {
        "name": "Welcome Email",
        "subject": "Welcome to DotMac BOS",
        "body_text": "Thanks for joining DotMac BOS. Here are your next steps...",
        "variables": ["first_name"],
    },
    {
        "name": "Feature Spotlight",
        "subject": "New feature: Faster reporting",
        "body_text": "Discover the latest reporting improvements and how to use them.",
        "variables": [],
    },
    {
        "name": "Re-engagement Offer",
        "subject": "We miss you at DotMac BOS",
        "body_text": "Here is a quick refresher and an exclusive offer.",
        "variables": ["first_name"],
    },
    {
        "name": "Customer Feedback",
        "subject": "Quick feedback on your experience",
        "body_text": "Tell us how we're doing. Your feedback helps us improve.",
        "variables": ["first_name"],
    },
    {
        "name": "Upsell Recommendation",
        "subject": "Upgrade options tailored for you",
        "body_text": "Explore add-ons and upgrades that fit your current plan.",
        "variables": ["first_name"],
    },
]


def seed_marketing_defaults(db: Session) -> dict:
    journey_count = db.query(JourneyTemplate).count()
    email_count = db.query(EmailTemplate).count()

    created_journeys = 0
    created_emails = 0

    if journey_count == 0:
        for item in DEFAULT_JOURNEY_TEMPLATES:
            db.add(JourneyTemplate(**item))
            created_journeys += 1

    if email_count == 0:
        for item in DEFAULT_EMAIL_TEMPLATES:
            db.add(EmailTemplate(**item))
            created_emails += 1

    if created_journeys or created_emails:
        db.commit()

    return {
        "journey_templates_created": created_journeys,
        "email_templates_created": created_emails,
    }
