from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import enum
import hashlib


class User(UserMixin, db.Model):
    """Application user for authentication and access control."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120))
    full_name = db.Column(db.String(120))
    phone_number = db.Column(db.String(30))
    department = db.Column(db.String(80))
    job_title = db.Column(db.String(80))
    role = db.Column(db.String(20), default='inspector')  # 'inspector', 'developer', or 'manager'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    created_at = db.Column(db.DateTime, default=db.func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_inspector(self):
        return self.role == 'inspector'

    @property
    def is_developer(self):
        return self.role == 'developer'

    @property
    def is_manager(self):
        return self.role == 'manager'

    @property
    def is_admin(self):
        return self.role in ('developer', 'manager')  # developers and managers have admin access


class DefectStatus(str, enum.Enum):
    REPORTED = 'Reported'
    UNDER_REVIEW = 'Under Review'
    FIXED = 'Fixed'

class DefectPriority(str, enum.Enum):
    URGENT = 'Urgent'
    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'

class DefectSeverity(str, enum.Enum):
    CRITICAL = 'Critical'
    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'

class Scan(db.Model):
    __tablename__ = 'scans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    name_normalized = db.Column(db.String(255), index=True)
    model_path = db.Column(db.String(500))  # Path to 3D model file
    source_upload_id = db.Column(db.String(120), unique=True, index=True)
    scan_fingerprint = db.Column(db.String(64), unique=True, index=True)
    import_batch_id = db.Column(db.String(120), index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.now())

    defects = db.relationship('Defect', backref='scan', lazy=True)
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_user_id])

    @staticmethod
    def normalize_name(name: str | None) -> str | None:
        if not name:
            return None
        return ' '.join(name.strip().lower().split())

    @staticmethod
    def build_fingerprint(model_path: str | None, project_name: str | None, source_upload_id: str | None) -> str | None:
        payload = '|'.join([
            (model_path or '').strip().lower(),
            (project_name or '').strip().lower(),
            (source_upload_id or '').strip().lower(),
        ])
        if not payload.replace('|', '').strip():
            return None
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

class Defect(db.Model):
    __tablename__ = 'defects'
    __table_args__ = (
        db.UniqueConstraint('scan_id', 'source_defect_key', name='uq_defects_scan_source_key'),
    )
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False)
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    z = db.Column(db.Float, nullable=False)
    element = db.Column(db.String(255))  # Auto-populated from mesh name (non-editable)
    location = db.Column(db.String(100))  # Room/area location (editable dropdown)
    defect_type = db.Column(db.String(50), default='Unknown')  # crack, water damage, structural, finish, electrical, plumbing
    severity = db.Column(db.String(20), default='Medium')  # Low, Medium, High, Critical
    priority = db.Column(db.String(20), default='Medium')  # Urgent, High, Medium, Low
    description = db.Column(db.Text)  # Auto-populated from mesh label (non-editable)
    status = db.Column(db.String(50), default='Reported')  # Reported, Under Review, Fixed
    image_path = db.Column(db.String(500))  # Path to snapshot image
    notes = db.Column(db.Text)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_at = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime)
    source_defect_key = db.Column(db.String(160), index=True)
    coord_key = db.Column(db.String(200), index=True)
    import_batch_id = db.Column(db.String(120), index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_manual = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    activities = db.relationship('ActivityLog', backref='defect', lazy=True)
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_user_id])

    @staticmethod
    def build_coord_key(x: float, y: float, z: float, defect_type: str | None, element: str | None) -> str:
        rounded = f"{round(float(x), 3):.3f}|{round(float(y), 3):.3f}|{round(float(z), 3):.3f}"
        dtype = (defect_type or '').strip().lower()
        elem = (element or '').strip().lower()
        return f"{rounded}|{dtype}|{elem}"

    @property
    def risk_score(self):
        """Calculate a risk score (0-100) based on severity and defect type."""
        # Severity Factor (Max 50 points)
        severity_points = 0
        if self.severity == 'Critical': severity_points = 50
        elif self.severity == 'High': severity_points = 35
        elif self.severity == 'Medium': severity_points = 20
        elif self.severity == 'Low': severity_points = 5

        # Type Factor (Max 50 points)
        type_points = 10  # default for unknown/cosmetic
        dt = self.defect_type.lower() if self.defect_type else ''
        if 'structural' in dt:
            type_points = 50
        elif 'water' in dt or 'electrical' in dt or 'crack' in dt:
            type_points = 35
        elif 'mechanical' in dt or 'plumbing' in dt:
            type_points = 20
        
        return severity_points + type_points

    def auto_calculate_priority(self):
        """Update the priority column based on the risk score."""
        score = self.risk_score
        if score >= 80:
            self.priority = 'Urgent'
        elif score >= 60:
            self.priority = 'High'
        elif score >= 30:
            self.priority = 'Medium'
        else:
            self.priority = 'Low'

# Assignment model removed

class ActivityLog(db.Model):
    """Track all changes/activities on defects"""
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    defect_id = db.Column(db.Integer, db.ForeignKey('defects.id'))
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'))
    action = db.Column(db.String(255), nullable=False)  # "updated status", "assigned to", "updated priority"
    old_value = db.Column(db.String(255))  # Previous value
    new_value = db.Column(db.String(255))  # New value
    event_uuid = db.Column(db.String(80), unique=True, index=True)
    request_id = db.Column(db.String(80), index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    scan = db.relationship('Scan', backref='activities')
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())