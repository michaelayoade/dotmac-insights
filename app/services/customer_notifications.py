"""
Customer Notification Service

Sends notifications to customers about all activities related to them:
- Service orders (scheduled, dispatched, completed, etc.)
- Support tickets (created, updated, resolved)
- Projects (started, milestones, completed)
- Invoices and payments

Supports multiple channels: email, SMS, WhatsApp, push notifications.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.field_service import (
    CustomerNotification,
    CustomerNotificationType,
    CustomerNotificationChannel,
    CustomerNotificationStatus,
    CustomerNotificationPreference,
    ServiceOrder,
    ServiceOrderStatus,
)
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.project import Project
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)


# =============================================================================
# MESSAGE TEMPLATES
# =============================================================================

NOTIFICATION_TEMPLATES: Dict[CustomerNotificationType, Dict[str, str]] = {
    # Service Order Templates
    CustomerNotificationType.SERVICE_SCHEDULED: {
        "title": "Service Scheduled: {order_type}",
        "message": """Dear {customer_name},

Your {order_type} service has been scheduled.

Order: #{order_number}
Date: {scheduled_date}
Time: {scheduled_time}
Address: {service_address}

Description: {title}

Our team will arrive at the scheduled time. Please ensure someone is available to provide access.

If you need to reschedule, please contact us as soon as possible.

Thank you for choosing us!""",
        "short": "Service scheduled for {scheduled_date} at {scheduled_time}. Order #{order_number}",
    },

    CustomerNotificationType.SERVICE_RESCHEDULED: {
        "title": "Service Rescheduled: {order_type}",
        "message": """Dear {customer_name},

Your service order #{order_number} has been rescheduled.

New Date: {scheduled_date}
New Time: {scheduled_time}
Address: {service_address}

Reason: {notes}

We apologize for any inconvenience. Please contact us if this new time doesn't work for you.

Thank you for your understanding.""",
        "short": "Service rescheduled to {scheduled_date} at {scheduled_time}. Order #{order_number}",
    },

    CustomerNotificationType.TECHNICIAN_ASSIGNED: {
        "title": "Technician Assigned: {order_type}",
        "message": """Dear {customer_name},

A technician has been assigned to your service order #{order_number}.

Technician: {technician_name}
Scheduled Date: {scheduled_date}
Scheduled Time: {scheduled_time}

Your technician will contact you if needed before the appointment.

Thank you!""",
        "short": "{technician_name} assigned to your service. {scheduled_date}",
    },

    CustomerNotificationType.TECHNICIAN_EN_ROUTE: {
        "title": "Technician On The Way!",
        "message": """Dear {customer_name},

Great news! Your technician {technician_name} is on the way to your location.

Order: #{order_number}
Estimated Arrival: {eta}
Address: {service_address}

Please ensure someone is available to provide access.

You can track their progress or contact them if needed.""",
        "short": "{technician_name} is on the way! ETA: {eta}",
    },

    CustomerNotificationType.TECHNICIAN_ARRIVED: {
        "title": "Technician Has Arrived",
        "message": """Dear {customer_name},

Your technician {technician_name} has arrived at your location.

Order: #{order_number}
Arrival Time: {arrival_time}

The service work will begin shortly.""",
        "short": "{technician_name} has arrived for your service.",
    },

    CustomerNotificationType.SERVICE_STARTED: {
        "title": "Service Work Started",
        "message": """Dear {customer_name},

Your {order_type} service has started.

Order: #{order_number}
Started: {start_time}
Technician: {technician_name}

Estimated Duration: {estimated_duration}

We'll notify you when the work is complete.""",
        "short": "Service started. Estimated completion: {estimated_duration}",
    },

    CustomerNotificationType.SERVICE_COMPLETED: {
        "title": "Service Completed Successfully",
        "message": """Dear {customer_name},

Your {order_type} service has been completed successfully!

Order: #{order_number}
Completed: {end_time}
Duration: {actual_duration}

Work Performed:
{work_performed}

{resolution_notes}

We hope you're satisfied with our service. Please let us know if you have any questions or concerns.

Thank you for your business!""",
        "short": "Service completed! Order #{order_number}. Thank you!",
    },

    CustomerNotificationType.SERVICE_CANCELLED: {
        "title": "Service Cancelled",
        "message": """Dear {customer_name},

Your service order #{order_number} has been cancelled.

Reason: {notes}

If you did not request this cancellation or have any questions, please contact us immediately.

We apologize for any inconvenience.""",
        "short": "Service #{order_number} cancelled. Contact us with questions.",
    },

    CustomerNotificationType.SERVICE_DELAYED: {
        "title": "Service Delay Notice",
        "message": """Dear {customer_name},

We regret to inform you that your service order #{order_number} is experiencing a delay.

Reason: {notes}
New Estimated Time: {eta}

We sincerely apologize for the inconvenience. Our team is working to complete your service as soon as possible.

Thank you for your patience and understanding.""",
        "short": "Service delayed. New ETA: {eta}. We apologize for the inconvenience.",
    },

    # Ticket Templates
    CustomerNotificationType.TICKET_CREATED: {
        "title": "Support Ticket Created: #{ticket_id}",
        "message": """Dear {customer_name},

Your support ticket has been created and our team will review it shortly.

Ticket: #{ticket_id}
Subject: {subject}
Priority: {priority}

We'll get back to you as soon as possible. You can track your ticket status in your account.

Thank you for contacting us!""",
        "short": "Ticket #{ticket_id} created. We'll respond soon.",
    },

    CustomerNotificationType.TICKET_UPDATED: {
        "title": "Ticket Update: #{ticket_id}",
        "message": """Dear {customer_name},

Your support ticket has been updated.

Ticket: #{ticket_id}
Status: {status}

{notes}

Thank you for your patience.""",
        "short": "Ticket #{ticket_id} updated. Status: {status}",
    },

    CustomerNotificationType.TICKET_REPLY: {
        "title": "New Reply on Ticket #{ticket_id}",
        "message": """Dear {customer_name},

You have a new reply on your support ticket.

Ticket: #{ticket_id}
Subject: {subject}

Reply:
{reply}

Please log in to your account to view the full conversation and respond.

Thank you!""",
        "short": "New reply on ticket #{ticket_id}. Check your account.",
    },

    CustomerNotificationType.TICKET_RESOLVED: {
        "title": "Ticket Resolved: #{ticket_id}",
        "message": """Dear {customer_name},

Your support ticket has been resolved.

Ticket: #{ticket_id}
Subject: {subject}
Resolution: {resolution}

If you're satisfied with the resolution, no action is needed. If you have any remaining concerns, please reply to this ticket or create a new one.

Thank you for your patience!""",
        "short": "Ticket #{ticket_id} resolved. Thank you!",
    },

    # Project Templates
    CustomerNotificationType.PROJECT_STARTED: {
        "title": "Project Started: {project_name}",
        "message": """Dear {customer_name},

Your project has officially started!

Project: {project_name}
Start Date: {start_date}
Expected Completion: {expected_end_date}
Project Manager: {project_manager}

We're excited to begin work on your project. You'll receive regular updates on our progress.

Thank you for your trust in us!""",
        "short": "Project '{project_name}' has started. Expected completion: {expected_end_date}",
    },

    CustomerNotificationType.PROJECT_MILESTONE: {
        "title": "Project Milestone: {milestone_name}",
        "message": """Dear {customer_name},

We're pleased to inform you that a milestone has been reached on your project.

Project: {project_name}
Milestone: {milestone_name}
Completion: {completion}%

{notes}

We're making great progress! Thank you for your continued partnership.""",
        "short": "Project milestone reached: {milestone_name} ({completion}%)",
    },

    CustomerNotificationType.PROJECT_COMPLETED: {
        "title": "Project Completed: {project_name}",
        "message": """Dear {customer_name},

Congratulations! Your project has been successfully completed.

Project: {project_name}
Completion Date: {end_date}

{summary}

We hope you're pleased with the results. Please don't hesitate to contact us if you have any questions or need further assistance.

Thank you for choosing us for your project!""",
        "short": "Project '{project_name}' completed! Thank you for your business.",
    },

    # Invoice Templates
    CustomerNotificationType.INVOICE_GENERATED: {
        "title": "New Invoice: #{invoice_number}",
        "message": """Dear {customer_name},

A new invoice has been generated for your account.

Invoice: #{invoice_number}
Amount: {amount}
Due Date: {due_date}

{description}

Please ensure payment is made by the due date to avoid any service interruptions.

Thank you for your business!""",
        "short": "Invoice #{invoice_number} for {amount} due {due_date}",
    },

    CustomerNotificationType.PAYMENT_RECEIVED: {
        "title": "Payment Received: Thank You!",
        "message": """Dear {customer_name},

Thank you! We've received your payment.

Amount: {amount}
Reference: {reference}
Invoice: #{invoice_number}

Your account is now up to date. Thank you for your prompt payment!""",
        "short": "Payment of {amount} received. Thank you!",
    },

    CustomerNotificationType.PAYMENT_DUE: {
        "title": "Payment Due Reminder: #{invoice_number}",
        "message": """Dear {customer_name},

This is a friendly reminder that payment for your invoice is due soon.

Invoice: #{invoice_number}
Amount: {amount}
Due Date: {due_date}
Days Until Due: {days_until_due}

Please ensure payment is made by the due date to avoid any service interruptions.

If you've already made the payment, please disregard this notice.

Thank you!""",
        "short": "Payment reminder: {amount} due {due_date} for invoice #{invoice_number}",
    },
}


# =============================================================================
# NOTIFICATION SERVICE
# =============================================================================

class CustomerNotificationService:
    """Service for creating and sending customer notifications."""

    def __init__(self, db: Session):
        self.db = db

    def get_customer_preferences(
        self,
        customer_id: int,
        notification_type: CustomerNotificationType
    ) -> Dict[str, bool]:
        """Get customer's notification preferences for a given type."""
        pref = self.db.query(CustomerNotificationPreference).filter(
            CustomerNotificationPreference.customer_id == customer_id,
            CustomerNotificationPreference.notification_type == notification_type
        ).first()

        if pref:
            return {
                "email": pref.email_enabled,
                "sms": pref.sms_enabled,
                "whatsapp": pref.whatsapp_enabled,
                "push": pref.push_enabled,
            }

        # Default preferences if not set
        return {
            "email": True,
            "sms": False,
            "whatsapp": False,
            "push": True,
        }

    def format_message(
        self,
        notification_type: CustomerNotificationType,
        data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Format notification message using template."""
        template = NOTIFICATION_TEMPLATES.get(notification_type, {
            "title": "Notification",
            "message": str(data),
            "short": "You have a new notification",
        })

        # Replace placeholders with data
        title = template["title"]
        message = template["message"]
        short = template.get("short", template["title"])

        for key, value in data.items():
            placeholder = "{" + key + "}"
            str_value = str(value) if value is not None else ""
            title = title.replace(placeholder, str_value)
            message = message.replace(placeholder, str_value)
            short = short.replace(placeholder, str_value)

        return {
            "title": title,
            "message": message,
            "short": short,
        }

    def create_notification(
        self,
        customer_id: int,
        notification_type: CustomerNotificationType,
        data: Dict[str, Any],
        channel: CustomerNotificationChannel = CustomerNotificationChannel.EMAIL,
        service_order_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
        project_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        schedule_at: Optional[datetime] = None,
    ) -> CustomerNotification:
        """Create a single notification record."""
        # Get customer info
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        # Format message
        data["customer_name"] = customer.name or "Valued Customer"
        formatted = self.format_message(notification_type, data)

        # Determine recipient based on channel
        recipient_email = None
        recipient_phone = None

        if channel == CustomerNotificationChannel.EMAIL:
            recipient_email = customer.email
        elif channel in [CustomerNotificationChannel.SMS, CustomerNotificationChannel.WHATSAPP]:
            recipient_phone = customer.phone

        notification = CustomerNotification(
            customer_id=customer_id,
            notification_type=notification_type,
            channel=channel,
            status=CustomerNotificationStatus.PENDING,
            title=formatted["title"],
            message=formatted["message"],
            short_message=formatted["short"][:160] if len(formatted["short"]) > 160 else formatted["short"],
            service_order_id=service_order_id,
            ticket_id=ticket_id,
            project_id=project_id,
            invoice_id=invoice_id,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            recipient_name=customer.name,
            extra_data=data,
            scheduled_at=schedule_at,
        )

        self.db.add(notification)
        return notification

    def notify_customer(
        self,
        customer_id: int,
        notification_type: CustomerNotificationType,
        data: Dict[str, Any],
        service_order_id: Optional[int] = None,
        ticket_id: Optional[int] = None,
        project_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        channels: Optional[List[CustomerNotificationChannel]] = None,
    ) -> List[CustomerNotification]:
        """
        Send notification to customer through their preferred channels.

        Returns list of created notification records.
        """
        # Get customer preferences
        preferences = self.get_customer_preferences(customer_id, notification_type)

        # Determine which channels to use
        if channels is None:
            channels = []
            if preferences["email"]:
                channels.append(CustomerNotificationChannel.EMAIL)
            if preferences["sms"]:
                channels.append(CustomerNotificationChannel.SMS)
            if preferences["whatsapp"]:
                channels.append(CustomerNotificationChannel.WHATSAPP)
            if preferences["push"]:
                channels.append(CustomerNotificationChannel.PUSH)

        # Default to email if no channels selected
        if not channels:
            channels = [CustomerNotificationChannel.EMAIL]

        notifications = []
        for channel in channels:
            try:
                notification = self.create_notification(
                    customer_id=customer_id,
                    notification_type=notification_type,
                    data=data,
                    channel=channel,
                    service_order_id=service_order_id,
                    ticket_id=ticket_id,
                    project_id=project_id,
                    invoice_id=invoice_id,
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Failed to create {channel.value} notification: {e}")

        self.db.commit()

        # Queue for delivery (in real implementation, this would be async)
        for notification in notifications:
            self._queue_for_delivery(notification)

        return notifications

    async def _send_notification_async(self, notification: CustomerNotification):
        """Actually send the notification via the appropriate provider."""
        from app.services.notification_providers import (
            get_email_provider,
            get_sms_provider,
            get_whatsapp_provider,
            NotificationResult,
        )

        result: Optional[NotificationResult] = None

        try:
            if notification.channel == CustomerNotificationChannel.EMAIL:
                if not notification.recipient_email:
                    notification.status = CustomerNotificationStatus.FAILED
                    notification.error_message = "No recipient email address"
                    return

                provider = get_email_provider()
                result = await provider.send(
                    to=notification.recipient_email,
                    subject=notification.title,
                    message=notification.message,
                    short_message=notification.short_message,
                    extra_data=notification.extra_data,
                )

            elif notification.channel == CustomerNotificationChannel.SMS:
                if not notification.recipient_phone:
                    notification.status = CustomerNotificationStatus.FAILED
                    notification.error_message = "No recipient phone number"
                    return

                provider = get_sms_provider()
                result = await provider.send(
                    to=notification.recipient_phone,
                    subject=notification.title,
                    message=notification.message,
                    short_message=notification.short_message,
                    extra_data=notification.extra_data,
                )

            elif notification.channel == CustomerNotificationChannel.WHATSAPP:
                if not notification.recipient_phone:
                    notification.status = CustomerNotificationStatus.FAILED
                    notification.error_message = "No recipient phone number"
                    return

                provider = get_whatsapp_provider()
                result = await provider.send(
                    to=notification.recipient_phone,
                    subject=notification.title,
                    message=notification.message,
                    short_message=notification.short_message,
                    extra_data=notification.extra_data,
                )

            elif notification.channel == CustomerNotificationChannel.PUSH:
                # Push notifications would integrate with FCM or similar
                notification.status = CustomerNotificationStatus.QUEUED
                logger.info("Push notifications not yet implemented")
                return

            elif notification.channel == CustomerNotificationChannel.IN_APP:
                # In-app notifications are stored and retrieved by the frontend
                notification.status = CustomerNotificationStatus.DELIVERED
                notification.delivered_at = datetime.utcnow()
                return

            # Process result
            if result:
                notification.attempt_count += 1
                if result.success:
                    notification.status = CustomerNotificationStatus.SENT
                    notification.delivered_at = datetime.utcnow()
                    notification.external_id = result.external_id
                    logger.info(f"Notification {notification.id} sent via {result.provider}")
                else:
                    if notification.attempt_count >= 3:
                        notification.status = CustomerNotificationStatus.FAILED
                    else:
                        notification.status = CustomerNotificationStatus.PENDING
                    notification.error_message = result.error_message
                    logger.warning(f"Notification {notification.id} failed: {result.error_message}")

        except Exception as e:
            notification.attempt_count += 1
            notification.error_message = str(e)
            if notification.attempt_count >= 3:
                notification.status = CustomerNotificationStatus.FAILED
            logger.error(f"Failed to send notification {notification.id}: {e}")

    def _queue_for_delivery(self, notification: CustomerNotification):
        """Queue notification for delivery via appropriate channel."""
        import asyncio

        # Mark as queued initially
        notification.status = CustomerNotificationStatus.QUEUED
        logger.info(f"Queued notification {notification.id} for {notification.channel.value} delivery")

        # Try to send immediately in background
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._send_notification_async(notification))
            else:
                loop.run_until_complete(self._send_notification_async(notification))
        except RuntimeError:
            # No event loop running, create one
            asyncio.run(self._send_notification_async(notification))

    # ==========================================================================
    # SERVICE ORDER NOTIFICATION HELPERS
    # ==========================================================================

    def notify_service_scheduled(self, service_order: ServiceOrder) -> List[CustomerNotification]:
        """Notify customer that service has been scheduled."""
        scheduled_time = "TBD"
        if service_order.scheduled_start_time:
            scheduled_time = service_order.scheduled_start_time.strftime("%I:%M %p")

        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.SERVICE_SCHEDULED,
            data={
                "order_number": service_order.order_number,
                "order_type": service_order.order_type.value.replace("_", " ").title(),
                "scheduled_date": service_order.scheduled_date.strftime("%B %d, %Y"),
                "scheduled_time": scheduled_time,
                "service_address": service_order.service_address,
                "title": service_order.title,
            },
            service_order_id=service_order.id,
        )

    def notify_service_rescheduled(
        self,
        service_order: ServiceOrder,
        reason: str = "Schedule adjustment"
    ) -> List[CustomerNotification]:
        """Notify customer that service has been rescheduled."""
        scheduled_time = "TBD"
        if service_order.scheduled_start_time:
            scheduled_time = service_order.scheduled_start_time.strftime("%I:%M %p")

        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.SERVICE_RESCHEDULED,
            data={
                "order_number": service_order.order_number,
                "order_type": service_order.order_type.value.replace("_", " ").title(),
                "scheduled_date": service_order.scheduled_date.strftime("%B %d, %Y"),
                "scheduled_time": scheduled_time,
                "service_address": service_order.service_address,
                "notes": reason,
            },
            service_order_id=service_order.id,
        )

    def notify_technician_assigned(self, service_order: ServiceOrder) -> List[CustomerNotification]:
        """Notify customer that a technician has been assigned."""
        technician_name = "A technician"
        if service_order.technician:
            technician_name = service_order.technician.name or "A technician"

        scheduled_time = "TBD"
        if service_order.scheduled_start_time:
            scheduled_time = service_order.scheduled_start_time.strftime("%I:%M %p")

        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.TECHNICIAN_ASSIGNED,
            data={
                "order_number": service_order.order_number,
                "order_type": service_order.order_type.value.replace("_", " ").title(),
                "technician_name": technician_name,
                "scheduled_date": service_order.scheduled_date.strftime("%B %d, %Y"),
                "scheduled_time": scheduled_time,
            },
            service_order_id=service_order.id,
        )

    def notify_technician_en_route(
        self,
        service_order: ServiceOrder,
        eta: str = "30 minutes"
    ) -> List[CustomerNotification]:
        """Notify customer that technician is on the way."""
        technician_name = "Your technician"
        if service_order.technician:
            technician_name = service_order.technician.name or "Your technician"

        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.TECHNICIAN_EN_ROUTE,
            data={
                "order_number": service_order.order_number,
                "technician_name": technician_name,
                "eta": eta,
                "service_address": service_order.service_address,
            },
            service_order_id=service_order.id,
        )

    def notify_technician_arrived(self, service_order: ServiceOrder) -> List[CustomerNotification]:
        """Notify customer that technician has arrived."""
        technician_name = "Your technician"
        if service_order.technician:
            technician_name = service_order.technician.name or "Your technician"

        arrival_time = service_order.arrival_time or datetime.utcnow()

        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.TECHNICIAN_ARRIVED,
            data={
                "order_number": service_order.order_number,
                "technician_name": technician_name,
                "arrival_time": arrival_time.strftime("%I:%M %p"),
            },
            service_order_id=service_order.id,
        )

    def notify_service_started(self, service_order: ServiceOrder) -> List[CustomerNotification]:
        """Notify customer that service work has started."""
        technician_name = "Our technician"
        if service_order.technician:
            technician_name = service_order.technician.name or "Our technician"

        start_time = service_order.actual_start_time or datetime.utcnow()
        estimated_duration = f"{float(service_order.estimated_duration_hours)} hours"

        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.SERVICE_STARTED,
            data={
                "order_number": service_order.order_number,
                "order_type": service_order.order_type.value.replace("_", " ").title(),
                "technician_name": technician_name,
                "start_time": start_time.strftime("%I:%M %p"),
                "estimated_duration": estimated_duration,
            },
            service_order_id=service_order.id,
        )

    def notify_service_completed(self, service_order: ServiceOrder) -> List[CustomerNotification]:
        """Notify customer that service has been completed."""
        end_time = service_order.actual_end_time or datetime.utcnow()
        actual_duration = "Unknown"
        if service_order.actual_duration_hours:
            hours = float(service_order.actual_duration_hours)
            if hours < 1:
                actual_duration = f"{int(hours * 60)} minutes"
            else:
                actual_duration = f"{hours:.1f} hours"

        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.SERVICE_COMPLETED,
            data={
                "order_number": service_order.order_number,
                "order_type": service_order.order_type.value.replace("_", " ").title(),
                "end_time": end_time.strftime("%I:%M %p on %B %d, %Y"),
                "actual_duration": actual_duration,
                "work_performed": service_order.work_performed or "Service completed as requested.",
                "resolution_notes": service_order.resolution_notes or "",
            },
            service_order_id=service_order.id,
        )

    def notify_service_cancelled(
        self,
        service_order: ServiceOrder,
        reason: str = "Service cancelled"
    ) -> List[CustomerNotification]:
        """Notify customer that service has been cancelled."""
        return self.notify_customer(
            customer_id=service_order.customer_id,
            notification_type=CustomerNotificationType.SERVICE_CANCELLED,
            data={
                "order_number": service_order.order_number,
                "notes": reason,
            },
            service_order_id=service_order.id,
        )

    # ==========================================================================
    # TICKET NOTIFICATION HELPERS
    # ==========================================================================

    def notify_ticket_created(self, ticket: Ticket) -> List[CustomerNotification]:
        """Notify customer that their ticket was created."""
        if not ticket.customer_id:
            return []
        return self.notify_customer(
            customer_id=ticket.customer_id,
            notification_type=CustomerNotificationType.TICKET_CREATED,
            data={
                "ticket_id": ticket.id,
                "subject": ticket.subject,
                "priority": ticket.priority.value if ticket.priority else "Normal",
            },
            ticket_id=ticket.id,
        )

    def notify_ticket_updated(
        self,
        ticket: Ticket,
        notes: str = ""
    ) -> List[CustomerNotification]:
        """Notify customer of ticket status update."""
        if not ticket.customer_id:
            return []
        return self.notify_customer(
            customer_id=ticket.customer_id,
            notification_type=CustomerNotificationType.TICKET_UPDATED,
            data={
                "ticket_id": ticket.id,
                "status": ticket.status.value if ticket.status else "Updated",
                "notes": notes,
            },
            ticket_id=ticket.id,
        )

    def notify_ticket_reply(
        self,
        ticket: Ticket,
        reply: str
    ) -> List[CustomerNotification]:
        """Notify customer of new reply on their ticket."""
        if not ticket.customer_id:
            return []
        return self.notify_customer(
            customer_id=ticket.customer_id,
            notification_type=CustomerNotificationType.TICKET_REPLY,
            data={
                "ticket_id": ticket.id,
                "subject": ticket.subject,
                "reply": reply[:500] + "..." if len(reply) > 500 else reply,
            },
            ticket_id=ticket.id,
        )

    def notify_ticket_resolved(
        self,
        ticket: Ticket,
        resolution: str = ""
    ) -> List[CustomerNotification]:
        """Notify customer that their ticket was resolved."""
        if not ticket.customer_id:
            return []
        return self.notify_customer(
            customer_id=ticket.customer_id,
            notification_type=CustomerNotificationType.TICKET_RESOLVED,
            data={
                "ticket_id": ticket.id,
                "subject": ticket.subject,
                "resolution": resolution or "Issue resolved.",
            },
            ticket_id=ticket.id,
        )

    # ==========================================================================
    # PROJECT NOTIFICATION HELPERS
    # ==========================================================================

    def notify_project_started(self, project: Project) -> List[CustomerNotification]:
        """Notify customer that their project has started."""
        if not project.customer_id:
            return []

        manager_name = "Our team"
        if project.project_manager:
            manager_name = project.project_manager.name or "Our team"

        return self.notify_customer(
            customer_id=project.customer_id,
            notification_type=CustomerNotificationType.PROJECT_STARTED,
            data={
                "project_name": project.project_name,
                "start_date": (project.actual_start_date or project.expected_start_date or datetime.utcnow()).strftime("%B %d, %Y"),
                "expected_end_date": project.expected_end_date.strftime("%B %d, %Y") if project.expected_end_date else "TBD",
                "project_manager": manager_name,
            },
            project_id=project.id,
        )

    def notify_project_milestone(
        self,
        project: Project,
        milestone_name: str,
        notes: str = ""
    ) -> List[CustomerNotification]:
        """Notify customer of project milestone."""
        if not project.customer_id:
            return []

        return self.notify_customer(
            customer_id=project.customer_id,
            notification_type=CustomerNotificationType.PROJECT_MILESTONE,
            data={
                "project_name": project.project_name,
                "milestone_name": milestone_name,
                "completion": float(project.percent_complete) if project.percent_complete else 0,
                "notes": notes,
            },
            project_id=project.id,
        )

    def notify_project_completed(
        self,
        project: Project,
        summary: str = ""
    ) -> List[CustomerNotification]:
        """Notify customer that project is completed."""
        if not project.customer_id:
            return []

        return self.notify_customer(
            customer_id=project.customer_id,
            notification_type=CustomerNotificationType.PROJECT_COMPLETED,
            data={
                "project_name": project.project_name,
                "end_date": (project.actual_end_date or datetime.utcnow()).strftime("%B %d, %Y"),
                "summary": summary or "All project deliverables have been completed.",
            },
            project_id=project.id,
        )

    # ==========================================================================
    # INVOICE NOTIFICATION HELPERS
    # ==========================================================================

    def notify_invoice_generated(self, invoice: Invoice) -> List[CustomerNotification]:
        """Notify customer of new invoice."""
        if not invoice.customer_id:
            return []
        amount = f"₦{float(invoice.total_amount):,.2f}" if invoice.total_amount else "₦0.00"

        return self.notify_customer(
            customer_id=invoice.customer_id,
            notification_type=CustomerNotificationType.INVOICE_GENERATED,
            data={
                "invoice_number": invoice.invoice_number or str(invoice.id),
                "amount": amount,
                "due_date": invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else "Upon receipt",
                "description": invoice.description or "",
            },
            invoice_id=invoice.id,
        )

    def notify_payment_received(
        self,
        customer_id: int,
        amount: Decimal,
        reference: str,
        invoice_id: Optional[int] = None,
        invoice_number: str = ""
    ) -> List[CustomerNotification]:
        """Notify customer of payment receipt."""
        return self.notify_customer(
            customer_id=customer_id,
            notification_type=CustomerNotificationType.PAYMENT_RECEIVED,
            data={
                "amount": f"₦{float(amount):,.2f}",
                "reference": reference,
                "invoice_number": invoice_number,
            },
            invoice_id=invoice_id,
        )

    def notify_payment_due(
        self,
        invoice: Invoice,
        days_until_due: int
    ) -> List[CustomerNotification]:
        """Notify customer of upcoming payment due."""
        if not invoice.customer_id:
            return []
        amount = f"₦{float(invoice.balance):,.2f}" if invoice.balance else "₦0.00"

        return self.notify_customer(
            customer_id=invoice.customer_id,
            notification_type=CustomerNotificationType.PAYMENT_DUE,
            data={
                "invoice_number": invoice.invoice_number or str(invoice.id),
                "amount": amount,
                "due_date": invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else "Now",
                "days_until_due": days_until_due,
            },
            invoice_id=invoice.id,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_notification_service(db: Session) -> CustomerNotificationService:
    """Factory function to get notification service instance."""
    return CustomerNotificationService(db)
