import pytz
from datetime import datetime

# Paris timezone
PARIS_TZ = pytz.timezone('Europe/Paris')

def get_paris_time():
    """Get current time in Paris timezone as naive datetime"""
    return datetime.now(PARIS_TZ).replace(tzinfo=None)

def format_paris_time(dt, format_str='%H:%M:%S'):
    """Format datetime assuming it's already in Paris timezone"""
    if dt is None:
        return None
    return dt.strftime(format_str)

def format_paris_date(dt, format_str='%d/%m/%Y'):
    """Format date assuming it's already in Paris timezone"""
    if dt is None:
        return None
    return dt.strftime(format_str)

def calculate_duration_since(dt):
    """Calculate duration since a datetime"""
    if dt is None:
        return None
    
    now = get_paris_time()
    duration = now - dt
    return duration

def format_duration(duration):
    """Format a timedelta duration in human readable format"""
    if duration is None:
        return "Unknown"
    
    total_seconds = int(duration.total_seconds())
    if total_seconds < 0:
        return "0s"
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)