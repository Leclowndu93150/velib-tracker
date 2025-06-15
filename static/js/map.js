// Initialize map
let map;
let stationMarkers = new L.LayerGroup();
let bikeMarkers = new L.LayerGroup();
let tripPaths = new L.LayerGroup();
let selectedItem = null;

// Custom icons
const stationIcon = L.divIcon({
    className: 'station-marker',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15]
});

const bikeIcon = L.divIcon({
    className: 'bike-marker',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10]
});

// Initialize map
function initMap() {
    map = L.map('map').setView([48.8566, 2.3522], 12); // Paris center
    window.map = map; // Make map globally accessible for theme switching
    
    // Always use light mode tiles for map
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // Add layer groups
    stationMarkers.addTo(map);
    bikeMarkers.addTo(map);
    tripPaths.addTo(map);
    
    // Load initial data
    loadStations();
    loadLiveStats();
    
    // Set up refresh intervals
    setInterval(loadStations, 60000); // Refresh every minute
    setInterval(loadLiveStats, 30000); // Refresh stats every 30 seconds
}

// Load stations
async function loadStations() {
    try {
        const response = await fetch('/api/stations');
        const data = await response.json();
        
        stationMarkers.clearLayers();
        
        data.stations.forEach(station => {
            const fillRate = (station.nb_bike + station.nb_ebike) / station.total_capacity;
            let markerClass = 'station-marker';
            
            if (fillRate === 0) markerClass += ' empty';
            else if (fillRate === 1) markerClass += ' full';
            else if (fillRate < 0.2) markerClass += ' low';
            
            const icon = L.divIcon({
                className: markerClass,
                html: `<span>${station.nb_bike + station.nb_ebike}</span>`,
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            });
            
            const marker = L.marker([station.latitude, station.longitude], { icon })
                .bindPopup(createStationPopup(station))
                .on('click', () => selectStation(station));
            
            // Apply filters
            if (shouldShowStation(station)) {
                marker.addTo(stationMarkers);
            }
        });
    } catch (error) {
        console.error('Error loading stations:', error);
    }
}

// Create station popup
function createStationPopup(station) {
    return `
        <div class="popup-content">
            <div class="popup-header">${station.name}</div>
            <div class="popup-stats">
                <div class="popup-stat">
                    <div class="popup-stat-value">${station.nb_bike}</div>
                    <div class="popup-stat-label">Mechanical</div>
                </div>
                <div class="popup-stat">
                    <div class="popup-stat-value">${station.nb_ebike}</div>
                    <div class="popup-stat-label">Electric</div>
                </div>
                <div class="popup-stat">
                    <div class="popup-stat-value">${station.nb_free_dock + station.nb_free_edock}</div>
                    <div class="popup-stat-label">Free Docks</div>
                </div>
                <div class="popup-stat">
                    <div class="popup-stat-value">${station.total_capacity}</div>
                    <div class="popup-stat-label">Capacity</div>
                </div>
            </div>
            <button class="btn btn-sm btn-primary w-100 mt-2" onclick="viewStationDetails('${station.code}')">
                View Details
            </button>
        </div>
    `;
}

// Load in-transit bikes
async function loadInTransitBikes() {
    if (!document.getElementById('showInTransit').checked) {
        bikeMarkers.clearLayers();
        return;
    }
    
    try {
        const response = await fetch('/api/trips/live');
        const data = await response.json();
        
        bikeMarkers.clearLayers();
        
        data.live_trips.forEach(trip => {
            if (trip.start_station) {
                // Place marker at start station for now
                const iconClass = trip.bike_electric ? 'bike-marker electric' : 'bike-marker';
                const icon = L.divIcon({
                    className: iconClass,
                    iconSize: [20, 20],
                    iconAnchor: [10, 10],
                    popupAnchor: [0, -10]
                });
                
                const marker = L.marker([trip.start_station.lat, trip.start_station.lon], { icon })
                    .bindPopup(createBikePopup(trip))
                    .addTo(bikeMarkers);
            }
        });
    } catch (error) {
        console.error('Error loading in-transit bikes:', error);
    }
}

// Create bike popup
function createBikePopup(trip) {
    const duration = Math.floor(trip.duration_so_far / 60);
    return `
        <div class="popup-content">
            <div class="popup-header">Bike ${trip.bike_name}</div>
            <p><strong>Type:</strong> ${trip.bike_electric ? 'Electric' : 'Mechanical'}</p>
            <p><strong>From:</strong> ${trip.start_station.name}</p>
            <p><strong>Duration:</strong> ${duration} minutes</p>
            <button class="btn btn-sm btn-primary w-100 mt-2" onclick="viewBikeDetails('${trip.bike_name}')">
                View Details
            </button>
        </div>
    `;
}

// Load live statistics
async function loadLiveStats() {
    try {
        const response = await fetch('/api/statistics/overview');
        const data = await response.json();
        
        const statsHtml = `
            <p><strong>Total Bikes:</strong> ${data.total_bikes}</p>
            <p><strong>Available:</strong> ${data.bike_status.disponible || 0}</p>
            <p><strong>In Transit:</strong> ${data.bike_status.in_transit || 0}</p>
            <p><strong>Missing:</strong> ${data.bike_status.missing || 0}</p>
            <p><strong>Malfunctions:</strong> ${data.active_malfunctions}</p>
            <p><strong>Trips Today:</strong> ${data.trips_today}</p>
            <p><strong>Last Hour:</strong> ${data.trips_last_hour}</p>
        `;
        
        document.getElementById('liveStats').innerHTML = statsHtml;
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Filter functions
function shouldShowStation(station) {
    const showEmpty = document.getElementById('showEmptyStations').checked;
    const showFull = document.getElementById('showFullStations').checked;
    const showAll = document.getElementById('showStations').checked;
    
    if (!showAll && !showEmpty && !showFull) return false;
    
    const isEmpty = (station.nb_bike + station.nb_ebike) === 0;
    const isFull = (station.nb_free_dock + station.nb_free_edock) === 0;
    
    if (showEmpty && isEmpty) return true;
    if (showFull && isFull) return true;
    if (showAll && !showEmpty && !showFull) return true;
    
    return false;
}

// Selection functions
function selectStation(station) {
    selectedItem = { type: 'station', data: station };
    showSelectedInfo();
}

async function showSelectedInfo() {
    if (!selectedItem) return;
    
    const infoDiv = document.getElementById('selectedInfo');
    const contentDiv = document.getElementById('selectedContent');
    
    if (selectedItem.type === 'station') {
        const station = selectedItem.data;
        contentDiv.innerHTML = `
            <h6>${station.name}</h6>
            <p class="mb-1"><small>Code: ${station.code}</small></p>
            <p class="mb-1">Bikes: ${station.nb_bike + station.nb_ebike} / ${station.total_capacity}</p>
            <button class="btn btn-sm btn-primary w-100 mt-2" onclick="viewStationHistory('${station.code}')">
                View History
            </button>
        `;
    }
    
    infoDiv.style.display = 'block';
}

// View functions
function viewStationDetails(stationCode) {
    window.location.href = `/stations/${stationCode}`;
}

function viewBikeDetails(bikeName) {
    window.location.href = `/bikes/${bikeName}`;
}

async function viewStationHistory(stationCode) {
    // Load and display station history
    try {
        const response = await fetch(`/api/stations/${stationCode}/history?hours=24`);
        const data = await response.json();
        // TODO: Display history chart
        console.log('Station history:', data);
    } catch (error) {
        console.error('Error loading station history:', error);
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    
    // Filter change listeners
    document.getElementById('showStations').addEventListener('change', loadStations);
    document.getElementById('showEmptyStations').addEventListener('change', loadStations);
    document.getElementById('showFullStations').addEventListener('change', loadStations);
    document.getElementById('showInTransit').addEventListener('change', loadInTransitBikes);
    document.getElementById('showMalfunctions').addEventListener('change', loadMalfunctioningBikes);
});

// Load malfunctioning bikes
async function loadMalfunctioningBikes() {
    if (!document.getElementById('showMalfunctions').checked) {
        return;
    }
    
    try {
        const response = await fetch('/api/bikes/malfunctioning');
        const data = await response.json();
        
        data.bikes.forEach(bike => {
            if (bike.current_station_id) {
                // TODO: Add malfunction markers to map
                console.log('Malfunctioning bike:', bike);
            }
        });
    } catch (error) {
        console.error('Error loading malfunctioning bikes:', error);
    }
}