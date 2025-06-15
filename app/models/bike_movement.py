from app import db
from datetime import datetime
from sqlalchemy import Index

class BikeMovement(db.Model):
    """Track precise bike movements between stations"""
    __tablename__ = 'bike_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    bike_id = db.Column(db.Integer, db.ForeignKey('bikes.id'), nullable=False)
    
    # Movement details
    event_type = db.Column(db.String(10), nullable=False)  # 'departed' or 'arrived'
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Optional context
    dock_position = db.Column(db.String(10))
    bike_status = db.Column(db.String(20))  # disponible, indisponible
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    bike = db.relationship('Bike', backref='movements')
    station = db.relationship('Station', backref='bike_movements')
    
    __table_args__ = (
        Index('idx_bike_movement_lookup', 'bike_id', 'timestamp'),
        Index('idx_movement_events', 'event_type', 'timestamp'),
        Index('idx_station_movements', 'station_id', 'timestamp'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'bike_id': self.bike_id,
            'bike_name': self.bike.bike_name if self.bike else None,
            'event_type': self.event_type,
            'station_id': self.station_id,
            'station_name': self.station.name if self.station else None,
            'timestamp': self.timestamp.isoformat(),
            'dock_position': self.dock_position,
            'bike_status': self.bike_status
        }