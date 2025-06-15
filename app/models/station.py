from app import db
from datetime import datetime
from sqlalchemy import Index

class Station(db.Model):
    __tablename__ = 'stations'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    station_type = db.Column(db.String(20))
    state = db.Column(db.String(20))
    
    # Current status (updated frequently)
    nb_bike = db.Column(db.Integer, default=0)
    nb_ebike = db.Column(db.Integer, default=0)
    nb_free_dock = db.Column(db.Integer, default=0)
    nb_free_edock = db.Column(db.Integer, default=0)
    total_capacity = db.Column(db.Integer, default=0)
    
    # Metadata
    credit_card = db.Column(db.Boolean, default=False)
    overflow = db.Column(db.Boolean, default=False)
    kiosk_state = db.Column(db.String(10))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bike_snapshots = db.relationship('BikeSnapshot', backref='station', lazy='dynamic')
    trip_starts = db.relationship('Trip', foreign_keys='Trip.start_station_id', backref='start_station', lazy='dynamic')
    trip_ends = db.relationship('Trip', foreign_keys='Trip.end_station_id', backref='end_station', lazy='dynamic')
    
    __table_args__ = (
        Index('idx_station_location', 'latitude', 'longitude'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'station_type': self.station_type,
            'state': self.state,
            'nb_bike': self.nb_bike,
            'nb_ebike': self.nb_ebike,
            'nb_free_dock': self.nb_free_dock,
            'nb_free_edock': self.nb_free_edock,
            'total_capacity': self.total_capacity,
            'credit_card': self.credit_card,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }