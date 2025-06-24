# DHT Sensor Examples
## Statistical Analysis for Environmental Monitoring with MicroTetherDB

This directory contains focused examples of using MicroTetherDB for DHT temperature and humidity sensor statistical analysis applications. All examples have been simplified into **3 main files** for easy understanding and usage.

## 📁 File Structure

### 🎯 `simple_dht.py` - **Start Here!**
**Perfect for beginners** - Plug-and-play anomaly detection with minimal setup.

```python
from simple_dht import SimpleDHTAnalytics, create_indoor_sensor

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

### 📊 `statistical_examples.py` - **Example Patterns** 

1. **`LongTermStatisticalAnalysis`** - Analyze WEEKS of persistent data (~70 lines)
2. **`CloudTrendAnalysis`** - Cloud-synced trend analysis with offline storage (~60 lines)
3. **`CloudAdaptiveStatistics`** - Bidirectional cloud feedback statistics (~80 lines)

```python
from statistical_examples import LongTermStatisticalAnalysis, CloudTrendAnalysis, CloudAdaptiveStatistics

# Analyze 30 days of data - extremely difficult with traditional storage!
long_term = LongTermStatisticalAnalysis(pin=4, learning_days=30)
long_term.take_reading()  # Analyzes weekly/seasonal patterns

# Cloud-synced trends with offline storage
cloud_trends = CloudTrendAnalysis(pin=4, sync_interval_minutes=30)
cloud_trends.take_reading()  # Syncs to cloud, works offline

# Adaptive statistics with cloud intelligence
adaptive = CloudAdaptiveStatistics(pin=4)
adaptive.take_reading()  # Cloud-enhanced adaptation
```

**✅ ENABLED by MicroTetherDB + Tendrl:**
- **Weeks of persistent data**: File storage with efficient TTL cleanup
- **Cloud intelligence**: Bidirectional sync with offline storage
- **Advanced queries**: `{'hour_of_day': 14, 'timestamp': {'$gte': week_ago}}`
- **25-167x faster** than traditional file storage
- **Remote monitoring**: Cloud dashboards and alerts

## 🚀 Quick Start Guide

### 1. **Just Want Alerts?** → Use `simple_dht.py`
```python
from simple_dht import create_indoor_sensor

sensor = create_indoor_sensor(pin=4)
sensor.start()
```

### 2. **Want to Learn Statistical Patterns?** → Use `statistical_examples.py`  
```python
from statistical_examples import LongTermStatisticalAnalysis

# Simple statistical pattern demonstration
analyzer = LongTermStatisticalAnalysis(pin=4, learning_days=7)
for i in range(30):
    analyzer.take_reading()
    time.sleep(30)  # Take reading every 30 seconds
```

### 3. **Want Production Examples?** → Build from the patterns above
The statistical patterns in `statistical_examples.py` can be combined and extended for production use.

## 📊 Statistical Patterns Explained

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

#### 1. **Long-Term Statistical Analysis** (~70 lines)
```python
# Analyze statistical patterns from weeks of data
long_term = LongTermStatisticalAnalysis(pin=4, learning_days=30)
long_term.take_reading()  # Calculates deviations, detects anomalies
```
- **What it does**: Calculates averages and deviations, detects statistical outliers
- **MicroTetherDB advantage**: Efficient retrieval of weeks of historical data
- **Memory**: ~25KB RAM

#### 2. **Cloud Trend Analysis** (~60 lines)  
```python
# Detect trends and sync to cloud
trends = CloudTrendAnalysis(pin=4, sync_interval_minutes=30)
trends.take_reading()  # Detects rising/falling trends, syncs to cloud
```
- **What it does**: Analyzes temperature change rates (°C per hour) with cloud sync
- **MicroTetherDB advantage**: Time-based queries for trend analysis + cloud storage
- **Memory**: ~20KB RAM

#### 3. **Adaptive Statistics** (~80 lines)
```python
# Adapt thresholds based on historical data
adaptive = CloudAdaptiveStatistics(pin=4)
adaptive.take_reading()  # Adapts thresholds using percentiles
```
- **What it does**: Uses percentiles to adapt normal ranges, with cloud feedback
- **MicroTetherDB advantage**: Historical data analysis with complex queries
- **Memory**: ~30KB RAM

## 🎛️ Configuration Examples

### Temperature Units
```python
# Fahrenheit
sensor = SimpleDHTAnalytics(pin=4, temp_unit='F')
sensor.set_thresholds(temp_range=[68, 79])  # °F

# Celsius  
sensor = SimpleDHTAnalytics(pin=4, temp_unit='C')
sensor.set_thresholds(temp_range=[20, 26])  # °C
```

### Data Storage Windows
```python
# Short-term (1 hour) - uses RAM only
sensor = SimpleDHTAnalytics(pin=4, data_window_hours=1)

# Medium-term (24 hours) - uses RAM with TTL
sensor = SimpleDHTAnalytics(pin=4, data_window_hours=24)

# Long-term (7 days) - uses file storage  
sensor = SimpleDHTAnalytics(pin=4, data_window_hours=168)
```

### Alert Customization
```python
def my_custom_alert(temp, humidity, reason):
    print(f"🚨 ALERT: {temp}°C, {humidity}% - {reason}")
    # Send email, SMS, webhook, etc.
    
sensor = SimpleDHTAnalytics(pin=4, alert_callback=my_custom_alert)
sensor.set_alert_cooldown(minutes=10)  # 10 min between similar alerts
```

### Cloud Integration
```python
# Enable cloud alerts (requires config.json)
sensor = SimpleDHTAnalytics(
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
- **2MB+ RAM** recommended for learning patterns
- **512KB+ flash** for data storage

### Recommended Setup:
- **ESP32** with 8MB RAM
- **DHT22** sensors (better accuracy than DHT11)
- **WiFi connection** for cloud features

### 🚀 **Advanced Setup - Massive Scale Possible:**
Modern boards like the **Unexpected Maker FeatherS3** enable unprecedented statistical analysis capabilities:

- **16MB QSPI Flash** - Store **months/years** of sensor data locally
- **8MB Extra QSPI PSRAM** - Massive in-memory datasets for complex statistical analysis
- **ESP32-S3** - Dual-core processing for real-time statistical analysis + cloud sync

**With this hardware + MicroTetherDB:**
```python
# MASSIVE long-term analysis - extremely difficult before!
massive_analyzer = LongTermStatisticalAnalysis(pin=4, learning_days=365)  # 1 YEAR of data!

# Multiple sensors with complex statistical analysis
multi_sensor_system = {
    'indoor': LongTermStatisticalAnalysis(pin=4, learning_days=180),
    'outdoor': LongTermStatisticalAnalysis(pin=5, learning_days=180), 
    'greenhouse': LongTermStatisticalAnalysis(pin=6, learning_days=180),
    'basement': LongTermStatisticalAnalysis(pin=7, learning_days=180)
}

# Advanced statistical analysis with 8MB PSRAM for in-memory processing
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

**Realistic Storage Strategies for Microcontrollers:**
```python
# PRACTICAL: High-frequency short-term (every 30 seconds for 1 week)
short_term = LongTermStatisticalAnalysis(pin=4, learning_days=7)     # ~500KB, very responsive

# PRACTICAL: Medium-frequency medium-term (every 5 minutes for 30 days) 
medium_term = LongTermStatisticalAnalysis(pin=4, learning_days=30)   # ~2MB, good performance
# Configure: take_reading() called every 5 minutes instead of 30 seconds

# PRACTICAL: Low-frequency long-term (every 30 minutes for 6 months)
long_term = LongTermStatisticalAnalysis(pin=4, learning_days=180)    # ~4MB, slower but usable
# Configure: take_reading() called every 30 minutes

# SMART STRATEGY: Hierarchical storage with data summarization
class SmartLongTermStorage:
    def __init__(self):
        # Recent data: every 1 minute for 24 hours (~1MB)
        self.recent_db = MicroTetherDB(filename="recent_1min.db")
        
        # Daily summaries: min/max/avg for 1 year (~50KB)
        self.daily_db = MicroTetherDB(filename="daily_summaries.db")
        
    def store_reading(self, temp, humidity):
        # Store recent reading with 24h TTL
        self.recent_db.put({
            'temp': temp, 'humidity': humidity, 'timestamp': time.time()
        }, ttl=24*3600)
        
        # Create daily summary (much smaller!)
        if self._is_end_of_day():
            daily_summary = self._create_daily_summary()
            self.daily_db.put(daily_summary, ttl=365*24*3600)  # 1 year
```

**The Real Value - Database Capabilities on Microcontrollers:**
1. **Structured Storage**: JSON-like documents instead of manual parsing
2. **Query Language**: MongoDB-style queries instead of linear search
3. **Automatic Indexing**: Fast lookups instead of scanning all data
4. **TTL Management**: Automatic cleanup instead of manual memory management
5. **Persistence**: Data survives restarts instead of RAM-only storage

**Production Recommendations for Real Microcontrollers:**
```python
# TYPICAL ESP32 (4MB flash): Smart frequency management
class ProductionSensorSystem:
    def __init__(self):
        # High frequency for anomaly detection (last 4 hours)
        self.realtime_db = MicroTetherDB(
            filename="realtime.db",
            ram_percentage=30  # ~300KB for 4-hour buffer
        )
        
        # Medium frequency for trend analysis (last 7 days) 
        self.trends_db = MicroTetherDB(
            filename="trends.db", 
            ram_percentage=20   # ~1MB for weekly patterns
        )
    
    def take_reading(self, temp, humidity):
        now = time.time()
        
        # Store every reading for immediate anomaly detection
        self.realtime_db.put({
            'temp': temp, 'humidity': humidity, 'timestamp': now
        }, ttl=4*3600)  # 4 hours only
        
        # Store every 10th reading (5-minute intervals) for trends
        if self.reading_count % 10 == 0:
            self.trends_db.put({
                'temp': temp, 'humidity': humidity, 'timestamp': now,
                'hour': int((now % 86400) / 3600)
            }, ttl=7*24*3600)  # 1 week

# Result: ~1.5MB total storage, fits comfortably on ESP32
sensor_system = ProductionSensorSystem()
```

**Bottom Line**: This brings **database-like capabilities** to microcontrollers, enabling **basic statistical analysis** that was previously impractical due to storage and query limitations.

## 🌐 Cloud Features (Optional)

When using `simple_dht.py` with `enable_cloud_alerts=True`:
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
analyzer = LongTermStatisticalAnalysis(pin=4, learning_days=7)  # Shorter period
```

## 📚 Learning Path

### Beginner (5 minutes):
1. Try `create_indoor_sensor()` from `simple_dht.py`
2. Adjust temperature ranges for your needs

### Intermediate (15 minutes):
1. Explore `LongTermStatisticalAnalysis` from `statistical_examples.py`
2. Understand how MicroTetherDB enables the statistical analysis patterns

### Advanced (30 minutes):
1. Try all 3 statistical analysis patterns in `statistical_examples.py`
2. Set up cloud integration with Tendrl
3. Combine patterns for custom applications

## 🤝 Enhanced Data Analysis for Microcontrollers

These examples demonstrate **statistical analysis patterns that were previously impractical** on microcontrollers due to storage and query limitations:

-----

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
```

**Traditional Microcontroller Limitations:**
- **Arrays**: Fixed size, RAM-only, lost on restart, no time queries
- **EEPROM**: Tiny capacity (1-4KB), wear leveling issues, no indexing
- **Flash Files**: Manual string parsing, no queries, linear search only
- **JSON Files**: Seems easier but creates major problems (see example below)
- **SD Cards**: Requires extra hardware, manual file management, no SQL
- **Result**: Only basic data logging, NO sophisticated analysis possible

**🚫 COMMON BUT PROBLEMATIC: JSON File Approach**

```python
# What many people try - seems simple but becomes VERY problematic
import json

def store_reading_json(temp, humidity):
    # PROBLEM 1: Must read entire file into RAM every time!
    try:
        with open('sensor_data.json', 'r') as f:
            data = json.load(f)  # Loads ENTIRE file - memory killer!
    except:
        data = []
    
    # PROBLEM 2: No TTL - file grows forever until device crashes
    data.append({
        'temp': temp,
        'humidity': humidity, 
        'timestamp': time.time()
    })
    
    # PROBLEM 3: Rewrite entire file every time - VERY slow
    with open('sensor_data.json', 'w') as f:
        json.dump(data, f)  # Rewrites everything!

def get_last_hour_readings():
    # PROBLEM 4: Must load entire file and search linearly
    with open('sensor_data.json', 'r') as f:
        all_data = json.load(f)  # Entire file in RAM again!
    
    one_hour_ago = time.time() - 3600
    recent = []
    
    # PROBLEM 5: No indexing - must check every record
    for record in all_data:  # Linear search through thousands!
        if record['timestamp'] >= one_hour_ago:
            recent.append(record)
    
    return recent

# RESULT: 
# - After 1 week: 20MB+ JSON file, device crashes from RAM usage
# - Queries take 10+ seconds as file grows  
# - No automatic cleanup - manual housekeeping nightmare
# - File corruption kills all historical data
```

**Why JSON Files Fail on Microcontrollers:**
- **Memory exhaustion**: Must load entire file for any operation
- **Performance degradation**: Linear search through thousands of records  
- **No data management**: Files grow until device crashes
- **Write amplification**: Rewriting entire file for each new record
- **No atomic operations**: Power loss can corrupt entire dataset
- **No time-series optimization**: Every query scans all data

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

# Complex queries that were extremely difficult on microcontrollers before:
last_week_2pm = db.query({
    'hour_of_day': 14,
    'timestamp': {'$gte': time.time() - 7*24*3600}
})

# This single query would require THOUSANDS of lines of C code
# on traditional Arduino/ESP32 platforms!
```

**MicroTetherDB Breakthrough on Constrained Devices:**
- **MongoDB-style queries**: Complex queries on 64KB RAM devices!
- **Persistent B-tree storage**: Data survives restarts and power loss
- **Automatic indexing**: Fast queries even with thousands of records
- **TTL management**: Automatic cleanup of old data
- **Memory efficiency**: Works within severe RAM constraints
- **Time-series analysis**: Efficient date/time range queries
- **Dynamic sizing**: Grows/shrinks based on available storage

**The combination of MicroTetherDB's structured storage + query capabilities + Tendrl's cloud sync enables sophisticated data analysis on constrained microcontrollers that was previously only practical on full OS devices.**

---

**💡 Pro Tip**: Start with `simple_dht.py` for immediate results, then explore `statistical_examples.py` to understand how MicroTetherDB enables statistical analysis patterns that would be extremely difficult with traditional storage!
