from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import func
from app import db
from app.models import Bike, Trip, MalfunctionLog, BikeSnapshot
import logging

logger = logging.getLogger(__name__)


class MalfunctionDetector:
    def __init__(self):
        self.boomerang_threshold = 3  # Number of boomerangs to flag
        self.low_speed_threshold = 8.0  # km/h for electric bikes
        self.missing_hours_threshold = 24  # Hours before marking as missing
        self.stuck_days_threshold = 7  # Days without movement
        
    def detect_all_malfunctions(self):
        """Run all malfunction detection algorithms"""
        self.detect_boomerang_bikes()
        self.detect_low_speed_bikes()
        self.detect_missing_bikes()
        self.detect_stuck_bikes()
        self.detect_battery_issues()
        self.update_malfunction_scores()
        
    def detect_boomerang_bikes(self):
        """Detect bikes with excessive boomerang trips"""
        # Find bikes with recent boomerangs
        recent_cutoff = datetime.utcnow() - timedelta(days=1)
        
        boomerang_stats = db.session.query(
            Trip.bike_id,
            func.count(Trip.id).label('boomerang_count'),
            func.max(Trip.end_time).label('last_boomerang')
        ).filter(
            Trip.is_boomerang == True,
            Trip.start_time >= recent_cutoff
        ).group_by(Trip.bike_id).having(
            func.count(Trip.id) >= self.boomerang_threshold
        ).all()
        
        for stat in boomerang_stats:
            bike = Bike.query.get(stat.bike_id)
            if bike:
                # Check if already flagged
                existing = MalfunctionLog.query.filter_by(
                    bike_id=bike.id,
                    malfunction_type='boomerang',
                    is_active=True
                ).first()
                
                if not existing:
                    malfunction = MalfunctionLog(
                        bike_id=bike.id,
                        malfunction_type='boomerang',
                        severity=min(5, stat.boomerang_count // 3),
                        description=f"Bike returned to same station {stat.boomerang_count} times in 24h"
                    )
                    db.session.add(malfunction)
                    bike.potential_malfunction = True
                    
                    logger.info(f"Flagged bike {bike.bike_name} for excessive boomerangs: {stat.boomerang_count}")
        
        db.session.commit()
    
    def detect_low_speed_bikes(self):
        """Detect bikes with consistently low speeds"""
        recent_cutoff = datetime.utcnow() - timedelta(days=3)
        
        # Get average speeds for bikes
        speed_stats = db.session.query(
            Trip.bike_id,
            func.avg(Trip.avg_speed).label('avg_speed'),
            func.count(Trip.id).label('trip_count')
        ).filter(
            Trip.start_time >= recent_cutoff,
            Trip.avg_speed.isnot(None),
            Trip.duration > 300  # At least 5 minute trips
        ).group_by(Trip.bike_id).having(
            func.count(Trip.id) >= 3  # At least 3 trips
        ).all()
        
        for stat in speed_stats:
            bike = Bike.query.get(stat.bike_id)
            if bike and bike.bike_electric and stat.avg_speed < self.low_speed_threshold:
                existing = MalfunctionLog.query.filter_by(
                    bike_id=bike.id,
                    malfunction_type='low_speed',
                    is_active=True
                ).first()
                
                if not existing:
                    malfunction = MalfunctionLog(
                        bike_id=bike.id,
                        malfunction_type='low_speed',
                        severity=3,
                        description=f"Electric bike averaging only {stat.avg_speed:.1f} km/h over {stat.trip_count} trips"
                    )
                    db.session.add(malfunction)
                    bike.potential_malfunction = True
                    
                    logger.info(f"Flagged electric bike {bike.bike_name} for low speed: {stat.avg_speed:.1f} km/h")
        
        db.session.commit()
    
    def detect_missing_bikes(self):
        """Detect bikes that haven't been seen for extended periods"""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.missing_hours_threshold)
        
        missing_bikes = Bike.query.filter(
            Bike.last_seen_at < cutoff_time,
            Bike.current_status != 'missing'
        ).all()
        
        for bike in missing_bikes:
            bike.current_status = 'missing'
            
            existing = MalfunctionLog.query.filter_by(
                bike_id=bike.id,
                malfunction_type='missing',
                is_active=True
            ).first()
            
            if not existing:
                hours_missing = (datetime.utcnow() - bike.last_seen_at).total_seconds() / 3600
                malfunction = MalfunctionLog(
                    bike_id=bike.id,
                    malfunction_type='missing',
                    severity=4,
                    description=f"Bike not seen for {hours_missing:.1f} hours"
                )
                db.session.add(malfunction)
                
                logger.info(f"Marked bike {bike.bike_name} as missing")
        
        db.session.commit()
    
    def detect_stuck_bikes(self):
        """Detect bikes that haven't moved from a station"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.stuck_days_threshold)
        
        # Only check bikes that have been tracked for at least the threshold period
        bike_creation_cutoff = datetime.utcnow() - timedelta(days=self.stuck_days_threshold + 1)
        
        # Find bikes with no trips in the last week
        bikes_with_recent_trips = db.session.query(Trip.bike_id).filter(
            Trip.start_time >= cutoff_date
        ).distinct().subquery()
        
        stuck_bikes = Bike.query.filter(
            Bike.current_station_id.isnot(None),
            Bike.id.notin_(bikes_with_recent_trips),
            Bike.last_seen_at >= cutoff_date,  # Still being seen at station
            Bike.created_at <= bike_creation_cutoff  # Only bikes we've been tracking long enough
        ).all()
        
        for bike in stuck_bikes:
            existing = MalfunctionLog.query.filter_by(
                bike_id=bike.id,
                malfunction_type='stuck',
                is_active=True
            ).first()
            
            if not existing:
                # Calculate actual days since last movement
                days_stuck = (datetime.utcnow() - bike.last_seen_at).days
                
                malfunction = MalfunctionLog(
                    bike_id=bike.id,
                    malfunction_type='stuck',
                    severity=2,
                    description=f"Bike hasn't moved from station in {days_stuck} days",
                    station_id=bike.current_station_id
                )
                db.session.add(malfunction)
                bike.potential_malfunction = True
                
                logger.info(f"Flagged bike {bike.bike_name} as stuck at station")
        
        db.session.commit()
    
    def detect_battery_issues(self):
        """Detect electric bikes with potential battery issues"""
        recent_cutoff = datetime.utcnow() - timedelta(hours=12)
        
        # Find electric bikes that were docked for charging but had issues after
        problem_bikes = db.session.query(
            Trip.bike_id,
            Trip.id.label('trip_id'),
            Trip.duration,
            Trip.avg_speed
        ).join(
            Bike, Trip.bike_id == Bike.id
        ).filter(
            Bike.bike_electric == True,
            Trip.start_time >= recent_cutoff,
            db.or_(
                Trip.is_boomerang == True,
                Trip.duration < 600,  # Less than 10 minutes
                Trip.avg_speed < 5.0  # Very low speed
            )
        ).all()
        
        for result in problem_bikes:
            # Check if bike was docked for at least 3 hours before this trip
            bike = Bike.query.get(result.bike_id)
            
            # Get previous docking duration
            prev_trip = Trip.query.filter(
                Trip.bike_id == result.bike_id,
                Trip.end_time < Trip.query.get(result.trip_id).start_time
            ).order_by(Trip.end_time.desc()).first()
            
            if prev_trip:
                docking_duration = (Trip.query.get(result.trip_id).start_time - prev_trip.end_time).total_seconds() / 3600
                
                if docking_duration >= 3:  # Was docked for at least 3 hours
                    existing = MalfunctionLog.query.filter_by(
                        bike_id=bike.id,
                        malfunction_type='battery_issue',
                        is_active=True
                    ).first()
                    
                    if not existing:
                        malfunction = MalfunctionLog(
                            bike_id=bike.id,
                            malfunction_type='battery_issue',
                            severity=3,
                            description=f"Electric bike had issues after {docking_duration:.1f}h charging",
                            related_trip_id=result.trip_id
                        )
                        db.session.add(malfunction)
                        bike.potential_malfunction = True
                        
                        logger.info(f"Flagged electric bike {bike.bike_name} for potential battery issues")
        
        db.session.commit()
    
    def update_malfunction_scores(self):
        """Update overall malfunction scores for bikes"""
        bikes = Bike.query.all()
        
        for bike in bikes:
            active_malfunctions = MalfunctionLog.query.filter_by(
                bike_id=bike.id,
                is_active=True
            ).all()
            
            if active_malfunctions:
                # Calculate weighted score
                total_score = sum(m.severity for m in active_malfunctions)
                bike.malfunction_score = min(10.0, total_score * 2.0)
                bike.potential_malfunction = True
            else:
                bike.malfunction_score = 0.0
                bike.potential_malfunction = False
        
        db.session.commit()
    
    def resolve_recovered_bikes(self):
        """Mark malfunctions as resolved for bikes that appear to be working again"""
        # Find bikes with successful recent trips
        recent_cutoff = datetime.utcnow() - timedelta(hours=6)
        
        healthy_trips = db.session.query(
            Trip.bike_id
        ).filter(
            Trip.start_time >= recent_cutoff,
            Trip.duration > 600,  # At least 10 minutes
            Trip.avg_speed > 10.0,  # Reasonable speed
            Trip.is_boomerang == False
        ).distinct().all()
        
        for (bike_id,) in healthy_trips:
            # Resolve active malfunctions
            active_malfunctions = MalfunctionLog.query.filter_by(
                bike_id=bike_id,
                is_active=True
            ).all()
            
            for malfunction in active_malfunctions:
                if malfunction.malfunction_type in ['boomerang', 'low_speed', 'battery_issue']:
                    malfunction.is_active = False
                    malfunction.resolved_at = datetime.utcnow()
                    logger.info(f"Resolved {malfunction.malfunction_type} for bike {bike_id}")
        
        db.session.commit()