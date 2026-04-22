from app.extensions import db
from app.models import Defect, Scan, User


def test_tasks_csv_export_includes_assignment_fields(app, login_dev):
    with app.app_context():
        dev = User.query.filter_by(username="dev1").first()
        scan = Scan(name="Export Scan", model_path="export.glb")
        db.session.add(scan)
        db.session.flush()

        defect = Defect(
            scan_id=scan.id,
            x=10.0,
            y=20.0,
            z=30.0,
            defect_type="Structural",
            severity="High",
            status="Under Review",
            assigned_to_user_id=dev.id,
        )
        defect.auto_calculate_priority()
        db.session.add(defect)
        db.session.commit()

    response = login_dev.get("/developer/tasks/export.csv?queue=all")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")

    csv_text = response.data.decode("utf-8")
    assert "assignee" in csv_text
    assert "assignee_id" in csv_text
    assert "due_date" in csv_text
    assert "Export Scan" in csv_text
