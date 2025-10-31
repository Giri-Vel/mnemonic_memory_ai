#!/usr/bin/env python3
"""
Migration Runner for Mnemonic

Runs all pending database migrations in order.
"""

import sqlite3
import sys
from pathlib import Path
import importlib.util


def get_current_version(db_path: str) -> int:
    """Get the current schema version from database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if schema_version table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='schema_version'
        """)
        
        if not cursor.fetchone():
            conn.close()
            return 0  # No migrations applied yet
        
        # Get latest version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result[0] else 0
        
    except Exception as e:
        print(f"Warning: Could not read schema version: {e}")
        return 0


def get_migration_files() -> list:
    """Get all migration files in order"""
    migrations_dir = Path(__file__).parent / "migrations"
    
    if not migrations_dir.exists():
        print(f"✗ Migrations directory not found: {migrations_dir}")
        return []
    
    # Find all migration files
    migration_files = sorted(migrations_dir.glob("*.py"))
    
    # Filter out __init__.py and __pycache__
    migration_files = [
        f for f in migration_files 
        if f.name != "__init__.py" and not f.name.startswith(".")
    ]
    
    return migration_files


def load_migration(migration_file: Path):
    """Load a migration module dynamically"""
    spec = importlib.util.spec_from_file_location(
        migration_file.stem, 
        migration_file
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_migrations(db_path: str, target_version: int = None):
    """
    Run all pending migrations
    
    Args:
        db_path: Path to SQLite database
        target_version: Target version (None = latest)
    """
    print(f"\n{'='*60}")
    print("MNEMONIC DATABASE MIGRATION")
    print(f"{'='*60}\n")
    
    # Check if database exists
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"Creating new database: {db_path}")
        # Touch the file to create it
        db_file.touch()
    
    # Get current version
    current_version = get_current_version(db_path)
    print(f"Current schema version: {current_version}")
    
    # Get migration files
    migration_files = get_migration_files()
    
    if not migration_files:
        print("✗ No migration files found in migrations/")
        return False
    
    print(f"Found {len(migration_files)} migration(s)\n")
    
    # Run pending migrations
    applied_count = 0
    
    for migration_file in migration_files:
        # Load migration module
        try:
            migration = load_migration(migration_file)
            migration_version = migration.get_migration_version()
        except Exception as e:
            print(f"✗ Failed to load {migration_file.name}: {e}")
            continue
        
        # Skip if already applied
        if migration_version <= current_version:
            print(f"⊘ Skipping {migration_file.name} (already applied)")
            continue
        
        # Skip if beyond target version
        if target_version and migration_version > target_version:
            print(f"⊘ Skipping {migration_file.name} (beyond target version)")
            continue
        
        # Apply migration
        print(f"→ Applying {migration_file.name}...")
        try:
            migration.upgrade(db_path)
            applied_count += 1
        except Exception as e:
            print(f"✗ Migration failed: {e}")
            return False
    
    print(f"\n{'='*60}")
    if applied_count > 0:
        print(f"✓ Applied {applied_count} migration(s)")
        new_version = get_current_version(db_path)
        print(f"✓ Schema version: {current_version} → {new_version}")
    else:
        print("✓ Database is up to date")
    print(f"{'='*60}\n")
    
    return True


def show_status(db_path: str):
    """Show migration status"""
    print(f"\n{'='*60}")
    print("MIGRATION STATUS")
    print(f"{'='*60}\n")
    
    current_version = get_current_version(db_path)
    print(f"Current version: {current_version}")
    
    migration_files = get_migration_files()
    print(f"\nAvailable migrations:")
    
    for migration_file in migration_files:
        try:
            migration = load_migration(migration_file)
            version = migration.get_migration_version()
            status = "✓ Applied" if version <= current_version else "⊙ Pending"
            print(f"  {status} - {migration_file.name} (v{version})")
        except Exception as e:
            print(f"  ✗ Error - {migration_file.name}: {e}")
    
    print()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate.py <db_path>              # Run all pending migrations")
        print("  python migrate.py <db_path> status       # Show migration status")
        print("  python migrate.py <db_path> <version>    # Migrate to specific version")
        print("\nExample:")
        print("  python migrate.py mnemonic.db")
        print("  python migrate.py mnemonic.db status")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    if len(sys.argv) > 2:
        if sys.argv[2] == "status":
            show_status(db_path)
        else:
            try:
                target_version = int(sys.argv[2])
                run_migrations(db_path, target_version)
            except ValueError:
                print(f"✗ Invalid version: {sys.argv[2]}")
                sys.exit(1)
    else:
        success = run_migrations(db_path)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()