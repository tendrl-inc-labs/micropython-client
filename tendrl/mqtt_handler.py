import json
import time
import _thread
import requests
import gc


from umqtt.simple import MQTTClient, MQTTException
from .config_manager import (
    update_entity_cache, 
    get_entity_cache, 
    _compute_api_key_hash,
    read_config
)

TENDRL_VERSION = "tendrl-micropython/0.1.0"

class MQTTHandler:
    def __init__(self, config, debug=False, callback=None):
        self._mqtt = None
        self._mqtt_lock = _thread.allocate_lock()
        self.config = config
        self.debug = debug
        self.connected = False
        self._consecutive_errors = 0
        self._max_batch_size = 4096
        self._max_messages_per_batch = 50
        self._reconnect_delay = 5
        self.entity_info = None
        self.callback = callback

    def _fetch_entity_info(self):
        response = None
        try:
            # Read config.json directly to check for API key changes after initialization
            current_config = read_config()
            api_key = current_config.get("api_key")
            if not api_key:
                if self.debug:
                    print("❌ Missing API key in configuration")
                return False

            self.config.update(current_config)
            api_key_hash = _compute_api_key_hash(api_key)

            cached_api_key_id, cached_subject = get_entity_cache(
                api_key_hash, 
                check_config_file=True,
                debug=self.debug
            )

            if cached_api_key_id and cached_subject:
                if (isinstance(cached_api_key_id, str) and 
                    isinstance(cached_subject, str) and
                    len(cached_api_key_id.strip()) > 0 and
                    len(cached_subject.strip()) > 0):
                    self.entity_info = {
                        'jti': cached_api_key_id,
                        'sub': cached_subject
                    }
                    if self.debug:
                        print("✅ Using cached entity info")
                    return True
                else:
                    if self.debug:
                        print("⚠️ Cached entity info invalid - fetching fresh")

            api_base_url = self.config.get("app_url", "https://app.tendrl.com")
            if not api_base_url.startswith(('http://', 'https://')):
                api_base_url = f"http://{api_base_url}"

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            url = f'{api_base_url}/api/claims?e_type={TENDRL_VERSION}'

            # GC before request to maximize available memory (critical for ESP32-WROOM)
            gc.collect()
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                # Parse JSON and close response immediately to free HTTP/SSL buffers
                try:
                    entity_info = response.json()
                except Exception as json_err:
                    if self.debug:
                        print(f"❌ Failed to parse JSON response: {json_err}")
                    try:
                        response.close()
                    except Exception:
                        pass
                    response = None
                    gc.collect()
                    return False
                finally:
                    # Close response immediately to free 30-70KB of HTTP/SSL buffers
                    try:
                        response.close()
                    except Exception:
                        pass
                    response = None
                    gc.collect()
                
                jti = entity_info.get('jti')
                sub = entity_info.get('sub')
                
                if not jti or not sub:
                    if self.debug:
                        print("❌ Invalid entity info from API - missing jti or sub")
                    return False
                
                if not isinstance(jti, str) or not isinstance(sub, str):
                    if self.debug:
                        print("❌ Invalid entity info from API - jti or sub not strings")
                    return False
                
                if len(jti.strip()) == 0 or len(sub.strip()) == 0:
                    if self.debug:
                        print("❌ Invalid entity info from API - empty jti or sub")
                    return False

                try:
                    update_entity_cache(
                        api_key_id=jti,
                        subject=sub,
                        api_key_hash=api_key_hash
                    )
                    if self.debug:
                        print("✅ Entity info cached successfully")
                except Exception as cache_err:
                    if self.debug:
                        print(f"⚠️ Error updating entity cache (non-critical): {cache_err}")

                self.entity_info = {
                    'jti': jti,
                    'sub': sub
                }
                return True
            else:
                status_code = response.status_code
                if self.debug:
                    print(f"❌ Failed to fetch entity info: {status_code}")
                try:
                    response.close()
                except Exception:
                    pass
                response = None
                gc.collect()
                return False
        except Exception as e:
            if self.debug:
                print(f"❌ Entity info fetch error: {e}")
            if response:
                try:
                    response.close()
                except Exception:
                    pass
                gc.collect()
            return False



    def _build_publish_topic(self):
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

        return f"{account}/{region}/{jti}/publish"

    def _build_messages_topic(self):
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

        return f"{account}/{region}/{jti}/messages"

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
            return False

        if not self.entity_info.get('jti'):
            if self.debug:
                print("❌ API key ID not found in API claims. Check your API key.")
            return False

        if not self.entity_info.get('sub'):
            if self.debug:
                print("❌ Subject not found in API claims.")
            return False

        mqtt_host = self.config.get("mqtt_host")
        mqtt_port = self.config.get("mqtt_port")
        mqtt_ssl = self.config.get("mqtt_ssl")

        if not mqtt_host or mqtt_host.strip() == "":
            if self.debug:
                print("❌ MQTT host is empty or not configured")
            return False

        api_key = self.config.get("api_key")
        if not api_key:
            if self.debug:
                print("❌ Missing API key in configuration")
            return False

        client_id = self.entity_info['sub']
        username = self.entity_info['jti']
        password = api_key

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
                    self._mqtt = MQTTClient(
                        client_id=client_id,
                        server=mqtt_host,
                        port=mqtt_port,
                        user=username,
                        password=password,
                        keepalive=300,
                        ssl=mqtt_ssl,
                        ssl_params={"server_hostname": mqtt_host}
                    )

                    self._mqtt.set_callback(self._on_message)

                    gc.collect()
                    self._mqtt.connect()
                    gc.collect()

                    self.connected = True
                    self._consecutive_errors = 0

                    try:
                        self._subscribe_to_topics()
                    except Exception as sub_err:
                        if self.debug:
                            print(f"⚠️ Subscription warning (non-critical): {sub_err}")

                    return True

                except MQTTException as mqtt_err:
                    if self.debug:
                        print(f"❌ MQTT connection error (Attempt {attempt + 1}): {mqtt_err}")
                        print(f"   Host: {mqtt_host}, Port: {mqtt_port}, SSL: {mqtt_ssl}")
                    self.connected = False
                    time.sleep(2**attempt)
                    continue
                except Exception as e:
                    if self.debug:
                        print(f"❌ Unexpected MQTT connection error (Attempt {attempt + 1}): {e}")
                        print(f"   Error type: {type(e).__name__}")
                        print(f"   Host: {mqtt_host}, Port: {mqtt_port}, SSL: {mqtt_ssl}")
                    self.connected = False
                    time.sleep(2**attempt)
                    continue

            self._mqtt = None
            self.connected = False
            if self.debug:
                print("❌ All MQTT connection attempts failed")
            return False

        except Exception as overall_err:
            if self.debug:
                print(f"❌ Critical MQTT connection failure: {overall_err}")
            self._mqtt = None
            self.connected = False
            return False

    def _subscribe_to_topics(self):
        if not self._mqtt or not self.connected:
            if self.debug:
                print("❌ Cannot subscribe - MQTT not connected")
            return

        try:
            messages_topic = self._build_messages_topic()
            self._mqtt.subscribe(messages_topic, qos=1)

        except Exception as e:
            if self.debug:
                print(f"❌ Error subscribing to topics: {e}")

    def _on_message(self, topic, msg):
        try:
            msg_str = msg.decode('utf-8')

            try:
                message_data = json.loads(msg_str)
            except json.JSONDecodeError:
                if self.debug:
                    print(f"❌ Invalid JSON in message: {msg_str}")
                return

            if self.callback and callable(self.callback):
                try:
                    self.callback(message_data)
                except Exception as e:
                    if self.debug:
                        print(f"❌ Callback error: {e}")

        except Exception as e:
            if self.debug:
                print(f"❌ Error handling MQTT message: {e}")

    def _try_reconnect(self):
        self.connected = False
        try:
            if self._mqtt:
                self._mqtt.disconnect()
        except Exception as close_err:
            if self.debug:
                print(f"Error disconnecting existing client: {close_err}")

        time.sleep(self._reconnect_delay)

        return self.connect()

    def publish_message(self, data):
        if not self.connected or self._mqtt is None:
            if self.debug:
                print("❌ Not connected to MQTT broker")
            return False, True

        try:
            p = json.dumps(data)
            topic = self._build_publish_topic()

            self._mqtt.publish(topic, p)
            return True, False
        except Exception as e:
            if self.debug:
                print(f"❌ Error in publish_message: {e}")
            return False, True

    def _chunk_messages(self, messages):
        chunks = []
        current_chunk = []
        current_size = 0

        for msg in messages:
            msg_str = json.dumps(msg) if isinstance(msg, dict) else str(msg)
            msg_size = len(msg_str.encode('utf-8'))

            if (current_size + msg_size > self._max_batch_size or
                len(current_chunk) >= self._max_messages_per_batch):
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [msg]
                current_size = msg_size
            else:
                current_chunk.append(msg)
                current_size += msg_size

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def send_batch(self, messages):
        if not self.connected or not self._mqtt:
            if self.debug:
                print("❌ MQTT not connected - cannot send batch")
            return False

        if not messages:
            if self.debug:
                print("No messages to send in batch")
            return True

        chunks = self._chunk_messages(messages)

        success_count = 0
        connection_error_count = 0
        total_messages = len(messages)

        for chunk_idx, chunk in enumerate(chunks):
            try:
                for msg in chunk:
                    success, is_connection_error = self.publish_message(msg)
                    if success:
                        success_count += 1
                    elif is_connection_error:
                        connection_error_count += 1
                        if self.debug:
                            print(f"❌ Connection error sending message in batch: {msg}")
                    else:
                        if self.debug:
                            print(f"❌ Validation error sending message in batch: {msg}")

            except Exception as e:
                if self.debug:
                    print(f"❌ Error sending batch chunk {chunk_idx}: {e}")
                connection_error_count += 1

        if self.debug:
            if success_count == total_messages:
                print(f"✅ Batch send complete: {success_count}/{total_messages} messages sent successfully")
            elif connection_error_count > 0:
                print(f"❌ Batch send failed: {connection_error_count} connection errors")
            else:
                print(f"⚠️ Batch send partial: {success_count}/{total_messages} messages sent")

        return connection_error_count == 0

    def check_messages(self):
        if not self.connected or not self._mqtt:
            if self.debug:
                print("❌ MQTT not connected - cannot check messages")
            return False

        try:
            m = self._mqtt.check_msg()
            return m
        except Exception as e:
            if self.debug:
                print(f"❌ Error checking messages: {e}")
            return False

    def cleanup(self):
        try:
            if self._mqtt:
                self._mqtt.disconnect()
                self._mqtt = None
            self.connected = False
        except Exception as e:
            if self.debug:
                print(f"❌ Error during MQTT cleanup: {e}")
