from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page — redirects based on user role after authentication."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('auth/login.html')

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('Invalid username or password.', 'error')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('This account is disabled. Contact an administrator.', 'error')
            return render_template('auth/login.html')

        login_user(user)
        flash(f'Welcome back, {user.username}!', 'success')

        # If user was trying to access a specific page, go there
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)

        # Otherwise redirect based on role
        return _redirect_by_role(user)

    return render_template('auth/login.html')


def _redirect_by_role(user):
    """Redirect user to the appropriate page based on their role."""
    if user.is_manager:
        return redirect(url_for('developer.manager_dashboard'))
    if user.is_developer:
        return redirect(url_for('developer.dashboard'))

    # Inspector → inspector dashboard
    return redirect(url_for('upload_data.inspector_dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    """Register a new user — only accessible to developers and managers."""
    if not current_user.is_admin:
        flash('Only developers and managers can create new users.', 'error')
        return _redirect_by_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'inspector')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_template('auth/register.html')

        if role not in ('inspector', 'developer', 'manager'):
            role = 'inspector'

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'User "{username}" created successfully as {role}.', 'success')
        return _redirect_by_role(current_user)

    return render_template('auth/register.html')
