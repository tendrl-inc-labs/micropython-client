# Tendrl MicroPython SDK

A resource-optimized SDK for IoT and embedded devices, featuring a minimal memory footprint and hardware-specific optimizations.

## Key Features

- **Minimal Memory Footprint**: Optimized for devices with limited RAM
- **API**: Easy to use in resource-constrained environments
- **Command Processing**: Support for receiving and processing remote commands
- **Configuration via JSON**: Uses config.json for device configuration
- **BTree-based Offline Storage**: Efficient storage with minimal overhead
- **Hardware Watchdog Integration**: Ensures reliability in unstable environments
- **WebSocket Communication**: Efficient protocol for IoT devices
- **Flexible Operation Modes**: Support for both managed and unmanaged operation

## Prerequisites

Before installing the Tendrl SDK, you need to have MicroPython installed on your device. Follow the official MicroPython setup guide for your specific board:

- [ESP32 Setup Guide](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html#esp32-intro)
- [ESP8266 Setup Guide](https://docs.micropython.org/en/latest/esp8266/tutorial/intro.html)
- [Raspberry Pi Pico W Setup Guide](https://docs.micropython.org/en/latest/rp2/quickref.html)

## Installation

### Option 1: Using the Install Script (Recommended)

1. Download the install script from our GitHub repository:

```python
# https://github.com/tendrl-inc/micropython-sdk/blob/main/install_script.py
```

#### Using Thonny IDE (Recommended for beginners)

1. Install [Thonny IDE](https://thonny.org/)
2. Open Thonny and select your MicroPython device
3. Download `install_script.py` from our GitHub repository
4. Open the file in Thonny and click "Run" to execute it

#### Using REPL (Alternative method)

1. Upload `install_script.py` to your device using your preferred method
2. Open the REPL (Python prompt) on your device
3. Run the script:

```python
import install_script
install_script.main()
```

The script will:

- Create a template `config.json` if it doesn't exist
- Install the SDK to `/lib/tendrl`
- Set up required directories and configurations

### Option 2: Manual Installation

1. Download the SDK from [GitHub](https://github.com/tendrl-inc/micropython-sdk)
2. Copy the `tendrl/` directory to your device's `/lib` directory
3. Create or update the `config.json` file in your device's root directory

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
| `managed` | `bool` | `True` | Enable managed mode (WiFi, queuing, offline storage) |

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
    "app_url": "https://app.tendrl.com"
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

### Async Configuration Options

```python
client = Client(
    mode="async",           # Enable async mode
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

The SDK includes a built-in BTree database for local storage:

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

```python
# Force a connection attempt
client._connect()  # In sync mode
# or
await client._async_connect()  # In async mode

# Check connection status
if client.client_enabled:
    print("Connected to Tendrl server")
else:
    print("Not connected")
```

## Offline Operation

The SDK stores messages when offline and sends them when reconnected:

```python
# Process offline queue manually
client._process_offline_queue()

# Send offline messages manually
client._send_offline_messages()
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
- Memory requirement: ~100KB RAM minimum

## License

Copyright (c) 2025 tendrl, inc.
All rights reserved. Unauthorized copying, distribution, modification, or usage of this code, via any medium, is strictly prohibited without express permission from the author.
