#!/usr/bin/env python3
"""
Database migration script to add missing columns and fix boomerang logic
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from sqlalchemy import text
from datetime import datetime

def migrate_database():
    app = create_app()
    with app.app_context():
        print("Starting database migration...")
        
        # Add the missing arrived_at_station column
        try:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE bikes ADD COLUMN arrived_at_station DATETIME'))
                conn.commit()
            print('✓ Successfully added arrived_at_station column')
        except Exception as e:
            print(f'! arrived_at_station column: {e}')
        
        # Verify the column exists
        with db.engine.connect() as conn:
            result = conn.execute(text('PRAGMA table_info(bikes)'))
            columns = [row[1] for row in result]
            print(f"Current bike columns: {columns}")
            
            if 'arrived_at_station' in columns:
                print('✓ arrived_at_station column is present')
                
                # Initialize arrived_at_station for existing bikes
                # Set it to last_seen_at for bikes currently at stations
                try:
                    conn.execute(text('''
                        UPDATE bikes 
                        SET arrived_at_station = last_seen_at 
                        WHERE current_station_id IS NOT NULL 
                        AND arrived_at_station IS NULL
                    '''))
                    conn.commit()
                    print('✓ Initialized arrived_at_station for existing bikes')
                except Exception as e:
                    print(f'! Error initializing arrived_at_station: {e}')
            else:
                print('✗ arrived_at_station column not found')
        
        # Commit changes
        db.session.commit()
        print("Database migration completed!")

if __name__ == '__main__':
    migrate_database()