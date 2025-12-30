import json
import time
import requests
import gc

try:
    from umqtt.simple import MQTTException
    from umqtt.robust import MQTTClient
    QOS = 1
    MQTT_SSL_ENABLED = True
except ImportError:
    try:
        from mqtt import MQTTClient, MQTTException
        QOS = 0
        MQTT_SSL_ENABLED = False
    except ImportError:
        print("Warning: mqtt not available")

from .config_manager import update_entity_cache , get_entity_cache


class MQTTHandler:
    """
    MQTT Handler using umqtt.robust for automatic reconnection.
    The robust client automatically handles reconnection on network errors,
    so operations will attempt to reconnect if the connection is lost.
    """
    def __init__(self, config, debug=False, callback=None):
        self._mqtt = None
        self.config = config
        self.debug = debug
        self.connected = False  # Tracks connection state, but robust handles reconnection
        self._consecutive_errors = 0
        self._max_batch_size = 4096
        self._max_messages_per_batch = 50
        self._reconnect_delay = 5
        self.entity_info = None
        self.callback = callback
        # Cache topics to avoid repeated string operations (performance optimization)
        self._publish_topic = None
        self._messages_topic = None

    def _fetch_entity_info(self):
        try:
            api_key = self.config.get("api_key")
            if not api_key:
                if self.debug:
                    print("Missing API key in configuration")
                return False

            # Try to get cached entity info from separate cache file
            cached_api_key_id, cached_subject = get_entity_cache()

            if cached_api_key_id and cached_subject:
                if self.debug:
                    print("Using cached entity info")
                self.entity_info = {
                    'jti': cached_api_key_id,
                    'sub': cached_subject
                }
                # Invalidate cached topics when entity_info changes
                self._publish_topic = None
                self._messages_topic = None
                return True

            if self.debug:
                print("Fetching entity info from API...")

            api_base_url = self.config.get("app_url", "https://app.tendrl.com")

            # Ensure the URL has a protocol prefix
            if not api_base_url.startswith(('http://', 'https://')):
                api_base_url = f"http://{api_base_url}"

            if self.debug:
                print(f"API Base URL: {api_base_url}")

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            url = f'{api_base_url}/api/claims'
            if self.debug:
                print(f"Fetching entity info from: {url}")

            gc.collect()
            response = requests.get(url, headers=headers)

            if self.debug:
                print(f"API Response Status: {response.status_code}")

            if response.status_code == 200:
                gc.collect()
                time.sleep(1)
                entity_info = response.json()

                # Cache entity info
                try:
                    update_entity_cache(
                        api_key_id=entity_info.get('jti'),
                        subject=entity_info.get('sub')
                    )
                    if self.debug:
                        print("Caching entity info")
                except Exception as cache_err:
                    if self.debug:
                        print(f"Error updating entity cache: {cache_err}")

                self.entity_info = entity_info
                # Invalidate cached topics when entity_info changes
                self._publish_topic = None
                self._messages_topic = None
                return True
            else:
                if self.debug:
                    print(f"Failed to fetch entity info: {response.status_code}")
                return False
        except Exception as e:
            if self.debug:
                print(f"Entity info fetch error: {e}")
            return False



    def _build_publish_topic(self):
        """Build the publish topic, which is always the same for all message types."""
        # Return cached topic if available (performance optimization)
        if self._publish_topic:
            return self._publish_topic
            
        if not self.entity_info:
            raise Exception('Entity info not available')

        sub = self.entity_info.get('sub', '')
        sub_parts = sub.split(':')
        if len(sub_parts) < 2:
            raise Exception('Invalid resource path format')

        account = sub_parts[0]
        region = sub_parts[1]
        jti = self.entity_info.get('jti', '')

        if not jti:
            raise Exception('JTI not found in entity info')

        # Cache the topic to avoid repeated string operations
        self._publish_topic = f"{account}/{region}/{jti}/publish"
        return self._publish_topic

    def _build_messages_topic(self):
        """Build the messages topic for subscribing to incoming messages."""
        # Return cached topic if available (performance optimization)
        if self._messages_topic:
            return self._messages_topic
            
        if not self.entity_info:
            raise Exception('Entity info not available')

        sub = self.entity_info.get('sub', '')
        sub_parts = sub.split(':')
        if len(sub_parts) < 2:
            raise Exception('Invalid resource path format')

        account = sub_parts[0]
        region = sub_parts[1]
        jti = self.entity_info.get('jti', '')

        if not jti:
            raise Exception('JTI not found in entity info')

        # Cache the topic to avoid repeated string operations
        self._messages_topic = f"{account}/{region}/{jti}/messages"
        return self._messages_topic

    def _validate_and_prepare_data(self, data):
        if data is None:
            raise Exception('Message data cannot be None')

        if isinstance(data, dict):
            return data

        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, TypeError):
                return {"message": data}

    def connect(self):
        self.connected = False
        self._consecutive_errors = 0

        if not self._fetch_entity_info():
            if self.debug:
                print("Failed to fetch entity information")
            return False

        if not self.entity_info.get('jti'):
            if self.debug:
                print("API key ID not found in API claims. Check your API key.")
            return False

        if not self.entity_info.get('sub'):
            if self.debug:
                print("Subject not found in API claims.")
            return False

        mqtt_host = self.config.get("mqtt_host")
        mqtt_port = self.config.get("mqtt_port")
        mqtt_ssl = self.config.get("mqtt_ssl")

        if self.debug:
            print(f"MQTT config: {mqtt_host}:{mqtt_port})")

        # Validate MQTT host configuration
        if not mqtt_host or mqtt_host.strip() == "":
            if self.debug:
                print("MQTT host is empty or not configured")
            return False

        api_key = self.config.get("api_key")
        if not api_key:
            if self.debug:
                print("Missing API key in configuration")
            return False

        client_id = self.entity_info['sub']
        username = self.entity_info['jti']
        password = api_key

        if self.debug:
            print(f"Connecting to MQTT broker: {mqtt_host}:{mqtt_port}")
            print(f"Client ID: {client_id}")
            print(f"Username: {username}")

        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if self._mqtt:
                        try:
                            self._mqtt.disconnect()
                        except Exception as close_err:
                            if self.debug:
                                print(f"Error disconnecting existing MQTT client: {close_err}")

                    # Build MQTT client parameters conditionally
                    # umqtt.robust supports ssl/ssl_params, but mqtt(openMV) does not have ssl param
                    mqtt_params = {
                        "client_id": client_id,
                        "server": mqtt_host,
                        "port": mqtt_port,
                        "user": username,
                        "password": password,
                        "keepalive": 300,
                    }

                    # Add SSL parameters if SSL is enabled
                    # ssl_params is needed for both umqtt.robust and mqtt(openMV) module
                    if mqtt_ssl:
                        if MQTT_SSL_ENABLED:
                            # umqtt.robust supports ssl parameter
                            mqtt_params["ssl"] = mqtt_ssl
                        # ssl_params is needed for both implementations
                        mqtt_params["ssl_params"] = {"server_hostname": mqtt_host}

                    self._mqtt = MQTTClient(**mqtt_params)

                    self._mqtt.set_callback(self._on_message)

                    if self.debug:
                        print("Attempting to connect...")
                    
                    # On OpenMV, the first SSL connection can be slow due to SSL stack initialization
                    # The SSL context needs to be created and certificates loaded on first use
                    # This can cause ETIMEDOUT on the first attempt, but retries succeed
                    # Add a small delay before first attempt to allow SSL context to initialize
                    if attempt == 0 and not MQTT_SSL_ENABLED and mqtt_ssl:
                        # OpenMV's mqtt module - first SSL connection needs warm-up time
                        # Give SSL stack a moment to initialize before attempting connection
                        if self.debug:
                            print("   (OpenMV: Allowing SSL stack initialization time...)")
                        time.sleep(2)  # 2 seconds for SSL context initialization
                    
                    gc.collect()
                    self._mqtt.connect()
                    gc.collect()

                    # Set connection status before attempting subscription
                    self.connected = True
                    self._consecutive_errors = 0

                    try:
                        self._subscribe_to_topics()
                    except Exception as sub_err:
                        if self.debug:
                            print(f"Subscription warning (non-critical): {sub_err}")

                    if self.debug:
                        print(f"MQTT connected successfully to {mqtt_host}")
                    return True

                except MQTTException as mqtt_err:
                    if self.debug:
                        print(f"MQTT connection error (Attempt {attempt + 1}): {mqtt_err}")
                        print(f"   Host: {mqtt_host}, Port: {mqtt_port}")
                    self.connected = False
                    time.sleep(2**attempt)
                    continue
                except Exception as e:
                    if self.debug:
                        print(f"Unexpected MQTT connection error (Attempt {attempt + 1}): {e}")
                        print(f"   Error type: {type(e).__name__}")
                        print(f"   Host: {mqtt_host}, Port: {mqtt_port}")
                    self.connected = False
                    time.sleep(2**attempt)
                    continue

            self._mqtt = None
            self.connected = False
            if self.debug:
                print("All MQTT connection attempts failed")
            return False

        except Exception as overall_err:
            if self.debug:
                print(f"Critical MQTT connection failure: {overall_err}")
            self._mqtt = None
            self.connected = False
            return False

    def _subscribe_to_topics(self):
        if not self._mqtt or not self.connected:
            if self.debug:
                print("Cannot subscribe - MQTT not connected")
            return

        try:
            # Subscribe to messages topic to receive commands/notifications
            messages_topic = self._build_messages_topic()
            self._mqtt.subscribe(messages_topic, qos=QOS)

            if self.debug:
                print(f"Subscribed to messages topic: {messages_topic}")

        except Exception as e:
            if self.debug:
                print(f"Error subscribing to topics: {e}")

    def _on_message(self, topic, msg):
        try:
            # Only decode topic if debug is enabled (performance optimization)
            if self.debug:
                topic_str = topic.decode('utf-8')
            msg_str = msg.decode('utf-8')

            if self.debug:
                print(f"Received message on topic {topic_str}: {msg_str}")

            try:
                message_data = json.loads(msg_str)
            except json.JSONDecodeError:
                if self.debug:
                    print(f"Invalid JSON in message: {msg_str}")
                return

            if self.callback and callable(self.callback):
                try:
                    self.callback(message_data)
                except Exception as e:
                    if self.debug:
                        print(f"Callback error: {e}")

        except Exception as e:
            if self.debug:
                print(f"Error handling MQTT message: {e}")

    def _try_reconnect(self):
        self.connected = False
        try:
            if self._mqtt:
                if self.debug:
                    print("Disconnecting existing MQTT client")
                self._mqtt.disconnect()
        except Exception as close_err:
            if self.debug:
                print(f"Error disconnecting existing client: {close_err}")

        time.sleep(self._reconnect_delay)

        return self.connect()

    def publish_message(self, data):
        # With umqtt.robust, allow automatic reconnection attempts
        # Only check if MQTT client exists, not connection state
        if self._mqtt is None:
            if self.debug:
                print("MQTT client not initialized")
            return False, True

        try:
            p = json.dumps(data)
            # Always use the publish topic
            topic = self._build_publish_topic()

            # umqtt.robust will automatically reconnect if connection is lost
            self._mqtt.publish(topic, p)
            # If publish succeeds, we're connected (robust handles reconnection)
            self.connected = True
            return True, False
        except Exception as e:
            if self.debug:
                print(f"Error in publish_message: {e}")
            # Mark as disconnected - robust will attempt reconnection on next operation
            self.connected = False
            return False, True

    def _chunk_messages(self, messages):
        """
        Chunk messages into batches based on size limits.
        Uses estimated size calculation to avoid expensive json.dumps() calls.
        """
        chunks = []
        current_chunk = []
        current_size = 0

        for msg in messages:
            # Estimate message size without expensive json.dumps() + encode()
            # JSON overhead: ~50-100 bytes (keys, structure, quotes, etc.)
            # For dicts: estimate based on content length (much faster than json.dumps)
            if isinstance(msg, dict):
                # Quick size estimate: sum of string lengths + JSON overhead
                # This avoids expensive json.dumps() + encode() calls
                estimated_size = 100  # Base JSON structure overhead
                for k, v in msg.items():
                    k_str = str(k)
                    # Estimate value size without json.dumps() for nested structures
                    if isinstance(v, (dict, list)):
                        # Rough estimate for nested: count items * average size
                        v_size = 50  # Conservative estimate for nested structures
                    else:
                        v_str = str(v)
                        v_size = len(v_str)
                    estimated_size += len(k_str) + v_size + 10  # Key + value + JSON overhead
            else:
                # For strings, estimate is just string length + JSON quotes
                msg_str = str(msg)
                estimated_size = len(msg_str) + 10  # String + JSON overhead
            
            if (current_size + estimated_size > self._max_batch_size or
                len(current_chunk) >= self._max_messages_per_batch):
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [msg]
                current_size = estimated_size
            else:
                current_chunk.append(msg)
                current_size += estimated_size

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def send_batch(self, messages):
        # With umqtt.robust, allow automatic reconnection attempts
        if self._mqtt is None:
            if self.debug:
                print("MQTT client not initialized - cannot send batch")
            return False

        if not messages:
            if self.debug:
                print("No messages to send in batch")
            return True

        chunks = self._chunk_messages(messages)

        success_count = 0
        connection_error_count = 0
        total_messages = len(messages)

        if self.debug:
            print(f"Sending batch of {total_messages} messages in {len(chunks)} chunks")

        for chunk_idx, chunk in enumerate(chunks):
            try:
                for msg in chunk:
                    success, is_connection_error = self.publish_message(msg)
                    if success:
                        success_count += 1
                    elif is_connection_error:
                        connection_error_count += 1
                        if self.debug:
                            print(f"Connection error sending message in batch: {msg}")
                    else:
                        if self.debug:
                            print(f"Validation error sending message in batch: {msg}")

            except Exception as e:
                if self.debug:
                    print(f"Error sending batch chunk {chunk_idx}: {e}")
                connection_error_count += 1

        if self.debug:
            if success_count == total_messages:
                print(f"Batch send complete: {success_count}/{total_messages} messages sent successfully")
            elif connection_error_count > 0:
                print(f"Batch send failed: {connection_error_count} connection errors")
            else:
                print(f"Batch send partial: {success_count}/{total_messages} messages sent")

        return connection_error_count == 0

    def check_messages(self):
        """
        Check for incoming MQTT messages. This is a non-blocking call that
        processes any pending messages by triggering the callback function.
        With umqtt.robust, automatic reconnection is handled internally.
        
        Returns:
            True if the check was successful (messages are processed via callback)
            False if there was an error or MQTT client not initialized
        """
        if self._mqtt is None:
            if self.debug:
                print("MQTT client not initialized - cannot check messages")
            return False

        try:
            # check_msg() returns None but processes messages via callback
            # umqtt.robust will automatically reconnect if connection is lost
            self._mqtt.check_msg()
            # If check_msg succeeds, we're connected
            self.connected = True
            return True
        except Exception as e:
            if self.debug:
                print(f"Error checking messages: {e}")
            # Mark as disconnected - robust will attempt reconnection on next operation
            self.connected = False
            return False

    def cleanup(self):
        try:
            if self._mqtt:
                if self.debug:
                    print("Disconnecting MQTT client")
                self._mqtt.disconnect()
                self._mqtt = None
            self.connected = False
            if self.debug:
                print("MQTT cleanup completed")
        except Exception as e:
            if self.debug:
                print(f"Error during MQTT cleanup: {e}")

    def send_file_system_command_response(self, output="", error="", exit_code=0, request_id=None):
        response_data = {
            "output": output,
            "error": error,
            "exitCode": exit_code
        }
        if request_id:
            response_data["request_id"] = request_id
        return self.publish_message(response_data)

    def send_terminal_command_response(self, output="", error="", exit_code=0, request_id=None):
        response_data = {
            "output": output,
            "error": error,
            "exitCode": exit_code
        }
        if request_id:
            response_data["request_id"] = request_id
        return self.publish_message(response_data)

    def send_client_command_response(self, data, request_id=None):
        if request_id:
            data["request_id"] = request_id
        return self.publish_message(data)

    def send_file_transfer(self, file_data):
        return self.publish_message(file_data)
