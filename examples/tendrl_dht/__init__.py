"""
DHT11/DHT22 Machine Learning Package
===================================

Simple learning patterns for DHT temperature/humidity sensors using MicroTetherDB.

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

🧠 IMPOSSIBLE-BEFORE ML PATTERNS:
    from examples.tendrl_dht import LongTermLearning, CloudTrendLearning, CloudAdaptiveLearning
    
    # Learn from weeks of data - impossible with traditional storage!
    long_term = LongTermLearning(pin=4, learning_days=30)
    long_term.take_reading()

Available Components:
    - SimpleDHTML: 🎯 RECOMMENDED - Plug-and-play sensor with anomaly detection
    - create_*_sensor: Pre-configured sensors for common scenarios  
    - LongTermLearning: Learn from weeks of persistent data (impossible before!)
    - CloudTrendLearning: Cloud-synced intelligence with offline storage
    - CloudAdaptiveLearning: Bidirectional cloud feedback learning
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
    
    # Impossible-before ML patterns - demonstrate MicroTetherDB + Tendrl capabilities
    from .ml_examples import (
        LongTermLearning,
        CloudTrendLearning,
        CloudAdaptiveLearning
    )
    
    __all__ = [
        # Simple plug-and-play (RECOMMENDED)
        'SimpleDHTML',
        'create_indoor_sensor',
        'create_outdoor_sensor',
        'create_greenhouse_sensor',
        
        # Impossible-before ML patterns
        'LongTermLearning',
        'CloudTrendLearning', 
        'CloudAdaptiveLearning'
    ]

except ImportError as e:
    # Graceful degradation if dependencies aren't available
    print(f"Warning: Some DHT ML components not available: {e}")
    __all__ = []

# Package metadata
__version__ = "2.0.0"  # Updated for simplified structure
__author__ = "MicroTetherDB Team"
__description__ = "Simple learning patterns for DHT11/DHT22 sensors using MicroTetherDB"
