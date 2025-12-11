"""
Migration script to add 'status' column to projects table.
This script adds the status column with default value 'draft' for existing projects.
"""
import sys
from pathlib import Path
from sqlalchemy import text
from database import engine, SessionLocal

def migrate():
    """Add status column to projects table if it doesn't exist."""
    db = SessionLocal()
    try:
        # Check if column already exists
        if engine.url.drivername == 'sqlite':
            # SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
            # So we check if column exists first
            result = db.execute(text("PRAGMA table_info(projects)"))
            columns = [row[1] for row in result]
            
            if 'status' not in columns:
                print("Adding 'status' column to projects table...")
                db.execute(text("ALTER TABLE projects ADD COLUMN status VARCHAR DEFAULT 'draft'"))
                # Update existing projects to have 'draft' status
                db.execute(text("UPDATE projects SET status = 'draft' WHERE status IS NULL"))
                db.commit()
                print("✅ Migration completed successfully!")
            else:
                print("✅ Column 'status' already exists. Migration not needed.")
        else:
            # PostgreSQL/MySQL
            try:
                db.execute(text("ALTER TABLE projects ADD COLUMN status VARCHAR DEFAULT 'draft'"))
                db.execute(text("UPDATE projects SET status = 'draft' WHERE status IS NULL"))
                db.commit()
                print("✅ Migration completed successfully!")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    print("✅ Column 'status' already exists. Migration not needed.")
                else:
                    raise
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("Running migration: Add status column to projects table...")
    migrate()

