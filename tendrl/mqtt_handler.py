import gc
import json
import time
import requests


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

# Import OpenMV detection utility
from .utils.util_helpers import is_openmv

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
        # Track subscription state to detect when re-subscription is needed
        self._subscribed = False

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

            api_base_url = self.config.get("app_url", "https://app.tendrl.com")

            # Ensure the URL has a protocol prefix
            if not api_base_url.startswith(('http://', 'https://')):
                api_base_url = f"http://{api_base_url}"

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            # Include client version in query parameter if available
            client_version = self.config.get('client_version', '')
            url = f'{api_base_url}/api/claims'
            if client_version:
                url = f'{url}?e_type={client_version}'

            gc.collect()
            response = requests.get(url, headers=headers)

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
        self._subscribed = False  # Reset subscription state on new connection
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

        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # On first attempt, allow time for DNS resolution and SSL stack initialization
                    # DNS resolution can fail on first attempt if network stack isn't fully ready
                    # Do this BEFORE cleaning up old client to give network stack time to initialize
                    if attempt == 0:
                        # Longer delay to allow DNS resolution to initialize
                        # This helps avoid ENOENT (-2) errors on first connection
                        time.sleep(1.0)

                        # For OpenMV with SSL, also allow SSL stack initialization time
                        if is_openmv() and mqtt_ssl:
                            time.sleep(2.0)  # Increased time for SSL context initialization on OpenMV
                    elif attempt > 0:
                        # After a failed attempt, wait longer before retrying
                        # This is especially important after timeout errors
                        retry_delay = 3 + (2 ** attempt)  # 5s, 7s, 11s for attempts 1, 2, 3
                        if self.debug:
                            print(f"   (Waiting {retry_delay}s before retry...)")
                        time.sleep(retry_delay)

                    # Clean up any existing MQTT client - check if it's valid first
                    # Do this AFTER the delay to avoid disconnecting a partially initialized client
                    if self._mqtt:
                        try:
                            # Only try to disconnect if the client has a disconnect method
                            # and if it's actually connected (has a valid socket)
                            if hasattr(self._mqtt, 'disconnect'):
                                # Check if client is connected before trying to disconnect
                                # This avoids errors when socket is None
                                is_connected = False
                                if hasattr(self._mqtt, 'sock') and self._mqtt.sock is not None:
                                    is_connected = True
                                elif hasattr(self._mqtt, 'isconnected') and callable(self._mqtt.isconnected):
                                    is_connected = self._mqtt.isconnected()

                                if is_connected:
                                    self._mqtt.disconnect()
                        except (AttributeError, OSError) as close_err:
                            # AttributeError/OSError from None socket is expected for failed connections
                            # Only log if it's not a NoneType error (which is expected)
                            if self.debug and "'NoneType'" not in str(close_err) and "write" not in str(close_err):
                                print(f"Error disconnecting existing MQTT client: {close_err}")
                        except Exception as close_err:
                            # Other errors might be worth logging
                            if self.debug:
                                print(f"Error disconnecting existing MQTT client: {close_err}")
                        finally:
                            # Always clear the reference after attempting disconnect
                            self._mqtt = None

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

                    # Add socket timeout for OpenMV (SSL handshake can take time)
                    # Some MQTT implementations support socket_timeout parameter
                    if is_openmv() and mqtt_ssl:
                        # OpenMV MQTT client may support socket_timeout
                        # This helps prevent ETIMEDOUT during SSL handshake
                        # Try adding socket_timeout - if client doesn't support it, will fail during construction
                        mqtt_params["socket_timeout"] = 30  # 30 second timeout for SSL handshake

                    # Add SSL parameters if SSL is enabled
                    # ssl_params is needed for both umqtt.robust and mqtt(openMV) module
                    if mqtt_ssl:
                        if MQTT_SSL_ENABLED:
                            # umqtt.robust supports ssl parameter
                            mqtt_params["ssl"] = mqtt_ssl
                        # ssl_params is needed for both implementations
                        mqtt_params["ssl_params"] = {"server_hostname": mqtt_host}

                    # Try to create MQTT client - if socket_timeout is not supported, retry without it
                    try:
                        self._mqtt = MQTTClient(**mqtt_params)
                    except TypeError:
                        # socket_timeout parameter not supported, remove it and try again
                        if "socket_timeout" in mqtt_params:
                            del mqtt_params["socket_timeout"]
                            self._mqtt = MQTTClient(**mqtt_params)
                        else:
                            raise  # Re-raise if it's a different TypeError

                    self._mqtt.set_callback(self._on_message)

                    if self.debug:
                        print("Attempting to connect...")

                    gc.collect()
                    self._mqtt.connect()
                    gc.collect()

                    # Set connection status before attempting subscription
                    self.connected = True
                    self._consecutive_errors = 0

                    try:
                        self._subscribe_to_topics()
                        self._subscribed = True  # Mark as subscribed after successful subscription
                    except Exception as sub_err:
                        if self.debug:
                            print(f"Subscription warning (non-critical): {sub_err}")
                        self._subscribed = False

                    if self.debug:
                        print(f"MQTT connected successfully to {mqtt_host}")
                    return True

                except MQTTException as mqtt_err:
                    if self.debug:
                        print(f"MQTT connection error (Attempt {attempt + 1}): {mqtt_err}")
                        print(f"   Host: {mqtt_host}, Port: {mqtt_port}")
                    self.connected = False
                    # Don't sleep here - delay is handled before the retry attempt
                    continue

            self._mqtt = None
            self.connected = False
            self._subscribed = False
            if self.debug:
                print("All MQTT connection attempts failed")
            return False

        except Exception as overall_err:
            if self.debug:
                print(f"Critical MQTT connection failure: {overall_err}")
            self._mqtt = None
            self.connected = False
            self._subscribed = False
            return False

    def _subscribe_to_topics(self):
        if not self._mqtt or not self.connected:
            if self.debug:
                print("Cannot subscribe - MQTT not connected")
            return False

        try:
            # Subscribe to messages topic to receive commands/notifications
            messages_topic = self._build_messages_topic()
            self._mqtt.subscribe(messages_topic, qos=QOS)

            if self.debug:
                print(f"Subscribed to messages topic: {messages_topic}")
            return True

        except Exception as e:
            if self.debug:
                print(f"Error subscribing to topics: {e}")
            return False

    def _on_message(self, topic, msg):
        try:
            msg_str = msg.decode('utf-8')

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
        self._subscribed = False  # Reset subscription state on manual reconnect
        try:
            if self._mqtt:
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
            
            # Check if we need to re-subscribe (umqtt.robust uses CleanSession=True, so subscriptions are lost)
            # Check actual connection state to detect if robust reconnected
            is_actually_connected = False
            if hasattr(self._mqtt, 'sock') and self._mqtt.sock is not None:
                is_actually_connected = True
            elif hasattr(self._mqtt, 'isconnected') and callable(self._mqtt.isconnected):
                is_actually_connected = self._mqtt.isconnected()
            
            # Re-subscribe if we're connected but not subscribed (robust may have reconnected)
            if is_actually_connected and not self._subscribed:
                if self.debug:
                    print("Re-subscribing after reconnection detected in publish...")
                if self._subscribe_to_topics():
                    self._subscribed = True
            return True, False
        except Exception as e:
            if self.debug:
                print(f"Error in publish_message: {e}")
            # Mark as disconnected - robust will attempt reconnection on next operation
            self.connected = False
            self._subscribed = False  # Reset subscription state on error
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
            return True

        chunks = self._chunk_messages(messages)

        success_count = 0
        connection_error_count = 0

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
        return connection_error_count == 0

    def check_messages(self):
        if self._mqtt is None:
            if self.debug:
                print("MQTT client not initialized - cannot check messages")
            return False

        try:
            # Check actual connection state before check_msg (umqtt.robust may have reconnected automatically)
            # umqtt.robust uses CleanSession=True, so subscriptions are lost on disconnect
            # We need to re-subscribe after any reconnection
            was_connected_before = self.connected
            is_actually_connected = False
            if hasattr(self._mqtt, 'sock') and self._mqtt.sock is not None:
                is_actually_connected = True
            elif hasattr(self._mqtt, 'isconnected') and callable(self._mqtt.isconnected):
                is_actually_connected = self._mqtt.isconnected()
            
            # If we're connected but not subscribed, re-subscribe
            # This handles the case where umqtt.robust reconnected automatically
            if is_actually_connected and not self._subscribed:
                if self.debug:
                    print("Connection detected but not subscribed - re-subscribing...")
                if self._subscribe_to_topics():
                    self._subscribed = True
                else:
                    # Subscription failed, mark as not subscribed
                    self._subscribed = False
            
            # check_msg() returns None but processes messages via callback
            # umqtt.robust will automatically reconnect if connection is lost
            self._mqtt.check_msg()
            # If check_msg succeeds, we're connected (robust may have reconnected during check_msg)
            self.connected = True
            
            # After check_msg, check again if we need to re-subscribe
            # (check_msg might have triggered a reconnection)
            if self.connected and not self._subscribed:
                if self.debug:
                    print("Re-subscribing after check_msg (reconnection detected)...")
                if self._subscribe_to_topics():
                    self._subscribed = True
            
            return True
        except Exception as e:
            if self.debug:
                print(f"Error checking messages: {e}")
            # Mark as disconnected - robust will attempt reconnection on next operation
            self.connected = False
            self._subscribed = False  # Reset subscription state on error
            return False

    def cleanup(self):
        try:
            if self._mqtt:
                self._mqtt.disconnect()
                self._mqtt = None
            self.connected = False
            self._subscribed = False
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
