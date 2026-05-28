import os
import click
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, render_template
from flask_login import current_user

load_dotenv()

from .config import Config
from .extensions import db, migrate, login_manager, csrf, mail


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'error'

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return db.session.get(User, int(user_id))

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

    # Inject cache-bust version for static assets (auto-busts on file change)
    @app.context_processor
    def inject_globals():
        import os
        paths = ['css/base.css', 'js/base.js', 'favicon.svg']
        mtimes = [os.path.getmtime(os.path.join(app.root_path, 'static', p))
                  for p in paths if os.path.exists(os.path.join(app.root_path, 'static', p))]
        return {'cache_bust': str(int(max(mtimes))) if mtimes else '0'}

    # Custom error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

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
            if current_user.is_manager:
                return redirect(url_for("developer.manager_dashboard"))
            if current_user.is_developer:
                return redirect(url_for("developer.dashboard"))
            return redirect(url_for("upload_data.inspector_dashboard"))
        return redirect(url_for("auth.login"))

    # CLI command to create users
    @app.cli.command('create-user')
    @click.option('--username', prompt=True, help='Username')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
    @click.option('--role', type=click.Choice(['inspector', 'developer', 'manager']), prompt=True, help='User role')
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