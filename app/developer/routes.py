import json
import os
import uuid
import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort, make_response
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Scan, Defect, DefectStatus, DefectPriority, User, ActivityLog
from app.utils import load_upload_metadata

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


def _default_due_date_for_defect(defect: Defect) -> datetime:
    """Apply a simple SLA policy from severity/type when due date is missing."""
    severity_days = {
        'Critical': 2,
        'High': 5,
        'Medium': 10,
        'Low': 20,
    }
    type_days = {
        'structural': 3,
        'electrical': 4,
        'water': 4,
        'crack': 6,
        'plumbing': 8,
        'mechanical': 8,
        'finish': 14,
    }

    severity_days_value = severity_days.get(defect.severity or 'Medium', 10)
    defect_type = (defect.defect_type or '').lower()
    type_days_value = min((days for key, days in type_days.items() if key in defect_type), default=10)
    due_days = min(severity_days_value, type_days_value)
    return datetime.utcnow() + timedelta(days=due_days)


def _valid_assignment_target(user_id: int | None) -> User | None:
    if not user_id:
        return None
    return User.query.filter_by(
        id=user_id,
        role='developer',  # Can only assign to developers, not managers
        is_active=True,
        is_available=True,
    ).first()


def _parse_due_date(raw_value):
    if raw_value in (None, ""):
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text)
        return datetime.fromisoformat(f"{text}T00:00:00")
    except ValueError:
        return None


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


@developer_bp.route("/developer", methods=["GET"])
@login_required
def dashboard():
    """Developer dashboard - focused personal work queue."""
    _ensure_developer_access()
    sort = request.args.get("sort", "recent")
    status_filter = request.args.get("status_filter", "all")
    date_range = request.args.get("date_range", "all")
    order_clause = Scan.created_at.desc() if sort == "recent" else Scan.created_at.asc()

    # Get all scans with defect counts
    query = db.session.query(
        Scan,
        db.func.count(Defect.id).label('defect_count'),
        db.func.coalesce(db.func.sum(db.case((Defect.status == 'Reported', 1), else_=0)), 0).label('reported_count'),
        db.func.coalesce(db.func.sum(db.case((Defect.status == 'Under Review', 1), else_=0)), 0).label('review_count'),
        db.func.coalesce(db.func.sum(db.case((Defect.status == 'Fixed', 1), else_=0)), 0).label('fixed_count')
    ).outerjoin(Defect).group_by(Scan.id).order_by(order_clause)
    
    # Developers only see their own assigned projects.
    query = query.filter(Scan.assigned_to_user_id == current_user.id)
    
    # Apply date range filter
    if date_range == "week":
        cutoff = datetime.now() - timedelta(days=7)
        query = query.filter(Scan.created_at >= cutoff)
    elif date_range == "month":
        cutoff = datetime.now() - timedelta(days=30)
        query = query.filter(Scan.created_at >= cutoff)
    elif date_range == "3months":
        cutoff = datetime.now() - timedelta(days=90)
        query = query.filter(Scan.created_at >= cutoff)
    
    scans = query.all()
    
    # Apply status filter in Python (simpler than SQL HAVING clause)
    if status_filter != "all":
        filtered_scans = []
        for scan_data in scans:
            scan, defect_count, reported, review, fixed = scan_data
            if status_filter == "complete" and defect_count > 0 and fixed == defect_count:
                filtered_scans.append(scan_data)
            elif status_filter == "in_progress" and review > 0:
                filtered_scans.append(scan_data)
            elif status_filter == "started" and reported > 0 and review == 0 and fixed == 0:
                filtered_scans.append(scan_data)
        scans = filtered_scans

    total_defects = sum(row.defect_count for row in scans)
    total_reported = sum(row.reported_count for row in scans)
    total_review = sum(row.review_count for row in scans)
    total_fixed = sum(row.fixed_count for row in scans)

    # --- Dashboard "At a Glance" Metrics ---
    urgent_attention = Defect.query.filter(
        Defect.priority.in_([DefectPriority.URGENT, DefectPriority.HIGH]),
        Defect.status != DefectStatus.FIXED,
    ).count()

    now_utc = datetime.utcnow()
    seven_days_ago = now_utc - timedelta(days=7)
    stale_reviews = Defect.query.filter(
        Defect.status == DefectStatus.UNDER_REVIEW,
        Defect.created_at < seven_days_ago,
    ).count()

    last_24h = now_utc - timedelta(hours=24)
    new_defects_24h = Defect.query.filter(Defect.created_at >= last_24h).count()

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
        metrics={
            'urgent_attention': urgent_attention,
            'stale_reviews': stale_reviews,
            'new_24h': new_defects_24h,
        },
    )


@developer_bp.route("/manager/dashboard", methods=["GET"])
@login_required
def manager_dashboard():
    """Manager dashboard - all projects and team assignment management."""
    _ensure_manager_access()
    sort = request.args.get("sort", "recent")
    status_filter = request.args.get("status_filter", "all")
    date_range = request.args.get("date_range", "all")
    order_clause = Scan.created_at.desc() if sort == "recent" else Scan.created_at.asc()

    query = db.session.query(
        Scan,
        db.func.count(Defect.id).label('defect_count'),
        db.func.coalesce(db.func.sum(db.case((Defect.status == 'Reported', 1), else_=0)), 0).label('reported_count'),
        db.func.coalesce(db.func.sum(db.case((Defect.status == 'Under Review', 1), else_=0)), 0).label('review_count'),
        db.func.coalesce(db.func.sum(db.case((Defect.status == 'Fixed', 1), else_=0)), 0).label('fixed_count')
    ).outerjoin(Defect).group_by(Scan.id).order_by(order_clause)

    if date_range == "week":
        cutoff = datetime.now() - timedelta(days=7)
        query = query.filter(Scan.created_at >= cutoff)
    elif date_range == "month":
        cutoff = datetime.now() - timedelta(days=30)
        query = query.filter(Scan.created_at >= cutoff)
    elif date_range == "3months":
        cutoff = datetime.now() - timedelta(days=90)
        query = query.filter(Scan.created_at >= cutoff)

    scans = query.all()

    if status_filter != "all":
        filtered_scans = []
        for scan_data in scans:
            _, defect_count, reported, review, fixed = scan_data
            if status_filter == "complete" and defect_count > 0 and fixed == defect_count:
                filtered_scans.append(scan_data)
            elif status_filter == "in_progress" and review > 0:
                filtered_scans.append(scan_data)
            elif status_filter == "started" and reported > 0 and review == 0 and fixed == 0:
                filtered_scans.append(scan_data)
        scans = filtered_scans

    total_defects = sum(row.defect_count for row in scans)
    total_reported = sum(row.reported_count for row in scans)
    total_review = sum(row.review_count for row in scans)
    total_fixed = sum(row.fixed_count for row in scans)

    now_utc = datetime.utcnow()
    seven_days_ago = now_utc - timedelta(days=7)
    urgent_attention = Defect.query.filter(
        Defect.priority.in_([DefectPriority.URGENT, DefectPriority.HIGH]),
        Defect.status != DefectStatus.FIXED,
    ).count()
    stale_reviews = Defect.query.filter(
        Defect.status == DefectStatus.UNDER_REVIEW,
        Defect.created_at < seven_days_ago,
    ).count()
    new_defects_24h = Defect.query.filter(Defect.created_at >= (now_utc - timedelta(hours=24))).count()

    project_counts = {
        'mine': Scan.query.filter(Scan.assigned_to_user_id == current_user.id).count(),
        'unassigned': Scan.query.filter(Scan.assigned_to_user_id.is_(None)).count(),
        'all': Scan.query.count(),
    }

    developers = User.query.filter_by(role='developer', is_active=True, is_available=True).order_by(User.username.asc()).all()

    scan_ids = [scan.id for scan, _, _, _, _ in scans]
    escalation_summary = {
        'urgent_hotspots': 0,
        'stale_reviews': 0,
        'overdue_backlog': 0,
    }
    project_escalations = {}
    escalation_counts_by_scan = {}

    if scan_ids:
        escalation_rows = db.session.query(
            Defect.scan_id,
            db.func.coalesce(
                db.func.sum(
                    db.case(
                        (
                            db.and_(
                                Defect.priority.in_([DefectPriority.URGENT, DefectPriority.HIGH]),
                                Defect.status != DefectStatus.FIXED,
                                Defect.is_active.is_(True),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label('urgent_open_count'),
            db.func.coalesce(
                db.func.sum(
                    db.case(
                        (
                            db.and_(
                                Defect.status == DefectStatus.UNDER_REVIEW,
                                Defect.created_at < seven_days_ago,
                                Defect.is_active.is_(True),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label('stale_review_count'),
            db.func.coalesce(
                db.func.sum(
                    db.case(
                        (
                            db.and_(
                                Defect.due_date.isnot(None),
                                Defect.due_date < now_utc,
                                Defect.status != DefectStatus.FIXED,
                                Defect.is_active.is_(True),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label('overdue_open_count'),
        ).filter(
            Defect.scan_id.in_(scan_ids)
        ).group_by(Defect.scan_id).all()

        for row in escalation_rows:
            escalation_counts_by_scan[row.scan_id] = {
                'urgent_open_count': int(row.urgent_open_count or 0),
                'stale_review_count': int(row.stale_review_count or 0),
                'overdue_open_count': int(row.overdue_open_count or 0),
            }

    for scan, _, _, _, _ in scans:
        counts = escalation_counts_by_scan.get(scan.id, {
            'urgent_open_count': 0,
            'stale_review_count': 0,
            'overdue_open_count': 0,
        })
        flags = []

        if counts['urgent_open_count'] >= 3:
            flags.append({
                'type': 'urgent_hotspots',
                'label': 'Urgent Hotspot',
                'detail': f"{counts['urgent_open_count']} urgent/high open",
                'level': 'danger',
            })
            escalation_summary['urgent_hotspots'] += 1
        if counts['stale_review_count'] >= 2:
            flags.append({
                'type': 'stale_reviews',
                'label': 'Stale Review',
                'detail': f"{counts['stale_review_count']} reviews older than 7d",
                'level': 'warning',
            })
            escalation_summary['stale_reviews'] += 1
        if counts['overdue_open_count'] >= 3:
            flags.append({
                'type': 'overdue_backlog',
                'label': 'Overdue Backlog',
                'detail': f"{counts['overdue_open_count']} overdue unresolved",
                'level': 'critical',
            })
            escalation_summary['overdue_backlog'] += 1

        project_escalations[scan.id] = {
            'flags': flags,
            'counts': counts,
        }

    team_workload = []
    for dev in developers:
        assigned_projects = Scan.query.filter_by(assigned_to_user_id=dev.id).count()
        open_defect_rows = Defect.query.join(Scan, Scan.id == Defect.scan_id).filter(
            Scan.assigned_to_user_id == dev.id,
            Defect.status != DefectStatus.FIXED,
            Defect.is_active.is_(True),
        ).all()
        open_defects = len(open_defect_rows)
        urgent_open = sum(1 for defect in open_defect_rows if defect.priority in (DefectPriority.URGENT, DefectPriority.HIGH))
        average_age_days = 0.0
        if open_defect_rows:
            age_days_values = [max((now_utc - (defect.created_at or now_utc)).total_seconds() / 86400, 0) for defect in open_defect_rows]
            average_age_days = round(sum(age_days_values) / len(age_days_values), 1)

        if open_defects >= 20 or urgent_open >= 8:
            load_state = 'overloaded'
        elif open_defects >= 8 or urgent_open >= 3:
            load_state = 'balanced'
        else:
            load_state = 'underloaded'

        utilization_percent = min(int((open_defects / 20) * 100), 100) if open_defects > 0 else 0

        team_workload.append({
            'developer': dev,
            'assigned_projects': assigned_projects,
            'open_defects': open_defects,
            'urgent_open': urgent_open,
            'average_age_days': average_age_days,
            'load_state': load_state,
            'utilization_percent': utilization_percent,
        })

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
        metrics={
            'urgent_attention': urgent_attention,
            'stale_reviews': stale_reviews,
            'new_24h': new_defects_24h,
            'project_counts': project_counts,
        },
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
        scan.assigned_at = datetime.utcnow()
        new_owner = assignee.username

    defects = Defect.query.filter(
        Defect.scan_id == scan.id,
        Defect.is_active.is_(True),
    ).all()
    for defect in defects:
        defect.assigned_to_user_id = scan.assigned_to_user_id
        defect.assigned_at = scan.assigned_at
        defect.due_date = None

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
        # Custom sort for priority: Urgent > High > Medium > Low
        # We map them to integers for sorting
        query = query.order_by(
            db.case(
                (Defect.priority == 'Urgent', 4),
                (Defect.priority == 'High', 3),
                (Defect.priority == 'Medium', 2),
                (Defect.priority == 'Low', 1),
                else_=0
            ).desc()
        )
    elif sort_by == 'severity':
        # Custom sort for severity
        query = query.order_by(
            db.case(
                (Defect.severity == 'Critical', 4),
                (Defect.severity == 'High', 3),
                (Defect.severity == 'Medium', 2),
                (Defect.severity == 'Low', 1),
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
                    continue  # Noise
                
                # Get indices of points in this cluster
                class_member_mask = (labels == k)
                cluster_defects = [defects[i] for i in range(len(defects)) if class_member_mask[i]]
                
                if cluster_defects:
                    # Calculate centroid
                    cx = sum(d.x for d in cluster_defects) / len(cluster_defects)
                    cy = sum(d.y for d in cluster_defects) / len(cluster_defects)
                    cz = sum(d.z for d in cluster_defects) / len(cluster_defects)
                    
                    # Count Critical defects in this hotspot
                    critical_count = sum(1 for d in cluster_defects if d.severity == 'Critical')
                    
                    # Collect unique locations for this cluster
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
            
            # Sort hottest spots first
            hotspots.sort(key=lambda x: (x['critical_count'], x['count']), reverse=True)
        except Exception as e:
            current_app.logger.error("DBSCAN Clustering Failed: %s", e)

    return render_template(
        "developer/scan_detail.html", 
        scan=scan, 
        defects=defects, 
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

            if bulk_action == 'claim_me':
                defect.assigned_to_user_id = current_user.id
                defect.assigned_at = datetime.utcnow()
                if not defect.due_date:
                    defect.due_date = _default_due_date_for_defect(defect)
            elif bulk_action == 'unassign':
                defect.assigned_to_user_id = None
                defect.assigned_at = None
            elif bulk_action == 'assign_to_user' and target_assignee:
                defect.assigned_to_user_id = target_assignee.id
                defect.assigned_at = datetime.utcnow()
                if not defect.due_date:
                    defect.due_date = _default_due_date_for_defect(defect)

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

    # Status distribution
    status_counts = {}
    for d in defects:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1

    # Priority distribution
    priority_counts = {}
    for d in defects:
        priority = d.priority or 'Medium'
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    # Severity distribution (ordered Critical → Low)
    severity_order = ['Critical', 'High', 'Medium', 'Low']
    severity_counts = {}
    for d in defects:
        severity = d.severity or 'Medium'
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
    
    # Count defects by location
    location_counts = {}
    for d in defects:
        location = d.location or 'Unknown'
        location_counts[location] = location_counts.get(location, 0) + 1
    
    # Priority weight (for intensity)
    priority_weight = {'Urgent': 4, 'High': 3, 'Medium': 2, 'Low': 1}
    location_priority = {}
    for d in defects:
        location = d.location or 'Unknown'
        priority = d.priority or 'Medium'
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
        if action == "claim_me":
            defect.assigned_to_user_id = current_user.id
            defect.assigned_at = datetime.utcnow()
        elif action == "unassign":
            defect.assigned_to_user_id = None
            defect.assigned_at = None
        elif action == "assign_to_user" and target_assignee:
            defect.assigned_to_user_id = target_assignee.id
            defect.assigned_at = datetime.utcnow()
            if not defect.due_date:
                defect.due_date = _default_due_date_for_defect(defect)
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

    now_utc = datetime.utcnow()
    queue = request.args.get("queue", "all")
    query = Defect.query.join(Scan).filter(Defect.is_active.is_(True))

    if queue == 'mine':
        query = query.filter(Defect.assigned_to_user_id == current_user.id)
    elif queue == 'unassigned':
        query = query.filter(Defect.assigned_to_user_id.is_(None))
    elif queue == 'overdue':
        query = query.filter(
            Defect.due_date.isnot(None),
            Defect.due_date < now_utc,
            Defect.status != DefectStatus.FIXED,
        )

    tasks = query.order_by(Defect.created_at.desc()).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'defect_id', 'scan_id', 'scan_name', 'status', 'severity', 'priority',
        'assignee', 'assignee_id', 'assigned_at', 'due_date', 'location', 'defect_type',
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
            d.due_date.isoformat() if d.due_date else '',
            d.location or '',
            d.defect_type or '',
            d.x,
            d.y,
            d.z,
            d.created_at.isoformat() if d.created_at else '',
        ])

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=ldms_tasks_{queue}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
    return response


@developer_bp.route('/developer/admin/users', methods=['GET'])
@login_required
def admin_users():
    """Light admin page to manage users and account states."""
    _ensure_admin_access()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('developer/admin_users.html', users=users)


@developer_bp.route('/developer/admin/users/<int:user_id>/update', methods=['POST'])
@login_required
def admin_update_user(user_id):
    """Apply account/role/password updates from admin page."""
    _ensure_admin_access()
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    action = (request.form.get('action') or '').strip()
    request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID') or uuid.uuid4().hex

    if action == 'toggle_active':
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
    else:
        flash('Unsupported admin action.', 'error')
        return redirect(url_for('developer.admin_users'))

    db.session.commit()
    flash(f'Updated user {user.username}.', 'success')
    return redirect(url_for('developer.admin_users'))
