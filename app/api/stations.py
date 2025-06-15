from flask import jsonify, request
from app.api import api_bp
from app.models import Station, Bike, BikeSnapshot, Trip
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func


@api_bp.route('/stations', methods=['GET'])
def get_stations():
    """Get all stations with current status"""
    stations = Station.query.all()
    return jsonify({
        'stations': [station.to_dict() for station in stations],
        'total': len(stations)
    })


@api_bp.route('/stations/<station_code>', methods=['GET'])
def get_station(station_code):
    """Get detailed information about a specific station"""
    station = Station.query.filter_by(code=station_code).first()
    if not station:
        return jsonify({'error': 'Station not found'}), 404
    
    # Get bikes currently at station
    current_bikes = Bike.query.filter_by(current_station_id=station.id).all()
    
    # Get station activity stats
    last_24h = datetime.utcnow() - timedelta(hours=24)
    departures = station.trip_starts.filter(Trip.start_time >= last_24h).count()
    arrivals = station.trip_ends.filter(Trip.end_time >= last_24h).count()
    
    response = station.to_dict()
    response.update({
        'current_bikes': [bike.to_dict() for bike in current_bikes],
        'activity_24h': {
            'departures': departures,
            'arrivals': arrivals,
            'turnover_rate': (departures + arrivals) / (station.total_capacity or 1)
        }
    })
    
    return jsonify(response)


@api_bp.route('/stations/<station_code>/history', methods=['GET'])
def get_station_history(station_code):
    """Get historical availability for a station"""
    station = Station.query.filter_by(code=station_code).first()
    if not station:
        return jsonify({'error': 'Station not found'}), 404
    
    # Get time range from query params
    hours = request.args.get('hours', 24, type=int)
    interval = request.args.get('interval', 60, type=int)  # minutes
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    # Get bike counts over time
    snapshots = db.session.query(
        func.date_trunc('hour', BikeSnapshot.timestamp).label('hour'),
        func.count(func.distinct(BikeSnapshot.bike_id)).label('bike_count')
    ).filter(
        BikeSnapshot.station_id == station.id,
        BikeSnapshot.timestamp >= cutoff
    ).group_by('hour').order_by('hour').all()
    
    history = []
    for snapshot in snapshots:
        history.append({
            'timestamp': snapshot.hour.isoformat(),
            'bike_count': snapshot.bike_count,
            'free_docks': station.total_capacity - snapshot.bike_count
        })
    
    return jsonify({
        'station_code': station_code,
        'history': history,
        'hours': hours
    })


@api_bp.route('/stations/search', methods=['GET'])
def search_stations():
    """Search stations by name or location"""
    query = request.args.get('q', '')
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    radius = request.args.get('radius', 1.0, type=float)  # km
    
    stations_query = Station.query
    
    if query:
        stations_query = stations_query.filter(
            Station.name.ilike(f'%{query}%')
        )
    
    if lat and lon:
        # Simple distance calculation (not perfect but fast)
        # For production, use PostGIS or similar
        stations = stations_query.all()
        nearby_stations = []
        
        for station in stations:
            # Approximate distance calculation
            dlat = abs(station.latitude - lat) * 111  # km per degree
            dlon = abs(station.longitude - lon) * 111 * 0.7  # rough approximation
            distance = (dlat**2 + dlon**2)**0.5
            
            if distance <= radius:
                station_dict = station.to_dict()
                station_dict['distance'] = round(distance, 2)
                nearby_stations.append(station_dict)
        
        nearby_stations.sort(key=lambda x: x['distance'])
        return jsonify({'stations': nearby_stations})
    
    stations = stations_query.limit(50).all()
    return jsonify({'stations': [s.to_dict() for s in stations]})