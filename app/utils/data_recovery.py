from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import func, and_, or_
from app import db
from app.models import Bike, Trip, Station, StationState, BikeSnapshot, MalfunctionLog
import logging

logger = logging.getLogger(__name__)


class DataRecovery:
    """Handle data cleanup and recovery for when the scraper was offline"""
    
    def __init__(self):
        self.max_trip_duration = 8 * 3600  # 8 hours max realistic trip
        self.missing_threshold = 24 * 3600  # 24 hours before marking as missing
        self.cleanup_age = 7 * 24 * 3600  # 7 days for old data cleanup
        
    def run_full_recovery(self):
        """Run all recovery procedures"""
        logger.info("Starting data recovery process...")
        
        # 1. Clean up incomplete trips
        self.cleanup_incomplete_trips()
        
        # 2. Fix bikes stuck in "in_transit" status
        self.fix_stuck_in_transit_bikes()
        
        # 3. Clean up old station states
        self.cleanup_old_station_states()
        
        # 4. Clean up old snapshots
        self.cleanup_old_snapshots()
        
        # 5. Resolve orphaned malfunctions
        self.cleanup_orphaned_malfunctions()
        
        # 6. Update bike statistics
        self.recalculate_bike_statistics()
        
        # 7. Mark truly missing bikes
        self.mark_missing_bikes()
        
        db.session.commit()
        logger.info("Data recovery process completed")
    
    def cleanup_incomplete_trips(self):
        """Remove or fix incomplete/impossible trips"""
        cutoff = datetime.utcnow() - timedelta(seconds=self.max_trip_duration)
        
        # Find trips that started too long ago and never ended (impossible)
        incomplete_trips = Trip.query.filter(
            and_(
                Trip.start_time < cutoff,
                Trip.end_time.is_(None)
            )
        ).all()
        
        logger.info(f"Found {len(incomplete_trips)} incomplete trips to remove")
        
        for trip in incomplete_trips:
            # Log the deletion
            logger.warning(f"Removing incomplete trip for bike {trip.bike.bike_name} "
                         f"started at {trip.start_time}")
            db.session.delete(trip)
        
        # Also remove trips with impossible durations (negative or too long)
        impossible_trips = Trip.query.filter(
            or_(
                Trip.duration < 0,
                Trip.duration > self.max_trip_duration,
                Trip.distance.isnot(None) and (Trip.distance < 0),
                Trip.distance.isnot(None) and (Trip.distance > 100)  # 100km max realistic
            )
        ).all()
        
        logger.info(f"Found {len(impossible_trips)} impossible trips to remove")
        
        for trip in impossible_trips:
            logger.warning(f"Removing impossible trip for bike {trip.bike.bike_name}: "
                         f"duration={trip.duration}s, distance={trip.distance}km")
            db.session.delete(trip)
    
    def fix_stuck_in_transit_bikes(self):
        """Fix bikes that are stuck in 'in_transit' status for too long"""
        cutoff = datetime.utcnow() - timedelta(seconds=self.max_trip_duration)
        
        stuck_bikes = Bike.query.filter(
            and_(
                Bike.current_status == 'in_transit',
                Bike.last_seen_at < cutoff
            )
        ).all()
        
        logger.info(f"Found {len(stuck_bikes)} bikes stuck in transit")
        
        for bike in stuck_bikes:
            # Check if we have recent snapshots to determine actual location
            recent_snapshot = BikeSnapshot.query.filter_by(bike_id=bike.id)\
                                               .order_by(BikeSnapshot.timestamp.desc())\
                                               .first()
            
            if recent_snapshot and recent_snapshot.timestamp > cutoff:
                # Bike was seen recently at a station
                bike.current_station_id = recent_snapshot.station_id
                bike.current_status = recent_snapshot.bike_status or 'disponible'
                bike.last_seen_at = recent_snapshot.timestamp
                logger.info(f"Recovered bike {bike.bike_name} to station {recent_snapshot.station_id}")
            else:
                # Mark as missing
                bike.current_status = 'missing'
                bike.current_station_id = None
                logger.warning(f"Marked bike {bike.bike_name} as missing (stuck in transit)")
    
    def cleanup_old_station_states(self):
        """Remove old station state records to save space"""
        cutoff = datetime.utcnow() - timedelta(seconds=self.cleanup_age)
        
        old_states = StationState.query.filter(StationState.timestamp < cutoff)
        count = old_states.count()
        old_states.delete()
        
        logger.info(f"Cleaned up {count} old station state records")
    
    def cleanup_old_snapshots(self):
        """Remove old bike snapshots, keeping only recent ones"""
        cutoff = datetime.utcnow() - timedelta(seconds=self.cleanup_age)
        
        old_snapshots = BikeSnapshot.query.filter(BikeSnapshot.timestamp < cutoff)
        count = old_snapshots.count()
        old_snapshots.delete()
        
        logger.info(f"Cleaned up {count} old bike snapshot records")
    
    def cleanup_orphaned_malfunctions(self):
        """Clean up malfunction logs for bikes that no longer exist or are resolved"""
        # Remove malfunctions for non-existent bikes
        orphaned = db.session.query(MalfunctionLog)\
                            .outerjoin(Bike, MalfunctionLog.bike_id == Bike.id)\
                            .filter(Bike.id.is_(None))
        
        count = orphaned.count()
        orphaned.delete(synchronize_session=False)
        
        # Auto-resolve old active malfunctions (older than 30 days)
        old_cutoff = datetime.utcnow() - timedelta(days=30)
        old_malfunctions = MalfunctionLog.query.filter(
            and_(
                MalfunctionLog.is_active == True,
                MalfunctionLog.detected_at < old_cutoff
            )
        ).all()
        
        for malfunction in old_malfunctions:
            malfunction.is_active = False
            malfunction.resolved_at = datetime.utcnow()
        
        logger.info(f"Cleaned up {count} orphaned malfunctions and auto-resolved {len(old_malfunctions)} old ones")
    
    def recalculate_bike_statistics(self):
        """Recalculate bike statistics from actual trip data"""
        bikes = Bike.query.all()
        
        for bike in bikes:
            # Recalculate from actual trips
            trips = Trip.query.filter_by(bike_id=bike.id).all()
            
            bike.total_trips = len(trips)
            bike.total_distance = sum(trip.distance or 0 for trip in trips)
            bike.total_duration = sum(trip.duration or 0 for trip in trips)
            bike.boomerang_count = sum(1 for trip in trips if trip.is_boomerang)
        
        logger.info(f"Recalculated statistics for {len(bikes)} bikes")
    
    def mark_missing_bikes(self):
        """Mark bikes as missing if they haven't been seen for too long"""
        cutoff = datetime.utcnow() - timedelta(seconds=self.missing_threshold)
        
        potentially_missing = Bike.query.filter(
            and_(
                Bike.last_seen_at < cutoff,
                Bike.current_status != 'missing'
            )
        ).all()
        
        for bike in potentially_missing:
            bike.current_status = 'missing'
            bike.current_station_id = None
            
            # Log as malfunction
            existing_missing = MalfunctionLog.query.filter_by(
                bike_id=bike.id,
                malfunction_type='missing',
                is_active=True
            ).first()
            
            if not existing_missing:
                malfunction = MalfunctionLog(
                    bike_id=bike.id,
                    malfunction_type='missing',
                    severity=4,
                    description=f"Bike not seen for over {self.missing_threshold/3600:.1f} hours"
                )
                db.session.add(malfunction)
        
        logger.info(f"Marked {len(potentially_missing)} bikes as missing")
    
    def reset_bike_status_from_snapshots(self):
        """Reset all bike statuses based on latest snapshots"""
        logger.info("Resetting bike statuses from latest snapshots...")
        
        # Get latest snapshot for each bike
        latest_snapshots = db.session.query(
            BikeSnapshot.bike_id,
            func.max(BikeSnapshot.timestamp).label('latest_time')
        ).group_by(BikeSnapshot.bike_id).subquery()
        
        current_snapshots = db.session.query(BikeSnapshot)\
                                    .join(latest_snapshots, 
                                          and_(BikeSnapshot.bike_id == latest_snapshots.c.bike_id,
                                               BikeSnapshot.timestamp == latest_snapshots.c.latest_time))\
                                    .all()
        
        for snapshot in current_snapshots:
            bike = snapshot.bike
            bike.current_station_id = snapshot.station_id
            bike.current_status = snapshot.bike_status or 'disponible'
            bike.last_seen_at = snapshot.timestamp
        
        logger.info(f"Reset status for {len(current_snapshots)} bikes from snapshots")
        db.session.commit()
    
    def cleanup_duplicate_trips(self):
        """Remove duplicate trip entries"""
        # Find trips with same bike, start time, and stations
        duplicates = db.session.query(Trip)\
                              .group_by(Trip.bike_id, Trip.start_time, Trip.start_station_id, Trip.end_station_id)\
                              .having(func.count(Trip.id) > 1)\
                              .all()
        
        removed_count = 0
        for trip in duplicates:
            # Keep the first one, remove the rest
            other_trips = Trip.query.filter(
                and_(
                    Trip.bike_id == trip.bike_id,
                    Trip.start_time == trip.start_time,
                    Trip.start_station_id == trip.start_station_id,
                    Trip.end_station_id == trip.end_station_id,
                    Trip.id != trip.id
                )
            ).all()
            
            for dup_trip in other_trips:
                db.session.delete(dup_trip)
                removed_count += 1
        
        logger.info(f"Removed {removed_count} duplicate trips")
        db.session.commit()
    
    def get_recovery_report(self) -> Dict:
        """Generate a report of current data health"""
        now = datetime.utcnow()
        
        # Count various issues
        old_cutoff = now - timedelta(hours=24)
        very_old_cutoff = now - timedelta(days=7)
        
        report = {
            'timestamp': now.isoformat(),
            'total_bikes': Bike.query.count(),
            'total_stations': Station.query.count(),
            'total_trips': Trip.query.count(),
            'issues': {
                'bikes_in_transit': Bike.query.filter_by(current_status='in_transit').count(),
                'missing_bikes': Bike.query.filter_by(current_status='missing').count(),
                'bikes_not_seen_24h': Bike.query.filter(Bike.last_seen_at < old_cutoff).count(),
                'active_malfunctions': MalfunctionLog.query.filter_by(is_active=True).count(),
                'old_station_states': StationState.query.filter(StationState.timestamp < very_old_cutoff).count(),
                'old_snapshots': BikeSnapshot.query.filter(BikeSnapshot.timestamp < very_old_cutoff).count(),
            },
            'data_age': {
                'newest_snapshot': BikeSnapshot.query.order_by(BikeSnapshot.timestamp.desc()).first(),
                'oldest_snapshot': BikeSnapshot.query.order_by(BikeSnapshot.timestamp.asc()).first(),
                'newest_trip': Trip.query.order_by(Trip.start_time.desc()).first(),
                'oldest_trip': Trip.query.order_by(Trip.start_time.asc()).first(),
            }
        }
        
        # Convert datetime objects to strings
        for key in ['newest_snapshot', 'oldest_snapshot']:
            if report['data_age'][key]:
                report['data_age'][key] = report['data_age'][key].timestamp.isoformat()
        
        for key in ['newest_trip', 'oldest_trip']:
            if report['data_age'][key]:
                report['data_age'][key] = report['data_age'][key].start_time.isoformat()
        
        return report