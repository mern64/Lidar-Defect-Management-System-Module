import glob
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import login_required, current_user

from .glb_snapshot import SnapshotRecord, extract_snapshots

try:
    from pygltflib import GLTF2
except ImportError:  # pragma: no cover
    GLTF2 = None

from app.extensions import db
from app.models import Scan, Defect
from app.utils import upload_root as _upload_root, metadata_path as _metadata_path, scan_metadata_path as _scan_metadata_path


process_data_bp = Blueprint("process_data", __name__)


@dataclass
class DefectRecord:
    id: str
    description: str
    x: float
    y: float
    z: float
    source_file: str
    element: Optional[str] = None
    defect_type: str = "Unknown"
    severity: str = "Medium"


def _processed_root() -> str:
    return os.path.join(current_app.instance_path, "processed", "module1")


def _glb_search_directories() -> List[str]:
    return [_processed_root(), _upload_root()]


def _load_glb_defect_file() -> Optional[str]:
    candidates: List[str] = []
    for directory in _glb_search_directories():
        if not os.path.isdir(directory):
            continue
        for pattern in ("*.glb", "*.gltf"):
            candidates.extend(glob.glob(os.path.join(directory, pattern)))

    if not candidates:
        return None

    latest = max(candidates, key=os.path.getmtime)
    current_app.logger.info("Using GLB/GTLF file %s for defect extraction", latest)
    return latest


def _load_metaroom_defect_file() -> Optional[str]:
    defect_file = os.path.join(_processed_root(), "defects.json")
    if not os.path.exists(defect_file):
        current_app.logger.warning("Defect JSON not found at %s", defect_file)
        return None
    return defect_file


def _parse_defects_from_file(defect_filepath: str) -> List[DefectRecord]:
    with open(defect_filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    source_file = data.get("source_file", os.path.basename(defect_filepath))
    raw_defects = data.get("defects", [])

    defects: List[DefectRecord] = []
    for entry in raw_defects:
        coords = entry.get("coordinates", {})
        try:
            defects.append(
                DefectRecord(
                    id=str(entry.get("id", "")),
                    description=str(entry.get("description", "")),
                    x=float(coords.get("x", 0.0)),
                    y=float(coords.get("y", 0.0)),
                    z=float(coords.get("z", 0.0)),
                    source_file=source_file,
                    element=entry.get("element"),
                    defect_type=entry.get("defect_type", "Unknown"),
                    severity=entry.get("severity", "Medium"),
                )
            )
        except (TypeError, ValueError) as exc:
            current_app.logger.warning("Skipping defect with invalid coordinates: %s (%s)", entry, exc)
    return defects


def _prepare_for_postgres(defects: List[DefectRecord]) -> List[dict]:
    prepared: List[dict] = []
    for record in defects:
        prepared.append(
            {
                "defect_id": record.id,
                "description": record.description,
                "element": record.element,
                "defect_type": record.defect_type,
                "severity": record.severity,
                "x": record.x,
                "y": record.y,
                "z": record.z,
                "source_file": record.source_file,
                "wkt_point": f"POINT Z ({record.x} {record.y} {record.z})",
            }
        )
    return prepared


def _parse_defects_from_glb(defect_filepath: str) -> List[DefectRecord]:
    if GLTF2 is None:
        raise RuntimeError("pygltflib is not installed; cannot parse GLB defects")

    snapshots: List[SnapshotRecord] = extract_snapshots(defect_filepath)
    defects: List[DefectRecord] = []
    for snapshot in snapshots:
        defects.append(
            DefectRecord(
                id=snapshot.snapshot_id,
                description=snapshot.label,
                x=snapshot.coordinates[0],
                y=snapshot.coordinates[1],
                z=snapshot.coordinates[2],
                source_file=os.path.basename(defect_filepath),
                element=snapshot.element,
                defect_type="Unknown",
                severity="Medium",
            )
        )
    return defects


def _load_defects() -> Tuple[List[DefectRecord], Optional[str], str]:
    glb_file = _load_glb_defect_file()
    if glb_file:
        try:
            defects = _parse_defects_from_glb(glb_file)
            if defects:
                return defects, glb_file, "glb"
            current_app.logger.warning("No snapshot metadata found in %s", glb_file)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.exception("Failed to parse GLB defects from %s: %s", glb_file, exc)

    json_file = _load_metaroom_defect_file()
    if json_file:
        try:
            defects = _parse_defects_from_file(json_file)
            return defects, json_file, "json"
        except Exception as exc:  # noqa: BLE001
            current_app.logger.exception("Failed to parse JSON defects from %s: %s", json_file, exc)

    return [], None, "none"


def _load_latest_metadata() -> Optional[dict]:
    metadata_file = _metadata_path()
    if not os.path.exists(metadata_file):
        return None
    try:
        with open(metadata_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        current_app.logger.error("Unable to load upload metadata: %s", exc)
        return None


def _save_latest_metadata(metadata: dict) -> None:
    metadata_file = _metadata_path()
    os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
    with open(metadata_file, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)


def _save_scan_metadata(scan_id: int, metadata: dict) -> None:
    """Persist a copy of upload metadata for a specific Scan.

    This prevents older projects from being "overwritten" when a new
    upload updates latest_upload.json, by giving each scan its own
    stable metadata snapshot.
    """
    if not metadata:
        return
    metadata_file = _scan_metadata_path(scan_id)
    os.makedirs(os.path.dirname(metadata_file), exist_ok=True)
    with open(metadata_file, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)


def _defect_assignments_map(metadata: Optional[dict]) -> Dict[str, str]:
    if not metadata:
        return {}
    assignments = metadata.get("assignments") or {}
    mapping = assignments.get("defect_to_image") or {}
    return {str(defect_id): str(image_id) for defect_id, image_id in mapping.items() if image_id}


def _image_entries(metadata: Optional[dict]) -> List[dict]:
    if not metadata:
        return []
    defect_map = _defect_assignments_map(metadata)
    image_to_defect = {image_id: defect_id for defect_id, image_id in defect_map.items()}
    entries: List[dict] = []
    for image in metadata.get("images", []):
        image_id = str(image.get("id"))
        entries.append(
            {
                "id": image_id,
                "file": image.get("file"),
                "page": image.get("page"),
                "width": image.get("width"),
                "height": image.get("height"),
                "assigned_defect": image_to_defect.get(image_id),
            }
        )
    return entries


def _resolve_image(metadata: dict, image_id: str) -> Optional[Tuple[str, str]]:
    image_dir = metadata.get("image_dir")
    if not image_dir:
        return None
    for image in metadata.get("images", []):
        if str(image.get("id")) == image_id:
            filename = image.get("file")
            if filename:
                return image_dir, filename
    return None


def _tokenize_text(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _auto_assign_images(metadata: dict, defects: List[DefectRecord]) -> bool:
    if not metadata or not defects:
        return False

    assignments = metadata.setdefault("assignments", {}).setdefault("defect_to_image", {})
    if assignments:
        return False

    images = metadata.get("images", [])
    if not images:
        return False

    assigned = False
    used_images: Set[str] = set()

    def _assign(defect_id: str, image_id: str) -> None:
        nonlocal assigned
        assignments[defect_id] = image_id
        used_images.add(image_id)
        assigned = True

    defect_tokens: Dict[str, Set[str]] = {}
    for defect in defects:
        key = str(defect.id)
        defect_tokens[key] = (
            _tokenize_text(defect.id)
            | _tokenize_text(defect.description)
            | _tokenize_text(defect.element)
        )

    for image in images:
        image_id = str(image.get("id", ""))
        if not image_id or image_id in used_images:
            continue
        filename = (image.get("file") or "").lower()
        for defect in defects:
            defect_id = str(defect.id)
            if not defect_id or defect_id in assignments:
                continue
            if defect_id.lower() in filename:
                _assign(defect_id, image_id)
                break

    for image in images:
        image_id = str(image.get("id", ""))
        if not image_id or image_id in used_images:
            continue
        image_tokens = _tokenize_text(image.get("file"))
        if not image_tokens:
            continue
        for defect in defects:
            defect_id = str(defect.id)
            if not defect_id or defect_id in assignments:
                continue
            if defect_tokens.get(defect_id) and image_tokens & defect_tokens[defect_id]:
                _assign(defect_id, image_id)
                break

    remaining_images = [img for img in images if str(img.get("id", "")) not in used_images]
    remaining_defects = [defect for defect in defects if str(defect.id) not in assignments]
    for image, defect in zip(remaining_images, remaining_defects):
        image_id = str(image.get("id", ""))
        defect_id = str(defect.id)
        if image_id and defect_id:
            _assign(defect_id, image_id)

    return assigned


def _render_error(message: str):
    return render_template(
        "process_data/process_result.html",
        error=message,
        defects=[],
        prepared_records=[],
        image_entries=[],
        defect_assignments={},
    )


@process_data_bp.route("/process-data", methods=["GET", "POST"])
@login_required
def process_defect_file():
    if request.method == "POST" and "save_to_db" in request.form:
        defects, source_path, source_kind = _load_defects()
        if not defects:
            flash("No defects to save.", "error")
            return redirect(url_for("process_data.process_defect_file"))

        # Load metadata for image assignments
        metadata = _load_latest_metadata()
        defect_assignments = _defect_assignments_map(metadata) if metadata else {}

        # Create (or reuse) a scan for this upload source.
        scan_name = request.form.get("scan_name", f"Scan from {source_kind}")
        glb_file = _load_glb_defect_file()  # Get the GLB path
        model_path = os.path.basename(glb_file) if glb_file else None
        source_upload_id = str((metadata or {}).get("id") or "").strip() or None
        project_name = (metadata or {}).get("project_name") or scan_name
        scan_fingerprint = Scan.build_fingerprint(model_path, project_name, source_upload_id)
        import_batch_id = source_upload_id or f"import-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        scan = None
        if source_upload_id:
            scan = Scan.query.filter_by(source_upload_id=source_upload_id).first()
        if scan is None and scan_fingerprint:
            scan = Scan.query.filter_by(scan_fingerprint=scan_fingerprint).first()

        reused_scan = False
        if scan is None:
            scan = Scan(
                name=scan_name,
                name_normalized=Scan.normalize_name(scan_name),
                model_path=model_path,
                source_upload_id=source_upload_id,
                scan_fingerprint=scan_fingerprint,
                import_batch_id=import_batch_id,
                created_by_user_id=current_user.id,
            )
            db.session.add(scan)
            db.session.commit()
        else:
            reused_scan = True
            if not scan.name_normalized:
                scan.name_normalized = Scan.normalize_name(scan.name)
            if not scan.source_upload_id and source_upload_id:
                scan.source_upload_id = source_upload_id
            if not scan.scan_fingerprint and scan_fingerprint:
                scan.scan_fingerprint = scan_fingerprint
            if model_path and not scan.model_path:
                scan.model_path = model_path
            if import_batch_id:
                scan.import_batch_id = import_batch_id
            db.session.commit()

        # Create defects with image assignments
        created_count = 0
        skipped_count = 0
        for rec in _prepare_for_postgres(defects):
            # Get image path for this defect if assigned
            image_path = None
            defect_id_str = str(rec["defect_id"])
            if defect_id_str in defect_assignments and metadata:
                image_id = defect_assignments[defect_id_str]
                resolved = _resolve_image(metadata, image_id)
                if resolved:
                    image_dir, filename = resolved
                    # Store relative path from upload_data folder
                    image_path = os.path.join(os.path.basename(image_dir), filename)

            source_defect_key = defect_id_str or None
            coord_key = Defect.build_coord_key(
                rec["x"],
                rec["y"],
                rec["z"],
                rec.get("defect_type", "Unknown"),
                rec.get("element"),
            )

            existing_defect = None
            if source_defect_key:
                existing_defect = Defect.query.filter_by(
                    scan_id=scan.id,
                    source_defect_key=source_defect_key,
                ).first()
            if existing_defect is None:
                existing_defect = Defect.query.filter_by(
                    scan_id=scan.id,
                    coord_key=coord_key,
                    is_active=True,
                ).first()

            if existing_defect:
                skipped_count += 1
                if image_path and not existing_defect.image_path:
                    existing_defect.image_path = image_path
                continue

            defect = Defect(
                scan_id=scan.id,
                x=rec["x"],
                y=rec["y"],
                z=rec["z"],
                element=rec.get("element"),
                defect_type=rec.get("defect_type", "Unknown"),
                severity=rec.get("severity", "Medium"),
                description=rec.get("description", ""),
                status="Reported",
                image_path=image_path,
                source_defect_key=source_defect_key,
                coord_key=coord_key,
                import_batch_id=import_batch_id,
                created_by_user_id=current_user.id,
                is_manual=False,
                is_active=True,
            )
            db.session.add(defect)
            created_count += 1
        db.session.commit()

        # Persist a per-scan copy of the upload metadata so that
        # each project keeps its own project details.
        if metadata:
            _save_scan_metadata(scan.id, metadata)

        flash(
            f"Defects processed for Scan ID {scan.id}. Added: {created_count}, skipped duplicates: {skipped_count}.",
            "success",
        )
        return redirect(
            url_for(
                "defects.visualize_scan",
                scan_id=scan.id,
                added=created_count,
                skipped=skipped_count,
                reused=1 if reused_scan else 0,
            )
        )

    # GET logic
    defects, source_path, source_kind = _load_defects()
    metadata = _load_latest_metadata()
    auto_assigned = False
    if metadata and defects:
        auto_assigned = _auto_assign_images(metadata, defects)
        if auto_assigned:
            _save_latest_metadata(metadata)
    image_entries = _image_entries(metadata)
    defect_assignments = _defect_assignments_map(metadata)

    if not source_path:
        return _render_error(
            "No GLB/JSON defect file found. Ensure the processed folder contains either a Snapshot-enabled GLB or defects.json."
        )

    for entry in image_entries:
        entry["url"] = url_for("process_data.serve_extracted_image", image_id=entry["id"])

    prepared_records = _prepare_for_postgres(defects)
    current_app.logger.info(
        "Prepared %d defect records for PostgreSQL from %s (%s).",
        len(prepared_records),
        source_path,
        source_kind,
    )

    error = None
    if not defects and source_kind == "glb":
        error = "No Snapshot metadata found inside the GLB file."

    # Get next scan ID for default name
    last_scan = Scan.query.order_by(Scan.id.desc()).first()
    next_scan_id = (last_scan.id + 1) if last_scan else 1
    
    # Get project name from metadata for default scan name
    project_name = metadata.get("project_name", "Scan") if metadata else "Scan"
    default_scan_name = f"scanID_{next_scan_id}_{project_name}"

    return render_template(
        "process_data/process_result.html",
        error=error,
        defects=defects,
        prepared_records=prepared_records,
        image_entries=image_entries,
        defect_assignments=defect_assignments,
        upload_metadata=metadata,
        default_scan_name=default_scan_name,
        auto_assigned=auto_assigned,
    )


@process_data_bp.route("/process-data.json", methods=["GET"])
@login_required
def process_defect_file_json():
    defects, source_path, source_kind = _load_defects()
    metadata = _load_latest_metadata()
    image_entries = _image_entries(metadata)
    defect_assignments = _defect_assignments_map(metadata)

    if not source_path:
        return jsonify({"ok": False, "error": "No GLB/JSON defect file found.", "records": []}), 404

    for entry in image_entries:
        entry["url"] = url_for("process_data.serve_extracted_image", image_id=entry["id"])

    prepared_records = _prepare_for_postgres(defects)
    return jsonify(
        {
            "ok": True,
            "count": len(prepared_records),
            "source": source_kind,
            "records": prepared_records,
            "images": image_entries,
            "assignments": defect_assignments,
        }
    )


@process_data_bp.route("/process-data/image/<image_id>", methods=["GET"])
@login_required
def serve_extracted_image(image_id: str):
    metadata = _load_latest_metadata()
    if not metadata:
        abort(404)

    resolved = _resolve_image(metadata, image_id)
    if not resolved:
        abort(404)

    image_dir, filename = resolved
    image_dir = os.path.abspath(image_dir)
    image_path = os.path.abspath(os.path.join(image_dir, filename))
    if os.path.commonpath([image_dir, image_path]) != image_dir:
        abort(404)
    if not os.path.exists(image_path):
        abort(404)

    return send_from_directory(image_dir, filename)


@process_data_bp.route("/process-data/assign-image", methods=["POST"])
@login_required
def assign_image_to_defect():
    metadata = _load_latest_metadata()
    if not metadata:
        flash("No upload metadata available. Upload a GLB/PDF first.", "error")
        return redirect(url_for("process_data.process_defect_file"))

    action = request.form.get("action", "assign")
    image_id = request.form.get("image_id")
    defect_id = request.form.get("defect_id")  # This is the snapshot name like "Snapshot-xxx"

    if not image_id:
        flash("Missing image selection.", "error")
        return redirect(url_for("process_data.process_defect_file"))

    assignments = metadata.setdefault("assignments", {}).setdefault("defect_to_image", {})

    resolved = _resolve_image(metadata, image_id)
    if not resolved:
        flash("Selected image is no longer available.", "error")
        return redirect(url_for("process_data.process_defect_file"))

    # Get the relative image path for database storage
    # _resolve_image returns (image_dir, filename) tuple
    image_dir, image_filename = resolved
    image_dir_name = os.path.basename(image_dir)
    relative_image_path = f"{image_dir_name}/{image_filename}"

    if action == "unassign":
        removed = False
        for defect_key, assigned_image in list(assignments.items()):
            if assigned_image == image_id:
                assignments.pop(defect_key)
                removed = True
                # Also update database - clear image_path for defects with this snapshot name
                _update_defect_image_in_db(defect_key, None)
        if removed:
            flash("Image unassigned from defect.", "success")
        else:
            flash("Image was not assigned.", "info")
    else:
        if not defect_id:
            flash("Select a defect before assigning an image.", "error")
            return redirect(url_for("process_data.process_defect_file"))

        for defect_key, assigned_image in list(assignments.items()):
            if defect_key == defect_id or assigned_image == image_id:
                assignments.pop(defect_key)
                # Clear old assignments in database
                _update_defect_image_in_db(defect_key, None)
        
        assignments[defect_id] = image_id
        # Update database with the image path
        _update_defect_image_in_db(defect_id, relative_image_path)
        flash(f"Linked image to defect {defect_id}.", "success")

    _save_latest_metadata(metadata)
    return redirect(url_for("process_data.process_defect_file"))


def _update_defect_image_in_db(snapshot_name: str, image_path: Optional[str]):
    """Update defect image_path in database by matching snapshot name in description."""
    # Find defects whose description contains this snapshot name
    defects = Defect.query.filter(Defect.description.contains(snapshot_name)).all()
    for defect in defects:
        defect.image_path = image_path
    if defects:
        db.session.commit()
