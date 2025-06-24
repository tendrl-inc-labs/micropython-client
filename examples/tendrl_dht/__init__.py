"""
DHT11/DHT22 Statistical Analysis Package
=======================================

Statistical analysis patterns for DHT temperature/humidity sensors using MicroTetherDB.

🚀 SIMPLE USAGE (Recommended):
    from examples.tendrl_dht import SimpleDHTAnalytics
    
    def my_alert(temp, humidity, reason):
        print(f"ALERT: {temp}°C, {humidity}% - {reason}")
    
    sensor = SimpleDHTAnalytics(pin=4, alert_callback=my_alert)
    sensor.set_thresholds(temp_range=[20, 25], humidity_range=[40, 60])
    sensor.start()  # Automatic monitoring with anomaly detection

🏠 PRE-CONFIGURED SENSORS:
    from examples.tendrl_dht import create_indoor_sensor, create_greenhouse_sensor
    
    indoor = create_indoor_sensor(pin=4, alert_callback=my_alert)
    indoor.start()

📊 ADVANCED STATISTICAL PATTERNS:
    from examples.tendrl_dht import LongTermStatisticalAnalysis, CloudTrendAnalysis, CloudAdaptiveStatistics
    
    # Analyze weeks of data - extremely difficult with traditional storage!
    long_term = LongTermStatisticalAnalysis(pin=4, learning_days=30)
    long_term.take_reading()

Available Components:
    - SimpleDHTAnalytics: 🎯 RECOMMENDED - Plug-and-play sensor with anomaly detection
    - create_*_sensor: Pre-configured sensors for common scenarios  
    - LongTermStatisticalAnalysis: Analyze weeks of persistent data (extremely difficult before!)
    - CloudTrendAnalysis: Cloud-synced trend analysis with offline storage
    - CloudAdaptiveStatistics: Bidirectional cloud feedback statistics
"""

# Import main classes for easy access
try:
    # Primary recommendation - simple plug-and-play
    from .simple_dht import (
        SimpleDHTAnalytics,
        create_indoor_sensor,
        create_outdoor_sensor, 
        create_greenhouse_sensor
    )
    
    # Advanced statistical patterns - demonstrate MicroTetherDB + Tendrl capabilities
    from .statistical_examples import (
        LongTermStatisticalAnalysis,
        CloudTrendAnalysis,
        CloudAdaptiveStatistics
    )
    
    __all__ = [
        # Simple plug-and-play (RECOMMENDED)
        'SimpleDHTAnalytics',
        'create_indoor_sensor',
        'create_outdoor_sensor',
        'create_greenhouse_sensor',
        
        # Advanced statistical patterns
        'LongTermStatisticalAnalysis',
        'CloudTrendAnalysis', 
        'CloudAdaptiveStatistics'
    ]

except ImportError as e:
    # Graceful degradation if dependencies aren't available
    print(f"Warning: Some DHT analytics components not available: {e}")
    __all__ = []

# Package metadata
__version__ = "2.0.0"  # Updated for simplified structure
__author__ = "MicroTetherDB Team"
__description__ = "Statistical analysis patterns for DHT11/DHT22 sensors using MicroTetherDB"
