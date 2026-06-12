"""routes/expenses.py — CRUD for expenses and split management."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Expense, ExpenseSplit, Group, GroupMember, User

expenses_bp = Blueprint("expenses", __name__, url_prefix="/api/expenses")


@expenses_bp.route("/group/<int:group_id>", methods=["GET"])
@login_required
def list_expenses(group_id):
    Group.query.get_or_404(group_id)
    expenses = (
        Expense.query
        .filter_by(group_id=group_id, is_settlement=False)
        .order_by(Expense.date.desc())
        .all()
    )
    return jsonify({"expenses": [e.to_dict() for e in expenses]})


@expenses_bp.route("/", methods=["POST"])
@login_required
def create_expense():
    data = request.get_json()
    group_id = data.get("group_id")
    description = (data.get("description") or "").strip()
    amount = data.get("amount")
    currency = (data.get("currency") or "INR").strip().upper()
    expense_date_str = data.get("date")
    paid_by_id = data.get("paid_by_id")
    split_type = (data.get("split_type") or "equal").strip().lower()
    split_details = data.get("split_details", {})  # {user_id: value}

    if not all([group_id, description, amount, paid_by_id]):
        return jsonify({"error": "group_id, description, amount, and paid_by_id are required"}), 400

    Group.query.get_or_404(group_id)
    User.query.get_or_404(paid_by_id)

    expense_date = date.fromisoformat(expense_date_str) if expense_date_str else date.today()

    # FX conversion
    from services.fx import convert_to_inr
    amount_inr, fx_rate = convert_to_inr(float(amount), currency, expense_date)

    expense = Expense(
        group_id=group_id,
        description=description,
        amount_inr=Decimal(str(amount_inr)),
        original_amount=Decimal(str(amount)),
        original_currency=currency,
        fx_rate_used=Decimal(str(fx_rate)),
        date=expense_date,
        paid_by_id=paid_by_id,
        split_type=split_type,
        import_source="manual",
    )
    db.session.add(expense)
    db.session.flush()

    # Compute splits
    group = Group.query.get(group_id)
    active_members = group.active_members_on(expense_date)

    _compute_and_save_splits(expense, split_type, split_details, active_members)
    db.session.commit()

    return jsonify({"expense": expense.to_dict()}), 201


@expenses_bp.route("/<int:expense_id>", methods=["GET"])
@login_required
def get_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    return jsonify({"expense": expense.to_dict()})


@expenses_bp.route("/<int:expense_id>", methods=["PUT"])
@login_required
def update_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    data = request.get_json()

    expense.description = data.get("description", expense.description).strip()
    if "amount" in data:
        currency = data.get("currency", expense.original_currency)
        from services.fx import convert_to_inr
        amount_inr, fx_rate = convert_to_inr(float(data["amount"]), currency, expense.date)
        expense.amount_inr = Decimal(str(amount_inr))
        expense.original_amount = Decimal(str(data["amount"]))
        expense.original_currency = currency
        expense.fx_rate_used = Decimal(str(fx_rate))
    if "date" in data:
        expense.date = date.fromisoformat(data["date"])
    if "paid_by_id" in data:
        expense.paid_by_id = data["paid_by_id"]
    if "split_type" in data:
        expense.split_type = data["split_type"]

    # Recompute splits
    if "split_details" in data or "split_type" in data:
        ExpenseSplit.query.filter_by(expense_id=expense_id).delete()
        group = Group.query.get(expense.group_id)
        active_members = group.active_members_on(expense.date)
        _compute_and_save_splits(expense, expense.split_type, data.get("split_details", {}), active_members)

    db.session.commit()
    return jsonify({"expense": expense.to_dict()})


@expenses_bp.route("/<int:expense_id>", methods=["DELETE"])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    return jsonify({"message": "Expense deleted"})


def _compute_and_save_splits(expense, split_type, split_details, members):
    """Helper: compute and persist splits for a manually created expense."""
    total = float(expense.amount_inr)
    n = len(members)
    if n == 0:
        return

    user_by_id = {u.id: u for u in members}

    if split_type == "equal":
        per_person = Decimal(str(total / n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_distributed = per_person * n
        remainder = Decimal(str(total)).quantize(Decimal("0.01")) - total_distributed
        for i, user in enumerate(members):
            amt = per_person + (remainder if i == 0 else Decimal("0"))
            db.session.add(ExpenseSplit(
                expense_id=expense.id, user_id=user.id,
                amount_owed=amt, split_value=None,
            ))

    elif split_type == "percentage":
        # split_details: {user_id: percentage}
        total_pct = sum(float(v) for v in split_details.values())
        if total_pct == 0:
            return _compute_and_save_splits(expense, "equal", {}, members)
        for uid_str, pct in split_details.items():
            uid = int(uid_str)
            if uid in user_by_id:
                amt = Decimal(str(total * float(pct) / total_pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                db.session.add(ExpenseSplit(
                    expense_id=expense.id, user_id=uid,
                    amount_owed=amt, split_value=Decimal(str(pct)),
                ))

    elif split_type == "exact":
        for uid_str, amt in split_details.items():
            uid = int(uid_str)
            db.session.add(ExpenseSplit(
                expense_id=expense.id, user_id=uid,
                amount_owed=Decimal(str(amt)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                split_value=Decimal(str(amt)),
            ))

    elif split_type == "shares":
        total_shares = sum(float(v) for v in split_details.values())
        if total_shares == 0:
            return _compute_and_save_splits(expense, "equal", {}, members)
        for uid_str, shares in split_details.items():
            uid = int(uid_str)
            if uid in user_by_id:
                amt = Decimal(str(total * float(shares) / total_shares)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                db.session.add(ExpenseSplit(
                    expense_id=expense.id, user_id=uid,
                    amount_owed=amt, split_value=Decimal(str(shares)),
                ))
