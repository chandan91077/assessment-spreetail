"""routes/settlements.py — Record and list debt settlements."""

from datetime import date
from decimal import Decimal
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Settlement, Group, User

settlements_bp = Blueprint("settlements", __name__, url_prefix="/api/settlements")


@settlements_bp.route("/group/<int:group_id>", methods=["GET"])
@login_required
def list_settlements(group_id):
    Group.query.get_or_404(group_id)
    settlements = (
        Settlement.query
        .filter_by(group_id=group_id)
        .order_by(Settlement.date.desc())
        .all()
    )
    return jsonify({"settlements": [s.to_dict() for s in settlements]})


@settlements_bp.route("/", methods=["POST"])
@login_required
def create_settlement():
    data = request.get_json()
    group_id = data.get("group_id")
    payer_id = data.get("payer_id")
    payee_id = data.get("payee_id")
    amount = data.get("amount")
    settlement_date_str = data.get("date")
    notes = (data.get("notes") or "").strip()

    if not all([group_id, payer_id, payee_id, amount]):
        return jsonify({"error": "group_id, payer_id, payee_id, and amount are required"}), 400

    if payer_id == payee_id:
        return jsonify({"error": "Payer and payee cannot be the same person"}), 400

    Group.query.get_or_404(group_id)
    User.query.get_or_404(payer_id)
    User.query.get_or_404(payee_id)

    settlement_date = date.fromisoformat(settlement_date_str) if settlement_date_str else date.today()

    settlement = Settlement(
        group_id=group_id,
        payer_id=payer_id,
        payee_id=payee_id,
        amount_inr=Decimal(str(amount)),
        date=settlement_date,
        notes=notes,
    )
    db.session.add(settlement)
    db.session.commit()
    return jsonify({"settlement": settlement.to_dict()}), 201


@settlements_bp.route("/<int:settlement_id>", methods=["DELETE"])
@login_required
def delete_settlement(settlement_id):
    settlement = Settlement.query.get_or_404(settlement_id)
    db.session.delete(settlement)
    db.session.commit()
    return jsonify({"message": "Settlement deleted"})


@settlements_bp.route("/group/<int:group_id>/balances", methods=["GET"])
@login_required
def group_balances(group_id):
    """Return net balances and minimal-transactions settlement plan."""
    Group.query.get_or_404(group_id)
    from services.balance_calculator import compute_group_balances, compute_minimal_transactions
    balances = compute_group_balances(group_id)
    transactions = compute_minimal_transactions(balances)
    return jsonify({
        "balances": balances,
        "suggested_settlements": transactions,
    })
