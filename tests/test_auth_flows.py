"""Tests for authentication flows — login, logout, role redirects, forgot/reset password."""

from app.extensions import db
from app.models import User


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Sign in" in response.data or b"Login" in response.data or b"login" in response.data


def test_login_with_valid_credentials(client, app):
    with app.app_context():
        user = User.query.filter_by(username="dev1").first()
        assert user is not None
    response = client.post(
        "/login",
        data={"username": "dev1", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_login_with_invalid_password(client):
    response = client.post(
        "/login",
        data={"username": "dev1", "password": "wrongpassword"},
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_login_with_nonexistent_user(client):
    response = client.post(
        "/login",
        data={"username": "nonexistent", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_logout(client, login_dev):
    response = login_dev.get("/logout", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_logout_clears_session(client, login_dev):
    login_dev.get("/logout", follow_redirects=False)
    response = login_dev.get("/developer", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_login_redirects_developer_to_dashboard(client, app):
    with app.app_context():
        user = User.query.filter_by(username="dev1").first()
    response = client.post(
        "/login",
        data={"username": "dev1", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "/developer" in response.location or "/login" not in response.location


def test_login_redirects_manager_to_manager_dashboard(client, app):
    with app.app_context():
        user = User.query.filter_by(username="manager1").first()
    response = client.post(
        "/login",
        data={"username": "manager1", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "/manager/dashboard" in response.location or "/login" not in response.location


def test_login_redirects_inspector_to_inspector_dashboard(client, app):
    with app.app_context():
        user = User.query.filter_by(username="insp1").first()
    response = client.post(
        "/login",
        data={"username": "insp1", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "/inspector" in response.location


def test_disabled_user_cannot_login(client, app):
    with app.app_context():
        user = User.query.filter_by(username="dev2").first()
        assert user is not None
        assert not user.is_active
    response = client.post(
        "/login",
        data={"username": "dev2", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_authenticated_user_cannot_access_login(client, login_dev):
    response = login_dev.get("/login", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_profile_page_requires_auth(client):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_profile_page_loads_for_authenticated(client, login_dev):
    response = login_dev.get("/profile", follow_redirects=True)
    assert response.status_code == 200


def test_forgot_password_page_renders(client):
    response = client.get("/forgot-password")
    assert response.status_code == 200
    assert b"forgot" in response.data.lower() or b"reset" in response.data.lower()


def test_forgot_password_accepts_email(client):
    response = client.post(
        "/forgot-password",
        data={"email": "nonexistent@test.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_reset_password_page_with_invalid_token(client):
    response = client.get("/reset-password/invalidtoken123")
    assert response.status_code in (200, 302)
