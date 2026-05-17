import json
import os
import uuid
import csv
import io
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort, make_response
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Scan, Defect, DefectStatus, DefectPriority, DefectSeverity, User, ActivityLog
from app.utils import load_upload_metadata
from app.services import developer_service

developer_bp = Blueprint("developer", __name__)


def _ensure_developer_access():
    if not current_user.is_developer:
        abort(403)


def _ensure_admin_access():
    if not current_user.is_admin:
        abort(403)


def _ensure_manager_access():
    if not current_user.is_manager:
        abort(403)




def _valid_assignment_target(user_id: int | None) -> User | None:
    if not user_id:
        return None
    return User.query.filter(
        User.id == user_id,
        User.role.in_(['developer', 'inspector']),
        User.is_active.is_(True),
        User.is_available.is_(True),
    ).first()




def _log_activity(defect, action, old_value, new_value, request_id):
    if old_value == new_value:
        return
    db.session.add(ActivityLog(
        defect_id=defect.id,
        scan_id=defect.scan_id,
        action=action,
        old_value=str(old_value) if old_value is not None else "",
        new_value=str(new_value) if new_value is not None else "",
        request_id=request_id,
        event_uuid=f"{request_id}:{action}:{defect.id}:{str(new_value)[:40]}",
        actor_user_id=current_user.id,
    ))


@developer_bp.route("/developer", methods=["GET"], strict_slashes=False)
@login_required
def dashboard():
    """Developer dashboard - focused personal work queue."""
    _ensure_developer_access()
    sort = request.args.get("sort", "recent")
    status_filter = request.args.get("status_filter", "all")
    date_range = request.args.get("date_range", "all")

    scans = developer_service.get_scans_with_defect_counts(
        user_id=current_user.id,
        sort=sort,
        date_range=date_range,
        status_filter=status_filter,
    )

    total_defects = sum(row.defect_count for row in scans)
    total_reported = sum(row.reported_count for row in scans)
    total_review = sum(row.review_count for row in scans)
    total_fixed = sum(row.fixed_count for row in scans)

    return render_template(
        "developer/dashboard.html",
        scans=scans,
        total_defects=total_defects,
        total_reported=total_reported,
        total_review=total_review,
        total_fixed=total_fixed,
        sort=sort,
        status_filter=status_filter,
        date_range=date_range,
        metrics=developer_service.get_dashboard_metrics(),
    )


@developer_bp.route("/manager/dashboard", methods=["GET"])
@login_required
def manager_dashboard():
    """Manager dashboard - all projects and team assignment management."""
    _ensure_manager_access()
    sort = request.args.get("sort", "recent")
    status_filter = request.args.get("status_filter", "all")
    date_range = request.args.get("date_range", "all")

    scans = developer_service.get_scans_with_defect_counts(
        is_manager=True, sort=sort, date_range=date_range, status_filter=status_filter,
    )

    total_defects = sum(row.defect_count for row in scans)
    total_reported = sum(row.reported_count for row in scans)
    total_review = sum(row.review_count for row in scans)
    total_fixed = sum(row.fixed_count for row in scans)

    metrics = developer_service.get_dashboard_metrics()
    metrics['project_counts'] = {
        'mine': Scan.query.filter(Scan.assigned_to_user_id == current_user.id).count(),
        'unassigned': Scan.query.filter(Scan.assigned_to_user_id.is_(None)).count(),
        'all': Scan.query.count(),
    }

    developers = User.query.filter_by(
        role='developer', is_active=True, is_available=True,
    ).order_by(User.username.asc()).all()

    scan_ids = [s[0].id for s in scans]
    escalation_counts = developer_service.get_escalation_data(scan_ids)

    escalation_summary = {'urgent_hotspots': 0, 'stale_reviews': 0, 'overdue_backlog': 0}
    project_escalations = {}
    for row in scans:
        scan = row[0]
        counts = escalation_counts.get(scan.id, {
            'urgent_open_count': 0, 'stale_review_count': 0, 'overdue_open_count': 0,
        })
        result = developer_service.build_escalation_flags(scan, counts)
        project_escalations[scan.id] = result
        if result['flags']:
            for flag in result['flags']:
                escalation_summary[flag['type']] = escalation_summary.get(flag['type'], 0) + 1

    team_workload = developer_service.get_team_workload(developers)

    return render_template(
        "manager/dashboard.html",
        scans=scans,
        total_defects=total_defects,
        total_reported=total_reported,
        total_review=total_review,
        total_fixed=total_fixed,
        sort=sort,
        status_filter=status_filter,
        date_range=date_range,
        metrics=metrics,
        developers=developers,
        team_workload=team_workload,
        escalation_summary=escalation_summary,
        project_escalations=project_escalations,
    )


@developer_bp.route('/developer/scan/<int:scan_id>/assign', methods=['POST'])
@login_required
def assign_project(scan_id):
    """Assign a whole project to one developer instead of assigning per defect."""
    _ensure_manager_access()

    scan = db.session.get(Scan, scan_id)
    if scan is None:
        abort(404)

    assignee_raw = (request.form.get('assigned_to_user_id') or '').strip()
    request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID') or uuid.uuid4().hex

    old_owner = scan.assigned_to.username if scan.assigned_to else 'Unassigned'

    if assignee_raw in ('', 'null', 'none'):
        scan.assigned_to_user_id = None
        scan.assigned_at = None
        new_owner = 'Unassigned'
    else:
        try:
            assignee_id = int(assignee_raw)
        except ValueError:
            flash('Invalid developer selection.', 'error')
            return redirect(request.referrer or url_for('developer.manager_dashboard'))

        assignee = _valid_assignment_target(assignee_id)
        if not assignee:
            flash('Selected developer is not active/available.', 'error')
            return redirect(request.referrer or url_for('developer.manager_dashboard'))

        scan.assigned_to_user_id = assignee.id
        scan.assigned_at = datetime.now(timezone.utc).replace(tzinfo=None)
        new_owner = assignee.username

    defects = Defect.query.filter(
        Defect.scan_id == scan.id,
        Defect.is_active.is_(True),
    ).all()
    for defect in defects:
        defect.assigned_to_user_id = scan.assigned_to_user_id
        defect.assigned_at = scan.assigned_at

    if old_owner != new_owner:
        db.session.add(ActivityLog(
            scan_id=scan.id,
            action='project owner updated',
            old_value=old_owner,
            new_value=new_owner,
            request_id=request_id,
            event_uuid=f"{request_id}:scan-owner:{scan.id}:{scan.assigned_to_user_id or 0}",
            actor_user_id=current_user.id,
        ))

    db.session.commit()
    flash(f'Project {scan.name} assigned to {new_owner}.', 'success')
    return redirect(request.referrer or url_for('developer.manager_dashboard'))


@developer_bp.route("/developer/scan/<int:scan_id>", methods=["GET"])
@login_required
def view_scan(scan_id):
    """View detailed defects for a specific scan"""
    _ensure_developer_access()
    from sqlalchemy import or_

    scan = Scan.query.get_or_404(scan_id)
    search_query = request.args.get('search', '').strip()

    # Base query for this scan
    query = Defect.query.filter_by(scan_id=scan_id)

    # Apply search filter if present
    if search_query:
        term = f"%{search_query}%"
        query = query.filter(
            or_(
                Defect.description.ilike(term),
                Defect.element.ilike(term),
                Defect.location.ilike(term),
                Defect.notes.ilike(term),
                Defect.defect_type.ilike(term)
            )
        )

    # Apply sorting
    sort_by = request.args.get('sort_by', 'created_desc')
    
    if sort_by == 'created_asc':
        query = query.order_by(Defect.created_at.asc())
    elif sort_by == 'priority':
        query = query.order_by(
            db.case(
                (Defect.priority == DefectPriority.URGENT.value, 4),
                (Defect.priority == DefectPriority.HIGH.value, 3),
                (Defect.priority == DefectPriority.MEDIUM.value, 2),
                (Defect.priority == DefectPriority.LOW.value, 1),
                else_=0
            ).desc()
        )
    elif sort_by == 'severity':
        query = query.order_by(
            db.case(
                (Defect.severity == DefectSeverity.CRITICAL.value, 4),
                (Defect.severity == DefectSeverity.HIGH.value, 3),
                (Defect.severity == DefectSeverity.MEDIUM.value, 2),
                (Defect.severity == DefectSeverity.LOW.value, 1),
                else_=0
            ).desc()
        )
    elif sort_by == 'status':
        query = query.order_by(Defect.status.asc())
    else:
        # Default: Newest first
        query = query.order_by(Defect.created_at.desc())

    defects = query.all()
    upload_metadata = load_upload_metadata(scan_id)

    # ---------------------------------------------------------
    # Hotspot Clustering (Machine Learning - DBSCAN)
    # ---------------------------------------------------------
    hotspots = []
    if len(defects) >= 2:
        try:
            import numpy as np
            from sklearn.cluster import DBSCAN

            # Extract coordinates
            coords = np.array([[d.x, d.y, d.z] for d in defects])

            # Run DBSCAN (eps=5.0 distance units, min_samples=2 defects)
            clustering = DBSCAN(eps=5.0, min_samples=2).fit(coords)
            labels = clustering.labels_

            # Group defects by cluster label (ignoring noise label -1)
            unique_labels = set(labels)
            for k in unique_labels:
                if k == -1:
                    continue
                
                class_member_mask = (labels == k)
                cluster_defects = [defects[i] for i in range(len(defects)) if class_member_mask[i]]
                
                if cluster_defects:
                    cx = sum(d.x for d in cluster_defects) / len(cluster_defects)
                    cy = sum(d.y for d in cluster_defects) / len(cluster_defects)
                    cz = sum(d.z for d in cluster_defects) / len(cluster_defects)
                    
                    critical_count = sum(1 for d in cluster_defects if d.severity == 'Critical')
                    cluster_locations = list(set(d.location for d in cluster_defects if d.location))

                    hotspots.append({
                        'id': int(k) + 1,
                        'count': len(cluster_defects),
                        'critical_count': critical_count,
                        'centroid': (cx, cy, cz),
                        'defect_ids': [d.id for d in cluster_defects],
                        'types': list(set(d.defect_type for d in cluster_defects if d.defect_type)),
                        'locations': cluster_locations
                    })
            
            hotspots.sort(key=lambda x: (x['critical_count'], x['count']), reverse=True)
        except Exception:  # noqa: BLE001
            current_app.logger.exception("DBSCAN Clustering Failed")

    from app.models import User
    developers = User.query.filter_by(role='developer', is_active=True).order_by(User.username).all()

    return render_template(
        "developer/scan_detail.html", 
        scan=scan, 
        defects=defects, 
        developers=developers,
        upload_metadata=upload_metadata,
        search_query=search_query,
        sort_by=sort_by,
        hotspots=hotspots,
    )


@developer_bp.route("/developer/defect/<int:defect_id>/update", methods=["POST"])
@login_required
def update_defect_progress(defect_id):
    """Update defect status/progress"""
    _ensure_developer_access()
    
    defect = Defect.query.get_or_404(defect_id)
    scan_id = defect.scan_id
    
    new_status = request.form.get("status")
    new_notes = request.form.get("notes", "").strip()

    # Enum validation
    valid_statuses = [e.value for e in DefectStatus]

    if new_status and new_status not in valid_statuses:
        return jsonify({"success": False, "message": "Invalid status"}), 400

    # Log changes
    if new_status and new_status != defect.status:
        request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID') or uuid.uuid4().hex
        activity = ActivityLog(
            defect_id=defect_id,
            scan_id=scan_id,
            action='status updated',
            old_value=defect.status,
            new_value=new_status,
            request_id=request_id,
            event_uuid=f"{request_id}:status:{defect_id}:{new_status}",
            actor_user_id=current_user.id,
        )
        db.session.add(activity)
    
    # Update defect
    if new_status:
        defect.status = new_status
    if new_notes:
        defect.notes = new_notes
        
    defect.auto_calculate_priority()
    if new_notes:
        defect.notes = new_notes

    db.session.commit()

    # Send email notification if status changed
    if new_status and new_status != defect.status:
        pass  # status was already changed above, compare with original
    if new_status:
        try:
            from app.models import ActivityLog as _AL
            # Check if we logged a status change
            latest = _AL.query.filter_by(defect_id=defect_id, action='status updated').order_by(_AL.timestamp.desc()).first()
            if latest and latest.old_value and latest.new_value and latest.old_value != latest.new_value:
                from app.notifications import send_status_change_notification
                send_status_change_notification(defect, latest.old_value, latest.new_value)
        except Exception as e:
            current_app.logger.error('Failed to send status change email: %s', e)

    # Return JSON for AJAX or redirect for regular form submission
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": f"Defect #{defect.id} updated successfully"})
    
    flash(f"✓ Defect #{defect.id} updated successfully", "success")
    return redirect(request.referrer or url_for('developer.dashboard'))


@developer_bp.route("/developer/image/<path:image_path>", methods=["GET"])
@login_required
def serve_defect_image(image_path: str):
    """Serve defect images from the uploads directory"""
    from flask import send_from_directory, current_app, abort
    import os

    current_app.logger.info(f"Serving defect image: {image_path}")

    # Security check - ensure the path doesn't contain dangerous elements
    if ".." in image_path or image_path.startswith("/"):
        current_app.logger.warning(f"Security violation in image path: {image_path}")
        abort(404)

    # Construct the full path to the uploads directory
    upload_root = os.path.join(current_app.instance_path, "uploads", "upload_data")
    full_image_path = os.path.join(upload_root, image_path)

    current_app.logger.debug(f"Full image path: {full_image_path}")

    # Security check - ensure the resolved path is within the upload directory
    upload_root_abs = os.path.abspath(upload_root)
    full_image_path_abs = os.path.abspath(full_image_path)

    if not full_image_path_abs.startswith(upload_root_abs):
        current_app.logger.warning(f"Path traversal attempt: {full_image_path_abs} not in {upload_root_abs}")
        abort(404)

    if not os.path.exists(full_image_path_abs):
        current_app.logger.warning(f"Image not found: {full_image_path_abs}")
        abort(404)

    # Get directory and filename
    image_dir = os.path.dirname(full_image_path_abs)
    filename = os.path.basename(full_image_path_abs)

    current_app.logger.info(f"Serving {filename} from {image_dir}")
    return send_from_directory(image_dir, filename)


@developer_bp.route("/developer/scan/<int:scan_id>/bulk-update", methods=["POST"])
@login_required
def bulk_update_defects(scan_id):
    """Bulk update multiple defects at once"""
    _ensure_developer_access()
    
    scan = Scan.query.get_or_404(scan_id)
    
    defect_ids = request.form.getlist("defect_ids[]")
    new_status = request.form.get("bulk_status")
    bulk_action = (request.form.get("bulk_action") or "status_only").strip()
    bulk_assignee_raw = request.form.get("bulk_assignee_id")
    request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID') or uuid.uuid4().hex
    
    if not defect_ids:
        flash("⚠ No defects selected", "error")
        return redirect(url_for('developer.view_scan', scan_id=scan_id))
    
    valid_statuses = [e.value for e in DefectStatus]

    if new_status and new_status not in valid_statuses:
        flash("⚠ Invalid status", "error")
        return redirect(url_for('developer.view_scan', scan_id=scan_id))

    target_assignee = None
    skipped_invalid_assignee = False
    if bulk_action == 'assign_to_user':
        try:
            assignee_id = int(bulk_assignee_raw or 0)
            target_assignee = _valid_assignment_target(assignee_id)
            if not target_assignee:
                skipped_invalid_assignee = True
        except (TypeError, ValueError):
            skipped_invalid_assignee = True
    
    # Update all selected defects
    updated_count = 0
    for defect_id in defect_ids:
        defect = Defect.query.filter_by(id=int(defect_id), scan_id=scan_id).first()
        if defect:
            old_assignee = defect.assigned_to.username if defect.assigned_to else 'Unassigned'
            # Log status change
            if new_status and new_status != defect.status:
                activity = ActivityLog(
                    defect_id=defect.id,
                    scan_id=scan_id,
                    action='status updated (bulk)',
                    old_value=defect.status,
                    new_value=new_status,
                    request_id=request_id,
                    event_uuid=f"{request_id}:bulk-status:{defect.id}:{new_status}",
                    actor_user_id=current_user.id,
                )
                db.session.add(activity)
            
            if new_status:
                defect.status = new_status

            if bulk_action == 'unassign':
                defect.assigned_to_user_id = None
                defect.assigned_at = None
            elif bulk_action == 'assign_to_user' and target_assignee:
                defect.assigned_to_user_id = target_assignee.id
                defect.assigned_at = datetime.now(timezone.utc).replace(tzinfo=None)

            new_assignee = defect.assigned_to.username if defect.assigned_to else 'Unassigned'
            _log_activity(defect, 'assignee updated (bulk)', old_assignee, new_assignee, request_id)
            defect.auto_calculate_priority()
            updated_count += 1
    
    db.session.commit()
    
    # Send bulk email notification
    if updated_count > 0 and new_status:
        try:
            from app.notifications import send_bulk_update_notification
            send_bulk_update_notification(
                scan=scan,
                defect_ids=[int(id) for id in defect_ids],
                new_status=new_status,
                new_priority=None
            )
        except Exception as e:
            current_app.logger.error('Failed to send bulk update email: %s', e)

    if skipped_invalid_assignee:
        flash("⚠ Invalid assignee was skipped; status updates were still applied.", "error")
    flash(f"✓ Successfully updated {updated_count} defect(s)", "success")
    return redirect(url_for('developer.view_scan', scan_id=scan_id))






# ===== PHASE 3: Analytics, Charts, Assignments, Activity =====

# (Team assignment removed)


@developer_bp.route("/developer/scan/<int:scan_id>/charts-data", methods=["GET"])
@login_required
def get_charts_data(scan_id):
    """Get data for charts (status, priority, severity)"""
    _ensure_developer_access()
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()

    status_counts = {}
    for d in defects:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1

    priority_counts = {}
    for d in defects:
        priority = d.priority or DefectPriority.MEDIUM.value
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    severity_order = [
        DefectSeverity.CRITICAL.value, DefectSeverity.HIGH.value,
        DefectSeverity.MEDIUM.value, DefectSeverity.LOW.value,
    ]
    severity_counts = {}
    for d in defects:
        severity = d.severity or DefectSeverity.MEDIUM.value
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    ordered_severity = {k: severity_counts[k] for k in severity_order if k in severity_counts}

    return jsonify({
        'status': status_counts,
        'priority': priority_counts,
        'severity': ordered_severity,
        'total': len(defects)
    })


@developer_bp.route("/developer/scan/<int:scan_id>/heatmap-data", methods=["GET"])
@login_required
def get_heatmap_data(scan_id):
    """Get heatmap data by location"""
    _ensure_developer_access()
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()
    
    location_counts = {}
    for d in defects:
        location = d.location or 'Unknown'
        location_counts[location] = location_counts.get(location, 0) + 1

    priority_weight = {
        DefectPriority.URGENT.value: 4, DefectPriority.HIGH.value: 3,
        DefectPriority.MEDIUM.value: 2, DefectPriority.LOW.value: 1,
    }
    location_priority = {}
    for d in defects:
        location = d.location or 'Unknown'
        priority = d.priority or DefectPriority.MEDIUM.value
        weight = priority_weight.get(priority, 2)
        location_priority[location] = location_priority.get(location, 0) + weight
    
    return jsonify({
        'locations': list(location_counts.keys()),
        'counts': list(location_counts.values()),
        'priority_weights': list(location_priority.values())
    })


@developer_bp.route("/developer/recent-activity", methods=["GET"])
@login_required
def get_recent_activity():
    """Get recent activity across all scans"""
    _ensure_developer_access()
    
    # Get last 20 activities
    activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(20).all()
    
    return jsonify([{
        'id': a.id,
        'action': a.action,
        'old_value': a.old_value,
        'new_value': a.new_value,
        'defect_id': a.defect_id,
        'scan_id': a.scan_id,
        'timestamp': a.timestamp.strftime('%Y-%m-%d %H:%M:%S') if a.timestamp else ''
    } for a in activities])


@developer_bp.route("/developer/tasks", methods=["GET"])
@login_required
def my_tasks():
    """Personal work queue for developers."""
    _ensure_developer_access()

    queue = request.args.get("queue", "mine")
    status_filter = request.args.get("status", "all")
    scan_filter = request.args.get("scan", "all")
    base_query = Defect.query.join(Scan).filter(Defect.is_active.is_(True))

    if queue == "unassigned":
        base_query = base_query.filter(Scan.assigned_to_user_id.is_(None))
    elif queue == "all":
        pass
    else:
        queue = "mine"
        base_query = base_query.filter(Scan.assigned_to_user_id == current_user.id)

    if status_filter != "all":
        base_query = base_query.filter(Defect.status == status_filter)
    if scan_filter != "all":
        try:
            scan_filter_id = int(scan_filter)
            base_query = base_query.filter(Defect.scan_id == scan_filter_id)
        except (TypeError, ValueError):
            scan_filter = "all"

    tasks = base_query.order_by(
        Defect.created_at.desc(),
    ).all()

    scan_options = Scan.query.order_by(Scan.created_at.desc()).all()

    counts = {
        "mine": Defect.query.filter(
            Defect.is_active.is_(True),
            Defect.scan_id.in_(db.session.query(Scan.id).filter(Scan.assigned_to_user_id == current_user.id)),
        ).count(),
        "unassigned": Defect.query.filter(
            Defect.is_active.is_(True),
            Defect.scan_id.in_(db.session.query(Scan.id).filter(Scan.assigned_to_user_id.is_(None))),
        ).count(),
        "all": Defect.query.filter(Defect.is_active.is_(True)).count(),
    }

    return render_template(
        "developer/tasks.html",
        tasks=tasks,
        queue=queue,
        status_filter=status_filter,
        scan_filter=str(scan_filter),
        scan_options=scan_options,
        counts=counts,
    )


@developer_bp.route("/developer/tasks/<int:defect_id>/update", methods=["POST"])
@login_required
def update_task(defect_id):
    """Update status for a task from the queue page."""
    _ensure_developer_access()

    defect = Defect.query.get_or_404(defect_id)
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or uuid.uuid4().hex

    old_status = defect.status
    new_status = request.form.get("status", "").strip()

    valid_statuses = [e.value for e in DefectStatus]
    if new_status and new_status in valid_statuses:
        defect.status = new_status

    defect.auto_calculate_priority()

    _log_activity(defect, "status updated", old_status, defect.status, request_id)

    db.session.commit()
    flash(f"Updated task #{defect.id}", "success")
    return redirect(url_for("developer.my_tasks", queue=request.args.get("queue", "mine")))


@developer_bp.route("/developer/tasks/bulk-assign", methods=["POST"])
@login_required
def bulk_assign_tasks():
    """Bulk assignment actions from My Tasks page."""
    _ensure_developer_access()

    defect_ids = request.form.getlist("defect_ids[]")
    action = (request.form.get("bulk_action") or "").strip()
    assignee_raw = request.form.get("bulk_assignee_id")
    queue = request.form.get("queue", "mine")
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or uuid.uuid4().hex

    if not defect_ids:
        flash("No tasks selected", "error")
        return redirect(url_for("developer.my_tasks", queue=queue))

    selected_ids = []
    for raw_id in defect_ids:
        try:
            selected_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not selected_ids:
        flash("No valid tasks selected", "error")
        return redirect(url_for("developer.my_tasks", queue=queue))

    tasks = Defect.query.filter(Defect.id.in_(selected_ids), Defect.is_active.is_(True)).all()
    if not tasks:
        flash("Selected tasks were not found", "error")
        return redirect(url_for("developer.my_tasks", queue=queue))

    target_assignee = None
    if action == "assign_to_user":
        try:
            assignee_id = int(assignee_raw or 0)
            target_assignee = _valid_assignment_target(assignee_id)
            if not target_assignee:
                flash("Invalid assignee skipped. No task assignment changed.", "error")
                target_assignee = None
        except (TypeError, ValueError):
            flash("Invalid assignee skipped. No task assignment changed.", "error")
            target_assignee = None

    updated = 0
    for defect in tasks:
        old_assignee = defect.assigned_to.username if defect.assigned_to else "Unassigned"
        if action == "unassign":
            defect.assigned_to_user_id = None
            defect.assigned_at = None
        elif action == "assign_to_user" and target_assignee:
            defect.assigned_to_user_id = target_assignee.id
            defect.assigned_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            continue

        new_assignee = defect.assigned_to.username if defect.assigned_to else "Unassigned"
        _log_activity(defect, "assignee updated (bulk)", old_assignee, new_assignee, request_id)
        updated += 1

    db.session.commit()
    flash(f"Updated assignee for {updated} task(s)", "success")
    return redirect(url_for("developer.my_tasks", queue=queue))


@developer_bp.route("/developer/tasks/export.csv", methods=["GET"])
@login_required
def export_tasks_csv():
    """Export queue with assignment fields for reporting."""
    _ensure_developer_access()

    queue = request.args.get("queue", "all")
    query = Defect.query.join(Scan).filter(Defect.is_active.is_(True))

    if queue == 'mine':
        query = query.filter(Defect.assigned_to_user_id == current_user.id)
    elif queue == 'unassigned':
        query = query.filter(Defect.assigned_to_user_id.is_(None))

    tasks = query.order_by(Defect.created_at.desc()).limit(10000).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'defect_id', 'scan_id', 'scan_name', 'status', 'severity', 'priority',
        'assignee', 'assignee_id', 'assigned_at', 'location', 'defect_type',
        'x', 'y', 'z', 'created_at',
    ])
    for d in tasks:
        writer.writerow([
            d.id,
            d.scan_id,
            d.scan.name if d.scan else '',
            d.status,
            d.severity,
            d.priority,
            d.assigned_to.username if d.assigned_to else '',
            d.assigned_to_user_id or '',
            d.assigned_at.isoformat() if d.assigned_at else '',
            d.location or '',
            d.defect_type or '',
            d.x,
            d.y,
            d.z,
            d.created_at.isoformat() if d.created_at else '',
        ])

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=ldms_tasks_{queue}_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.csv'
    return response


@developer_bp.route('/developer/admin/users', methods=['GET'])
@login_required
def admin_users():
    """Light admin page to manage users and account states."""
    _ensure_manager_access()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('developer/admin_users.html', users=users)


@developer_bp.route('/developer/admin/users/<int:user_id>/update', methods=['POST'])
@login_required
def admin_update_user(user_id):
    """Apply account/role/password updates from admin page."""
    _ensure_manager_access()
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    action = (request.form.get('action') or '').strip()
    request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID') or uuid.uuid4().hex

    if action == 'toggle_active':
        if user.role == 'manager' and user.is_active:
            active_manager_count = User.query.filter_by(role='manager', is_active=True).count()
            if active_manager_count <= 1:
                flash('Cannot deactivate the only active manager account.', 'error')
                return redirect(url_for('developer.admin_users'))
        old = 'active' if user.is_active else 'inactive'
        user.is_active = not user.is_active
        new = 'active' if user.is_active else 'inactive'
        db.session.add(ActivityLog(
            action='user account state changed',
            old_value=f"{user.username}:{old}",
            new_value=f"{user.username}:{new}",
            request_id=request_id,
            event_uuid=f"{request_id}:user-state:{user.id}:{new}",
            actor_user_id=current_user.id,
        ))
    elif action == 'toggle_available':
        old = 'available' if user.is_available else 'unavailable'
        user.is_available = not user.is_available
        new = 'available' if user.is_available else 'unavailable'
        db.session.add(ActivityLog(
            action='user availability changed',
            old_value=f"{user.username}:{old}",
            new_value=f"{user.username}:{new}",
            request_id=request_id,
            event_uuid=f"{request_id}:user-availability:{user.id}:{new}",
            actor_user_id=current_user.id,
        ))
    elif action == 'change_role':
        new_role = request.form.get('role', '').strip()
        if new_role in ('inspector', 'developer'):
            if user.role == 'manager':
                manager_count = User.query.filter_by(role='manager').count()
                if manager_count <= 1:
                    flash('Cannot change role for the only manager account.', 'error')
                    return redirect(url_for('developer.admin_users'))
            old_role = user.role
            user.role = new_role
            db.session.add(ActivityLog(
                action='user role changed',
                old_value=f"{user.username}:{old_role}",
                new_value=f"{user.username}:{new_role}",
                request_id=request_id,
                event_uuid=f"{request_id}:user-role:{user.id}:{new_role}",
                actor_user_id=current_user.id,
            ))
    elif action == 'reset_password':
        new_password = request.form.get('new_password', '')
        if len(new_password) >= 6:
            user.set_password(new_password)
            db.session.add(ActivityLog(
                action='user password reset',
                old_value=user.username,
                new_value='password_reset',
                request_id=request_id,
                event_uuid=f"{request_id}:user-password:{user.id}",
                actor_user_id=current_user.id,
            ))
        else:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('developer.admin_users'))
    elif action == 'delete_user':
        if user.id == current_user.id:
            flash('You cannot delete your own account while logged in.', 'error')
            return redirect(url_for('developer.admin_users'))
        if user.role == 'manager':
            manager_count = User.query.filter_by(role='manager').count()
            if manager_count <= 1:
                flash('Cannot delete the only manager account.', 'error')
                return redirect(url_for('developer.admin_users'))

        db.session.add(ActivityLog(
            action='user deleted',
            old_value=f"{user.username}:{user.role}",
            new_value='deleted',
            request_id=request_id,
            event_uuid=f"{request_id}:user-delete:{user.id}",
            actor_user_id=current_user.id,
        ))
        db.session.delete(user)
    else:
        flash('Unsupported admin action.', 'error')
        return redirect(url_for('developer.admin_users'))

    db.session.commit()
    flash(f'Updated user {user.username}.', 'success')
    return redirect(url_for('developer.admin_users'))
