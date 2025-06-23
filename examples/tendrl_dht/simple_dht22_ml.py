"""
Simple DHT22 ML Example using MicroTetherDB
===========================================

A minimal example showing how to use MicroTetherDB for basic machine learning
with DHT22 temperature/humidity sensors on microcontrollers.

This example demonstrates:
1. Storing sensor readings with automatic cleanup
2. Computing running statistics for anomaly detection
3. Using stored patterns for comparison
"""

import time

from tendrl.lib.microtetherdb import MicroTetherDB


class SimpleDHT22ML:
    """
    Simple ML class for DHT22 anomaly detection using MicroTetherDB
    """

    def __init__(self):
        # Initialize database - uses 15% of available RAM by default
        self.db = MicroTetherDB(
            filename="dht22_simple.db",
            in_memory=False,  # Persist data across reboots
            ttl_check_interval=300  # Clean up expired data every 5 minutes
        )

        # Anomaly detection thresholds
        self.temp_tolerance = 5.0   # ±5°C from average
        self.humidity_tolerance = 15.0  # ±15% from average

    def store_reading(self, temperature, humidity):
        """
        Store a sensor reading with automatic TTL cleanup
        """
        reading = {
            "temperature": temperature,
            "humidity": humidity,
            "timestamp": time.time(),
            "hour": int(time.time() % (24 * 3600) / 3600)  # Hour of day (0-23)
        }

        # Store reading - automatically deleted after 7 days
        key = self.db.put(
            reading,
            ttl=7 * 24 * 3600,  # 7 days in seconds
            tags=["sensor_reading"]
        )

        return key

    def get_running_statistics(self):
        """
        Get running statistics from stored readings
        """
        # Get all recent readings (last 24 hours)
        cutoff_time = time.time() - (24 * 3600)
        recent_readings = self.db.query({
            "timestamp": {"$gte": cutoff_time},
            "tags": "sensor_reading"
        })

        if len(recent_readings) < 5:  # Need at least 5 readings
            return None

        # Calculate basic statistics
        temperatures = [r["temperature"] for r in recent_readings]
        humidities = [r["humidity"] for r in recent_readings]

        stats = {
            "temp_avg": sum(temperatures) / len(temperatures),
            "temp_min": min(temperatures),
            "temp_max": max(temperatures),
            "humidity_avg": sum(humidities) / len(humidities),
            "humidity_min": min(humidities),
            "humidity_max": max(humidities),
            "sample_count": len(recent_readings),
            "calculated_at": time.time()
        }

        return stats

    def is_anomaly(self, temperature, humidity):
        """
        Simple anomaly detection based on recent averages
        """
        stats = self.get_running_statistics()

        if not stats:
            return False, "insufficient_data"

        # Check if current reading is outside normal range
        temp_diff = abs(temperature - stats["temp_avg"])
        humidity_diff = abs(humidity - stats["humidity_avg"])
        temp_anomaly = temp_diff > self.temp_tolerance
        humidity_anomaly = humidity_diff > self.humidity_tolerance

        if temp_anomaly or humidity_anomaly:
            reason = []
            if temp_anomaly:
                reason.append(f"temp_deviation: {temp_diff:.1f}°C")
            if humidity_anomaly:
                reason.append(f"humidity_deviation: {humidity_diff:.1f}%")

            return True, ", ".join(reason)

        return False, "normal"

    def store_normal_pattern(self, label, temp_range, humidity_range):
        """
        Store a known normal pattern for comparison
        """
        pattern = {
            "label": label,
            "temp_min": temp_range[0],
            "temp_max": temp_range[1],
            "humidity_min": humidity_range[0],
            "humidity_max": humidity_range[1],
            "created_at": time.time()
        }

        key = self.db.put(
            f"pattern_{label}",
            pattern,
            ttl=30 * 24 * 3600,  # Keep patterns for 30 days
            tags=["normal_pattern"]
        )

        return key

    def check_against_patterns(self, temperature, humidity):
        """
        Check if current reading matches any stored normal patterns
        """
        patterns = self.db.query({"tags": "normal_pattern"})

        for pattern in patterns:
            if (pattern["temp_min"] <= temperature <= pattern["temp_max"] and
                pattern["humidity_min"] <= humidity <= pattern["humidity_max"]):
                return True, pattern["label"]

        return False, "no_matching_pattern"

    def comprehensive_check(self, temperature, humidity):
        """
        Comprehensive anomaly check using multiple methods
        """
        # Store the reading first
        self.store_reading(temperature, humidity)

        results = {
            "temperature": temperature,
            "humidity": humidity,
            "timestamp": time.time(),
            "checks": {}
        }

        # Statistical anomaly check
        is_stats_anomaly, stats_reason = self.is_anomaly(temperature, humidity)
        results["checks"]["statistical"] = {
            "anomaly": is_stats_anomaly,
            "reason": stats_reason
        }

        # Pattern matching check
        matches_pattern, pattern_info = self.check_against_patterns(temperature, humidity)
        results["checks"]["pattern"] = {
            "matches_known_pattern": matches_pattern,
            "pattern_info": pattern_info
        }

        # Overall assessment
        results["overall_anomaly"] = is_stats_anomaly and not matches_pattern
        results["confidence"] = "high" if is_stats_anomaly and not matches_pattern else "low"

        return results


def main():
    """
    Simple demo of DHT22 ML anomaly detection
    """
    ml = SimpleDHT22ML()

    print("Simple DHT22 ML Demo")
    print("=" * 30)

    # Store some normal patterns
    print("\n1. Storing normal patterns...")
    ml.store_normal_pattern("indoor_comfort", [20, 25], [40, 60])
    ml.store_normal_pattern("outdoor_summer", [25, 32], [30, 70])
    print("  Stored: indoor_comfort (20-25°C, 40-60%)")
    print("  Stored: outdoor_summer (25-32°C, 30-70%)")

    # Simulate storing normal readings over time
    print("\n2. Storing normal readings...")
    normal_readings = [
        (22.1, 45), (23.5, 48), (21.8, 52), (24.2, 41),
        (22.9, 49), (23.8, 46), (21.5, 55), (24.5, 43)
    ]

    for temp, humidity in normal_readings:
        ml.store_reading(temp, humidity)
        print(f"  Stored: {temp}°C, {humidity}%")
        time.sleep(0.1)  # Small delay to simulate time passing

    # Test some readings
    print("\n3. Testing anomaly detection...")

    test_cases = [
        (23.0, 47, "Normal reading"),
        (35.0, 85, "Very high - possible error"),
        (15.0, 25, "Very low - environmental change"),
        (22.5, 95, "High humidity - possible leak"),
    ]

    for temp, humidity, description in test_cases:
        print(f"\nTesting: {temp}°C, {humidity}% ({description})")

        result = ml.comprehensive_check(temp, humidity)

        print(f"  Overall Anomaly: {'YES' if result['overall_anomaly'] else 'NO'}")
        print(f"  Confidence: {result['confidence']}")

        # Show detailed results
        stats_check = result["checks"]["statistical"]
        pattern_check = result["checks"]["pattern"]

        if stats_check["anomaly"]:
            print(f"  Statistical anomaly: {stats_check['reason']}")

        if pattern_check["matches_known_pattern"]:
            print(f"  Matches pattern: {pattern_check['pattern_info']}")
        else:
            print(f"  No pattern match: {pattern_check['pattern_info']}")

    # Show statistics
    print("\n4. Current statistics...")
    stats = ml.get_running_statistics()
    if stats:
        print(f"  Temperature: {stats['temp_avg']:.1f}°C "
              f"(range: {stats['temp_min']:.1f} - {stats['temp_max']:.1f}°C)")
        print(f"  Humidity: {stats['humidity_avg']:.1f}% "
              f"(range: {stats['humidity_min']:.1f} - {stats['humidity_max']:.1f}%)")
        print(f"  Based on {stats['sample_count']} readings")

    # Cleanup
    ml.db.close()
    print("\nDemo completed!")


if __name__ == "__main__":
    main()
