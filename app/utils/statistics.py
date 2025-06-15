from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from sqlalchemy import func, desc
from app import db
from app.models import Bike, Trip, Station, MalfunctionLog
import logging

logger = logging.getLogger(__name__)


class StatisticsCalculator:
    """Calculate various statistics for the Velib system"""
    
    def __init__(self):
        pass
    
    def get_system_overview(self) -> Dict:
        """Get overall system statistics"""
        total_bikes = Bike.query.count()
        total_stations = Station.query.count()
        
        # Status breakdown
        status_counts = db.session.query(
            Bike.current_status,
            func.count(Bike.id)
        ).group_by(Bike.current_status).all()
        
        # Active malfunctions
        active_malfunctions = MalfunctionLog.query.filter_by(is_active=True).count()
        
        # Today's activity
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_trips = Trip.query.filter(Trip.start_time >= today_start).count()
        
        # Last hour activity
        last_hour = datetime.utcnow() - timedelta(hours=1)
        last_hour_trips = Trip.query.filter(Trip.start_time >= last_hour).count()
        
        return {
            'total_bikes': total_bikes,
            'total_stations': total_stations,
            'bike_status_breakdown': dict(status_counts),
            'active_malfunctions': active_malfunctions,
            'trips_today': today_trips,
            'trips_last_hour': last_hour_trips,
            'timestamp': datetime.utcnow()
        }
    
    def calculate_bike_statistics(self, bike_id: int, days: int = 7) -> Dict:
        """Calculate statistics for a specific bike"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        stats = db.session.query(
            func.count(Trip.id).label('trip_count'),
            func.sum(Trip.distance).label('total_distance'),
            func.sum(Trip.duration).label('total_duration'),
            func.avg(Trip.avg_speed).label('avg_speed'),
            func.count(func.case([(Trip.is_boomerang == True, 1)])).label('boomerang_count')
        ).filter(
            Trip.bike_id == bike_id,
            Trip.start_time >= cutoff
        ).first()
        
        return {
            'period_days': days,
            'trip_count': stats.trip_count or 0,
            'total_distance': round(stats.total_distance or 0, 2),
            'total_duration': stats.total_duration or 0,
            'avg_speed': round(stats.avg_speed or 0, 2),
            'boomerang_count': stats.boomerang_count or 0
        }
    
    def calculate_station_statistics(self, station_id: int, hours: int = 24) -> Dict:
        """Calculate statistics for a specific station"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Departure and arrival counts
        departures = Trip.query.filter(
            Trip.start_station_id == station_id,
            Trip.start_time >= cutoff
        ).count()
        
        arrivals = Trip.query.filter(
            Trip.end_station_id == station_id,
            Trip.end_time >= cutoff
        ).count()
        
        # Average dwell time (time bikes spend at station)
        # This would require more complex logic with snapshots
        
        return {
            'period_hours': hours,
            'departures': departures,
            'arrivals': arrivals,
            'total_activity': departures + arrivals,
            'turnover_rate': (departures + arrivals) / hours
        }
    
    def get_popular_routes(self, hours: int = 24, limit: int = 20) -> List[Dict]:
        """Get most popular routes in the system"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        routes = db.session.query(
            Trip.start_station_id,
            Trip.end_station_id,
            func.count(Trip.id).label('trip_count'),
            func.avg(Trip.duration).label('avg_duration'),
            func.avg(Trip.distance).label('avg_distance'),
            func.avg(Trip.avg_speed).label('avg_speed')
        ).filter(
            Trip.start_time >= cutoff,
            Trip.start_station_id != Trip.end_station_id
        ).group_by(
            Trip.start_station_id,
            Trip.end_station_id
        ).order_by(
            desc('trip_count')
        ).limit(limit).all()
        
        result = []
        for route in routes:
            start_station = Station.query.get(route.start_station_id)
            end_station = Station.query.get(route.end_station_id)
            
            if start_station and end_station:
                result.append({
                    'start_station': {
                        'id': start_station.id,
                        'code': start_station.code,
                        'name': start_station.name
                    },
                    'end_station': {
                        'id': end_station.id,
                        'code': end_station.code,
                        'name': end_station.name
                    },
                    'trip_count': route.trip_count,
                    'avg_duration': round(route.avg_duration or 0),
                    'avg_distance': round(route.avg_distance or 0, 2),
                    'avg_speed': round(route.avg_speed or 0, 2)
                })
        
        return result
    
    def get_hourly_patterns(self, days: int = 7) -> List[Dict]:
        """Get usage patterns by hour of day"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        patterns = db.session.query(
            func.extract('hour', Trip.start_time).label('hour'),
            func.count(Trip.id).label('trip_count'),
            func.avg(Trip.duration).label('avg_duration'),
            func.avg(Trip.distance).label('avg_distance')
        ).filter(
            Trip.start_time >= cutoff
        ).group_by('hour').order_by('hour').all()
        
        return [
            {
                'hour': int(p.hour),
                'trip_count': p.trip_count,
                'avg_duration': round(p.avg_duration or 0),
                'avg_distance': round(p.avg_distance or 0, 2)
            }
            for p in patterns
        ]
    
    def get_system_health_score(self) -> Dict:
        """Calculate overall system health metrics"""
        total_bikes = Bike.query.count()
        
        if total_bikes == 0:
            return {
                'health_score': 0,
                'availability_rate': 0,
                'malfunction_rate': 0,
                'missing_rate': 0
            }
        
        # Count bikes by status
        available_bikes = Bike.query.filter_by(current_status='disponible').count()
        malfunctioning_bikes = Bike.query.filter_by(potential_malfunction=True).count()
        missing_bikes = Bike.query.filter_by(current_status='missing').count()
        
        # Calculate rates
        availability_rate = (available_bikes / total_bikes) * 100
        malfunction_rate = (malfunctioning_bikes / total_bikes) * 100
        missing_rate = (missing_bikes / total_bikes) * 100
        
        # Health score (simple formula - can be made more sophisticated)
        health_score = max(0, 100 - malfunction_rate * 2 - missing_rate * 3)
        
        return {
            'health_score': round(health_score, 2),
            'availability_rate': round(availability_rate, 2),
            'malfunction_rate': round(malfunction_rate, 2),
            'missing_rate': round(missing_rate, 2),
            'total_bikes': total_bikes,
            'available_bikes': available_bikes,
            'malfunctioning_bikes': malfunctioning_bikes,
            'missing_bikes': missing_bikes
        }