# TetherDB

A high-performance, embedded database for MicroPython that provides MongoDB-like querying capabilities with TTL support, batch operations, and data compression.

## Features

- **MongoDB-style querying** with operators ($eq, $gt, $gte, $lt, $lte, $in, $contains, $exists, $ne)
- **Time-to-Live (TTL)** support for automatic data expiration
- **Batch operations** for efficient bulk inserts and deletes
- **Data compression** for storage efficiency (using uzlib)
- **Adaptive flush thresholds** that automatically adjust based on workload
- **Configurable BTree parameters** for performance tuning
- **Delayed flushing** to reduce disk I/O operations
- **Thread-safe operations** with queue-based processing
- **Efficient memory usage** with streaming query processing
- **Automatic cleanup** of expired entries
- **Tag-based organization** for easier data categorization and retrieval

## Installation

1. Copy the `TetherDB.py` file to your MicroPython project
2. Import the module:
```python
from tendrl.lib.tetherdb.TetherDB import DB
```

## Basic Usage

### Creating a Database

```python
from tendrl.lib.tetherdb.TetherDB import DB

# Create a database with default settings
db = DB("my_database.db")

# Create a database with custom settings
db = DB(
    "my_database.db",
    flush_threshold=20,              # Number of operations before auto-flushing
    auto_flush_seconds=5,            # Seconds between auto-flushes
    btree_cachesize=128,             # BTree cache size
    btree_pagesize=1024,             # BTree page size
    use_compression=True,            # Enable data compression
    compress_min_size=256,           # Minimum size for compression
    adaptive_threshold=True          # Adjust flush threshold based on workload
)
```

### Basic Operations

```python
# Store data with auto-generated key
key = db.put({"name": "John", "age": 30})
print(f"Stored data with auto-generated key: {key}")

# Store data with a custom ID
custom_key = db.put({"name": "Jane", "age": 25}, _id="user_jane")
print(f"Stored data with custom ID: {custom_key}")  # Will be "user_jane"

# Store data with TTL and custom ID
key_with_ttl = db.put({"name": "Temporary"}, ttl=10, _id="temp_user")
print(f"Stored temporary data with custom ID: {key_with_ttl}")

# Retrieve data
data = db.get(custom_key)
print(f"Retrieved data: {data}")  # {'name': 'Jane', 'age': 25}

# Delete data
deleted_count = db.delete(custom_key)
print(f"Deleted {deleted_count} items")  # Deleted 1 items
```

#### Custom ID Considerations

- If you provide an `_id`, it must be unique. Attempting to store a document with an existing `_id` will raise a `ValueError`.
- Custom IDs can be any string, but they should be unique within the database.
- If no `_id` is provided, the database will automatically generate a unique key.
- Custom IDs can be useful for maintaining consistent references or migrating data between databases.

### Query Operations

```python
# Insert some test data
db.put({"name": "John", "age": 30, "tags": ["admin"]})
db.put({"name": "Jane", "age": 25, "tags": ["user"]})
db.put({"name": "Bob", "age": 35, "tags": ["user", "premium"]})

# Simple equality query
results = db.query({"name": "John"})
print(results)  # [{'name': 'John', 'age': 30, 'tags': ['admin']}]

# Query with operators
results = db.query({"age": {"$gt": 25}})
print(results)  # [{'name': 'John', 'age': 30, ...}, {'name': 'Bob', 'age': 35, ...}]

# Combined queries
results = db.query({"age": {"$gte": 25, "$lt": 35}, "tags": {"$contains": "user"}})
print(results)  # [{'name': 'Jane', 'age': 25, 'tags': ['user']}]
```

## Batch Operations

Batch operations significantly improve performance when inserting or deleting multiple items.

```python
# Create batch data
items = [
    {"id": 1, "name": "Item 1"},
    {"id": 2, "name": "Item 2"},
    {"id": 3, "name": "Item 3"},
    # ...more items
]

# Insert batch (5-10x faster than individual inserts)
keys = db.put_batch(items)
print(f"Inserted {len(keys)} items")

# Delete batch (2-4x faster than individual deletes)
deleted_count = db.delete_batch(keys[:50])  # Delete first 50 items
print(f"Deleted {deleted_count} items")
```

## Query Operators

TetherDB supports MongoDB-style query operators:

```python
# Equality (both forms are equivalent)
db.query({"name": "John"})
db.query({"name": {"$eq": "John"}})

# Greater than
db.query({"age": {"$gt": 25}})

# Greater than or equal
db.query({"age": {"$gte": 30}})

# Less than
db.query({"age": {"$lt": 30}})

# Less than or equal
db.query({"age": {"$lte": 30}})

# In list
db.query({"name": {"$in": ["John", "Jane"]}})

# Contains (works for both lists and strings)
db.query({"tags": {"$contains": "admin"}})
db.query({"name": {"$contains": "oh"}})  # Matches "John"

# Exists (check if field exists)
db.query({"email": {"$exists": True}})

# Not equal
db.query({"name": {"$ne": "John"}})
```

## Tags

TetherDB supports tagging data for easier organization and retrieval. Tags can be added either as a dedicated parameter or as a regular field in your data.

### Using the Tags Parameter

```python
# Store data with tags as a parameter
key = db.put({"name": "John", "age": 30}, tags=["user", "active", "premium"])

# Tags are stored in the "_tags" field within the document
data = db.get(key)
print(data)  # {'name': 'John', 'age': 30, '_tags': ['user', 'active', 'premium']}
```

### Querying by Tags

```python
# Find all documents with a specific tag
results = db.query({"_tags": {"$contains": "active"}})

# Find documents with multiple tags
results = db.query({"_tags": {"$contains": "premium"}})

# Combine tag queries with other conditions
results = db.query({
    "_tags": {"$contains": "user"},
    "age": {"$gt": 25}
})
```

### Tags Best Practices

1. **Tag Consistency**: Use consistent tag naming conventions
   ```python
   # GOOD: Consistent tag naming
   db.put({"name": "User1"}, tags=["role:admin", "status:active"])
   db.put({"name": "User2"}, tags=["role:user", "status:inactive"])
   
   # Query by consistent tag patterns
   admins = db.query({"_tags": {"$contains": "role:admin"}})
   ```

2. **Selective Tagging**: Only tag with useful categorizations
   ```python
   # Selective tagging for important categories
   db.put({"sensor": "temp-1", "value": 22.5}, tags=["type:temperature", "location:outside"])
   db.put({"sensor": "hum-1", "value": 65}, tags=["type:humidity", "location:inside"])
   ```

3. **Direct Field vs Tags**: For frequently queried properties, consider using direct fields instead of tags
   ```python
   # BETTER: Direct fields for commonly queried properties
   db.put({
       "name": "Sensor1",
       "type": "temperature",  # Direct field instead of tag
       "location": "outside"   # Direct field instead of tag
   })
   
   # Query using direct fields
   outdoor_sensors = db.query({"location": "outside"})
   ```

4. **Tag Limitations**: Don't use tags for complex relationships or hierarchical data
   ```python
   # NOT RECOMMENDED: Complex hierarchies in tags
   db.put({"name": "Document1"}, tags=["folder:project/docs/2023/q1"])
   
   # BETTER: Use structured fields
   db.put({
       "name": "Document1",
       "folder": {
           "project": "main",
           "category": "docs",
           "year": 2023,
           "quarter": 1
       }
   })
   ```

## TTL (Time-to-Live)

Time-to-Live automatically removes data after a specified time period:

```python
# Store data that expires in 60 seconds
key = db.put({"name": "Temporary"}, ttl=60)

# Data will be automatically removed after 60 seconds
# You can force cleanup immediately with:
db.cleanup()
```

## Auto Cleanup Mechanism

TetherDB handles expired data using two cleanup mechanisms:

1. **Automatic Cleanup**: A background worker automatically scans for and removes expired keys every 60 seconds
2. **Manual Cleanup**: The `cleanup()` method forces an immediate cleanup when called

Here's how the automatic cleanup process works:

```python
# The database continuously cleans up expired keys without user intervention
db = DB("my_database.db")

# Store data with TTL (will be auto-removed after 30 seconds)
key = db.put({"temporary": True}, ttl=30)

# The background worker will automatically remove this key after expiration
# You don't need to do anything - it's handled for you!

# For immediate cleanup, you can still call:
deleted_count = db.cleanup()
print(f"Manually removed {deleted_count} expired items")
```

When the database is initialized, it also performs an initial cleanup to remove any expired keys from previous sessions. The cleanup process only removes keys that have actually expired, leaving unexpired and never-expiring keys (TTL=0) untouched.

The automatic cleanup ensures your database doesn't accumulate stale data, even if you never explicitly call the cleanup method.

## Simple Benchmark Results

These benchmark results were measured on a typical MicroPython environment and give an approximation of expected performance:

### Basic Operations
- **Put**: ~12-15ms per item
- **Get**: ~10-12ms per item
- **Delete**: ~10-12ms per item
- **Query**: ~30ms for simple queries

### Batch Performance Improvements
- **Batch Put**: 1.5-2× faster than individual puts
- **Batch Delete**: 1.2-1.5× faster than individual deletes

### Bulk Operations (100 items)
- **Regular Put (100 items)**: ~5-6 seconds
- **Batch Put (100 items)**: ~3-4 seconds
- **Regular Delete (100 items)**: ~5-6 seconds
- **Batch Delete (100 items)**: ~4-5 seconds

Performance will vary based on hardware, database size, and configuration settings. The batch operations show significant performance benefits, especially for larger datasets. These gains come from reducing overhead, minimizing disk I/O, and optimizing memory usage.

## Advanced Configuration

### Optimizing for Different Workloads

```python
# For read-heavy workloads:
db = DB(
    "read_optimized.db",
    btree_cachesize=256,     # Larger cache improves read performance
    btree_pagesize=2048      # Larger pages reduce tree height
)

# For write-heavy workloads:
db = DB(
    "write_optimized.db",
    flush_threshold=50,      # Flush less frequently
    auto_flush_seconds=10    # More time between flushes
)

# For memory-constrained devices:
db = DB(
    "memory_constrained.db",
    btree_cachesize=64,      # Smaller cache uses less RAM
    btree_pagesize=512,      # Smaller pages use less RAM
    use_compression=True     # Compression reduces memory usage
)

# For large datasets:
db = DB(
    "large_dataset.db",
    btree_cachesize=512,     # Larger cache for more data
    btree_pagesize=4096,     # Larger pages for better handling of large datasets
    use_compression=True,    # Compress to save space
    compress_min_size=128    # Compress more data
)
```

### Compression Settings

Compression reduces storage requirements but adds CPU overhead:

```python
# Enable compression for all data larger than 128 bytes
db = DB("compressed.db", use_compression=True, compress_min_size=128)

# Only compress data larger than 512 bytes (better performance, less compression)
db = DB("selectively_compressed.db", use_compression=True, compress_min_size=512)

# Disable compression (fastest, but uses more storage)
db = DB("uncompressed.db", use_compression=False)
```

## Best Practices

### Memory Management

```python
# Explicitly clean up resources when done
db = DB("temp.db")
try:
    # Use the database
    data = db.get(some_key)
finally:
    # Clean up
    del db
    # Force garbage collection on memory-constrained devices
    import gc
    gc.collect()
```

### Batch Processing

```python
# GOOD: Use batch operations for bulk data
items = [{"id": i, "data": f"Value {i}"} for i in range(100)]
keys = db.put_batch(items)

# BAD: Don't use loops for bulk operations
keys = []
for i in range(100):
    key = db.put({"id": i, "data": f"Value {i}"})
    keys.append(key)
```

### Query Optimization

```python
# GOOD: Use specific queries
results = db.query({"type": "sensor", "value": {"$gt": 50}})

# BAD: Don't filter in-memory when you can use query operators
all_sensors = db.query({"type": "sensor"})
high_value_sensors = [s for s in all_sensors if s.get("value", 0) > 50]
```

### Context Managers

```python
# Use context managers for automatic cleanup
with DB("context_test.db") as db:
    key = db.put({"test": "data"})
    data = db.get(key)
# Database is automatically cleaned up when exiting context
```

## Performance Optimization Tips

1. **Use batch operations** for bulk inserts and deletes (5-10x faster)
2. **Adjust BTree parameters** based on workload:
   - Higher `btree_cachesize` for better read performance
   - Higher `btree_pagesize` for larger datasets
3. **Configure flush thresholds** appropriately:
   - Higher thresholds improve write throughput
   - Lower thresholds reduce memory usage
4. **Use selective compression**:
   - Enable compression for storage-constrained devices
   - Increase `compress_min_size` if CPU is limited
5. **Structure your data** to optimize queries:
   - Keep document size small (< 1KB)
   - Use flat structures where possible
   - Use consistent field names for better query performance

## Error Handling

```python
try:
    # Attempt to store overly large data
    key = db.put({"huge_field": "x" * 2000})
except ValueError as e:
    print(f"Error: {e}")  # Data too large

# Handle missing keys gracefully
key = "nonexistent_key"
data = db.get(key)
if data is None:
    print(f"No data found for key: {key}")
```

## Limitations

- Maximum data size per entry: 1KB
- No support for complex queries or aggregation
- No support for indexes
- No support for transactions
- No support for concurrent database access from multiple processes

## License

Copyright (c) 2025 Hunter McGuire (tendrl, inc.)
All rights reserved. Unauthorized copying, distribution, modification, or usage of this code, via any medium, is strictly prohibited without express permission from the author.
