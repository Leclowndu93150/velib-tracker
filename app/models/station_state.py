from app import db
from datetime import datetime
from sqlalchemy import Index

class StationState(db.Model):
    """Store station states for trip detection"""
    __tablename__ = 'station_states'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    bike_names = db.Column(db.Text)  # JSON string of bike names
    processed = db.Column(db.Boolean, default=False)
    
    __table_args__ = (
        Index('idx_station_state_lookup', 'timestamp', 'station_id'),
        Index('idx_state_processed', 'processed', 'timestamp'),
    )