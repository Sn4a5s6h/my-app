from flask import request
from database.models import AuditLog, db
from flask_login import current_user
import logging

def record_audit_log(action, table_name=None, record_id=None, old_values=None, new_values=None):
    """تسجيل حركة في سجل التدقيق"""
    try:
        audit_log = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=str(old_values) if old_values else None,
            new_values=str(new_values) if new_values else None,
            ip_address=request.remote_addr if request else None,
            user_agent=request.user_agent.string if request and request.user_agent else None
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        logging.error(f"Error recording audit log: {e}")
