#!/usr/bin/env python3
"""
Migration script to convert absolute file paths to relative paths.

This script updates the database to store only filenames instead of full paths,
making the application portable across different deployment environments.

Usage:
    python migrate_file_paths.py
"""

import os
from pathlib import Path
from database import get_db, engine
from models import DBFile
from sqlalchemy.orm import Session

def migrate_file_paths():
    """Convert absolute file paths to relative paths in the database."""
    
    db = next(get_db())
    
    try:
        # Get all files
        files = db.query(DBFile).all()
        
        print(f"Found {len(files)} files in database")
        updated_count = 0
        
        for file_obj in files:
            old_path = file_obj.file_path
            path = Path(old_path)
            
            # Check if path is absolute
            if path.is_absolute():
                # Extract just the filename
                filename = path.name
                
                print(f"Updating file ID {file_obj.id}:")
                print(f"  Old: {old_path}")
                print(f"  New: {filename}")
                
                file_obj.file_path = filename
                updated_count += 1
            else:
                print(f"File ID {file_obj.id} already has relative path: {old_path}")
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Successfully updated {updated_count} file paths")
        else:
            print("\n✅ No files needed updating")
            
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during migration: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("File Path Migration Script")
    print("=" * 60)
    print()
    
    migrate_file_paths()
    
    print()
    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)

