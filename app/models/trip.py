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
                self.is_boomerang = (self.start_station_id == self.end_station_id and self.duration <= 300)  # 5 minutes or less
                self.is_short_trip = (self.duration < 300)  # Less than 5 minutes
    
    def to_dict(self):
        # Import here to avoid circular imports
        from app.utils.timezone import format_paris_time, format_paris_date
        
        # Format times with precise hour:minute display in Paris timezone
        start_time_formatted = None
        end_time_formatted = None
        start_date = None
        end_date = None
        
        if self.start_time:
            start_time_formatted = format_paris_time(self.start_time, '%H:%M:%S')
            start_date = format_paris_date(self.start_time, '%d/%m/%Y')
            
        if self.end_time:
            end_time_formatted = format_paris_time(self.end_time, '%H:%M:%S')
            end_date = format_paris_date(self.end_time, '%d/%m/%Y')
        
        # Human-readable duration
        duration_formatted = self._format_duration(self.duration) if self.duration else None
        
        return {
            'id': self.id,
            'bike_id': self.bike_id,
            'start_station_id': self.start_station_id,
            'end_station_id': self.end_station_id,
            'start_station_name': self.start_station.name if self.start_station else 'Unknown',
            'end_station_name': self.end_station.name if self.end_station else 'Unknown',
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'start_time_formatted': start_time_formatted,
            'end_time_formatted': end_time_formatted,
            'start_date': start_date,
            'end_date': end_date,
            'duration': self.duration,
            'duration_formatted': duration_formatted,
            'distance': round(self.distance, 2) if self.distance else None,
            'avg_speed': round(self.avg_speed, 2) if self.avg_speed else None,
            'is_boomerang': self.is_boomerang,
            'is_short_trip': self.is_short_trip
        }
    
    def _format_duration(self, seconds):
        """Format duration in a human-readable way"""
        if not seconds:
            return "0s"
            
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if remaining_seconds > 0 or not parts:  # Show seconds if no other parts or if only seconds
            parts.append(f"{remaining_seconds}s")
            
        return " ".join(parts)
    
    def get_precise_timing(self):
        """Get precise timing information for this trip in Paris timezone"""
        # Import here to avoid circular imports
        from app.utils.timezone import format_paris_time, format_paris_date
        
        return {
            'taken_at': {
                'date': format_paris_date(self.start_time, '%d/%m/%Y') if self.start_time else None,
                'time': format_paris_time(self.start_time, '%H:%M:%S') if self.start_time else None,
                'timestamp': self.start_time.isoformat() if self.start_time else None
            },
            'returned_at': {
                'date': format_paris_date(self.end_time, '%d/%m/%Y') if self.end_time else None,
                'time': format_paris_time(self.end_time, '%H:%M:%S') if self.end_time else None,
                'timestamp': self.end_time.isoformat() if self.end_time else None
            },
            'duration': {
                'seconds': self.duration,
                'formatted': self._format_duration(self.duration) if self.duration else None,
                'minutes': round(self.duration / 60, 1) if self.duration else None
            }
        }