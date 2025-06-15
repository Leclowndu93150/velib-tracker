# Velib Tracker

Real-time monitoring and analysis system for Paris Velib bicycle sharing network.

## Overview

Velib Tracker continuously monitors all Velib stations and bicycles, automatically detecting trips, analyzing usage patterns, and identifying potential equipment malfunctions. The system provides a web interface with interactive maps, detailed statistics, and maintenance insights.

## Quick Start

```bash
git clone <repository-url>
cd velib-tracker
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Navigate to http://localhost:5000

## Core Features

**Live Monitoring**
- Real-time station status and bike availability
- Interactive map with live trip visualization
- Automatic trip detection and reconstruction

**Analytics & Insights**
- Usage statistics and activity patterns
- Popular routes and station rankings
- System health metrics and trends

**Malfunction Detection**
- Boomerang trips (quick same-station returns)
- Consistently slow bikes and battery issues
- Missing bikes (24+ hours) and stuck bikes (7+ days)
- Maintenance alerts and recommendations

## Architecture

- **Backend**: Flask + SQLite with optimized concurrent access
- **Frontend**: Leaflet.js maps + Bootstrap UI
- **Data Collection**: Continuous API scraping with cloudscraper
- **Processing**: In-memory task queue + APScheduler for background jobs
- **Storage**: Differential updates to minimize database size

## API Reference

### Core Data
| Endpoint | Description |
|----------|-------------|
| `GET /api/stations` | All stations with current status |
| `GET /api/stations/<code>` | Station details and history |
| `GET /api/bikes/<name>` | Bike details and trip history |
| `GET /api/trips` | Trip data with filtering |
| `GET /api/trips/live` | Bikes currently in transit |

### Analytics
| Endpoint | Description |
|----------|-------------|
| `GET /api/statistics/overview` | System-wide metrics |
| `GET /api/statistics/awards` | Usage records and achievements |
| `GET /api/bikes/malfunctioning` | Bikes flagged for maintenance |
| `GET /api/trips/popular-routes` | Most traveled routes |

### Monitoring
| Endpoint | Description |
|----------|-------------|
| `GET /api/queue/status` | Database queue health |
| `GET /api/statistics/system-health` | Overall system status |

All endpoints support pagination and filtering. See `/api/docs` for complete parameter documentation.

## Configuration

Optional environment variables:
```bash
VELIB_AUTH_TOKEN=your_api_token
VELIB_API_URL=https://www.velib-metropole.fr/api/secured/searchStation
DB_PATH=data/velib.db
LOG_LEVEL=INFO
```

## Data Collection Method

The system queries the Velib mobile app API every minute to:
1. Capture current bike locations at all stations
2. Compare with previous snapshots to detect movement
3. Reconstruct trips when bikes disappear/reappear at different stations
4. Store only state changes to minimize storage requirements

## Performance Features

- **Smart Snapshots**: Only record actual state changes
- **Queue System**: Prevents database lock conflicts
- **Strategic Indexing**: Optimized for common query patterns
- **Background Processing**: Async trip reconstruction and analysis
- **Connection Pooling**: Efficient SQLite usage with timeout handling

## Requirements

- Python 3.8+
- SQLite (included)
- No external database dependencies

Dependencies managed via `requirements.txt`

## Contributing

Issues and pull requests welcome. Please ensure new features include appropriate tests and documentation.

## Disclaimer

Unofficial tracker using publicly accessible data. Malfunction indicators are pattern-based estimates, not official diagnoses. System tracks bicycles, not individual users.
