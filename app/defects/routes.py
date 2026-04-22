from flask import Blueprint, jsonify, request, send_from_directory, abort, render_template, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import Defect, Scan, ActivityLog
from app.utils import load_upload_metadata
import os
from datetime import datetime
import uuid
from sqlalchemy.exc import IntegrityError

defects_bp = Blueprint('defects', __name__)

# Exempt JSON API endpoints from CSRF since they are called via JavaScript fetch()
# Forms that submit via HTML (with CSRF tokens) are NOT exempted

@defects_bp.route('/projects', methods=['GET'])
@login_required
def list_projects():
    """List all scans/projects in the database"""
    scans = Scan.query.order_by(Scan.created_at.desc()).all()
    
    # Enhance scan data with defect counts and metadata
    projects = []
    for scan in scans:
        defect_count = Defect.query.filter_by(scan_id=scan.id).count()
        
        metadata = load_upload_metadata(scan.id)
        
        projects.append({
            'id': scan.id,
            'name': scan.name,
            'created_at': scan.created_at,
            'defect_count': defect_count,
            'model_path': scan.model_path,
            'metadata': metadata
        })
    
    return render_template('defects/projects.html', projects=projects)

@defects_bp.route('/scans/<int:scan_id>/visualize', methods=['GET'])
@login_required
def visualize_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()
    model_url = url_for('defects.serve_model', scan_id=scan_id) if scan.model_path else None

    def _to_non_negative_int(value):
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return None

    added = _to_non_negative_int(request.args.get('added'))
    skipped = _to_non_negative_int(request.args.get('skipped'))
    reused = request.args.get('reused') == '1'
    import_summary = None
    if added is not None or skipped is not None:
        import_summary = {
            'added': added if added is not None else 0,
            'skipped': skipped if skipped is not None else 0,
            'reused': reused,
        }

    upload_metadata = load_upload_metadata(scan_id)
    
    return render_template('defects/visualization.html', 
                          scan=scan, 
                          scan_id=scan_id, 
                          model_url=model_url, 
                          defects=defects,
                          upload_metadata=upload_metadata,
                          import_summary=import_summary)

@defects_bp.route('/scans/<int:scan_id>/defects', methods=['GET'])
@login_required
def get_scan_defects(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()
    
    # Load per-scan upload metadata to get the scan date
    metadata = load_upload_metadata(scan_id)
    upload_date = metadata.get('scan_date') if metadata else None
    
    defect_list = [{
        'defectId': d.id,
        'x': d.x,
        'y': d.y,
        'z': d.z,
        'element': d.element,
        'location': d.location,
        'defect_type': d.defect_type,
        'severity': d.severity,
        'status': d.status,
        'assigned_to_user_id': d.assigned_to_user_id,
        'assigned_to_username': d.assigned_to.username if d.assigned_to else None,
        'due_date': d.due_date.strftime('%Y-%m-%d') if d.due_date else None,
        'description': d.description,
        'created_at': upload_date if upload_date else (d.created_at.strftime('%Y-%m-%d') if d.created_at else None)
    } for d in defects]
    return jsonify(defect_list)

@defects_bp.route('/defect/<int:defect_id>', methods=['GET'])
@login_required
def get_defect_details(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    image_url = None
    if defect.image_path:
        image_url = f'/defects/image/{defect_id}'
    return jsonify({
        'id': defect.id,
        'element': defect.element,
        'location': defect.location,
        'defect_type': defect.defect_type,
        'severity': defect.severity,
        'description': defect.description,
        'x': defect.x,
        'y': defect.y,
        'z': defect.z,
        'status': defect.status,
        'assigned_to_user_id': defect.assigned_to_user_id,
        'assigned_to_username': defect.assigned_to.username if defect.assigned_to else None,
        'assigned_at': defect.assigned_at.isoformat() if defect.assigned_at else None,
        'due_date': defect.due_date.strftime('%Y-%m-%d') if defect.due_date else None,
        'imageUrl': image_url,
        'notes': defect.notes
    })

@defects_bp.route('/defect/<int:defect_id>/status', methods=['PUT'])
@csrf.exempt
@login_required
def update_defect_status(defect_id):
    defect = db.session.get(Defect, defect_id)
    if defect is None:
        abort(404)
    data = request.get_json()
    old_status = defect.status
    old_assignee = defect.assigned_to.username if defect.assigned_to else 'Unassigned'
    old_due = defect.due_date.strftime('%Y-%m-%d') if defect.due_date else ''
    request_id = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID') or uuid.uuid4().hex

    # Only developers can change the status
    if 'status' in data and current_user.role == 'developer':
        defect.status = data['status']
    if 'notes' in data:
        defect.notes = data['notes']
    if 'location' in data:
        defect.location = data['location']
    if 'defect_type' in data:
        defect.defect_type = data['defect_type']
    if 'severity' in data:
        defect.severity = data['severity']

    assignment_fields_present = 'assigned_to_user_id' in data or 'due_date' in data
    if assignment_fields_present:
        return jsonify({'message': 'Per-defect assignment is disabled. Assign project owner from Developer Dashboard.'}), 400
        
    defect.auto_calculate_priority()

    if old_status != defect.status:
        db.session.add(ActivityLog(
            defect_id=defect.id,
            scan_id=defect.scan_id,
            action='status updated',
            old_value=old_status,
            new_value=defect.status,
            request_id=request_id,
            event_uuid=f"{request_id}:status:{defect.id}:{defect.status}",
            actor_user_id=current_user.id,
        ))

    new_assignee = defect.assigned_to.username if defect.assigned_to else 'Unassigned'
    if old_assignee != new_assignee:
        db.session.add(ActivityLog(
            defect_id=defect.id,
            scan_id=defect.scan_id,
            action='assignee updated',
            old_value=old_assignee,
            new_value=new_assignee,
            request_id=request_id,
            event_uuid=f"{request_id}:assignee:{defect.id}:{defect.assigned_to_user_id or 0}",
            actor_user_id=current_user.id,
        ))

    new_due = defect.due_date.strftime('%Y-%m-%d') if defect.due_date else ''
    if old_due != new_due:
        db.session.add(ActivityLog(
            defect_id=defect.id,
            scan_id=defect.scan_id,
            action='due date updated',
            old_value=old_due,
            new_value=new_due,
            request_id=request_id,
            event_uuid=f"{request_id}:due:{defect.id}:{new_due or 'none'}",
            actor_user_id=current_user.id,
        ))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # Duplicate idempotency key (event_uuid) means retry of an already applied update.
        return jsonify({'message': 'Duplicate update ignored', 'status': defect.status}), 200

    # Send email notification if status changed
    if old_status != defect.status:
        try:
            from app.notifications import send_status_change_notification
            send_status_change_notification(defect, old_status, defect.status)
        except Exception as e:
            current_app.logger.error('Failed to send status change email: %s', e)

    return jsonify({'message': 'Defect updated successfully', 'status': defect.status})

@defects_bp.route('/defect/<int:defect_id>', methods=['DELETE'])
@csrf.exempt
@login_required
def delete_defect(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    db.session.delete(defect)
    db.session.commit()
    return jsonify({'message': 'Defect deleted successfully'})

@defects_bp.route('/scans/<int:scan_id>/defects', methods=['POST'])
@csrf.exempt
@login_required
def create_defect(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    data = request.get_json()
    x = float(data.get('x', 0) or 0)
    y = float(data.get('y', 0) or 0)
    z = float(data.get('z', 0) or 0)
    defect_type = data.get('defect_type', 'Unknown')
    element = data.get('element', '')

    source_defect_key = str(data.get('source_defect_key') or '').strip() or None
    coord_key = Defect.build_coord_key(x, y, z, defect_type, element)

    existing = None
    if source_defect_key:
        existing = Defect.query.filter_by(scan_id=scan_id, source_defect_key=source_defect_key).first()
    if existing is None:
        existing = Defect.query.filter_by(scan_id=scan_id, coord_key=coord_key, is_active=True).first()

    if existing:
        return jsonify({
            'message': 'Duplicate defect skipped',
            'defectId': existing.id,
            'duplicate': True,
        }), 200

    defect = Defect(
        scan_id=scan_id,
        x=x,
        y=y,
        z=z,
        element=element,
        location=data.get('location', ''),
        defect_type=defect_type,
        severity=data.get('severity', 'Medium'),
        description=data.get('description', ''),
        status=data.get('status', 'Reported'),
        notes=data.get('notes', ''),
        source_defect_key=source_defect_key,
        coord_key=coord_key,
        is_manual=True,
        created_by_user_id=current_user.id,
        import_batch_id=f"manual-{uuid.uuid4().hex[:12]}",
    )
    
    defect.auto_calculate_priority()
    db.session.add(defect)
    db.session.commit()

    # Send email alert for critical defects
    if defect.severity == 'Critical':
        try:
            from app.notifications import send_critical_defect_alert
            send_critical_defect_alert(defect)
        except Exception as e:
            current_app.logger.error('Failed to send critical defect email: %s', e)

    return jsonify({'message': 'Defect created', 'defectId': defect.id}), 201

@defects_bp.route('/scans/<int:scan_id>/model', methods=['GET'])
@login_required
def serve_model(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    if not scan.model_path:
        abort(404)
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'upload_data')
    response = send_from_directory(upload_dir, scan.model_path)
    response.headers['Content-Type'] = 'model/gltf-binary'
    return response

@defects_bp.route('/defects/image/<int:defect_id>', methods=['GET'])
@login_required
def serve_defect_image(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    if not defect.image_path:
        abort(404)
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'upload_data')
    return send_from_directory(upload_dir, defect.image_path)

@defects_bp.route('/project/<int:scan_id>', methods=['GET'])
@login_required
def view_project(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    defects = Defect.query.filter_by(scan_id=scan_id).all()
    model_url = url_for('defects.serve_model', scan_id=scan_id) if scan.model_path else None
    
    upload_metadata = load_upload_metadata(scan_id)
            
    return render_template('defects/project_detail.html', 
                          scan=scan, 
                          scan_id=scan_id, 
                          model_url=model_url, 
                          defects=defects,
                          upload_metadata=upload_metadata)