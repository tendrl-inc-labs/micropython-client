# Simple DHT ML Sensor - Plug & Play Anomaly Detection

**Get temperature/humidity anomaly detection in 3 lines of code!**

## 🚀 Quick Start

```python
from examples.tendrl_dht import SimpleDHTML

def my_alert(temp, humidity, reason):
    print(f"🚨 ALERT: {temp}°, {humidity}% - {reason}")
    # Send notification, log to file, etc.

# Setup sensor with your alert function
# Supports both Celsius and Fahrenheit, configurable data windows and alert cooldowns
sensor = SimpleDHTML(pin=4, sensor_type='DHT22', alert_callback=my_alert, 
                    temp_unit='F', data_window_hours=24, alert_cooldown_minutes=3)

# Set acceptable ranges (in your chosen temperature unit)
sensor.set_thresholds(temp_range=[68, 77], humidity_range=[40, 60])  # Fahrenheit

# Start monitoring (default: 30 seconds, configurable)
sensor.start()  # Uses default 30-second interval
# sensor.start(interval_seconds=60)  # Or specify custom interval

# That's it! Anomalies will trigger your alert function automatically
```

## 🏠 Pre-configured Sensors

Even simpler - use pre-configured sensors for common scenarios:

```python
from examples.tendrl_dht import create_indoor_sensor, create_greenhouse_sensor

def my_alert(temp, humidity, reason):
    print(f"ALERT: {reason}")

# Indoor monitoring with Fahrenheit, 24-hour data window, and 5-minute alert cooldown
indoor = create_indoor_sensor(pin=4, alert_callback=my_alert, 
                             temp_unit='F', data_window_hours=24, alert_cooldown_minutes=5)
indoor.start()  # Default 30-second readings

## 📊 Available Metrics & Data Analysis

### **Real-time Status**

```python
status = sensor.get_status()
print(f"Current: {status['temperature']['current']}{status['temperature']['unit']}")
print(f"Average: {status['temperature']['average']}{status['temperature']['unit']}")
print(f"Range: {status['temperature']['range']}{status['temperature']['unit']}")
print(f"Total readings: {status['total_readings']}")
print(f"Data window: {status['data_window_hours']} hours")
```

### **Comprehensive Data Structure**

Each sensor reading contains:

```json
{
  "temp": 23.5,           // Temperature in Celsius (internal storage)
  "temp_unit": "C",       // Internal storage unit (always Celsius)
  "humidity": 47.2,       // Humidity percentage  
  "timestamp": 1640995200, // Unix timestamp
  "count": 150,           // Reading sequence number
  "hour": 14              // Hour of day (0-23) for pattern analysis
}
```

**Note**: Temperatures are always stored internally in Celsius for consistency, but displayed in your chosen unit (°C or °F).

### **Available Analytics**

- **Current values**: Latest temperature/humidity readings
- **Running averages**: Mean temperature/humidity over time windows
- **Min/Max ranges**: Daily/hourly extremes
- **Deviation analysis**: How much current reading differs from average
- **Trend detection**: Sudden changes (>5°C or >20% humidity)
- **Pattern matching**: Comparison against known normal conditions
- **Alert frequencies**: Cooldown tracking to prevent notification spam

## 🕒 Data Storage & Viewing Windows

### **Storage Configurations**

| **Configuration** | **Window Size** | **Memory Usage** | **Use Case** |
|-------------------|-----------------|------------------|--------------|
| **Simple Monitoring** | 1 hour (120 readings) | ~5% RAM | Real-time alerts |
| **Daily Analysis** | 24 hours (2,880 readings) | ~15% RAM | Daily patterns |
| **Weekly Trends** | 7 days (20,160 readings) | File storage | Environmental trends |
| **Long-term** | 30+ days | File storage | Seasonal analysis |

### **Memory Efficiency**

- **ESP32 (520KB RAM)**: Comfortable with 7-day windows
- **ESP8266 (80KB RAM)**: Best with 1-24 hour windows  
- **File storage**: Can handle months of data (limited by flash)
- **Automatic cleanup**: TTL system removes old data automatically

### **Custom Window Configuration**

```python
# Real-time monitoring (minimal memory)
sensor = SimpleDHTML(pin=4)
sensor.db = MicroTetherDB(
    ram_percentage=5,      # Use only 5% RAM
    ttl_check_interval=300, # Clean every 5 minutes
)
# Data stored with 1-hour TTL in _take_reading()

# Historical analysis (balanced)
sensor.db = MicroTetherDB(
    in_memory=False,       # Use file storage
    ram_percentage=15,     # 15% RAM for caching
)
# Modify TTL in _take_reading() to 7*24*3600 for 7-day window

# Long-term trends (maximum data)
sensor.db = MicroTetherDB(
    in_memory=False,       # File storage required
    ram_percentage=25,     # 25% RAM for performance
)
# Modify TTL to 30*24*3600 for 30-day window
```

## 🔍 Advanced Querying

Access the underlying MicroTetherDB for custom analysis:

```python
# Get recent temperature spikes
spikes = sensor.db.query({
    "temp": {"$gt": 30},
    "timestamp": {"$gte": time.time() - 3600}  # Last hour
})

# Morning temperature patterns
morning_data = sensor.db.query({
    "hour": {"$gte": 6, "$lte": 10},
    "temp": {"$exists": True},
    "$limit": 50
})

# Humidity ranges for specific conditions
humid_conditions = sensor.db.query({
    "humidity": {"$gte": 70},
    "temp": {"$lt": 25}
})
```

## ⚙️ What You Get

- **Configurable reading intervals** - 10 seconds to hours (default: 30 seconds)
- **Threshold alerts** when values go outside your ranges
- **Smart detection** of sudden changes (>5°C or >20% humidity)
- **Configurable alert cooldown** prevents spam (0-30+ minutes, default: 5 minutes)
- **Minimal memory** usage (~10KB RAM for basic, scalable to MB for analysis)
- **Both sensors** supported (DHT11 and DHT22)
- **Rich querying** with MongoDB-style syntax
- **Automatic data cleanup** with TTL management
- **Historical analysis** capabilities

## 🎯 Perfect For

- **Home automation** - Monitor room conditions with trend analysis
- **Greenhouse control** - Plant environment alerts with historical data
- **Server rooms** - Temperature monitoring with long-term trending
- **HVAC systems** - Equipment failure detection with pattern recognition
- **IoT projects** - Environmental monitoring with data analytics
- **Research projects** - Climate data collection with statistical analysis

## ⚙️ Configuration Reference

### **Complete Configuration Options**

| **Parameter** | **Type** | **Default** | **Options** | **Description** |
|---------------|----------|-------------|-------------|-----------------|
| `pin` | int | Required | 0-39 (ESP32), 0-16 (ESP8266) | GPIO pin for DHT sensor |
| `sensor_type` | str | `'DHT22'` | `'DHT11'`, `'DHT22'` | Sensor model (DHT11: whole numbers, DHT22: 1 decimal) |
| `alert_callback` | function | `None` | User function | Called on anomalies: `callback(temp, humidity, reason)` |
| `temp_unit` | str | `'C'` | `'C'`, `'F'` | Temperature unit (Celsius or Fahrenheit) |
| `data_window_hours` | int | `1` | `1, 24, 168, 720, ...` | Hours of data to keep (affects storage type) |
| `alert_cooldown_minutes` | int | `5` | `0, 1, 5, 10, 30, ...` | Minutes between similar alerts (0 = no cooldown) |

### **Method Configuration Options**

| **Method** | **Parameter** | **Default** | **Options** | **Description** |
|------------|---------------|-------------|-------------|-----------------|
| `set_thresholds()` | `temp_range` | `[15, 35]` (°C) | `[min, max]` | Acceptable temperature range in your chosen unit |
| | `humidity_range` | `[20, 80]` | `[min, max]` | Acceptable humidity range (0-100%) |
| `set_alert_cooldown()` | `minutes` | `5` | `0, 1, 5, 10, 30, ...` | Minutes between similar alerts (0 = immediate alerts) |
| `start()` | `interval_seconds` | `30` | `10, 30, 60, 300, 3600, ...` | How often to take readings |

### **Automatic Configurations by Data Window**

| **Window** | **Storage** | **RAM Usage** | **TTL Cleanup** | **Use Case** |
|------------|-------------|---------------|-----------------|--------------|
| **1 hour** | In-memory | ~5% | Every 5 min | Real-time alerts |
| **24 hours** | In-memory | ~15% | Every 5 min | Daily analysis |
| **7 days (168h)** | File storage | ~20% cache | Every 10 min | Weekly trends |
| **30 days (720h)** | File storage | ~25% cache | Every 10 min | Long-term analysis |

### **Pre-configured Sensor Defaults**

| **Function** | **Temp Range (°C)** | **Temp Range (°F)** | **Humidity** | **Window** | **Alert Cooldown** |
|--------------|-------------------|-------------------|--------------|------------|-------------------|
| `create_indoor_sensor()` | 20-26°C | 68-79°F | 40-60% | 24 hours | 5 minutes |

### **Quick Configuration Examples**

| **Scenario** | **Configuration Code** |
|--------------|------------------------|
| **Basic indoor monitoring** | `SimpleDHTML(pin=4, temp_unit='F', data_window_hours=24)` |
| **Critical system (fast alerts)** | `SimpleDHTML(pin=4, data_window_hours=1)`<br/>`sensor.start(interval_seconds=10)  # Fast 10-second readings` |
| **Battery-powered outdoor** | `SimpleDHTML(pin=4, temp_unit='C', data_window_hours=168)`<br/>`sensor.start(interval_seconds=300)  # 5-minute readings` |
| **Research/long-term study** | `SimpleDHTML(pin=4, data_window_hours=720)`<br/>`sensor.start(interval_seconds=3600)  # Hourly readings` |
| **Greenhouse with weekly analysis** | `create_greenhouse_sensor(pin=4, temp_unit='C', data_window_hours=168)`<br/>`sensor.start()  # Default 30-second readings` |

## 🌡️ Temperature Units & Data Windows

### **Temperature Unit Support**

```python
# Celsius (default)
sensor_c = SimpleDHTML(pin=4, temp_unit='C')
sensor_c.set_thresholds(temp_range=[20, 25])  # 20-25°C

# Fahrenheit  
sensor_f = SimpleDHTML(pin=4, temp_unit='F')
sensor_f.set_thresholds(temp_range=[68, 77])  # 68-77°F (same as 20-25°C)

# Status returns temperatures in your chosen unit
status = sensor_f.get_status()
print(f"Current: {status['temperature']['current']}°F")
```

### **Configurable Data Windows**

```python
# 1 hour window (minimal memory, real-time alerts)
sensor = SimpleDHTML(pin=4, data_window_hours=1)      # ~5% RAM, in-memory

# 24 hour window (daily analysis) 
sensor = SimpleDHTML(pin=4, data_window_hours=24)     # ~15% RAM, in-memory

# 7 day window (weekly trends)
sensor = SimpleDHTML(pin=4, data_window_hours=168)    # File storage, ~20% RAM cache

# 30 day window (long-term analysis)
sensor = SimpleDHTML(pin=4, data_window_hours=720)    # File storage, ~25% RAM cache

# Check your current window
status = sensor.get_status()
print(f"Data window: {status['data_window_hours']} hours")
```

### **Automatic Storage Configuration**

- **≤ 24 hours**: Uses fast in-memory storage
- **> 24 hours**: Automatically switches to persistent file storage
- **TTL cleanup**: Old data automatically deleted based on your window size
- **Memory scaling**: RAM usage automatically adjusted based on window size

### **Reading Interval Configuration**

```python
# Default: 30 seconds
sensor.start()  # Takes readings every 30 seconds

# Fast monitoring (10 seconds - good for critical systems)
sensor.start(interval_seconds=10)

# Standard monitoring (1 minute - balanced)
sensor.start(interval_seconds=60)

# Slow monitoring (5 minutes - battery saving)
sensor.start(interval_seconds=300)

# Very slow monitoring (1 hour - long-term trends)
sensor.start(interval_seconds=3600)

# Check current interval
print(f"Reading every {sensor.reading_interval/1000} seconds")
```

**Interval Recommendations:**

- **10-30 seconds**: Critical systems, real-time alerts
- **1-5 minutes**: Standard monitoring, good battery life
- **15-60 minutes**: Long-term data collection, minimal power usage

## 🚨 Alert Cooldown Configuration

**Prevent notification spam with configurable alert cooldowns!**

### **Constructor Configuration**

```python
# 5-minute cooldown (default)
sensor = SimpleDHTML(pin=4, alert_cooldown_minutes=5)

# No cooldown - immediate alerts for critical systems
critical_sensor = SimpleDHTML(pin=4, alert_cooldown_minutes=0)

# Long cooldown for outdoor monitoring
outdoor_sensor = SimpleDHTML(pin=4, alert_cooldown_minutes=15)
```

### **Runtime Configuration**

```python
# Change cooldown anytime
sensor.set_alert_cooldown(10)  # 10 minutes between alerts
sensor.set_alert_cooldown(0)   # Immediate alerts
sensor.set_alert_cooldown(30)  # 30-minute cooldown
```

### **Pre-configured Cooldowns**

```python
# Indoor: 5 minutes (responsive for living spaces)
indoor = create_indoor_sensor(pin=4, alert_cooldown_minutes=5)
```

### **Cooldown Recommendations**

| **Use Case** | **Recommended Cooldown** | **Reason** |
|--------------|-------------------------|------------|
| **Critical systems** | 0-1 minutes | Immediate response needed |
| **Indoor monitoring** | 5 minutes | Balance between responsiveness and spam |
| **Outdoor weather** | 10-15 minutes | Weather changes more slowly |
| **Greenhouse/controlled** | 15-30 minutes | Stable environment, fewer alerts needed |
| **Long-term research** | 30+ minutes | Focus on significant changes only |

### **Alert Status Tracking**

```python
status = sensor.get_status()
print(f"Alert cooldown: {status['alert_settings']['cooldown_minutes']} minutes")
print(f"Last alert: {status['alert_settings']['seconds_since_last_alert']} seconds ago")
```

## 🔧 Additional Customization

```python
# Custom thresholds (in your chosen temperature unit)
sensor.set_thresholds(
    temp_range=[64, 82],      # Fahrenheit range
    humidity_range=[30, 70]   # Humidity percentage
)

# Configure reading intervals
sensor.start(interval_seconds=10)   # Fast monitoring - every 10 seconds
sensor.start(interval_seconds=60)   # Every minute  
sensor.start(interval_seconds=300)  # Every 5 minutes
sensor.start(interval_seconds=3600) # Every hour for long-term monitoring

# Different sensor types with units and windows
dht11_sensor = SimpleDHTML(pin=4, sensor_type='DHT11', temp_unit='F', data_window_hours=24)
dht22_sensor = SimpleDHTML(pin=5, sensor_type='DHT22', temp_unit='C', data_window_hours=168)
```

## 📋 Requirements

- **Hardware**: ESP32/ESP8266 + DHT11 or DHT22 sensor
- **Software**: MicroPython with `machine`, `dht`, and `btree` modules
- **Memory**: ~10KB RAM (basic) to ~25% RAM (advanced analysis)

## 🔍 How It Works

1. **Reads sensor** at your configured interval (default: 30 seconds, range: 10 seconds to hours)
2. **Stores data** in MicroTetherDB with automatic TTL cleanup
3. **Checks thresholds** - alerts if outside your ranges
4. **Detects sudden changes** - compares with recent averages (last 10 readings)
5. **Prevents spam** - Configurable cooldown between similar alerts (default: 5 minutes)
6. **Enables analysis** - Rich querying and statistical functions
7. **Calls your function** when anomalies are detected

## 📈 Performance & Scalability

### **Database Performance**

- **Memory storage**: 2x faster overall performance
- **Query operations**: 33% faster than file storage
- **Batch operations**: 25-167x faster in memory
- **Memory overhead**: Only ~40-60 bytes per reading

### **Recommended Use Cases by Window**

| **Window** | **Use Case** | **Available Metrics** |
|------------|--------------|----------------------|
| **1 hour** | Immediate alerts, sensor validation | Current status, recent trends |
| **24 hours** | Daily pattern analysis, HVAC control | Hourly patterns, daily extremes |
| **7 days** | Weekly trends, seasonal adjustments | Weekly cycles, anomaly baselines |
| **30+ days** | Long-term analysis, predictive maintenance | Seasonal patterns, drift detection |

## 🎁 Bonus: Pre-configured Options

```python
# Available pre-configured sensors with full configuration support:
create_indoor_sensor(pin, alert_callback, temp_unit='C', data_window_hours=24, alert_cooldown_minutes=5)
    # Celsius: 20-26°C, Fahrenheit: 68-79°F, 40-60% humidity, 24-hour window, 5-minute cooldown
```

## 📚 Educational Examples

For learning and research, check out:

- `simple_dht22_ml.py` - Educational ML example with clear code comments
- `simple_sensor_ml.py` - Production-ready implementation (this module)

Both examples show different approaches to environmental monitoring with machine learning on microcontrollers.
