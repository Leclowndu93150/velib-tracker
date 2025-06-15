import threading
import queue
import logging
from typing import Callable, Any
from functools import wraps
import time

logger = logging.getLogger(__name__)


class DatabaseQueue:
    """Simple in-memory queue for serializing database operations"""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        self.app_context = None
        
    def start_worker(self, app):
        """Start the database worker thread"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
            
        self.app_context = app
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        logger.info("Database queue worker started")
        
    def stop_worker(self):
        """Stop the database worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Database queue worker stopped")
        
    def _worker(self):
        """Main worker loop - processes queued database tasks"""
        while self.running:
            try:
                # Get task with timeout to allow periodic checks
                task = self.task_queue.get(timeout=1)
                
                if task is None:  # Poison pill to stop worker
                    break
                    
                func, args, kwargs, result_callback, error_callback = task
                
                # Execute task within app context
                with self.app_context.app_context():
                    try:
                        result = func(*args, **kwargs)
                        if result_callback:
                            result_callback(result)
                    except Exception as e:
                        logger.error(f"Database task failed: {e}")
                        if error_callback:
                            error_callback(e)
                        
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker thread error: {e}")
                
    def enqueue_task(self, func: Callable, *args, 
                    result_callback: Callable = None,
                    error_callback: Callable = None,
                    **kwargs) -> bool:
        """
        Enqueue a database task to be executed by the worker thread
        
        Args:
            func: Function to execute
            *args: Function arguments
            result_callback: Called with result if task succeeds
            error_callback: Called with exception if task fails
            **kwargs: Function keyword arguments
            
        Returns:
            True if task was enqueued successfully
        """
        if not self.running:
            logger.warning("Cannot enqueue task - worker not running")
            return False
            
        try:
            task = (func, args, kwargs, result_callback, error_callback)
            self.task_queue.put(task, timeout=5)
            return True
        except queue.Full:
            logger.error("Task queue is full - dropping task")
            return False
        except Exception as e:
            logger.error(f"Failed to enqueue task: {e}")
            return False


# Global queue instance
db_queue = DatabaseQueue()


def queued_db_operation(func):
    """
    Decorator to automatically queue database operations
    
    Usage:
        @queued_db_operation
        def my_db_function():
            # database operations here
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if db_queue.running:
            # Extract callbacks if provided
            result_callback = kwargs.pop('_result_callback', None)
            error_callback = kwargs.pop('_error_callback', None)
            
            return db_queue.enqueue_task(
                func, *args, 
                result_callback=result_callback,
                error_callback=error_callback,
                **kwargs
            )
        else:
            # Fallback to direct execution if queue not running
            logger.warning(f"Queue not running, executing {func.__name__} directly")
            return func(*args, **kwargs)
    
    return wrapper


def start_queue_worker(app):
    """Start the global database queue worker"""
    db_queue.start_worker(app)


def stop_queue_worker():
    """Stop the global database queue worker"""
    db_queue.stop_worker()


def get_queue_status():
    """Get current queue status for monitoring"""
    return {
        'running': db_queue.running,
        'queue_size': db_queue.task_queue.qsize(),
        'worker_alive': db_queue.worker_thread.is_alive() if db_queue.worker_thread else False
    }