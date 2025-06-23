"""
DHT11/DHT22 Machine Learning Package
===================================

Plug-and-play anomaly detection for DHT temperature/humidity sensors.

🚀 SIMPLE USAGE (Recommended):
    from examples.tendrl_dht import SimpleDHTML
    
    def my_alert(temp, humidity, reason):
        print(f"ALERT: {temp}°C, {humidity}% - {reason}")
    
    sensor = SimpleDHTML(pin=4, alert_callback=my_alert)
    sensor.set_thresholds(temp_range=[20, 25], humidity_range=[40, 60])
    sensor.start()  # Automatic monitoring with anomaly detection

🏠 PRE-CONFIGURED SENSORS:
    from examples.tendrl_dht import create_indoor_sensor, create_greenhouse_sensor
    
    indoor = create_indoor_sensor(pin=4, alert_callback=my_alert)
    indoor.start()

📚 EDUCATIONAL EXAMPLE:
    from examples.tendrl_dht import SimpleDHT22ML
    
    # Basic educational ML example with clear code comments
    ml = SimpleDHT22ML()

Available Components:
    - SimpleDHTML: 🎯 RECOMMENDED - Plug-and-play sensor with anomaly detection
    - create_*_sensor: Pre-configured sensors for common scenarios  
    - SimpleDHT22ML: Educational example showing basic ML concepts
"""

# Import main classes for easy access
try:
    # Primary recommendation - simple plug-and-play
    from .simple_sensor_ml import (
        SimpleDHTML,
        create_indoor_sensor,
        create_outdoor_sensor, 
        create_greenhouse_sensor
    )
    
    # Educational/research implementation
    from .simple_dht22_ml import SimpleDHT22ML
    
    __all__ = [
        # Simple plug-and-play (RECOMMENDED)
        'SimpleDHTML',
        'create_indoor_sensor',
        'create_outdoor_sensor',
        'create_greenhouse_sensor',
        
        # Educational example
        'SimpleDHT22ML'
    ]

except ImportError as e:
    # Graceful degradation if dependencies aren't available
    print(f"Warning: Some DHT ML components not available: {e}")
    __all__ = []

# Package metadata
__version__ = "1.0.0"
__author__ = "MicroTetherDB Team"
__description__ = "Simple plug-and-play anomaly detection for DHT11/DHT22 sensors"
