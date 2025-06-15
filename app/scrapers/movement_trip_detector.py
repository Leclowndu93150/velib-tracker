from datetime import datetime, timedelta
from typing import List, Dict
from app import db
from app.models import Trip, Bike, Station
from app.models.bike_movement import BikeMovement
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)


class MovementTripDetector:
    """Detect trips from precise bike movement events"""
    
    def __init__(self, max_trip_duration=10800, min_trip_duration=60):  # 3 hours max, 1 minute min
        self.max_trip_duration = max_trip_duration
        self.min_trip_duration = min_trip_duration
    
    def detect_trips_from_movements(self, lookback_hours=1):
        """Detect trips from unprocessed bike movements"""
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        # Get all departure events that don't have corresponding trips yet
        departures = BikeMovement.query.filter(
            and_(
                BikeMovement.event_type == 'departed',
                BikeMovement.timestamp >= cutoff
            )
        ).order_by(BikeMovement.timestamp).all()
        
        trips_created = 0
        
        for departure in departures:
            # Find corresponding arrival for this bike after this departure
            arrival = BikeMovement.query.filter(
                and_(
                    BikeMovement.bike_id == departure.bike_id,
                    BikeMovement.event_type == 'arrived',
                    BikeMovement.timestamp > departure.timestamp,
                    BikeMovement.timestamp <= departure.timestamp + timedelta(seconds=self.max_trip_duration)
                )
            ).order_by(BikeMovement.timestamp).first()
            
            if arrival:
                # Check if trip already exists
                existing_trip = Trip.query.filter_by(
                    bike_id=departure.bike_id,
                    start_station_id=departure.station_id,
                    end_station_id=arrival.station_id,
                    start_time=departure.timestamp,
                    end_time=arrival.timestamp
                ).first()
                
                if not existing_trip:
                    trip = self._create_trip_from_movements(departure, arrival)
                    if trip:
                        trips_created += 1
        
        if trips_created > 0:
            db.session.commit()
            logger.info(f"Created {trips_created} trips from movement detection")
        
        return trips_created
    
    def _create_trip_from_movements(self, departure: BikeMovement, arrival: BikeMovement) -> Trip:
        """Create a trip from departure and arrival movements"""
        duration = (arrival.timestamp - departure.timestamp).total_seconds()
        
        # Validate trip duration
        if duration < self.min_trip_duration:
            logger.debug(f"Skipping short trip for bike {departure.bike.bike_name}: {duration}s")
            return None
        
        if duration > self.max_trip_duration:
            logger.debug(f"Skipping long trip for bike {departure.bike.bike_name}: {duration}s")
            return None
        
        # Create trip
        trip = Trip(
            bike_id=departure.bike_id,
            start_station_id=departure.station_id,
            end_station_id=arrival.station_id,
            start_time=departure.timestamp,
            end_time=arrival.timestamp
        )
        
        # Calculate metrics
        trip.calculate_metrics()
        
        # Update bike statistics
        bike = departure.bike
        bike.total_trips += 1
        if trip.distance:
            bike.total_distance += trip.distance
        if trip.duration:
            bike.total_duration += trip.duration
        if trip.is_boomerang:
            bike.boomerang_count += 1
        
        db.session.add(trip)
        
        logger.info(f"Created movement-based trip for bike {bike.bike_name}: "
                   f"{departure.station.name} -> {arrival.station.name}, "
                   f"duration: {duration}s, distance: {trip.distance:.2f if trip.distance else 0}km")
        
        return trip
    
    def get_incomplete_trips(self, lookback_hours=3) -> List[Dict]:
        """Find bikes that departed but haven't arrived yet"""
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        
        # Get all departures without corresponding arrivals
        incomplete = []
        
        departures = BikeMovement.query.filter(
            and_(
                BikeMovement.event_type == 'departed',
                BikeMovement.timestamp >= cutoff
            )
        ).all()
        
        for departure in departures:
            # Check if there's a corresponding arrival
            arrival = BikeMovement.query.filter(
                and_(
                    BikeMovement.bike_id == departure.bike_id,
                    BikeMovement.event_type == 'arrived',
                    BikeMovement.timestamp > departure.timestamp
                )
            ).first()
            
            if not arrival:
                duration_missing = (datetime.utcnow() - departure.timestamp).total_seconds()
                incomplete.append({
                    'bike_name': departure.bike.bike_name if departure.bike else 'Unknown',
                    'departure_station': departure.station.name if departure.station else 'Unknown',
                    'departure_time': departure.timestamp,
                    'duration_missing': duration_missing
                })
        
        return incomplete