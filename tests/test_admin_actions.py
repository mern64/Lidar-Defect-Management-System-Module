from app.extensions import db
from app.models import User


def test_admin_can_toggle_user_active(app, login_dev):
    with app.app_context():
        target = User(username="target_user", role="inspector", is_active=True, is_available=True)
        target.set_password("password123")
        db.session.add(target)
        db.session.commit()
        target_id = target.id

    response = login_dev.post(
        f"/developer/admin/users/{target_id}/update",
        data={"action": "toggle_active"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    with app.app_context():
        updated = db.session.get(User, target_id)
        assert updated is not None
        assert updated.is_active is False


def test_disabled_user_cannot_login(app, client):
    with app.app_context():
        disabled = User(username="disabled_user", role="developer", is_active=False, is_available=True)
        disabled.set_password("password123")
        db.session.add(disabled)
        db.session.commit()

    response = client.post(
        "/login",
        data={"username": "disabled_user", "password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"This account is disabled" in response.data


def test_manager_cannot_create_manager_account(app, login_manager):
    response = login_manager.post(
        "/register",
        data={
            "username": "manager2",
            "full_name": "Manager Two",
            "email": "manager2@corp.example",
            "phone_number": "+60123456789",
            "department": "Operations",
            "job_title": "Ops Manager",
            "password": "password123",
            "role": "manager",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Manager account creation is restricted" in response.data

    with app.app_context():
        manager = User.query.filter_by(username="manager2").first()
        assert manager is None


def test_register_persists_corporate_profile_fields(app, login_dev):
    response = login_dev.post(
        "/register",
        data={
            "username": "newdev",
            "full_name": "Nur Afiqah Rahman",
            "email": "afiqah@corp.example",
            "phone_number": "+60 12-345 6789",
            "department": "Facilities",
            "job_title": "Building Engineer",
            "password": "password123",
            "role": "developer",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    with app.app_context():
        user = User.query.filter_by(username="newdev").first()
        assert user is not None
        assert user.full_name == "Nur Afiqah Rahman"
        assert user.email == "afiqah@corp.example"
        assert user.phone_number == "+60123456789"
        assert user.department == "Facilities"
        assert user.job_title == "Building Engineer"


def test_admin_can_delete_non_manager_user(app, login_dev):
    with app.app_context():
        target = User(username="delete_me", role="inspector", is_active=True, is_available=True)
        target.set_password("password123")
        db.session.add(target)
        db.session.commit()
        target_id = target.id

    response = login_dev.post(
        f"/developer/admin/users/{target_id}/update",
        data={"action": "delete_user"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    with app.app_context():
        deleted = db.session.get(User, target_id)
        assert deleted is None


def test_admin_cannot_delete_only_manager(app, login_dev):
    with app.app_context():
        manager = User.query.filter_by(role="manager").first()
        assert manager is not None
        manager_id = manager.id

    response = login_dev.post(
        f"/developer/admin/users/{manager_id}/update",
        data={"action": "delete_user"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cannot delete the only manager account" in response.data

    with app.app_context():
        manager = db.session.get(User, manager_id)
        assert manager is not None
