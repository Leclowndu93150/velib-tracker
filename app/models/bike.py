from app import db
from datetime import datetime
from sqlalchemy import Index

class Bike(db.Model):
    __tablename__ = 'bikes'
    
    id = db.Column(db.Integer, primary_key=True)
    bike_name = db.Column(db.String(20), unique=True, nullable=False, index=True)
    bike_electric = db.Column(db.Boolean, default=False)
    
    # Current status
    current_station_id = db.Column(db.Integer, db.ForeignKey('stations.id'))
    current_status = db.Column(db.String(20), default='unknown')  # disponible, indisponible, in_transit, missing
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Precise tracking for trip calculation
    arrived_at_station = db.Column(db.DateTime)  # When bike arrived at current station
    left_station_at = db.Column(db.DateTime)  # When bike left previous station
    previous_station_id = db.Column(db.Integer, db.ForeignKey('stations.id'))  # Previous station
    
    # Statistics
    total_trips = db.Column(db.Integer, default=0)
    total_distance = db.Column(db.Float, default=0)
    total_duration = db.Column(db.Integer, default=0)  # in seconds
    boomerang_count = db.Column(db.Integer, default=0)
    
    # Malfunction indicators
    potential_malfunction = db.Column(db.Boolean, default=False)
    malfunction_score = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    snapshots = db.relationship('BikeSnapshot', backref='bike', lazy='dynamic', cascade='all, delete-orphan')
    trips = db.relationship('Trip', backref='bike', lazy='dynamic')
    malfunctions = db.relationship('MalfunctionLog', backref='bike', lazy='dynamic')
    current_station = db.relationship('Station', foreign_keys=[current_station_id])
    previous_station = db.relationship('Station', foreign_keys=[previous_station_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'bike_name': self.bike_name,
            'bike_electric': self.bike_electric,
            'current_station_id': self.current_station_id,
            'current_status': self.current_status,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'total_trips': self.total_trips,
            'total_distance': round(self.total_distance, 2),
            'total_duration': self.total_duration,
            'boomerang_count': self.boomerang_count,
            'potential_malfunction': self.potential_malfunction,
            'malfunction_score': round(self.malfunction_score, 2)
        }


class BikeSnapshot(db.Model):
    __tablename__ = 'bike_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    bike_id = db.Column(db.Integer, db.ForeignKey('bikes.id'), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Bike status at snapshot time
    bike_status = db.Column(db.String(20))
    dock_position = db.Column(db.String(10))
    bike_rate = db.Column(db.Integer)
    last_rate_date = db.Column(db.DateTime)
    number_of_rates = db.Column(db.Integer)
    bike_block_cause = db.Column(db.String(10))
    
    __table_args__ = (
        Index('idx_bike_snapshot_lookup', 'bike_id', 'timestamp'),
        Index('idx_station_snapshot_lookup', 'station_id', 'timestamp'),
        Index('idx_snapshot_timestamp', 'timestamp'),
    )