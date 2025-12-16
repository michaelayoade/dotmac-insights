"""Auto-matching service for corporate card transactions to expense claim lines."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.models.expense_management import (
    CorporateCardTransaction,
    CorporateCard,
    ExpenseClaim,
    ExpenseClaimLine,
    ExpenseClaimStatus,
    CardTransactionStatus,
    FundingMethod,
)


@dataclass
class MatchCandidate:
    """A potential match between transaction and expense line."""
    transaction_id: int
    expense_claim_line_id: int
    expense_claim_id: int
    confidence: float  # 0.0 to 1.0
    match_reasons: List[str]


@dataclass
class MatchConfig:
    """Configuration for the matching algorithm."""
    # Amount tolerance (percentage, e.g., 0.01 = 1%)
    amount_tolerance_pct: float = 0.01
    # Maximum date difference in days
    max_date_diff_days: int = 7
    # Minimum confidence to auto-match
    auto_match_threshold: float = 0.85
    # Weights for scoring
    weight_amount: float = 0.4
    weight_date: float = 0.25
    weight_employee: float = 0.25
    weight_merchant: float = 0.1


class TransactionMatchingService:
    """
    Auto-matches corporate card transactions to expense claim lines.

    Matching criteria:
    1. Amount: Transaction amount matches expense line (with tolerance)
    2. Date: Transaction date within window of expense date
    3. Employee: Card holder matches expense claim submitter
    4. Merchant: Fuzzy match of merchant names (optional boost)
    """

    def __init__(self, db: Session, config: Optional[MatchConfig] = None):
        self.db = db
        self.config = config or MatchConfig()

    def find_matches_for_transaction(
        self,
        transaction_id: int,
        min_confidence: float = 0.5,
    ) -> List[MatchCandidate]:
        """
        Find potential expense line matches for a single transaction.

        Args:
            transaction_id: ID of the transaction to match
            min_confidence: Minimum confidence score to include

        Returns:
            List of match candidates sorted by confidence (highest first)
        """
        txn = self.db.query(CorporateCardTransaction).options(
            joinedload(CorporateCardTransaction.card)
        ).filter(
            CorporateCardTransaction.id == transaction_id
        ).first()

        if not txn:
            return []

        if txn.status not in (CardTransactionStatus.IMPORTED, CardTransactionStatus.UNMATCHED):
            return []

        return self._find_matches_for_txn(txn, min_confidence)

    def find_all_matches(
        self,
        statement_id: Optional[int] = None,
        card_id: Optional[int] = None,
        min_confidence: float = 0.5,
    ) -> List[MatchCandidate]:
        """
        Find matches for all unmatched transactions.

        Args:
            statement_id: Filter to specific statement
            card_id: Filter to specific card
            min_confidence: Minimum confidence score

        Returns:
            List of all match candidates
        """
        query = self.db.query(CorporateCardTransaction).options(
            joinedload(CorporateCardTransaction.card)
        ).filter(
            CorporateCardTransaction.status.in_([
                CardTransactionStatus.IMPORTED,
                CardTransactionStatus.UNMATCHED,
            ])
        )

        if statement_id:
            query = query.filter(CorporateCardTransaction.statement_id == statement_id)
        if card_id:
            query = query.filter(CorporateCardTransaction.card_id == card_id)

        transactions = query.all()
        all_candidates = []

        for txn in transactions:
            candidates = self._find_matches_for_txn(txn, min_confidence)
            all_candidates.extend(candidates)

        # Sort by confidence descending
        all_candidates.sort(key=lambda c: c.confidence, reverse=True)
        return all_candidates

    def auto_match(
        self,
        statement_id: Optional[int] = None,
        card_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Automatically match transactions above the confidence threshold.

        Args:
            statement_id: Filter to specific statement
            card_id: Filter to specific card
            dry_run: If True, don't actually update records

        Returns:
            Summary of matches made
        """
        candidates = self.find_all_matches(
            statement_id=statement_id,
            card_id=card_id,
            min_confidence=self.config.auto_match_threshold,
        )

        # Track which lines and transactions have been matched
        matched_txns = set()
        matched_lines = set()
        matches_made = []

        for candidate in candidates:
            # Skip if already matched in this run
            if candidate.transaction_id in matched_txns:
                continue
            if candidate.expense_claim_line_id in matched_lines:
                continue

            # Verify line isn't already matched
            line = self.db.query(ExpenseClaimLine).filter(
                ExpenseClaimLine.id == candidate.expense_claim_line_id
            ).first()

            if not line:
                continue

            # Check if line already has a matched transaction
            existing_match = self.db.query(CorporateCardTransaction).filter(
                CorporateCardTransaction.expense_claim_line_id == line.id,
                CorporateCardTransaction.status == CardTransactionStatus.MATCHED,
            ).first()

            if existing_match:
                continue

            if not dry_run:
                txn = self.db.query(CorporateCardTransaction).filter(
                    CorporateCardTransaction.id == candidate.transaction_id
                ).first()

                if txn:
                    txn.expense_claim_line_id = candidate.expense_claim_line_id
                    txn.match_confidence = candidate.confidence
                    txn.status = CardTransactionStatus.MATCHED

            matched_txns.add(candidate.transaction_id)
            matched_lines.add(candidate.expense_claim_line_id)
            matches_made.append(candidate)

        if not dry_run:
            self.db.flush()

        return {
            "matches_made": len(matches_made),
            "dry_run": dry_run,
            "threshold": self.config.auto_match_threshold,
            "matches": [
                {
                    "transaction_id": m.transaction_id,
                    "expense_claim_line_id": m.expense_claim_line_id,
                    "expense_claim_id": m.expense_claim_id,
                    "confidence": round(m.confidence, 3),
                    "reasons": m.match_reasons,
                }
                for m in matches_made
            ],
        }

    def _find_matches_for_txn(
        self,
        txn: CorporateCardTransaction,
        min_confidence: float,
    ) -> List[MatchCandidate]:
        """Find matching expense lines for a transaction."""
        candidates = []

        # Get card holder employee ID
        card = txn.card
        if not card:
            return []

        card_employee_id = card.employee_id

        # Calculate date window
        txn_date = txn.transaction_date.date() if hasattr(txn.transaction_date, 'date') else txn.transaction_date
        date_min = txn_date - timedelta(days=self.config.max_date_diff_days)
        date_max = txn_date + timedelta(days=self.config.max_date_diff_days)

        # Calculate amount window
        txn_amount = abs(txn.amount)
        amount_tolerance = txn_amount * Decimal(str(self.config.amount_tolerance_pct))
        amount_min = txn_amount - amount_tolerance
        amount_max = txn_amount + amount_tolerance

        # Query potential matching expense lines
        # - From approved/posted claims
        # - With corporate_card funding method
        # - Within date window
        # - Within amount window
        # - Not already matched to a transaction

        lines = self.db.query(ExpenseClaimLine).join(
            ExpenseClaim, ExpenseClaimLine.expense_claim_id == ExpenseClaim.id
        ).filter(
            ExpenseClaim.status.in_([
                ExpenseClaimStatus.APPROVED,
                ExpenseClaimStatus.POSTED,
                ExpenseClaimStatus.PAID,
            ]),
            ExpenseClaimLine.funding_method == FundingMethod.CORPORATE_CARD,
            ExpenseClaimLine.expense_date >= date_min,
            ExpenseClaimLine.expense_date <= date_max,
            ExpenseClaimLine.claimed_amount >= amount_min,
            ExpenseClaimLine.claimed_amount <= amount_max,
        ).options(
            joinedload(ExpenseClaimLine.claim)
        ).all()

        for line in lines:
            claim = line.claim

            # Check if line already matched
            existing_match = self.db.query(CorporateCardTransaction).filter(
                CorporateCardTransaction.expense_claim_line_id == line.id,
                CorporateCardTransaction.status == CardTransactionStatus.MATCHED,
            ).first()

            if existing_match:
                continue

            # Calculate match score
            confidence, reasons = self._calculate_match_score(
                txn, txn_date, txn_amount, card_employee_id,
                line, claim,
            )

            if confidence >= min_confidence:
                candidates.append(MatchCandidate(
                    transaction_id=txn.id,
                    expense_claim_line_id=line.id,
                    expense_claim_id=claim.id,
                    confidence=confidence,
                    match_reasons=reasons,
                ))

        # Sort by confidence
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    def _calculate_match_score(
        self,
        txn: CorporateCardTransaction,
        txn_date: date,
        txn_amount: Decimal,
        card_employee_id: int,
        line: ExpenseClaimLine,
        claim: ExpenseClaim,
    ) -> Tuple[float, List[str]]:
        """Calculate confidence score for a potential match."""
        scores = []
        reasons = []

        # 1. Amount score
        line_amount = abs(line.claimed_amount)
        if line_amount > 0:
            amount_diff = abs(txn_amount - line_amount)
            amount_diff_pct = float(amount_diff / line_amount)

            if amount_diff_pct == 0:
                amount_score = 1.0
                reasons.append("Exact amount match")
            elif amount_diff_pct <= self.config.amount_tolerance_pct:
                amount_score = 1.0 - (amount_diff_pct / self.config.amount_tolerance_pct) * 0.2
                reasons.append(f"Amount within {amount_diff_pct*100:.1f}% tolerance")
            else:
                amount_score = 0.0
        else:
            amount_score = 0.0

        scores.append((amount_score, self.config.weight_amount))

        # 2. Date score
        date_diff = abs((txn_date - line.expense_date).days)
        if date_diff == 0:
            date_score = 1.0
            reasons.append("Same date")
        elif date_diff <= self.config.max_date_diff_days:
            date_score = 1.0 - (date_diff / self.config.max_date_diff_days)
            reasons.append(f"Date diff: {date_diff} days")
        else:
            date_score = 0.0

        scores.append((date_score, self.config.weight_date))

        # 3. Employee score
        if claim.employee_id == card_employee_id:
            employee_score = 1.0
            reasons.append("Same employee")
        else:
            employee_score = 0.0

        scores.append((employee_score, self.config.weight_employee))

        # 4. Merchant similarity (optional boost)
        merchant_score = 0.0
        if txn.merchant_name and line.merchant_name:
            similarity = self._string_similarity(
                txn.merchant_name.lower(),
                line.merchant_name.lower(),
            )
            if similarity >= 0.8:
                merchant_score = similarity
                reasons.append(f"Merchant match: {similarity*100:.0f}%")
            elif similarity >= 0.5:
                merchant_score = similarity * 0.5
                reasons.append(f"Partial merchant match: {similarity*100:.0f}%")

        scores.append((merchant_score, self.config.weight_merchant))

        # Calculate weighted average
        total_weight = sum(w for _, w in scores)
        if total_weight > 0:
            confidence = sum(s * w for s, w in scores) / total_weight
        else:
            confidence = 0.0

        return confidence, reasons

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity ratio."""
        return SequenceMatcher(None, s1, s2).ratio()


def suggest_matches_endpoint_helper(
    db: Session,
    transaction_id: Optional[int] = None,
    statement_id: Optional[int] = None,
    card_id: Optional[int] = None,
    min_confidence: float = 0.5,
) -> dict:
    """Helper function for API endpoint to suggest matches."""
    service = TransactionMatchingService(db)

    if transaction_id:
        candidates = service.find_matches_for_transaction(
            transaction_id, min_confidence
        )
    else:
        candidates = service.find_all_matches(
            statement_id=statement_id,
            card_id=card_id,
            min_confidence=min_confidence,
        )

    return {
        "total": len(candidates),
        "min_confidence": min_confidence,
        "candidates": [
            {
                "transaction_id": c.transaction_id,
                "expense_claim_line_id": c.expense_claim_line_id,
                "expense_claim_id": c.expense_claim_id,
                "confidence": round(c.confidence, 3),
                "reasons": c.match_reasons,
            }
            for c in candidates
        ],
    }
