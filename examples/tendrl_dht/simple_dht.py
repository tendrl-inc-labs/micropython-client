"""
Simple DHT11/DHT22 Smart Sensor - Plug and Play Anomaly Detection
================================================================

A streamlined approach to DHT sensor monitoring with built-in anomaly detection.
Just provide thresholds and get alerts - no complex configuration needed.

This uses smart monitoring techniques like:
- Threshold-based anomaly detection
- Rolling averages for context
- Sudden change detection from recent patterns

Usage:
    sensor = SimpleDHTAnalytics(pin=4, sensor_type='DHT22')
    sensor.set_thresholds(temp_range=[18, 28], humidity_range=[30, 70])
    sensor.start()  # Runs automatically, calls your alert function on anomalies
"""

import time
try:
    from machine import Pin, Timer
    from dht import DHT11, DHT22
except ImportError:
    # For testing without hardware
    pass

try:
    from tendrl.lib.microtetherdb import MicroTetherDB
    from tendrl import Client
except ImportError:
    print("Warning: Tendrl SDK not available")
    MicroTetherDB = None
    Client = None


class SimpleDHTSensor:
    """
    Plug-and-play DHT sensor with anomaly detection
    
    Features:
    - Automatic sensor readings every 30 seconds
    - Simple threshold-based anomaly detection
    - Rolling window statistics for context
    - Customizable alert callbacks
    - Minimal memory usage (~10KB)
    """

    def __init__(self, pin, sensor_type='DHT22', alert_callback=None,
                 temp_unit='C', data_window_hours=1, alert_cooldown_minutes=5, window_size=20,
                 enable_cloud_alerts=False, device_name=None, location=None):
        """
        Initialize the sensor
        
        Args:
            pin: GPIO pin number for DHT sensor
            sensor_type: 'DHT11' or 'DHT22'
            alert_callback: Function called on anomalies (temp, humidity, reason)
            temp_unit: Temperature unit - 'C' for Celsius, 'F' for Fahrenheit
            data_window_hours: How many hours of data to keep (1, 24, 168=7days, 720=30days)
            alert_cooldown_minutes: Minutes to wait between similar alerts (default: 5)
            window_size: Number of recent readings to use for context analysis (default: 20)
            enable_cloud_alerts: Enable Tendrl cloud alerting (requires config.json)
            device_name: Name for cloud alerts (e.g., "Living Room Sensor")
            location: Location for cloud alerts (e.g., "Home", "Office")
        """
        self.sensor_type = sensor_type.upper()
        self.alert_callback = alert_callback or self._default_alert
        self.temp_unit = temp_unit.upper()
        self.data_window_hours = data_window_hours
        self.alert_cooldown_minutes = alert_cooldown_minutes
        self.window_size = window_size
        self.enable_cloud_alerts = enable_cloud_alerts
        self.device_name = device_name or f"{sensor_type} Sensor"
        self.location = location or "Unknown Location"

        # Initialize sensor
        try:
            if self.sensor_type == 'DHT11':
                self.sensor = DHT11(Pin(pin))
            else:
                self.sensor = DHT22(Pin(pin))
        except NameError:
            self.sensor = None  # Testing mode

        # Configure database based on data window
        self._configure_database()
        
        # Initialize cloud client if enabled
        self.client = None
        if self.enable_cloud_alerts:
            self._init_cloud_client()

        # Configuration - default ranges in Celsius, will be converted if needed
        self.temp_range = [15, 35]  # Default acceptable temperature range (Celsius)
        self.humidity_range = [20, 80]  # Default acceptable humidity range
        self.reading_interval = 30000  # 30 seconds

        # State
        self.timer = None
        self.reading_count = 0
        self.last_alert_time = 0
        self.alert_cooldown = alert_cooldown_minutes * 60  # Convert minutes to seconds

    def _configure_database(self):
        """Configure database based on data window requirements"""
        if not MicroTetherDB:
            self.db = None
            return

        # Calculate TTL and storage settings based on window size
        ttl_seconds = self.data_window_hours * 3600

        if self.data_window_hours <= 24:
            # Short-term: use in-memory storage
            self.db = MicroTetherDB(
                in_memory=True,
                ram_percentage=5 if self.data_window_hours <= 1 else 15,
                ttl_check_interval=300  # Check every 5 minutes
            )
        else:
            # Long-term: use file storage
            self.db = MicroTetherDB(
                in_memory=False,
                ram_percentage=20,  # More RAM for caching
                ttl_check_interval=600,  # Check every 10 minutes
                filename=f"dht_{self.sensor_type.lower()}_data.db"
            )

        # Store the TTL for use in _take_reading
        self._data_ttl = ttl_seconds

    def _init_cloud_client(self):
        """Initialize Tendrl client for cloud alerting"""
        if not Client:
            print("⚠️ Tendrl client not available - cloud alerts disabled")
            self.enable_cloud_alerts = False
            return
            
        try:
            self.client = Client(
                debug=False,  # Keep quiet for production use
                managed=True,
                offline_storage=True  # Store alerts offline if network fails
            )
            self.client.start()
            print(f"✅ Cloud alerts enabled for {self.device_name}")
        except Exception as e:
            print(f"⚠️ Cloud client failed to initialize: {e}")
            self.enable_cloud_alerts = False
            self.client = None

    def _celsius_to_fahrenheit(self, celsius):
        """Convert Celsius to Fahrenheit"""
        return (celsius * 9/5) + 32

    def _fahrenheit_to_celsius(self, fahrenheit):
        """Convert Fahrenheit to Celsius"""
        return (fahrenheit - 32) * 5/9

    def _convert_temp_display(self, temp_celsius):
        """Convert temperature for display based on unit setting"""
        if self.temp_unit == 'F':
            return self._celsius_to_fahrenheit(temp_celsius)
        return temp_celsius

    def _convert_temp_to_celsius(self, temp):
        """Convert temperature to Celsius for internal calculations"""
        if self.temp_unit == 'F':
            return self._fahrenheit_to_celsius(temp)
        return temp

    def set_thresholds(self, temp_range=None, humidity_range=None):
        """
        Set acceptable ranges for temperature and humidity
        
        Args:
            temp_range: [min_temp, max_temp] in the configured temperature unit
            humidity_range: [min_humidity, max_humidity] in percentage
        """
        if temp_range:
            # Convert to Celsius for internal storage if needed
            if self.temp_unit == 'F':
                self.temp_range = [self._fahrenheit_to_celsius(temp_range[0]),
                                 self._fahrenheit_to_celsius(temp_range[1])]
            else:
                self.temp_range = temp_range
        if humidity_range:
            self.humidity_range = humidity_range

        # Display in user's preferred unit
        display_temp = [self._convert_temp_display(t) for t in self.temp_range]
        unit_symbol = 'F' if self.temp_unit == 'F' else 'C'
        print(f"Thresholds set: Temp {display_temp}°{unit_symbol}, Humidity {self.humidity_range}%")

    def set_alert_cooldown(self, minutes):
        """
        Set the cooldown period between similar alerts
        
        Args:
            minutes: Minutes to wait between similar alerts (0 = no cooldown)
        """
        self.alert_cooldown_minutes = minutes
        self.alert_cooldown = minutes * 60
        print(f"Alert cooldown set to {minutes} minutes")

    def set_window_size(self, size):
        """
        Set the number of recent readings to use for context analysis
        
        Args:
            size: Number of readings (5-50 recommended, default: 20)
        """
        if size < 3:
            size = 3
            print("Warning: Window size too small, setting to minimum of 3")
        elif size > 100:
            size = 100
            print("Warning: Window size too large, setting to maximum of 100")
        
        self.window_size = size
        print(f"Context window size set to {size} readings")

    def start(self, interval_seconds=30):
        """
        Start automatic monitoring
        
        Args:
            interval_seconds: How often to take readings (default: 30 seconds)
        """
        self.reading_interval = interval_seconds * 1000

        if self.timer:
            self.timer.deinit()

        try:
            self.timer = Timer(0)
            self.timer.init(
                period=self.reading_interval,
                mode=Timer.PERIODIC,
                callback=self._take_reading
            )
            print(f"Started {self.sensor_type} monitoring (every {interval_seconds}s)")
        except NameError:
            print("Timer not available - running in test mode")

    def stop(self):
        """Stop monitoring"""
        if self.timer:
            self.timer.deinit()
            self.timer = None
        if self.db:
            self.db.close()
        print("Monitoring stopped")

    def _take_reading(self, timer):
        """Take a sensor reading and check for anomalies"""
        if not self.sensor:
            return

        try:
            self.sensor.measure()
            temp = self.sensor.temperature()
            humidity = self.sensor.humidity()

            # Round based on sensor precision
            if self.sensor_type == 'DHT11':
                temp = round(temp)
                humidity = round(humidity)
            else:
                temp = round(temp, 1)
                humidity = round(humidity, 1)

            timestamp = time.time()
            self.reading_count += 1

            # Store reading (always store temperature in Celsius internally)
            if self.db:
                self.db.put({
                    'temp': temp,  # Always stored in Celsius
                    'temp_unit': 'C',  # Internal storage unit
                    'humidity': humidity,
                    'timestamp': timestamp,
                    'count': self.reading_count
                }, ttl=self._data_ttl)  # Use configured data window

            # Check for anomalies
            self._check_anomaly(temp, humidity, timestamp)

        except Exception as e:
            print(f"Reading error: {e}")

    def _check_anomaly(self, temp, humidity, timestamp):
        """Check if current reading is anomalous"""
        anomalies = []

        # Simple threshold checks
        display_temp = self._convert_temp_display(temp)
        display_min = self._convert_temp_display(self.temp_range[0])
        display_max = self._convert_temp_display(self.temp_range[1])
        unit_symbol = 'F' if self.temp_unit == 'F' else 'C'

        if temp < self.temp_range[0]:
            anomalies.append(
                f"Temperature too low: {display_temp:.1f}°{unit_symbol} (min: {display_min:.1f}°{unit_symbol})"
            )
        elif temp > self.temp_range[1]:
            anomalies.append(
                f"Temperature too high: {display_temp:.1f}°{unit_symbol} (max: {display_max:.1f}°{unit_symbol})"
            )

        if humidity < self.humidity_range[0]:
            anomalies.append(f"Humidity too low: {humidity}% (min: {self.humidity_range[0]}%)")
        elif humidity > self.humidity_range[1]:
            anomalies.append(f"Humidity too high: {humidity}% (max: {self.humidity_range[1]}%)")

        # Enhanced checks with recent data context
        if self.db and self.reading_count > 5:
            recent_readings = self._get_recent_readings(self.window_size)
            if recent_readings:
                context_anomalies = self._check_context_anomalies(temp, humidity, recent_readings)
                anomalies.extend(context_anomalies)

        # Trigger alerts if anomalies found
        if anomalies and self._should_alert(timestamp):
            reason = "; ".join(anomalies)
            self.alert_callback(temp, humidity, reason)
            self.last_alert_time = timestamp

    def _check_context_anomalies(self, temp, humidity, recent_readings):
        """Check for anomalies based on recent reading patterns"""
        anomalies = []

        if len(recent_readings) < 3:
            return anomalies

        # Calculate recent averages
        recent_temps = [r['temp'] for r in recent_readings]
        recent_humidity = [r['humidity'] for r in recent_readings]

        avg_temp = sum(recent_temps) / len(recent_temps)
        avg_humidity = sum(recent_humidity) / len(recent_humidity)

        # Check for sudden changes (more than 5°C or 20% humidity)
        temp_change = abs(temp - avg_temp)
        humidity_change = abs(humidity - avg_humidity)

        # Convert threshold for Fahrenheit (5°C = 9°F)
        temp_threshold = 9 if self.temp_unit == 'F' else 5
        unit_symbol = 'F' if self.temp_unit == 'F' else 'C'

        if temp_change > temp_threshold:
            display_change = self._convert_temp_display(temp_change) if self.temp_unit == 'F' else temp_change
            anomalies.append(
                f"Sudden temperature change: {display_change:.1f}°{unit_symbol} from recent average"
            )

        if humidity_change > 20:
            anomalies.append(
                f"Sudden humidity change: {humidity_change:.1f}% from recent average"
            )

        return anomalies

    def _get_recent_readings(self, count=10):
        """Get recent readings from database"""
        if not self.db:
            return []

        try:
            # Query recent readings
            results = self.db.query({
                'count': {'$exists': True},
                '$limit': count
            })
            # Sort by count (most recent first)
            return sorted(results, key=lambda x: x.get('count', 0), reverse=True)
        except Exception:
            return []

    def _should_alert(self, timestamp):
        """Check if enough time has passed since last alert"""
        return (timestamp - self.last_alert_time) > self.alert_cooldown

    def _default_alert(self, temp, humidity, reason):
        """Default alert function with optional cloud alerting"""
        # Always log locally
        temp_display = self._convert_temp_display(temp)
        unit_symbol = 'F' if self.temp_unit == 'F' else 'C'
        print(f"🚨 ANOMALY DETECTED: {temp_display:.1f}°{unit_symbol}, {humidity}% - {reason}")
        
        # Send to cloud if enabled
        if self.enable_cloud_alerts and self.client and self.client.client_enabled:
            self._send_cloud_alert(temp, humidity, reason)

    def _send_cloud_alert(self, temp, humidity, reason):
        """Send alert to Tendrl cloud platform"""
        try:
            temp_display = self._convert_temp_display(temp)
            unit_symbol = 'F' if self.temp_unit == 'F' else 'C'
            
            # Create alert data with context
            alert_data = {
                'alert_type': 'sensor_anomaly',
                'device_name': self.device_name,
                'location': self.location,
                'sensor_type': self.sensor_type,
                'temperature': round(temp_display, 1),
                'temperature_unit': unit_symbol,
                'humidity': round(humidity, 1),
                'reason': reason,
                'timestamp': time.time(),
                'reading_count': self.reading_count,
                'data_window_hours': self.data_window_hours,
                'analysis_window_size': self.window_size
            }
            
            # Add ML context if available
            recent_readings = self._get_recent_readings(min(10, self.window_size))
            if len(recent_readings) >= 3:
                temps = [self._convert_temp_display(r['temp']) for r in recent_readings]
                humidities = [r['humidity'] for r in recent_readings]
                alert_data.update({
                    'recent_temp_avg': round(sum(temps) / len(temps), 1),
                    'recent_humidity_avg': round(sum(humidities) / len(humidities), 1),
                    'temp_deviation': round(abs(temp_display - sum(temps) / len(temps)), 1),
                    'humidity_deviation': round(abs(humidity - sum(humidities) / len(humidities)), 1)
                })
            
            # Send to cloud with offline storage
            self.client.publish(
                data=alert_data,
                tags=['sensor_alerts', 'anomaly_detection', self.location.lower().replace(' ', '_')],
                entity=f"{self.device_name.lower().replace(' ', '_')}_alerts",
                write_offline=True,  # Store offline if network fails
                db_ttl=7*24*3600  # Keep offline alerts for 1 week
            )
            
        except Exception as e:
            print(f"⚠️ Cloud alert failed: {e}")

    def get_status(self):
        """Get current sensor status and recent statistics"""
        if not self.db:
            return {"error": "Database not available"}

        recent = self._get_recent_readings(self.window_size)
        if not recent:
            return {"readings": 0, "status": "No data"}

        temps = [r['temp'] for r in recent]  # These are stored in Celsius
        humidity = [r['humidity'] for r in recent]

        # Convert temperatures to user's preferred unit for display
        display_temps = [self._convert_temp_display(t) for t in temps] if temps else []
        display_thresholds = [self._convert_temp_display(t) for t in self.temp_range]
        unit_symbol = 'F' if self.temp_unit == 'F' else 'C'

        return {
            "total_readings": self.reading_count,
            "recent_readings": len(recent),
            "data_window_hours": self.data_window_hours,
            "temperature": {
                "current": round(display_temps[0], 1) if display_temps else None,
                "average": round(sum(display_temps) / len(display_temps), 1) if display_temps else None,
                "range": [round(min(display_temps), 1), round(max(display_temps), 1)] if display_temps else None,
                "unit": unit_symbol
            },
            "humidity": {
                "current": humidity[0] if humidity else None,
                "average": round(sum(humidity) / len(humidity), 1) if humidity else None,
                "range": [min(humidity), max(humidity)] if humidity else None,
                "unit": "%"
            },
            "thresholds": {
                "temperature": [round(t, 1) for t in display_thresholds],
                "humidity": self.humidity_range,
                "temp_unit": unit_symbol
            },
            "alert_settings": {
                "cooldown_minutes": self.alert_cooldown_minutes,
                "last_alert_time": self.last_alert_time,
                "seconds_since_last_alert": int(time.time() - self.last_alert_time) if self.last_alert_time > 0 else None
            }
        }


# Convenience functions for even simpler usage
def create_indoor_sensor(pin, alert_callback=None, temp_unit='C', data_window_hours=24, alert_cooldown_minutes=5, window_size=20, 
                        enable_cloud_alerts=False, device_name=None, location=None):
    """Create sensor configured for indoor monitoring (20-26°C/68-79°F, 40-60% humidity)"""
    sensor = SimpleDHTSensor(pin, 'DHT22', alert_callback, temp_unit, data_window_hours, alert_cooldown_minutes, window_size,
                        enable_cloud_alerts, device_name or "Indoor Sensor", location or "Home")
    if temp_unit.upper() == 'F':
        sensor.set_thresholds(temp_range=[68, 79], humidity_range=[40, 60])  # Fahrenheit
    else:
        sensor.set_thresholds(temp_range=[20, 26], humidity_range=[40, 60])  # Celsius
    return sensor

def create_outdoor_sensor(pin, alert_callback=None, temp_unit='C', data_window_hours=24, alert_cooldown_minutes=10, window_size=30,
                         enable_cloud_alerts=False, device_name=None, location=None):
    """Create sensor configured for outdoor monitoring (0-40°C/32-104°F, 10-90% humidity)"""
    sensor = SimpleDHTSensor(pin, 'DHT22', alert_callback, temp_unit, data_window_hours, alert_cooldown_minutes, window_size,
                        enable_cloud_alerts, device_name or "Outdoor Sensor", location or "Garden")
    if temp_unit.upper() == 'F':
        sensor.set_thresholds(temp_range=[32, 104], humidity_range=[10, 90])  # Fahrenheit
    else:
        sensor.set_thresholds(temp_range=[0, 40], humidity_range=[10, 90])  # Celsius
    return sensor

def create_greenhouse_sensor(pin, alert_callback=None, temp_unit='C', data_window_hours=168, alert_cooldown_minutes=15, window_size=50,
                            enable_cloud_alerts=False, device_name=None, location=None):
    """Create sensor configured for greenhouse monitoring (18-30°C/64-86°F, 50-80% humidity)"""
    sensor = SimpleDHTSensor(pin, 'DHT22', alert_callback, temp_unit, data_window_hours, alert_cooldown_minutes, window_size,
                        enable_cloud_alerts, device_name or "Greenhouse Sensor", location or "Greenhouse")
    if temp_unit.upper() == 'F':
        sensor.set_thresholds(temp_range=[64, 86], humidity_range=[50, 80])  # Fahrenheit
    else:
        sensor.set_thresholds(temp_range=[18, 30], humidity_range=[50, 80])  # Celsius
    return sensor
