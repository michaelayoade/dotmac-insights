"""
Notification Providers

Implementations for various notification delivery channels:
- Email (SMTP, SendGrid, Mailgun)
- SMS (Twilio, Termii, Africa's Talking)
- WhatsApp (Twilio WhatsApp, WhatsApp Business API)
- Push (Firebase Cloud Messaging)
"""
from __future__ import annotations

import os
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    """Result of a notification delivery attempt."""
    success: bool
    provider: str
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None


class NotificationProvider(ABC):
    """Base class for notification providers."""

    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        message: str,
        short_message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send notification and return result."""
        pass


# =============================================================================
# EMAIL PROVIDERS
# =============================================================================

class SMTPEmailProvider(NotificationProvider):
    """Send emails via SMTP."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.host = host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = port or int(os.getenv("SMTP_PORT", "587"))
        self.username = username or os.getenv("SMTP_USERNAME")
        self.password = password or os.getenv("SMTP_PASSWORD")
        self.from_email = from_email or os.getenv("SMTP_FROM_EMAIL", self.username)
        self.from_name = from_name or os.getenv("SMTP_FROM_NAME", "Notifications")
        self.use_tls = use_tls

    async def send(
        self,
        to: str,
        subject: str,
        message: str,
        short_message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send email via SMTP."""
        if not self.username or not self.password:
            return NotificationResult(
                success=False,
                provider="smtp",
                error_message="SMTP credentials not configured"
            )

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to

            # Plain text version
            text_part = MIMEText(message, "plain")
            msg.attach(text_part)

            # HTML version (simple conversion)
            html_message = message.replace("\n", "<br>\n")
            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                  {html_message}
                </div>
              </body>
            </html>
            """
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Connect and send
            context = ssl.create_default_context()
            with smtplib.SMTP(self.host, self.port) as server:
                if self.use_tls:
                    server.starttls(context=context)
                server.login(self.username, self.password)
                server.sendmail(self.from_email, to, msg.as_string())

            logger.info(f"Email sent successfully to {to}")
            return NotificationResult(
                success=True,
                provider="smtp",
            )

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return NotificationResult(
                success=False,
                provider="smtp",
                error_message=str(e)
            )


class SendGridProvider(NotificationProvider):
    """Send emails via SendGrid API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY")
        self.from_email = from_email or os.getenv("SENDGRID_FROM_EMAIL")
        self.from_name = from_name or os.getenv("SENDGRID_FROM_NAME", "Notifications")

    async def send(
        self,
        to: str,
        subject: str,
        message: str,
        short_message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send email via SendGrid."""
        if not self.api_key:
            return NotificationResult(
                success=False,
                provider="sendgrid",
                error_message="SendGrid API key not configured"
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "personalizations": [{"to": [{"email": to}]}],
                        "from": {
                            "email": self.from_email,
                            "name": self.from_name,
                        },
                        "subject": subject,
                        "content": [
                            {"type": "text/plain", "value": message},
                        ],
                    },
                )

                if response.status_code in [200, 202]:
                    message_id = response.headers.get("X-Message-Id")
                    return NotificationResult(
                        success=True,
                        provider="sendgrid",
                        external_id=message_id,
                    )
                else:
                    return NotificationResult(
                        success=False,
                        provider="sendgrid",
                        error_message=f"SendGrid error: {response.status_code} - {response.text}",
                    )

        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return NotificationResult(
                success=False,
                provider="sendgrid",
                error_message=str(e)
            )


# =============================================================================
# SMS PROVIDERS
# =============================================================================

class TwilioSMSProvider(NotificationProvider):
    """Send SMS via Twilio."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_FROM_NUMBER")

    async def send(
        self,
        to: str,
        subject: str,
        message: str,
        short_message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send SMS via Twilio."""
        if not all([self.account_sid, self.auth_token, self.from_number]):
            return NotificationResult(
                success=False,
                provider="twilio_sms",
                error_message="Twilio credentials not configured"
            )

        # Use short message for SMS
        sms_message = short_message or message[:160]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "To": to,
                        "From": self.from_number,
                        "Body": sms_message,
                    },
                )

                if response.status_code == 201:
                    data = response.json()
                    return NotificationResult(
                        success=True,
                        provider="twilio_sms",
                        external_id=data.get("sid"),
                        response_data=data,
                    )
                else:
                    return NotificationResult(
                        success=False,
                        provider="twilio_sms",
                        error_message=f"Twilio error: {response.status_code} - {response.text}",
                    )

        except Exception as e:
            logger.error(f"Twilio SMS error: {e}")
            return NotificationResult(
                success=False,
                provider="twilio_sms",
                error_message=str(e)
            )


class TermiiSMSProvider(NotificationProvider):
    """Send SMS via Termii (popular in Nigeria)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        sender_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("TERMII_API_KEY")
        self.sender_id = sender_id or os.getenv("TERMII_SENDER_ID", "N-Alert")

    async def send(
        self,
        to: str,
        subject: str,
        message: str,
        short_message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send SMS via Termii."""
        if not self.api_key:
            return NotificationResult(
                success=False,
                provider="termii",
                error_message="Termii API key not configured"
            )

        sms_message = short_message or message[:160]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.ng.termii.com/api/sms/send",
                    json={
                        "to": to,
                        "from": self.sender_id,
                        "sms": sms_message,
                        "type": "plain",
                        "channel": "generic",
                        "api_key": self.api_key,
                    },
                )

                data = response.json()
                if data.get("code") == "ok":
                    return NotificationResult(
                        success=True,
                        provider="termii",
                        external_id=data.get("message_id"),
                        response_data=data,
                    )
                else:
                    return NotificationResult(
                        success=False,
                        provider="termii",
                        error_message=data.get("message", "Unknown error"),
                    )

        except Exception as e:
            logger.error(f"Termii SMS error: {e}")
            return NotificationResult(
                success=False,
                provider="termii",
                error_message=str(e)
            )


# =============================================================================
# WHATSAPP PROVIDERS
# =============================================================================

class TwilioWhatsAppProvider(NotificationProvider):
    """Send WhatsApp messages via Twilio."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_WHATSAPP_NUMBER")

    async def send(
        self,
        to: str,
        subject: str,
        message: str,
        short_message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send WhatsApp message via Twilio."""
        if not all([self.account_sid, self.auth_token, self.from_number]):
            return NotificationResult(
                success=False,
                provider="twilio_whatsapp",
                error_message="Twilio WhatsApp credentials not configured"
            )

        # Format phone numbers for WhatsApp
        from_whatsapp = f"whatsapp:{self.from_number}"
        to_whatsapp = f"whatsapp:{to}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "To": to_whatsapp,
                        "From": from_whatsapp,
                        "Body": message,
                    },
                )

                if response.status_code == 201:
                    data = response.json()
                    return NotificationResult(
                        success=True,
                        provider="twilio_whatsapp",
                        external_id=data.get("sid"),
                        response_data=data,
                    )
                else:
                    return NotificationResult(
                        success=False,
                        provider="twilio_whatsapp",
                        error_message=f"Twilio WhatsApp error: {response.status_code}",
                    )

        except Exception as e:
            logger.error(f"Twilio WhatsApp error: {e}")
            return NotificationResult(
                success=False,
                provider="twilio_whatsapp",
                error_message=str(e)
            )


# =============================================================================
# PROVIDER FACTORY
# =============================================================================

def get_email_provider() -> NotificationProvider:
    """Get configured email provider."""
    provider = os.getenv("EMAIL_PROVIDER", "smtp").lower()

    if provider == "sendgrid":
        return SendGridProvider()
    else:
        return SMTPEmailProvider()


def get_sms_provider() -> NotificationProvider:
    """Get configured SMS provider."""
    provider = os.getenv("SMS_PROVIDER", "termii").lower()

    if provider == "twilio":
        return TwilioSMSProvider()
    else:
        return TermiiSMSProvider()


def get_whatsapp_provider() -> NotificationProvider:
    """Get configured WhatsApp provider."""
    return TwilioWhatsAppProvider()
