# MicroTetherDB

A lightweight, feature-rich key-value database for MicroPython devices with support for in-memory storage (default), compression (when available), async operations, and BTree storage.

## Installation

1. Copy the `microtetherdb` directory to your MicroPython device
2. Import the database class:
```python
from microtetherdb import MicroTetherDB
```

## Usage

### Basic Operations

```python
# Create a new in-memory database with default settings (15% of free memory)
db = MicroTetherDB()

# Create a file-based database
db = MicroTetherDB(
    "my_database.db",
    in_memory=False  # explicitly set to False for file storage
)

# Create an in-memory database with custom memory allocation
db = MicroTetherDB(
    ram_percentage=25  # use 25% of available free memory
)

# Store data with optional TTL (time-to-live in seconds)
# Method 1: put(data, ttl=None, tags=None, _id=None)
db.put(
    {"name": "John", "age": 30},
    ttl=3600,  # expires in 1 hour
    tags=["user", "active"]
)

# Method 2: put(key, data, ttl=None, tags=None)
db.put(
    "user1",
    {"name": "John", "age": 30},
    ttl=3600,  # expires in 1 hour
    tags=["user", "active"]
)

# Retrieve data
value = db.get("user1")

# Delete data
db.delete("user1")

# Clear all data
db.delete(purge=True)
```

### Memory Management

The database automatically manages memory usage in several ways:

1. **Dynamic Memory Sizing**:
   - By default, uses 15% of available free memory
   - Minimum allocation: 1KB
   - Maximum allocation: 32KB
   - Automatically adjusts block size and count
   - Falls back to file-based storage if memory is insufficient

2. **Memory Optimization**:
   - Uses smaller blocks (max 256 bytes) for better memory management
   - Implements garbage collection before initialization
   - Provides memory usage information during initialization
   - Automatically reduces memory usage if needed

3. **Memory Monitoring**:
   - Prints memory information during initialization
   - Shows total and free memory
   - Reports block size and count being used
   - Shows percentage of free memory being used

Example output:
```
Memory info - Total: 131072, Free: 65536
Using 32 blocks of 256 bytes each (15% of free memory)
```

### Advanced Features

```python
# Create database with custom settings
db = MicroTetherDB(
    ram_percentage=20,         # use 20% of free memory
    use_compression=True,      # enable compression if uzlib is available
    min_compress_size=256,     # minimum size for compression
    btree_cachesize=32,        # BTree cache size
    btree_pagesize=512,        # BTree page size
    adaptive_threshold=True    # automatically adjust flush threshold
)

# Store data with tags (using key-first method)
db.put(
    "user1",
    {"name": "John", "age": 30},
    tags=["user", "active"]
)

# Query data by tags and conditions
results = db.query({
    "tags": "active",
    "age": {"$gt": 25},
    "name": {"$contains": "Jo"}
})

# Batch operations
items = [
    {"name": "John", "age": 30},
    {"name": "Jane", "age": 25}
]
keys = db.put_batch(items, ttls=[3600, 7200])  # different TTLs for each item

# Delete multiple items
deleted = db.delete_batch(keys)
```

### Async Usage

```python
import asyncio

async def main():
    async with MicroTetherDB() as db:
        # Async operations
        await db.put({"key": "value"})
        value = await db.get("key")
        
        # Batch operations
        items = [{"key1": "value1"}, {"key2": "value2"}]
        keys = await db.put_batch(items)
        
        # Complex queries
        results = await db.query({"key1": {"$exists": True}})

# Run async code
asyncio.run(main())
```

## Features

- In-memory storage by default (faster performance)
- Dynamic memory sizing based on available RAM
- Optional file-based storage
- BTree-based storage for efficient key-value operations
- Data compression (when uzlib is available)
- TTL (Time-To-Live) support
- Tag-based querying
- Complex query conditions ($gt, $lt, $in, etc.)
- Automatic cleanup of expired entries
- Thread-safe operations with async support
- Locking mechanism
- Memory efficient
- Batch operations
- Adaptive flush threshold
- Operation counting and monitoring

## Core Components

The database is modularized into several components:

- `db.py`: Main database implementation
- `core/ram_device.py`: RAM block device for in-memory storage
- `core/future.py`: Future class for async operations
- `core/exceptions.py`: Custom exceptions
- `core/compression.py`: Data compression utilities

## Query Operators

The database supports the following query operators:

- `$eq`: Equal to
- `$gt`: Greater than
- `$gte`: Greater than or equal to
- `$lt`: Less than
- `$lte`: Less than or equal to
- `$in`: Value is in array
- `$ne`: Not equal to
- `$exists`: Field exists
- `$contains`: String or array contains value

## Limitations

- Keys must be strings
- Values must be JSON serializable
- In-memory storage is lost on power cycle
- Limited by available RAM for in-memory storage
- No complex queries or indexing
- Compression requires the `uzlib` module (not available on all MicroPython devices)
- BTree module must be available
- Maximum value size is 1KB

## Best Practices

1. Use in-memory storage for temporary data or when persistence isn't needed
2. Use file-based storage when data persistence is required
3. Let the database automatically manage memory usage
4. Monitor memory usage through initialization logs
5. Set reasonable TTL values to prevent database growth
6. Use compression for larger values (if uzlib is available)
7. Regular cleanup of expired entries
8. Handle exceptions appropriately
9. Use tags for better data organization
10. Use batch operations for better performance
11. Monitor operation counts for adaptive threshold tuning

## Example

```python
from microtetherdb import MicroTetherDB

# Create in-memory database with automatic memory sizing
db = MicroTetherDB(
    ram_percentage=15,        # use 15% of free memory
    use_compression=True,     # will be disabled if uzlib is not available
    min_compress_size=256,
    adaptive_threshold=True
)

try:
    # Store user data with TTL and tags (using key-first method)
    db.put(
        "user1",
        {"name": "John", "age": 30},
        ttl=86400,  # 24 hours
        tags=["user", "active"]
    )

    # Retrieve user data
    user1 = db.get("user1")
    print(f"User 1: {user1}")

    # Query users by tag and age
    active_users = db.query({
        "tags": "active",
        "age": {"$gt": 25}
    })
    print(f"Active users over 25: {active_users}")

    # Batch operations
    users = [
        {"name": "Jane", "age": 28},
        {"name": "Bob", "age": 35}
    ]
    keys = db.put_batch(users, ttls=[3600, 7200])

    # Delete expired entries
    cleaned = db.cleanup()
    print(f"Cleaned up {cleaned} expired entries")

finally:
    # Cleanup is automatic, but you can force it
    db.cleanup()
```
