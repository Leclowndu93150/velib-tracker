from flask import render_template, redirect, url_for, current_app, abort

def register_routes(app):
    """Register all routes with the Flask app"""
    
    @app.route('/')
    def index():
        """Main map view"""
        return render_template('index.html')

    @app.route('/bikes')
    def bikes():
        """Bikes list view"""
        return render_template('bikes.html')

    @app.route('/bikes/<bike_name>')
    def bike_detail(bike_name):
        """Individual bike detail view"""
        return render_template('bike_detail.html', bike_name=bike_name)

    @app.route('/stations')
    def stations():
        """Stations list view"""
        return render_template('stations.html')

    @app.route('/stations/<station_code>')
    def station_detail(station_code):
        """Individual station detail view"""
        return render_template('station_detail.html', station_code=station_code)

    @app.route('/statistics')
    def statistics():
        """Statistics dashboard"""
        return render_template('statistics.html')

    @app.route('/awards')
    def awards():
        """Velib Awards page"""
        return render_template('awards.html')
    
    @app.route('/trips')
    def trips():
        """All trips view"""
        return render_template('trips.html')
    
    @app.route('/recovery')
    def recovery():
        """Data recovery page (development only)"""
        # Only allow access in development mode
        if not app.config.get('DEBUG') and app.config.get('ENV') != 'development':
            abort(404)  # Return 404 instead of 403 to hide existence
        return render_template('recovery.html')