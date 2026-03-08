import os
import click
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, render_template
from flask_login import current_user

load_dotenv()  # Load .env file before Config reads env vars

from .config import Config
from .extensions import db, login_manager, csrf


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'error'

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    with app.app_context():
        # Import models so SQLAlchemy knows about them before creating tables
        from . import models
        db.create_all()

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
    def create_user(username, password, role):
        """Create a new user (inspector or developer)."""
        from .models import User

        if User.query.filter_by(username=username).first():
            click.echo(f'Error: User "{username}" already exists.')
            return

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'{role.capitalize()} user "{username}" created successfully.')

    # Keep old create-admin command for backward compatibility
    @app.cli.command('create-admin')
    @click.option('--username', prompt=True, help='Admin username')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
    def create_admin(username, password):
        """Create a developer/admin user for the application."""
        from .models import User

        if User.query.filter_by(username=username).first():
            click.echo(f'Error: User "{username}" already exists.')
            return

        user = User(username=username, role='developer')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Developer user "{username}" created successfully.')

    return app