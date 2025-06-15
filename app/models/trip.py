from app import db
from datetime import datetime
from sqlalchemy import Index
from geopy.distance import geodesic

class Trip(db.Model):
    __tablename__ = 'trips'
    
    id = db.Column(db.Integer, primary_key=True)
    bike_id = db.Column(db.Integer, db.ForeignKey('bikes.id'), nullable=False)
    start_station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    end_station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer)  # in seconds
    distance = db.Column(db.Float)  # in km
    avg_speed = db.Column(db.Float)  # in km/h
    
    # Trip classification
    is_boomerang = db.Column(db.Boolean, default=False)
    is_short_trip = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_trip_bike_time', 'bike_id', 'start_time'),
        Index('idx_trip_stations', 'start_station_id', 'end_station_id'),
        Index('idx_trip_time', 'start_time', 'end_time'),
    )
    
    def calculate_metrics(self):
        """Calculate trip duration, distance, and speed"""
        if self.start_time and self.end_time:
            self.duration = int((self.end_time - self.start_time).total_seconds())
            
            if self.start_station and self.end_station:
                start_coords = (self.start_station.latitude, self.start_station.longitude)
                end_coords = (self.end_station.latitude, self.end_station.longitude)
                self.distance = geodesic(start_coords, end_coords).kilometers
                
                if self.duration > 0:
                    self.avg_speed = (self.distance / (self.duration / 3600))
                    
                # Classify trip
                self.is_boomerang = (self.start_station_id == self.end_station_id and self.duration < 600)
                self.is_short_trip = (self.duration < 300)  # Less than 5 minutes
    
    def to_dict(self):
        return {
            'id': self.id,
            'bike_id': self.bike_id,
            'start_station_id': self.start_station_id,
            'end_station_id': self.end_station_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'distance': round(self.distance, 2) if self.distance else None,
            'avg_speed': round(self.avg_speed, 2) if self.avg_speed else None,
            'is_boomerang': self.is_boomerang,
            'is_short_trip': self.is_short_trip
        }