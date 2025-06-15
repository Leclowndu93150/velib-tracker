from flask import jsonify, request
from app.api import api_bp
from app.models import Trip, Bike, Station
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, desc


@api_bp.route('/trips', methods=['GET'])
def get_trips():
    """Get trips with filters"""
    # Filters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    min_duration = request.args.get('min_duration', type=int)  # seconds
    max_duration = request.args.get('max_duration', type=int)
    boomerang_only = request.args.get('boomerang_only', type=lambda x: x.lower() == 'true')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    query = Trip.query
    
    if start_date:
        query = query.filter(Trip.start_time >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Trip.end_time <= datetime.fromisoformat(end_date))
    if min_duration:
        query = query.filter(Trip.duration >= min_duration)
    if max_duration:
        query = query.filter(Trip.duration <= max_duration)
    if boomerang_only:
        query = query.filter_by(is_boomerang=True)
    
    query = query.order_by(desc(Trip.start_time))
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    trips = []
    for trip in paginated.items:
        trip_dict = trip.to_dict()
        # Add bike and station info
        trip_dict['bike_name'] = trip.bike.bike_name if trip.bike else None
        trip_dict['start_station_name'] = trip.start_station.name if trip.start_station else None
        trip_dict['end_station_name'] = trip.end_station.name if trip.end_station else None
        trips.append(trip_dict)
    
    return jsonify({
        'trips': trips,
        'total': paginated.total,
        'page': page,
        'pages': paginated.pages,
        'per_page': per_page
    })


@api_bp.route('/trips/<int:trip_id>', methods=['GET'])
def get_trip(trip_id):
    """Get detailed information about a specific trip"""
    trip = Trip.query.get(trip_id)
    if not trip:
        return jsonify({'error': 'Trip not found'}), 404
    
    response = trip.to_dict()
    
    # Add detailed information
    response.update({
        'bike': trip.bike.to_dict() if trip.bike else None,
        'start_station': trip.start_station.to_dict() if trip.start_station else None,
        'end_station': trip.end_station.to_dict() if trip.end_station else None
    })
    
    # Add path coordinates for visualization
    if trip.start_station and trip.end_station:
        response['path'] = {
            'start': {
                'lat': trip.start_station.latitude,
                'lon': trip.start_station.longitude
            },
            'end': {
                'lat': trip.end_station.latitude,
                'lon': trip.end_station.longitude
            }
        }
    
    return jsonify(response)


@api_bp.route('/trips/live', methods=['GET'])
def get_live_trips():
    """Get bikes currently in transit"""
    in_transit_bikes = Bike.query.filter_by(current_status='in_transit').all()
    
    live_trips = []
    for bike in in_transit_bikes:
        # Get last trip start
        last_trip = Trip.query.filter_by(bike_id=bike.id)\
                             .order_by(desc(Trip.start_time))\
                             .first()
        
        if last_trip and not last_trip.end_time:
            trip_info = {
                'bike_name': bike.bike_name,
                'bike_electric': bike.bike_electric,
                'start_station': {
                    'code': last_trip.start_station.code,
                    'name': last_trip.start_station.name,
                    'lat': last_trip.start_station.latitude,
                    'lon': last_trip.start_station.longitude
                } if last_trip.start_station else None,
                'start_time': last_trip.start_time.isoformat(),
                'duration_so_far': int((datetime.utcnow() - last_trip.start_time).total_seconds())
            }
            live_trips.append(trip_info)
    
    return jsonify({
        'live_trips': live_trips,
        'total': len(live_trips)
    })


@api_bp.route('/trips/popular-routes', methods=['GET'])
def get_popular_routes():
    """Get most popular routes"""
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    popular_routes = db.session.query(
        Trip.start_station_id,
        Trip.end_station_id,
        func.count(Trip.id).label('trip_count'),
        func.avg(Trip.duration).label('avg_duration'),
        func.avg(Trip.distance).label('avg_distance')
    ).filter(
        Trip.start_time >= cutoff,
        Trip.start_station_id != Trip.end_station_id  # Exclude boomerangs
    ).group_by(
        Trip.start_station_id,
        Trip.end_station_id
    ).order_by(
        desc('trip_count')
    ).limit(limit).all()
    
    routes = []
    for route in popular_routes:
        start_station = Station.query.get(route.start_station_id)
        end_station = Station.query.get(route.end_station_id)
        
        if start_station and end_station:
            routes.append({
                'start_station': {
                    'code': start_station.code,
                    'name': start_station.name,
                    'lat': start_station.latitude,
                    'lon': start_station.longitude
                },
                'end_station': {
                    'code': end_station.code,
                    'name': end_station.name,
                    'lat': end_station.latitude,
                    'lon': end_station.longitude
                },
                'trip_count': route.trip_count,
                'avg_duration': round(route.avg_duration or 0),
                'avg_distance': round(route.avg_distance or 0, 2)
            })
    
    return jsonify({
        'routes': routes,
        'hours': hours,
        'total': len(routes)
    })