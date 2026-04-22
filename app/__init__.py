import os
import click
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, render_template
from flask_login import current_user
from sqlalchemy import text

load_dotenv()  # Load .env file before Config reads env vars

from .config import Config
from .extensions import db, login_manager, csrf, mail


def _apply_schema_evolution(app: Flask) -> None:
    """Apply lightweight additive schema changes for existing databases.

    This project currently relies on ``db.create_all()`` and does not use
    Alembic migrations. These statements are additive/idempotent safeguards
    to keep existing environments in sync.
    """
    if app.config.get("SKIP_SCHEMA_EVOLUTION"):
        return

    stmts = [
        # users
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_available BOOLEAN NOT NULL DEFAULT true",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_users_role_active ON users (role, is_active)",
        # scans
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS name_normalized VARCHAR(255)",
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS source_upload_id VARCHAR(120)",
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS scan_fingerprint VARCHAR(64)",
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS import_batch_id VARCHAR(120)",
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER",
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS assigned_to_user_id INTEGER",
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_scans_name_normalized ON scans (name_normalized)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_scans_source_upload_id ON scans (source_upload_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_scans_scan_fingerprint ON scans (scan_fingerprint)",
        "CREATE INDEX IF NOT EXISTS ix_scans_import_batch_id ON scans (import_batch_id)",
        "CREATE INDEX IF NOT EXISTS ix_scans_assigned_to_user_id ON scans (assigned_to_user_id)",
        # defects
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS source_defect_key VARCHAR(160)",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS coord_key VARCHAR(200)",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS import_batch_id VARCHAR(120)",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS is_manual BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS assigned_to_user_id INTEGER",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP",
        "ALTER TABLE defects ADD COLUMN IF NOT EXISTS due_date TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS ix_defects_source_defect_key ON defects (source_defect_key)",
        "CREATE INDEX IF NOT EXISTS ix_defects_coord_key ON defects (coord_key)",
        "CREATE INDEX IF NOT EXISTS ix_defects_import_batch_id ON defects (import_batch_id)",
        "CREATE INDEX IF NOT EXISTS ix_defects_assigned_status ON defects (assigned_to_user_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_defects_due_status ON defects (due_date, status)",
        "CREATE INDEX IF NOT EXISTS ix_defects_unassigned ON defects (scan_id) WHERE assigned_to_user_id IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_defects_scan_source_defect_key ON defects (scan_id, source_defect_key)",
        # activity_logs
        "ALTER TABLE activity_logs ADD COLUMN IF NOT EXISTS event_uuid VARCHAR(80)",
        "ALTER TABLE activity_logs ADD COLUMN IF NOT EXISTS request_id VARCHAR(80)",
        "ALTER TABLE activity_logs ADD COLUMN IF NOT EXISTS actor_user_id INTEGER",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_activity_logs_event_uuid ON activity_logs (event_uuid)",
        "CREATE INDEX IF NOT EXISTS ix_activity_logs_request_id ON activity_logs (request_id)",
        # backfill normalized/hash keys for existing rows
        "UPDATE scans SET name_normalized = lower(trim(name)) WHERE name_normalized IS NULL",
        "UPDATE defects SET coord_key = CONCAT(to_char(round(x::numeric,3), 'FM999999999.000'), '|', to_char(round(y::numeric,3), 'FM999999999.000'), '|', to_char(round(z::numeric,3), 'FM999999999.000'), '|', lower(coalesce(defect_type,'')), '|', lower(coalesce(element,''))) WHERE coord_key IS NULL",
    ]

    with app.app_context():
        for stmt in stmts:
            try:
                db.session.execute(text(stmt))
            except Exception as exc:  # noqa: BLE001
                app.logger.warning("Schema evolution statement failed: %s", exc)
                db.session.rollback()
        db.session.commit()


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'error'

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return db.session.get(User, int(user_id))

    with app.app_context():
        # Import models so SQLAlchemy knows about them before creating tables
        from . import models
        db.create_all()
        _apply_schema_evolution(app)

    # Import and register blueprints
    from .upload_data.routes import upload_data_bp
    from .process_data.routes import process_data_bp
    from .defects.routes import defects_bp
    from .developer.routes import developer_bp
    from .auth.routes import auth_bp

    app.register_blueprint(upload_data_bp)
    app.register_blueprint(process_data_bp)
    app.register_blueprint(defects_bp)
    app.register_blueprint(developer_bp)
    app.register_blueprint(auth_bp)

    # Custom error pages
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    @app.route("/")
    def index():
        # Redirect based on role if logged in, otherwise go to login
        if current_user.is_authenticated:
            if current_user.is_developer:
                return redirect(url_for("developer.dashboard"))
            else:
                return redirect(url_for("upload_data.inspector_dashboard"))
        return redirect(url_for("auth.login"))

    # CLI command to create users
    @app.cli.command('create-user')
    @click.option('--username', prompt=True, help='Username')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
    @click.option('--role', type=click.Choice(['inspector', 'developer']), prompt=True, help='User role')
    @click.option('--email', default='', help='Email address for notifications')
    def create_user(username, password, role, email):
        """Create a new user (inspector or developer)."""
        from .models import User

        if User.query.filter_by(username=username).first():
            click.echo(f'Error: User "{username}" already exists.')
            return

        user = User(username=username, role=role, email=email or None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'{role.capitalize()} user "{username}" created successfully.')

    # Keep old create-admin command for backward compatibility
    @app.cli.command('create-admin')
    @click.option('--username', prompt=True, help='Admin username')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
    @click.option('--email', default='', help='Email address for notifications')
    def create_admin(username, password, email):
        """Create a developer/admin user for the application."""
        from .models import User

        if User.query.filter_by(username=username).first():
            click.echo(f'Error: User "{username}" already exists.')
            return

        user = User(username=username, role='developer', email=email or None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Developer user "{username}" created successfully.')

    return app