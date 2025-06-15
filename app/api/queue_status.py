from flask import Blueprint, jsonify
from app.queue_manager import get_queue_status

queue_bp = Blueprint('queue', __name__)

@queue_bp.route('/queue/status')
def queue_status():
    """Get current queue status for monitoring"""
    status = get_queue_status()
    return jsonify(status)