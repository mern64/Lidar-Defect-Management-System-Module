from app.extensions import db
from app.models import Defect, Scan, User


def _make_defect(scan_id, **kwargs):
    defect = Defect(
        scan_id=scan_id,
        x=kwargs.get("x", 1.0),
        y=kwargs.get("y", 2.0),
        z=kwargs.get("z", 3.0),
        defect_type=kwargs.get("defect_type", "Unknown"),
        severity=kwargs.get("severity", "Medium"),
        status=kwargs.get("status", "Reported"),
        assigned_to_user_id=kwargs.get("assigned_to_user_id"),
        due_date=kwargs.get("due_date"),
    )
    defect.auto_calculate_priority()
    db.session.add(defect)
    return defect


def test_my_tasks_queue_filters_and_overdue_excludes_fixed(app, login_dev):
    with app.app_context():
        dev1 = User.query.filter_by(username="dev1").first()

        mine_scan = Scan(name="Mine Project", model_path="mine.glb", assigned_to_user_id=dev1.id)
        unassigned_scan = Scan(name="Unassigned Project", model_path="unassigned.glb")
        db.session.add(mine_scan)
        db.session.add(unassigned_scan)
        db.session.flush()

        mine = _make_defect(mine_scan.id, assigned_to_user_id=dev1.id, status="Reported")
        unassigned = _make_defect(unassigned_scan.id, assigned_to_user_id=None, status="Reported")
        db.session.commit()
        mine_id = mine.id
        unassigned_id = unassigned.id

    mine_response = login_dev.get("/developer/tasks?queue=mine")
    assert mine_response.status_code == 200
    assert f"Defect #{mine_id}".encode() in mine_response.data
    assert f"Defect #{unassigned_id}".encode() not in mine_response.data

    unassigned_response = login_dev.get("/developer/tasks?queue=unassigned")
    assert unassigned_response.status_code == 200
    assert f"Defect #{unassigned_id}".encode() in unassigned_response.data
    assert f"Defect #{mine_id}".encode() not in unassigned_response.data
