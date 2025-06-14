import gc
import os
import time
import asyncio
from tendrl.lib.microtetherdb.db import MicroTetherDB

def show_memory():
    free = gc.mem_free()
    allocated = gc.mem_alloc()
    total = free + allocated
    print("Total:", total, "bytes")
    print("Used:", allocated, "bytes")
    print("Free:", free, "bytes")

def measure_time(func):
    """Decorator to measure execution time in milliseconds"""
    def wrapper(*args, **kwargs):
        start = time.ticks_ms()
        result = func(*args, **kwargs)
        end = time.ticks_ms()
        duration = time.ticks_diff(end, start)
        return result
    return wrapper

def time_operation(operation, *args, performance_summary=None, **kwargs):
    """Helper function to measure individual operation time in milliseconds"""
    start = time.ticks_ms()
    result = None
    success = False
    start_memory = gc.mem_alloc()

    # Determine operation type for performance tracking
    op_name = operation.__name__
    # Map function names to metric categories
    if op_name == "put_batch":
        metric_category = "batch_put"
    elif op_name == "delete_batch":
        metric_category = "batch_delete"
    else:
        metric_category = op_name

    try:
        # Remove performance_summary from kwargs
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'performance_summary'}

        # Handle async operations - MicroPython style
        if hasattr(operation, '__await__'):
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(operation(*args, **filtered_kwargs))
        else:
            result = operation(*args, **filtered_kwargs)

        success = True

        if performance_summary is not None and metric_category in ['batch_put', 'batch_delete']:
            if op_name == "put_batch":
                items_processed = len(result) if result else 0
            else:  # delete_batch
                items_processed = result if result else 0

            performance_summary[metric_category]['total_items'] += items_processed

            if performance_summary[metric_category]['total_ops'] > 0:
                performance_summary[metric_category]['avg_items_per_batch'] = (
                    performance_summary[metric_category]['total_items'] /
                    performance_summary[metric_category]['total_ops']
                )

        # Track query result counts
        if performance_summary is not None and op_name == "query":
            if not isinstance(result, list):
                result = list(result)
            performance_summary['query']['result_counts'].append(len(result))

    except Exception as e:
        success = False
        raise

    end = time.ticks_ms()
    duration = time.ticks_diff(end, start)
    end_memory = gc.mem_alloc()
    memory_used = end_memory - start_memory

    # Track performance metrics
    if performance_summary is not None and metric_category in performance_summary:
        # Update basic metrics
        performance_summary[metric_category]['total_time'] += duration
        performance_summary[metric_category]['total_ops'] += 1
        performance_summary[metric_category]['avg_time'] = (
            performance_summary[metric_category]['total_time'] /
            performance_summary[metric_category]['total_ops']
        )

        # Update memory metrics
        performance_summary[metric_category]['memory_used'] += memory_used
        performance_summary[metric_category]['peak_memory'] = max(
            performance_summary[metric_category]['peak_memory'],
            end_memory
        )

        # Update success/failure metrics
        if success:
            performance_summary[metric_category]['success_count'] += 1
        else:
            performance_summary[metric_category]['failure_count'] += 1

        # Update min/max times
        if duration < performance_summary[metric_category]['min_time']:
            performance_summary[metric_category]['min_time'] = duration
        if duration > performance_summary[metric_category]['max_time']:
            performance_summary[metric_category]['max_time'] = duration

    return result, duration

@measure_time
def test_basic_operations(performance_summary, db):
    """Test basic put/get operations"""
    try:
        # Test put
        result, _ = time_operation(db.put, {"name": "John", "age": 30}, performance_summary=performance_summary)
        if result is None:
            raise ValueError("Put operation failed to return a key")

        key = result  # Store the key for later use

        # Test get
        result, _ = time_operation(db.get, key, performance_summary=performance_summary)
        if result is None:
            raise ValueError(f"Failed to retrieve data for key {key}")

        assert result["name"] == "John" and result["age"] == 30, "Get data mismatch"

        # Test delete
        result, _ = time_operation(db.delete, key, performance_summary=performance_summary)
        assert result == 1, "Delete count mismatch"

        # Verify deletion
        result, _ = time_operation(db.get, key, performance_summary=performance_summary)
        assert result is None, "Data still exists after delete"

        # Test explicit key with put
        result, _ = time_operation(db.put, "test_key", {"name": "Jane", "age": 25}, performance_summary=performance_summary)
        assert result == "test_key", "Explicit key mismatch"

        # Verify data with explicit key
        data = db.get("test_key")
        assert data["name"] == "Jane" and data["age"] == 25, "Explicit key data mismatch"

    finally:
        del db

@measure_time
def test_ttl(performance_summary, db):
    """Test TTL functionality"""
    try:
        # Create a separate test database with faster TTL checking (1 second interval)
        test_db = MicroTetherDB(
            filename="ttl_test.db",
            in_memory=True,
            ttl_check_interval=1  # Check every 1 second instead of 10
        )
        
        # Store data with 2 second TTL
        result, _ = time_operation(test_db.put, {"name": "John"}, ttl=2, performance_summary=performance_summary)

        # Verify data exists
        data, _ = time_operation(test_db.get, result, performance_summary=performance_summary)
        assert data is not None, "Data not found before TTL"

        # Wait for TTL to expire (3 seconds should be enough with 1s check interval)
        time.sleep(3)

        # Check if data is gone (background worker should have cleaned it up)
        data, _ = time_operation(test_db.get, result, performance_summary=performance_summary)
        
        # If still not cleaned up, force cleanup as fallback
        if data is not None:
            test_db.cleanup()
            data, _ = time_operation(test_db.get, result, performance_summary=performance_summary)

        # Verify data is gone
        assert data is None, "Data still exists after TTL"
        
        # Clean up test database
        test_db.close()

    finally:
        del db

@measure_time
def test_batch_operations(performance_summary, db):
    """Test batch operations"""
    try:
        # Test batch put
        batch_items = [
            {"name": "Item1", "value": 10},
            {"name": "Item2", "value": 20},
            {"name": "Item3", "value": 30},
        ]

        keys, _ = time_operation(db.put_batch, batch_items, performance_summary=performance_summary)
        assert len(keys) == 3, "Should insert 3 items"

        # Verify the data was inserted correctly
        for i, key in enumerate(keys):
            data = db.get(key)
            assert data["name"] == f"Item{i + 1}", f"Item {i + 1} name incorrect"
            assert data["value"] == (i + 1) * 10, f"Item {i + 1} value incorrect"

        # Test batch delete
        deleted, _ = time_operation(db.delete_batch, keys[:2], performance_summary=performance_summary)
        assert deleted == 2, "Should delete 2 items"

        # Verify deletion
        assert db.get(keys[0]) is None, "First item should be deleted"
        assert db.get(keys[1]) is None, "Second item should be deleted"
        assert db.get(keys[2]) is not None, "Third item should still exist"

        # Test batch put with TTLs
        ttl_batch = [
            {"name": f"TTL{i}", "value": i * 100} for i in range(10)
        ]
        ttls = [5 + (i % 5) for i in range(10)]  # TTLs between 5-10 seconds

        keys_ttl, _ = time_operation(db.put_batch, ttl_batch, ttls=ttls, performance_summary=performance_summary)

        # Verify TTL items were inserted
        for i, key in enumerate(keys_ttl):
            data = db.get(key)
            assert data["name"] == f"TTL{i}", f"TTL item {i} name incorrect"
            assert data["value"] == i * 100, f"TTL item {i} value incorrect"

    finally:
        del db

@measure_time
def test_query_operators(performance_summary, db):
    """Test query operators"""
    try:
        # Store test data
        test_data = [
            {"name": "John", "age": 30, "tags": ["user"], "profile": {"level": 1, "active": True}},
            {"name": "Jane", "age": 25, "tags": ["user", "premium"], "profile": {"level": 2, "active": True}},
            {"name": "Bob", "age": 35, "tags": ["admin"], "profile": {"level": 3, "active": False}},
            {"name": "Alice", "age": 28, "tags": ["user", "premium"], "profile": {"level": 2, "active": True}},
            {"name": "Dave", "age": 42, "tags": ["admin", "super"], "profile": {"level": 4, "active": True}},
        ]

        # Measure put operations
        keys = []
        for data in test_data:
            result, _ = time_operation(db.put, data, performance_summary=performance_summary)
            keys.append(result)

        # Test various query operators with timing
        query_tests = [
            ("$eq - Simple equality", {"name": "John"}),
            ("$eq - Explicit operator", {"name": {"$eq": "John"}}),
            ("$gt - Greater than", {"age": {"$gt": 30}}),
            ("$gte - Greater than or equal", {"age": {"$gte": 30}}),
            ("$lt - Less than", {"age": {"$lt": 30}}),
            ("$lte - Less than or equal", {"age": {"$lte": 30}}),
            ("$in - Value in array", {"name": {"$in": ["John", "Jane"]}}),
            ("$ne - Not equal", {"name": {"$ne": "John"}}),
            ("$exists - Field exists", {"profile": {"$exists": True}}),
            ("$contains - Array contains", {"tags": {"$contains": "admin"}}),
            ("Nested field query", {"profile.level": {"$gt": 2}}),
            ("Nested field simple", {"profile.active": True}),
            ("Multiple conditions", {"age": {"$gt": 25}, "profile.active": True}),
            ("Tag query", {"tags": "premium"}),
            ("Query with limit", {"age": {"$gt": 0}, "$limit": 2}),
        ]

        for op_name, query_dict in query_tests:
            result, _ = time_operation(db.query, query_dict, performance_summary=performance_summary)
            
            if not isinstance(result, list):
                result = list(result)

            # Add specific assertions for certain queries
            if op_name == "$eq - Simple equality":
                assert len(result) == 1 and result[0]["name"] == "John", "Simple equality query failed"
            elif op_name == "$gt - Greater than":
                assert all(doc["age"] > 30 for doc in result), "Greater than query failed"
            elif op_name == "Query with limit":
                assert len(result) <= 2, "Limit query failed"
            elif op_name == "Tag query":
                assert all("premium" in doc.get("_tags", []) for doc in result), "Tag query failed"

        # Clean up
        for key in keys:
            db.delete(key)

    finally:
        del db

@measure_time
def test_large_batch_operations(performance_summary, db):
    """Test large batch operations with various data types and sizes"""
    try:
        # Generate smaller batch of varied data to avoid memory issues
        large_batch = []
        for i in range(20):  # Reduced from 50 to 20 items
            item = {
                "id": i,
                "name": f"Item{i}",
                "value": i * 10,
                "tags": ["batch", "large"] + (["premium"] if i % 3 == 0 else []),
                "metadata": {
                    "created": time.time(),
                    "version": f"1.{i}",
                    "flags": [f"flag{j}" for j in range(i % 3)],  # Reduced array size
                    "active": i % 2 == 0
                },
                "scores": [j * 10 for j in range(i % 5)],  # Reduced array size
                "description": "x" * (i * 5)  # Reduced string size
            }
            large_batch.append(item)

        # Test large batch put
        keys, _ = time_operation(db.put_batch, large_batch, performance_summary=performance_summary)

        # Verify data integrity
        for i, key in enumerate(keys):
            data = db.get(key)
            assert data["id"] == i, f"Item {i} id mismatch"
            assert data["name"] == f"Item{i}", f"Item {i} name mismatch"
            assert len(data["tags"]) >= 2, f"Item {i} missing base tags"

        # Test batch operations with TTLs
        ttl_batch = [
            {"name": f"TTL{i}", "value": i * 100} for i in range(10)
        ]
        ttls = [5 + (i % 5) for i in range(10)]  # TTLs between 5-10 seconds

        keys_ttl, _ = time_operation(db.put_batch, ttl_batch, ttls=ttls, performance_summary=performance_summary)

        # Test batch delete with partial keys
        deleted, _ = time_operation(db.delete_batch, keys[::2], performance_summary=performance_summary)

        # Verify partial deletion
        for i, key in enumerate(keys):
            data = db.get(key)
            if i % 2 == 0:
                assert data is None, f"Item {i} should be deleted"
            else:
                assert data is not None, f"Item {i} should still exist"

    finally:
        del db

@measure_time
def test_advanced_querying(performance_summary, db):
    """Test advanced query patterns and combinations"""
    try:
        # Generate smaller test data
        test_data = []
        for i in range(5):  # Reduced from 10 to 5 items
            item = {
                "id": i,
                "name": f"User{i}",
                "age": 20 + (i % 20),
                "tags": ["user"] + (["premium"] if i % 3 == 0 else []),
                "profile": {
                    "level": 1 + (i % 3),
                    "active": i % 2 == 0
                },
                "metadata": {
                    "status": "active" if i % 2 == 0 else "inactive"
                }
            }
            test_data.append(item)

        # Store test data
        keys = []
        for i, data in enumerate(test_data):
            result, _ = time_operation(db.put, data, performance_summary=performance_summary)
            keys.append(result)

        # Test simpler query patterns
        complex_queries = [
            ("Simple equality", {"name": "User0"}),
            ("Numeric comparison", {"age": {"$gt": 25}}),
            ("Tag query", {"tags": "premium"}),
            ("Nested field", {"profile.active": True}),
            ("Multiple conditions", {
                "age": {"$gt": 20},
                "profile.level": {"$gt": 1}
            })
        ]

        for i, (query_name, query_dict) in enumerate(complex_queries):
            result, _ = time_operation(db.query, query_dict, performance_summary=performance_summary)
            
            if not isinstance(result, list):
                result = list(result)
            
            # Add specific assertions for certain queries
            if "Simple equality" in query_name:
                assert len(result) == 1 and result[0]["name"] == "User0", "Simple equality query failed"
            elif "Numeric comparison" in query_name:
                assert all(doc["age"] > 25 for doc in result), "Age comparison failed"
            elif "Tag query" in query_name:
                assert all("premium" in doc["tags"] for doc in result), "Tag query failed"

        # Clean up
        for key in keys:
            db.delete(key)

    finally:
        del db
        gc.collect()

def format_memory_size(bytes_value):
    """Convert bytes to human readable format (KB/MB)"""
    if bytes_value is None:
        return "N/A"
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value/1024:.1f} KB"
    else:
        return f"{bytes_value/(1024*1024):.1f} MB"

def run_tests(db):
    """Run all tests with specified DB instance"""
    # Determine storage type for reporting
    storage_type = "memory" if getattr(db, 'in_memory', False) else "file"
    print(f"\nRunning tests with {storage_type} storage...")

    # Initialize memory tracking
    initial_memory = {
        "total": gc.mem_free() + gc.mem_alloc(),
        "used": gc.mem_alloc(),
        "free": gc.mem_free()
    }

    performance_summary = {
        "put": {
            "total_time": 0,
            "total_ops": 0,
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "memory_used": 0,
            "peak_memory": 0
        },
        "get": {
            "total_time": 0,
            "total_ops": 0,
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "memory_used": 0,
            "peak_memory": 0
        },
        "delete": {
            "total_time": 0,
            "total_ops": 0,
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "memory_used": 0,
            "peak_memory": 0
        },
        "batch_put": {
            "total_time": 0,
            "total_ops": 0,
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "total_items": 0,
            "avg_items_per_batch": 0,
            "memory_used": 0,
            "peak_memory": 0
        },
        "batch_delete": {
            "total_time": 0,
            "total_ops": 0,
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "total_items": 0,
            "avg_items_per_batch": 0,
            "memory_used": 0,
            "peak_memory": 0
        },
        "query": {
            "total_time": 0,
            "total_ops": 0,
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "result_counts": [],
            "memory_used": 0,
            "peak_memory": 0
        }
    }

    try:
        total_start_time = time.ticks_ms()
        peak_memory_used = 0

        def run_test_with_perf(test_func, db):
            nonlocal peak_memory_used
            test_func(performance_summary, db)
            gc.collect()
            # Update peak memory after each test
            current_memory = gc.mem_alloc()
            peak_memory_used = max(peak_memory_used, current_memory)

        # Run tests
        run_test_with_perf(test_basic_operations, db)
        run_test_with_perf(test_ttl, db)
        run_test_with_perf(test_batch_operations, db)
        run_test_with_perf(test_query_operators, db)
        run_test_with_perf(test_large_batch_operations, db)
        run_test_with_perf(test_advanced_querying, db)

        total_end_time = time.ticks_ms()
        total_test_time = time.ticks_diff(total_end_time, total_start_time) / 1000  # Convert to seconds

        # Calculate final memory stats
        final_memory = {
            "total": gc.mem_free() + gc.mem_alloc(),
            "used": gc.mem_alloc(),
            "free": gc.mem_free()
        }

        # Print performance summary
        print(f"\n{'=' * 80}")
        print(f"PERFORMANCE SUMMARY FOR {storage_type.upper()} STORAGE")
        print(f"{'=' * 80}")

        print("\nMEMORY USAGE SUMMARY:")
        print(f"{'Metric':<20} {'Initial':<15} {'Final':<15} {'Change':<15}")
        print("-" * 65)
        print(f"{'Total Memory':<20} {format_memory_size(initial_memory['total']):<15} {format_memory_size(final_memory['total']):<15} {format_memory_size(final_memory['total'] - initial_memory['total']):<15}")
        print(f"{'Used Memory':<20} {format_memory_size(initial_memory['used']):<15} {format_memory_size(final_memory['used']):<15} {format_memory_size(final_memory['used'] - initial_memory['used']):<15}")
        print(f"{'Free Memory':<20} {format_memory_size(initial_memory['free']):<15} {format_memory_size(final_memory['free']):<15} {format_memory_size(final_memory['free'] - initial_memory['free']):<15}")
        print(f"{'Peak Memory Used':<20} {'N/A':<15} {format_memory_size(peak_memory_used):<15} {format_memory_size(peak_memory_used - initial_memory['used']):<15}")

        print("\nBASIC OPERATION METRICS:")
        print(f"{'Operation':<15} {'Total Ops':<15} {'Total Time(ms)':<15} {'Avg Time(ms)':<15} {'Min Time(ms)':<15} {'Max Time(ms)':<15} {'Memory Used':<15}")
        print("-" * 105)

        for op, metrics in performance_summary.items():
            min_time = metrics['min_time'] if metrics['min_time'] != float('inf') else 0
            max_time = metrics['max_time']
            avg_time = metrics['avg_time'] if metrics['total_ops'] > 0 else 0
            memory_used = metrics.get('memory_used', 0)
            print(f"{op:<15} {metrics['total_ops']:<15} {metrics['total_time']:<15} {avg_time:<15} {min_time:<15} {max_time:<15} {format_memory_size(memory_used):<15}")

        print("\nSUCCESS RATE METRICS:")
        print(f"{'Operation':<15} {'Success Count':<15} {'Failure Count':<15} {'Success Rate(%)':<15}")
        print("-" * 60)

        for op, metrics in performance_summary.items():
            success_count = metrics.get('success_count', 0)
            failure_count = metrics.get('failure_count', 0)
            total = success_count + failure_count
            success_rate = (success_count / total * 100) if total > 0 else 0
            print(f"{op:<15} {success_count:<15} {failure_count:<15} {success_rate:<15.2f}")

        if performance_summary['batch_put']['total_ops'] > 0 or performance_summary['batch_delete']['total_ops'] > 0:
            print("\nBATCH OPERATION METRICS:")
            print(f"{'Operation':<15} {'Total Batches':<20} {'Total Items':<20} {'Avg Items/Batch':<20} {'Memory Used':<15}")
            print("-" * 90)

            for op in ['batch_put', 'batch_delete']:
                metrics = performance_summary[op]
                total_batches = metrics['total_ops']
                total_items = metrics.get('total_items', 0)
                avg_items = metrics.get('avg_items_per_batch', 0)
                memory_used = metrics.get('memory_used', 0)
                print(f"{op:<15} {total_batches:<20} {total_items:<20} {avg_items:<20.2f} {format_memory_size(memory_used):<15}")

        if performance_summary['query']['result_counts']:
            result_counts = performance_summary['query']['result_counts']
            print("\nQUERY RESULT METRICS:")
            print(f"Average results per query: {sum(result_counts) / len(result_counts) if result_counts else 0:.2f}")
            print(f"Minimum results: {min(result_counts) if result_counts else 0}")
            print(f"Maximum results: {max(result_counts) if result_counts else 0}")
            print(f"Memory used per query: {format_memory_size(performance_summary['query'].get('memory_used', 0) / len(result_counts) if result_counts else 0)}")

        print(f"\nTotal Test Execution Time: {total_test_time:.2f} seconds")
        print(f"{'=' * 80}")

        return performance_summary

    except Exception as e:
        print(f"\nTest failed: {e}")
        raise

def main():
    """Run tests for both memory and file storage"""
    print("Initializing test environment...")

    # Run file-backed tests first
    print("\nRunning with file DB...")
    with MicroTetherDB(
        filename="test.db",
        in_memory=False,
        ram_percentage=25,  # Increased from default 15% to 25%
        adaptive_threshold=True
    ) as file_db:
        file_performance = run_tests(file_db)

    # Run memory-backed tests
    print("\nRunning with in-memory DB...")
    with MicroTetherDB(
        filename="mem.db",
        in_memory=True,
        ram_percentage=25,  # Increased from default 15% to 25%
        adaptive_threshold=True
    ) as mem_db:
        memory_performance = run_tests(mem_db)

    # Compare results
    print("\n" + "=" * 80)
    print("COMPARISON OF FILE VS MEMORY STORAGE")
    print("=" * 80)

    print("\nOPERATION SPEED COMPARISON (ms):")
    print(f"{'Operation':<15} {'File Avg':<15} {'Memory Avg':<15} {'Speedup':<15}")
    print("-" * 60)

    for op, metrics in file_performance.items():
        if metrics['total_ops'] > 0 and op in memory_performance and memory_performance[op]['total_ops'] > 0:
            file_avg = metrics['avg_time']
            memory_avg = memory_performance[op]['avg_time']
            speedup = file_avg / memory_avg if memory_avg > 0 else 0
            print(f"{op:<15} {file_avg:<15.2f} {memory_avg:<15.2f} {speedup:<15.2f}")

if __name__ == "__main__":
    main()
