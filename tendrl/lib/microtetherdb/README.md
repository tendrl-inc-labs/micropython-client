# MicroTetherDB

A lightweight, feature-rich key-value (BTree) database for MicroPython devices with support for in-memory storage (RAM / volatile) and file-based storage (flash / persistent) with async operations and efficient TTL management.

## Installation

1. Copy the `microtetherdb` directory to your MicroPython device
2. Import the database class:

```python
from microtetherdb import MicroTetherDB
```

## Usage

### Basic Operations

```python
# Create a new in-memory database with default settings (25% of free memory)
db = MicroTetherDB()

# Create a file-based database
db = MicroTetherDB(
    "my_database.db",
    in_memory=False  # explicitly set to False for file storage
)

# Create an in-memory database with custom memory allocation
db = MicroTetherDB(
    ram_percentage=30  # use 30% of available free memory
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

### TTL (Time-To-Live) Management

The database features an efficient TTL system that automatically removes expired items:

```python
# Create database with custom TTL check frequency
db = MicroTetherDB(
    ttl_check_interval=5,    # Check for expired items every 5 seconds
    cleanup_interval=1800    # Full cleanup every 30 minutes
)

# Store data with different TTL values
db.put("session_token", {"token": "abc123"}, ttl=300)    # 5 minutes
db.put("cache_data", {"result": "cached"}, ttl=60)       # 1 minute
db.put("temp_file", {"path": "/tmp/file"}, ttl=10)       # 10 seconds

# Items are automatically removed when they expire
# No need to manually clean up expired data
```

**TTL Features:**

- **Efficient Index**: Uses a min-heap to track only items with TTLs
- **Frequent Checks**: Expired items removed every 10 seconds by default
- **No Full Scans**: Only checks items that might be expired
- **Automatic Cleanup**: No manual intervention required
- **Performance**: O(log n) insertion, O(1) expiry checking for expired items

### Query Examples

The database supports rich querying capabilities with various operators. Here are examples of different query types:

```python
# Basic equality query
results = db.query({"name": "John"})

# Numeric comparisons
results = db.query({
    "age": {"$gt": 25},           # Greater than
    "score": {"$gte": 80},        # Greater than or equal
    "temperature": {"$lt": 30},   # Less than
    "pressure": {"$lte": 1000}    # Less than or equal
})

# Multiple conditions
results = db.query({
    "age": {"$gt": 25},
    "status": "active",
    "score": {"$gte": 80}
})

# Array operations
results = db.query({
    "tags": "active",             # Array contains
    "categories": {"$in": ["electronics", "gadgets"]}  # Value in array
})

# String operations
results = db.query({
    "name": {"$contains": "Jo"},  # String contains
    "description": {"$ne": "test"}  # Not equal
})

# Field existence
results = db.query({
    "email": {"$exists": True},   # Field exists
    "phone": {"$exists": False}   # Field doesn't exist
})

# Nested field queries
results = db.query({
    "address.city": "New York",
    "settings.notifications": True
})

# Limit results
results = db.query({
    "status": "active",
    "$limit": 10  # Return only first 10 matches
})

# Complex queries with multiple operators
results = db.query({
    "age": {"$gt": 25, "$lt": 50},
    "status": {"$in": ["active", "pending"]},
    "score": {"$gte": 80},
    "name": {"$contains": "Jo"},
    "$limit": 5
})
```

### Advanced Features

```python
# Create database with custom settings
db = MicroTetherDB(
    filename="my_database.db",
    in_memory=True,               # use in-memory storage
    ram_percentage=25,            # use 25% of free memory
    max_retries=3,                # retry failed operations
    retry_delay=0.1,              # delay between retries
    lock_timeout=5.0,             # lock timeout in seconds
    cleanup_interval=3600,        # full cleanup interval in seconds
    ttl_check_interval=10,        # TTL expiry check interval in seconds
    btree_cachesize=32,           # BTree cache size
    btree_pagesize=512,           # BTree page size
    adaptive_threshold=True       # automatically adjust flush threshold
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

### Context Manager Usage

```python
# Synchronous context manager
with MicroTetherDB() as db:
    db.put({"key": "value"})
    value = db.get("key")
    
    # Batch operations
    items = [{"key1": "value1"}, {"key2": "value2"}]
    keys = db.put_batch(items)
    
    # Complex queries
    results = db.query({"key1": {"$exists": True}})

# Async context manager
import asyncio

async def main():
    async with MicroTetherDB() as db:
        # All operations are the same - the database handles async internally
        db.put({"key": "value"})
        value = db.get("key")
        results = db.query({"key": {"$exists": True}})

asyncio.run(main())
```

### Event Loop Integration

For applications that already have their own event loops, MicroTetherDB can integrate seamlessly:

```python
import asyncio
from microtetherdb import MicroTetherDB

async def user_application():
    """Your existing async application"""
    # Get your application's event loop
    loop = asyncio.get_event_loop()
    
    # Create database with your event loop
    db = MicroTetherDB(
        filename="app_data.db",
        in_memory=False,
        event_loop=loop  # Use your event loop
    )
    
    # Database operations work normally
    with db as store:
        store.put({"sensor": "temperature", "value": 25.5}, ttl=3600)
        data = store.get("sensor_key")
        results = store.query({"sensor": "temperature"})
    
    return results

async def main():
    # Your application controls the event loop
    results = await user_application()
    print(f"Results: {results}")

# Run your application
asyncio.run(main())
```

**Benefits of Event Loop Integration:**

- **No Conflicts**: Database uses your application's event loop
- **Shared Resources**: Better performance and resource utilization  
- **Application Control**: Your app remains in control of async execution
- **Seamless Integration**: Works with existing async applications

**Event Loop Handling:**

- If `event_loop` is provided, database uses it for all async operations
- If no `event_loop` is provided, database detects the current running loop
- Database creates its own loop only as a fallback
- All async operations (TTL cleanup, worker tasks) use the same loop

## Features

- In-memory storage by default (faster performance)
- Optional file-based storage for persistence
- BTree-based storage for efficient key-value operations
- **Efficient TTL (Time-To-Live) system with indexed expiry tracking**
- **Automatic background cleanup of expired items**
- Tag-based querying
- Complex query conditions ($gt, $lt, $in, etc.)
- Thread-safe operations with async support
- Locking mechanism
- Memory efficient
- Batch operations
- Adaptive flush threshold
- Operation counting and monitoring

## Competitive Advantages

MicroTetherDB fills a critical gap in the MicroPython database ecosystem by combining the best features from different approaches:

| Feature | MicroTetherDB | btree | SQLite Ports | Simple KV |
|---------|---------------|-------|---------------|-----------|
| **Memory Efficient** | ✅ Configurable | ✅ | ❌ Heavy | ✅ |
| **Automatic TTL** | ✅ **Unique** | ❌ | ❌ | ❌ |
| **Rich Queries** | ✅ **Unique** | ❌ | ✅ | ❌ |
| **Dual Storage** | ✅ **Unique** | ❌ | ❌ | ❌ |
| **Production Ready** | ✅ | ❌ | ⚠️ | ❌ |
| **Easy API** | ✅ | ❌ | ⚠️ | ✅ |

**Key Differentiators:**

- **Only MicroPython database with automatic TTL management** - perfect for IoT sensor data, caching, and session management
- **MongoDB-style queries on microcontrollers** - no other lightweight solution offers this level of querying
- **Intelligent memory management** - adapts to your device's available RAM
- **Dual storage modes** - choose between speed (in-memory) and persistence (file-based)
- **Production-ready architecture** - comprehensive error handling, async support, and extensive test coverage

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

## Constructor Parameters

```python
MicroTetherDB(
    filename="microtether.db",    # Database filename (for file storage)
    in_memory=True,               # Use in-memory storage (default: True)
    ram_percentage=25,            # Percentage of free memory to use (default: 25)
    max_retries=3,                # Maximum retries for failed operations
    retry_delay=0.1,              # Delay between retries in seconds
    lock_timeout=5.0,             # Lock timeout in seconds
    cleanup_interval=3600,        # Full cleanup interval in seconds (default: 1 hour)
    ttl_check_interval=10,        # TTL expiry check interval in seconds (default: 10s)
    btree_cachesize=32,           # BTree cache size
    btree_pagesize=512,           # BTree page size
    adaptive_threshold=True,      # Enable adaptive flush threshold
    event_loop=None               # Event loop for async operations (optional)
)
```

**Key Parameters:**

- `filename`: Database file path (only used when `in_memory=False`)
- `in_memory`: Choose between memory (fast) or file (persistent) storage
- `ram_percentage`: Memory limit as percentage of available RAM
- `ttl_check_interval`: How often to check for expired TTL items (default: 10 seconds)
- `cleanup_interval`: How often to run full database cleanup (default: 1 hour)
- `adaptive_threshold`: Automatically adjust flush frequency based on operation patterns
- `event_loop`: Optional event loop for async operations (integrates with user applications)

## Limitations

- Keys must be strings
- Values must be JSON serializable
- In-memory storage is lost on power cycle
- Limited by available RAM for in-memory storage
- No complex queries or indexing
- BTree module must be available
- Maximum value size is 8KB (after JSON serialization)

## Best Practices

1. Use in-memory storage for temporary data or when persistence isn't needed
2. Use file-based storage when data persistence is required
3. Set reasonable TTL values to prevent database growth
4. **Adjust `ttl_check_interval` based on your TTL usage patterns**
5. **Use shorter intervals (1-5s) for applications with many short-lived TTL items**
6. **Use longer intervals (30-60s) for applications with few or long-lived TTL items**
7. Regular cleanup of expired entries happens automatically
8. Handle exceptions appropriately
9. Use tags for better data organization
10. Use batch operations for better performance
11. Monitor operation counts for adaptive threshold tuning
12. The database automatically adjusts flush thresholds based on operation patterns
13. **For async applications, provide your event loop to avoid conflicts**
14. **Use context managers for proper async resource management**

## Async Best Practices

When using MicroTetherDB in async applications:

1. **Provide Your Event Loop**: Always pass your application's event loop to avoid conflicts

   ```python
   loop = asyncio.get_event_loop()
   db = MicroTetherDB(event_loop=loop)
   ```

2. **Use Context Managers**: Ensure proper resource cleanup in async contexts

   ```python
   async with MicroTetherDB(event_loop=loop) as db:
       # Database operations
       pass
   ```

3. **Shared Event Loop**: Multiple database instances can share the same event loop

   ```python
   loop = asyncio.get_event_loop()
   client_db = MicroTetherDB("client.db", event_loop=loop)
   cache_db = MicroTetherDB("cache.db", event_loop=loop)
   ```

4. **TTL in Async Apps**: Adjust TTL check intervals based on your async task frequency

   ```python
   # For apps with frequent async operations
   db = MicroTetherDB(ttl_check_interval=5, event_loop=loop)
   
   # For apps with infrequent async operations  
   db = MicroTetherDB(ttl_check_interval=30, event_loop=loop)
   ```

## Performance Characteristics

### TTL System Performance

- **Index Maintenance**: O(log n) for adding TTL items
- **Expiry Checking**: O(k) where k = number of expired items (not total items)
- **Memory Overhead**: ~24 bytes per TTL item for index entry
- **Background Processing**: Non-blocking, runs between operations
- **Cleanup Frequency**: Configurable from 1 second to hours

### When to Adjust TTL Check Interval

- **High TTL Usage**: Set to 1-5 seconds for responsive cleanup
- **Low TTL Usage**: Set to 30-60 seconds to reduce overhead
- **Battery Constrained**: Set to 60+ seconds to reduce CPU usage
- **Real-time Applications**: Set to 1-2 seconds for immediate cleanup

## Examples

### Basic Usage

```python
from microtetherdb import MicroTetherDB

# Create in-memory database
db = MicroTetherDB(
    ram_percentage=25,        # use 25% of free memory
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

### Async Integration Example

```python
import asyncio
from microtetherdb import MicroTetherDB

async def sensor_data_manager():
    """Example async application with database integration"""
    
    # Get current event loop
    loop = asyncio.get_event_loop()
    
    # Create database with event loop integration
    async with MicroTetherDB(
        filename="sensors.db",
        in_memory=False,
        ttl_check_interval=5,  # Check TTL every 5 seconds
        event_loop=loop        # Use our event loop
    ) as db:
        
        # Simulate sensor data collection
        for i in range(10):
            sensor_data = {
                "temperature": 20 + i,
                "humidity": 50 + (i * 2),
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Store with 30-second TTL
            key = db.put(sensor_data, ttl=30, tags=["sensor", "environment"])
            print(f"Stored sensor data: {key}")
            
            # Query recent data
            recent_data = db.query({
                "temperature": {"$gt": 22},
                "tags": "environment"
            })
            print(f"Recent high temperature readings: {len(recent_data)}")
            
            # Wait before next reading
            await asyncio.sleep(2)
        
        # Final cleanup (automatic, but shown for demonstration)
        cleaned = db.cleanup()
        print(f"Final cleanup: {cleaned} expired entries")

# Run the async application
asyncio.run(sensor_data_manager())
```

## License

Copyright (c) 2025 tendrl, inc.
All rights reserved. Unauthorized copying, distribution, modification, or usage of this code, via any medium, is strictly prohibited without express permission from the author.
