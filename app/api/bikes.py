from flask import jsonify, request
from app.api import api_bp
from app.models import Bike, Trip, MalfunctionLog, BikeSnapshot, Station
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc


@api_bp.route('/bikes', methods=['GET'])
def get_bikes():
    """Get bikes with filters"""
    # Filters
    status = request.args.get('status')  # disponible, indisponible, in_transit, missing
    electric = request.args.get('electric', type=lambda x: x.lower() == 'true')
    malfunction = request.args.get('malfunction', type=lambda x: x.lower() == 'true')
    station_code = request.args.get('station_code')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    
    query = Bike.query
    
    if status:
        query = query.filter_by(current_status=status)
    if electric is not None:
        query = query.filter_by(bike_electric=electric)
    if malfunction is not None:
        query = query.filter_by(potential_malfunction=malfunction)
    if station_code:
        station = Station.query.filter_by(code=station_code).first()
        if station:
            query = query.filter_by(current_station_id=station.id)
    
    # Order by malfunction score desc, then by last seen
    query = query.order_by(desc(Bike.malfunction_score), desc(Bike.last_seen_at))
    
    # Paginate
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'bikes': [bike.to_dict() for bike in paginated.items],
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
        'per_page': per_page
    })


@api_bp.route('/bikes/<bike_name>', methods=['GET'])
def get_bike(bike_name):
    """Get detailed information about a specific bike"""
    bike = Bike.query.filter_by(bike_name=bike_name).first()
    if not bike:
        return jsonify({'error': 'Bike not found'}), 404
    
    # Get recent trips
    recent_trips = Trip.query.filter_by(bike_id=bike.id)\
                            .order_by(desc(Trip.start_time))\
                            .limit(20).all()
    
    # Get active malfunctions
    active_malfunctions = MalfunctionLog.query.filter_by(
        bike_id=bike.id,
        is_active=True
    ).all()
    
    # Calculate statistics
    last_7_days = datetime.utcnow() - timedelta(days=7)
    week_stats = db.session.query(
        func.count(Trip.id).label('trip_count'),
        func.sum(Trip.distance).label('total_distance'),
        func.sum(Trip.duration).label('total_duration'),
        func.avg(Trip.avg_speed).label('avg_speed')
    ).filter(
        Trip.bike_id == bike.id,
        Trip.start_time >= last_7_days
    ).first()
    
    response = bike.to_dict()
    response.update({
        'recent_trips': [trip.to_dict() for trip in recent_trips],
        'active_malfunctions': [m.to_dict() for m in active_malfunctions],
        'week_statistics': {
            'trip_count': week_stats.trip_count or 0,
            'total_distance': round(week_stats.total_distance or 0, 2),
            'total_duration': week_stats.total_duration or 0,
            'avg_speed': round(week_stats.avg_speed or 0, 2)
        }
    })
    
    # Add current station info if docked
    if bike.current_station:
        response['current_station'] = {
            'code': bike.current_station.code,
            'name': bike.current_station.name,
            'latitude': bike.current_station.latitude,
            'longitude': bike.current_station.longitude
        }
    
    return jsonify(response)


@api_bp.route('/bikes/<bike_name>/trips', methods=['GET'])
def get_bike_trips(bike_name):
    """Get trip history for a bike"""
    bike = Bike.query.filter_by(bike_name=bike_name).first()
    if not bike:
        return jsonify({'error': 'Bike not found'}), 404
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Date filters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Trip.query.filter_by(bike_id=bike.id)
    
    if start_date:
        query = query.filter(Trip.start_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Trip.start_time <= datetime.fromisoformat(end_date))
    
    query = query.order_by(desc(Trip.start_time))
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    trips = []
    for trip in paginated.items:
        trip_dict = trip.to_dict()
        # Add station names
        trip_dict['start_station_name'] = trip.start_station.name if trip.start_station else None
        trip_dict['end_station_name'] = trip.end_station.name if trip.end_station else None
        trips.append(trip_dict)
    
    return jsonify({
        'bike_name': bike_name,
        'trips': trips,
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
        'per_page': per_page
    })


@api_bp.route('/bikes/<bike_name>/malfunctions', methods=['GET'])
def get_bike_malfunctions(bike_name):
    """Get malfunction history for a bike"""
    bike = Bike.query.filter_by(bike_name=bike_name).first()
    if not bike:
        return jsonify({'error': 'Bike not found'}), 404
    
    malfunctions = MalfunctionLog.query.filter_by(bike_id=bike.id)\
                                      .order_by(desc(MalfunctionLog.detected_at))\
                                      .all()
    
    return jsonify({
        'bike_name': bike_name,
        'malfunctions': [m.to_dict() for m in malfunctions],
        'total': len(malfunctions)
    })


@api_bp.route('/bikes/malfunctioning', methods=['GET'])
def get_malfunctioning_bikes():
    """Get bikes with active malfunctions"""
    malfunction_type = request.args.get('type')
    min_severity = request.args.get('min_severity', 1, type=int)
    
    query = db.session.query(Bike).join(MalfunctionLog).filter(
        MalfunctionLog.is_active == True,
        MalfunctionLog.severity >= min_severity
    )
    
    if malfunction_type:
        query = query.filter(MalfunctionLog.malfunction_type == malfunction_type)
    
    bikes = query.distinct().all()
    
    results = []
    for bike in bikes:
        bike_dict = bike.to_dict()
        # Add active malfunctions
        active_malfunctions = MalfunctionLog.query.filter_by(
            bike_id=bike.id,
            is_active=True
        ).all()
        bike_dict['malfunctions'] = [m.to_dict() for m in active_malfunctions]
        results.append(bike_dict)
    
    # Sort by malfunction score
    results.sort(key=lambda x: x['malfunction_score'], reverse=True)
    
    return jsonify({
        'bikes': results,
        'total': len(results)
    })