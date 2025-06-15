import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from app import db
from app.models import Trip, Bike, Station, StationState
import logging

logger = logging.getLogger(__name__)


class TripReconstructor:
    def __init__(self, max_trip_duration=10800):  # 3 hours max
        self.max_trip_duration = max_trip_duration
        
    def reconstruct_trips(self):
        """Reconstruct trips from station state changes"""
        # Get unprocessed station states from last 3 hours
        cutoff = datetime.utcnow() - timedelta(hours=3)
        
        # Get pairs of consecutive timestamps
        timestamps = db.session.query(StationState.timestamp)\
                              .filter(StationState.timestamp >= cutoff)\
                              .filter(StationState.processed == False)\
                              .distinct()\
                              .order_by(StationState.timestamp)\
                              .all()
        
        timestamps = [ts[0] for ts in timestamps]
        
        if len(timestamps) < 2:
            return
        
        for i in range(len(timestamps) - 1):
            current_time = timestamps[i]
            next_time = timestamps[i + 1]
            
            # Get station states
            current_state = self._get_station_state(current_time)
            next_state = self._get_station_state(next_time)
            
            if current_state and next_state:
                trips = self._detect_trips(current_state, next_state, current_time, next_time)
                
                for trip_data in trips:
                    self._create_trip(trip_data)
                
                # Mark states as processed
                self._mark_processed(current_time)
        
        db.session.commit()
    
    def _get_station_state(self, timestamp: datetime) -> Optional[Dict]:
        """Get station state from database"""
        states = StationState.query.filter_by(timestamp=timestamp).all()
        
        if not states:
            return None
        
        result = {}
        for state in states:
            result[str(state.station_id)] = json.loads(state.bike_names)
        
        return result
    
    def _detect_trips(self, current_state: Dict, next_state: Dict, 
                     current_time: datetime, next_time: datetime) -> List[Dict]:
        """Detect trips between two station states"""
        trips = []
        
        # Track bike departures (OUT events)
        departures = {}  # {bike_name: station_id}
        
        for station_id, bikes in current_state.items():
            next_bikes = set(next_state.get(station_id, []))
            current_bikes = set(bikes)
            
            # Bikes that left this station
            departed = current_bikes - next_bikes
            for bike_name in departed:
                departures[bike_name] = int(station_id)
        
        # Track bike arrivals (IN events) and match with departures
        for station_id, bikes in next_state.items():
            current_bikes = set(current_state.get(station_id, []))
            next_bikes = set(bikes)
            
            # Bikes that arrived at this station
            arrived = next_bikes - current_bikes
            for bike_name in arrived:
                if bike_name in departures:
                    # Found a complete trip
                    departure_station_id = departures[bike_name]
                    arrival_station_id = int(station_id)
                    
                    trips.append({
                        'bike_name': bike_name,
                        'start_station_id': departure_station_id,
                        'end_station_id': arrival_station_id,
                        'start_time': current_time,
                        'end_time': next_time
                    })
        
        return trips
    
    def _create_trip(self, trip_data: Dict):
        """Create a trip record from detected trip data"""
        bike = Bike.query.filter_by(bike_name=trip_data['bike_name']).first()
        if not bike:
            return
        
        # Check if trip already exists
        existing_trip = Trip.query.filter_by(
            bike_id=bike.id,
            start_time=trip_data['start_time'],
            end_time=trip_data['end_time']
        ).first()
        
        if existing_trip:
            return
        
        trip = Trip(
            bike_id=bike.id,
            start_station_id=trip_data['start_station_id'],
            end_station_id=trip_data['end_station_id'],
            start_time=trip_data['start_time'],
            end_time=trip_data['end_time']
        )
        
        # Calculate metrics
        trip.calculate_metrics()
        
        # Update bike statistics
        bike.total_trips += 1
        if trip.distance:
            bike.total_distance += trip.distance
        if trip.duration:
            bike.total_duration += trip.duration
        if trip.is_boomerang:
            bike.boomerang_count += 1
        
        db.session.add(trip)
        
        logger.info(f"Created trip for bike {bike.bike_name}: "
                   f"{trip.start_station_id} -> {trip.end_station_id}, "
                   f"duration: {trip.duration}s, distance: {trip.distance}km")
    
    def _mark_processed(self, timestamp: datetime):
        """Mark timestamp as processed"""
        StationState.query.filter_by(timestamp=timestamp).update({'processed': True})
        db.session.commit()
    
    def find_incomplete_trips(self, lookback_hours=3):
        """Find bikes that departed but haven't arrived yet"""
        cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        # Get recent timestamps
        timestamps = db.session.query(StationState.timestamp)\
                              .filter(StationState.timestamp >= cutoff_time)\
                              .distinct()\
                              .order_by(StationState.timestamp.desc())\
                              .limit(20)\
                              .all()
        
        timestamps = [ts[0] for ts in timestamps]
        
        incomplete_trips = []
        
        for i in range(len(timestamps) - 1):
            current_time = timestamps[i]
            next_time = timestamps[i + 1]
            
            if next_time < cutoff_time:
                break
                
            current_state = self._get_station_state(current_time)
            next_state = self._get_station_state(next_time)
            
            if current_state and next_state:
                # Find bikes that departed but haven't arrived
                all_current_bikes = set()
                all_next_bikes = set()
                
                for bikes in current_state.values():
                    all_current_bikes.update(bikes)
                for bikes in next_state.values():
                    all_next_bikes.update(bikes)
                
                departed_bikes = all_current_bikes - all_next_bikes
                
                for bike_name in departed_bikes:
                    bike = Bike.query.filter_by(bike_name=bike_name).first()
                    if bike and bike.current_status == 'in_transit':
                        incomplete_trips.append({
                            'bike_name': bike_name,
                            'last_seen': current_time,
                            'duration_missing': (datetime.utcnow() - current_time).total_seconds()
                        })
        
        return incomplete_trips