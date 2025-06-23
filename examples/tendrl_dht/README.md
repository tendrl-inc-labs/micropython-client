# DHT Sensor ML Examples - Simple Learning Patterns
## Machine Learning for Environmental Monitoring with MicroTetherDB

This directory contains focused examples of using MicroTetherDB for DHT sensor machine learning applications. All examples have been simplified into **3 main files** for easy understanding and usage.

## 📁 File Structure

### 🎯 `simple_sensor_ml.py` - **Start Here!**
**Perfect for beginners** - Plug-and-play anomaly detection with minimal setup.

```python
from simple_sensor_ml import SimpleDHTML, create_indoor_sensor

# One-line setup for indoor monitoring
sensor = create_indoor_sensor(pin=4, temp_unit='F')
sensor.start()  # That's it!
```

**Features:**
- 🔧 **Plug-and-play** - Just set pin and go
- 🌡️ **Fahrenheit/Celsius** support  
- ⏰ **Configurable data windows** (1 hour to 30 days)
- 🔔 **Smart alert cooldowns** (prevent spam)
- ☁️ **Optional cloud alerts** via Tendrl
- 🏠 **Pre-built configurations** (indoor, outdoor, greenhouse)
- 📊 **Context analysis** with rolling windows
- 💾 **Automatic data management** with TTL

### 🧠 `ml_examples.py` - **Impossible-Before ML Patterns** 
**Revolutionary capabilities** - Shows ML patterns that were IMPOSSIBLE with traditional microcontroller storage.

Contains **3 breakthrough patterns:**

1. **`LongTermLearning`** - Learn from WEEKS of persistent data (~70 lines)
2. **`CloudTrendLearning`** - Cloud-synced intelligence with offline storage (~60 lines)
3. **`CloudAdaptiveLearning`** - Bidirectional cloud feedback learning (~80 lines)

```python
from ml_examples import LongTermLearning, CloudTrendLearning, CloudAdaptiveLearning

# Learn from 30 days of data - impossible with traditional storage!
long_term = LongTermLearning(pin=4, learning_days=30)
long_term.take_reading()  # Learns weekly/seasonal patterns

# Cloud-synced trends with offline storage
cloud_trends = CloudTrendLearning(pin=4, sync_interval_minutes=30)
cloud_trends.take_reading()  # Syncs to cloud, works offline

# Adaptive learning with cloud intelligence
adaptive = CloudAdaptiveLearning(pin=4)
adaptive.take_reading()  # Cloud-enhanced adaptation
```

**🚫 IMPOSSIBLE Without MicroTetherDB + Tendrl:**
- Long-term learning (weeks/months of data)
- Cloud sync with offline storage
- Bidirectional cloud intelligence
- Time-series queries over persistent data
- Seasonal pattern recognition

**✅ ENABLED by MicroTetherDB + Tendrl:**
- **Weeks of persistent data**: File storage with efficient TTL cleanup
- **Cloud intelligence**: Bidirectional sync with offline storage
- **Advanced queries**: `{'hour_of_day': 14, 'timestamp': {'$gte': week_ago}}`
- **25-167x faster** than traditional file storage
- **Remote monitoring**: Cloud dashboards and alerts



## 🚀 Quick Start Guide

### 1. **Just Want Alerts?** → Use `simple_sensor_ml.py`
```python
from simple_sensor_ml import create_indoor_sensor

sensor = create_indoor_sensor(pin=4)
sensor.start()
```

### 2. **Want to Learn ML Patterns?** → Use `ml_examples.py`  
```python
from ml_examples import StatisticalLearning

# Simple learning pattern demonstration
learner = StatisticalLearning(pin=4, window_size=15)
for i in range(30):
    learner.take_reading()
    time.sleep(30)  # Take reading every 30 seconds
```

### 3. **Want Production Examples?** → Build from the patterns above
The learning patterns in `ml_examples.py` can be combined and extended for production use.

## 🧠 Learning Patterns Explained

### Why MicroTetherDB Makes This Possible

**Without MicroTetherDB (traditional approach):**
```python
# Limited to simple arrays - manual memory management
readings = []  # Fixed size, manual cleanup needed
if len(readings) > 100:
    readings.pop(0)  # Manual memory management

# Or slow file operations
with open('data.txt', 'a') as f:  # Slow, hard to query
    f.write(f"{temp},{humidity}\n")
```

**With MicroTetherDB (our approach):**
```python
# Efficient queries with automatic cleanup
recent_data = db.query({
    'timestamp': {'$gte': now - 3600},  # Last hour
    'temp': {'$exists': True}
})  # 25-167x faster than files, automatic TTL cleanup
```

### The 3 Core Patterns:

#### 1. **Statistical Learning** (~50 lines)
```python
# Learn what's "normal" and detect outliers
stats = StatisticalLearning(pin=4, window_size=20)
stats.take_reading()  # Calculates Z-scores, detects anomalies
```
- **What it does**: Learns average and standard deviation, detects statistical outliers
- **MicroTetherDB advantage**: Efficient retrieval of recent N readings
- **Memory**: ~10KB RAM

#### 2. **Trend Learning** (~40 lines)  
```python
# Detect gradual changes over time
trends = TrendLearning(pin=4, trend_minutes=30)
trends.take_reading()  # Detects rising/falling trends
```
- **What it does**: Analyzes temperature change rates (°C per hour)
- **MicroTetherDB advantage**: Time-based queries for trend analysis
- **Memory**: ~15KB RAM

#### 3. **Adaptive Learning** (~60 lines)
```python
# Learn normal ranges from actual data
adaptive = AdaptiveLearning(pin=4)
adaptive.take_reading()  # Adapts thresholds based on history
```
- **What it does**: Uses percentiles to learn normal ranges, adapts over time
- **MicroTetherDB advantage**: Historical data analysis with complex queries
- **Memory**: ~20KB RAM

## 🎛️ Configuration Examples

### Temperature Units
```python
# Fahrenheit
sensor = SimpleDHTML(pin=4, temp_unit='F')
sensor.set_thresholds(temp_range=[68, 79])  # °F

# Celsius  
sensor = SimpleDHTML(pin=4, temp_unit='C')
sensor.set_thresholds(temp_range=[20, 26])  # °C
```

### Data Storage Windows
```python
# Short-term (1 hour) - uses RAM only
sensor = SimpleDHTML(pin=4, data_window_hours=1)

# Medium-term (24 hours) - uses RAM with TTL
sensor = SimpleDHTML(pin=4, data_window_hours=24)

# Long-term (7 days) - uses file storage  
sensor = SimpleDHTML(pin=4, data_window_hours=168)
```

### Alert Customization
```python
def my_custom_alert(temp, humidity, reason):
    print(f"🚨 ALERT: {temp}°C, {humidity}% - {reason}")
    # Send email, SMS, webhook, etc.
    
sensor = SimpleDHTML(pin=4, alert_callback=my_custom_alert)
sensor.set_alert_cooldown(minutes=10)  # 10 min between similar alerts
```

### Cloud Integration
```python
# Enable cloud alerts (requires config.json)
sensor = SimpleDHTML(
    pin=4,
    enable_cloud_alerts=True,
    device_name="Living Room Sensor",
    location="Home"
)
```

## 📊 Comparison: Traditional vs MicroTetherDB

| Feature | Traditional Files | Simple Arrays | MicroTetherDB |
|---------|------------------|---------------|---------------|
| **Query Speed** | Slow (full file read) | Fast (limited size) | **Indexed lookups** |
| **Memory Management** | Manual | Manual | **Automatic TTL** |
| **Complex Queries** | Manual parsing | Linear search | **MongoDB-style syntax** |
| **Time-series** | Very difficult | Limited | **Built-in time queries** |
| **Data Persistence** | Yes | No | **Configurable** |
| **Analysis Capability** | Basic logging | Very limited | **Statistical patterns** |

## 🔧 Hardware Requirements & Scaling

### Minimum Setup:
- **ESP32** or similar MicroPython board
- **DHT22** sensor (or DHT11 for basic use)
- **4MB+ RAM** recommended for learning patterns
- **512KB+ flash** for data storage

### Recommended Setup:
- **ESP32** with 8MB RAM
- **DHT22** sensors (better accuracy than DHT11)
- **WiFi connection** for cloud features

### 🚀 **Advanced Setup - Massive Scale Possible:**
Modern boards like the **Unexpected Maker FeatherS3** enable unprecedented ML capabilities:

- **16MB QSPI Flash** - Store **months/years** of sensor data locally
- **8MB Extra QSPI PSRAM** - Massive in-memory datasets for complex ML
- **ESP32-S3** - Dual-core processing for real-time ML + cloud sync

**With this hardware + MicroTetherDB:**
```python
# MASSIVE long-term learning - impossible before!
massive_learner = LongTermLearning(pin=4, learning_days=365)  # 1 YEAR of data!

# Multiple sensors with complex ML
multi_sensor_system = {
    'indoor': LongTermLearning(pin=4, learning_days=180),
    'outdoor': LongTermLearning(pin=5, learning_days=180), 
    'greenhouse': LongTermLearning(pin=6, learning_days=180),
    'basement': LongTermLearning(pin=7, learning_days=180)
}

# Advanced ML with 8MB PSRAM for in-memory processing
advanced_db = MicroTetherDB(
    in_memory=True,
    ram_percentage=80,  # Use most of the 8MB PSRAM!
    filename="yearly_climate_data.db"  # 16MB flash backup
)
```

**Scale Comparison:**

| Hardware | Flash | RAM | Data Storage | Learning Period |
|----------|-------|-----|--------------|-----------------|
| **Basic ESP32** | 4MB | 320KB | Days | Hours-Days |
| **ESP32 (8MB)** | 4MB | 8MB | Weeks | Days-Weeks |
| **FeatherS3** | **16MB** | **8MB PSRAM** | **Months-Years** | **Seasonal-Annual** |


### ⚠️ **Realistic Capabilities & Constraints:**

**What This Actually Enables:**
- **Simple pattern detection**: Threshold-based anomaly detection
- **Basic trend analysis**: Compare current vs historical averages
- **Time-based queries**: Find data by hour/day patterns
- **Persistent storage**: Data survives restarts (major improvement for microcontrollers)

**What This Is NOT:**
- **Not "AI" or "Deep Learning"**: These are statistical analysis patterns
- **Not Enterprise ML**: Limited by microcontroller processing power
- **Not Real-time**: Constrained by single-threaded execution
- **Not Unlimited Scale**: Storage and query performance have limits

**Realistic Storage Performance:**
```python
# PRACTICAL: Good performance for microcontroller applications
short_term = LongTermLearning(pin=4, learning_days=7)     # ~10MB, responsive
medium_term = LongTermLearning(pin=4, learning_days=30)   # ~50MB, slower queries

# CHALLENGING: Possible but with performance trade-offs
long_term = LongTermLearning(pin=4, learning_days=90)     # ~150MB, slow queries

# AVOID: Likely too slow for practical use
massive_term = LongTermLearning(pin=4, learning_days=365) # ~600MB, very slow
```

**The Real Value - Database Capabilities on Microcontrollers:**
1. **Structured Storage**: JSON-like documents instead of manual parsing
2. **Query Language**: MongoDB-style queries instead of linear search
3. **Automatic Indexing**: Fast lookups instead of scanning all data
4. **TTL Management**: Automatic cleanup instead of manual memory management
5. **Persistence**: Data survives restarts instead of RAM-only storage

**Production Recommendations:**
```python
# Realistic approach for microcontroller constraints
practical_storage = LongTermLearning(
    pin=4, 
    learning_days=14,          # 2 weeks detailed data
    summary_retention_days=90  # 3 months of hourly summaries
)
```

**Bottom Line**: This brings **database-like capabilities** to microcontrollers, enabling **basic statistical analysis** that was previously impractical due to storage and query limitations.

## 🌐 Cloud Features (Optional)

When using `simple_sensor_ml.py` with `enable_cloud_alerts=True`:
- **Real-time alerts** sent to Tendrl cloud platform
- **Offline storage** when network is unavailable
- **Multi-device management** from single interface

Requires `config.json` with your Tendrl credentials.

## 🔍 Troubleshooting

### Common Issues:

**1. "MicroTetherDB not available"**
```python
# Normal - examples detect this and work in demo mode
# Install MicroTetherDB to enable full functionality
```

**2. "Timer not available"**  
```python
# Running without hardware - this is normal for development/testing
# All examples detect hardware availability automatically
```

**3. Memory errors:**
```python
# Reduce window sizes for learning patterns
learner = StatisticalLearning(pin=4, window_size=10)  # Smaller window
```

## 📚 Learning Path

### Beginner (5 minutes):
1. Try `create_indoor_sensor()` from `simple_sensor_ml.py`
2. Adjust temperature ranges for your needs

### Intermediate (15 minutes):
1. Explore `StatisticalLearning` from `ml_examples.py`
2. Understand how MicroTetherDB enables the learning patterns

### Advanced (30 minutes):
1. Try all 3 learning patterns in `ml_examples.py`
2. Set up cloud integration with Tendrl
3. Combine patterns for custom applications

## 🤝 Database Capabilities for MicroPython

These examples demonstrate **structured data analysis patterns** that were **impractical before** due to storage and query limitations on microcontrollers:

### 📱 **Target: Constrained Microcontrollers (NOT Full OS Devices)**

**What we mean by "microcontroller":**
- **ESP32, ESP8266, Arduino, STM32, RP2040** - No operating system, bare metal/RTOS
- **MicroPython/CircuitPython** - Minimal runtime, severe memory constraints
- **NOT Raspberry Pi** - Pi runs full Linux OS with databases, file systems, etc.
- **NOT Desktop/Server** - Full computers have unlimited storage/processing

**Key Constraints of True Microcontrollers:**
- **Limited RAM**: 32KB-8MB total (vs Pi's 1-8GB)
- **No OS Services**: No file system, databases, or complex libraries
- **No SQL Engines**: No PostgreSQL, MySQL, SQLite, or database servers
- **Restart = Data Loss**: RAM-only storage disappears on power cycle
- **Linear Search Only**: No indexing, B-trees, or query optimization
- **Single-threaded**: Limited processing power and concurrency

**🚫 BEFORE (Traditional Constrained Microcontroller Storage):**

```c
// Arduino/ESP32 traditional approach - SEVERELY LIMITED
float temp_readings[100];  // Fixed size array, RAM only
int reading_count = 0;

void store_reading(float temp) {
    if (reading_count < 100) {
        temp_readings[reading_count++] = temp;
    }
    // PROBLEMS:
    // 1. Data lost on restart/power cycle!
    // 2. No time-based queries possible!
    // 3. Fixed size - can't grow dynamically!
    // 4. No persistence across reboots!
}

// Want last week's 2PM readings? IMPOSSIBLE!
// Want temperature trends over time? IMPOSSIBLE!  
// Want to query by date/time? IMPOSSIBLE!
// Want automatic data cleanup? IMPOSSIBLE!
```

**Traditional Microcontroller Limitations:**
- **Arrays**: Fixed size, RAM-only, lost on restart, no time queries
- **EEPROM**: Tiny capacity (1-4KB), wear leveling issues, no indexing
- **Flash Files**: Manual string parsing, no queries, linear search only
- **SD Cards**: Requires extra hardware, manual file management, no SQL
- **Result**: Only basic data logging, NO sophisticated analysis possible

**✅ AFTER (MicroTetherDB on Constrained Microcontrollers):**

```python
# ESP32 with MicroTetherDB - BREAKTHROUGH CAPABILITIES!
db = MicroTetherDB(filename="sensor_data.db")  # Persistent across restarts!

# Store with automatic indexing, TTL, and persistence
db.put({
    'temp': 24.5, 
    'humidity': 65.0,
    'timestamp': time.time(),
    'hour_of_day': 14,
    'day_of_week': 1
}, ttl=30*24*3600)  # 30 days automatic cleanup

# Complex queries that were IMPOSSIBLE on microcontrollers before:
last_week_2pm = db.query({
    'hour_of_day': 14,
    'timestamp': {'$gte': time.time() - 7*24*3600}
})

# This single query would require THOUSANDS of lines of C code
# on traditional Arduino/ESP32 platforms!
```

**MicroTetherDB Breakthrough on Constrained Devices:**
- **MongoDB-style queries**: Complex queries on 32KB RAM devices!
- **Persistent B-tree storage**: Data survives restarts and power loss
- **Automatic indexing**: Fast queries even with thousands of records
- **TTL management**: Automatic cleanup of old data
- **Memory efficiency**: Works within severe RAM constraints
- **Time-series analysis**: Efficient date/time range queries
- **Dynamic sizing**: Grows/shrinks based on available storage

**The combination of MicroTetherDB's structured storage + query capabilities + Tendrl's cloud sync makes database-driven IoT applications practical on constrained microcontrollers for the first time.**

## 📄 License

Same as parent project - see LICENSE file.

---

**💡 Pro Tip**: Start with `simple_sensor_ml.py` for immediate results, then explore `ml_examples.py` to understand how MicroTetherDB enables learning patterns that would be impossible with traditional storage!
