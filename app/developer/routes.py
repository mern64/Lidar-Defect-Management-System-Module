import json
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required
from app.extensions import db
from app.models import Scan, Defect, DefectStatus, DefectPriority
from app.utils import load_upload_metadata

developer_bp = Blueprint("developer", __name__)


@developer_bp.route("/developer", methods=["GET"])
@login_required
def dashboard():
    """Developer dashboard - view all projects and their defects"""
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
    
    # Apply date range filter
    from datetime import datetime, timedelta, timezone
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
    from datetime import datetime, timedelta, timezone
    
    # 1. Urgent Attention: High/Urgent priority that are NOT fixed
    urgent_attention = Defect.query.filter(
        Defect.priority.in_([DefectPriority.URGENT, DefectPriority.HIGH]),
        Defect.status != DefectStatus.FIXED
    ).count()

    # 2. Stale Reviews: 'Under Review' status for > 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    # Note: tracking strictly by 'updated_at' would be better if we had it on Defect, 
    # but we can approximate using created_at or join with ActivityLog. 
    # For now, let's use created_at for simplicity or assume if it's still Under Review it's stale.
    # A better approach: Join with ActivityLog to find when it was last updated.
    # Simple proxy: Defects created > 7 days ago still in 'Under Review'
    stale_reviews = Defect.query.filter(
        Defect.status == DefectStatus.UNDER_REVIEW,
        Defect.created_at < seven_days_ago
    ).count()

    # 3. Recent Activity: Defects created in last 24h
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
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
            'new_24h': new_defects_24h
        }
    )


@developer_bp.route("/developer/scan/<int:scan_id>", methods=["GET"])
@login_required
def view_scan(scan_id):
    """View detailed defects for a specific scan"""
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

    return render_template(
        "developer/scan_detail.html", 
        scan=scan, 
        defects=defects, 
        upload_metadata=upload_metadata,
        search_query=search_query,
        sort_by=sort_by
    )


@developer_bp.route("/developer/defect/<int:defect_id>/update", methods=["POST"])
@login_required
def update_defect_progress(defect_id):
    """Update defect status/progress"""
    from app.models import ActivityLog
    
    defect = Defect.query.get_or_404(defect_id)
    scan_id = defect.scan_id
    
    new_status = request.form.get("status")
    new_priority = request.form.get("priority")
    new_notes = request.form.get("notes", "").strip()

    # Enum validation
    valid_statuses = [e.value for e in DefectStatus]
    valid_priorities = [e.value for e in DefectPriority]

    if new_status and new_status not in valid_statuses:
        return jsonify({"success": False, "message": "Invalid status"}), 400
    
    if new_priority and new_priority not in valid_priorities:
        return jsonify({"success": False, "message": "Invalid priority"}), 400

    # Log changes
    if new_status and new_status != defect.status:
        activity = ActivityLog(
            defect_id=defect_id,
            scan_id=scan_id,
            action='status updated',
            old_value=defect.status,
            new_value=new_status
        )
        db.session.add(activity)
    
    if new_priority and new_priority != defect.priority:
        activity = ActivityLog(
            defect_id=defect_id,
            scan_id=scan_id,
            action='priority updated',
            old_value=defect.priority or DefectPriority.MEDIUM.value,
            new_value=new_priority
        )
        db.session.add(activity)
    
    # Update defect
    if new_status:
        defect.status = new_status
    if new_priority:
        defect.priority = new_priority
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
    from app.models import ActivityLog
    
    scan = Scan.query.get_or_404(scan_id)
    
    defect_ids = request.form.getlist("defect_ids[]")
    new_status = request.form.get("bulk_status")
    new_priority = request.form.get("bulk_priority")
    
    if not defect_ids:
        flash("⚠ No defects selected", "error")
        return redirect(url_for('developer.view_scan', scan_id=scan_id))
    
    valid_statuses = [e.value for e in DefectStatus]
    valid_priorities = [e.value for e in DefectPriority]

    if new_status and new_status not in valid_statuses:
        flash("⚠ Invalid status", "error")
        return redirect(url_for('developer.view_scan', scan_id=scan_id))
    
    if new_priority and new_priority not in valid_priorities:
        flash("⚠ Invalid priority", "error")
        return redirect(url_for('developer.view_scan', scan_id=scan_id))
    
    # Update all selected defects
    updated_count = 0
    for defect_id in defect_ids:
        defect = Defect.query.filter_by(id=int(defect_id), scan_id=scan_id).first()
        if defect:
            # Log status change
            if new_status and new_status != defect.status:
                activity = ActivityLog(
                    defect_id=defect.id,
                    scan_id=scan_id,
                    action='status updated (bulk)',
                    old_value=defect.status,
                    new_value=new_status
                )
                db.session.add(activity)
            
            # Log priority change
            if new_priority and new_priority != defect.priority:
                activity = ActivityLog(
                    defect_id=defect.id,
                    scan_id=scan_id,
                    action='priority updated (bulk)',
                    old_value=defect.priority or DefectPriority.MEDIUM.value,
                    new_value=new_priority
                )
                db.session.add(activity)
            
            if new_status:
                defect.status = new_status
            if new_priority:
                defect.priority = new_priority
            updated_count += 1
    
    db.session.commit()
    
    # Send bulk email notification
    if updated_count > 0 and (new_status or new_priority):
        try:
            from app.notifications import send_bulk_update_notification
            send_bulk_update_notification(
                scan=scan,
                defect_ids=[int(id) for id in defect_ids],
                new_status=new_status,
                new_priority=new_priority
            )
        except Exception as e:
            current_app.logger.error('Failed to send bulk update email: %s', e)

    flash(f"✓ Successfully updated {updated_count} defect(s)", "success")
    return redirect(url_for('developer.view_scan', scan_id=scan_id))






# ===== PHASE 3: Analytics, Charts, Assignments, Activity =====

# (Team assignment removed)


@developer_bp.route("/developer/scan/<int:scan_id>/charts-data", methods=["GET"])
@login_required
def get_charts_data(scan_id):
    """Get data for charts (status, priority, severity)"""
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
    from app.models import ActivityLog
    
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
