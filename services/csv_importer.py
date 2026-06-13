"""
csv_importer.py — The core CSV import pipeline.

This module parses expenses_export.csv and applies 14 anomaly detection rules.
Each anomaly is recorded as an ImportAnomaly row for user review.

Policy summary (full details in SCOPE.md):
  DUPLICATE            → Flag for user decision; suggested action = ASK_USER
  NEGATIVE_AMOUNT      → Treat as refund; import as negative expense; flag it
  CURRENCY_USD         → Convert at documented rate; flag conversion
  SETTLEMENT_AS_EXPENSE→ Reclassify as Settlement record; skip expense creation
  POST_DEPARTURE       → Exclude departed member from split; flag it
  PRE_JOIN             → Exclude pre-join member from split; flag it
  MISSING_PAID_BY      → Hold in pending; require user to assign before finalising
  UNKNOWN_MEMBER       → Create read-only guest user; flag for merge
  INCONSISTENT_DATE    → Parse with dateutil; normalise; flag original format
  AMOUNT_WITH_SYMBOL   → Strip ₹ $ , ; parse as float; flag it
  WRONG_SPLIT_LABEL    → Normalise to canonical label; flag it
  ZERO_AMOUNT          → Skip; log as warning
  FUTURE_DATE          → Import with warning flag
  BAD_PERCENTAGE_SUM   → Normalise to 100 %; flag it
"""

import csv
import json
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO

from dateutil import parser as dateutil_parser
from sqlalchemy import or_

from models import (
    db, User, Group, GroupMember, Expense, ExpenseSplit,
    Settlement, ImportSession, ImportAnomaly,
)
from services.fx import convert_to_inr

# Members who are "permanent" flatmates (not guests)
# This list is populated from the DB at import time
SETTLEMENT_KEYWORDS = [
    "pays back", "pay back", "settles", "settlement", "repays",
    "reimburse", "transfer", "owes back",
]

# Canonical split type mappings
SPLIT_LABEL_MAP = {
    "50/50": "equal",
    "50-50": "equal",
    "half": "equal",
    "halves": "equal",
    "even": "equal",
    "split equally": "equal",
    "equal split": "equal",
    "by percentage": "percentage",
    "percent": "percentage",
    "by shares": "shares",
    "share": "shares",
    "exact amounts": "exact",
    "fixed": "exact",
}

TODAY = date.today()


def _clean_amount(raw: str) -> tuple[float | None, list[str]]:
    """
    Strip currency symbols and commas from an amount string.
    Returns (float_value, list_of_warnings).
    """
    warnings = []
    if not raw or not str(raw).strip():
        return None, ["Amount field is empty"]

    original = str(raw).strip()
    cleaned = original

    # Detect and strip known currency symbols
    if any(sym in cleaned for sym in ["₹", "$", "£", "€"]):
        warnings.append(f"AMOUNT_WITH_SYMBOL: stripped currency symbol from '{original}'")
        cleaned = re.sub(r"[₹$£€]", "", cleaned)

    # Remove commas (e.g. 1,200)
    cleaned = cleaned.replace(",", "").strip()

    try:
        val = float(cleaned)
        return val, warnings
    except ValueError:
        return None, [f"Cannot parse amount: '{original}'"]


def _parse_date(raw: str) -> tuple[date | None, list[str]]:
    """
    Parse a date string in any format using dateutil.
    Returns (date, list_of_warnings).
    """
    warnings = []
    if not raw or not str(raw).strip():
        return None, ["Date field is empty"]

    original = str(raw).strip()

    # Detect non-ISO formats
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not iso_pattern.match(original):
        warnings.append(f"INCONSISTENT_DATE: non-ISO date format '{original}' normalised")

    try:
        parsed = dateutil_parser.parse(original, dayfirst=False)
        return parsed.date(), warnings
    except Exception:
        try:
            parsed = dateutil_parser.parse(original, dayfirst=True)
            return parsed.date(), warnings + [f"Date '{original}' parsed with dayfirst=True"]
        except Exception:
            return None, [f"Cannot parse date: '{original}'"]


def _normalise_split_type(raw: str) -> tuple[str, list[str]]:
    """Normalise split type to canonical label."""
    warnings = []
    if not raw:
        return "equal", []
    cleaned = raw.strip().lower()
    if cleaned in ("equal", "exact", "percentage", "shares"):
        return cleaned, []
    if cleaned in SPLIT_LABEL_MAP:
        canonical = SPLIT_LABEL_MAP[cleaned]
        warnings.append(f"WRONG_SPLIT_LABEL: '{raw}' normalised to '{canonical}'")
        return canonical, warnings
    warnings.append(f"WRONG_SPLIT_LABEL: unknown split type '{raw}', defaulting to 'equal'")
    return "equal", warnings


def _is_settlement_description(description: str) -> bool:
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in SETTLEMENT_KEYWORDS)


def _parse_split_details(raw: str) -> dict:
    """Parse 'Name:value,Name:value' into {name: value}."""
    result = {}
    if not raw or not str(raw).strip():
        return result
    for part in str(raw).split(","):
        part = part.strip()
        if ":" in part:
            name, val = part.split(":", 1)
            try:
                result[name.strip()] = float(val.strip())
            except ValueError:
                pass
    return result


def run_import(file_content: str, group_id: int, session_id: int) -> dict:
    """
    Main import function. Processes a CSV string and returns a summary.

    Args:
        file_content: raw CSV text
        group_id: target group
        session_id: ImportSession.id (already created by caller)

    Returns:
        dict with counts and anomaly list
    """
    session = ImportSession.query.get(session_id)
    group = Group.query.get(group_id)

    reader = csv.DictReader(StringIO(file_content))
    rows = list(reader)
    session.total_rows = len(rows)

    # Build name→User lookup (case-insensitive)
    all_users = User.query.all()
    user_by_name = {u.display_name.lower(): u for u in all_users}

    # Build membership timeline for this group
    memberships = GroupMember.query.filter_by(group_id=group_id).all()

    imported = 0
    skipped = 0
    pending = 0
    anomalies_created = []

    # Track descriptions already seen for duplicate detection
    seen_descriptions = {}  # description → list of (row_num, amount)

    for row_num, row in enumerate(rows, start=2):  # start=2 because row 1 is header
        row_anomalies = []
        skip_row = False
        pending_review = False

        raw_date = row.get("date", "").strip()
        raw_amount = row.get("amount", "").strip()
        raw_currency = row.get("currency", "INR").strip() or "INR"
        raw_description = row.get("description", "").strip()
        raw_paid_by = row.get("paid_by", "").strip()
        raw_split_type = row.get("split_type", "equal").strip()
        raw_split_details = row.get("split_details", "").strip()

        # ── Rule 1: MISSING_PAID_BY ────────────────────────────────────────
        if not raw_paid_by:
            row_anomalies.append(("MISSING_PAID_BY",
                "paid_by field is blank — cannot assign payer",
                "PENDING_REVIEW"))
            pending_review = True

        # ── Rule 2: AMOUNT_WITH_SYMBOL / amount parsing ────────────────────
        amount_val, amount_warnings = _clean_amount(raw_amount)
        for w in amount_warnings:
            if "AMOUNT_WITH_SYMBOL" in w:
                row_anomalies.append(("AMOUNT_WITH_SYMBOL", w, "AUTO_FIXED"))
            elif "Cannot parse" in w:
                row_anomalies.append(("AMOUNT_WITH_SYMBOL", w, "SKIP"))
                skip_row = True

        if amount_val is None and not skip_row:
            skip_row = True

        # ── Rule 3: ZERO_AMOUNT ────────────────────────────────────────────
        if amount_val is not None and amount_val == 0:
            row_anomalies.append(("ZERO_AMOUNT",
                f"Amount is zero for '{raw_description}' — skipping row",
                "SKIP"))
            skip_row = True

        # ── Rule 4: NEGATIVE_AMOUNT ────────────────────────────────────────
        is_refund = False
        if amount_val is not None and amount_val < 0:
            row_anomalies.append(("NEGATIVE_AMOUNT",
                f"Negative amount {amount_val} for '{raw_description}' — treating as refund",
                "IMPORT_AS_REFUND"))
            is_refund = True

        # ── Rule 5: DATE parsing ───────────────────────────────────────────
        parsed_date, date_warnings = _parse_date(raw_date)
        for w in date_warnings:
            if "INCONSISTENT_DATE" in w:
                row_anomalies.append(("INCONSISTENT_DATE", w, "AUTO_FIXED"))
        if parsed_date is None:
            row_anomalies.append(("INCONSISTENT_DATE",
                f"Cannot parse date '{raw_date}' — skipping row",
                "SKIP"))
            skip_row = True

        # ── Rule 6: FUTURE_DATE ────────────────────────────────────────────
        if parsed_date and parsed_date > TODAY:
            row_anomalies.append(("FUTURE_DATE",
                f"Expense dated {parsed_date} is in the future",
                "IMPORT_WITH_FLAG"))

        # ── Rule 7: CURRENCY_USD ───────────────────────────────────────────
        is_usd = False
        if raw_currency.upper() == "USD":
            is_usd = True
            row_anomalies.append(("CURRENCY_USD",
                f"Amount {amount_val} USD will be converted to INR at documented rate",
                "AUTO_CONVERT"))

        # ── Rule 8: SETTLEMENT_AS_EXPENSE ─────────────────────────────────
        is_settlement = _is_settlement_description(raw_description)
        if is_settlement:
            row_anomalies.append(("SETTLEMENT_AS_EXPENSE",
                f"'{raw_description}' looks like a settlement, not an expense — reclassifying",
                "RECLASSIFY_AS_SETTLEMENT"))

        # ── Rule 9: WRONG_SPLIT_LABEL ──────────────────────────────────────
        split_type, split_warnings = _normalise_split_type(raw_split_type)
        for w in split_warnings:
            row_anomalies.append(("WRONG_SPLIT_LABEL", w, "AUTO_FIXED"))

        # ── Rule 10: UNKNOWN_MEMBER ────────────────────────────────────────
        paid_by_user = None
        if raw_paid_by:
            paid_by_user = user_by_name.get(raw_paid_by.lower())
            if paid_by_user is None:
                # Create a guest account
                row_anomalies.append(("UNKNOWN_MEMBER",
                    f"'{raw_paid_by}' is not a registered member — created as guest user",
                    "CREATE_GUEST"))

        # ── Rule 11: DUPLICATE ────────────────────────────────────────────
        desc_key = raw_description.lower().strip()
        if desc_key and amount_val is not None:
            if desc_key in seen_descriptions:
                prev_row, prev_amount = seen_descriptions[desc_key]
                row_anomalies.append(("DUPLICATE",
                    f"'{raw_description}' (₹{amount_val}) appears to duplicate row {prev_row} (₹{prev_amount}). "
                    "User must decide which to keep.",
                    "PENDING_REVIEW"))
                pending_review = True
            else:
                seen_descriptions[desc_key] = (row_num, amount_val)

        # ── Rule 12: MEMBERSHIP checks (POST_DEPARTURE / PRE_JOIN) ────────
        excluded_members = []
        if parsed_date:
            for m in memberships:
                member_name = m.user.display_name.lower()
                # Check if member was not active on expense date
                if m.joined_at > parsed_date:
                    excluded_members.append(m.user)
                    row_anomalies.append(("PRE_JOIN",
                        f"{m.user.display_name} joined on {m.joined_at} but expense date is {parsed_date} — excluded from split",
                        "EXCLUDE_FROM_SPLIT"))
                elif m.left_at and m.left_at < parsed_date:
                    excluded_members.append(m.user)
                    row_anomalies.append(("POST_DEPARTURE",
                        f"{m.user.display_name} left on {m.left_at} but expense date is {parsed_date} — excluded from split",
                        "EXCLUDE_FROM_SPLIT"))

        # ── Rule 13: BAD_PERCENTAGE_SUM ───────────────────────────────────
        split_details_parsed = _parse_split_details(raw_split_details)
        if split_type == "percentage" and split_details_parsed:
            total_pct = sum(split_details_parsed.values())
            if abs(total_pct - 100.0) > 0.01:
                row_anomalies.append(("BAD_PERCENTAGE_SUM",
                    f"Percentages sum to {total_pct:.1f}% (not 100%) — normalised proportionally",
                    "AUTO_NORMALIZE"))
                # Normalise
                split_details_parsed = {k: v / total_pct * 100 for k, v in split_details_parsed.items()}

        # ── Record anomalies ───────────────────────────────────────────────
        raw_row_json = json.dumps(dict(row))
        for a_type, a_desc, a_action in row_anomalies:
            anomaly = ImportAnomaly(
                session_id=session_id,
                row_number=row_num,
                raw_row=raw_row_json,
                anomaly_type=a_type,
                description=a_desc,
                suggested_action=a_action,
                resolved=False,
            )
            db.session.add(anomaly)
            anomalies_created.append(anomaly)

        # ── Skip or defer ─────────────────────────────────────────────────
        if skip_row:
            skipped += 1
            db.session.flush()
            continue

        if pending_review:
            pending += 1
            db.session.flush()
            continue

        # ── Convert currency ───────────────────────────────────────────────
        amount_inr, fx_rate = convert_to_inr(abs(amount_val), raw_currency, parsed_date)
        if is_refund:
            amount_inr = -amount_inr

        # ── Resolve or create paid_by user ────────────────────────────────
        if paid_by_user is None and raw_paid_by:
            paid_by_user = _get_or_create_guest(raw_paid_by, user_by_name)

        # ── Handle settlement reclassification ────────────────────────────
        if is_settlement and split_details_parsed and paid_by_user:
            for payee_name, amt in split_details_parsed.items():
                payee = user_by_name.get(payee_name.lower())
                if payee:
                    settlement = Settlement(
                        group_id=group_id,
                        payer_id=paid_by_user.id,
                        payee_id=payee.id,
                        amount_inr=Decimal(str(amt)),
                        date=parsed_date,
                        notes=f"Imported from CSV row {row_num}: {raw_description}",
                    )
                    db.session.add(settlement)
            imported += 1
            db.session.flush()
            continue

        # ── Create expense record ─────────────────────────────────────────
        expense = Expense(
            group_id=group_id,
            description=raw_description,
            amount_inr=Decimal(str(amount_inr)),
            original_amount=Decimal(str(abs(amount_val))),
            original_currency=raw_currency.upper(),
            fx_rate_used=Decimal(str(fx_rate)),
            date=parsed_date,
            paid_by_id=paid_by_user.id if paid_by_user else None,
            split_type=split_type,
            is_settlement=False,
            import_source="csv_import",
            import_session_id=session_id,
            notes="; ".join(a[1] for a in row_anomalies) if row_anomalies else "",
        )
        db.session.add(expense)
        db.session.flush()  # get expense.id

        # ── Compute splits ────────────────────────────────────────────────
        # Active members on expense date, minus excluded members
        active_members = group.active_members_on(parsed_date) if parsed_date else []
        excluded_ids = {u.id for u in excluded_members}
        split_members = [u for u in active_members if u.id not in excluded_ids]

        # If paid_by user is not in the group, still include them
        if paid_by_user and paid_by_user not in split_members and paid_by_user not in excluded_members:
            split_members.append(paid_by_user)

        if not split_members:
            split_members = active_members if active_members else [paid_by_user] if paid_by_user else []

        _create_splits(expense, split_type, split_details_parsed, split_members, user_by_name)

        imported += 1
        db.session.flush()

    # Finalise session
    session.imported_count = imported
    session.skipped_count = skipped
    session.pending_review_count = pending
    session.status = "complete"
    db.session.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "pending_review": pending,
        "anomalies": len(anomalies_created),
    }


def _get_or_create_guest(name: str, user_by_name: dict) -> User:
    """Return existing user or create a guest account with the given display name."""
    key = name.lower()
    if key in user_by_name:
        return user_by_name[key]
    guest = User(
        username=f"guest_{name.lower().replace(' ', '_')}",
        display_name=name,
        password_hash="GUEST_NO_LOGIN",
    )
    db.session.add(guest)
    db.session.flush()
    user_by_name[key] = guest
    return guest


def _create_splits(expense: Expense, split_type: str, split_details: dict,
                   members: list, user_by_name: dict):
    """
    Create ExpenseSplit rows for an expense.
    """
    total = float(expense.amount_inr)
    n = len(members)
    if n == 0:
        return

    if split_type == "equal":
        per_person = Decimal(str(total / n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Distribute rounding remainder to first member
        total_distributed = per_person * n
        remainder = Decimal(str(total)).quantize(Decimal("0.01")) - total_distributed

        for i, user in enumerate(members):
            amt = per_person + (remainder if i == 0 else Decimal("0"))
            db.session.add(ExpenseSplit(
                expense_id=expense.id,
                user_id=user.id,
                amount_owed=amt,
                split_value=None,
            ))

    elif split_type == "percentage":
        if split_details:
            for name, pct in split_details.items():
                user = user_by_name.get(name.lower())
                if user:
                    amt = Decimal(str(total * pct / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    db.session.add(ExpenseSplit(
                        expense_id=expense.id,
                        user_id=user.id,
                        amount_owed=amt,
                        split_value=Decimal(str(pct)),
                    ))
        else:
            # Fall back to equal
            _create_splits(expense, "equal", {}, members, user_by_name)

    elif split_type == "exact":
        if split_details:
            for name, amt in split_details.items():
                user = user_by_name.get(name.lower())
                if user:
                    db.session.add(ExpenseSplit(
                        expense_id=expense.id,
                        user_id=user.id,
                        amount_owed=Decimal(str(amt)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                        split_value=Decimal(str(amt)),
                    ))
        else:
            _create_splits(expense, "equal", {}, members, user_by_name)

    elif split_type == "shares":
        if split_details:
            total_shares = sum(split_details.values())
            for name, shares in split_details.items():
                user = user_by_name.get(name.lower())
                if user and total_shares > 0:
                    amt = Decimal(str(total * shares / total_shares)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    db.session.add(ExpenseSplit(
                        expense_id=expense.id,
                        user_id=user.id,
                        amount_owed=amt,
                        split_value=Decimal(str(shares)),
                    ))
        else:
            _create_splits(expense, "equal", {}, members, user_by_name)
