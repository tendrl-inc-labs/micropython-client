# DHT Sensor Examples
## Statistical Analysis for Environmental Monitoring with MicroTetherDB

## 🚀 **2-Minute Quick Start - See the Power Immediately**

```python
# Copy-paste this and see smart monitoring instantly:
from examples.tendrl_dht import create_indoor_sensor

def my_alert(temp, humidity, reason):
    print(f"🚨 SMART ALERT: {reason}")

sensor = create_indoor_sensor(pin=4, alert_callback=my_alert)
sensor.start()

# Now move your sensor near a heat source and watch it detect:
# ✅ Sudden temperature changes from rolling average (not just thresholds!)
# ✅ Context-aware anomalies with automatic data storage
# ✅ Smart alert cooldowns (no notification spam)
# ✅ Automatic TTL cleanup (no manual memory management)
```

**That's it!** In 6 lines you get smart sensor monitoring that would normally take 200+ lines of Arduino code.

📦 **Try This Next**: Want cloud alerts? Just add `enable_cloud_alerts=True`  
📦 **Try This Next**: Want 30 days of data? Change to `data_window_hours=720`  
📦 **Try This Next**: Want greenhouse settings? Use `create_greenhouse_sensor()`  

---

## 🤯 **The "Impossible" Made Simple**

**❌ What it takes WITHOUT MicroTetherDB + Tendrl:**
```c
// For rolling average anomaly detection = 500+ lines
float readings[100];  
int reading_index = 0;
float calculate_average() { /* 20+ lines of manual loops */ }
void detect_anomaly() { /* 40+ lines comparing to fixed thresholds */ }
void manage_circular_buffer() { /* 30+ lines of manual indexing */ }

// For persistent storage = 200+ lines  
void write_to_file() { /* 75+ lines with error handling */ }
void read_from_file() { /* 50+ lines with parsing */ }
void cleanup_old_data() { /* 100+ lines of manual TTL */ }

// For cloud connectivity = 300+ lines
void setup_wifi() { /* 75+ lines with reconnection */ }
void http_post() { /* 100+ lines with retry logic */ }  
void handle_offline() { /* 125+ lines for offline storage */ }

// TOTAL: 1000+ lines for basic smart monitoring
```

**✅ With MicroTetherDB + Tendrl:**
```python
# Same intelligent functionality = 2 lines
sensor = create_indoor_sensor(pin=4, enable_cloud_alerts=True)
sensor.start()
```

**What makes this possible:**

| **Feature** | **Without MicroTetherDB/Tendrl** | **With MicroTetherDB/Tendrl** |
|-------------|----------------------------------|-------------------------------|
| **Rolling averages** | 100+ lines of circular buffers | `db.query({'timestamp': {'$gte': hour_ago}})` |
| **Persistent storage** | 200+ lines of file management | `db.put(data, ttl=7*24*3600)` |
| **Cloud sync** | 300+ lines of HTTP/WiFi code | `client.publish(data, write_offline=True)` |
| **Memory cleanup** | 50+ lines of manual TTL | Automatic with MicroTetherDB |
| **Offline resilience** | 150+ lines of retry logic | Built into Tendrl Client |
| **Time queries** | Impossible with arrays | `{'hour_of_day': 14, 'timestamp': {'$gte': week_ago}}` |

---

## 📁 What's Included

**🎯 `simple_dht.py`** - Powered by MicroTetherDB persistence + Tendrl cloud sync  
**📊 `statistical_examples.py`** - Shows advanced patterns impossible without MicroTetherDB

```python
# Basic monitoring - uses MicroTetherDB for rolling averages
sensor = create_indoor_sensor(pin=4)
sensor.start()

# Advanced analysis - MicroTetherDB enables 30 days of persistent queries
analyzer = LongTermStatisticalAnalysis(pin=4, learning_days=30)
analyzer.take_reading()
```

**Specific MicroTetherDB features demonstrated:**
- **Time-series queries** - `db.query({'hour_of_day': 14, 'timestamp': {'$gte': week_ago}})`
- **Automatic TTL cleanup** - `db.put(data, ttl=30*24*3600)` (no manual memory management)
- **Persistent B-tree storage** - Data survives ESP32 restarts and power cycles
- **MongoDB-style syntax** - Complex queries impossible with traditional arrays/files

**Specific Tendrl Client features demonstrated:**
- **Offline-first publishing** - `client.publish(data, write_offline=True)`
- **Automatic retry and reconnection** - Built-in network resilience
- **Remote monitoring** - Cloud dashboard automatically created
- **Production-ready error handling** - No manual HTTP/WiFi management needed

## 🔧 Configuration Options

```python
# Different environments
indoor = create_indoor_sensor(pin=4, temp_unit='F')     # 68-79°F
outdoor = create_outdoor_sensor(pin=5)                  # 0-40°C  
greenhouse = create_greenhouse_sensor(pin=6)            # 18-30°C

# Data storage options
sensor = SimpleDHTSensor(pin=4, data_window_hours=168)  # 1 week of data

# Custom alerts
def my_alert(temp, humidity, reason):
    print(f"🚨 {reason}")

sensor = SimpleDHTSensor(pin=4, alert_callback=my_alert)

# Cloud integration (requires config.json)
sensor = SimpleDHTSensor(pin=4, enable_cloud_alerts=True)
```

## 🔑 What Makes This Possible

### **MicroTetherDB Enables Smart Analysis**

**❌ Traditional ESP32/Arduino storage:**
```c
float readings[100];  // Fixed size, lost on restart
// Manual file writes - no queries, linear search only
// Manual memory cleanup - complex and error-prone
// No time-based analysis possible
```

**✅ With MicroTetherDB:**
```python
# MongoDB-style queries over weeks of data
week_avg = db.query({
    'hour_of_day': 14,
    'timestamp': {'$gte': week_ago}
})

# Automatic TTL cleanup (no manual memory management)
db.put(sensor_data, ttl=30*24*3600)  # 30 days auto-cleanup

# Persistent B-tree storage (survives restarts)
# Complex time-series analysis with indexed lookups
```

**Key capabilities only possible with MicroTetherDB:**
- **Rolling averages from persistent data** - Traditional: impossible without manual file parsing
- **Time-based anomaly detection** - Traditional: requires complex timestamp management  
- **Weekly/seasonal pattern analysis** - Traditional: extremely difficult with arrays/files
- **Automatic memory management** - Traditional: manual cleanup leads to crashes

### **Tendrl Client Enables Cloud Intelligence**

**❌ Traditional ESP32 cloud connection:**
```c
// 150+ lines for basic WiFi + HTTP POST
void setup_wifi() { /* 50+ lines */ }
void send_data() { /* 75+ lines of HTTP handling */ }
void handle_failures() { /* Manual retry logic */ }
// No offline storage, no automatic reconnection
```

**✅ With Tendrl Client:**
```python
# One line for cloud sync with offline fallbacks
client.publish(sensor_data, write_offline=True)

# Automatic reconnection, retry logic, compression
# Built-in offline storage when network fails
# Remote monitoring dashboard automatically created
```

**Key capabilities only possible with Tendrl:**
- **Offline-first design** - Data stored locally when network fails, synced when reconnected
- **Automatic retry and compression** - Traditional: complex manual implementation
- **Remote threshold updates** - Traditional: requires custom server + OTA updates
- **Production-ready IoT resilience** - Traditional: hundreds of lines of error handling

### **The Combination Creates "Impossible" Features**

```python
# This single example does what would require 500+ lines of C code:
sensor = create_indoor_sensor(pin=4, enable_cloud_alerts=True)
sensor.start()

# Behind the scenes this provides:
# ✅ Persistent storage (MicroTetherDB)
# ✅ Rolling average anomaly detection (MicroTetherDB time queries)  
# ✅ Cloud alerts with offline fallback (Tendrl)
# ✅ Automatic memory cleanup (MicroTetherDB TTL)
# ✅ Remote monitoring dashboard (Tendrl)
# ✅ Production-ready error handling (Both)
```

## 💾 Hardware Requirements

**Minimum:** ESP32 + DHT22 sensor (2MB+ RAM recommended)  
**Recommended:** ESP32 with 8MB RAM for advanced patterns  
**Advanced:** Boards like FeatherS3 (16MB flash + 8MB PSRAM) for months of data

## ☁️ Cloud Features (Optional)

Add `enable_cloud_alerts=True` for:
- Real-time alerts to Tendrl platform
- Offline storage when network fails
- Remote monitoring dashboard

*Requires `config.json` with Tendrl credentials*



## 🔍 Troubleshooting

### Quick Fixes for Common Issues:

**❓ Getting "MicroTetherDB not available" message?**
- ✅ **This is normal!** Examples work in demo mode without the full database
- 📦 **Want full features?** Install MicroTetherDB for persistent storage

**❓ Getting "Timer not available" message?**  
- ✅ **This is normal!** Running without hardware for development/testing
- 📦 **On real hardware?** Examples automatically detect and use timers

**❓ Getting memory errors?**
- 📦 **Easy fix:** Use shorter data windows: `data_window_hours=24` instead of `720`
- 📦 **For advanced patterns:** Use `learning_days=7` instead of `30`

**❓ Sensor not working?**
- 📦 **Check wiring:** DHT22 data pin to GPIO, VCC to 3.3V, GND to GND
- 📦 **Try different pin:** `create_indoor_sensor(pin=5)` if pin 4 doesn't work

## 🎯 Next Steps

**Just want it to work?** Use the 2-minute quick start above.

**Want to explore more?**
- Try different environments: `create_greenhouse_sensor()`, `create_outdoor_sensor()`
- Add cloud alerts: `enable_cloud_alerts=True`
- Advanced patterns: See `statistical_examples.py` for weeks of data analysis

**Ready for production?** Customize alert thresholds, data windows, and cloud integration.
