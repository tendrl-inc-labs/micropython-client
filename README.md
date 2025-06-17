# Tendrl MicroPython SDK

A resource-optimized SDK for IoT and embedded devices, featuring a minimal memory footprint and hardware-specific optimizations.

## Key Features

- **Minimal Memory Footprint**: Optimized for devices with limited RAM
- **API**: Easy to use in resource-constrained environments
- **Configuration via JSON**: Uses config.json for device configuration
- **BTree-based Offline Storage**: Efficient storage with minimal overhead
- **Hardware Watchdog Integration**: Ensures reliability in unstable environments
- **WebSocket Communication**: Efficient protocol for IoT devices
- **Flexible Operation Modes**: Support for both managed and unmanaged operation

## Prerequisites

Before installing the Tendrl SDK, you need to have MicroPython installed on your device. Follow the official MicroPython setup guide for your specific board:

- [ESP32 Setup Guide](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html#esp32-intro)
- [ESP8266 Setup Guide](https://docs.micropython.org/en/latest/esp8266/tutorial/intro.html)
    (ESP8266 RAM limitations make it difficult to use as a library alone. Freeze into firmware or use new v1.25.0 ROMFS build)
- [Raspberry Pi Pico W Setup Guide](https://docs.micropython.org/en/latest/rp2/quickref.html)

## Installation

The Tendrl SDK offers two installation options to suit different device constraints and use cases:

### Installation Types Overview

| Feature | Full Installation | Minimal Installation |
|---------|------------------|---------------------|
| **Client & Networking** | ✅ | ✅ |
| **Message Publishing** | ✅ | ✅ |
| **WebSocket Communication** | ✅ | ✅ |
| **Client Database (MicroTetherDB)** | ✅ | ❌ |
| **Offline Storage** | ✅ | ❌ |
| **TTL Management** | ✅ | ❌ |
| **Rich Queries** | ✅ | ❌ |
| **Flash Storage Required** | ~150KB | ~100KB |
| **Use Case** | Full-featured IoT applications | Resource-constrained devices |

### Choosing Your Installation

**Choose Full Installation if you need:**
- Local data storage and caching
- Offline message queuing
- Rich database queries
- TTL-based data expiration
- Maximum feature set

**Choose Minimal Installation if you need:**
- Direct message sending only
- Minimal flash storage usage
- Simple networking without persistence
- Maximum memory efficiency

### Option 1: Using the Install Script (Recommended)

**Step 1**: Download the install script from our GitHub repository:

```python
# https://github.com/tendrl-inc-labs/micropython-client/blob/main/install_script.py
```

**Step 2**: Configure installation type by editing `install_script.py`:

```python
# At the top of install_script.py, set:
INSTALL_DB = True   # Full installation with MicroTetherDB (Default)
# OR
INSTALL_DB = False  # Minimal installation without database
```

**Step 3**: Run the script on your device:

#### Using Thonny IDE (Recommended for beginners)

1. Install [Thonny IDE](https://thonny.org/)
2. Open Thonny and select your MicroPython device
3. Open the edited `install_script.py` in Thonny
4. Click "Run" to execute the installation

#### Using REPL (Alternative method)

1. Upload the edited `install_script.py` to your device
2. Open the REPL (Python prompt) on your device
3. Run the script:

```python
import install_script
install_script.main()
```

The script will automatically:

- Install the appropriate version based on your `INSTALL_DB` setting
- Create a template `config.json` if it doesn't exist
- Install the SDK to `/lib/tendrl`
- Set up required directories and configurations
- Display confirmation of installed features

### Option 2: Manual Installation

1. Download the SDK from [GitHub](https://github.com/tendrl-inc-labs/micropython-client)
2. Copy the `tendrl/` directory to your device's `/lib` directory
3. Create or update the `config.json` file in your device's root directory



### Client Configuration by Installation Type

The client automatically detects available features and configures itself appropriately:

#### Full Installation Usage

```python
from tendrl import Client

# All features available (default configuration)
client = Client(
    debug=True,
    # client_db=True,          # Auto-enabled
    # client_db_in_memory=True, # Default: in-memory
    # offline_storage=True      # Auto-enabled
)

# Use database features
key = client.db_put({"sensor": "temperature", "value": 23.5})
data = client.db_get(key)

# Offline storage works
client.publish(
    {"temperature": 23.5},
    write_offline=True  # Stores offline if connection fails
)
```

#### Minimal Installation Usage

```python
from tendrl import Client

# Database features auto-disabled
client = Client(
    debug=True,
    # client_db=False,      # Auto-disabled (no MicroTetherDB)
    # offline_storage=False # Auto-disabled (no MicroTetherDB)
)

# Database methods raise helpful errors
try:
    client.db_put({"test": "data"})
except Exception as e:
    print(e)  # "Client database not available - install full package"

# Basic publishing still works
client.publish(
    {"temperature": 23.5},
    write_offline=False  # Must be False - no offline storage
)
```

### Feature Comparison

| Feature | Full Installation | Minimal Installation |
|---------|------------------|---------------------|
| **Client & Networking** | ✅ | ✅ |
| **Message Publishing** | ✅ | ✅ |
| **WebSocket Communication** | ✅ | ✅ |
| **Client Database** | ✅ | ❌ |
| **Offline Storage** | ✅ | ❌ |
| **TTL Management** | ✅ | ❌ |
| **Rich Queries** | ✅ | ❌ |
| **Flash Storage** | ~150KB | ~100KB |

## Configuration

The SDK uses a configuration file approach rather than constructor parameters. Create a `config.json` file in your device's root directory:

```json
{
    "api_key": "your_api_key",
    "wifi_ssid": "your_wifi_network",
    "wifi_pw": "your_wifi_password",
    "reset": false
}
```

The SDK merges this user configuration with its internal defaults.

## Quick Start

```python
from tendrl import Client

# Initialize client - configuration is loaded from config.json
client = Client()

# Define data collection function
@client.tether(tags=["sensors"]) #optional tags for Flows(automations)
def read_sensors():
    return {
        "temperature": 25.5,
        "humidity": 60.0
    }

# Start the client - connect WiFi and tether queue
client.start()
```

## Client Initialization

The SDK provides several initialization options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | `str` | `"sync"` | Operation mode: "sync" or "async" (requires asyncio support) |
| `debug` | `bool` | `False` | Enable debug output |
| `timer` | `int` | `0` | Timer ID for sync mode |
| `freq` | `int` | `3` | Timer frequency |
| `callback` | `callable` | `None` | Optional callback function for message processing |
| `check_msg_rate` | `int` | `5` | How often to check for messages (seconds) |
| `max_batch_size` | `int` | `15` | Maximum batch size (memory-conscious) |
| `db_page_size` | `int` | `1024` | BTree page size for database operations |
| `watchdog` | `int` | `0` | Watchdog timer period (0 to disable) |
| `send_heartbeat` | `bool` | `True` | Enable heartbeat messages |
| `client_db` | `bool` | `True` | Enable client database |
| `client_db_in_memory` | `bool` | `True` | Use in-memory storage for client database |
| `offline_storage` | `bool` | `True` | Enable offline message storage |
| `managed` | `bool` | `True` | Enable managed mode (WiFi, queuing, offline storage) |
| `event_loop` | `asyncio.AbstractEventLoop` | `None` | Event loop for async mode (integrates with user applications) |

## Operation Modes

The SDK supports two distinct operation modes to suit different use cases:

### 1. Managed Mode (Default)

Managed mode provides full functionality including:

- WiFi connection management
- Message queuing and batching
- Offline message storage
- Automatic reconnection
- Heartbeat monitoring
- Client database for persistence

Best for:

- Devices that need reliable message delivery
- Applications requiring offline operation
- Systems that need automatic WiFi management
- Long-running applications

```python
from tendrl import Client

# Initialize in managed mode (default)
client = Client(
    mode="sync",
    managed=True,  # Default, can be omitted
    debug=True
)

# Start the client - handles WiFi and connection
client.start()

# Data will be queued and sent in batches
@client.tether(write_offline=True)
def read_sensors():
    return {"temperature": 25.5}

# Messages are stored offline if connection fails
client.publish(
    data={"status": "operational"},
    write_offline=True,
    db_ttl=3600  # Store for 1 hour
)
```

### 2. Unmanaged Mode

Unmanaged mode provides minimal operation:

- Direct message sending without queuing
- No WiFi management (assumes network is available)
- No offline storage
- No heartbeats
- Minimal resource usage

Best for:

- Devices with existing network management
- Applications that need direct message sending
- Systems with limited resources
- Short-lived operations

```python
from tendrl import Client

# Initialize in unmanaged mode
client = Client(
    mode="sync",
    managed=False,
    debug=True
)

# No need to start() - connection is established on first publish
# Messages are sent directly without queuing
client.publish(
    data={"temperature": 25.5},
    tags=["sensors"]
)

# Using with existing WiFi connection
import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("your_ssid", "your_password")

# SDK will use existing connection
client.publish(
    data={"status": "connected"},
    wait_response=True  # Wait for server response
)
```

### Mode Selection Guide

Choose managed mode when:

- You need reliable message delivery
- Your device needs to operate offline
- You want automatic WiFi management
- You need message persistence
- Your application runs continuously

Choose unmanaged mode when:

- You have existing network management
- You need direct message sending
- You have limited resources
- You're running short-lived operations
- You want minimal overhead

### Configuration Requirements

Both modes require:

```json
{
    "api_key": "your_api_key",
}
```

Managed mode additionally requires:

```json
{
    "wifi_ssid": "your_wifi_network",
    "wifi_pw": "your_wifi_password"
}
```

## Data Collection Methods

### Using Decorators

```python
# Basic usage with tags
@client.tether(tags=["environment"])
def collect_environment():
    return {
        "temperature": 25.5,
        "humidity": 60.0,
        "pressure": 1013.25
    }

# With offline storage
@client.tether(write_offline=True, db_ttl=3600, tags=["critical"])
def collect_critical_data():
    return {
        "battery": 3.7,
        "signal": -67
    }
```

### Manual Publishing

```python
# Publish data directly
client.publish(
    data={"latitude": 37.7749, "longitude": -122.4194},
    tags=["location"],
    entity="device-123",
    write_offline=True,  # Store offline if connection fails (managed mode only)
    db_ttl=7200  # Time-to-live for offline storage (seconds)
)
```

**Note**: In unmanaged mode:

- `write_offline` is automatically disabled
- Messages are sent directly without queuing
- No offline storage is available
- No WiFi management is performed

## Asynchronous Mode

The SDK supports asynchronous operation for devices with asyncio support:

```python
import uasyncio as asyncio
from tendrl import Client

# Async data collection function
async def collect_async_data():
    # Simulate sensor reading or network operation
    await asyncio.sleep(1)
    return {
        "temperature": 25.5,
        "humidity": 60.0
    }

# Initialize client in async mode
async def main():
    client = Client(
        mode="async",  # Use async mode
        debug=True     # Enable debug for async operations
    )

    # Register an async tether
    @client.tether(tags=["async_sensors"])
    async def async_sensor_tether():
        data = await collect_async_data()
        return data

    # Start the client asynchronously
    await client.start()

    # Manually publish async data
    await client.async_publish(
        data={"status": "operational"},
        tags=["system"],
        entity="device-async-123"
    )

# Run the async main function
asyncio.run(main())
```

### Async Features

- Supports `uasyncio` for cooperative multitasking
- Async data collection methods
- Non-blocking message publishing
- Compatible with devices supporting asyncio

**Note**: Async mode requires:

- MicroPython 1.15+ with asyncio support
- Devices with sufficient RAM (recommended 256KB+)
- Platforms like ESP32 with native asyncio

### Event Loop Integration

For applications that already have their own event loops, you can integrate the Tendrl client seamlessly:

```python
import uasyncio as asyncio
from tendrl import Client

async def user_sensor_task():
    """Your existing async task"""
    while True:
        # Your sensor reading logic
        print("Reading sensors...")
        await asyncio.sleep(5)

async def main():
    # Get your application's event loop
    loop = asyncio.get_event_loop()
    
    # Pass your loop to the client
    client = Client(
        mode="async",
        event_loop=loop,  # Use your event loop
        debug=True
    )
    
    # Start client on your loop
    client.start()
    
    # Start your own tasks
    sensor_task = asyncio.create_task(user_sensor_task())
    
    # Both run concurrently on the same loop
    await asyncio.sleep(30)
    
    # Clean up
    sensor_task.cancel()
    await client.async_stop()

# Run your application
asyncio.run(main())
```

**Benefits of Event Loop Integration:**

- No event loop conflicts
- Client integrates with existing async applications
- Shared resources and better performance
- Application remains in control of the event loop

### Async Configuration Options

```python
client = Client(
    mode="async",           # Enable async mode
    event_loop=your_loop,   # Optional: use your event loop
    async_timeout=10,       # Global async operation timeout
    max_async_tasks=5,      # Maximum concurrent async tasks
    async_retry_count=3,    # Number of retry attempts for async operations
)
```

### Handling Async Errors

```python
async def error_handling_example():
    try:
        await client.async_publish(
            data={"critical": "sensor_data"},
            tags=["error_test"]
        )
    except AsyncTimeoutError:
        # Handle async timeout
        print("Async operation timed out")
    except NetworkError:
        # Handle network-related async errors
        print("Network error in async mode")
```

## Database Operations

The SDK includes a built-in BTree database for local storage powered by **MicroTetherDB**:

```python
# Store data
client.db_put({"sensor": "temp", "value": 25.5}, ttl=3600)

# Retrieve data
data = client.db_get("some_key")

# Query data
results = client.db_query({"sensor": "temp"})

# List all keys
keys = client.db_list()

# Delete data
client.db_delete("some_key")

# Clean up expired entries
client.db_cleanup()
```

**📖 For complete database documentation, advanced features, and examples, see the [MicroTetherDB README](tendrl/lib/microtetherdb/README.md)**

### Database Features

- **Automatic TTL Management**: Items expire automatically
- **Rich Queries**: MongoDB-style query operators ($gt, $lt, $in, etc.)
- **Dual Storage Modes**: In-memory (fast) or file-based (persistent)
- **Event Loop Integration**: Seamless async application integration
- **Memory Efficient**: Configurable RAM usage
- **Production Ready**: Comprehensive error handling and test coverage

## Configuration Management

You can update the configuration programmatically:

```python
from tendrl.config_manager import update_config, read_config

# Update specific configuration values
update_config(
    api_key="new_api_key",
    wifi_ssid="new_network",
    wifi_pw="new_password"
)

# Read current configuration
config = read_config()
print(f"Current API key: {config['api_key']}")
```

## Hardware Integration

### Watchdog Support

```python
import machine

# Initialize client with watchdog support
client = Client(watchdog=30)  # 30 second watchdog

# Or start with an explicit watchdog period
client.start(watchdog=30)
```

## Connection Management

The SDK automatically manages network connections:

### Check connection status

```python
if client.client_enabled:
    print("Connected to Tendrl server")
else:
    print("Not connected")
```

## Memory Management

The SDK is optimized for memory-constrained devices:

```python
import gc

# Perform garbage collection
gc.collect()

# Check memory usage
free_mem = gc.mem_free()
print(f"Free memory: {free_mem} bytes")
```

## Platform Compatibility

- MicroPython 1.15+
- ESP32, Raspberry Pi Pico W, STM32, nRF52
- Memory requirement: ~100KB RAM minimum (much less RAM needed is using frozen or in ROMFS)

## Installation Options

### Full Installation (Recommended)

Includes MicroTetherDB for local data storage and caching:

```python
# Run on your MicroPython device
import mip
mip.install("github:tendrl-inc-labs/micropython-client/package.json", target="/lib")
```

### Minimal Installation

Excludes MicroTetherDB to save ~50KB flash space:

```python
# Run on your MicroPython device  
import mip
mip.install("github:tendrl-inc-labs/micropython-client/package-minimal.json", target="/lib")
```

### Using Install Script

```python
# Edit INSTALL_DB variable in install_script.py, then run:
exec(open("install_script.py").read())
```

**Configuration**: Edit the `INSTALL_DB` variable at the top of `install_script.py`:

- `INSTALL_DB = True` → Full installation with MicroTetherDB (default)
- `INSTALL_DB = False` → Minimal installation without database (saves ~50KB)

## Quick Start

### With Database (Full Installation)

```python
from tendrl import Client

# Full featured client (default)
client = Client(
    client_db=True,           # Enable client database
    client_db_in_memory=True, # Fast in-memory client DB
    offline_storage=True      # Enable offline message storage
)

# Persistent client database
client = Client(
    client_db=True, 
    client_db_in_memory=False  # File-based client DB
)

# Minimal database usage (client DB only)
client = Client(
    client_db=True,
    offline_storage=False  # Disable offline storage to save memory
)

# Use local database for caching
client.db_put({"sensor": "temp", "value": 23.5}, ttl=3600)
data = client.db_get(key)
results = client.db_query({"sensor": "temp"})
```

### Without Database (Minimal Installation)

```python
from tendrl import Client

# Create client without database features
client = Client(client_db=False, offline_storage=False)

# Direct publishing only
client.publish({"sensor": "temp", "value": 23.5})
```

## Features

- **Lightweight**: Minimal installation uses <100KB flash
- **Local Database**: Optional MicroTetherDB with TTL, queries, and caching
- **Automatic TTL**: Background cleanup of expired data
- **Rich Queries**: MongoDB-style query operators
- **Dual Storage**: In-memory (fast) or file-based (persistent)
- **Production Ready**: Comprehensive error handling and async support

## Database Features (Full Installation Only)

- **Automatic TTL Management**: Set expiry times, automatic cleanup
- **Rich Query Engine**: $gt, $lt, $in, $contains, nested fields
- **Dual Storage Modes**: Memory (speed) vs File (persistence)  
- **Batch Operations**: Efficient bulk insert/delete
- **Memory Efficient**: Configurable RAM usage limits
- **Production Ready**: Async support, error handling, comprehensive tests

## Database Storage Options (Full Installation)

The Tendrl client can use up to two separate databases:

### Main Storage Database (Offline Messages)

- **Purpose**: Internal message queuing and offline storage
- **Storage**: Always file-based (`/lib/tendrl/tether.db`) when enabled
- **Persistence**: Survives device restarts
- **Control**: `offline_storage=True/False`

### Client Database (Your Data)

- **Purpose**: Your application data storage
- **Storage**: Configurable (in-memory or file-based)
- **Access**: Via `client.db_*` methods
- **Control**: `client_db=True/False` and `client_db_in_memory=True/False`

```python
# Full featured (default) - both databases enabled
client = Client(
    client_db=True,           # Your data storage
    client_db_in_memory=True, # Fast in-memory
    offline_storage=True      # Offline message queue
)

# ✅ Full offline capabilities
# ✅ Fast client database
# ❌ Higher memory usage

# Client database only - no offline storage
client = Client(
    client_db=True,
    offline_storage=False  # Saves memory
)
# ✅ Your data storage available
# ✅ Lower memory usage
# ❌ No offline message queuing

# Persistent client database
client = Client(
    client_db=True, 
    client_db_in_memory=False  # File-based storage
)
# ✅ Data survives restarts
# ✅ Good performance
# ❌ Slightly slower than in-memory

# Minimal - no databases
client = Client(
    client_db=False,
    offline_storage=False
)
# ✅ Lowest memory usage
# ✅ Simplest setup
# ❌ No local data storage
# ❌ No offline capabilities
```

## License

Copyright (c) 2025 tendrl, inc.
All rights reserved. Unauthorized copying, distribution, modification, or usage of this code, via any medium, is strictly prohibited without express permission from the author.
