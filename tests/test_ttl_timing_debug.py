import time
import btree
from tendrl.lib.microtetherdb.db import MicroTetherDB

def debug_ttl_timing():
    """Debug the exact timing issue"""
    print("=== TTL Timing Debug ===")
    
    db = MicroTetherDB(in_memory=True, ttl_check_interval=60)  # Disable automatic cleanup
    
    try:
        start_time = int(time.time())
        print(f"Test start time: {start_time}")
        
        # Add items with precise timing
        print("\nAdding items...")
        
        # Short TTL items (6 seconds) - use data-first method to get generated keys
        short_keys = []
        for i in range(3):
            key = db.put({"type": "short", "id": i, "data": f"short_{i}"}, ttl=6)
            short_keys.append(key)
            print(f"Added short_{i} with key: {key}")
        
        # Medium TTL items (15 seconds) 
        medium_keys = []
        for i in range(2):
            key = db.put({"type": "medium", "id": i, "data": f"medium_{i}"}, ttl=15)
            medium_keys.append(key)
            print(f"Added medium_{i} with key: {key}")
        
        creation_time = int(time.time())
        print(f"All items created by: {creation_time}")
        print(f"Creation took: {creation_time - start_time} seconds")
        
        # Parse keys to see embedded timestamps
        print("\nKey analysis:")
        for i, key in enumerate(short_keys):
            parts = key.split(":")
            timestamp = int(parts[0])
            ttl = int(parts[1])
            expiry = timestamp + ttl
            print(f"short_{i}: timestamp={timestamp}, ttl={ttl}, expires_at={expiry}")
        
        for i, key in enumerate(medium_keys):
            parts = key.split(":")
            timestamp = int(parts[0])
            ttl = int(parts[1])
            expiry = timestamp + ttl
            print(f"medium_{i}: timestamp={timestamp}, ttl={ttl}, expires_at={expiry}")
        
        # Wait for short items to expire
        print(f"\nWaiting for short TTL items to expire...")
        wait_until = start_time + 7  # Wait 7 seconds from start
        current_time = int(time.time())
        wait_time = max(0, wait_until - current_time)
        print(f"Current time: {current_time}, waiting {wait_time} more seconds...")
        
        if wait_time > 0:
            time.sleep(wait_time)
        
        check_time = int(time.time())
        print(f"Check time: {check_time}")
        
        # Check what should be expired
        print("\nExpiry analysis:")
        for i, key in enumerate(short_keys):
            parts = key.split(":")
            timestamp = int(parts[0])
            ttl = int(parts[1])
            expiry = timestamp + ttl
            is_expired = check_time > expiry
            print(f"short_{i}: expires_at={expiry}, current={check_time}, expired={is_expired}")
        
        for i, key in enumerate(medium_keys):
            parts = key.split(":")
            timestamp = int(parts[0])
            ttl = int(parts[1])
            expiry = timestamp + ttl
            is_expired = check_time > expiry
            print(f"medium_{i}: expires_at={expiry}, current={check_time}, expired={is_expired}")
        
        # Test TTL manager directly
        print("\nTTL Manager analysis:")
        for i, key in enumerate(short_keys):
            is_expired = db._ttl_manager.is_expired(key)
            print(f"short_{i}: TTL manager says expired={is_expired}")
        
        for i, key in enumerate(medium_keys):
            is_expired = db._ttl_manager.is_expired(key)
            print(f"medium_{i}: TTL manager says expired={is_expired}")
        
        # Check what exists before cleanup
        print("\nBefore cleanup - what exists:")
        for i, key in enumerate(short_keys):
            exists = db.get(key) is not None
            print(f"short_{i}: exists={exists}")
        
        for i, key in enumerate(medium_keys):
            exists = db.get(key) is not None
            print(f"medium_{i}: exists={exists}")
        
        # Run cleanup and see what gets deleted
        print("\nRunning cleanup...")
        deleted = db.cleanup()
        print(f"Cleanup deleted: {deleted} items")
        
        # Check what exists after cleanup
        print("\nAfter cleanup - what exists:")
        for i, key in enumerate(short_keys):
            exists = db.get(key) is not None
            print(f"short_{i}: exists={exists}")
        
        for i, key in enumerate(medium_keys):
            exists = db.get(key) is not None
            print(f"medium_{i}: exists={exists}")
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_ttl_timing() 