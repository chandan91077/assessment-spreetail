"""routes/imports.py — CSV upload and anomaly review workflow."""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, ImportSession, ImportAnomaly, Group

imports_bp = Blueprint("imports", __name__, url_prefix="/api/imports")


@imports_bp.route("/upload", methods=["POST"])
@login_required
def upload_csv():
    """
    Accept a CSV file upload and a target group_id.
    Creates an ImportSession, runs the importer, and returns the anomaly report.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted"}), 400

    group_id = request.form.get("group_id")
    if not group_id:
        return jsonify({"error": "group_id is required"}), 400

    group_id = int(group_id)
    Group.query.get_or_404(group_id)

    file_content = file.read().decode("utf-8-sig")  # handle BOM

    # Create session record
    session_obj = ImportSession(
        filename=file.filename,
        group_id=group_id,
        status="pending",
    )
    db.session.add(session_obj)
    db.session.flush()

    from services.csv_importer import run_import
    result = run_import(file_content, group_id, session_obj.id)

    return jsonify({
        "session": session_obj.to_dict(),
        "result": result,
        "anomalies": [a.to_dict() for a in session_obj.anomalies.all()],
    }), 201


@imports_bp.route("/sessions", methods=["GET"])
@login_required
def list_sessions():
    sessions = ImportSession.query.order_by(ImportSession.imported_at.desc()).all()
    return jsonify({"sessions": [s.to_dict() for s in sessions]})


@imports_bp.route("/sessions/<int:session_id>", methods=["GET"])
@login_required
def get_session(session_id):
    session_obj = ImportSession.query.get_or_404(session_id)
    anomalies = session_obj.anomalies.order_by(ImportAnomaly.row_number).all()
    return jsonify({
        "session": session_obj.to_dict(),
        "anomalies": [a.to_dict() for a in anomalies],
    })


@imports_bp.route("/anomalies/<int:anomaly_id>/resolve", methods=["POST"])
@login_required
def resolve_anomaly(anomaly_id):
    """
    Meera's review endpoint. User sets their decision on a flagged anomaly.
    decision: APPROVED | REJECTED | MODIFIED
    """
    anomaly = ImportAnomaly.query.get_or_404(anomaly_id)
    data = request.get_json()
    decision = (data.get("decision") or "").strip().upper()

    if decision not in ("APPROVED", "REJECTED", "MODIFIED"):
        return jsonify({"error": "decision must be APPROVED, REJECTED, or MODIFIED"}), 400

    anomaly.user_decision = decision
    anomaly.resolved = True
    db.session.commit()
    return jsonify({"anomaly": anomaly.to_dict()})


@imports_bp.route("/sessions/<int:session_id>/report", methods=["GET"])
@login_required
def import_report(session_id):
    """
    Produce the full import report for a session — listing every anomaly,
    its type, description, suggested action, and user decision.
    """
    session_obj = ImportSession.query.get_or_404(session_id)
    anomalies = session_obj.anomalies.order_by(ImportAnomaly.row_number).all()

    report_lines = []
    report_lines.append(f"=== IMPORT REPORT: {session_obj.filename} ===")
    report_lines.append(f"Imported at: {session_obj.imported_at}")
    report_lines.append(f"Total rows: {session_obj.total_rows}")
    report_lines.append(f"Imported: {session_obj.imported_count}")
    report_lines.append(f"Skipped: {session_obj.skipped_count}")
    report_lines.append(f"Pending review: {session_obj.pending_review_count}")
    report_lines.append(f"Anomalies detected: {session_obj.anomalies.count()}")
    report_lines.append("")
    report_lines.append("--- ANOMALY DETAIL ---")
    for a in anomalies:
        report_lines.append(
            f"Row {a.row_number:3d} | {a.anomaly_type:<30} | {a.suggested_action:<20} | "
            f"{'[' + a.user_decision + ']' if a.user_decision else '[PENDING]'} | {a.description}"
        )

    return jsonify({
        "session": session_obj.to_dict(),
        "report_text": "\n".join(report_lines),
        "anomalies": [a.to_dict() for a in anomalies],
    })
