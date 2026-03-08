"""Shared utility functions used by multiple blueprints."""

import json
import os

from flask import current_app


def upload_root() -> str:
    """Return the root directory for uploaded scan data."""
    return os.path.join(current_app.instance_path, "uploads", "upload_data")


def metadata_path() -> str:
    """Return the path to the legacy global metadata file."""
    return os.path.join(upload_root(), "latest_upload.json")


def scan_metadata_path(scan_id: int) -> str:
    """Return the per-scan metadata snapshot path.

    Each scan gets its own copy of the upload metadata so that
    projects keep their original upload details instead of all
    sharing the global latest_upload.json.
    """
    return os.path.join(upload_root(), f"scan_{scan_id}_metadata.json")


def load_upload_metadata(scan_id: int | None = None) -> dict | None:
    """Load upload metadata, preferring per-scan snapshots.

    If *scan_id* is provided the function first tries the per-scan
    snapshot (``scan_<id>_metadata.json``).  Falls back to the legacy
    ``latest_upload.json`` when the snapshot doesn't exist.
    """
    # Prefer per-scan metadata
    if scan_id is not None:
        per_scan = scan_metadata_path(scan_id)
        if os.path.exists(per_scan):
            try:
                with open(per_scan, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError):
                current_app.logger.warning(
                    "Could not read per-scan metadata for scan %s",
                    scan_id,
                    exc_info=True,
                )

    # Fallback to legacy global metadata
    legacy = metadata_path()
    if not os.path.exists(legacy):
        return None
    try:
        with open(legacy, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        current_app.logger.warning("Could not read upload metadata", exc_info=True)
        return None
