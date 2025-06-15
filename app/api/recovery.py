from flask import jsonify, request, current_app, abort
from app.api import api_bp
from app.utils.data_recovery import DataRecovery
from app import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def check_dev_mode():
    """Check if we're in development mode, abort if not"""
    if not current_app.config.get('DEBUG') and current_app.config.get('ENV') != 'development':
        abort(404)  # Return 404 to hide existence in production


@api_bp.route('/recovery/status', methods=['GET'])
def get_recovery_status():
    """Get current data health status"""
    check_dev_mode()
    try:
        recovery = DataRecovery()
        report = recovery.get_recovery_report()
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error getting recovery status: {e}")
        return jsonify({'error': 'Failed to get recovery status'}), 500


@api_bp.route('/recovery/run', methods=['POST'])
def run_manual_recovery():
    """Manually trigger data recovery"""
    check_dev_mode()
    try:
        action = request.json.get('action', 'full') if request.json else 'full'
        
        recovery = DataRecovery()
        
        if action == 'full':
            recovery.run_full_recovery()
            message = "Full data recovery completed"
        elif action == 'cleanup_trips':
            recovery.cleanup_incomplete_trips()
            db.session.commit()
            message = "Trip cleanup completed"
        elif action == 'fix_transit':
            recovery.fix_stuck_in_transit_bikes()
            db.session.commit()
            message = "Fixed bikes stuck in transit"
        elif action == 'reset_status':
            recovery.reset_bike_status_from_snapshots()
            message = "Reset bike statuses from snapshots"
        elif action == 'cleanup_duplicates':
            recovery.cleanup_duplicate_trips()
            message = "Removed duplicate trips"
        elif action == 'cleanup_old':
            recovery.cleanup_old_station_states()
            recovery.cleanup_old_snapshots()
            db.session.commit()
            message = "Cleaned up old data"
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        logger.info(f"Manual recovery action '{action}' completed")
        
        # Get updated status
        report = recovery.get_recovery_report()
        
        return jsonify({
            'success': True,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'status': report
        })
        
    except Exception as e:
        logger.error(f"Error in manual recovery: {e}")
        return jsonify({'error': f'Recovery failed: {str(e)}'}), 500


@api_bp.route('/recovery/actions', methods=['GET'])
def get_available_actions():
    """Get list of available recovery actions"""
    check_dev_mode()
    actions = {
        'full': {
            'name': 'Full Recovery',
            'description': 'Run all recovery procedures',
            'risk': 'low'
        },
        'cleanup_trips': {
            'name': 'Clean Incomplete Trips',
            'description': 'Remove trips that are impossible or incomplete',
            'risk': 'low'
        },
        'fix_transit': {
            'name': 'Fix Stuck Bikes',
            'description': 'Fix bikes stuck in transit status',
            'risk': 'low'
        },
        'reset_status': {
            'name': 'Reset Bike Statuses',
            'description': 'Reset all bike statuses from latest snapshots',
            'risk': 'medium'
        },
        'cleanup_duplicates': {
            'name': 'Remove Duplicates',
            'description': 'Remove duplicate trip entries',
            'risk': 'medium'
        },
        'cleanup_old': {
            'name': 'Clean Old Data',
            'description': 'Remove old snapshots and station states',
            'risk': 'low'
        }
    }
    
    return jsonify({
        'actions': actions,
        'recommendation': 'Start with "full" recovery for comprehensive cleanup'
    })