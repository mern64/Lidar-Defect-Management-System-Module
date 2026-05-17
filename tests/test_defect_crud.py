"""Tests for defect CRUD operations via API endpoints."""

import json

from app.extensions import db
from app.models import Defect, Scan, User


def _seed_scan_and_defect():
    scan = Scan(name="Test Scan CRUD", model_path="test.glb")
    db.session.add(scan)
    db.session.flush()
    defect = Defect(
        scan_id=scan.id,
        x=1.0, y=2.0, z=3.0,
        defect_type="Crack",
        severity="Medium",
        status="Reported",
        element="Wall",
        location="Living Room",
        description="Test defect",
    )
    defect.auto_calculate_priority()
    defect.coord_key = Defect.build_coord_key(defect.x, defect.y, defect.z, defect.defect_type, defect.element)
    db.session.add(defect)
    db.session.commit()
    return defect.id, scan.id


def test_create_defect_api(app, login_dev):
    with app.app_context():
        _, scan_id = _seed_scan_and_defect()
    response = login_dev.post(
        f"/scans/{scan_id}/defects",
        json={"x": 10, "y": 20, "z": 30, "defect_type": "Water Leak", "element": "Ceiling"},
        headers={"Origin": "http://localhost", "Content-Type": "application/json"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["defectId"] is not None


def test_create_duplicate_defect_returns_200(app, login_dev):
    with app.app_context():
        defect_id, scan_id = _seed_scan_and_defect()
        defect = db.session.get(Defect, defect_id)
    response = login_dev.post(
        f"/scans/{scan_id}/defects",
        json={
            "x": defect.x, "y": defect.y, "z": defect.z,
            "defect_type": defect.defect_type,
            "element": defect.element,
        },
        headers={"Origin": "http://localhost", "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("duplicate") is True


def test_delete_defect_api(app, login_dev):
    with app.app_context():
        defect_id, _ = _seed_scan_and_defect()
    response = login_dev.delete(
        f"/defect/{defect_id}",
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Defect, defect_id) is None


def test_delete_nonexistent_defect_returns_404(app, login_dev):
    response = login_dev.delete(
        "/defect/99999",
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 404


def test_update_defect_status_api(app, login_dev):
    with app.app_context():
        defect_id, _ = _seed_scan_and_defect()
    response = login_dev.put(
        f"/defect/{defect_id}/status",
        json={"status": "Under Review", "notes": "Reviewed and confirmed"},
        headers={"Origin": "http://localhost", "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "Under Review"


def test_get_defect_details_api(app, login_dev):
    with app.app_context():
        defect_id, _ = _seed_scan_and_defect()
    response = login_dev.get(f"/defect/{defect_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == defect_id
    assert data["defect_type"] == "Crack"


def test_get_defects_for_scan(app, login_dev):
    with app.app_context():
        defect_id, scan_id = _seed_scan_and_defect()
    response = login_dev.get(f"/scans/{scan_id}/defects")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1
    assert any(d["defectId"] == defect_id for d in data)


def test_update_defect_rejects_cross_origin(app, login_dev):
    with app.app_context():
        defect_id, _ = _seed_scan_and_defect()
    response = login_dev.put(
        f"/defect/{defect_id}/status",
        json={"status": "Under Review"},
        headers={"Origin": "https://evil.com", "Content-Type": "application/json"},
    )
    assert response.status_code == 403


def test_delete_defect_rejects_cross_origin(app, login_dev):
    with app.app_context():
        defect_id, _ = _seed_scan_and_defect()
    response = login_dev.delete(
        f"/defect/{defect_id}",
        headers={"Origin": "https://evil.com"},
    )
    assert response.status_code == 403


def test_create_defect_rejects_cross_origin(app, login_dev):
    with app.app_context():
        _, scan_id = _seed_scan_and_defect()
    response = login_dev.post(
        f"/scans/{scan_id}/defects",
        json={"x": 5, "y": 5, "z": 5, "defect_type": "Test"},
        headers={"Origin": "https://malicious.com", "Content-Type": "application/json"},
    )
    assert response.status_code == 403
