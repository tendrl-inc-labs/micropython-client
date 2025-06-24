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

**That's it!** You now have MongoDB-style time-series queries, persistent B-tree storage, and production-ready cloud sync on a microcontroller.

> 📌 **Hardware needed:** DHT22 sensor connected to GPIO pin 4 (or change `pin=4` to your wiring).

📦 **Try This Next**: Want cloud alerts? Just add `enable_cloud_alerts=True`  
📦 **Try This Next**: Want 30 days of data? Change to `data_window_hours=720`  
📦 **Try This Next**: Want greenhouse settings? Use `create_greenhouse_sensor()`  

---

## 🚀 **Database & Cloud Sophistication on Microcontrollers**

**❌ Traditional microcontroller limitations:**
```c
// Fixed arrays - no persistence, no queries
float readings[100];  // Lost on restart, linear search only

// Basic files - manual parsing, no indexing
FILE *fp = fopen("data.txt", "a");  // No structured queries

// Manual HTTP - basic POST only
http_post(url, data);  // No retry, no offline storage
```

**✅ MicroTetherDB + Tendrl brings enterprise-grade capabilities:**
```python
# MongoDB-style queries with automatic indexing
recent_data = db.query({
    'hour_of_day': 14,
    'timestamp': {'$gte': week_ago}
})

# Production-ready cloud sync with offline resilience  
client.publish(sensor_data, write_offline=True)
```

**Technical sophistication that changes everything:**

| **Capability** | **Traditional Microcontroller** | **MicroTetherDB + Tendrl** |
|----------------|--------------------------------|----------------------------|
| **Query Performance** | Linear search through arrays | **B-tree indexed lookups** |
| **Time-Series Analysis** | Manual timestamp comparison | **Native time-range queries** |
| **Data Persistence** | Volatile RAM or manual files | **Automatic B-tree storage** |
| **Memory Management** | Manual cleanup and overflow | **Automatic TTL with indexing** |
| **Cloud Resilience** | Basic HTTP POST | **Offline-first with batching** |
| **Network Handling** | Manual retry loops | **WebSocket with auto-reconnect** |

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
- **Cloud data publishing** - Sends sensor data to Tendrl platform
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

## 🔑 Key Technical Capabilities

### **MicroTetherDB: Persistent Storage with Queries**
- **B-tree indexing** - Fast lookups vs linear array searches
- **MongoDB-style queries** - `db.query({'timestamp': {'$gte': week_ago}})`
- **Automatic TTL cleanup** - `db.put(data, ttl=30*24*3600)` no manual memory management
- **Persistent storage** - Data survives power cycles and restarts

### **Tendrl Client: Production IoT Networking**
- **WebSocket connections** - Real-time bidirectional communication
- **Message batching** - Efficient network usage with smart chunking  
- **Offline-first** - Local storage syncs when network reconnects
- **Auto-reconnection** - Handles network failures gracefully

### **Combined Result**
```python
# Weeks of persistent data + cloud sync on microcontrollers
recent_data = db.query({'timestamp': {'$gte': week_ago}})
client.publish(sensor_data, write_offline=True)
```

## 💾 Hardware Requirements

**Minimum:** ESP32 + DHT22 sensor (2MB+ RAM recommended)  
**Recommended:** ESP32 with 8MB RAM for advanced patterns  
**Advanced:** Boards like FeatherS3 (16MB flash + 8MB PSRAM) for months of data

## ☁️ Cloud Features (Optional)

Add `enable_cloud_alerts=True` for:
- Real-time alerts to Tendrl platform
- Offline storage when network fails
- Data publishing to cloud for remote monitoring

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
