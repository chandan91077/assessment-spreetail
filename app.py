# -*- coding: utf-8 -*-
"""
app.py — Flask application factory for Spreetail.

Run locally:
    python app.py

For production (Render / Gunicorn):
    gunicorn app:create_app()
"""

import os
from flask import Flask, send_from_directory
from flask_login import LoginManager
from models import db, User


def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # ── Configuration ──────────────────────────────────────────────────────
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "spreetail.db")

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "spreetail-dev-secret-change-in-prod"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{db_path}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB upload limit
    )

    if test_config:
        app.config.update(test_config)

    # ── Extensions ─────────────────────────────────────────────────────────
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return {"error": "Authentication required"}, 401

    # ── Blueprints ─────────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.groups import groups_bp
    from routes.expenses import expenses_bp
    from routes.settlements import settlements_bp
    from routes.imports import imports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(settlements_bp)
    app.register_blueprint(imports_bp)

    # ── Serve the SPA ──────────────────────────────────────────────────────
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.template_folder, "index.html")

    # ── DB init ────────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_users()

    return app


def _seed_users():
    """
    Pre-seed the five flatmates so they can log in with password 'password123'.
    Idempotent — safe to call on every startup.
    """
    flatmates = [
        ("aisha", "Aisha"),
        ("rohan", "Rohan"),
        ("priya", "Priya"),
        ("meera", "Meera"),
        ("sam", "Sam"),
    ]
    for username, display_name in flatmates:
        if not User.query.filter_by(username=username).first():
            user = User(username=username, display_name=display_name)
            user.set_password("password123")
            db.session.add(user)
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
