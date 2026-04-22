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
