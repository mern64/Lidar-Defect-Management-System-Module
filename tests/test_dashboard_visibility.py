from app.extensions import db
from app.models import Scan, User


def test_dashboard_defaults_to_assigned_projects_only(app, login_dev):
    with app.app_context():
        dev1 = User.query.filter_by(username="dev1").first()

        mine = Scan(name="Assigned Project", model_path="mine.glb", assigned_to_user_id=dev1.id)
        other = Scan(name="Unassigned Project", model_path="other.glb")
        db.session.add(mine)
        db.session.add(other)
        db.session.commit()

    response = login_dev.get("/developer")
    assert response.status_code == 200
    assert b"Assigned Project\n                        </h3>" in response.data
    assert b"Unassigned Project\n                        </h3>" not in response.data
    assert b"/developer/my_tasks" not in response.data
    assert b"/developer/admin_users" not in response.data
    assert b"My Projects" not in response.data
    assert b"Unassigned Projects" not in response.data


def test_developer_dashboard_does_not_show_all_override(app, login_dev):
    with app.app_context():
        dev1 = User.query.filter_by(username="dev1").first()

        mine = Scan(name="Assigned Project 2", model_path="mine2.glb", assigned_to_user_id=dev1.id)
        other = Scan(name="Unassigned Project 2", model_path="other2.glb")
        db.session.add(mine)
        db.session.add(other)
        db.session.commit()

    response = login_dev.get("/developer?show_all=1")
    assert response.status_code == 200
    assert b"Assigned Project 2\n                        </h3>" in response.data
    assert b"Unassigned Project 2\n                        </h3>" not in response.data


def test_manager_dashboard_shows_all_projects(app, login_manager):
    with app.app_context():
        dev1 = User.query.filter_by(username="dev1").first()

        mine = Scan(name="Manager Assigned Project", model_path="l1.glb", assigned_to_user_id=dev1.id)
        other = Scan(name="Manager Unassigned Project", model_path="l2.glb")
        db.session.add(mine)
        db.session.add(other)
        db.session.commit()

    response = login_manager.get("/manager/dashboard")
    assert response.status_code == 200
    assert b"Manager Assigned Project" in response.data
    assert b"Manager Unassigned Project" in response.data


def test_developer_cannot_access_manager_dashboard(login_dev):
    response = login_dev.get("/manager/dashboard")
    assert response.status_code == 403
