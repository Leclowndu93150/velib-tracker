from apscheduler.schedulers.background import BackgroundScheduler
from app.scrapers import VelibScraper
from app.scrapers.movement_trip_detector import MovementTripDetector
from app.utils import MalfunctionDetector
from app.utils.data_recovery import DataRecovery
from app.queue_manager import db_queue, queued_db_operation
import logging
import os

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
app_instance = None


@queued_db_operation
def scrape_velib_data():
    """Scrape Velib data from API - queued to prevent database locks"""
    try:
        scraper = VelibScraper()
        success = scraper.run_update()
        if success:
            logger.info("Successfully scraped Velib data")
        else:
            logger.error("Failed to scrape Velib data")
        return success
    except Exception as e:
        logger.error(f"Error in Velib scraper: {e}")
        raise


@queued_db_operation
def detect_trips_from_movements():
    """Detect trips from precise bike movements - queued to prevent database locks"""
    try:
        detector = MovementTripDetector()
        trips_created = detector.detect_trips_from_movements()
        logger.info(f"Successfully detected {trips_created} trips from movements")
        return True
    except Exception as e:
        logger.error(f"Error in movement-based trip detection: {e}")
        raise


@queued_db_operation
def detect_malfunctions():
    """Run malfunction detection algorithms - queued to prevent database locks"""
    try:
        detector = MalfunctionDetector()
        detector.detect_all_malfunctions()
        detector.resolve_recovered_bikes()
        logger.info("Successfully ran malfunction detection")
        return True
    except Exception as e:
        logger.error(f"Error in malfunction detection: {e}")
        raise


@queued_db_operation
def run_data_recovery():
    """Run data recovery and cleanup - queued to prevent database locks"""
    try:
        recovery = DataRecovery()
        recovery.run_full_recovery()
        logger.info("Successfully ran data recovery")
        return True
    except Exception as e:
        logger.error(f"Error in data recovery: {e}")
        raise


def start_scheduler(app):
    """Start the background scheduler"""
    global app_instance
    app_instance = app
    
    # Start the database queue worker first
    db_queue.start_worker(app)
    
    with app.app_context():
        # Schedule tasks
        scrape_interval = int(os.environ.get('API_SCRAPE_INTERVAL', 60))
        
        # Scrape every minute (or configured interval)
        scheduler.add_job(
            func=scrape_velib_data,
            trigger="interval",
            seconds=scrape_interval,
            id='scrape_velib',
            name='Scrape Velib data',
            replace_existing=True
        )
        
        # Detect trips from movements every 2 minutes
        scheduler.add_job(
            func=detect_trips_from_movements,
            trigger="interval",
            minutes=2,
            id='detect_trips',
            name='Detect trips from movements',
            replace_existing=True
        )
        
        # Detect malfunctions every 15 minutes
        scheduler.add_job(
            func=detect_malfunctions,
            trigger="interval",
            minutes=15,
            id='detect_malfunctions',
            name='Detect malfunctions',
            replace_existing=True
        )
        
        # Run data recovery every 6 hours
        scheduler.add_job(
            func=run_data_recovery,
            trigger="interval",
            hours=6,
            id='data_recovery',
            name='Data recovery and cleanup',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("Scheduler started successfully")
        
        # Run initial scrape
        scrape_velib_data()
        
        # Run initial trip detection
        detect_trips_from_movements()


def shutdown_scheduler():
    """Shutdown the scheduler"""
    try:
        scheduler.shutdown()
        db_queue.stop_worker()
        logger.info("Scheduler shutdown successfully")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")