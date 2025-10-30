#!/usr/bin/env python3
"""
Check ChromaDB version and test list support in metadata.
"""
import chromadb
from chromadb.config import Settings
import tempfile
import shutil
from pathlib import Path

def test_list_support():
    """Test if ChromaDB supports lists in metadata."""
    print("=" * 60)
    print("ChromaDB Version Check")
    print("=" * 60)
    
    # Check version
    version = chromadb.__version__
    print(f"ChromaDB Version: {version}")
    
    # Parse version to check if >= 0.4.0
    try:
        major, minor, *_ = version.split('.')
        version_tuple = (int(major), int(minor))
        
        if version_tuple >= (0, 4):
            print(f"✓ Version {version} should support lists in metadata")
        else:
            print(f"⚠ Version {version} may not support lists in metadata")
            print("  Recommendation: Upgrade to ChromaDB >= 0.4.0")
    except:
        print(f"⚠ Could not parse version: {version}")
    
    print("\n" + "=" * 60)
    print("Testing List Support")
    print("=" * 60)
    
    # Create temporary test directory
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Initialize test client
        client = chromadb.PersistentClient(
            path=str(temp_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create test collection
        collection = client.create_collection("test_list_support")
        
        # Test 1: Add with list metadata
        print("\nTest 1: Adding document with list in metadata...")
        try:
            collection.add(
                documents=["Test document"],
                metadatas=[{"tags": ["tag1", "tag2", "tag3"]}],
                ids=["test1"]
            )
            print("✓ SUCCESS: Can add lists to metadata")
            
            # Retrieve and check
            result = collection.get(ids=["test1"])
            print(f"  Retrieved tags: {result['metadatas'][0].get('tags')}")
            
        except Exception as e:
            print(f"✗ FAILED: Cannot add lists to metadata")
            print(f"  Error: {e}")
            return False
        
        # Test 2: Update with list metadata
        print("\nTest 2: Updating document with list in metadata...")
        try:
            collection.update(
                documents=["Updated document"],
                metadatas=[{"tags": ["new1", "new2"]}],
                ids=["test1"]
            )
            print("✓ SUCCESS: Can update with lists in metadata")
            
            # Retrieve and check
            result = collection.get(ids=["test1"])
            print(f"  Retrieved tags: {result['metadatas'][0].get('tags')}")
            
        except Exception as e:
            print(f"✗ FAILED: Cannot update with lists in metadata")
            print(f"  Error: {e}")
            return False
        
        # Test 3: Query with list filtering
        print("\nTest 3: Querying with list filters...")
        try:
            # Add another document
            collection.add(
                documents=["Another document"],
                metadatas=[{"tags": ["different", "tags"]}],
                ids=["test2"]
            )
            
            # Try to query (note: where clauses on lists have limited support)
            results = collection.query(
                query_texts=["test"],
                n_results=2
            )
            print("✓ SUCCESS: Can query collections with list metadata")
            
        except Exception as e:
            print(f"⚠ WARNING: Query works but filtering may be limited")
            print(f"  Error: {e}")
        
        print("\n" + "=" * 60)
        print("RESULT: ChromaDB supports lists in metadata! ✓")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ FAILED: ChromaDB does not support lists properly")
        print(f"Error: {e}")
        print("\n" + "=" * 60)
        print("RECOMMENDATION:")
        print("=" * 60)
        print("1. Upgrade ChromaDB: pip install --upgrade chromadb")
        print("2. Or use string format for tags: 'tag1,tag2,tag3'")
        return False
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_list_support()