from apscheduler.schedulers.background import BackgroundScheduler
from app.scrapers import VelibScraper, TripReconstructor
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
def reconstruct_trips():
    """Reconstruct trips from station state changes - queued to prevent database locks"""
    try:
        reconstructor = TripReconstructor()
        reconstructor.reconstruct_trips()
        logger.info("Successfully reconstructed trips")
        return True
    except Exception as e:
        logger.error(f"Error in trip reconstruction: {e}")
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
        
        # Reconstruct trips every 5 minutes
        scheduler.add_job(
            func=reconstruct_trips,
            trigger="interval",
            minutes=5,
            id='reconstruct_trips',
            name='Reconstruct trips',
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


def shutdown_scheduler():
    """Shutdown the scheduler"""
    try:
        scheduler.shutdown()
        db_queue.stop_worker()
        logger.info("Scheduler shutdown successfully")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")