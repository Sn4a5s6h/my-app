from datetime import datetime
from database import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50))
    table_name = db.Column(db.String(100))
    record_id = db.Column(db.Integer)
    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(200))

    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))

    def __repr__(self):
        return f'<AuditLog {self.action} - {self.table_name} ({self.timestamp})>'
