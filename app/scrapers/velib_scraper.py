import cloudscraper
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set
from app import db
from app.models import Station, Bike, BikeSnapshot, StationState, Trip
from app.models.bike_movement import BikeMovement
from geopy.distance import geodesic
from app.utils.timezone import get_paris_time
import logging

logger = logging.getLogger(__name__)


class VelibScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'windows',
                'mobile': False
            }
        )
        self.url = os.environ.get('VELIB_API_URL', 'https://www.velib-metropole.fr/api/secured/searchStation')
        self.headers = {
            "User-Agent": "velib/7.5.1 (com.paris.velib; build:553; iOS 15.4.0) Alamofire/7.5.1",
            "Authorization": os.environ.get('VELIB_AUTH_TOKEN'),
            "Content-Type": "application/json; charset=utf-8",
        }
        
    def fetch_all_stations(self) -> List[Dict]:
        """Fetch all station data from Velib API"""
        payload = {
            "stationName": "",
            "disponibility": "yes"
        }
        
        try:
            response = self.scraper.post(self.url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching station data: {e}")
            return []
    
    def update_stations_and_bikes(self, station_data_list: List[Dict]):
        """Update stations and bikes with differential updates"""
        # Use Paris time for everything
        timestamp = get_paris_time()
        
        # Track bikes seen in this update
        seen_bike_ids = set()
        station_bikes_current = {}  # {station_id: set(bike_names)}
        
        for data in station_data_list:
            station_info = data['station']
            station_code = station_info['code']
            
            # Update or create station with error handling
            station = Station.query.filter_by(code=station_code).first()
            if not station:
                try:
                    station = Station(
                        code=station_code,
                        name=station_info['name'],
                        latitude=station_info['gps']['latitude'],
                        longitude=station_info['gps']['longitude'],
                        station_type=station_info.get('stationType', 'PUBLIC'),
                        state=station_info.get('state', 'Operative')
                    )
                    db.session.add(station)
                    db.session.flush()  # Get station ID
                except Exception as e:
                    # Station might have been created by another process
                    db.session.rollback()
                    station = Station.query.filter_by(code=station_code).first()
                    if not station:
                        logger.error(f"Failed to create or find station {station_code}: {e}")
                        continue
            
            # Update station metrics
            station.nb_bike = data.get('nbBike', 0)
            station.nb_ebike = data.get('nbEbike', 0)
            station.nb_free_dock = data.get('nbFreeDock', 0)
            station.nb_free_edock = data.get('nbFreeEDock', 0)
            station.total_capacity = data.get('nbDock', 0) + data.get('nbEDock', 0)
            station.credit_card = data.get('creditCard', 'no') == 'yes'
            station.kiosk_state = data.get('kioskState', 'no')
            station.updated_at = timestamp
            
            # Process bikes at this station
            bikes_at_station = set()
            for bike_data in data.get('bikes', []):
                bike_name = bike_data['bikeName']
                bikes_at_station.add(bike_name)
                seen_bike_ids.add(bike_name)
                
                # Update or create bike
                bike = Bike.query.filter_by(bike_name=bike_name).first()
                if not bike:
                    bike = Bike(
                        bike_name=bike_name,
                        bike_electric=(bike_data.get('bikeElectric', 'no') == 'yes')
                    )
                    db.session.add(bike)
                    db.session.flush()
                
                # Check if bike state has changed to decide if we need a snapshot
                current_bike_status = bike_data.get('bikeStatus', 'unknown')
                current_dock_position = bike_data.get('dockPosition')
                current_bike_rate = bike_data.get('bikeRate')
                
                needs_snapshot = False
                station_changed = False
                
                # Check if this is a new bike or if critical data has changed
                if (bike.current_station_id != station.id or 
                    bike.current_status != current_bike_status or
                    abs((timestamp - bike.last_seen_at).total_seconds()) > 3600):  # Also snapshot every hour as backup
                    needs_snapshot = True
                
                # Track precise bike movements
                if bike.current_station_id != station.id:
                    station_changed = True
                    
                    # If bike was at a different station, record departure from old station
                    if bike.current_station_id is not None:
                        departure = BikeMovement(
                            bike_id=bike.id,
                            event_type='departed',
                            station_id=bike.current_station_id,
                            timestamp=bike.left_station_at or timestamp,  # Use precise time if available
                            bike_status=bike.current_status
                        )
                        db.session.add(departure)
                        bike.left_station_at = timestamp
                        bike.previous_station_id = bike.current_station_id
                    
                    # Record arrival at new station
                    arrival = BikeMovement(
                        bike_id=bike.id,
                        event_type='arrived',
                        station_id=station.id,
                        timestamp=timestamp,
                        dock_position=current_dock_position,
                        bike_status=current_bike_status
                    )
                    db.session.add(arrival)
                    bike.arrived_at_station = timestamp
                    
                    # Create trip if we have both departure and arrival
                    if bike.previous_station_id and bike.left_station_at:
                        self._create_trip_from_movement(bike, timestamp)
                
                elif bike.arrived_at_station is None:
                    # Handle initial state - bike was already at station when we started tracking
                    bike.arrived_at_station = timestamp
                    arrival = BikeMovement(
                        bike_id=bike.id,
                        event_type='arrived',
                        station_id=station.id,
                        timestamp=timestamp,
                        dock_position=current_dock_position,
                        bike_status=current_bike_status
                    )
                    db.session.add(arrival)
                
                # Update bike current status
                bike.current_station_id = station.id
                bike.current_status = current_bike_status
                bike.last_seen_at = timestamp
                
                # Only create snapshot if something meaningful changed
                if needs_snapshot:
                    snapshot = BikeSnapshot(
                        bike_id=bike.id,
                        station_id=station.id,
                        timestamp=timestamp,
                        bike_status=current_bike_status,
                        dock_position=current_dock_position,
                        bike_rate=current_bike_rate,
                        number_of_rates=bike_data.get('numberOfRates', 0),
                        bike_block_cause=bike_data.get('bikeBlockCause', '')
                    )
                    
                    # Parse last rate date if available
                    if bike_data.get('lastRateDate'):
                        try:
                            snapshot.last_rate_date = datetime.fromisoformat(
                                bike_data['lastRateDate'].replace('Z', '+00:00')
                            )
                        except:
                            pass
                    
                    db.session.add(snapshot)
            
            station_bikes_current[station.id] = bikes_at_station
        
        # Store current state in database for trip detection
        self._store_station_state_in_db(station_bikes_current, timestamp)
        
        # Mark bikes not seen as potentially in transit or missing
        all_bikes = Bike.query.filter(Bike.current_status.in_(['disponible', 'indisponible'])).all()
        for bike in all_bikes:
            if bike.bike_name not in seen_bike_ids:
                time_since_last_seen = (timestamp - bike.last_seen_at).total_seconds()
                if time_since_last_seen < 10800:  # 3 hours
                    bike.current_status = 'in_transit'
                else:
                    bike.current_status = 'missing'
                bike.current_station_id = None
        
        db.session.commit()
        logger.info(f"Updated {len(station_data_list)} stations and {len(seen_bike_ids)} bikes")
    
    def _store_station_state_in_db(self, station_bikes: Dict[int, Set[str]], timestamp: datetime):
        """Store current station state in database for trip detection"""
        # Clean up old states (older than 24 hours)
        cutoff = timestamp - timedelta(hours=24)
        db.session.query(StationState).filter(StationState.timestamp < cutoff).delete()
        
        # Store current state for each station
        for station_id, bikes in station_bikes.items():
            state = StationState(
                timestamp=timestamp,
                station_id=station_id,
                bike_names=json.dumps(list(bikes))
            )
            db.session.add(state)
        
        db.session.commit()
    
    def _create_trip_from_movement(self, bike: Bike, arrival_time: datetime):
        """Create a trip record from precise movement data"""
        if not bike.previous_station_id or not bike.left_station_at:
            return
        
        # Check if trip already exists
        existing_trip = Trip.query.filter_by(
            bike_id=bike.id,
            start_station_id=bike.previous_station_id,
            end_station_id=bike.current_station_id,
            start_time=bike.left_station_at,
            end_time=arrival_time
        ).first()
        
        if existing_trip:
            return
        
        # Create new trip with precise timing
        trip = Trip(
            bike_id=bike.id,
            start_station_id=bike.previous_station_id,
            end_station_id=bike.current_station_id,
            start_time=bike.left_station_at,
            end_time=arrival_time
        )
        
        # Calculate metrics using the Trip model's method
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
        
        logger.info(f"Created precise trip for bike {bike.bike_name}: "
                   f"{trip.start_station.name if trip.start_station else 'Unknown'} -> "
                   f"{trip.end_station.name if trip.end_station else 'Unknown'}, "
                   f"duration: {trip.duration}s, distance: {trip.distance:.2f if trip.distance else 0}km")
    
    def run_update(self):
        """Main update method to be called periodically"""
        try:
            station_data = self.fetch_all_stations()
            if station_data:
                self.update_stations_and_bikes(station_data)
                return True
            return False
        except Exception as e:
            logger.error(f"Error in update cycle: {e}")
            return False