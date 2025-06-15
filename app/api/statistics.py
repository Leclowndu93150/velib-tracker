from flask import jsonify, request
from app.api import api_bp
from app.models import Bike, Trip, Station, MalfunctionLog
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_


@api_bp.route('/statistics/overview', methods=['GET'])
def get_overview_statistics():
    """Get system-wide statistics"""
    # Basic counts
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
    
    return jsonify({
        'total_bikes': total_bikes,
        'total_stations': total_stations,
        'bike_status': dict(status_counts),
        'active_malfunctions': active_malfunctions,
        'trips_today': today_trips,
        'trips_last_hour': last_hour_trips,
        'timestamp': datetime.utcnow().isoformat()
    })


@api_bp.route('/statistics/awards', methods=['GET'])
def get_velib_awards():
    """Get Velib Awards - interesting statistics"""
    days = request.args.get('days', 7, type=int)
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Most used bike
    most_used = db.session.query(
        Bike.bike_name,
        func.count(Trip.id).label('trip_count')
    ).join(Trip).filter(
        Trip.start_time >= cutoff
    ).group_by(Bike.bike_name).order_by(
        desc('trip_count')
    ).first()
    
    # Longest trip
    longest_trip = Trip.query.filter(
        Trip.start_time >= cutoff,
        Trip.distance.isnot(None)
    ).order_by(desc(Trip.distance)).first()
    
    # Fastest average speed (excluding very short trips)
    fastest_bike = db.session.query(
        Bike.bike_name,
        func.avg(Trip.avg_speed).label('avg_speed')
    ).join(Trip).filter(
        Trip.start_time >= cutoff,
        Trip.duration > 300,  # At least 5 minutes
        Trip.avg_speed.isnot(None)
    ).group_by(Bike.bike_name).order_by(
        desc('avg_speed')
    ).first()
    
    # Most boomeranged bike
    most_boomeranged = db.session.query(
        Bike.bike_name,
        func.count(Trip.id).label('boomerang_count')
    ).join(Trip).filter(
        Trip.start_time >= cutoff,
        Trip.is_boomerang == True
    ).group_by(Bike.bike_name).order_by(
        desc('boomerang_count')
    ).first()
    
    # Busiest station
    busiest_station = db.session.query(
        Station.code,
        Station.name,
        func.count(Trip.id).label('activity_count')
    ).join(
        Trip,
        db.or_(Trip.start_station_id == Station.id, Trip.end_station_id == Station.id)
    ).filter(
        Trip.start_time >= cutoff
    ).group_by(Station.code, Station.name).order_by(
        desc('activity_count')
    ).first()
    
    awards = {
        'period_days': days,
        'most_used_bike': {
            'bike_name': most_used.bike_name if most_used else None,
            'trip_count': most_used.trip_count if most_used else 0
        } if most_used else None,
        'longest_trip': {
            'bike_name': longest_trip.bike.bike_name if longest_trip else None,
            'distance': round(longest_trip.distance, 2) if longest_trip else 0,
            'duration': longest_trip.duration if longest_trip else 0,
            'date': longest_trip.start_time.isoformat() if longest_trip else None
        } if longest_trip else None,
        'fastest_bike': {
            'bike_name': fastest_bike.bike_name if fastest_bike else None,
            'avg_speed': round(fastest_bike.avg_speed, 2) if fastest_bike else 0
        } if fastest_bike else None,
        'most_boomeranged': {
            'bike_name': most_boomeranged.bike_name if most_boomeranged else None,
            'boomerang_count': most_boomeranged.boomerang_count if most_boomeranged else 0
        } if most_boomeranged else None,
        'busiest_station': {
            'code': busiest_station.code if busiest_station else None,
            'name': busiest_station.name if busiest_station else None,
            'activity_count': busiest_station.activity_count if busiest_station else 0
        } if busiest_station else None
    }
    
    return jsonify(awards)


@api_bp.route('/statistics/hourly-activity', methods=['GET'])
def get_hourly_activity():
    """Get hourly activity patterns"""
    days = request.args.get('days', 7, type=int)
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get trips grouped by hour of day
    hourly_stats = db.session.query(
        func.extract('hour', Trip.start_time).label('hour'),
        func.count(Trip.id).label('trip_count'),
        func.avg(Trip.duration).label('avg_duration')
    ).filter(
        Trip.start_time >= cutoff
    ).group_by('hour').order_by('hour').all()
    
    activity = []
    for stat in hourly_stats:
        activity.append({
            'hour': int(stat.hour),
            'trip_count': stat.trip_count,
            'avg_duration': round(stat.avg_duration or 0)
        })
    
    return jsonify({
        'hourly_activity': activity,
        'period_days': days
    })


@api_bp.route('/statistics/malfunction-summary', methods=['GET'])
def get_malfunction_summary():
    """Get summary of current malfunctions"""
    # Count by type
    malfunction_counts = db.session.query(
        MalfunctionLog.malfunction_type,
        func.count(MalfunctionLog.id).label('count'),
        func.avg(MalfunctionLog.severity).label('avg_severity')
    ).filter(
        MalfunctionLog.is_active == True
    ).group_by(MalfunctionLog.malfunction_type).all()
    
    # Recent detections
    last_24h = datetime.utcnow() - timedelta(hours=24)
    recent_detections = MalfunctionLog.query.filter(
        MalfunctionLog.detected_at >= last_24h
    ).count()
    
    # Top affected bikes
    top_affected = db.session.query(
        Bike.bike_name,
        Bike.malfunction_score,
        func.count(MalfunctionLog.id).label('malfunction_count')
    ).join(MalfunctionLog).filter(
        MalfunctionLog.is_active == True
    ).group_by(Bike.bike_name, Bike.malfunction_score).order_by(
        desc(Bike.malfunction_score)
    ).limit(10).all()
    
    return jsonify({
        'malfunction_types': [
            {
                'type': m.malfunction_type,
                'count': m.count,
                'avg_severity': round(m.avg_severity, 2)
            } for m in malfunction_counts
        ],
        'recent_detections_24h': recent_detections,
        'top_affected_bikes': [
            {
                'bike_name': b.bike_name,
                'malfunction_score': round(b.malfunction_score, 2),
                'malfunction_count': b.malfunction_count
            } for b in top_affected
        ]
    })


@api_bp.route('/statistics/system-health', methods=['GET'])
def get_system_health():
    """Get overall system health metrics"""
    # Calculate various health indicators
    total_bikes = Bike.query.count()
    
    # Availability rate
    available_bikes = Bike.query.filter_by(current_status='disponible').count()
    availability_rate = (available_bikes / total_bikes * 100) if total_bikes > 0 else 0
    
    # Malfunction rate
    malfunctioning_bikes = Bike.query.filter_by(potential_malfunction=True).count()
    malfunction_rate = (malfunctioning_bikes / total_bikes * 100) if total_bikes > 0 else 0
    
    # Missing rate
    missing_bikes = Bike.query.filter_by(current_status='missing').count()
    missing_rate = (missing_bikes / total_bikes * 100) if total_bikes > 0 else 0
    
    # Station fill rates
    from sqlalchemy import case
    
    station_stats = db.session.query(
        func.avg((Station.nb_bike + Station.nb_ebike) * 100.0 / Station.total_capacity).label('avg_fill_rate'),
        func.sum(case((Station.nb_bike + Station.nb_ebike == 0, 1), else_=0)).label('empty_stations'),
        func.sum(case((Station.nb_free_dock + Station.nb_free_edock == 0, 1), else_=0)).label('full_stations')
    ).filter(Station.total_capacity > 0).first()
    
    return jsonify({
        'availability_rate': round(availability_rate, 2),
        'malfunction_rate': round(malfunction_rate, 2),
        'missing_rate': round(missing_rate, 2),
        'station_metrics': {
            'avg_fill_rate': round(station_stats.avg_fill_rate or 0, 2),
            'empty_stations': station_stats.empty_stations or 0,
            'full_stations': station_stats.full_stations or 0
        },
        'health_score': round(100 - malfunction_rate - missing_rate, 2),
        'timestamp': datetime.utcnow().isoformat()
    })