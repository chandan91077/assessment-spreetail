"""
models.py — SQLAlchemy ORM models for Spreetail.

Every table here corresponds to a real relational concept.
Balances are NEVER stored — they are always computed from expenses + settlements.
This makes them auditable and correct by construction.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    memberships = db.relationship("GroupMember", back_populates="user", lazy="dynamic")
    paid_expenses = db.relationship("Expense", foreign_keys="Expense.paid_by_id", back_populates="paid_by_user", lazy="dynamic")
    splits = db.relationship("ExpenseSplit", back_populates="user", lazy="dynamic")
    sent_settlements = db.relationship("Settlement", foreign_keys="Settlement.payer_id", back_populates="payer", lazy="dynamic")
    received_settlements = db.relationship("Settlement", foreign_keys="Settlement.payee_id", back_populates="payee", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "display_name": self.display_name}


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship("GroupMember", back_populates="group", lazy="dynamic")
    expenses = db.relationship("Expense", back_populates="group", lazy="dynamic")
    settlements = db.relationship("Settlement", back_populates="group", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }

    def active_members_on(self, date):
        """Return User objects who were active members of this group on the given date."""
        from sqlalchemy import or_
        memberships = GroupMember.query.filter(
            GroupMember.group_id == self.id,
            GroupMember.joined_at <= date,
            or_(GroupMember.left_at == None, GroupMember.left_at >= date),
        ).all()
        return [m.user for m in memberships]


class GroupMember(db.Model):
    __tablename__ = "group_members"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    joined_at = db.Column(db.Date, nullable=False)
    left_at = db.Column(db.Date, nullable=True)   # NULL = still active

    group = db.relationship("Group", back_populates="members")
    user = db.relationship("User", back_populates="memberships")

    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "user_display_name": self.user.display_name,
            "joined_at": self.joined_at.isoformat(),
            "left_at": self.left_at.isoformat() if self.left_at else None,
        }


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

SPLIT_TYPES = ("equal", "exact", "percentage", "shares")


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)

    # Always stored in INR; original values preserved for auditability
    amount_inr = db.Column(db.Numeric(12, 2), nullable=False)
    original_amount = db.Column(db.Numeric(12, 2), nullable=True)
    original_currency = db.Column(db.String(10), default="INR")
    fx_rate_used = db.Column(db.Numeric(10, 4), default=1.0)

    date = db.Column(db.Date, nullable=False)
    paid_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # nullable for pending imports

    split_type = db.Column(db.String(20), nullable=False, default="equal")
    is_settlement = db.Column(db.Boolean, default=False)
    import_source = db.Column(db.String(20), default="manual")   # 'manual' | 'csv_import'
    import_session_id = db.Column(db.Integer, db.ForeignKey("import_sessions.id"), nullable=True)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group", back_populates="expenses")
    paid_by_user = db.relationship("User", foreign_keys=[paid_by_id], back_populates="paid_expenses")
    splits = db.relationship("ExpenseSplit", back_populates="expense", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "description": self.description,
            "amount_inr": float(self.amount_inr),
            "original_amount": float(self.original_amount) if self.original_amount else None,
            "original_currency": self.original_currency,
            "fx_rate_used": float(self.fx_rate_used) if self.fx_rate_used else 1.0,
            "date": self.date.isoformat(),
            "paid_by_id": self.paid_by_id,
            "paid_by_name": self.paid_by_user.display_name if self.paid_by_user else "Unassigned",
            "split_type": self.split_type,
            "is_settlement": self.is_settlement,
            "import_source": self.import_source,
            "notes": self.notes,
            "splits": [s.to_dict() for s in self.splits],
        }


class ExpenseSplit(db.Model):
    __tablename__ = "expense_splits"

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount_owed = db.Column(db.Numeric(12, 2), nullable=False)   # final INR amount
    split_value = db.Column(db.Numeric(10, 4), nullable=True)    # raw %, share count, or exact amount

    expense = db.relationship("Expense", back_populates="splits")
    user = db.relationship("User", back_populates="splits")

    def to_dict(self):
        return {
            "id": self.id,
            "expense_id": self.expense_id,
            "user_id": self.user_id,
            "user_display_name": self.user.display_name,
            "amount_owed": float(self.amount_owed),
            "split_value": float(self.split_value) if self.split_value else None,
        }


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------

class Settlement(db.Model):
    __tablename__ = "settlements"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    payer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    payee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount_inr = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group", back_populates="settlements")
    payer = db.relationship("User", foreign_keys=[payer_id], back_populates="sent_settlements")
    payee = db.relationship("User", foreign_keys=[payee_id], back_populates="received_settlements")

    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "payer_id": self.payer_id,
            "payer_name": self.payer.display_name,
            "payee_id": self.payee_id,
            "payee_name": self.payee.display_name,
            "amount_inr": float(self.amount_inr),
            "date": self.date.isoformat(),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Import Sessions & Anomalies
# ---------------------------------------------------------------------------

class ImportSession(db.Model):
    __tablename__ = "import_sessions"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_rows = db.Column(db.Integer, default=0)
    imported_count = db.Column(db.Integer, default=0)
    skipped_count = db.Column(db.Integer, default=0)
    pending_review_count = db.Column(db.Integer, default=0)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    status = db.Column(db.String(20), default="pending")   # pending | complete

    anomalies = db.relationship("ImportAnomaly", back_populates="session", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "imported_at": self.imported_at.isoformat(),
            "total_rows": self.total_rows,
            "imported_count": self.imported_count,
            "skipped_count": self.skipped_count,
            "pending_review_count": self.pending_review_count,
            "group_id": self.group_id,
            "status": self.status,
        }


ANOMALY_TYPES = (
    "DUPLICATE",
    "NEGATIVE_AMOUNT",
    "CURRENCY_USD",
    "SETTLEMENT_AS_EXPENSE",
    "POST_DEPARTURE",
    "PRE_JOIN",
    "MISSING_PAID_BY",
    "UNKNOWN_MEMBER",
    "INCONSISTENT_DATE",
    "AMOUNT_WITH_SYMBOL",
    "WRONG_SPLIT_LABEL",
    "ZERO_AMOUNT",
    "FUTURE_DATE",
    "BAD_PERCENTAGE_SUM",
)

USER_DECISIONS = ("APPROVED", "REJECTED", "MODIFIED")


class ImportAnomaly(db.Model):
    __tablename__ = "import_anomalies"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("import_sessions.id"), nullable=False)
    row_number = db.Column(db.Integer, nullable=False)
    raw_row = db.Column(db.Text, nullable=False)         # JSON of original CSV row
    anomaly_type = db.Column(db.String(40), nullable=False)
    description = db.Column(db.Text, nullable=False)
    suggested_action = db.Column(db.String(40), nullable=False)
    user_decision = db.Column(db.String(20), nullable=True)   # NULL until reviewed
    resolved = db.Column(db.Boolean, default=False)

    session = db.relationship("ImportSession", back_populates="anomalies")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "row_number": self.row_number,
            "raw_row": self.raw_row,
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "user_decision": self.user_decision,
            "resolved": self.resolved,
        }
