from app.extensions import db
from app.models import Defect, Scan, User


def _seed_defect():
    scan = Scan(name="Scan A", model_path="a.glb")
    db.session.add(scan)
    db.session.flush()

    defect = Defect(
        scan_id=scan.id,
        x=1.0,
        y=2.0,
        z=3.0,
        defect_type="Structural Crack",
        severity="High",
        status="Reported",
    )
    defect.auto_calculate_priority()
    db.session.add(defect)
    db.session.commit()
    return defect.id, scan.id


def test_assignment_endpoint_rejects_per_defect_assignment(app, login_dev):
    with app.app_context():
        defect_id, _ = _seed_defect()
        assignee = User.query.filter_by(username="dev1").first()

    response = login_dev.put(
        f"/defect/{defect_id}/status",
        json={"assigned_to_user_id": assignee.id, "status": "Under Review"},
    )
    assert response.status_code == 400
    assert b"Per-defect assignment is disabled" in response.data

    with app.app_context():
        defect = db.session.get(Defect, defect_id)
        assert defect.assigned_to_user_id is None
        assert defect.status == "Reported"


def test_project_assignment_endpoint_updates_scan_and_defects(app, login_dev):
    with app.app_context():
        defect_id, scan_id = _seed_defect()
        assignee = User.query.filter_by(username="dev1").first()

    response = login_dev.post(
        f"/developer/scan/{scan_id}/assign",
        data={"assigned_to_user_id": str(assignee.id)},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_project_assignment_endpoint_updates_scan_and_defects_for_manager(app, login_manager):
    with app.app_context():
        defect_id, scan_id = _seed_defect()
        assignee = User.query.filter_by(username="dev1").first()

    response = login_manager.post(
        f"/developer/scan/{scan_id}/assign",
        data={"assigned_to_user_id": str(assignee.id)},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    with app.app_context():
        defect = db.session.get(Defect, defect_id)
        scan = db.session.get(Scan, scan_id)
        assert scan is not None
        assert scan.assigned_to_user_id == assignee.id
        assert defect.assigned_to_user_id == assignee.id
