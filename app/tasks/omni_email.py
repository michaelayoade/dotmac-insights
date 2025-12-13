from __future__ import annotations

import imaplib
import email
from email.header import decode_header
from email.message import Message as EmailMessage
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.omni import (
    OmniChannel,
    OmniConversation,
    OmniParticipant,
    OmniMessage,
    OmniAttachment,
)
from app.models.agent import Agent
from app.worker import celery_app


def _decode_header_value(value: Optional[str]) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for text, enc in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            decoded.append(text)
    return "".join(decoded)


def _get_part_content(part: EmailMessage) -> Optional[str]:
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return None
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="ignore")
    except Exception:
        return None


def _extract_email_fields(msg: EmailMessage) -> Dict[str, Any]:
    subject = _decode_header_value(msg.get("Subject"))
    msg_id = msg.get("Message-ID")
    in_reply_to = msg.get("In-Reply-To")
    sender = email.utils.parseaddr(msg.get("From"))[1]

    text_body = None
    html_body = None
    attachments: List[Dict[str, Any]] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = (part.get("Content-Disposition") or "").lower()
            content_type = part.get_content_type()

            if "attachment" in content_disposition:
                filename = _decode_header_value(part.get_filename())
                payload = part.get_payload(decode=True)
                attachments.append(
                    {
                        "filename": filename,
                        "mime_type": content_type,
                        "size_bytes": len(payload) if payload else None,
                        "metadata": {
                            "content_id": part.get("Content-ID"),
                        },
                    }
                )
            elif content_type == "text/plain" and text_body is None:
                text_body = _get_part_content(part)
            elif content_type == "text/html" and html_body is None:
                html_body = _get_part_content(part)
    else:
        text_body = _get_part_content(msg)

    body = text_body or html_body or ""

    return {
        "subject": subject,
        "body": body,
        "sender": sender,
        "message_id": msg_id,
        "in_reply_to": in_reply_to,
        "attachments": attachments,
    }


def _get_or_create_participant(db: Session, handle: str, channel_type: str) -> OmniParticipant:
    participant = (
        db.query(OmniParticipant)
        .filter(OmniParticipant.handle == handle, OmniParticipant.channel_type == channel_type)
        .first()
    )
    if not participant:
        participant = OmniParticipant(
            handle=handle,
            channel_type=channel_type,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(participant)
        db.flush()
    return participant


def _get_or_create_conversation(db: Session, channel: OmniChannel, thread_id: Optional[str], subject: Optional[str]) -> OmniConversation:
    conv = None
    if thread_id:
        conv = (
            db.query(OmniConversation)
            .filter(
                OmniConversation.channel_id == channel.id,
                OmniConversation.external_thread_id == thread_id,
            )
            .first()
        )
    if not conv:
        conv = OmniConversation(
            channel_id=channel.id,
            external_thread_id=thread_id,
            subject=subject,
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(conv)
        db.flush()
    return conv


def _persist_message(
    db: Session,
    conversation: OmniConversation,
    participant: OmniParticipant,
    channel: OmniChannel,
    payload: Dict[str, Any],
) -> OmniMessage:
    msg = OmniMessage(
        conversation_id=conversation.id,
        direction="inbound",
        body=payload.get("body"),
        subject=payload.get("subject"),
        participant_id=participant.id,
        channel_id=channel.id,
        provider_message_id=payload.get("message_id"),
        meta={"in_reply_to": payload.get("in_reply_to")},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(msg)
    db.flush()

    for att in payload.get("attachments", []):
        attachment = OmniAttachment(
            message_id=msg.id,
            filename=att.get("filename"),
            mime_type=att.get("mime_type"),
            size_bytes=att.get("size_bytes"),
            meta=att.get("metadata"),
        )
        db.add(attachment)

    conversation.last_message_at = datetime.utcnow()
    return msg


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def poll_email_channel(self, channel_id: int):
    """Poll an IMAP inbox for new messages for a given channel."""
    db: Session = SessionLocal()
    try:
        channel = db.query(OmniChannel).filter(OmniChannel.id == channel_id, OmniChannel.is_active == True).first()
        if not channel:
            return
        cfg = channel.config or {}
        host = cfg.get("imap_host")
        port = int(cfg.get("imap_port") or 993)
        username = cfg.get("imap_username")
        password = cfg.get("imap_password")
        folder = cfg.get("imap_folder", "INBOX")
        use_ssl = cfg.get("imap_use_ssl", True)

        if not host or not username or not password:
            return

        if use_ssl:
            imap = imaplib.IMAP4_SSL(host, port)
        else:
            imap = imaplib.IMAP4(host, port)
        imap.login(username, password)
        imap.select(folder)

        # Fetch unseen emails
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            imap.logout()
            return

        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            raw_email = msg_data[0][1]
            email_msg = email.message_from_bytes(raw_email)
            payload = _extract_email_fields(email_msg)
            thread_id = payload.get("in_reply_to") or payload.get("message_id")

            participant = _get_or_create_participant(db, payload.get("sender") or "", channel.type)
            conv = _get_or_create_conversation(db, channel, thread_id, payload.get("subject"))
            _persist_message(db, conv, participant, channel, payload)

            # mark as seen
            imap.store(num, "+FLAGS", "\\Seen")

        imap.logout()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
