import time
import btree
from tendrl.lib.microtetherdb.db import MicroTetherDB

def test_read_write_consistency():
    """Test that reads see unflushed writes immediately"""
    print("Testing Read-Write Consistency...")
    
    # Create database with very high flush threshold to prevent automatic flushing
    db = MicroTetherDB(
        in_memory=True,
        adaptive_threshold=False  # Disable adaptive flushing
    )
    
    # Set very high threshold to prevent flushing
    db._flush_manager._flush_threshold = 1000
    
    try:
        print("\n1. Testing immediate read after write (no flush)...")
        
        # Write data without triggering flush
        key = db.put({"test": "data", "value": 123})
        print(f"Wrote key: {key}")
        print(f"Flush counter: {db._flush_counter}")
        
        # Immediately read the data back
        result = db.get(key)
        print(f"Read result: {result}")
        
        # Verify we can read what we just wrote
        assert result is not None, "Should be able to read unflushed write"
        assert result["test"] == "data", "Data should match what was written"
        assert result["value"] == 123, "Value should match what was written"
        
        print("✅ Can read unflushed writes immediately")
        
        print("\n2. Testing multiple writes without flush...")
        
        # Write multiple items without flushing
        keys = []
        for i in range(5):
            key = db.put({"item": i, "data": f"test_{i}"})
            keys.append(key)
            
        print(f"Wrote {len(keys)} items")
        print(f"Flush counter: {db._flush_counter}")
        
        # Read all items back
        for i, key in enumerate(keys):
            result = db.get(key)
            assert result is not None, f"Item {i} should be readable"
            assert result["item"] == i, f"Item {i} data should match"
            
        print("✅ All unflushed writes are readable")
        
        print("\n3. Testing delete without flush...")
        
        # Delete an item without flushing
        deleted_key = keys[2]
        delete_result = db.delete(deleted_key)
        print(f"Deleted key: {deleted_key}, result: {delete_result}")
        print(f"Flush counter: {db._flush_counter}")
        
        # Verify deletion is immediately visible
        result = db.get(deleted_key)
        assert result is None, "Deleted item should not be readable"
        
        # Verify other items still exist
        for i, key in enumerate(keys):
            if i == 2:  # Skip the deleted one
                continue
            result = db.get(key)
            assert result is not None, f"Non-deleted item {i} should still exist"
            
        print("✅ Unflushed deletes are immediately visible")
        
        print("\n4. Testing query on unflushed data...")
        
        # Query should see all unflushed data
        results = db.query({"item": {"$gte": 0}})
        print(f"Query found {len(results)} items")
        
        # Should find 4 items (5 written, 1 deleted)
        assert len(results) == 4, f"Expected 4 items, found {len(results)}"
        
        print("✅ Queries see unflushed writes and deletes")
        
        print("\n5. Testing after manual flush...")
        
        # Now manually flush
        db._db.flush()
        db._flush_manager.reset_counters()
        print("Manually flushed database")
        
        # Everything should still be readable
        for i, key in enumerate(keys):
            if i == 2:  # Skip the deleted one
                continue
            result = db.get(key)
            assert result is not None, f"Item {i} should still exist after flush"
            
        # Deleted item should still be gone
        result = db.get(deleted_key)
        assert result is None, "Deleted item should still be gone after flush"
        
        print("✅ Data consistency maintained after flush")
        
        return True
        
    finally:
        db.close()

def test_btree_consistency_directly():
    """Test btree consistency behavior directly"""
    print("\nTesting BTree Consistency Directly...")
    
    try:
        import io
        
        # Create btree directly
        stream = io.BytesIO()
        db = btree.open(stream, cachesize=32, pagesize=512)
        
        print("1. Writing to btree without flush...")
        db[b"key1"] = b"value1"
        db[b"key2"] = b"value2"
        
        print("2. Reading from btree before flush...")
        result1 = db[b"key1"]
        result2 = db[b"key2"]
        
        print(f"Read key1: {result1}")
        print(f"Read key2: {result2}")
        
        assert result1 == b"value1", "Should read unflushed write"
        assert result2 == b"value2", "Should read unflushed write"
        
        print("3. Deleting from btree without flush...")
        del db[b"key1"]
        
        print("4. Checking deletion before flush...")
        try:
            result = db[b"key1"]
            assert False, "Should not be able to read deleted key"
        except KeyError:
            print("✅ Deleted key not found (correct)")
            
        # key2 should still exist
        result2 = db[b"key2"]
        assert result2 == b"value2", "Non-deleted key should still exist"
        
        print("✅ BTree maintains consistency without flushing")
        
        db.close()
        return True
        
    except ImportError:
        print("⚠️  btree module not available for direct testing")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING DATABASE CONSISTENCY")
    print("=" * 60)
    
    # Test high-level database consistency
    test_read_write_consistency()
    
    # Test low-level btree consistency
    test_btree_consistency_directly()
    
    print("\n" + "=" * 60)
    print("CONCLUSION: Reads see unflushed writes immediately!")
    print("BTree maintains in-memory consistency regardless of flush status.")
    print("Flushing only affects persistence, not read consistency.")
    print("=" * 60) 