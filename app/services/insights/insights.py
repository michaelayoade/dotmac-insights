"""Insights service for deep analytics.

Provides comprehensive analytics for data relationships,
completeness, and actionable intelligence.

This is an internal-only service - NOT exposed via API endpoints.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from itertools import groupby
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, case, distinct, and_, or_, extract, text, cast
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Date

from app.config import settings
from app.models.party import Party, PartyRole, CustomerAccount
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.credit_note import CreditNote
from app.models.pop import Pop
from app.models.employee import Employee
from app.models.tariff import Tariff
from app.models.lead import Lead
from app.models.project import Project
from app.models.router import Router
from app.models.customer_note import CustomerNote

from .insights_types import (
    DataCompletenessResult,
    CustomerSegmentsResult,
    CustomerHealthResult,
    ChurnRiskResult,
    PlanChangesResult,
    RelationshipMapResult,
    FinancialInsightsResult,
    OperationalInsightsResult,
    NetworkHealthResult,
    AnomaliesResult,
    DataAvailabilityResult,
    CompletenessRecommendation,
    FieldCompleteness,
    SystemLinkage,
    PaymentBehavior,
    PaymentTiming,
    PaymentTimingDistribution,
    SupportIntensity,
    ChurnIndicators,
    RiskSegments,
    TicketMetrics,
    ConversationMetrics,
    AgingBucket,
    Anomaly,
    Pattern,
    AnomalySummary,
    MissingData,
)

if TYPE_CHECKING:
    from app.auth import Principal

logger = logging.getLogger(__name__)


class InsightsService:
    """Service for deep analytics and insights.

    Provides comprehensive data analysis including:
    - Data completeness and quality
    - Customer segmentation and health
    - Financial insights
    - Operational metrics
    - Anomaly detection

    Note: This service does NOT commit transactions.
    The caller is responsible for transaction control.
    """

    def __init__(self, db: Session, principal: Optional["Principal"] = None) -> None:
        """Initialize the insights service.

        Args:
            db: SQLAlchemy database session
            principal: Optional authentication principal for RBAC filtering
        """
        self.db = db
        self.principal = principal
        self._apply_statement_timeout()

    def _apply_statement_timeout(self) -> None:
        """Apply per-request statement timeout for Postgres connections."""
        timeout_ms = getattr(settings, "analytics_statement_timeout_ms", None)
        if not timeout_ms or not self.db.bind or self.db.bind.dialect.name != "postgresql":
            return
        try:
            self.db.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": timeout_ms})
        except Exception:
            # Rollback the failed transaction to allow subsequent queries to work
            self.db.rollback()
            return

    # =========================================================================
    # DATA COMPLETENESS & QUALITY
    # =========================================================================

    def get_data_completeness(self) -> DataCompletenessResult:
        """Comprehensive data completeness analysis across all entities.

        Shows what data is available, missing, and the quality score.
        Performance: Consolidated from 30+ queries to 5 aggregate queries.
        """
        party_pop = (
            self.db.query(
                Subscription.party_id.label("party_id"),
                func.min(Router.pop_id).label("pop_id"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(Router.pop_id.isnot(None))
            .group_by(Subscription.party_id)
            .subquery()
        )

        # Single query for all customer field counts using CASE WHEN aggregation
        customer_stats = self.db.query(
            func.count(CustomerAccount.id).label("total"),
            func.count(case((and_(Party.primary_email.isnot(None), Party.primary_email != ""), 1))).label("email"),
            func.count(case((CustomerAccount.billing_email.isnot(None), 1))).label("billing_email"),
            func.count(case((and_(Party.primary_phone.isnot(None), Party.primary_phone != ""), 1))).label("phone"),
            func.count(case((func.jsonb_array_length(Party.addresses) > 0, 1))).label("address"),
            func.count(case((party_pop.c.pop_id.isnot(None), 1))).label("pop_assigned"),
            func.count(case((CustomerAccount.account_number.isnot(None), 1))).label("account_number"),
            func.count(case((CustomerAccount.created_at.isnot(None), 1))).label("signup_date"),
            # System linkage
            func.count(case((CustomerAccount.external_ids["splynx_id"].astext.isnot(None), 1))).label("splynx_linked"),
            func.count(case((CustomerAccount.external_ids["erpnext_id"].astext.isnot(None), 1))).label("erpnext_linked"),
            func.count(case((CustomerAccount.external_ids["chatwoot_id"].astext.isnot(None), 1))).label("chatwoot_linked"),
            func.count(case((CustomerAccount.external_ids["zoho_id"].astext.isnot(None), 1))).label("zoho_linked"),
        ).select_from(CustomerAccount).join(
            Party, CustomerAccount.party_id == Party.id
        ).outerjoin(
            party_pop, party_pop.c.party_id == CustomerAccount.party_id
        ).first()

        total_customers = customer_stats.total
        if total_customers == 0:
            return DataCompletenessResult(
                summary={"error": "No customer data available", "total_customers": 0},
                customer_fields={},
                system_linkage={},
                subscriptions={},
                invoices={},
                payments={},
                support={},
                recommendations=[],
            )

        # Extract customer field completeness from single query result
        customer_fields_raw = {
            "email": customer_stats.email,
            "billing_email": customer_stats.billing_email,
            "phone": customer_stats.phone,
            "address": customer_stats.address,
            "pop_assigned": customer_stats.pop_assigned,
            "account_number": customer_stats.account_number,
            "signup_date": customer_stats.signup_date,
        }

        # Extract system linkage from same query result
        system_linkage_raw = {
            "splynx_linked": customer_stats.splynx_linked,
            "erpnext_linked": customer_stats.erpnext_linked,
            "chatwoot_linked": customer_stats.chatwoot_linked,
            "zoho_linked": customer_stats.zoho_linked,
        }

        # Calculate completeness percentages
        critical_fields = ["email", "phone", "address"]
        critical_score = sum(customer_fields_raw[f] for f in critical_fields) / (len(critical_fields) * total_customers) * 100
        all_fields_score = sum(customer_fields_raw.values()) / (len(customer_fields_raw) * total_customers) * 100

        # Single query for subscription completeness
        sub_stats = self.db.query(
            func.count(Subscription.id).label("total"),
            func.count(case((Subscription.tariff_id.isnot(None), 1))).label("with_tariff"),
            func.count(case((Subscription.router_id.isnot(None), 1))).label("with_router"),
            func.count(case((or_(Subscription.ipv4_address.isnot(None), Subscription.ipv6_address.isnot(None)), 1))).label("with_ip"),
            func.count(case((Subscription.mac_address.isnot(None), 1))).label("with_mac"),
        ).first()

        sub_completeness = {
            "total": sub_stats.total,
            "with_tariff": sub_stats.with_tariff,
            "with_router": sub_stats.with_router,
            "with_ip_assigned": sub_stats.with_ip,
            "with_mac_address": sub_stats.with_mac,
        }

        # Single query for invoice quality
        invoice_stats = self.db.query(
            func.count(Invoice.id).label("total"),
            func.count(case((Invoice.customer_account_id.isnot(None), 1))).label("with_customer"),
            func.count(case((Invoice.customer_account_id.is_(None), 1))).label("orphaned"),
            func.count(case((Invoice.due_date.isnot(None), 1))).label("with_due_date"),
        ).first()

        invoice_quality = {
            "total": invoice_stats.total,
            "with_customer": invoice_stats.with_customer,
            "orphaned": invoice_stats.orphaned,
            "with_due_date": invoice_stats.with_due_date,
        }

        # Single query for payment quality
        payment_stats = self.db.query(
            func.count(Payment.id).label("total"),
            func.count(case((Payment.customer_account_id.isnot(None), 1))).label("with_customer"),
            func.count(case((Payment.invoice_id.isnot(None), 1))).label("with_invoice"),
            func.count(case((and_(Payment.customer_account_id.is_(None), Payment.invoice_id.is_(None)), 1))).label("orphaned"),
        ).first()

        payment_quality = {
            "total": payment_stats.total,
            "with_customer": payment_stats.with_customer,
            "with_invoice": payment_stats.with_invoice,
            "orphaned": payment_stats.orphaned,
        }

        # Single query for support quality (conversations + tickets)
        convo_stats = self.db.query(
            func.count(Conversation.id).label("total"),
            func.count(case((Conversation.customer_account_id.isnot(None), 1))).label("linked"),
            func.count(case((Conversation.customer_account_id.is_(None), 1))).label("orphaned"),
        ).first()

        ticket_stats = self.db.query(
            func.count(Ticket.id).label("total"),
            func.count(case((Ticket.customer_account_id.isnot(None), 1))).label("linked"),
            func.count(case((Ticket.customer_account_id.is_(None), 1))).label("orphaned"),
            func.count(case((Ticket.assigned_employee_id.isnot(None), 1))).label("assigned"),
        ).first()

        support_quality = {
            "conversations": {
                "total": convo_stats.total,
                "linked_to_customer": convo_stats.linked,
                "orphaned": convo_stats.orphaned,
            },
            "tickets": {
                "total": ticket_stats.total,
                "linked_to_customer": ticket_stats.linked,
                "orphaned": ticket_stats.orphaned,
                "assigned_to_employee": ticket_stats.assigned,
            }
        }

        # Build result
        customer_fields = {
            field: FieldCompleteness(
                count=count,
                percent=round(count / total_customers * 100, 1),
                missing=total_customers - count,
            )
            for field, count in customer_fields_raw.items()
        }

        system_linkage = {
            system: SystemLinkage(
                count=count,
                percent=round(count / total_customers * 100, 1),
            )
            for system, count in system_linkage_raw.items()
        }

        recommendations = self._generate_completeness_recommendations(
            customer_fields_raw, total_customers, system_linkage_raw
        )

        return DataCompletenessResult(
            summary={
                "total_customers": total_customers,
                "critical_completeness_score": round(critical_score, 1),
                "overall_completeness_score": round(all_fields_score, 1),
                "grade": "A" if critical_score >= 90 else "B" if critical_score >= 75 else "C" if critical_score >= 60 else "D" if critical_score >= 40 else "F",
            },
            customer_fields=customer_fields,
            system_linkage=system_linkage,
            subscriptions=sub_completeness,
            invoices=invoice_quality,
            payments=payment_quality,
            support=support_quality,
            recommendations=recommendations,
        )

    def _generate_completeness_recommendations(
        self, fields: Dict[str, int], total: int, linkage: Dict[str, int]
    ) -> List[CompletenessRecommendation]:
        """Generate actionable recommendations based on data completeness."""
        recommendations = []

        if fields["email"] / total < 0.9:
            recommendations.append(CompletenessRecommendation(
                priority="high",
                category="contact",
                issue=f"Missing email for {total - fields['email']} customers ({round((1 - fields['email']/total) * 100, 1)}%)",
                action="Run email collection campaign or sync from external systems",
                impact="Critical for billing notifications and communication",
            ))

        if fields["phone"] / total < 0.85:
            recommendations.append(CompletenessRecommendation(
                priority="high",
                category="contact",
                issue=f"Missing phone for {total - fields['phone']} customers",
                action="Collect phone numbers during customer interactions",
                impact="Needed for support and urgent communications",
            ))

        if fields["pop_assigned"] / total < 0.95:
            recommendations.append(CompletenessRecommendation(
                priority="high",
                category="network",
                issue=f"{total - fields['pop_assigned']} customers without POP assignment",
                action="Assign customers to nearest POP based on location",
                impact="Critical for network capacity planning",
            ))

        if linkage["chatwoot_linked"] / total < 0.7:
            recommendations.append(CompletenessRecommendation(
                priority="medium",
                category="integration",
                issue=f"{total - linkage['chatwoot_linked']} customers not linked to Chatwoot",
                action="Run customer matching between systems using email/phone",
                impact="Enables unified customer support view",
            ))

        return recommendations

    # =========================================================================
    # CUSTOMER INSIGHTS & SEGMENTATION
    # =========================================================================

    def get_customer_segments(self, limit: int = 100) -> CustomerSegmentsResult:
        """Advanced customer segmentation based on multiple dimensions."""
        # Status distribution
        status_dist = self.db.query(
            CustomerAccount.status,
            func.count(CustomerAccount.id).label("count"),
            func.sum(CustomerAccount.mrr).label("total_mrr")
        ).group_by(CustomerAccount.status).all()

        segment_expr = func.coalesce(PartyRole.metadata_["customer_type"].astext, "unknown")
        billing_expr = func.coalesce(PartyRole.metadata_["billing_type"].astext, "unknown")

        # Customer type distribution
        type_dist = self.db.query(
            segment_expr.label("segment"),
            func.count(CustomerAccount.id).label("count"),
            func.sum(CustomerAccount.mrr).label("total_mrr")
        ).outerjoin(
            PartyRole,
            and_(PartyRole.party_id == CustomerAccount.party_id, PartyRole.role == "customer"),
        ).group_by(segment_expr).all()

        # Billing type distribution
        billing_dist = self.db.query(
            billing_expr.label("billing_type"),
            func.count(CustomerAccount.id).label("count"),
            func.sum(CustomerAccount.mrr).label("total_mrr")
        ).outerjoin(
            PartyRole,
            and_(PartyRole.party_id == CustomerAccount.party_id, PartyRole.role == "customer"),
        ).group_by(billing_expr).all()

        # Tenure segments - single aggregated query
        days_since_signup = func.date_part("day", func.current_date() - CustomerAccount.created_at)
        tenure_bucket = case(
            (days_since_signup <= 30, 'New (0-30 days)'),
            (days_since_signup <= 90, 'Growing (31-90 days)'),
            (days_since_signup <= 365, 'Established (91-365 days)'),
            (days_since_signup <= 730, 'Loyal (1-2 years)'),
            else_='Long-term (2+ years)'
        )

        tenure_data = (
            self.db.query(
                tenure_bucket.label("segment"),
                func.count(CustomerAccount.id).label("count"),
            )
            .filter(CustomerAccount.created_at.isnot(None))
            .group_by(tenure_bucket)
            .all()
        )

        # Ensure all segments are represented in order
        segment_order = [
            "New (0-30 days)",
            "Growing (31-90 days)",
            "Established (91-365 days)",
            "Loyal (1-2 years)",
            "Long-term (2+ years)",
        ]
        tenure_map = {row.segment: row.count for row in tenure_data}
        tenure_segments = [{"segment": seg, "count": tenure_map.get(seg, 0)} for seg in segment_order]

        # MRR segments - single aggregated query
        mrr_bucket = case(
            (or_(CustomerAccount.mrr.is_(None), CustomerAccount.mrr == 0), 'No MRR'),
            (CustomerAccount.mrr < 10000, 'Low (<10K)'),
            (CustomerAccount.mrr < 50000, 'Medium (10K-50K)'),
            (CustomerAccount.mrr < 200000, 'High (50K-200K)'),
            else_='Enterprise (200K+)'
        )

        mrr_data = (
            self.db.query(
                mrr_bucket.label("segment"),
                func.count(CustomerAccount.id).label("count"),
            )
            .group_by(mrr_bucket)
            .all()
        )

        mrr_order = ["No MRR", "Low (<10K)", "Medium (10K-50K)", "High (50K-200K)", "Enterprise (200K+)"]
        mrr_map = {row.segment: row.count for row in mrr_data}
        mrr_segments = [{"segment": seg, "count": mrr_map.get(seg, 0)} for seg in mrr_order]

        party_pop = (
            self.db.query(
                Subscription.party_id.label("party_id"),
                func.min(Router.pop_id).label("pop_id"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(Router.pop_id.isnot(None))
            .group_by(Subscription.party_id)
            .subquery()
        )

        # Geographic distribution (top cities from POP locations)
        city_dist = self.db.query(
            Pop.city,
            func.count(distinct(party_pop.c.party_id)).label("count"),
            func.sum(CustomerAccount.mrr).label("total_mrr")
        ).join(
            party_pop, party_pop.c.pop_id == Pop.id
        ).join(
            CustomerAccount, CustomerAccount.party_id == party_pop.c.party_id
        ).filter(Pop.city.isnot(None)).group_by(Pop.city).order_by(
            func.count(distinct(party_pop.c.party_id)).desc()
        ).limit(limit).all()

        # POP distribution
        pop_dist = self.db.query(
            Pop.name,
            Pop.city,
            func.count(distinct(party_pop.c.party_id)).label("customer_count"),
            func.sum(CustomerAccount.mrr).label("total_mrr")
        ).join(
            party_pop, party_pop.c.pop_id == Pop.id
        ).join(
            CustomerAccount, CustomerAccount.party_id == party_pop.c.party_id
        ).group_by(
            Pop.id, Pop.name, Pop.city
        ).order_by(func.count(distinct(party_pop.c.party_id)).desc()).limit(limit).all()

        return CustomerSegmentsResult(
            by_status=[
                {
                    "status": row.status if row.status else "unknown",
                    "count": row.count,
                    "mrr": float(row.total_mrr or 0),
                }
                for row in status_dist
            ],
            by_type=[
                {
                    "type": row.segment or "unknown",
                    "count": row.count,
                    "mrr": float(row.total_mrr or 0),
                }
                for row in type_dist
            ],
            by_billing_type=[
                {
                    "billing_type": row.billing_type or "unknown",
                    "count": row.count,
                    "mrr": float(row.total_mrr or 0),
                }
                for row in billing_dist
            ],
            by_tenure=tenure_segments,
            by_mrr_tier=mrr_segments,
            by_city=[
                {
                    "city": row.city or "Unknown",
                    "count": row.count,
                    "mrr": float(row.total_mrr or 0),
                }
                for row in city_dist
            ],
            by_pop=[
                {
                    "pop_name": row.name,
                    "city": row.city,
                    "customer_count": row.customer_count,
                    "mrr": float(row.total_mrr or 0),
                }
                for row in pop_dist
            ],
        )

    def get_customer_health(self) -> CustomerHealthResult:
        """Customer health analysis including payment behavior, support needs, and risk indicators."""
        total_active = self.db.query(CustomerAccount).filter(CustomerAccount.status == "active").count()

        # Payment behavior analysis
        # Customers with overdue invoices
        customers_with_overdue = self.db.query(distinct(Invoice.customer_account_id)).filter(
            Invoice.status == InvoiceStatus.OVERDUE,
            Invoice.customer_account_id.isnot(None),
        ).count()

        # Average payment timing - keep processing in SQL to avoid loading all invoices
        days_early = func.date_part("day", Invoice.due_date - Invoice.paid_date)
        payment_timing = self.db.query(
            func.sum(case(
                (and_(Invoice.paid_date <= Invoice.due_date, days_early > 3), 1),
                else_=0
            )).label("early"),
            func.sum(case(
                (and_(Invoice.paid_date <= Invoice.due_date, days_early <= 3), 1),
                else_=0
            )).label("on_time"),
            func.sum(case(
                (Invoice.paid_date > Invoice.due_date, 1),
                else_=0
            )).label("late"),
            func.count(Invoice.id).label("total_paid"),
        ).filter(
            Invoice.status == InvoiceStatus.PAID,
            Invoice.paid_date.isnot(None),
            Invoice.due_date.isnot(None)
        ).one()

        early_payments = int(payment_timing.early or 0)
        on_time_payments = int(payment_timing.on_time or 0)
        late_payments = int(payment_timing.late or 0)
        total_paid = int(payment_timing.total_paid or 0)

        # Support intensity (tickets per customer)
        tickets_per_customer = self.db.query(
            Ticket.customer_account_id,
            func.count(Ticket.id).label("ticket_count")
        ).filter(
            Ticket.customer_account_id.isnot(None),
            Ticket.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
        ).group_by(Ticket.customer_account_id).subquery()

        ticket_intensity = self.db.query(
            func.count(tickets_per_customer.c.customer_account_id).label("customers_with_tickets_30d"),
            func.sum(case((tickets_per_customer.c.ticket_count >= 3, 1), else_=0)).label("high_support_customers")
        ).one()
        customers_with_tickets_30d = int(ticket_intensity.customers_with_tickets_30d or 0)
        high_support_customers = int(ticket_intensity.high_support_customers or 0)

        # Conversation activity
        convos_per_customer = self.db.query(
            Conversation.customer_account_id,
            func.count(Conversation.id).label("convo_count")
        ).filter(
            Conversation.customer_account_id.isnot(None),
            Conversation.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
        ).group_by(Conversation.customer_account_id).subquery()

        convo_intensity = self.db.query(
            func.count(convos_per_customer.c.customer_account_id).label("customers_with_conversations_30d")
        ).one()
        customers_with_conversations_30d = int(convo_intensity.customers_with_conversations_30d or 0)

        # Churn indicators
        recently_cancelled = self.db.query(CustomerAccount).filter(
            CustomerAccount.status == "cancelled",
            CustomerAccount.cancelled_at >= datetime.now(timezone.utc) - timedelta(days=30)
        ).count()

        recently_suspended = self.db.query(CustomerAccount).filter(
            CustomerAccount.status == "suspended"
        ).count()

        # Inactive customers (no recent activity)
        customers_with_recent_payment = self.db.query(distinct(Payment.customer_account_id)).filter(
            Payment.payment_date >= datetime.now(timezone.utc) - timedelta(days=60),
            Payment.customer_account_id.isnot(None),
        ).count()

        return CustomerHealthResult(
            summary={
                "total_active_customers": total_active,
                "healthy_percent": round((total_active - customers_with_overdue - high_support_customers) / max(total_active, 1) * 100, 1),
            },
            payment_behavior=PaymentBehavior(
                customers_with_overdue=customers_with_overdue,
                overdue_percent=round(customers_with_overdue / max(total_active, 1) * 100, 1),
                payment_timing=PaymentTiming(
                    early=early_payments,
                    on_time=on_time_payments,
                    late=late_payments,
                    total_paid_invoices=total_paid,
                ),
                payment_timing_distribution=PaymentTimingDistribution(
                    early_percent=round(early_payments / max(total_paid, 1) * 100, 1),
                    on_time_percent=round(on_time_payments / max(total_paid, 1) * 100, 1),
                    late_percent=round(late_payments / max(total_paid, 1) * 100, 1),
                ),
            ),
            support_intensity=SupportIntensity(
                customers_with_tickets_30d=customers_with_tickets_30d,
                high_support_customers=high_support_customers,
                customers_with_conversations_30d=customers_with_conversations_30d,
            ),
            churn_indicators=ChurnIndicators(
                recently_cancelled_30d=recently_cancelled,
                currently_suspended=recently_suspended,
                inactive_60d=total_active - customers_with_recent_payment,
            ),
            risk_segments=RiskSegments(
                at_risk=customers_with_overdue + recently_suspended,
                high_maintenance=high_support_customers,
                churned_30d=recently_cancelled,
            ),
        )

    def get_churn_risk(self) -> ChurnRiskResult:
        """Get summary of churn risks."""
        overdue_customers = self.db.query(distinct(Invoice.customer_account_id)).filter(
            Invoice.status == InvoiceStatus.OVERDUE
        ).count()
        recently_cancelled = self.db.query(CustomerAccount).filter(
            CustomerAccount.status == "cancelled",
            CustomerAccount.cancelled_at >= datetime.now(timezone.utc) - timedelta(days=30)
        ).count()
        suspended = self.db.query(CustomerAccount).filter(CustomerAccount.status == "suspended").count()
        high_ticket_customers = self.db.query(func.count(CustomerAccount.id)).join(
            Ticket, Ticket.customer_account_id == CustomerAccount.id
        ).filter(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
        ).group_by(CustomerAccount.id).having(func.count(Ticket.id) >= 3).count()

        return ChurnRiskResult(
            summary={
                "overdue_customers": overdue_customers,
                "recent_cancellations_30d": recently_cancelled,
                "suspended_customers": suspended,
                "high_ticket_customers": high_ticket_customers,
            }
        )

    def get_plan_changes(self, months: int = 6) -> PlanChangesResult:
        """Plan change insights (upgrade/downgrade/lateral) over the past N months."""
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=months * 30)

        subs = (
            self.db.query(Subscription)
            .filter(
                Subscription.start_date.isnot(None),
                Subscription.start_date >= start_dt,
            )
            .order_by(Subscription.party_id, Subscription.start_date)
            .all()
        )

        transitions: List[Dict[str, Any]] = []
        customers_with_changes = set()

        for _, cust_subs in groupby(subs, key=lambda s: s.party_id):
            history = list(cust_subs)
            if len(history) < 2:
                continue
            customers_with_changes.add(history[0].party_id)
            history = sorted(history, key=lambda s: s.start_date or datetime.min)
            for prev, curr in zip(history, history[1:]):
                prev_price = float(prev.price or 0)
                curr_price = float(curr.price or 0)
                if curr_price > prev_price:
                    change_type = "upgrade"
                elif curr_price < prev_price:
                    change_type = "downgrade"
                else:
                    change_type = "lateral"
                transitions.append(
                    {
                        "party_id": curr.party_id,
                        "from_plan": prev.plan_name,
                        "to_plan": curr.plan_name,
                        "price_change": round(curr_price - prev_price, 2),
                        "change_type": change_type,
                        "date": (curr.start_date or end_dt).date().isoformat(),
                    }
                )

        upgrades = sum(1 for t in transitions if t["change_type"] == "upgrade")
        downgrades = sum(1 for t in transitions if t["change_type"] == "downgrade")
        lateral = sum(1 for t in transitions if t["change_type"] == "lateral")

        upgrade_mrr = sum(t["price_change"] for t in transitions if t["change_type"] == "upgrade")
        downgrade_mrr = sum(abs(t["price_change"]) for t in transitions if t["change_type"] == "downgrade")
        net_mrr = upgrade_mrr - downgrade_mrr

        active_customers = self.db.query(func.count(CustomerAccount.id)).filter(CustomerAccount.status == "active").scalar() or 0

        transition_counts: Dict[str, Dict[str, Any]] = {}
        for t in transitions:
            key = f"{t['from_plan']} -> {t['to_plan']}"
            if key not in transition_counts:
                transition_counts[key] = {"count": 0, "type": t["change_type"]}
            transition_counts[key]["count"] += 1

        common_transitions = sorted(
            [
                {"transition": k, "count": v["count"], "type": v["type"]}
                for k, v in transition_counts.items()
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:20]

        recent_changes = sorted(transitions, key=lambda t: t["date"], reverse=True)[:20]

        customers_changed = len(customers_with_changes)
        total_changes = len(transitions)

        upgrade_rate = round(upgrades / active_customers * 100, 2) if active_customers else 0
        downgrade_rate = round(downgrades / active_customers * 100, 2) if active_customers else 0
        upgrade_to_downgrade_ratio = round(upgrades / downgrades, 2) if downgrades else (upgrades if upgrades else 0)

        return PlanChangesResult(
            period_months=months,
            summary={
                "customers_with_plan_changes": customers_changed,
                "total_changes": total_changes,
                "upgrades": upgrades,
                "downgrades": downgrades,
                "lateral_moves": lateral,
            },
            revenue_impact={
                "upgrade_mrr_gained": round(upgrade_mrr, 2),
                "downgrade_mrr_lost": round(downgrade_mrr, 2),
                "net_mrr_change": round(net_mrr, 2),
            },
            rates={
                "upgrade_rate": upgrade_rate,
                "downgrade_rate": downgrade_rate,
                "upgrade_to_downgrade_ratio": upgrade_to_downgrade_ratio,
            },
            common_transitions=common_transitions,
            recent_changes=recent_changes,
        )

    # =========================================================================
    # RELATIONSHIP ANALYSIS
    # =========================================================================

    def get_relationship_map(self) -> RelationshipMapResult:
        """Analyze relationships between entities and identify orphaned/unlinked records."""
        # Entity counts
        entities = {
            "customer_accounts": self.db.query(CustomerAccount).count(),
            "subscriptions": self.db.query(Subscription).count(),
            "invoices": self.db.query(Invoice).count(),
            "payments": self.db.query(Payment).count(),
            "conversations": self.db.query(Conversation).count(),
            "tickets": self.db.query(Ticket).count(),
            "credit_notes": self.db.query(CreditNote).count(),
            "projects": self.db.query(Project).count(),
            "employees": self.db.query(Employee).count(),
            "pops": self.db.query(Pop).count(),
            "tariffs": self.db.query(Tariff).count(),
            "routers": self.db.query(Router).count(),
            "leads": self.db.query(Lead).count(),
        }

        # Relationship coverage
        relationships = {
            "subscriptions_to_parties": {
                "linked": self.db.query(Subscription).filter(Subscription.party_id.isnot(None)).count(),
                "orphaned": self.db.query(Subscription).filter(Subscription.party_id.is_(None)).count(),
            },
            "subscriptions_to_tariffs": {
                "linked": self.db.query(Subscription).filter(Subscription.tariff_id.isnot(None)).count(),
                "orphaned": self.db.query(Subscription).filter(Subscription.tariff_id.is_(None)).count(),
            },
            "invoices_to_customers": {
                "linked": self.db.query(Invoice).filter(Invoice.customer_account_id.isnot(None)).count(),
                "orphaned": self.db.query(Invoice).filter(Invoice.customer_account_id.is_(None)).count(),
            },
            "payments_to_customers": {
                "linked": self.db.query(Payment).filter(Payment.customer_account_id.isnot(None)).count(),
                "orphaned": self.db.query(Payment).filter(Payment.customer_account_id.is_(None)).count(),
            },
            "payments_to_invoices": {
                "linked": self.db.query(Payment).filter(Payment.invoice_id.isnot(None)).count(),
                "unlinked": self.db.query(Payment).filter(Payment.invoice_id.is_(None)).count(),
            },
            "conversations_to_customers": {
                "linked": self.db.query(Conversation).filter(Conversation.customer_account_id.isnot(None)).count(),
                "orphaned": self.db.query(Conversation).filter(Conversation.customer_account_id.is_(None)).count(),
            },
            "tickets_to_customers": {
                "linked": self.db.query(Ticket).filter(Ticket.customer_account_id.isnot(None)).count(),
                "orphaned": self.db.query(Ticket).filter(Ticket.customer_account_id.is_(None)).count(),
            },
            "tickets_to_employees": {
                "assigned": self.db.query(Ticket).filter(Ticket.assigned_employee_id.isnot(None)).count(),
                "unassigned": self.db.query(Ticket).filter(Ticket.assigned_employee_id.is_(None)).count(),
            },
            "customer_accounts_to_pops": {
                "linked": self.db.query(distinct(Subscription.party_id)).join(
                    Router, Subscription.router_id == Router.id
                ).filter(Router.pop_id.isnot(None)).count(),
                "orphaned": self.db.query(distinct(Subscription.party_id)).outerjoin(
                    Router, Subscription.router_id == Router.id
                ).filter(or_(Router.pop_id.is_(None), Subscription.router_id.is_(None))).count(),
            },
            "leads_converted": {
                "converted": self.db.query(Lead).filter(Lead.customer_account_id.isnot(None)).count(),
                "not_converted": self.db.query(Lead).filter(Lead.customer_account_id.is_(None)).count(),
            },
        }

        # Calculate relationship health scores
        relationship_scores = {}
        for rel_name, data in relationships.items():
            total = data.get("linked", 0) + data.get("orphaned", data.get("unlinked", data.get("unassigned", data.get("not_converted", 0))))
            if total > 0:
                linked = data.get("linked", data.get("assigned", data.get("converted", 0)))
                relationship_scores[rel_name] = round(linked / total * 100, 1)
            else:
                relationship_scores[rel_name] = 100.0

        return RelationshipMapResult(
            entity_counts=entities,
            relationships=relationships,
            relationship_health_scores=relationship_scores,
            average_overall_score=round(sum(relationship_scores.values()) / len(relationship_scores), 1),
        )

    # =========================================================================
    # FINANCIAL INSIGHTS
    # =========================================================================

    def get_financial_insights(self, months: int = 12) -> FinancialInsightsResult:
        """Deep financial analysis including revenue patterns, payment behavior, and forecasting indicators."""
        try:
            # Total MRR
            total_mrr = self.db.query(func.sum(CustomerAccount.mrr)).filter(
                CustomerAccount.status == "active"
            ).scalar() or 0

            segment_expr = func.coalesce(PartyRole.metadata_["customer_type"].astext, "unknown")

            # Revenue by customer type
            mrr_by_type = self.db.query(
                segment_expr.label("segment"),
                func.sum(CustomerAccount.mrr).label("mrr"),
                func.count(CustomerAccount.id).label("count")
            ).outerjoin(
                PartyRole,
                and_(PartyRole.party_id == CustomerAccount.party_id, PartyRole.role == "customer"),
            ).filter(
                CustomerAccount.status == "active"
            ).group_by(segment_expr).all()

            # Invoice aging
            aging_buckets: Dict[str, AgingBucket] = {
                "current": AgingBucket(count=0, amount=0.0),
                "1_30_days": AgingBucket(count=0, amount=0.0),
                "31_60_days": AgingBucket(count=0, amount=0.0),
                "61_90_days": AgingBucket(count=0, amount=0.0),
                "over_90_days": AgingBucket(count=0, amount=0.0),
            }

            days_overdue = func.date_part("day", func.current_date() - cast(Invoice.due_date, Date))
            invoice_balance = func.coalesce(
                Invoice.balance,
                func.coalesce(Invoice.total_amount, 0) - func.coalesce(Invoice.amount_paid, 0),
            )
            aging_bucket = case(
                (days_overdue <= 0, "current"),
                (days_overdue <= 30, "1_30_days"),
                (days_overdue <= 60, "31_60_days"),
                (days_overdue <= 90, "61_90_days"),
                else_="over_90_days",
            )

            overdue_by_bucket = self.db.query(
                aging_bucket.label("bucket"),
                func.count(Invoice.id).label("count"),
                func.sum(invoice_balance).label("amount")
            ).filter(
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID]),
                Invoice.due_date.isnot(None),
                Invoice.is_deleted == False,
                invoice_balance > 0,
            ).group_by(
                aging_bucket
            ).all()

            for row in overdue_by_bucket:
                aging_buckets[row.bucket] = AgingBucket(
                    count=row.count,
                    amount=float(row.amount or 0),
                )

            # Payment method distribution
            payment_methods = self.db.query(
                Payment.payment_method,
                func.count(Payment.id).label("count"),
                func.sum(Payment.amount).label("total")
            ).filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED])
            ).group_by(Payment.payment_method).all()

            # Credit notes impact
            total_credits = self.db.query(func.sum(CreditNote.amount)).filter(
                CreditNote.status.in_(["issued", "applied"])
            ).scalar() or 0

            # Monthly revenue trend
            revenue_trend = self.db.query(
                extract('year', Payment.payment_date).label('year'),
                extract('month', Payment.payment_date).label('month'),
                func.sum(Payment.amount).label('total')
            ).filter(
                Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED]),
                Payment.payment_date.isnot(None),
                Payment.payment_date >= datetime.now(timezone.utc) - timedelta(days=months * 30)
            ).group_by(
                extract('year', Payment.payment_date),
                extract('month', Payment.payment_date)
            ).order_by(
                extract('year', Payment.payment_date),
                extract('month', Payment.payment_date)
            ).all()

            return FinancialInsightsResult(
                mrr={
                    "total": float(total_mrr),
                    "by_customer_type": [
                        {
                            "type": row.segment or "unknown",
                            "mrr": float(row.mrr or 0),
                            "customer_count": row.count,
                            "avg_mrr": round(float(row.mrr or 0) / max(int(getattr(row, "count", 1) or 1), 1), 2),
                        }
                        for row in mrr_by_type
                    ],
                },
                invoice_aging=aging_buckets,
                total_outstanding=sum(b.amount for b in aging_buckets.values()),
                payment_methods=[
                    {
                        "method": row.payment_method.value if row.payment_method else "unknown",
                        "count": row.count,
                        "total": float(row.total or 0),
                    }
                    for row in payment_methods
                ],
                credit_notes_issued=float(total_credits),
                revenue_trend=[
                    {
                        "year": int(row.year),
                        "month": int(row.month),
                        "period": f"{int(row.year)}-{int(row.month):02d}",
                        "revenue": float(row.total or 0),
                    }
                    for row in revenue_trend
                ],
            )
        except Exception as exc:
            logger.exception("financial_insights_failed", extra={"error": str(exc)})
            return FinancialInsightsResult(
                mrr={"error": "financial insights unavailable"},
                invoice_aging={},
                total_outstanding=0.0,
                payment_methods=[],
                credit_notes_issued=0.0,
                revenue_trend=[],
            )

    # =========================================================================
    # OPERATIONAL INSIGHTS
    # =========================================================================

    def get_operational_insights(self, days: int = 30) -> OperationalInsightsResult:
        """Operational metrics including support performance, network utilization, and employee productivity."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Ticket analysis
        ticket_stats = self.db.query(
            func.count(Ticket.id).label("total"),
            func.sum(case((Ticket.status == TicketStatus.RESOLVED, 1), else_=0)).label("resolved"),
            func.avg(case(
                (
                    and_(Ticket.status == TicketStatus.RESOLVED, Ticket.resolution_date.isnot(None)),
                    func.extract('epoch', Ticket.resolution_date - Ticket.created_at) / 3600
                ),
                else_=None
            )).label("avg_resolution_hours"),
        ).filter(
            Ticket.created_at >= since
        ).one()
        total_tickets = int(ticket_stats.total or 0)
        resolved_tickets = int(ticket_stats.resolved or 0)
        avg_resolution_hours = float(ticket_stats.avg_resolution_hours or 0)

        tickets_by_priority_rows = self.db.query(
            Ticket.priority,
            func.count(Ticket.id).label("count")
        ).filter(
            Ticket.created_at >= since
        ).group_by(Ticket.priority).all()
        tickets_by_priority = {
            (row.priority.value if row.priority else "unknown"): row.count
            for row in tickets_by_priority_rows
        }

        # Conversation analysis
        convo_stats = self.db.query(
            func.count(Conversation.id).label("total"),
            func.sum(case((Conversation.status == ConversationStatus.RESOLVED, 1), else_=0)).label("resolved"),
            func.avg(case(
                (
                    and_(Conversation.status == ConversationStatus.RESOLVED, Conversation.first_response_time_seconds.isnot(None)),
                    Conversation.first_response_time_seconds / 3600.0
                ),
                else_=None
            )).label("avg_first_response_hours"),
        ).filter(
            Conversation.created_at >= since
        ).one()
        total_conversations = int(convo_stats.total or 0)
        resolved_convos = int(convo_stats.resolved or 0)
        avg_response_hours = float(convo_stats.avg_first_response_hours or 0)

        by_channel_rows = self.db.query(
            Conversation.channel,
            func.count(Conversation.id).label("count")
        ).filter(
            Conversation.created_at >= since
        ).group_by(Conversation.channel).all()
        by_channel = {row.channel or "unknown": row.count for row in by_channel_rows}

        # Employee productivity (tickets handled)
        employee_tickets = self.db.query(
            Employee.name,
            func.count(Ticket.id).label("ticket_count")
        ).join(
            Ticket, Ticket.assigned_employee_id == Employee.id
        ).filter(
            Ticket.created_at >= since
        ).group_by(Employee.id, Employee.name).order_by(
            func.count(Ticket.id).desc()
        ).limit(10).all()

        # POP utilization
        party_pop = (
            self.db.query(
                Subscription.party_id.label("party_id"),
                func.min(Router.pop_id).label("pop_id"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(Router.pop_id.isnot(None))
            .group_by(Subscription.party_id)
            .subquery()
        )
        active_party_pop = (
            self.db.query(
                Subscription.party_id.label("party_id"),
                func.min(Router.pop_id).label("pop_id"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(
                Router.pop_id.isnot(None),
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .group_by(Subscription.party_id)
            .subquery()
        )

        pop_stats = self.db.query(
            Pop.name,
            Pop.city,
            func.count(distinct(party_pop.c.party_id)).label("customer_count"),
            func.count(distinct(active_party_pop.c.party_id)).label("active_customers"),
        ).outerjoin(
            party_pop, party_pop.c.pop_id == Pop.id
        ).outerjoin(
            active_party_pop, active_party_pop.c.pop_id == Pop.id
        ).group_by(Pop.id, Pop.name, Pop.city).all()

        return OperationalInsightsResult(
            period_days=days,
            tickets=TicketMetrics(
                total=total_tickets,
                resolved=resolved_tickets,
                resolution_rate=round(resolved_tickets / max(total_tickets, 1) * 100, 1),
                avg_resolution_hours=round(avg_resolution_hours, 1),
                by_priority=tickets_by_priority,
            ),
            conversations=ConversationMetrics(
                total=total_conversations,
                resolved=resolved_convos,
                resolution_rate=round(resolved_convos / max(total_conversations, 1) * 100, 1),
                avg_first_response_hours=round(avg_response_hours, 1),
                by_channel=by_channel,
            ),
            employee_productivity=[
                {"name": row.name, "tickets_handled": row.ticket_count}
                for row in employee_tickets
            ],
            pop_utilization=[
                {
                    "name": row.name,
                    "city": row.city,
                    "total_customers": row.customer_count,
                    "active_customers": row.active_customers or 0,
                }
                for row in pop_stats
            ],
        )

    def get_network_health(self) -> NetworkHealthResult:
        """Get summary of network health."""
        # Build the subqueries for POP association
        party_pop = (
            self.db.query(
                Subscription.party_id.label("party_id"),
                func.min(Router.pop_id).label("pop_id"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(Router.pop_id.isnot(None))
            .group_by(Subscription.party_id)
            .subquery()
        )
        active_party_pop = (
            self.db.query(
                Subscription.party_id.label("party_id"),
                func.min(Router.pop_id).label("pop_id"),
            )
            .join(Router, Subscription.router_id == Router.id)
            .filter(
                Router.pop_id.isnot(None),
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .group_by(Subscription.party_id)
            .subquery()
        )

        pop_stats = self.db.query(
            Pop.id,
            Pop.name,
            Pop.city,
            func.count(distinct(party_pop.c.party_id)).label("customers"),
            func.count(distinct(active_party_pop.c.party_id)).label("active_customers"),
        ).outerjoin(
            party_pop, party_pop.c.pop_id == Pop.id
        ).outerjoin(
            active_party_pop, active_party_pop.c.pop_id == Pop.id
        ).group_by(
            Pop.id, Pop.name, Pop.city
        ).order_by(func.count(distinct(party_pop.c.party_id)).desc()).limit(50).all()

        routers = self.db.query(func.count(Router.id)).scalar() or 0
        pops = self.db.query(func.count(Pop.id)).scalar() or 0

        return NetworkHealthResult(
            summary={
                "pops": pops,
                "routers": routers,
                "avg_customers_per_pop": round(
                    (sum(r.customers or 0 for r in pop_stats) / max(len(pop_stats), 1)), 2
                ),
            },
            by_pop=[
                {
                    "id": row.id,
                    "name": row.name,
                    "city": row.city,
                    "customers": row.customers,
                    "active_customers": row.active_customers or 0,
                }
                for row in pop_stats
            ],
        )

    # =========================================================================
    # ANOMALY & PATTERN DETECTION
    # =========================================================================

    def detect_anomalies(self) -> AnomaliesResult:
        """Detect data anomalies and patterns that may indicate issues."""
        anomalies: List[Anomaly] = []
        patterns: List[Pattern] = []

        # Check for customers with subscriptions but no invoices in 90 days
        active_with_sub_no_invoice = self.db.query(CustomerAccount).join(
            Subscription, Subscription.party_id == CustomerAccount.party_id
        ).filter(
            CustomerAccount.status == "active",
            Subscription.status == SubscriptionStatus.ACTIVE
        ).outerjoin(
            Invoice, and_(
                Invoice.customer_account_id == CustomerAccount.id,
                Invoice.invoice_date >= datetime.now(timezone.utc) - timedelta(days=90)
            )
        ).filter(Invoice.id.is_(None)).count()

        if active_with_sub_no_invoice > 0:
            anomalies.append(Anomaly(
                type="billing",
                severity="high",
                description=f"{active_with_sub_no_invoice} active customers with subscriptions but no invoices in 90 days",
                action="Review billing configuration for these customers",
            ))

        # Payments without invoices
        orphan_payments = self.db.query(Payment).filter(
            Payment.invoice_id.is_(None),
            Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.POSTED])
        ).count()

        if orphan_payments > 0:
            patterns.append(Pattern(
                type="payment_pattern",
                description=f"{orphan_payments} completed payments not linked to invoices",
                insight="May indicate advance payments or reconciliation issues",
            ))

        # Customers with many open tickets
        high_ticket_base = self.db.query(
            CustomerAccount.id.label("id"),
            Party.name.label("name"),
            func.count(Ticket.id).label("open_tickets")
        ).join(
            Party, CustomerAccount.party_id == Party.id
        ).join(
            Ticket, Ticket.customer_account_id == CustomerAccount.id
        ).filter(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED])
        ).group_by(CustomerAccount.id, Party.name).having(
            func.count(Ticket.id) >= 5
        )
        high_ticket_sub = high_ticket_base.subquery()
        high_ticket_total = self.db.query(func.count()).select_from(high_ticket_sub).scalar() or 0
        high_ticket_customers = self.db.query(
            high_ticket_sub.c.id,
            high_ticket_sub.c.name,
            high_ticket_sub.c.open_tickets
        ).order_by(
            high_ticket_sub.c.open_tickets.desc()
        ).limit(25).all()

        if high_ticket_total:
            anomalies.append(Anomaly(
                type="support",
                severity="medium",
                description=f"{high_ticket_total} customers have 5+ open tickets",
                customers=[{"id": c.id, "name": c.name, "tickets": c.open_tickets} for c in high_ticket_customers[:5]],
            ))

        # Duplicate customer detection (same email or phone)
        duplicate_email_sub = self.db.query(
            Party.primary_email
        ).filter(
            Party.primary_email.isnot(None),
            Party.primary_email != ""
        ).group_by(Party.primary_email).having(func.count(Party.id) > 1).subquery()
        duplicate_emails = self.db.query(func.count()).select_from(duplicate_email_sub).scalar() or 0

        if duplicate_emails:
            anomalies.append(Anomaly(
                type="data_quality",
                severity="medium",
                description=f"{duplicate_emails} email addresses used by multiple customers",
                action="Review and merge duplicate customer records",
            ))

        duplicate_phone_sub = self.db.query(
            Party.primary_phone
        ).filter(
            Party.primary_phone.isnot(None),
            Party.primary_phone != ""
        ).group_by(Party.primary_phone).having(func.count(Party.id) > 1).subquery()
        duplicate_phones = self.db.query(func.count()).select_from(duplicate_phone_sub).scalar() or 0

        if duplicate_phones:
            anomalies.append(Anomaly(
                type="data_quality",
                severity="low",
                description=f"{duplicate_phones} phone numbers used by multiple customers",
                action="Review potential duplicate records",
            ))

        # Very old unresolved tickets
        old_tickets = self.db.query(Ticket).filter(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.REPLIED]),
            Ticket.created_at < datetime.now(timezone.utc) - timedelta(days=30)
        ).count()

        if old_tickets > 0:
            anomalies.append(Anomaly(
                type="support",
                severity="high",
                description=f"{old_tickets} tickets open for more than 30 days",
                action="Review and escalate stale tickets",
            ))

        # Subscription price anomalies (outliers)
        avg_price = self.db.query(func.avg(Subscription.price)).filter(
            Subscription.price.isnot(None),
            Subscription.price > 0
        ).scalar() or 0

        if avg_price > 0:
            high_price_subs = self.db.query(Subscription).filter(
                Subscription.price > avg_price * 5
            ).count()

            if high_price_subs > 0:
                patterns.append(Pattern(
                    type="pricing",
                    description=f"{high_price_subs} subscriptions with price 5x above average",
                    insight="May be enterprise customers or data entry errors",
                ))

        return AnomaliesResult(
            anomalies=anomalies,
            patterns=patterns,
            summary=AnomalySummary(
                total_anomalies=len(anomalies),
                high_severity=len([a for a in anomalies if a.severity == "high"]),
                medium_severity=len([a for a in anomalies if a.severity == "medium"]),
                low_severity=len([a for a in anomalies if a.severity == "low"]),
            ),
        )

    # =========================================================================
    # DATA AVAILABILITY REPORT
    # =========================================================================

    def get_data_availability(self) -> DataAvailabilityResult:
        """Report on what data is available vs what's needed for comprehensive analytics."""
        # Check data freshness
        latest_sync = self.db.query(func.max(CustomerAccount.created_at)).scalar()

        # Data availability by source
        sources = {
            "splynx": {
                "customers": self.db.query(CustomerAccount).filter(
                    CustomerAccount.external_ids["splynx_id"].astext.isnot(None)
                ).count(),
                "subscriptions": self.db.query(Subscription).filter(Subscription.splynx_id.isnot(None)).count(),
                "invoices": self.db.query(Invoice).filter(Invoice.splynx_id.isnot(None)).count(),
                "payments": self.db.query(Payment).filter(Payment.splynx_id.isnot(None)).count(),
                "tickets": self.db.query(Ticket).filter(Ticket.splynx_id.isnot(None)).count(),
            },
            "erpnext": {
                "customers": self.db.query(CustomerAccount).filter(
                    CustomerAccount.external_ids["erpnext_id"].astext.isnot(None)
                ).count(),
                "invoices": self.db.query(Invoice).filter(Invoice.erpnext_id.isnot(None)).count(),
                "payments": self.db.query(Payment).filter(Payment.erpnext_id.isnot(None)).count(),
                "employees": self.db.query(Employee).filter(Employee.erpnext_id.isnot(None)).count(),
                "tickets": self.db.query(Ticket).filter(Ticket.erpnext_id.isnot(None)).count(),
            },
            "chatwoot": {
                "customers": self.db.query(CustomerAccount).filter(
                    CustomerAccount.external_ids["chatwoot_id"].astext.isnot(None)
                ).count(),
                "conversations": self.db.query(Conversation).filter(Conversation.chatwoot_id.isnot(None)).count(),
            },
        }

        # What data is missing that we need
        missing_data: List[MissingData] = []

        total_customers = self.db.query(CustomerAccount).count()

        # Critical missing data
        no_contact = self.db.query(Party).filter(
            and_(
                or_(Party.primary_email.is_(None), Party.primary_email == ""),
                or_(Party.primary_phone.is_(None), Party.primary_phone == "")
            )
        ).count()

        if no_contact > 0:
            missing_data.append(MissingData(
                entity="customers",
                field="contact_info",
                count=no_contact,
                impact="critical",
                description="Customers without email AND phone - cannot be contacted",
            ))

        no_location = self.db.query(Party).filter(
            func.jsonb_array_length(Party.addresses) == 0
        ).count()

        if no_location > 0:
            missing_data.append(MissingData(
                entity="customers",
                field="location",
                count=no_location,
                impact="high",
                description="Customers without address or GPS coordinates",
            ))

        # Subscriptions without network info
        no_network = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.ipv4_address.is_(None),
            Subscription.mac_address.is_(None)
        ).count()

        if no_network > 0:
            missing_data.append(MissingData(
                entity="subscriptions",
                field="network_assignment",
                count=no_network,
                impact="medium",
                description="Active subscriptions without IP or MAC address",
            ))

        return DataAvailabilityResult(
            last_sync=latest_sync.isoformat() if latest_sync else None,
            data_by_source=sources,
            missing_critical_data=missing_data,
            totals={
                "customers": total_customers,
                "subscriptions": self.db.query(Subscription).count(),
                "invoices": self.db.query(Invoice).count(),
                "payments": self.db.query(Payment).count(),
                "conversations": self.db.query(Conversation).count(),
                "tickets": self.db.query(Ticket).count(),
            },
        )
