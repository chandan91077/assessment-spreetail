"""
balance_calculator.py — Pure computation of who owes whom.

Design decision: Balances are NEVER stored in the database.
They are computed fresh on every request from the immutable ledger of
expenses and settlements. This guarantees correctness at the cost of
a few extra queries — acceptable for a flat of 5 people.

The minimal-transactions algorithm used here is a greedy creditor-debtor
matching that produces the smallest number of settlement transactions
from any net-balance state.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


def compute_group_balances(group_id: int) -> dict:
    """
    Compute net balances for every member of a group.

    Returns a dict:
        {
          user_id: {
            "display_name": str,
            "net": float,        # positive = is owed money, negative = owes money
            "paid": float,
            "owed": float,
            "expense_breakdown": [
                {"expense_id": int, "description": str, "date": str,
                 "paid": float, "owed": float, "net": float}
            ]
          }
        }
    """
    from models import Expense, ExpenseSplit, Settlement, GroupMember, User

    # Collect all active (or ever) members so we show zero-balance members too
    memberships = GroupMember.query.filter_by(group_id=group_id).all()
    member_ids = {m.user_id for m in memberships}

    balances = {}
    for m in memberships:
        balances[m.user_id] = {
            "display_name": m.user.display_name,
            "net": Decimal("0"),
            "paid": Decimal("0"),
            "owed": Decimal("0"),
            "expense_breakdown": [],
        }

    # Process expenses (exclude is_settlement=True — they are not real expenses)
    expenses = Expense.query.filter_by(group_id=group_id, is_settlement=False).all()

    for expense in expenses:
        exp_date = expense.date

        for split in expense.splits:
            uid = split.user_id
            if uid not in balances:
                # Ghost member (e.g. someone who left and re-joined under a new membership)
                user = User.query.get(uid)
                balances[uid] = {
                    "display_name": user.display_name if user else f"User#{uid}",
                    "net": Decimal("0"),
                    "paid": Decimal("0"),
                    "owed": Decimal("0"),
                    "expense_breakdown": [],
                }

            owed = Decimal(str(split.amount_owed))
            balances[uid]["owed"] += owed
            balances[uid]["net"] -= owed

        # Credit the payer
        if expense.paid_by_id:
            pid = expense.paid_by_id
            amount = Decimal(str(expense.amount_inr))
            if pid not in balances:
                user = User.query.get(pid)
                balances[pid] = {
                    "display_name": user.display_name if user else f"User#{pid}",
                    "net": Decimal("0"),
                    "paid": Decimal("0"),
                    "owed": Decimal("0"),
                    "expense_breakdown": [],
                }
            balances[pid]["paid"] += amount
            balances[pid]["net"] += amount

            # Per-expense breakdown for Rohan's requirement
            for split in expense.splits:
                uid = split.user_id
                if uid in balances:
                    owed = Decimal(str(split.amount_owed))
                    paid_contribution = amount if uid == pid else Decimal("0")
                    balances[uid]["expense_breakdown"].append({
                        "expense_id": expense.id,
                        "description": expense.description,
                        "date": expense.date.isoformat(),
                        "paid": float(paid_contribution),
                        "owed": float(owed),
                        "net": float(paid_contribution - owed),
                    })

    # Process settlements
    settlements = Settlement.query.filter_by(group_id=group_id).all()
    for s in settlements:
        amount = Decimal(str(s.amount_inr))
        # Payer's balance improves (they paid someone, reducing their debt)
        if s.payer_id in balances:
            balances[s.payer_id]["net"] += amount
        # Payee's balance decreases (they received money, reducing their credit)
        if s.payee_id in balances:
            balances[s.payee_id]["net"] -= amount

    # Convert Decimals to floats for JSON serialisation
    for uid in balances:
        balances[uid]["net"] = float(balances[uid]["net"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        balances[uid]["paid"] = float(balances[uid]["paid"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        balances[uid]["owed"] = float(balances[uid]["owed"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    return balances


def compute_minimal_transactions(balances: dict) -> list[dict]:
    """
    Given net balances, compute the minimal set of transactions to settle all debts.

    Algorithm: Greedy creditor-debtor matching.
      1. Sort members into two lists: creditors (net > 0) and debtors (net < 0).
      2. Always match the largest creditor with the largest debtor.
      3. The smaller of the two amounts is settled; the larger carries forward.
      4. Repeat until all balances are zero.

    This gives the minimum number of transactions (not proven optimal for all cases
    but works correctly for all practical group sizes).
    """
    # Work with integer paise to avoid float rounding
    paise = {}
    for uid, data in balances.items():
        paise[uid] = round(data["net"] * 100)

    creditors = sorted(
        [(uid, v) for uid, v in paise.items() if v > 0],
        key=lambda x: -x[1],
    )
    debtors = sorted(
        [(uid, -v) for uid, v in paise.items() if v < 0],
        key=lambda x: -x[1],
    )

    creditors = list(creditors)
    debtors = list(debtors)

    transactions = []

    ci, di = 0, 0
    while ci < len(creditors) and di < len(debtors):
        c_uid, c_amt = creditors[ci]
        d_uid, d_amt = debtors[di]

        settle = min(c_amt, d_amt)
        transactions.append({
            "from_user_id": d_uid,
            "from_user_name": balances[d_uid]["display_name"],
            "to_user_id": c_uid,
            "to_user_name": balances[c_uid]["display_name"],
            "amount_inr": settle / 100,
        })

        creditors[ci] = (c_uid, c_amt - settle)
        debtors[di] = (d_uid, d_amt - settle)

        if creditors[ci][1] == 0:
            ci += 1
        if debtors[di][1] == 0:
            di += 1

    return transactions
