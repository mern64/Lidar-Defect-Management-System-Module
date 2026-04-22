from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
import re

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


def _allowed_roles_for_creator(user):
    """Return roles allowed for the currently logged-in creator."""
    if user.is_manager:
        return ('inspector', 'developer')
    return ('inspector', 'developer', 'manager')


def _is_valid_email(value):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value or ""))


def _normalize_phone(value):
    text = (value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[^0-9+]", "", text)
    return normalized or None


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

    allowed_roles = _allowed_roles_for_creator(current_user)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'inspector')
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_number = _normalize_phone(request.form.get('phone_number', ''))
        department = request.form.get('department', '').strip()
        job_title = request.form.get('job_title', '').strip()

        if not username or not password or not full_name or not email:
            flash('Username, full name, work email, and password are required.', 'error')
            return render_template('auth/register.html', allowed_roles=allowed_roles)

        if not _is_valid_email(email):
            flash('Please provide a valid work email address.', 'error')
            return render_template('auth/register.html', allowed_roles=allowed_roles)

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth/register.html', allowed_roles=allowed_roles)

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_template('auth/register.html', allowed_roles=allowed_roles)

        if db.session.query(User.id).filter(func.lower(User.email) == email).first():
            flash('Work email already exists.', 'error')
            return render_template('auth/register.html', allowed_roles=allowed_roles)

        if role not in allowed_roles:
            if current_user.is_manager and role == 'manager':
                flash('Manager account creation is restricted. Please choose inspector or developer.', 'error')
                return render_template('auth/register.html', allowed_roles=allowed_roles)
            role = 'inspector'

        user = User(
            username=username,
            role=role,
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            department=department or None,
            job_title=job_title or None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'User "{username}" created successfully as {role}.', 'success')
        return _redirect_by_role(current_user)

    return render_template('auth/register.html', allowed_roles=allowed_roles)
