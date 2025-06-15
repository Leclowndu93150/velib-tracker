#!/usr/bin/env python3
import os
import logging
import atexit
from app import create_app
from app.scheduler import start_scheduler, shutdown_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create Flask app
app = create_app()

# Start background scheduler
start_scheduler(app)

# Register cleanup
atexit.register(shutdown_scheduler)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )