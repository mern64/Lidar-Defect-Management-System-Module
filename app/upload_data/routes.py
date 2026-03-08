import json
import os
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename

from .pdf_utils import extract_pdf_images

try:
    from pygltflib import GLTF2
except ImportError:
    GLTF2 = None

from app.process_data.glb_snapshot import extract_snapshots

upload_data_bp = Blueprint("upload_data", __name__)

ALLOWED_GLB_EXT = {".glb"}
ALLOWED_PDF_EXT = {".pdf"}
METADATA_FILENAME = "latest_upload.json"

def _allowed_file(filename: str, allowed_exts) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in allowed_exts


def _validate_file_magic(filepath: str, expected_magic: bytes) -> bool:
    """Validate file content by checking magic bytes at the start of the file."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(len(expected_magic))
        return header == expected_magic
    except (OSError, IOError):
        return False

@upload_data_bp.route("/inspector")
@login_required
def inspector_dashboard():
    """Inspector landing page with options to upload or view projects."""
    from app.models import Scan, Defect
    total_projects = Scan.query.count()
    total_defects = Defect.query.count()
    return render_template(
        "upload_data/inspector_dashboard.html",
        total_projects=total_projects,
        total_defects=total_defects,
    )

@upload_data_bp.route("/upload-data", methods=["GET", "POST"])
@login_required
def upload_scan_data():
    """
    Use Case DM_01: Upload Scan Data
    User: Homeowner / Inspector
    Goal: Upload the 3D GLB model and data file (PDF report) to the system.
    Precondition: None
    Postcondition: Files are stored, and automated data processing is initiated.
    """
    if request.method == "GET":
        return render_template("upload_data/upload.html")

    try:
        glb_file = request.files.get("glb_model")
        pdf_file = request.files.get("pdf_report")
        project_name = request.form.get("project_name", "")
        scan_date = request.form.get("scan_date", "")
        address = request.form.get("address", "")
        latitude = request.form.get("latitude", "")
        longitude = request.form.get("longitude", "")
        unit_no = request.form.get("unit_no", "")
        notes = request.form.get("notes", "")

        if not glb_file or glb_file.filename == "":
            flash("Please upload a GLB 3D model file.", "error")
            return redirect(request.url)

        if not pdf_file or pdf_file.filename == "":
            flash("Please upload a PDF report.", "error")
            return redirect(request.url)

        if not _allowed_file(glb_file.filename, ALLOWED_GLB_EXT):
            flash("Invalid 3D model file type. Only .glb is allowed.", "error")
            return redirect(request.url)

        if not _allowed_file(pdf_file.filename, ALLOWED_PDF_EXT):
            flash("Invalid report file type. Only .pdf is allowed.", "error")
            return redirect(request.url)

        upload_root = os.path.join(current_app.instance_path, "uploads", "upload_data")
        os.makedirs(upload_root, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        upload_id = f"upload_{timestamp}"
        image_dir = os.path.join(upload_root, f"{upload_id}_images")

        glb_name = secure_filename(glb_file.filename)
        pdf_name = secure_filename(pdf_file.filename)

        glb_path = os.path.join(upload_root, glb_name)
        pdf_path = os.path.join(upload_root, pdf_name)

        glb_file.save(glb_path)
        pdf_file.save(pdf_path)

        # Validate file content (magic bytes) to prevent renamed files
        if not _validate_file_magic(glb_path, b'glTF'):
            os.remove(glb_path)
            os.remove(pdf_path)
            flash("Invalid GLB file content. The file does not appear to be a valid 3D model.", "error")
            return redirect(request.url)

        if not _validate_file_magic(pdf_path, b'%PDF'):
            os.remove(glb_path)
            os.remove(pdf_path)
            flash("Invalid PDF file content. The file does not appear to be a valid PDF document.", "error")
            return redirect(request.url)

        extracted_images = extract_pdf_images(pdf_path, image_dir)
        _persist_latest_upload_metadata(
            upload_root,
            {
                "id": upload_id,
                "created_at": timestamp,
                "project_name": project_name,
                "scan_date": scan_date,
                "address": address,
                "latitude": latitude,
                "longitude": longitude,
                "unit_no": unit_no,
                "glb_path": glb_path,
                "pdf_path": pdf_path,
                "image_dir": image_dir,
                "images": extracted_images,
                "assignments": {"defect_to_image": {}},
                "notes": notes,
            },
        )

        _start_automated_data_processing(glb_path, pdf_path, scan_date, address, unit_no, notes)

        flash("Scan data uploaded successfully. Automated processing has started.", "success")
        # Redirect to process data page
        return redirect(url_for("process_data.process_defect_file"))
    except Exception as e:
        current_app.logger.error("Error during upload: %s", str(e))
        flash(f"An error occurred during upload: {str(e)}", "error")
        return redirect(request.url)

def _start_automated_data_processing(glb_path: str, pdf_path: str, scan_date: str, address: str, unit_no: str, notes: str) -> None:
    current_app.logger.info("Starting automated processing for:")
    current_app.logger.info("GLB: %s", glb_path)
    current_app.logger.info("PDF: %s", pdf_path)
    current_app.logger.info("Scan Date: %s", scan_date)
    current_app.logger.info("Address: %s", address)
    current_app.logger.info("Unit No: %s", unit_no)
    if notes:
        current_app.logger.info("Notes: %s", notes)
    
    # Extract defects from GLB and save to processed folder
    if GLTF2 is None:
        current_app.logger.error("pygltflib is not installed; cannot process GLB defects")
        return
    
    try:
        snapshots = extract_snapshots(glb_path)
        defects = []
        for snapshot in snapshots:
            defects.append({
                "id": snapshot.snapshot_id,
                "description": snapshot.label,
                "coordinates": {
                    "x": snapshot.coordinates[0],
                    "y": snapshot.coordinates[1],
                    "z": snapshot.coordinates[2],
                },
                "element": snapshot.element,
                "defect_type": "Unknown",
                "severity": "Medium",
            })
        
        # Save to processed folder
        processed_dir = os.path.join(current_app.instance_path, "processed", "module1")
        os.makedirs(processed_dir, exist_ok=True)
        defects_path = os.path.join(processed_dir, "defects.json")
        with open(defects_path, "w", encoding="utf-8") as fh:
            json.dump({"defects": defects}, fh, indent=2)
        
        current_app.logger.info("Extracted %d defects and saved to %s", len(defects), defects_path)
    except Exception as e:
        current_app.logger.error("Error during automated processing: %s", str(e))


def _persist_latest_upload_metadata(upload_root: str, payload: dict) -> None:
    metadata_path = os.path.join(upload_root, METADATA_FILENAME)
    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)