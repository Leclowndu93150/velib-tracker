from app import db
from datetime import datetime

class MalfunctionLog(db.Model):
    __tablename__ = 'malfunction_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    bike_id = db.Column(db.Integer, db.ForeignKey('bikes.id'), nullable=False)
    
    malfunction_type = db.Column(db.String(50), nullable=False)  # boomerang, low_speed, battery_issue, missing, stuck
    severity = db.Column(db.Integer, default=1)  # 1-5 scale
    description = db.Column(db.Text)
    
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Related data
    related_trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'))
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'bike_id': self.bike_id,
            'malfunction_type': self.malfunction_type,
            'severity': self.severity,
            'description': self.description,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'is_active': self.is_active
        }