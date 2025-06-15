# Velib Tracker

A comprehensive tracking system for Velib bicycles in Paris, providing real-time monitoring, trip analysis, and malfunction detection.

## Features

- **Real-time Tracking**: Monitor all Velib stations and bikes with minute-by-minute updates
- **Interactive Map**: Visualize station locations, bike availability, and live trips
- **Trip Reconstruction**: Automatically detect and record bike trips between stations
- **Malfunction Detection**: Identify potentially problematic bikes using multiple indicators:
  - Boomerang trips (quick returns to same station)
  - Consistently low speeds
  - Battery issues (for electric bikes)
  - Missing bikes (not seen for 24+ hours)
  - Stuck bikes (no movement for 7+ days)
- **Statistics Dashboard**: System-wide metrics and trends
- **Velib Awards**: Fun statistics like most-used bike, longest trip, busiest station
- **Efficient Storage**: Differential updates to minimize database size

## Architecture

- **Backend**: Flask (Python)
- **Database**: SQLite with optimized concurrent access
- **Queue System**: In-memory task queue for database operations
- **Frontend**: Leaflet.js for maps, Bootstrap for UI
- **Scraping**: Continuous monitoring using cloudscraper
- **Scheduling**: APScheduler for background tasks

## Setup Instructions

### Prerequisites

- Python 3.8+
- No external dependencies required (SQLite included)

### Installation

1. Clone the repository:
```bash
cd velib-tracker
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables (optional):
```bash
# Create .env file with Velib API credentials if you have them
echo "VELIB_AUTH_TOKEN=your_token_here" > .env
echo "VELIB_API_URL=https://www.velib-metropole.fr/api/secured/searchStation" >> .env
```

5. Run the application:
```bash
python run.py
```

The application will start on http://localhost:5000

## API Endpoints

### Stations
- `GET /api/stations` - List all stations
- `GET /api/stations/<code>` - Get station details
- `GET /api/stations/<code>/history` - Get station availability history
- `GET /api/stations/search` - Search stations by name or location

### Bikes
- `GET /api/bikes` - List bikes with filters
- `GET /api/bikes/<bike_name>` - Get bike details
- `GET /api/bikes/<bike_name>/trips` - Get bike trip history
- `GET /api/bikes/<bike_name>/malfunctions` - Get bike malfunction history
- `GET /api/bikes/malfunctioning` - List bikes with active malfunctions

### Trips
- `GET /api/trips` - List trips with filters
- `GET /api/trips/<id>` - Get trip details
- `GET /api/trips/live` - Get bikes currently in transit
- `GET /api/trips/popular-routes` - Get most popular routes

### Statistics
- `GET /api/statistics/overview` - System-wide statistics
- `GET /api/statistics/awards` - Velib Awards
- `GET /api/statistics/hourly-activity` - Activity patterns by hour
- `GET /api/statistics/malfunction-summary` - Malfunction statistics
- `GET /api/statistics/system-health` - Overall system health metrics

### System Monitoring
- `GET /api/queue/status` - Database queue status and health

## Data Collection Method

The system uses the same technique as shown in the video:
1. Query every Velib station every minute via the mobile app API
2. Track which bikes are present at each station
3. Detect trips by comparing bike locations between consecutive snapshots
4. Store only changes to minimize database size

## Malfunction Detection Algorithms

1. **Boomerangs**: Bikes returned to the same station within 5-10 minutes
2. **Low Speed**: Electric bikes averaging < 8 km/h over multiple trips
3. **Battery Issues**: Electric bikes showing problems after charging time
4. **Missing**: Bikes not seen at any station for 24+ hours
5. **Stuck**: Bikes at the same station for 7+ days without trips

## Performance Optimizations

- **Smart Snapshots**: Only create bike snapshots when state actually changes
- **Task Queue**: In-memory queue prevents database lock conflicts  
- **SQLite Optimization**: Connection pooling and timeout handling
- **Efficient Indexing**: Strategic database indexes for fast queries
- **Background Processing**: Async trip reconstruction and malfunction detection
- **Pagination**: All list endpoints support pagination

## Contributing

Feel free to submit issues and enhancement requests!

## Disclaimer

This is an unofficial tracker based on publicly accessible data. Malfunction indicators are estimates based on observed patterns, not official diagnoses. The system focuses on bikes, not individual users.