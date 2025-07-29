import json
import time
import _thread
import urequests
import gc
import os
import ssl
from umqtt.simple import MQTTClient, MQTTException
from .config_manager import update_config, clear_entity_cache


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
        self._client_id = None
        self._jti = None
        self._e_type = None
        self.entity_info = None
        self.callback = callback

    def _fetch_entity_info(self):
        try:
            api_key = self.config.get("api_key")
            if not api_key:
                if self.debug:
                    print("❌ Missing API key in configuration")
                return False
            
            cached_api_key_id = self.config.get("api_key_id")
            cached_subject = self.config.get("subject")
            
            if cached_api_key_id and cached_subject:
                if self.debug:
                    print("📋 Using cached entity info")
                self.entity_info = {
                    'jti': cached_api_key_id,
                    'sub': cached_subject
                }
                return True
            
            if self.debug:
                print("🌐 Fetching entity info from API...")
            
            app_url = self.config.get("app_url", "https://app.tendrl.com")
            if app_url:
                api_base_url = app_url
            else:
                mqtt_host = self.config.get("mqtt_host", "mqtt.tendrl.com")
                if mqtt_host == 'localhost':
                    api_base_url = 'http://localhost:8081'
                else:
                    api_base_url = f'https://{mqtt_host.replace("mqtt-", "app-")}'
            
            if self.debug:
                print(f"API Base URL: {api_base_url}")
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            url = f'{api_base_url}/api/claims'
            if self.debug:
                print(f"Fetching entity info from: {url}")
            
            response = urequests.get(url, headers=headers)
            
            if self.debug:
                print(f"API Response Status: {response.status_code}")
                print(f"API Response: {response.text}")
            
            if response.status_code == 200:
                self.entity_info = response.json()
                if self.debug:
                    print(f"Entity info loaded: {self.entity_info}")
                
                jti = self.entity_info.get('jti')
                sub = self.entity_info.get('sub')
                if jti and sub:
                    if self.debug:
                        print("💾 Caching entity info")
                    update_config(api_key_id=jti, subject=sub)
                
                response.close()
                return True
            else:
                if self.debug:
                    print(f"Failed to get entity info: {response.status_code}")
                    print(f"Response: {response.text}")
                
                if response.status_code in [401, 403]:
                    if self.debug:
                        print("🔒 Clearing cached entity info due to authentication failure")
                    clear_entity_cache()
                
                response.close()
                return False
                
        except Exception as e:
            if self.debug:
                print(f"Error fetching entity info: {e}")
            return False

    def _create_tls_context(self):
        mqtt_ssl = self.config.get("mqtt_ssl", False)
        if not mqtt_ssl:
            return None
            
        try:
            ssl_context = ssl.create_default_context()
            
            mqtt_host = self.config.get("mqtt_host", "mqtt.tendrl.com")
            if mqtt_host == 'localhost':
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                if self.debug:
                    print("TLS: Using development mode (self-signed certs allowed)")
            else:
                if self.debug:
                    print("TLS: Using production mode (strict certificate validation)")
            
            return ssl_context
        except Exception as e:
            if self.debug:
                print(f"Error creating TLS context: {e}")
            return None

    def _build_topic(self, action):
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
        
        return f"{account}/{region}/{jti}/{action}"

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
                return {"value": parsed}
            except (ValueError, TypeError):
                return {"message": data}
        
        if isinstance(data, (int, float, bool, list)):
            return {"value": data}
        
        return {"value": str(data)}

    def connect(self, jti=None):
        self.connected = False
        self._consecutive_errors = 0
        
        if not self._fetch_entity_info():
            if self.debug:
                print("❌ Failed to fetch entity information")
            return False
        
        if not self.entity_info.get('jti'):
            if self.debug:
                print("❌ JTI not found in API claims. Check your API key.")
            return False
        
        if not self.entity_info.get('sub'):
            if self.debug:
                print("❌ Resource path not found in API claims.")
            return False
        
        mqtt_host = self.config.get("mqtt_host", "mqtt.tendrl.com")
        mqtt_port = self.config.get("mqtt_port", 1883)
        mqtt_ssl = self.config.get("mqtt_ssl", False)
        
        if self.debug:
            print(f"🔧 MQTT config: {mqtt_host}:{mqtt_port} (SSL: {mqtt_ssl})")
        
        api_key = self.config.get("api_key")
        if not api_key:
            if self.debug:
                print("❌ Missing API key in configuration")
            return False
        
        client_id = self.entity_info['sub']
        username = self.entity_info['jti']
        password = api_key
        
        if self.debug:
            print(f"Connecting to MQTT broker: {mqtt_host}:{mqtt_port}")
            print(f"Client ID: {client_id}")
            print(f"Username: {username}")
            print(f"TLS: {mqtt_ssl}")
        
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
                    
                    ssl_context = self._create_tls_context() if mqtt_ssl else None
                    
                    self._mqtt = MQTTClient(
                        client_id=client_id,
                        server=mqtt_host,
                        port=mqtt_port,
                        user=username,
                        password=password,
                        keepalive=60,
                        ssl=ssl_context
                    )
                    
                    self._mqtt.set_callback(self._on_message)
                    
                    if self.debug:
                        print("Attempting to connect...")
                    self._mqtt.connect()
                    
                    try:
                        self._subscribe_to_topics()
                    except Exception as sub_err:
                        if self.debug:
                            print(f"⚠️ Subscription warning (non-critical): {sub_err}")
                    
                    self.connected = True
                    self._consecutive_errors = 0
                    self._jti = username
                    self._client_id = client_id
                    
                    if self.debug:
                        print(f"✅ MQTT connected successfully to {mqtt_host}")
                    return True
                    
                except MQTTException as mqtt_err:
                    if self.debug:
                        print(f"❌ MQTT connection error (Attempt {attempt + 1}): {mqtt_err}")
                    self.connected = False
                    time.sleep(2**attempt)
                    continue
                except Exception as e:
                    if self.debug:
                        print(f"❌ Unexpected MQTT connection error (Attempt {attempt + 1}): {e}")
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
        
        if self.debug:
            print("📡 No subscriptions needed - backend handles routing")

    def _on_message(self, topic, msg):
        try:
            topic_str = topic.decode('utf-8')
            msg_str = msg.decode('utf-8')
            
            if self.debug:
                print(f"📨 Received message on topic {topic_str}: {msg_str}")
            
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
                if self.debug:
                    print("Disconnecting existing MQTT client")
                self._mqtt.disconnect()
        except Exception as close_err:
            if self.debug:
                print(f"Error disconnecting existing client: {close_err}")
        
        time.sleep(self._reconnect_delay)
        
        return self.connect()

    def publish_message(self, data, msg_type="publish", destination=None, tags=None):
        if not self.connected or self._mqtt is None:
            if self.debug:
                print("❌ Not connected to MQTT broker")
            return False, True
        
        try:
            if not msg_type or not isinstance(msg_type, str):
                raise Exception('msg_type must be a non-empty string')
            
            if destination and not isinstance(destination, str):
                raise Exception('destination must be a string or None')
            
            if tags and not isinstance(tags, list):
                raise Exception('tags must be a list or None')
            
            topic = self._build_topic(msg_type)
            
            validated_data = self._validate_and_prepare_data(data)
            
            message = {
                "msg_type": msg_type,
                "data": validated_data,
                "timestamp": time.time()
            }
            
            if destination:
                message["destination"] = destination
            
            if tags:
                message["context"] = {"tags": tags}
            
            payload = json.dumps(message)
            
            if self.debug:
                print(f"Publishing to topic: {topic}")
            self._mqtt.publish(topic, payload, qos=1)
            
            if self.debug:
                print(f"✅ Message published to topic: {topic}")
                print(f"📤 Message: {payload}")
            return True, False
            
        except Exception as e:
            if self.debug:
                print(f"❌ Error publishing message: {e}")
            
            is_connection_error = (
                not self.connected or 
                self._mqtt is None or
                isinstance(e, MQTTException) or
                "connection" in str(e).lower() or
                "network" in str(e).lower() or
                "timeout" in str(e).lower()
            )
            
            return False, is_connection_error

    def send_message(self, msg, max_retries=1):
        if not self.connected or not self._mqtt:
            if self.debug:
                print("❌ MQTT not connected - cannot send message")
            return False
        
        with self._mqtt_lock:
            try:
                success, is_connection_error = self.publish_message(msg, "publish")
                
                if not success and is_connection_error:
                    self._consecutive_errors += 1
                    if self._consecutive_errors >= 3:
                        if self.debug:
                            print(f"⚠️ Consecutive connection errors ({self._consecutive_errors}) - attempting reconnect")
                        self._try_reconnect()
                
                return success
                
            except MQTTException as mqtt_err:
                if self.debug:
                    print(f"❌ MQTT send error: {mqtt_err}")
                self._consecutive_errors += 1
                if self._consecutive_errors >= 3:
                    if self.debug:
                        print(f"⚠️ Consecutive errors ({self._consecutive_errors}) - attempting reconnect")
                    self._try_reconnect()
                return False
            except Exception as e:
                if self.debug:
                    print(f"❌ Unexpected send error: {e}")
                return False

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
        
        if self.debug:
            print(f"📦 Sending batch of {total_messages} messages in {len(chunks)} chunks")
        
        for chunk_idx, chunk in enumerate(chunks):
            try:
                for msg in chunk:
                    success, is_connection_error = self.publish_message(msg, "publish")
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
            self._mqtt.check_msg()
            return True
        except Exception as e:
            if self.debug:
                print(f"❌ Error checking messages: {e}")
            return False

    def cleanup(self):
        try:
            if self._mqtt:
                if self.debug:
                    print("🔌 Disconnecting MQTT client")
                self._mqtt.disconnect()
                self._mqtt = None
            self.connected = False
            if self.debug:
                print("✅ MQTT cleanup completed")
        except Exception as e:
            if self.debug:
                print(f"❌ Error during MQTT cleanup: {e}")

    def send_simple_message(self, message, destination=None, tags=None):
        return self.publish_message(message, "publish", destination, tags)

    def publish_sensor_data(self, sensor_data, tags=None):
        if not isinstance(sensor_data, dict):
            raise Exception('sensor_data must be a dict')
        
        if tags is None:
            tags = ["sensor"]
        
        return self.publish_message(
            data=sensor_data,
            msg_type="publish",
            tags=tags
        )
    
    def publish_cross_account_message(self, data, destination, msg_type="publish", tags=None):
        return self.publish_message(data, msg_type, destination, tags)
    
    def send_file_system_command_response(self, output="", error="", exit_code=0, request_id=None):
        response_data = {
            "output": output,
            "error": error,
            "exitCode": exit_code
        }
        if request_id:
            response_data["request_id"] = request_id
        return self.publish_message(response_data, 'fs_cmd_resp')
    
    def send_terminal_command_response(self, output="", error="", exit_code=0, request_id=None):
        response_data = {
            "output": output,
            "error": error,
            "exitCode": exit_code
        }
        if request_id:
            response_data["request_id"] = request_id
        return self.publish_message(response_data, 'terminal_cmd_resp')
    
    def send_client_command_response(self, data, request_id=None):
        if request_id:
            data["request_id"] = request_id
        return self.publish_message(data, 'client_cmd_resp')
    
    def send_file_transfer(self, file_data, destination=None):
        return self.publish_message(file_data, 'file', destination) 