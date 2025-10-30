#!/usr/bin/env python3
"""
Migration script to convert tags from string format to JSON-serialized list format.

This script:
1. Reads all memories from ChromaDB
2. Converts tags from "work,important" → '["work", "important"]' (JSON string)
3. Updates ChromaDB with the new format
4. Creates a backup before migration

Note: ChromaDB 1.2.1 doesn't support native lists in metadata, so we use
JSON serialization to preserve list structure while maintaining compatibility.

Usage:
    python migrate_tags.py [--dry-run]
"""
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import shutil
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mnemonic.vector_store import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backup_chroma_db(persist_dir: str) -> str:
    """
    Create a backup of the ChromaDB directory.
    
    Args:
        persist_dir: Path to ChromaDB directory
        
    Returns:
        Path to backup directory
    """
    persist_path = Path(persist_dir)
    if not persist_path.exists():
        logger.warning(f"ChromaDB directory not found: {persist_dir}")
        return ""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = persist_path.parent / f"chroma_backup_{timestamp}"
    
    logger.info(f"Creating backup: {backup_path}")
    shutil.copytree(persist_path, backup_path)
    logger.info(f"✓ Backup created successfully")
    
    return str(backup_path)


def convert_tags_to_json(tags_value):
    """
    Convert tags from various formats to JSON-serialized list.
    
    Args:
        tags_value: Tags value (could be string, JSON string, or None)
        
    Returns:
        JSON string of tags, or None if empty
    """
    if tags_value is None or tags_value == "":
        return None  # No tags
    
    # Try to parse as JSON first (in case already migrated)
    if isinstance(tags_value, str):
        try:
            parsed = json.loads(tags_value)
            if isinstance(parsed, list):
                # Already in JSON list format
                return tags_value if parsed else None
        except json.JSONDecodeError:
            pass
        
        # Parse comma-separated string
        tags = [tag.strip() for tag in tags_value.split(",") if tag.strip()]
        if tags:
            return json.dumps(tags)
        return None
    
    # Unknown format
    logger.warning(f"Unknown tags format: {type(tags_value)} = {tags_value}")
    return None


def migrate_tags(persist_dir: str = ".mnemonic/chroma", dry_run: bool = False):
    """
    Migrate tags from string format to JSON-serialized list format.
    
    Args:
        persist_dir: Path to ChromaDB directory
        dry_run: If True, show what would be changed without applying
    """
    logger.info("=" * 60)
    logger.info("Starting Tags Migration (JSON Serialization)")
    logger.info("=" * 60)
    logger.info("Strategy: Convert tags to JSON strings for ChromaDB 1.2.1")
    logger.info("Example: 'work,ai' → '[\"work\", \"ai\"]'")
    
    # Create backup (unless dry run)
    if not dry_run:
        backup_path = backup_chroma_db(persist_dir)
        if backup_path:
            logger.info(f"Backup location: {backup_path}")
    else:
        logger.info("DRY RUN MODE - No changes will be made")
    
    # Initialize vector store
    logger.info(f"\nLoading ChromaDB from: {persist_dir}")
    vector_store = VectorStore(persist_directory=persist_dir)
    
    # Get all memories
    memories = vector_store.get_all_memories()
    logger.info(f"Found {len(memories)} memories")
    
    if len(memories) == 0:
        logger.info("No memories to migrate")
        return
    
    # Analyze and migrate
    needs_migration = 0
    already_migrated = 0
    no_tags = 0
    
    logger.info("\n" + "=" * 60)
    logger.info("Processing Memories")
    logger.info("=" * 60)
    
    for memory in memories:
        memory_id = memory["id"]
        metadata = memory["metadata"]
        tags = metadata.get("tags")
        
        # Check if tags need migration
        is_json_list = False
        if isinstance(tags, str):
            try:
                parsed = json.loads(tags)
                is_json_list = isinstance(parsed, list)
            except json.JSONDecodeError:
                pass
        
        if isinstance(tags, str) and not is_json_list:
            # String format - needs migration
            needs_migration += 1
            old_tags = tags
            new_tags = convert_tags_to_json(tags)
            
            logger.info(f"\nMemory {memory_id[:8]}...")
            logger.info(f"  Old: tags = {repr(old_tags)}")
            if new_tags:
                logger.info(f"  New: tags = {new_tags}")
            else:
                logger.info(f"  New: (no tags - will remove)")
            
            if not dry_run:
                # Update metadata with new tags
                if new_tags is not None:
                    metadata["tags"] = new_tags
                else:
                    # Remove tags key if empty
                    metadata.pop("tags", None)
                    no_tags += 1
                
                # Re-serialize metadata (VectorStore will handle this)
                # But we need to pass native lists so it can serialize properly
                if "tags" in metadata:
                    metadata["tags"] = json.loads(metadata["tags"])
                
                # Update in ChromaDB
                vector_store.update_memory(
                    memory_id=memory_id,
                    content=memory["content"],
                    metadata=metadata
                )
                logger.info(f"  ✓ Updated")
        
        elif isinstance(tags, str) and is_json_list:
            # Already JSON format
            already_migrated += 1
            logger.debug(f"Memory {memory_id[:8]}... already has JSON tags")
        
        elif isinstance(tags, list):
            # Native list (shouldn't happen in ChromaDB 1.2.1, but handle it)
            logger.info(f"\nMemory {memory_id[:8]}...")
            logger.info(f"  Found native list: {tags}")
            logger.info(f"  Converting to JSON string...")
            
            if not dry_run:
                metadata["tags"] = tags  # VectorStore will serialize
                vector_store.update_memory(
                    memory_id=memory_id,
                    content=memory["content"],
                    metadata=metadata
                )
                logger.info(f"  ✓ Updated")
            needs_migration += 1
        
        elif tags is None:
            # No tags - this is fine
            logger.debug(f"Memory {memory_id[:8]}... has no tags")
        
        else:
            logger.warning(f"Memory {memory_id[:8]}... unknown tags type: {type(tags)}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Total memories:        {len(memories)}")
    logger.info(f"Needs migration:       {needs_migration}")
    logger.info(f"Already JSON format:   {already_migrated}")
    logger.info(f"No tags (removed):     {no_tags}")
    
    if dry_run:
        logger.info("\nDRY RUN - No changes were made")
        logger.info("Run without --dry-run to apply changes")
    else:
        logger.info(f"\n✓ Migration completed successfully!")
        logger.info(f"Backup saved to: {backup_path}")
        logger.info("\nTags are now stored as JSON strings:")
        logger.info('  Example: \'["work", "ai", "important"]\'')


def main():
    parser = argparse.ArgumentParser(
        description="Migrate tags from string to JSON-serialized list format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without applying"
    )
    parser.add_argument(
        "--persist-dir",
        default=".mnemonic/chroma",
        help="Path to ChromaDB directory (default: .mnemonic/chroma)"
    )
    
    args = parser.parse_args()
    
    try:
        migrate_tags(persist_dir=args.persist_dir, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()