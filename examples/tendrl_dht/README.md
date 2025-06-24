# DHT Sensor Examples

## Statistical Analysis for Environmental Monitoring with MicroTetherDB

## 🚀 **2-Minute Quick Start - See the Power Immediately**

```python
# Traditional approach: 50+ lines of setup, manual memory management, network handling
# sensor = DHT22(Pin(4)); readings = []; def check_thresholds()...

# Our approach: 3 lines, enterprise-grade capabilities
from examples.tendrl_dht import create_indoor_sensor

def my_alert(temp, humidity, reason):
    print(f"🚨 SMART ALERT: {reason}")

sensor = create_indoor_sensor(pin=4, alert_callback=my_alert)
sensor.start()  # Done!
```

**🎯 What you just got:**

- **Persistent B-tree storage** (data survives restarts vs. lost arrays)
- **Smart anomaly detection** (rolling averages + context vs. basic thresholds)
- **Automatic memory cleanup** (TTL management vs. manual array handling)
- **Production-ready networking** (offline-first + auto-reconnect vs. manual HTTP)

**That's it!** You now have MongoDB-style time-series queries, persistent B-tree storage, and production-ready cloud sync on a microcontroller.

> 📌 **Hardware needed:** DHT22 sensor connected to GPIO pin 4 (or change `pin=4` to your wiring).

📦 **Try This Next**: Want cloud alerts? Just add `enable_cloud_alerts=True`  
📦 **Try This Next**: Want 30 days of data? Change to `data_window_hours=720`  
📦 **Try This Next**: Want greenhouse settings? Use `create_greenhouse_sensor()`  

---

## 🚀 **Database & Cloud Sophistication on Microcontrollers**

**❌ Arduino/C approach:**

```c
// Fixed arrays - no persistence, no queries
float readings[100];  // Lost on restart, linear search only
```

**⚠️ Basic MicroPython approach:**

```python
# Simple lists - better than C but still limited
readings = []  # Lost on restart, memory limited
with open('data.txt', 'a') as f:
    f.write(f"{temp},{humidity},{time}\n")  # Manual parsing needed
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

**Technical sophistication progression:**

| **Capability** | **Arduino/C** | **Basic MicroPython** | **MicroTetherDB + Tendrl** |
|----------------|---------------|------------------------|----------------------------|
| **Query Performance** | Linear array search | Linear list search | **B-tree indexed lookups** |
| **Time-Series Analysis** | Manual timestamps | Manual file parsing | **Native time-range queries** |
| **Data Persistence** | Volatile RAM only | Basic text files | **Automatic B-tree storage** |
| **Memory Management** | Manual arrays | Manual list cleanup | **Automatic TTL with indexing** |
| **Cloud Resilience** | Manual HTTP/WiFi | Basic `requests/mqtt` | **Offline-first with batching** |
| **Network Handling** | Manual connection mgmt | Manual retry loops | **WebSocket with auto-reconnect** |

**🚫 Common IoT Pain Points We Solve:**

- **Memory leaks from growing arrays** → Automatic TTL cleanup with B-tree indexing
- **Lost data on restart/power cycle** → Persistent B-tree storage survives reboots  
- **Network failures crash system** → Offline-first with automatic reconnection
- **Manual threshold tuning for environments** → Context-aware anomaly detection

---

## 📁 What's Included

**🎯 `simple_dht.py`** - Plug-and-play sensor with smart monitoring  
**📊 `statistical_examples.py`** - Advanced patterns using weeks of persistent data

```python
# Basic monitoring - 3 lines for enterprise-grade capabilities
sensor = create_indoor_sensor(pin=4)
sensor.start()

# Advanced analysis - 30 days of persistent queries
analyzer = LongTermStatisticalAnalysis(pin=4, learning_days=30)
analyzer.take_reading()
```

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

**Database:** B-tree indexing, MongoDB-style queries, automatic TTL cleanup, persistent storage  
**Networking:** WebSocket connections, offline-first with batching, auto-reconnection  
**Result:** `db.query({'timestamp': {'$gte': week_ago}})` + `client.publish(data, write_offline=True)`

## 💾 Hardware Requirements

**Minimum:** ESP32 + DHT22 sensor
**Recommended:** ESP32 with 2+MB RAM for advanced patterns  
**Advanced:** Boards like FeatherS3 (16MB flash + 8MB PSRAM) for months of data

## ☁️ Cloud Features (Optional)

Add `enable_cloud_alerts=True` for:

- Real-time alerts to Tendrl platform
- Offline storage when network fails
- Data publishing to cloud for remote monitoring

*Requires `config.json` with Tendrl credentials*

## 🔍 Troubleshooting

### Quick Fixes for Common Issues

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
