import gc
import os
import time
import asyncio
from tendrl.lib.microtetherdb.MicroTetherDB import MicroTetherDB

def measure_time(func):
    """Decorator to measure execution time in milliseconds"""
    def wrapper(*args, **kwargs):
        start = time.ticks_ms()
        result = func(*args, **kwargs)
        end = time.ticks_ms()
        duration = time.ticks_diff(end, start)
        print(f"{func.__name__} took {duration}ms")
        return result
    return wrapper

def time_operation(operation, *args, performance_summary=None, **kwargs):
    """Helper function to measure individual operation time in milliseconds"""
    print(f"\n--- DEBUG: time_operation called ---")
    print(f"Operation name: {operation.__name__}")
    print(f"Positional args: {args}")
    print(f"Keyword args: {kwargs}")

    start = time.ticks_ms()
    result = None
    success = False
    
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
        
        # Track batch operation details
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
        print(f"Error in {op_name} operation: {e}")
        success = False
        raise

    end = time.ticks_ms()
    duration = time.ticks_diff(end, start)
    
    # Track performance metrics
    if performance_summary is not None and metric_category in performance_summary:
        # Update basic metrics
        performance_summary[metric_category]['total_time'] += duration
        performance_summary[metric_category]['total_ops'] += 1
        performance_summary[metric_category]['avg_time'] = (
            performance_summary[metric_category]['total_time'] / 
            performance_summary[metric_category]['total_ops']
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
            
        print(f"Updated performance metrics for {metric_category}: ops={performance_summary[metric_category]['total_ops']}, time={performance_summary[metric_category]['total_time']}")
    
    return result, duration

@measure_time
def test_basic_operations(performance_summary, use_memory=False):
    """Test basic put/get operations"""
    print("\nTesting basic operations...")

    # Clean up any existing test file
    if not use_memory:
        try:
            os.unlink("test.db")
        except:
            pass

    db = MicroTetherDB(":memory:" if use_memory else "test.db")
    try:
        # Test put
        print("\nTesting put operation...")
        result, put_time = time_operation(db.put, {"name": "John", "age": 30}, performance_summary=performance_summary)
        print(f"Put operation took {put_time}ms")
        print(f"Put key: {result}")

        # Ensure key is not None
        if result is None:
            raise ValueError("Put operation failed to return a key")

        key = result  # Store the key for later use

        # Test get
        print("\nTesting get operation...")
        result, get_time = time_operation(db.get, key, performance_summary=performance_summary)
        print(f"Get operation took {get_time}ms")
        print(f"Get data: {result}")

        # Ensure result is not None and has expected content
        if result is None:
            raise ValueError(f"Failed to retrieve data for key {key}")

        assert result["name"] == "John" and result["age"] == 30, "Get data mismatch"

        # Test delete
        print("\nTesting delete operation...")
        result, delete_time = time_operation(db.delete, key, performance_summary=performance_summary)
        print(f"Delete operation took {delete_time}ms")
        print(f"Delete count: {result}")
        assert result == 1, "Delete count mismatch"

        # Verify deletion
        print("\nVerifying deletion...")
        result, verify_time = time_operation(db.get, key, performance_summary=performance_summary)
        print(f"Verify operation took {verify_time}ms")
        print(f"Get after delete: {result}")
        assert result is None, "Data still exists after delete"

        print("\nOperation timing summary:")
        print(f"Put: {put_time}ms")
        print(f"Get: {get_time}ms")
        print(f"Delete: {delete_time}ms")
        print(f"Verify: {verify_time}ms")
    finally:
        del db

@measure_time
def test_ttl(performance_summary, use_memory=False):
    """Test TTL functionality"""
    print("\nTesting TTL...")

    db = MicroTetherDB(":memory:" if use_memory else "test.db")
    try:
        # Store data with 5 second TTL
        result, put_time = time_operation(db.put, {"name": "John"}, ttl=5, performance_summary=performance_summary)
        print(f"Put operation took {put_time}ms")
        print(f"Put with TTL key: {result}")

        # Verify data exists
        data, get_time = time_operation(db.get, result, performance_summary=performance_summary)
        print(f"Get operation took {get_time}ms")
        print(f"Get before TTL: {data}")
        assert data is not None, "Data not found before TTL"

        # Wait for TTL to expire
        time.sleep(6)

        # Force cleanup to ensure expired keys are removed
        cleanup_start = time.ticks_ms()
        deleted = db.cleanup()
        cleanup_time = time.ticks_diff(time.ticks_ms(), cleanup_start)
        print(f"Cleanup operation took {cleanup_time}ms")
        print(f"Deleted {deleted} expired keys")

        # Verify data is gone
        data, verify_time = time_operation(db.get, result, performance_summary=performance_summary)
        print(f"Verify operation took {verify_time}ms")
        print(f"Get after TTL: {data}")
        assert data is None, "Data still exists after TTL"

        print("\nOperation timing summary:")
        print(f"Put: {put_time}ms")
        print(f"Get: {get_time}ms")
        print(f"Cleanup: {cleanup_time}ms")
        print(f"Verify: {verify_time}ms")
    finally:
        del db

@measure_time
def test_batch_operations(performance_summary, use_memory=False):
    """Test batch operations"""
    print("\nTesting batch operations...")

    db = MicroTetherDB(":memory:" if use_memory else "test.db")
    try:
        # Test batch put
        batch_items = [
            {"name": "Item1", "value": 10},
            {"name": "Item2", "value": 20},
            {"name": "Item3", "value": 30},
        ]

        print("Testing put_batch operation...")
        keys, put_time = time_operation(db.put_batch, batch_items, performance_summary=performance_summary)
        print(f"Batch put operation took {put_time}ms")
        print(f"Inserted {len(keys)} items with keys: {keys}")
        assert len(keys) == 3, "Should insert 3 items"

        # Verify the data was inserted correctly
        for i, key in enumerate(keys):
            data = db.get(key)
            print(f"Retrieved item {i + 1}: {data}")
            assert data["name"] == f"Item{i + 1}", f"Item {i + 1} name incorrect"
            assert data["value"] == (i + 1) * 10, f"Item {i + 1} value incorrect"

        # Test batch delete
        print("Testing delete_batch operation...")
        deleted, delete_time = time_operation(db.delete_batch, keys[:2], performance_summary=performance_summary)
        print(f"Batch delete operation took {delete_time}ms")
        print(f"Deleted {deleted} items")
        assert deleted == 2, "Should delete 2 items"

        # Verify deletion
        assert db.get(keys[0]) is None, "First item should be deleted"
        assert db.get(keys[1]) is None, "Second item should be deleted"
        assert db.get(keys[2]) is not None, "Third item should still exist"

        print("Batch operations tests passed")
    finally:
        del db

@measure_time
def test_query_operators(performance_summary, use_memory=False):
    """Test query operators"""
    print("\nTesting query operators...")

    db = MicroTetherDB(":memory:" if use_memory else "test.db")
    try:
        # Store test data
        test_data = [
            {"name": "John", "age": 30, "tags": ["user"]},
            {"name": "Jane", "age": 25, "tags": ["user"]},
            {"name": "Bob", "age": 35, "tags": ["admin"]},
        ]

        # Measure put operations
        keys = []
        put_times = []
        for data in test_data:
            try:
                result, put_time = time_operation(db.put, data, performance_summary=performance_summary)
                keys.append(result)
                put_times.append(put_time)
                print(f"Successfully put data: {data}")
            except Exception as e:
                print(f"Error putting data: {e}")
                put_time = 0
                put_times.append(put_time)
        print(f"Average put time: {sum(put_times) / len(put_times)}ms")

        # Test various query operators with timing
        query_tests = [
            ("$eq", {"name": "John"}),
            ("$gt", {"age": {"$gt": 30}}),
            ("$in", {"name": {"$in": ["John", "Jane"]}}),
            ("$contains", {"tags": {"$contains": "admin"}}),
            ("$exists", {"tags": {"$exists": True}}),
            ("$ne", {"name": {"$ne": "John"}}),
        ]

        print("\nQuery operator timing:")
        for op_name, query_dict in query_tests:
            try:
                print(f"\nExecuting {op_name} query with: {query_dict}")
                result, query_time = time_operation(db.query, query_dict, performance_summary=performance_summary)
                print(f"{op_name} query took {query_time}ms")
                
                if not isinstance(result, list):
                    result = list(result)
                    
                print(f"{op_name} results: {result}")
            except Exception as e:
                print(f"Error executing {op_name} query: {e}")
                print(f"Query that caused error: {query_dict}")

        # Clean up
        for key in keys:
            db.delete(key)

    finally:
        del db

def run_tests(use_memory=False):
    """Run all tests with specified storage type"""
    storage_type = "memory" if use_memory else "file"
    print(f"\nRunning tests with {storage_type} storage...")
    
    performance_summary = {
        "put": {
            "total_time": 0, 
            "total_ops": 0, 
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0
        },
        "get": {
            "total_time": 0, 
            "total_ops": 0, 
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0
        },
        "delete": {
            "total_time": 0, 
            "total_ops": 0, 
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0
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
            "avg_items_per_batch": 0
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
            "avg_items_per_batch": 0
        },
        "query": {
            "total_time": 0, 
            "total_ops": 0, 
            "avg_time": 0,
            "success_count": 0,
            "failure_count": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "result_counts": []
        }
    }

    try:
        print(f"Starting tests with {storage_type} storage...")
        total_start_time = time.time()

        def run_test_with_perf(test_func):
            test_func(performance_summary, use_memory)
            gc.collect()

        # Run tests
        run_test_with_perf(test_basic_operations)
        run_test_with_perf(test_ttl)
        run_test_with_perf(test_batch_operations)
        run_test_with_perf(test_query_operators)

        total_end_time = time.time()
        total_test_time = total_end_time - total_start_time

        # Print performance summary
        print(f"\n{'=' * 80}")
        print(f"PERFORMANCE SUMMARY FOR {storage_type.upper()} STORAGE")
        print(f"{'=' * 80}")
        
        print("\nBASIC OPERATION METRICS:")
        print("{:<15} {:<15} {:<15} {:<15} {:<15} {:<15}".format(
            "Operation", "Total Ops", "Total Time(ms)", "Avg Time(ms)", "Min Time(ms)", "Max Time(ms)"))
        print("-" * 90)
        
        for op, metrics in performance_summary.items():
            min_time = metrics['min_time'] if metrics['min_time'] != float('inf') else 0
            max_time = metrics['max_time']
            print("{:<15} {:<15} {:<15.2f} {:<15.2f} {:<15.2f} {:<15.2f}".format(
                op, 
                metrics['total_ops'], 
                metrics['total_time'], 
                metrics['avg_time'] if metrics['total_ops'] > 0 else 0,
                min_time,
                max_time
            ))
        
        print("\nSUCCESS RATE METRICS:")
        print("{:<15} {:<15} {:<15} {:<15}".format(
            "Operation", "Success Count", "Failure Count", "Success Rate(%)"))
        print("-" * 60)
        
        for op, metrics in performance_summary.items():
            success_count = metrics.get('success_count', 0)
            failure_count = metrics.get('failure_count', 0)
            total = success_count + failure_count
            success_rate = (success_count / total * 100) if total > 0 else 0
            print("{:<15} {:<15} {:<15} {:<15.2f}".format(
                op, success_count, failure_count, success_rate))
        
        if performance_summary['batch_put']['total_ops'] > 0 or performance_summary['batch_delete']['total_ops'] > 0:
            print("\nBATCH OPERATION METRICS:")
            print("{:<15} {:<20} {:<20} {:<20}".format(
                "Operation", "Total Batches", "Total Items", "Avg Items/Batch"))
            print("-" * 75)
            
            for op in ['batch_put', 'batch_delete']:
                metrics = performance_summary[op]
                total_batches = metrics['total_ops']
                total_items = metrics.get('total_items', 0)
                avg_items = metrics.get('avg_items_per_batch', 0)
                print("{:<15} {:<20} {:<20} {:<20.2f}".format(
                    op, total_batches, total_items, avg_items))
        
        if performance_summary['query']['result_counts']:
            result_counts = performance_summary['query']['result_counts']
            print("\nQUERY RESULT METRICS:")
            print("Average results per query: {:.2f}".format(
                sum(result_counts) / len(result_counts) if result_counts else 0))
            print("Minimum results: {}".format(min(result_counts) if result_counts else 0))
            print("Maximum results: {}".format(max(result_counts) if result_counts else 0))
        
        print(f"\nTotal Test Execution Time: {total_test_time:.2f} seconds")
        print(f"{'=' * 80}")

        return performance_summary

    except Exception as e:
        print(f"\nTest failed: {e}")
        raise

def main():
    """Run tests for both memory and file storage"""
    print("Initializing test environment...")
    
    # Run tests with memory storage
    memory_performance = run_tests(use_memory=True)
    
    # Run tests with file storage
    file_performance = run_tests(use_memory=False)
    
    # Compare results
    print("\n" + "=" * 80)
    print("COMPARISON OF MEMORY VS FILE STORAGE")
    print("=" * 80)
    
    print("\nOPERATION SPEED COMPARISON (ms):")
    print("{:<15} {:<15} {:<15} {:<15}".format(
        "Operation", "Memory Avg", "File Avg", "Speedup"))
    print("-" * 60)
    
    for op in memory_performance.keys():
        if memory_performance[op]['total_ops'] > 0 and file_performance[op]['total_ops'] > 0:
            memory_avg = memory_performance[op]['avg_time']
            file_avg = file_performance[op]['avg_time']
            speedup = file_avg / memory_avg if memory_avg > 0 else 0
            print("{:<15} {:<15.2f} {:<15.2f} {:<15.2f}x".format(
                op, memory_avg, file_avg, speedup))

if __name__ == "__main__":
    main()
