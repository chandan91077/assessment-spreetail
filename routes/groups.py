"""routes/groups.py — CRUD for groups and group membership."""

from datetime import date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Group, GroupMember, User

groups_bp = Blueprint("groups", __name__, url_prefix="/api/groups")


@groups_bp.route("/", methods=["GET"])
@login_required
def list_groups():
    # Return groups the current user belongs to
    memberships = current_user.memberships.all()
    group_ids = {m.group_id for m in memberships}
    groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else []
    return jsonify({"groups": [g.to_dict() for g in groups]})


@groups_bp.route("/", methods=["POST"])
@login_required
def create_group():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()

    if not name:
        return jsonify({"error": "Group name is required"}), 400

    group = Group(name=name, description=description)
    db.session.add(group)
    db.session.flush()

    # Automatically add the creator as a member starting today
    join_date = date.today()
    gm = GroupMember(group_id=group.id, user_id=current_user.id, joined_at=join_date)
    db.session.add(gm)
    db.session.commit()

    return jsonify({"group": group.to_dict()}), 201


@groups_bp.route("/<int:group_id>", methods=["GET"])
@login_required
def get_group(group_id):
    group = Group.query.get_or_404(group_id)
    members = GroupMember.query.filter_by(group_id=group_id).all()
    return jsonify({
        "group": group.to_dict(),
        "members": [m.to_dict() for m in members],
    })


@groups_bp.route("/<int:group_id>", methods=["PUT"])
@login_required
def update_group(group_id):
    group = Group.query.get_or_404(group_id)
    data = request.get_json()
    group.name = data.get("name", group.name).strip()
    group.description = data.get("description", group.description).strip()
    db.session.commit()
    return jsonify({"group": group.to_dict()})


@groups_bp.route("/<int:group_id>/members", methods=["POST"])
@login_required
def add_member(group_id):
    Group.query.get_or_404(group_id)
    data = request.get_json()
    user_id = data.get("user_id")
    joined_at_str = data.get("joined_at")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    User.query.get_or_404(user_id)

    # Check if already a member (with no left_at)
    existing = GroupMember.query.filter_by(
        group_id=group_id, user_id=user_id, left_at=None
    ).first()
    if existing:
        return jsonify({"error": "User is already an active member"}), 409

    joined_at = date.fromisoformat(joined_at_str) if joined_at_str else date.today()
    gm = GroupMember(group_id=group_id, user_id=user_id, joined_at=joined_at)
    db.session.add(gm)
    db.session.commit()
    return jsonify({"member": gm.to_dict()}), 201


@groups_bp.route("/<int:group_id>/members/<int:user_id>/leave", methods=["POST"])
@login_required
def remove_member(group_id, user_id):
    Group.query.get_or_404(group_id)
    data = request.get_json() or {}
    left_at_str = data.get("left_at")

    membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=user_id, left_at=None
    ).first()
    if not membership:
        return jsonify({"error": "Active membership not found"}), 404

    membership.left_at = date.fromisoformat(left_at_str) if left_at_str else date.today()
    db.session.commit()
    return jsonify({"member": membership.to_dict()})
