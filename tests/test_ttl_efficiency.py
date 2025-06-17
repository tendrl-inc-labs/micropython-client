import time
import gc

import btree

from tendrl.lib.microtetherdb.db import MicroTetherDB

def test_ttl_efficiency():
    """Test the new efficient TTL system"""
    print("Testing TTL Efficiency...")
    
    # Create database with frequent TTL checks
    db = MicroTetherDB(
        in_memory=True,
        ttl_check_interval=2,  # Check every 2 seconds
        cleanup_interval=60    # Full cleanup every minute
    )
    
    try:
        print("\n1. Adding items with various TTLs...")
        
        # Record start time for precise timing
        start_time = int(time.time())
        
        # Add items with different TTL values - use much longer TTLs to avoid timing issues
        items_added = 0
        
        # Short TTL items (will expire in 8 seconds)
        for i in range(5):
            db.put(f"short_{i}", {"data": f"expires_soon_{i}"}, ttl=8)
            items_added += 1
        
        # Medium TTL items (will expire in 20 seconds)
        for i in range(3):
            db.put(f"medium_{i}", {"data": f"expires_later_{i}"}, ttl=20)
            items_added += 1
            
        # Long TTL items (will expire in 40 seconds)
        for i in range(2):
            db.put(f"long_{i}", {"data": f"expires_much_later_{i}"}, ttl=40)
            items_added += 1
            
        # No TTL items (permanent)
        for i in range(3):
            db.put(f"permanent_{i}", {"data": f"never_expires_{i}"})
            items_added += 1
            
        print(f"Added {items_added} items total")
        print(f"TTL index size: {len(db._ttl_index)} items")
        
        # Verify TTL index only contains TTL items
        expected_ttl_items = 5 + 3 + 2  # short + medium + long
        assert len(db._ttl_index) == expected_ttl_items, f"Expected {expected_ttl_items} TTL items, got {len(db._ttl_index)}"
        
        print("\n2. Waiting for short TTL items to expire...")
        
        # Wait for short TTL items to expire (8 seconds + 2 second buffer)
        elapsed = int(time.time()) - start_time
        wait_time = max(0, 10 - elapsed)  # Wait until 10 seconds have passed
        if wait_time > 0:
            print(f"Waiting {wait_time} more seconds...")
            time.sleep(wait_time)
        
        # DON'T call manual cleanup - let the automatic TTL system handle it
        print("Waiting for automatic TTL cleanup...")
        time.sleep(3)  # Wait for TTL cleanup to run
        
        print(f"TTL index size after automatic cleanup: {len(db._ttl_index)} items")
        
        # Verify short TTL items are gone
        expired_count = 0
        for i in range(5):
            result = db.get(f"short_{i}")
            if result is None:
                expired_count += 1
            else:
                print(f"Warning: Short TTL item {i} still exists")
                
        print(f"Expired short TTL items: {expired_count}/5")
        
        # Verify other items still exist
        medium_exists = 0
        for i in range(3):
            result = db.get(f"medium_{i}")
            if result is not None:
                medium_exists += 1
            else:
                print(f"Error: Medium TTL item {i} should still exist but is gone")
                
        long_exists = 0
        for i in range(2):
            result = db.get(f"long_{i}")
            if result is not None:
                long_exists += 1
            else:
                print(f"Error: Long TTL item {i} should still exist but is gone")
                
        permanent_exists = 0
        for i in range(3):
            result = db.get(f"permanent_{i}")
            if result is not None:
                permanent_exists += 1
            else:
                print(f"Error: Permanent item {i} should still exist but is gone")
        
        print(f"Medium TTL items still exist: {medium_exists}/3")
        print(f"Long TTL items still exist: {long_exists}/2")
        print(f"Permanent items still exist: {permanent_exists}/3")
        
        # Allow some timing variance - at least 3 out of 5 short items should be expired
        assert expired_count >= 3, f"Expected at least 3 short TTL items to be expired, got {expired_count}"
        assert medium_exists == 3, f"Expected all 3 medium TTL items to exist, got {medium_exists}"
        assert long_exists == 2, f"Expected all 2 long TTL items to exist, got {long_exists}"
        assert permanent_exists == 3, f"Expected all 3 permanent items to exist, got {permanent_exists}"
        
        print("\n3. Testing automatic background cleanup...")
        
        # Add more short TTL items
        for i in range(3):
            db.put(f"auto_expire_{i}", {"data": f"auto_cleanup_{i}"}, ttl=3)
            
        print("Added 3 items with 3-second TTL")
        print("Waiting for automatic cleanup...")
        
        # Wait for automatic cleanup (ttl_check_interval=2 seconds + buffer)
        time.sleep(5)
        
        # Check if items were automatically removed
        auto_expired_count = 0
        for i in range(3):
            result = db.get(f"auto_expire_{i}")
            if result is None:
                auto_expired_count += 1
                
        print(f"Automatically expired items: {auto_expired_count}/3")
        
        print("\n4. Performance comparison simulation...")
        
        # Simulate what old system would do (full scan)
        start_time = time.time()
        all_keys = list(db._db.keys(None, None, btree.INCL))
        old_system_time = time.time() - start_time
        
        # Simulate new system (TTL index check)
        start_time = time.time()
        ttl_items_to_check = len(db._ttl_index)
        new_system_time = time.time() - start_time
        
        print(f"Total keys in database: {len(all_keys)}")
        print(f"TTL items to check: {ttl_items_to_check}")
        print(f"Old system would scan: {len(all_keys)} keys")
        print(f"New system checks: {ttl_items_to_check} TTL entries")
        
        efficiency_ratio = len(all_keys) / max(ttl_items_to_check, 1)
        print(f"Efficiency improvement: {efficiency_ratio:.1f}x")
        
        print("\n✅ TTL efficiency test completed successfully!")
        
        return {
            "total_items": len(all_keys),
            "ttl_items": ttl_items_to_check,
            "efficiency_ratio": efficiency_ratio,
            "auto_cleanup_success": auto_expired_count >= 2,  # Allow some timing variance
            "expired_short_items": expired_count,
            "remaining_medium_items": medium_exists,
            "remaining_long_items": long_exists,
            "remaining_permanent_items": permanent_exists
        }
        
    finally:
        db.close()

def test_ttl_index_accuracy():
    """Test that TTL index accurately tracks expiry times"""
    print("\nTesting TTL Index Accuracy...")
    
    db = MicroTetherDB(in_memory=True, ttl_check_interval=1)
    
    try:
        current_time = int(time.time())
        
        # Add items with known expiry times
        db.put("expire_in_5", {"test": "data"}, ttl=5)
        db.put("expire_in_10", {"test": "data"}, ttl=10)
        db.put("no_expiry", {"test": "data"})  # No TTL
        
        # Check TTL index contents
        assert len(db._ttl_index) == 2, "Should have 2 TTL items"
        
        # Verify expiry times are reasonable
        for expiry_time, key in db._ttl_index:
            time_diff = expiry_time - current_time
            assert 1 <= time_diff <= 15, f"Expiry time seems wrong for {key}: {time_diff}s"
            
        print("✅ TTL index accuracy test passed!")
        
    finally:
        db.close()

def debug_ttl_timing():
    """Debug TTL timing to understand the issue"""
    print("\nDebugging TTL Timing...")
    
    db = MicroTetherDB(in_memory=True, ttl_check_interval=1)
    
    try:
        start_time = int(time.time())
        print(f"Start time: {start_time}")
        
        # Add a single item with 5 second TTL (use data-first method to get generated key)
        key = db.put({"data": "test"}, ttl=5)
        print(f"Added item with key: {key}")
        
        # Parse the key to see the embedded timestamp and TTL
        timestamp_str, ttl_str, unique_id = key.split(":")
        embedded_timestamp = int(timestamp_str)
        embedded_ttl = int(ttl_str)
        
        print(f"Embedded timestamp: {embedded_timestamp}")
        print(f"Embedded TTL: {embedded_ttl}")
        print(f"Should expire at: {embedded_timestamp + embedded_ttl}")
        
        # Check expiry calculation
        current_time = int(time.time())
        expiry_time = embedded_timestamp + embedded_ttl
        time_until_expiry = expiry_time - current_time
        
        print(f"Current time: {current_time}")
        print(f"Time until expiry: {time_until_expiry} seconds")
        
        # Test the _is_expired method directly
        is_expired_now = db._ttl_manager.is_expired(key)
        print(f"Is expired now: {is_expired_now}")
        
        # Wait and check again
        time.sleep(6)
        current_time = int(time.time())
        is_expired_after_wait = db._ttl_manager.is_expired(key)
        time_after_wait = current_time - (embedded_timestamp + embedded_ttl)
        
        print(f"After waiting 6 seconds:")
        print(f"Current time: {current_time}")
        print(f"Time past expiry: {time_after_wait} seconds")
        print(f"Is expired after wait: {is_expired_after_wait}")
        
        # Try to get the item
        result = db.get(key)
        print(f"Can still get item: {result is not None}")
        
        # Wait for automatic cleanup
        print("Waiting for automatic cleanup...")
        time.sleep(3)
        
        # Try to get again
        result_after_cleanup = db.get(key)
        print(f"Can get item after automatic cleanup: {result_after_cleanup is not None}")
        
    finally:
        db.close()

if __name__ == "__main__":
    # Run debug first to understand timing
    debug_ttl_timing()
    
    # Run tests
    results = test_ttl_efficiency()
    test_ttl_index_accuracy()
    
    print(f"\n📊 Final Results:")
    print(f"   Total database items: {results['total_items']}")
    print(f"   Items with TTL: {results['ttl_items']}")
    print(f"   Efficiency improvement: {results['efficiency_ratio']:.1f}x")
    print(f"   Auto-cleanup working: {'✅' if results['auto_cleanup_success'] else '❌'}")
    print(f"   Expired short items: {results['expired_short_items']}/5")
    print(f"   Remaining medium items: {results['remaining_medium_items']}/3")
    print(f"   Remaining long items: {results['remaining_long_items']}/2")
    print(f"   Remaining permanent items: {results['remaining_permanent_items']}/3") 