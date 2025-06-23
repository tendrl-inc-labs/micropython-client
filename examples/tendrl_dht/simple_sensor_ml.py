"""
Simple DHT11/DHT22 ML - Plug and Play Anomaly Detection
======================================================

A streamlined approach to DHT sensor monitoring with built-in anomaly detection.
Just provide thresholds and get alerts - no complex configuration needed.

Usage:
    sensor = SimpleDHTML(pin=4, sensor_type='DHT22')
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
except ImportError:
    print("Warning: MicroTetherDB not available")
    MicroTetherDB = None


class SimpleDHTML:
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
                 temp_unit='C', data_window_hours=1, alert_cooldown_minutes=5):
        """
        Initialize the sensor
        
        Args:
            pin: GPIO pin number for DHT sensor
            sensor_type: 'DHT11' or 'DHT22'
            alert_callback: Function called on anomalies (temp, humidity, reason)
            temp_unit: Temperature unit - 'C' for Celsius, 'F' for Fahrenheit
            data_window_hours: How many hours of data to keep (1, 24, 168=7days, 720=30days)
            alert_cooldown_minutes: Minutes to wait between similar alerts (default: 5)
        """
        self.sensor_type = sensor_type.upper()
        self.alert_callback = alert_callback or self._default_alert
        self.temp_unit = temp_unit.upper()
        self.data_window_hours = data_window_hours
        self.alert_cooldown_minutes = alert_cooldown_minutes

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

        # Configuration - default ranges in Celsius, will be converted if needed
        self.temp_range = [15, 35]  # Default acceptable temperature range (Celsius)
        self.humidity_range = [20, 80]  # Default acceptable humidity range
        self.reading_interval = 30000  # 30 seconds
        self.window_size = 20  # Keep last 20 readings for context

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
            recent_readings = self._get_recent_readings(10)
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
        """Default alert function"""
        print(f"🚨 ANOMALY DETECTED: {temp}°C, {humidity}% - {reason}")

    def get_status(self):
        """Get current sensor status and recent statistics"""
        if not self.db:
            return {"error": "Database not available"}

        recent = self._get_recent_readings(10)
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
def create_indoor_sensor(pin, alert_callback=None, temp_unit='C', data_window_hours=24, alert_cooldown_minutes=5):
    """Create sensor configured for indoor monitoring (20-26°C/68-79°F, 40-60% humidity)"""
    sensor = SimpleDHTML(pin, 'DHT22', alert_callback, temp_unit, data_window_hours, alert_cooldown_minutes)
    if temp_unit.upper() == 'F':
        sensor.set_thresholds(temp_range=[68, 79], humidity_range=[40, 60])  # Fahrenheit
    else:
        sensor.set_thresholds(temp_range=[20, 26], humidity_range=[40, 60])  # Celsius
    return sensor

def create_outdoor_sensor(pin, alert_callback=None, temp_unit='C', data_window_hours=24, alert_cooldown_minutes=10):
    """Create sensor configured for outdoor monitoring (0-40°C/32-104°F, 10-90% humidity)"""
    sensor = SimpleDHTML(pin, 'DHT22', alert_callback, temp_unit, data_window_hours, alert_cooldown_minutes)
    if temp_unit.upper() == 'F':
        sensor.set_thresholds(temp_range=[32, 104], humidity_range=[10, 90])  # Fahrenheit
    else:
        sensor.set_thresholds(temp_range=[0, 40], humidity_range=[10, 90])  # Celsius
    return sensor

def create_greenhouse_sensor(pin, alert_callback=None, temp_unit='C', data_window_hours=168, alert_cooldown_minutes=15):
    """Create sensor configured for greenhouse monitoring (18-30°C/64-86°F, 50-80% humidity)"""
    sensor = SimpleDHTML(pin, 'DHT22', alert_callback, temp_unit, data_window_hours, alert_cooldown_minutes)
    if temp_unit.upper() == 'F':
        sensor.set_thresholds(temp_range=[64, 86], humidity_range=[50, 80])  # Fahrenheit
    else:
        sensor.set_thresholds(temp_range=[18, 30], humidity_range=[50, 80])  # Celsius
    return sensor

# Demo usage
def main():
    """Demo showing simple usage"""
    print("Simple DHT ML Demo")
    print("=" * 30)

    def my_alert(temp, humidity, reason):
        print(f"📱 ALERT: {temp}°, {humidity}% - {reason}")
        # Here you could send notifications, log to file, etc.

    # Method 1: Manual setup with Fahrenheit and 24-hour window
    sensor = SimpleDHTML(pin=4, sensor_type='DHT22', alert_callback=my_alert,
                        temp_unit='F', data_window_hours=24, alert_cooldown_minutes=3)
    sensor.set_thresholds(temp_range=[68, 77], humidity_range=[40, 60])  # Fahrenheit

    # Method 2: Pre-configured for common scenarios
    # indoor_sensor = create_indoor_sensor(pin=4, alert_callback=my_alert, temp_unit='F', data_window_hours=24)
    # outdoor_sensor = create_outdoor_sensor(pin=5, alert_callback=my_alert, temp_unit='C', data_window_hours=168)

    print("\nConfiguration:")
    print(f"  Sensor: {sensor.sensor_type}")
    print(f"  Temperature unit: {sensor.temp_unit}")
    print(f"  Data window: {sensor.data_window_hours} hours")
    print(f"  Temperature range: {[round(sensor._convert_temp_display(t), 1) for t in sensor.temp_range]}°{sensor.temp_unit}")
    print(f"  Humidity range: {sensor.humidity_range}%")
    print(f"  Reading interval: {sensor.reading_interval/1000}s")
    print(f"  Alert cooldown: {sensor.alert_cooldown_minutes} minutes")

    print("\nTo start monitoring:")
    print("  sensor.start()  # Takes readings every 30 seconds")
    print("  # Anomalies will trigger your alert_callback function")

    print("\nTo adjust alert cooldown:")
    print("  sensor.set_alert_cooldown(10)  # 10 minutes between alerts")
    print("  sensor.set_alert_cooldown(0)   # No cooldown (immediate alerts)")

    print("\nTo check status anytime:")
    print("  status = sensor.get_status()")
    print("  print(status)")


if __name__ == "__main__":
    main()
