"""Integration tests for the upload -> process -> defect pipeline."""

import io
import json
import os
from unittest.mock import patch

from app.extensions import db
from app.models import Defect, Scan
from app.process_data.glb_snapshot import SnapshotRecord


# ── helpers ──────────────────────────────────────────────────────────────────


def _minimal_glb_stream():
    """Return a BytesIO with valid GLB magic bytes."""
    return io.BytesIO(b"glTF" + (2).to_bytes(4, "little") + (20).to_bytes(4, "little"))


def _minimal_pdf_stream():
    """Return a BytesIO with valid PDF magic bytes."""
    return io.BytesIO(b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF\n")


MOCK_IMAGES = [
    {"id": "img_1", "file": "page01_img01_1.png", "page": 1, "width": 100, "height": 200},
    {"id": "img_2", "file": "page02_img01_2.png", "page": 2, "width": 150, "height": 300},
]

MOCK_SNAPSHOTS = [
    SnapshotRecord(
        snapshot_id="snap_001",
        label="Crack in wall",
        coordinates=(1.0, 2.0, 3.0),
        source_node="Wall/Snapshot-snap_001",
        element="Wall",
    ),
    SnapshotRecord(
        snapshot_id="snap_002",
        label="Water stain on ceiling",
        coordinates=(4.0, 5.0, 6.0),
        source_node="Ceiling/Snapshot-snap_002",
        element="Ceiling",
    ),
]


def _upload_data(
    client, tmp_path, glb_data=None, pdf_data=None, form_extra=None
):
    """POST a GLB + PDF to /upload-data, returning the response."""
    glb_data = glb_data or _minimal_glb_stream()
    pdf_data = pdf_data or _minimal_pdf_stream()
    form_extra = form_extra or {}

    data = {
        "glb_model": (glb_data, "model.glb"),
        "pdf_report": (pdf_data, "report.pdf"),
        "project_name": "Test Project",
        "scan_date": "2026-05-12",
        "address": "123 Test St",
        "latitude": "1.234",
        "longitude": "5.678",
        **form_extra,
    }
    return client.post("/upload-data", data=data, content_type="multipart/form-data")


# ── tests ────────────────────────────────────────────────────────────────────


class TestUploadEndpoint:
    def test_upload_requires_auth(self, client):
        response = client.get("/upload-data")
        assert response.status_code == 302  # redirect to login

    def test_upload_creates_metadata_and_defects_file(
        self, app, client, login_dev, tmp_path
    ):
        app.instance_path = str(tmp_path)

        with (
            patch("app.upload_data.routes.extract_pdf_images", return_value=MOCK_IMAGES),
            patch("app.upload_data.routes.extract_snapshots", return_value=MOCK_SNAPSHOTS),
        ):
            response = _upload_data(client, tmp_path)

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/process-data")

        # Metadata file
        metadata_path = tmp_path / "uploads" / "upload_data" / "latest_upload.json"
        assert metadata_path.exists()
        metadata = json.loads(metadata_path.read_text())
        assert metadata["project_name"] == "Test Project"
        assert metadata["images"] == MOCK_IMAGES
        assert "glTF" in metadata.get("glb_path", "") or "glb" in metadata.get("glb_path", "")
        assert metadata["assignments"] == {"defect_to_image": {}}

        # Defects file
        defects_path = tmp_path / "processed" / "module1" / "defects.json"
        assert defects_path.exists()
        defects_data = json.loads(defects_path.read_text())
        assert len(defects_data["defects"]) == 2
        assert defects_data["defects"][0]["id"] == "snap_001"
        assert defects_data["defects"][0]["coordinates"] == {"x": 1.0, "y": 2.0, "z": 3.0}
        assert defects_data["defects"][0]["element"] == "Wall"
        assert defects_data["defects"][1]["id"] == "snap_002"
        assert defects_data["defects"][1]["coordinates"] == {"x": 4.0, "y": 5.0, "z": 6.0}

    def test_upload_rejects_missing_glb(self, app, client, login_dev, tmp_path):
        app.instance_path = str(tmp_path)
        response = client.post(
            "/upload-data",
            data={"pdf_report": (_minimal_pdf_stream(), "report.pdf")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 302
        assert "upload-data" in response.headers["Location"]

    def test_upload_rejects_invalid_glb_magic(self, app, client, login_dev, tmp_path):
        app.instance_path = str(tmp_path)
        response = client.post(
            "/upload-data",
            data={
                "glb_model": (io.BytesIO(b"NOTglTF"), "model.glb"),
                "pdf_report": (_minimal_pdf_stream(), "report.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 302

    def test_upload_rejects_invalid_pdf_magic(self, app, client, login_dev, tmp_path):
        app.instance_path = str(tmp_path)
        response = client.post(
            "/upload-data",
            data={
                "glb_model": (_minimal_glb_stream(), "model.glb"),
                "pdf_report": (io.BytesIO(b"NOTPDF"), "report.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 302


class TestProcessEndpoint:
    def _setup_files(self, tmp_path, defects=None, metadata_overrides=None):
        """Create prerequisite files for the /process-data flow."""
        defects = defects or [
            {
                "id": "snap_001",
                "description": "Crack in wall",
                "coordinates": {"x": 1.0, "y": 2.0, "z": 3.0},
                "element": "Wall",
                "defect_type": "Structural",
                "severity": "High",
            },
            {
                "id": "snap_002",
                "description": "Water stain on ceiling",
                "coordinates": {"x": 4.0, "y": 5.0, "z": 6.0},
                "element": "Ceiling",
                "defect_type": "Water",
                "severity": "Medium",
            },
        ]

        # defects.json
        defects_dir = tmp_path / "processed" / "module1"
        defects_dir.mkdir(parents=True, exist_ok=True)
        (defects_dir / "defects.json").write_text(
            json.dumps({"defects": defects, "source_file": "defects.json"})
        )

        # latest_upload.json
        upload_dir = tmp_path / "uploads" / "upload_data"
        upload_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "id": "upload_test_001",
            "created_at": "20260512120000",
            "project_name": "Test Project",
            "scan_date": "2026-05-12",
            "image_dir": str(upload_dir / "upload_test_001_images"),
            "images": [],
            "assignments": {"defect_to_image": {}},
            **(metadata_overrides or {}),
        }
        (upload_dir / "latest_upload.json").write_text(json.dumps(metadata))

    def test_process_creates_scan_and_defects(
        self, app, client, login_dev, tmp_path
    ):
        app.instance_path = str(tmp_path)
        self._setup_files(tmp_path)

        with patch("app.process_data.routes._load_glb_defect_file", return_value=None):
            response = client.post(
                "/process-data",
                data={"save_to_db": "1", "scan_name": "Integration Test Scan"},
            )

        assert response.status_code == 302
        location = response.headers["Location"]
        assert "/scans/" in location
        assert "added=2" in location
        assert "skipped=0" in location

        with app.app_context():
            # Verify Scan record
            scan = Scan.query.filter_by(source_upload_id="upload_test_001").first()
            assert scan is not None
            assert scan.name == "Integration Test Scan"
            assert scan.name_normalized == "integration test scan"
            assert scan.model_path is None  # no GLB file loaded

            # Verify Defect records
            defects = Defect.query.filter_by(scan_id=scan.id).all()
            assert len(defects) == 2

            snap_001 = next(d for d in defects if d.source_defect_key == "snap_001")
            assert snap_001.x == 1.0
            assert snap_001.y == 2.0
            assert snap_001.z == 3.0
            assert snap_001.element == "Wall"
            assert snap_001.defect_type == "Structural"
            assert snap_001.severity == "High"
            assert snap_001.status == "Reported"
            assert snap_001.is_manual is False
            assert snap_001.is_active is True

            snap_002 = next(d for d in defects if d.source_defect_key == "snap_002")
            assert snap_002.x == 4.0
            assert snap_002.y == 5.0
            assert snap_002.z == 6.0
            assert snap_002.element == "Ceiling"
            assert snap_002.defect_type == "Water"
            assert snap_002.severity == "Medium"

    def test_process_skips_duplicate_defects(
        self, app, client, login_dev, tmp_path
    ):
        app.instance_path = str(tmp_path)
        self._setup_files(tmp_path)

        with patch("app.process_data.routes._load_glb_defect_file", return_value=None):
            # First POST - creates scan + defects
            r1 = client.post(
                "/process-data",
                data={"save_to_db": "1", "scan_name": "Dedup Test Scan"},
            )
            assert r1.status_code == 302
            assert "added=2" in r1.headers["Location"]

            # Second POST with same data - should skip both defects
            r2 = client.post(
                "/process-data",
                data={"save_to_db": "1", "scan_name": "Dedup Test Scan"},
            )
            assert r2.status_code == 302
            assert "added=0" in r2.headers["Location"]
            assert "skipped=2" in r2.headers["Location"]

        with app.app_context():
            scan = Scan.query.filter_by(source_upload_id="upload_test_001").first()
            defects = Defect.query.filter_by(scan_id=scan.id).all()
            assert len(defects) == 2

    def test_process_reuses_existing_scan(
        self, app, client, login_dev, tmp_path
    ):
        app.instance_path = str(tmp_path)
        self._setup_files(tmp_path)

        # Pre-create a scan with the same source_upload_id
        scan = Scan(
            name="Pre-existing Scan",
            source_upload_id="upload_test_001",
            created_by_user_id=1,
        )
        with app.app_context():
            db.session.add(scan)
            db.session.commit()
            scan_id = scan.id

        with patch("app.process_data.routes._load_glb_defect_file", return_value=None):
            response = client.post(
                "/process-data",
                data={"save_to_db": "1", "scan_name": "Should Be Ignored"},
            )

        assert response.status_code == 302
        # Should have reused=1
        assert "reused=1" in response.headers["Location"]
        # Should still reference the same scan ID (via URL path)
        assert f"/scans/{scan_id}/" in response.headers["Location"]

        with app.app_context():
            reused_scan = db.session.get(Scan, scan_id)
            assert reused_scan.name == "Pre-existing Scan"

    def test_process_empty_defects_shows_error(
        self, app, client, login_dev, tmp_path
    ):
        app.instance_path = str(tmp_path)
        # Create metadata but NO defects file
        upload_dir = tmp_path / "uploads" / "upload_data"
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / "latest_upload.json").write_text(
            json.dumps({"id": "test_empty", "project_name": "Empty", "images": []})
        )

        response = client.post(
            "/process-data",
            data={"save_to_db": "1"},
        )

        assert response.status_code == 302
        assert "/process-data" in response.headers["Location"]
