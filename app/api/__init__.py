from flask import Blueprint

api_bp = Blueprint('api', __name__)

from . import stations, bikes, trips, statistics, recovery, queue_status

# Register queue status routes
from .queue_status import queue_bp
api_bp.register_blueprint(queue_bp)