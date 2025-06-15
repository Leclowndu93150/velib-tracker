#!/usr/bin/env python3
"""
Script to clear malfunction logs that were incorrectly flagged due to timing issues
"""
from app import create_app, db
from app.models import MalfunctionLog, Bike
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    # Clear all "stuck" malfunctions since they were likely false positives
    # due to checking bikes that haven't been tracked for 7+ days
    stuck_malfunctions = MalfunctionLog.query.filter_by(
        malfunction_type='stuck',
        is_active=True
    ).all()
    
    print(f"Found {len(stuck_malfunctions)} stuck malfunction logs to clear")
    
    for malfunction in stuck_malfunctions:
        bike = Bike.query.get(malfunction.bike_id)
        if bike:
            # Only keep if bike has actually been tracked for 8+ days
            days_tracked = (datetime.utcnow() - bike.created_at).days
            if days_tracked < 8:
                print(f"Clearing false positive stuck flag for bike {bike.bike_name} (tracked for {days_tracked} days)")
                malfunction.is_active = False
                bike.potential_malfunction = False
            else:
                print(f"Keeping stuck flag for bike {bike.bike_name} (tracked for {days_tracked} days)")
    
    # Reset malfunction scores for bikes with cleared flags
    for bike in Bike.query.filter_by(potential_malfunction=False).all():
        bike.malfunction_score = 0
    
    db.session.commit()
    print("Malfunction cleanup completed!")