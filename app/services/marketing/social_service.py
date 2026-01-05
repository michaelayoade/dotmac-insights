"""Social media service stubs for the Marketing module."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.models.marketing import SocialAccount, SocialPost, SocialPostStatus, SocialPlatform
from app.services.errors import NotFoundError
from app.services.validation.soft_validation_service import SoftValidationService


class SocialMediaService:
    """Provide social calendars, posts, and account data."""

    def __init__(self, db: Session):
        self.db = db

    def list_posts(self) -> List[Dict[str, Any]]:
        posts = (
            self.db.query(SocialPost, SocialAccount)
            .join(SocialAccount, SocialPost.account_id == SocialAccount.id)
            .order_by(SocialPost.created_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for post, account in posts:
            content = (post.content or "").strip()
            title = content.split(".")[0][:60] if content else "Social post"
            excerpt = content[:140] + "..." if len(content) > 140 else content
            results.append(
                {
                    "title": title,
                    "platforms": account.platform.value.replace("_", " ").title(),
                    "status": post.status.value,
                    "excerpt": excerpt,
                    "scheduled_at": _format_datetime(post.scheduled_at),
                    "owner": "Marketing Team",
                }
            )
        return results

    def list_accounts(self) -> List[Dict[str, Any]]:
        accounts = (
            self.db.query(SocialAccount)
            .order_by(SocialAccount.created_at.desc())
            .all()
        )
        results: List[Dict[str, Any]] = []
        for account in accounts:
            stats = account.stats or {}
            followers = stats.get("followers", 0)
            results.append(
                {
                    "platform": account.platform.value.replace("_", " ").title(),
                    "handle": account.display_name or account.account_id,
                    "followers": followers,
                    "status": "connected" if account.access_token_encrypted else "pending",
                    "last_synced": _format_datetime(account.updated_at),
                }
            )
        return results

    def list_calendar_days(self) -> List[Dict[str, Any]]:
        today = datetime.utcnow().date()
        days: List[Dict[str, Any]] = []
        for offset in range(5):
            day = today + timedelta(days=offset)
            days.append(
                {
                    "label": day.strftime("%a"),
                    "date": day.strftime("%b %d"),
                }
            )
        return days

    def list_calendar_posts(self) -> List[Dict[str, Any]]:
        posts = (
            self.db.query(SocialPost, SocialAccount)
            .join(SocialAccount, SocialPost.account_id == SocialAccount.id)
            .filter(SocialPost.status == SocialPostStatus.SCHEDULED)
            .order_by(SocialPost.scheduled_at.asc().nullslast())
            .limit(10)
            .all()
        )
        results: List[Dict[str, Any]] = []
        for post, account in posts:
            content = (post.content or "").strip()
            title = content.split(".")[0][:50] if content else "Scheduled post"
            results.append(
                {
                    "time": _format_time(post.scheduled_at),
                    "title": title,
                    "platforms": account.platform.value.replace("_", " ").title(),
                }
            )
        return results

    def get_account(self, account_id: int) -> SocialAccount:
        account = (
            self.db.query(SocialAccount)
            .filter(SocialAccount.id == account_id)
            .first()
        )
        if not account:
            raise NotFoundError("Social account not found")
        return account

    def create_account(self, data: Dict[str, Any]) -> SocialAccount:
        account = SocialAccount(
            platform=data.get("platform", SocialPlatform.FACEBOOK),
            account_id=data["account_id"],
            display_name=data.get("display_name"),
            profile_url=data.get("profile_url"),
            access_token_encrypted=data.get("access_token_encrypted"),
            refresh_token_encrypted=data.get("refresh_token_encrypted"),
            token_expires_at=data.get("token_expires_at"),
            stats=data.get("stats") or {},
        )
        self.db.add(account)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(account)
        return account

    def update_account(self, account_id: int, data: Dict[str, Any]) -> SocialAccount:
        account = self.get_account(account_id)
        for field in [
            "platform",
            "account_id",
            "display_name",
            "profile_url",
            "access_token_encrypted",
            "refresh_token_encrypted",
            "token_expires_at",
            "stats",
        ]:
            if field in data:
                setattr(account, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(account)
        return account

    def delete_account(self, account_id: int) -> None:
        account = self.get_account(account_id)
        self.db.delete(account)

    def get_post(self, post_id: int) -> SocialPost:
        post = (
            self.db.query(SocialPost)
            .filter(SocialPost.id == post_id)
            .first()
        )
        if not post:
            raise NotFoundError("Social post not found")
        return post

    def create_post(self, data: Dict[str, Any]) -> SocialPost:
        post = SocialPost(
            account_id=data["account_id"],
            content=data["content"],
            media_urls=data.get("media_urls") or [],
            scheduled_at=data.get("scheduled_at"),
            published_at=data.get("published_at"),
            status=data.get("status", SocialPostStatus.DRAFT),
            platform_post_id=data.get("platform_post_id"),
            metrics=data.get("metrics") or {},
            error=data.get("error"),
        )
        self.db.add(post)
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(post)
        return post

    def update_post(self, post_id: int, data: Dict[str, Any]) -> SocialPost:
        post = self.get_post(post_id)
        for field in [
            "account_id",
            "content",
            "media_urls",
            "scheduled_at",
            "published_at",
            "status",
            "platform_post_id",
            "metrics",
            "error",
        ]:
            if field in data:
                setattr(post, field, data[field])
        self.db.flush()
        SoftValidationService(self.db).validate_and_store(post)
        return post

    def delete_post(self, post_id: int) -> None:
        post = self.get_post(post_id)
        self.db.delete(post)


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "--"
    return value.strftime("%b %d, %Y")


def _format_time(value: datetime | None) -> str:
    if not value:
        return "--"
    return value.strftime("%I:%M %p").lstrip("0")
