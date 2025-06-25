"""
Statistical Analysis Patterns with MicroTetherDB + Tendrl
========================================================

This demonstrates 3 data analysis patterns that MicroTetherDB + Tendrl enable
on microcontrollers, which would be very difficult with traditional storage approaches.

🚫 WITHOUT MicroTetherDB + Tendrl:
- Simple arrays (limited size, lose data on restart)
- Files (slow, no structured queries, manual cleanup)
- Basic key-value storage (no time-series queries, no cloud sync)
- Limited historical analysis (can't efficiently access weeks of data)
- No cloud data synchronization

✅ WITH MicroTetherDB + Tendrl:
- Structured time-series queries over weeks of data
- Automatic memory management with TTL
- MongoDB-style query syntax for complex data access
- Persistent storage that survives restarts
- Cloud sync with offline storage capability
- Remote monitoring and data synchronization

Note: These are statistical analysis patterns - threshold detection, trend analysis, 
and adaptive statistics. They enable practical data analytics within microcontroller 
constraints but are not machine learning in the algorithmic sense.
"""

import time

try:
    from machine import Pin
    from dht import DHT22
    HARDWARE = True
except ImportError:
    HARDWARE = False

try:
    from tendrl.lib.microtetherdb import MicroTetherDB
    DB_AVAILABLE = True
except ImportError:
    print("MicroTetherDB not available")
    DB_AVAILABLE = False

try:
    from tendrl import Client
    CLOUD_AVAILABLE = True
except ImportError:
    print("Tendrl client not available")
    CLOUD_AVAILABLE = False


# =============================================================================
# PATTERN 1: LONG-TERM STATISTICAL ANALYSIS (~70 lines)
# Extremely difficult without persistent storage + efficient queries
# =============================================================================

class LongTermStatisticalAnalysis:
    """
    Analyze statistical patterns from weeks of persistent data.
    
    Traditional approach: Limited to ~100 readings in RAM, lost on restart
    MicroTetherDB approach: Weeks of data with structured queries and persistence
    """

    def __init__(self, pin=4, learning_days=30):
        self.sensor = DHT22(Pin(pin)) if HARDWARE else None
        self.learning_days = learning_days

        # KEY INSIGHT: File storage for long-term learning
        # This would be extremely difficult with simple arrays or basic files
        #
        # SCALING: With boards like UM FeatherS3 (16MB flash + 8MB PSRAM):
        # - learning_days=90-180 (approaching practical limits)
        # - Multiple sensors simultaneously
        # - More complex statistical analysis with additional RAM
        # - Smart data rotation: detailed recent + summarized historical
        if DB_AVAILABLE:
            self.db = MicroTetherDB(
                in_memory=False,  # File storage for persistence
                filename=f"long_term_learning_{learning_days}d.db",
                ram_percentage=25,  # More RAM for caching (up to 8MB on FeatherS3!)
                ttl_check_interval=3600  # Check hourly for old data
            )
        else:
            self.db = None

        # Cloud integration for remote monitoring
        if CLOUD_AVAILABLE:
            self.client = Client(
                debug=False,
                offline_storage=True  # Critical: store data even when offline
            )
            try:
                self.client.start()
                self.cloud_enabled = True
                print("☁️ Cloud learning enabled - data syncs to Tendrl platform")
            except:
                self.cloud_enabled = False
        else:
            self.cloud_enabled = False

        self.reading_count = 0

    def take_reading(self):
        """Take reading and learn from WEEKS of historical data"""
        if not self.sensor or not self.db:
            return

        self.sensor.measure()
        temp, humidity = self.sensor.temperature(), self.sensor.humidity()
        now = time.time()

        # Store with long TTL - this is the KEY capability
        # Traditional storage: Extremely difficult to keep weeks of data efficiently
        ttl_seconds = self.learning_days * 24 * 3600  # Days to seconds

        reading_data = {
            'temp': temp, 
            'humidity': humidity, 
            'timestamp': now,
            'hour_of_day': int((now % 86400) / 3600),  # 0-23
            'day_of_week': int((now / 86400) % 7),     # 0-6
            'reading_id': self.reading_count
        }

        self.db.put(reading_data, ttl=ttl_seconds)
        self.reading_count += 1

        # Learn from historical patterns (extremely difficult with traditional storage)
        if self.reading_count >= 10:
            self._learn_long_term_patterns(temp, humidity, now)

        # Send to cloud with context
        if self.cloud_enabled and self.reading_count % 10 == 0:  # Every 10th reading
            self._send_learning_update(temp, humidity, now)

    def _learn_long_term_patterns(self, current_temp, current_humidity, current_time):
        """Analyze patterns from weeks of data using structured queries"""

        current_hour = int((current_time % 86400) / 3600)
        current_day = int((current_time / 86400) % 7)

        # PATTERN 1: Same time of day over weeks
        # Traditional storage: Very difficult - would need complex manual file parsing
        same_time_data = self.db.query({
            'hour_of_day': current_hour,
            'timestamp': {'$gte': current_time - (7 * 24 * 3600)}  # Last week
        })

        if len(same_time_data) >= 5:
            historical_temps = [r['temp'] for r in same_time_data]
            avg_temp = sum(historical_temps) / len(historical_temps)
            deviation = abs(current_temp - avg_temp)

            if deviation > 5.0:  # 5°C deviation from weekly pattern
                print(f"📊 LONG-TERM ANOMALY: {current_temp}°C vs weekly avg {avg_temp:.1f}°C "
                      f"at hour {current_hour} (deviation: {deviation:.1f}°C)")

        # PATTERN 2: Day of week patterns
        # Traditional storage: Challenging to implement efficiently
        same_day_data = self.db.query({
            'day_of_week': current_day,
            'timestamp': {'$gte': current_time - (30 * 24 * 3600)}  # Last month
        })

        if len(same_day_data) >= 10:
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            day_temps = [r['temp'] for r in same_day_data]
            day_avg = sum(day_temps) / len(day_temps)

            print(f"🗓️ {day_names[current_day]} learning: Current {current_temp}°C, "
                  f"historical avg {day_avg:.1f}°C (from {len(same_day_data)} readings)")

        # PATTERN 3: Seasonal trends (requires persistent long-term storage)
        if self.reading_count >= 100:
            trend_data = self.db.query({
                'timestamp': {'$gte': current_time - (self.learning_days * 24 * 3600)},
                'temp': {'$exists': True}
            })

            if len(trend_data) >= 50:
                # Sort by timestamp and analyze trend
                trend_data.sort(key=lambda x: x['timestamp'])
                old_avg = sum(r['temp'] for r in trend_data[:10]) / 10
                recent_avg = sum(r['temp'] for r in trend_data[-10:]) / 10
                seasonal_change = recent_avg - old_avg

                if abs(seasonal_change) > 2.0:
                    direction = "warming" if seasonal_change > 0 else "cooling"
                    print(f"🌡️ SEASONAL TREND: {direction} {abs(seasonal_change):.1f}°C "
                          f"over {self.learning_days} days ({len(trend_data)} readings)")

                # Performance warning for large datasets
                if len(trend_data) > 50000:  # ~6 months of 30-second readings
                    print("⚠️  Large dataset detected - btree queries may slow down")
                    print("   Consider data rotation for production systems (detailed recent + summarized historical)")

    def _send_learning_update(self, temp, humidity, timestamp):
        """Send learning insights to cloud - bidirectional intelligence"""
        try:
            # Get learning context
            week_data = self.db.query({
                'timestamp': {'$gte': timestamp - (7 * 24 * 3600)}
            })

            learning_data = {
                'device_learning': {
                    'current_temp': temp,
                    'current_humidity': humidity,
                    'total_readings': self.reading_count,
                    'learning_days': self.learning_days,
                    'week_data_points': len(week_data),
                    'storage_type': 'persistent_file',
                    'ml_capability': 'long_term_patterns'
                }
            }

            # Publish with offline storage (critical for IoT)
            self.client.publish(
                data=learning_data,
                tags=['ml_learning', 'long_term_analysis'],
                entity='dht_long_term_learner',
                write_offline=True,  # Store offline if network fails
                db_ttl=30*24*3600   # Keep offline data for 30 days
            )

        except Exception as e:
            print(f"Cloud sync error: {e}")


# =============================================================================
# PATTERN 2: CLOUD-ENABLED TREND ANALYSIS (~60 lines)
# Extremely difficult without cloud sync + persistent storage
# =============================================================================

class CloudTrendAnalysis:
    """
    Detect trends locally AND sync to cloud for remote monitoring/control
    
    Traditional approach: Local only, no remote visibility
    MicroTetherDB + Tendrl: Cloud connectivity for data analysis
    """

    def __init__(self, pin=4, sync_interval_minutes=30):
        self.sensor = DHT22(Pin(pin)) if HARDWARE else None
        self.sync_interval = sync_interval_minutes * 60
        self.last_sync = 0

        # Persistent storage for reliable trend detection
        if DB_AVAILABLE:
            self.db = MicroTetherDB(
                in_memory=False,  # File storage survives restarts
                filename="cloud_trends.db",
                ttl_check_interval=1800  # 30 minutes
            )
        else:
            self.db = None

        # Cloud client with tether decorator support
        if CLOUD_AVAILABLE:
            self.client = Client(
                debug=False,
                offline_storage=True,
                managed=True
            )
            try:
                self.client.start()
                self.cloud_enabled = True
                print("☁️ Cloud trend detection enabled")
            except:
                self.cloud_enabled = False
        else:
            self.cloud_enabled = False

    def take_reading(self):
        """Take reading with cloud sync"""
        if not self.sensor or not self.db:
            return

        self.sensor.measure()
        temp, humidity = self.sensor.temperature(), self.sensor.humidity()
        now = time.time()

        # Store locally with 7-day TTL
        self.db.put({
            'temp': temp, 
            'humidity': humidity, 
            'timestamp': now
        }, ttl=7*24*3600)

        # Detect trends locally
        trend_info = self._detect_local_trends(now)

        # Sync to cloud if interval passed
        if now - self.last_sync > self.sync_interval:
            self._sync_to_cloud(temp, humidity, trend_info, now)
            self.last_sync = now

    def _detect_local_trends(self, current_time):
        """Detect trends using persistent data"""
        # Get last 24 hours of data
        trend_data = self.db.query({
            'timestamp': {'$gte': current_time - 86400},
            'temp': {'$exists': True}
        })

        if len(trend_data) < 10:
            return None

        # Calculate 24-hour trend
        trend_data.sort(key=lambda x: x['timestamp'])
        time_span = trend_data[-1]['timestamp'] - trend_data[0]['timestamp']
        temp_change = trend_data[-1]['temp'] - trend_data[0]['temp']

        if time_span > 0:
            trend_per_hour = (temp_change / time_span) * 3600

            trend_info = {
                'trend_per_hour': round(trend_per_hour, 2),
                'data_points': len(trend_data),
                'time_span_hours': round(time_span / 3600, 1),
                'is_significant': abs(trend_per_hour) > 1.0
            }

            if trend_info['is_significant']:
                direction = "rising" if trend_per_hour > 0 else "falling"
                print(f"📈 TREND: {direction} {abs(trend_per_hour):.1f}°C/hour "
                      f"(from {len(trend_data)} readings)")

            return trend_info

        return None

    def _sync_to_cloud(self, temp, humidity, trend_info, timestamp):
        """Sync trends to cloud with offline storage"""
        if not self.cloud_enabled:
            return

        try:
            sync_data = {
                'local_analysis': {
                    'current_temp': temp,
                    'current_humidity': humidity,
                    'trend_analysis': trend_info,
                    'storage_persistent': True,
                    'sync_timestamp': timestamp
                }
            }

            # Direct publish with offline storage
            self.client.publish(
                data=sync_data,
                tags=['trend_analysis', 'iot_analysis'],
                entity='dht_trend_detector',
                write_offline=True,
                db_ttl=14*24*3600  # 2 weeks offline storage
            )

            print("☁️ Synced trend data to cloud")

        except Exception as e:
            print(f"Cloud sync error: {e}")


# =============================================================================
# PATTERN 3: ADAPTIVE STATISTICS WITH CLOUD FEEDBACK (~80 lines)
# Extremely difficult without bidirectional cloud communication + persistent storage
# =============================================================================

class CloudAdaptiveStatistics:
    """
    Learn locally, get cloud intelligence, adapt thresholds remotely
    
    Traditional approach: Fixed thresholds, no remote updates
    MicroTetherDB + Tendrl: Cloud-connected adaptive thresholds
    """

    def __init__(self, pin=4):
        self.sensor = DHT22(Pin(pin)) if HARDWARE else None

        # Persistent adaptive thresholds
        self.learned_temp_range = [10, 35]
        self.adaptation_count = 0

        # Long-term storage for learning
        if DB_AVAILABLE:
            self.db = MicroTetherDB(
                in_memory=False,
                filename="adaptive_learning.db",
                ttl_check_interval=3600
            )
        else:
            self.db = None

        # Cloud client for bidirectional communication
        if CLOUD_AVAILABLE:
            self.client = Client(
                debug=False,
                offline_storage=True
            )
            try:
                self.client.start()
                self.cloud_enabled = True
                print("☁️ Cloud adaptive learning enabled")

                # Example of correct tether decorator usage:
                # 1. Decorate a function that returns a dict
                # 2. The decorator handles publishing automatically
                # 3. Supports offline storage when network is unavailable
                @self.client.tether(
                    write_offline=True,
                    db_ttl=30*24*3600,  # 30 days
                    tags=['system_status', 'initialization'],
                    entity='adaptive_learner_status'
                )
                def send_initialization_status():
                    return {
                        'status': 'initialized',
                        'learning_enabled': True,
                        'temp_range': self.learned_temp_range,
                        'timestamp': time.time()
                    }

                # Call the tethered function to send initialization status
                send_initialization_status()

            except:
                self.cloud_enabled = False
        else:
            self.cloud_enabled = False

    def take_reading(self):
        """Take reading with cloud-enhanced adaptive learning"""
        if not self.sensor or not self.db:
            return

        self.sensor.measure()
        temp, humidity = self.sensor.temperature(), self.sensor.humidity()
        now = time.time()

        # Store with 30-day TTL for long-term learning
        self.db.put({
            'temp': temp, 
            'humidity': humidity, 
            'timestamp': now,
            'learned_min': self.learned_temp_range[0],
            'learned_max': self.learned_temp_range[1]
        }, ttl=30*24*3600)

        # Adapt thresholds based on historical data
        if int(now) % 3600 == 0:  # Every hour
            self._adapt_with_cloud_intelligence(now)

        # Check against learned thresholds
        self._check_adaptive_thresholds(temp, humidity)

    def _adapt_with_cloud_intelligence(self, current_time):
        """Adapt thresholds using local data + cloud intelligence"""
        # Get 30 days of historical data
        historical = self.db.query({
            'timestamp': {'$gte': current_time - (30 * 24 * 3600)},
            'temp': {'$exists': True}
        })

        if len(historical) >= 100:  # Need substantial data
            temps = sorted([r['temp'] for r in historical])

            # Calculate new ranges using percentiles
            new_min = temps[int(len(temps) * 0.1)]  # 10th percentile
            new_max = temps[int(len(temps) * 0.9)]  # 90th percentile

            # Gradual adaptation
            old_range = self.learned_temp_range.copy()
            self.learned_temp_range[0] = self.learned_temp_range[0] * 0.8 + new_min * 0.2
            self.learned_temp_range[1] = self.learned_temp_range[1] * 0.8 + new_max * 0.2

            self.adaptation_count += 1

            # Send adaptation to cloud for remote monitoring
            if self.cloud_enabled:
                adaptation_data = {
                    'threshold_adaptation': {
                        'old_range': old_range,
                        'new_range': self.learned_temp_range,
                        'adaptation_count': self.adaptation_count,
                        'data_points_used': len(historical),
                        'learning_days': 30
                    }
                }

                self.client.publish(
                    data=adaptation_data,
                    tags=['adaptive_learning', 'threshold_update'],
                    entity='dht_adaptive_system',
                    write_offline=True,
                    db_ttl=90*24*3600  # 3 months offline storage
                )

            print(f"🎯 Adapted thresholds (#{self.adaptation_count}): "
                  f"{self.learned_temp_range[0]:.1f}-{self.learned_temp_range[1]:.1f}°C "
                  f"from {len(historical)} readings")

    def _check_adaptive_thresholds(self, temp, humidity):
        """Check against learned thresholds with cloud alerting"""
        if temp < self.learned_temp_range[0] or temp > self.learned_temp_range[1]:
            alert_data = {
                'adaptive_alert': {
                    'temperature': temp,
                    'humidity': humidity,
                    'learned_range': self.learned_temp_range,
                    'adaptation_count': self.adaptation_count,
                    'alert_type': 'learned_threshold_breach'
                }
            }

            print(f"🚨 ADAPTIVE ALERT: {temp}°C outside learned range "
                  f"({self.learned_temp_range[0]:.1f}-{self.learned_temp_range[1]:.1f}°C)")

            # Send alert to cloud
            if self.cloud_enabled:
                self.client.publish(
                    data=alert_data,
                    tags=['alerts', 'adaptive_learning'],
                    entity='dht_adaptive_alerts',
                    write_offline=True,
                    db_ttl=7*24*3600  # 1 week offline storage
                )


# =============================================================================
# USAGE EXAMPLES - Showcasing Unique Capabilities
# =============================================================================

def demo_long_term_analysis():
    """Demo: Long-term statistical analysis extremely difficult with traditional storage"""
    print("=== Long-Term Statistical Analysis (30 days of data) ===")
    print("Traditional storage: Extremely difficult - limited to ~100 readings in RAM")
    print("MicroTetherDB: Weeks of data with efficient time-series queries")

    analyzer = LongTermStatisticalAnalysis(pin=4, learning_days=30)

    # Simulate taking readings over time
    for _ in range(50):
        analyzer.take_reading()
        if not HARDWARE:
            break
        time.sleep(2)

def demo_cloud_trends():
    """Demo: Cloud-synced trend analysis with offline storage"""
    print("=== Cloud Trend Analysis ===")
    print("Traditional approach: Local only, no remote monitoring")
    print("MicroTetherDB + Tendrl: Bidirectional cloud intelligence")

    analyzer = CloudTrendAnalysis(pin=4, sync_interval_minutes=5)

    for _ in range(30):
        analyzer.take_reading()
        if not HARDWARE:
            break
        time.sleep(3)

def demo_cloud_adaptive():
    """Demo: Cloud-enhanced adaptive statistics"""
    print("=== Cloud Adaptive Statistics ===")
    print("Traditional approach: Fixed thresholds, no remote updates")
    print("MicroTetherDB + Tendrl: Cloud-enhanced adaptive intelligence")

    analyzer = CloudAdaptiveStatistics(pin=4)

    for _ in range(100):
        analyzer.take_reading()
        if not HARDWARE:
            break
        time.sleep(1)


if __name__ == "__main__":
    print("📊 MicroTetherDB + Tendrl: Advanced Statistical Analysis Patterns")
    print()
    print("These patterns demonstrate statistical capabilities that were extremely difficult")
    print("with traditional microcontroller storage approaches:")
    print()
    print("1. 📊 Long-term statistical analysis from weeks of persistent data")
    print("2. ☁️ Cloud-synced trend analysis with offline storage")
    print("3. 🎯 Adaptive statistics with bidirectional cloud feedback")
    print()

    if DB_AVAILABLE and CLOUD_AVAILABLE:
        print("✅ Full capabilities available!")
        print("Uncomment demo functions to see advanced statistical patterns:")
        print("# demo_long_term_analysis()")
        print("# demo_cloud_trends()")
        print("# demo_cloud_adaptive()")
    elif DB_AVAILABLE:
        print("⚠️ MicroTetherDB available, but Tendrl client missing")
        print("Install Tendrl client for cloud capabilities")
    else:
        print("⚠️ Install MicroTetherDB + Tendrl for full capabilities")
