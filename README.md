# Tendrl MicroPython Client

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/tendrl-inc/clients/nano_agent)
![MicroPython](https://img.shields.io/badge/MicroPython-1.19%2B-blue) ![License](https://img.shields.io/badge/License-Proprietary-red)

A resource-efficient SDK for IoT and embedded devices, featuring a minimal memory footprint and hardware-specific features.

## Key Features

- **Minimal Memory Footprint**: Designed for devices with limited RAM
- **MQTT Communication**: Reliable protocol with QoS 1 delivery for IoT devices
- **JPEG Video Streaming**: Real-time video streaming with cooperative multitasking
- **Automatic Entity Discovery**: Fetches entity info from API using API key
- **Simple Callback System**: Easy message handling with user-defined callbacks
- **Configuration via JSON**: Uses config.json for device configuration
- **BTree-based Offline Storage**: Efficient storage with minimal overhead
- **Hardware Watchdog Integration**: Ensures reliability in unstable environments
- **Flexible Operation Modes**: Support for both managed and unmanaged operation
- **TLS Support**: Secure connections with proper SSL context

## Prerequisites

Before installing the Tendrl SDK, you need to have MicroPython installed on your device. Follow the official MicroPython setup guide for your specific board:

- [ESP32 Setup Guide](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html#esp32-intro)
- [Raspberry Pi Pico W Setup Guide](https://docs.micropython.org/en/latest/rp2/quickref.html)

### Device Compatibility

**✅ Recommended Devices:**
- **ESP32-WROOM with PSRAM** - Excellent (520 KB RAM + PSRAM, no fragmentation issues)
- **ESP32-S2/S3** - Excellent (newer architecture, better memory management)
- **ESP32-C3** - Good (sufficient RAM, modern design)
- **Raspberry Pi Pico W** - Good (264 KB RAM, different memory architecture)

**❌ Not Recommended:**
- **ESP8266** - Insufficient RAM (80 KB total, only ~40-50 KB available for user code)
- **ESP32-WROOM without PSRAM** - TLS fragmentation issues (TLS handshakes require large contiguous memory blocks that may not be available due to heap fragmentation, even with sufficient total RAM)

**Memory Requirements:**
- **Minimum RAM:** 150 KB total (125 KB absolute minimum)
- **Client Runtime:** ~57 KB steady state (without streaming active)
- **Streaming Runtime:** Additional ~20-40 KB when streaming (for JPEG buffers and socket buffers)
- **Flash Storage:** ~100 KB (minimal package) or ~172 KB (full package with database)

## Installation

The Tendrl SDK offers two installation options to suit different device constraints and use cases:

### Feature Comparison

| Feature | Full Installation | Minimal Installation |
|---------|------------------|---------------------|
| **Client & Networking** | ✅ | ✅ |
| **Message Publishing** | ✅ | ✅ |
| **MQTT Communication** | ✅ | ✅ |
| **JPEG Video Streaming** | ⚠️ Optional | ⚠️ Optional |
| **Client Database** | ✅ | ❌ |
| **Offline Storage** | ✅ | ❌ |
| **TTL Management** | ✅ | ❌ |
| **Rich Queries** | ✅ | ❌ |
| **Flash Storage** | ~172KB | ~100KB |
| **Flash Storage (with streaming)** | ~207KB | ~135KB |

 &nbsp;

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

**JPEG Streaming (Optional for both installations):**

- Streaming requires a separate installation step
- Works with both minimal and full installations
- Adds ~35KB to flash storage
- See installation instructions below

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

INSTALL_STREAMING = True   # Set to True to include JPEG streaming support (optional)
# OR
INSTALL_STREAMING = False  # Default: No streaming (saves ~35KB flash)
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

### Installing JPEG Streaming (Optional)

Streaming is **not included by default** in either minimal or full installations. To add streaming support:

**Using the Install Script:**
```python
# In install_script.py, set:
INSTALL_STREAMING = True
```

**Using mip (Manual):**
```python
import mip
# Install streaming module separately
mip.install("github:tendrl-inc-labs/micropython-client/package-streaming.json", target="/lib")
```

**Manual Installation:**
- Copy `tendrl/streaming.py` to `/lib/tendrl/streaming.py` on your device

**Note:** Streaming adds ~35KB to flash storage and works with both minimal and full installations.

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

## Configuration

Create a `config.json` file in your device's root directory:

```json
{
    "api_key": "your_api_key",
    "wifi_ssid": "your_wifi_network",
    "wifi_pw": "your_wifi_password",
    "reset": false
}
```

**Fields:**
- `api_key` (required): Your Tendrl API key
- `wifi_ssid` (required): WiFi network name
- `wifi_pw` (required): WiFi password
- `reset` (optional): Set to `true` to clear cached entity info (useful with watchdog)

## Quick Start

### Basic Messaging

```python
from tendrl import Client

# Initialize client - configuration is loaded from config.json
client = Client()

# Start the client - connect WiFi and tether queue
client.start()

# Simplest way: use tether decorator to automatically send function return values
# Function must return dict or str
@client.tether(tags=["sensors"])  # Optional tags for Flows (automations)
def read_sensors():
    return {
        "temperature": 25.5,
        "humidity": 60.0
    }

# Call your function - data is automatically collected and sent
read_sensors()  # Data is automatically queued and sent
```

### Streaming (Requires Async Mode)

```python
import asyncio
from tendrl import Client

async def main():
    # Initialize in async mode (REQUIRED for streaming)
    client = Client(mode="async", debug=True)
    client.start()
    await asyncio.sleep(2)
    
    # Start streaming - simplest usage (camera automatically configured with optimized settings)
    client.start_streaming()
    
    # Keep running
    await asyncio.sleep(60)
    await client.async_stop()

asyncio.run(main())
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
| `client_db_in_memory` | `bool` | `True` | Use in-memory storage for client database (recommended to avoid corruption risk) |
| `offline_storage` | `bool` | `True` | Enable offline message storage (file-based, [see warning below](#file-based-storage-warning)) |
| `managed` | `bool` | `True` | Enable managed mode (WiFi, queuing, offline storage) |
| `event_loop` | `asyncio.AbstractEventLoop` | `None` | Event loop for async mode (integrates with user applications) |

> **Mode and Event Loop**: Given MicroPython only has a single event loop, having the sync mode allows using one of the hardware timers to circumvent this limitation for necesarry non-blocking, background processing. This is the default mode for ease of use.
>
> **Streaming Requirement**: JPEG streaming requires `mode="async"`. The client will warn if you try to start streaming in sync mode.

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

# Simplest way: use tether decorator to automatically send function return values
# Function must return dict or str
@client.tether(write_offline=True, tags=["sensors"])
def read_sensors():
    return {"temperature": 25.5}

# Call your function - data is automatically collected and sent
read_sensors()  # Data is queued and sent in batches, stored offline if connection fails

# Alternative: manual publishing (for one-off messages)
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
    data={"status": "connected"}
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


## MQTT Communication

The SDK uses MQTT for reliable communication with the Tendrl platform. Key features:

### Automatic Entity Discovery with Caching

The client automatically fetches entity information from the API using your API key and caches it for efficiency:

```python
from tendrl import Client

# Client automatically fetches entity info on first connection
# Subsequent connections use cached JTI and subject
client = Client(debug=True)
client.start()

# Entity info is used for:
# - MQTT topic structure: <account>/<region>/<jti>/<action>
# - Authentication with MQTT broker
# - Message routing

# Cached data is automatically cleared if API credentials become invalid
```

### Message Callback System

Handle incoming messages with a simple callback function:

```python
def message_handler(message):
    """Handle incoming messages"""
    msg_type = message.get('msg_type')
    data = message.get('data', {})
    print(f"Published data: {data}")

# Initialize client with callback
client = Client(
    mode="sync",
    debug=True,
    callback=message_handler
)
```

### Topic Structure

Messages are published to topics following this structure:

```sh
<account>/<region>/<jti>/<action>
```

Example: `1001/us-east/entity:gateway/publish`

### TLS Support

Secure connections are supported with automatic SSL context creation:

```json
{
    "mqtt_host": "mqtt.tendrl.com",
    "mqtt_port": 443,
    "mqtt_ssl": true
}
```

For development environments, self-signed certificates are automatically allowed when using localhost.

## Data Collection Methods

### Using Decorators

```python
# Basic usage with tags
# Function must return dict or str
@client.tether(tags=["environment"])
def collect_environment():
    return {
        "temperature": 25.5,
        "humidity": 60.0,
        "pressure": 1013.25
    }

# With offline storage
# Function must return dict or str
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

## Message Callbacks

```python
# Set up callback to handle incoming messages
def message_handler(message):
    # Process incoming message
    print(f"Received: {message['msg_type']} from {message['source']}")
    return 0  # Return non-zero if processing fails

# Initialize client with callback
client = Client(
    callback=message_handler,
    check_msg_rate=5  # Check for messages every 5 seconds (default: 5)
)
client.start()
```

### IncomingMessage Structure

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `msg_type` | `str` | Message type identifier (e.g., "command", "notification", "alert") | ✅ Yes |
| `source` | `str` | Sender's resource path (set by server) | ✅ Yes |
| `timestamp` | `str` | RFC3339 timestamp (set by server) | ✅ Yes |
| `data` | `dict/list/any` | The actual message payload (can be any JSON type) | ✅ Yes |
| `tags` | `list` | Message tags | ❌ Optional |

### Message Context Structure

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `tags` | `list` | Message tags for categorization | ❌ Optional |
| `dynamicActions` | `dict` | Server-side validation results | ❌ Optional |

#### How It Works

1. **Background Checking**: In managed mode, the SDK automatically checks for messages every 5 seconds (configurable via `check_msg_rate` parameter)
2. **Callback Execution**: Your callback function is called for each incoming message
3. **Error Handling**: Failed callbacks don't stop other message processing
4. **Connectivity Aware**: Automatically handles network failures and updates connectivity state

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
    # Function must return dict or str
    @client.tether(tags=["async_sensors"])
    async def async_sensor_tether():
        data = await collect_async_data()
        return data

    # Start the client (runs in background)
    client.start()

    # Manually publish data (works in async mode too)
    client.publish(
        data={"status": "operational"},
        tags=["system"],
        entity="device-async-123"
    )
    
    # Call your tether-decorated function
    await async_sensor_tether()
    
    # Keep running
    await asyncio.sleep(30)
    
    # Stop the client
    await client.async_stop()

# Run the async main function
asyncio.run(main())
```

### Async Features

- Supports `uasyncio` for cooperative multitasking
- Async data collection methods
- Non-blocking message publishing
- Compatible with devices supporting asyncio

**Note**: Async mode requires:

- MicroPython 1.19.0+ with asyncio support
- Devices with sufficient RAM (recommended 150KB+ for reliable TLS)
- Platforms like ESP32-S2/S3 or ESP32-WROOM with PSRAM (recommended for async mode)

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
- Shared resources and efficient operation
- Application remains in control of the event loop

### Async Configuration Options

```python
client = Client(
    mode="async",           # Enable async mode
    event_loop=your_loop,   # Optional: use your event loop
    debug=True
)
```

## JPEG Video Streaming

The SDK supports real-time JPEG video streaming with cooperative multitasking, allowing streaming and messaging to work together seamlessly.

> **Note:** Streaming requires a separate installation step. See [Installing JPEG Streaming](#installing-jpeg-streaming-optional) in the Installation section.

### Quick Start

```python
import asyncio
from tendrl import Client

async def main():
    # Initialize client in async mode (REQUIRED for streaming)
    client = Client(
        mode="async",        # REQUIRED: Streaming only works in async mode
        debug=True,
    )
    
    # Start the client
    client.start()
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Start streaming - simplest usage (uses default camera settings)
    # Camera automatically set up with optimized settings (VGA, quality 50)
    client.start_streaming()
    
    # Keep running
    await asyncio.sleep(60)
    await client.async_stop()

asyncio.run(main())
```

### Streaming Features

- **Real-time JPEG Streaming**: Stream video frames to Tendrl platform
- **Cooperative Multitasking**: Yields control to allow messaging operations
- **Automatic Camera Setup**: Default camera configuration for OpenMV devices
- **Dynamic Control**: Start/stop streaming programmatically
- **Duration Control**: Stream for a specific duration or indefinitely

### Streaming Requirements

- **Streaming Module Installed**: Requires `tendrl/streaming.py` to be installed (see [Installing JPEG Streaming](#installing-jpeg-streaming-optional))
- **Async Mode**: Must use `Client(mode="async")`
- **Camera Support**: Requires `sensor` module (OpenMV) or custom capture function
- **Network Connection**: Requires active network connection
- **API Key**: Must be configured in `config.json`

### Streaming Methods

#### `start_streaming()`

Start streaming JPEG frames to the server.

```python
stream_task = client.start_streaming(
    capture_frame_func=None,      # Custom capture function (optional)
    target_fps=15,                 # Target frames per second (default: 15, max: 30)
    quality=50,                    # JPEG quality 0-100 (default: 50, optimized for consistent performance)
    stream_duration=-1             # Duration in seconds (-1 = indefinite, default)
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `capture_frame_func` | `callable` | `None` | Function that returns JPEG bytes. If `None` and `sensor` module available, camera is automatically configured with optimized settings (VGA, JPEG, quality, skip_frames). |
| `target_fps` | `int` | `15` | Target frames per second (maximum: 30, enforced by server). Default 15 provides consistent performance. |
| `quality` | `int` | `50` | JPEG quality 0-100 (lower = smaller files, faster transmission). Default 50 is optimized for consistent performance. |
| `stream_duration` | `int` | `-1` | Duration in seconds. `-1` = stream indefinitely until stopped |

**Camera Configuration:**

When `capture_frame_func` is `None` and the `sensor` module is available, the camera is automatically configured with these optimized settings:
- **Format**: JPEG (`sensor.JPEG`)
- **Resolution**: VGA (640x480) (`sensor.VGA`)
- **Quality**: Set via `quality` parameter (default: 50)
- **Stabilization**: 1500ms frame skip for camera stabilization

These settings are optimized for streaming performance and can be adjusted via the `quality` parameter. For custom camera configuration, provide your own `capture_frame_func`.

**Returns:** Background task (async mode) or `None` (sync mode)

**Raises:**
- `ValueError`: If `target_fps` exceeds 30 or is <= 0
- `ImportError`: If `sensor` module not available and no `capture_frame_func` provided

#### `stop_streaming()`

Stop the active streaming task.

```python
client.stop_streaming()
```

**Returns:** `None`

#### `is_streaming()`

Check if streaming is currently active.

```python
if client.is_streaming():
    print("Streaming is active")
    client.stop_streaming()
```

**Returns:** `bool` - `True` if streaming is active, `False` otherwise

### Streaming Examples

#### Example 1: Simplest Usage (Default Camera)

```python
import asyncio
from tendrl import Client

async def main():
    client = Client(mode="async", debug=True)
    client.start()
    await asyncio.sleep(2)
    
    # Simplest usage - uses default camera settings (VGA, quality 50)
    # Defaults: target_fps=15, quality=50 (optimized for consistent performance)
    client.start_streaming()
    
    # Stream indefinitely (default)
    await asyncio.sleep(3600)  # Run for 1 hour
    await client.async_stop()

asyncio.run(main())
```

#### Example 2: Adjust Quality and FPS

```python
import asyncio
from tendrl import Client

async def main():
    client = Client(mode="async", debug=True)
    client.start()
    await asyncio.sleep(2)
    
    # Adjust quality and FPS for your use case
    # Defaults: target_fps=15, quality=50 (optimized for consistent performance)
    # Lower quality (45-50) = smaller files, faster transmission
    # Higher quality (55-60) = better image quality, larger files
    # Lower FPS (10-15) = less bandwidth, more stable on slower networks
    # Higher FPS (18-20) = smoother video, requires better network
    client.start_streaming(
        target_fps=20,      # Higher FPS for better networks
        quality=55           # Higher quality for better image quality
    )
    
    await asyncio.sleep(60)
    await client.async_stop()

asyncio.run(main())
```

#### Example 3: Custom Capture Function

```python
import asyncio
import sensor
from tendrl import Client

def setup_camera():
    """Custom camera setup with specific settings"""
    sensor.reset()
    sensor.set_pixformat(sensor.JPEG)
    sensor.set_framesize(sensor.QVGA)  # Smaller resolution
    sensor.set_quality(50)              # Lower quality
    sensor.skip_frames(time=1500)

def capture_frame():
    """Custom capture function"""
    img = sensor.snapshot()
    return img.bytearray()

async def main():
    client = Client(mode="async", debug=True)
    client.start()
    await asyncio.sleep(2)
    
    # Setup camera first, then provide custom capture function
    setup_camera()
    client.start_streaming(
        capture_frame_func=capture_frame,
        target_fps=15,
        quality=50  # Note: quality parameter not used with custom capture
    )
    
    await asyncio.sleep(60)
    await client.async_stop()

asyncio.run(main())
```

#### Example 4: Timed Streaming (Motion Detection)

```python
import asyncio
from tendrl import Client

async def main():
    client = Client(mode="async", debug=True)
    client.start()
    await asyncio.sleep(2)
    
    # Stream for 30 seconds when motion detected
    if detect_motion():
        client.start_streaming(stream_duration=30)
        print("Streaming for 30 seconds...")
    
    await asyncio.sleep(60)
    await client.async_stop()

asyncio.run(main())
```

#### Example 5: Streaming + Messaging Together

```python
import asyncio
from tendrl import Client

async def main():
    # Create client with both streaming and messaging
    client = Client(
        mode="async",
        debug=True,
    )
    
    client.start()
    await asyncio.sleep(2)
    
    # Start streaming (uses defaults: target_fps=15, quality=50)
    client.start_streaming()
    
    # Publish messages while streaming
    @client.tether(tags=["sensors"])
    async def read_sensors():
        return {
            "temperature": 23.5,
            "streaming_active": client.is_streaming()
        }
    
    # Both streaming and messaging work together
    await asyncio.sleep(60)
    await client.async_stop()

asyncio.run(main())
```

### Camera Configuration

When using the default camera (no `capture_frame_func` provided), the camera is automatically configured with these optimized settings:

- **Format**: JPEG (`sensor.JPEG`)
- **Resolution**: VGA (640x480) (`sensor.VGA`)
- **Quality**: Configurable via `quality` parameter (default: 50)
- **Stabilization**: 1500ms frame skip for camera stabilization

These settings are optimized for streaming performance. The `quality` parameter allows you to balance image quality vs. file size and transmission speed:
- **Lower quality (45-50)**: Smaller files, faster transmission, good for slower networks (default: 50)
- **Higher quality (60-70)**: Better image quality, larger files, requires better network

For custom camera configurations, provide your own `capture_frame_func` that handles camera setup and frame capture.

### Streaming Configuration

The streaming implementation uses cooperative multitasking with optimized internal parameters:

- **Cooperative Yielding**: Yields periodically to allow messaging operations
- **Memory Management**: Automatic GC at optimized intervals
- **Frame Pacing**: Accurate frame timing with proper delays
- **Error Recovery**: Automatic reconnection on network errors
- **Performance Monitoring**: Performance stats printed when `debug=True` (every 60 frames)

### Streaming Best Practices

1. **Use Async Mode**: Streaming requires `mode="async"`
2. **Quality Settings**: Default quality 50 provides consistent performance. Lower (45-50) = smaller files, faster transmission. Higher (55-60) = better image quality.
3. **FPS Settings**: Lower FPS (15-20) = less bandwidth, more stable on slower networks
4. **Debug Mode**: Enable `debug=True` to see performance stats every 60 frames and identify bottlenecks
5. **Test Network**: Verify your network can handle the target FPS and quality
6. **Test Under Load**: Verify streaming + messaging work together in your use case

### Streaming Limitations

- **Maximum FPS**: Server enforces 30 FPS maximum
- **Network Dependent**: Requires stable network connection
- **Memory Usage**: JPEG frames consume memory (quality and size affect usage)
- **Camera Required**: Requires camera hardware or custom capture function

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

<a id="file-based-storage-warning"></a>
### ⚠️ File-Based Storage Warning

**Important**: When using file-based storage (`in_memory=False`), there is a risk of database corruption if:

- **Power loss occurs during write operations** - The database uses BTree which writes directly to flash storage
- **Improper shutdown** - Device is reset or powered off without proper cleanup
- **File system errors** - Underlying filesystem issues can cause corruption

**Recommendations**:

1. **Use in-memory storage when possible** (`client_db_in_memory=True`) - This eliminates corruption risk but data is lost on power loss
2. **Proper shutdown** - Always call `client.stop()` or `await client.async_stop()` before powering off
3. **UPS/Battery backup** - For critical systems, use uninterruptible power supplies
4. **Regular backups** - For important data, implement periodic backup strategies
5. **Error handling** - The database will attempt to recover from minor corruption, but severe corruption may require database recreation

**Note**: The database includes automatic flushing and error recovery mechanisms, making corruption rare in normal operation. However, power loss during active writes can still cause issues. For mission-critical applications, consider using in-memory storage with periodic cloud synchronization.


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

### Stop the client

```python
# Stop the client (sync mode)
client.stop()

# Stop the client (async mode)
await client.async_stop()
```

## Memory Management

The SDK is designed for memory-constrained devices:

```python
import gc

# Perform garbage collection
gc.collect()

# Check memory usage
free_mem = gc.mem_free()
print(f"Free memory: {free_mem} bytes")
```

## Platform Compatibility

### Supported Platforms

- **MicroPython:** 1.19.0 or higher
- **Recommended:** ESP32-WROOM (with PSRAM), ESP32-S2/S3, ESP32-C3, Raspberry Pi Pico W
- **Not Recommended:** ESP8266, ESP32-WROOM (without PSRAM)

### System Requirements

**Memory (RAM):**
- **Minimum Recommended:** 150 KB total RAM
- **Client Runtime:** ~57 KB steady state (without streaming active)
- **Streaming Runtime:** Additional ~20-40 KB when streaming (JPEG buffers + socket buffers)
- **TLS Overhead:** ~3-4 KB
- **Safety Margin:** ~20-30 KB for application code and buffers

**Storage (Flash):**
- **Minimal Package:** ~100 KB (without database features)
- **Full Package:** ~172 KB (with MicroTetherDB database)

**Note:** ESP32-WROOM without PSRAM may experience TLS connection failures due to memory fragmentation, even with sufficient total RAM. TLS handshakes require large contiguous memory blocks (20-40 KB) that may not be available after heap fragmentation.


## Features

- **Lightweight**: Minimal installation uses <100KB flash
- **JPEG Video Streaming**: Real-time video streaming with cooperative multitasking
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

## Examples

The SDK includes comprehensive examples demonstrating various use cases:

### Basic Examples

- **`examples/jpeg_stream_example.py`**: Simple streaming example
- **`examples/streaming_with_messaging.py`**: Streaming + messaging together
- **`examples/client_configuration.py`**: Configuration examples

### Running Examples

```python
# Upload example file to your device
# Then run in REPL or Thonny:

import examples.jpeg_stream_example
# Or
import examples.streaming_with_messaging
```

## Troubleshooting

### Streaming Issues

**Streaming doesn't start:**
- Ensure `mode="async"` is set
- Check that camera/sensor module is available
- Verify network connection is established
- Check `debug=True` for error messages

**Frame drops:**
- Lower JPEG quality (try 50-60)
- Reduce frame size (try QVGA instead of VGA)
- Check network stability
- Monitor memory usage

**Streaming freezes:**
- Normal: GC runs every ~10 seconds (configurable via `gc_interval`)
- Reduce `gc_interval` for more frequent, smaller GCs
- Check for memory leaks in your code

### Messaging Issues

**Messages not sending:**
- Check `client.client_enabled` status
- Verify MQTT connection (`client.mqtt.connected`)
- Check network connectivity
- Review debug output

**Batch processing slow:**
- Normal: Batches process in 2-5ms
- Check message size (large messages = slower)
- Monitor queue size

### General Issues

**Memory errors:**
- Use minimal installation if database not needed
- Lower JPEG quality for streaming
- Reduce batch sizes
- Monitor with `gc.mem_free()`

**Connection issues:**
- Verify WiFi credentials in `config.json`
- Check API key is valid
- Review network connectivity
- Check TLS/SSL configuration

## License

Copyright (c) 2025 tendrl, inc.
All rights reserved. Unauthorized copying, distribution, modification, or usage of this code, via any medium, is strictly prohibited without express permission from the author.
