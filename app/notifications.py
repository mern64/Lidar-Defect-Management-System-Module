"""Email notification system for LDMS.

Sends automatic email alerts when:
- A Critical severity defect is created
- A defect status is changed (e.g. Reported → Fixed)

Uses Flask-Mail with Gmail SMTP. Emails are sent in background threads
to avoid blocking the request.
"""

import threading
from typing import List, Optional

from flask import current_app, render_template_string
from flask_mail import Message

from app.extensions import mail


# ─── HTML Email Templates ────────────────────────────────────────────

CRITICAL_DEFECT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #f8fafc; }
    .container { max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .header { background: linear-gradient(135deg, #ef4444, #dc2626); padding: 24px 32px; color: white; }
    .header h1 { margin: 0; font-size: 20px; font-weight: 700; }
    .header p { margin: 8px 0 0; font-size: 14px; opacity: 0.9; }
    .body { padding: 32px; }
    .field { margin-bottom: 16px; }
    .field-label { font-size: 11px; text-transform: uppercase; font-weight: 600; color: #64748b; letter-spacing: 0.5px; margin-bottom: 4px; }
    .field-value { font-size: 15px; color: #1e293b; font-weight: 500; }
    .badge { display: inline-block; padding: 4px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; }
    .badge-critical { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    .footer { padding: 16px 32px; background: #f1f5f9; text-align: center; font-size: 12px; color: #94a3b8; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⚠️ Critical Defect Alert</h1>
      <p>A critical severity defect has been reported</p>
    </div>
    <div class="body">
      <div class="field">
        <div class="field-label">Defect ID</div>
        <div class="field-value">#{{ defect_id }}</div>
      </div>
      <div class="field">
        <div class="field-label">Project / Scan</div>
        <div class="field-value">{{ scan_name }}</div>
      </div>
      <div class="field">
        <div class="field-label">Element</div>
        <div class="field-value">{{ element or 'Not specified' }}</div>
      </div>
      <div class="field">
        <div class="field-label">Location</div>
        <div class="field-value">{{ location or 'Not specified' }}</div>
      </div>
      <div class="field">
        <div class="field-label">Type</div>
        <div class="field-value">{{ defect_type }}</div>
      </div>
      <div class="field">
        <div class="field-label">Severity</div>
        <div class="field-value"><span class="badge badge-critical">{{ severity }}</span></div>
      </div>
      <div class="field">
        <div class="field-label">Coordinates</div>
        <div class="field-value">X: {{ x }}, Y: {{ y }}, Z: {{ z }}</div>
      </div>
      {% if description %}
      <div class="field">
        <div class="field-label">Description</div>
        <div class="field-value">{{ description }}</div>
      </div>
      {% endif %}
    </div>
    <div class="footer">
      LDMS — LiDAR Defect Management System
    </div>
  </div>
</body>
</html>
"""

STATUS_CHANGE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #f8fafc; }
    .container { max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .header { background: linear-gradient(135deg, #3b82f6, #6366f1); padding: 24px 32px; color: white; }
    .header h1 { margin: 0; font-size: 20px; font-weight: 700; }
    .header p { margin: 8px 0 0; font-size: 14px; opacity: 0.9; }
    .body { padding: 32px; }
    .field { margin-bottom: 16px; }
    .field-label { font-size: 11px; text-transform: uppercase; font-weight: 600; color: #64748b; letter-spacing: 0.5px; margin-bottom: 4px; }
    .field-value { font-size: 15px; color: #1e293b; font-weight: 500; }
    .status-change { display: flex; align-items: center; gap: 12px; margin: 20px 0; padding: 16px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
    .status-old { padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    .status-arrow { color: #94a3b8; font-size: 18px; }
    .status-new { padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
    .footer { padding: 16px 32px; background: #f1f5f9; text-align: center; font-size: 12px; color: #94a3b8; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🔄 Defect Status Updated</h1>
      <p>A defect status has been changed</p>
    </div>
    <div class="body">
      <div class="field">
        <div class="field-label">Defect ID</div>
        <div class="field-value">#{{ defect_id }}</div>
      </div>
      <div class="field">
        <div class="field-label">Project / Scan</div>
        <div class="field-value">{{ scan_name }}</div>
      </div>
      <div class="field">
        <div class="field-label">Element</div>
        <div class="field-value">{{ element or 'Not specified' }}</div>
      </div>
      <div class="status-change">
        <span class="status-old">{{ old_status }}</span>
        <span class="status-arrow">→</span>
        <span class="status-new">{{ new_status }}</span>
      </div>
      <div class="field">
        <div class="field-label">Type</div>
        <div class="field-value">{{ defect_type }}</div>
      </div>
      <div class="field">
        <div class="field-label">Severity</div>
        <div class="field-value">{{ severity }}</div>
      </div>
    </div>
    <div class="footer">
      LDMS — LiDAR Defect Management System
    </div>
  </div>
</body>
</html>
"""

BULK_UPDATE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #f8fafc; }
    .container { max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .header { background: linear-gradient(135deg, #10b981, #059669); padding: 24px 32px; color: white; }
    .header h1 { margin: 0; font-size: 20px; font-weight: 700; }
    .header p { margin: 8px 0 0; font-size: 14px; opacity: 0.9; }
    .body { padding: 32px; }
    .field { margin-bottom: 16px; }
    .field-label { font-size: 11px; text-transform: uppercase; font-weight: 600; color: #64748b; letter-spacing: 0.5px; margin-bottom: 4px; }
    .field-value { font-size: 15px; color: #1e293b; font-weight: 500; }
    .summary-box { margin: 20px 0; padding: 16px; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0; text-align: center; }
    .summary-number { font-size: 24px; font-weight: 700; color: #16a34a; }
    .summary-text { font-size: 14px; color: #15803d; font-weight: 500; margin-top: 4px; }
    .defect-list { margin-top: 16px; font-size: 13px; color: #475569; }
    .footer { padding: 16px 32px; background: #f1f5f9; text-align: center; font-size: 12px; color: #94a3b8; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📋 Bulk Update Summary</h1>
      <p>Multiple defects have just been updated</p>
    </div>
    <div class="body">
      <div class="field">
        <div class="field-label">Project / Scan</div>
        <div class="field-value">{{ scan_name }}</div>
      </div>
      
      <div class="summary-box">
        <div class="summary-number">{{ update_count }}</div>
        <div class="summary-text">Defects Updated</div>
      </div>

      <div class="field">
        <div class="field-label">Updates Applied</div>
        <div class="field-value" style="display: flex; gap: 12px; flex-wrap: wrap;">
          {% if new_status %}
          <span style="padding: 4px 10px; background: #e2e8f0; border-radius: 4px; font-size: 13px;">Status → <b>{{ new_status }}</b></span>
          {% endif %}
          {% if new_priority %}
          <span style="padding: 4px 10px; background: #e2e8f0; border-radius: 4px; font-size: 13px;">Priority → <b>{{ new_priority }}</b></span>
          {% endif %}
        </div>
      </div>
      
      <div class="defect-list">
        <strong>Affected Defect IDs:</strong> {{ defect_ids | join(', ') }}
      </div>
    </div>
    <div class="footer">
      LDMS — LiDAR Defect Management System
    </div>
  </div>
</body>
</html>
"""


def _get_notification_emails() -> List[str]:
    """Get the list of email addresses to notify."""
    emails_str = current_app.config.get("NOTIFICATION_EMAILS", "")
    if not emails_str:
        return []
    return [e.strip() for e in emails_str.split(",") if e.strip()]


def _send_async_email(app, msg):
    """Send email in a background thread."""
    with app.app_context():
        try:
            mail.send(msg)
            app.logger.info("Notification email sent to %s", msg.recipients)
        except Exception as e:
            app.logger.error("Failed to send email: %s", e)


def _send_email(subject: str, html_body: str, recipients: Optional[List[str]] = None):
    """Send an email notification (non-blocking)."""
    if not current_app.config.get("MAIL_USERNAME"):
        current_app.logger.debug("Mail not configured, skipping notification.")
        return

    if recipients is None:
        recipients = _get_notification_emails()

    if not recipients:
        current_app.logger.debug("No notification recipients configured.")
        return

    msg = Message(
        subject=subject,
        recipients=recipients,
        html=html_body,
    )

    # Send in background thread to avoid blocking the request
    app = current_app._get_current_object()
    thread = threading.Thread(target=_send_async_email, args=(app, msg))
    thread.daemon = True
    thread.start()


def send_critical_defect_alert(defect):
    """Send an alert email when a Critical severity defect is created.

    Args:
        defect: The Defect model instance.
    """
    scan = defect.scan
    html = render_template_string(
        CRITICAL_DEFECT_TEMPLATE,
        defect_id=defect.id,
        scan_name=scan.name if scan else "Unknown",
        element=defect.element,
        location=defect.location,
        defect_type=defect.defect_type,
        severity=defect.severity,
        x=round(defect.x, 2),
        y=round(defect.y, 2),
        z=round(defect.z, 2),
        description=defect.description,
    )
    _send_email(
        subject=f"⚠️ LDMS Alert: Critical Defect #{defect.id} Reported",
        html_body=html,
    )


def send_status_change_notification(defect, old_status: str, new_status: str):
    """Send a notification when a defect status changes.

    Args:
        defect: The Defect model instance.
        old_status: Previous status string.
        new_status: New status string.
    """
    scan = defect.scan
    html = render_template_string(
        STATUS_CHANGE_TEMPLATE,
        defect_id=defect.id,
        scan_name=scan.name if scan else "Unknown",
        element=defect.element,
        old_status=old_status,
        new_status=new_status,
        defect_type=defect.defect_type,
        severity=defect.severity,
    )
    _send_email(
        subject=f"🔄 LDMS: Defect #{defect.id} status changed to {new_status}",
        html_body=html,
    )


def send_bulk_update_notification(scan, defect_ids: List[int], new_status: Optional[str], new_priority: Optional[str]):
    """Send a summary notification when multiple defects are updated.

    Args:
        scan: The Scan model instance.
        defect_ids: List of defect IDs updated.
        new_status: The new status applied (if any).
        new_priority: The new priority applied (if any).
    """
    if not defect_ids:
        return

    update_summary = []
    if new_status:
        update_summary.append(f"Status to '{new_status}'")
    if new_priority:
        update_summary.append(f"Priority to '{new_priority}'")
    
    summary_str = " and ".join(update_summary)

    html = render_template_string(
        BULK_UPDATE_TEMPLATE,
        scan_name=scan.name if scan else "Unknown",
        update_count=len(defect_ids),
        defect_ids=defect_ids,
        new_status=new_status,
        new_priority=new_priority,
    )
    
    _send_email(
        subject=f"📋 LDMS Bulk Update: {len(defect_ids)} defects updated out of {scan.name if scan else 'project'}",
        html_body=html,
    )


