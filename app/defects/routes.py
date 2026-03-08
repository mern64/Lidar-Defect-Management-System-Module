from flask import Blueprint, jsonify, request, send_from_directory, abort, render_template, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import Defect, Scan
from app.utils import load_upload_metadata
import os
from datetime import datetime

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
    
    upload_metadata = load_upload_metadata(scan_id)
    
    return render_template('defects/visualization.html', 
                          scan=scan, 
                          scan_id=scan_id, 
                          model_url=model_url, 
                          defects=defects,
                          upload_metadata=upload_metadata)

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
        'imageUrl': image_url,
        'notes': defect.notes
    })

@defects_bp.route('/defect/<int:defect_id>/status', methods=['PUT'])
@csrf.exempt
@login_required
def update_defect_status(defect_id):
    defect = Defect.query.get_or_404(defect_id)
    data = request.get_json()
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
    db.session.commit()
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
    defect = Defect(
        scan_id=scan_id,
        x=data.get('x', 0),
        y=data.get('y', 0),
        z=data.get('z', 0),
        element=data.get('element', ''),
        location=data.get('location', ''),
        defect_type=data.get('defect_type', 'Unknown'),
        severity=data.get('severity', 'Medium'),
        description=data.get('description', ''),
        status=data.get('status', 'Reported'),
        notes=data.get('notes', '')
    )
    db.session.add(defect)
    db.session.commit()
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