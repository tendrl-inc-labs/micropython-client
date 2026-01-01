import json
import sys
import time
import gc


try:
    import machine
    import micropython
    micropython.alloc_emergency_exception_buf(100)
    MACHINE_AVAILABLE = True
except ImportError:
    MACHINE_AVAILABLE = False
try:
    import asyncio
    ASYNCIO_AVAILABLE = True
except ImportError:
    ASYNCIO_AVAILABLE = False
try:
    import btree
    BTREE_AVAILABLE = True
except ImportError:
    BTREE_AVAILABLE = False

from .network_manager import NetworkManager
from .mqtt_handler import MQTTHandler
from .queue_manager import QueueManager, QueueFull
from .utils.util_helpers import (
    safe_storage_operation,
    retrieve_offline_messages,
    send_offline_messages,
    make_message,
    free
)
from .config_manager import read_config

class DBError(Exception):
    pass

class Client:
    def __init__(self,mode="sync",debug=False,timer=0,freq=3,callback=None,
        check_msg_rate=5,max_batch_size=15,db_page_size=1024,watchdog=0,
        send_heartbeat=True, client_db=True, client_db_in_memory=True,
        offline_storage=True, managed=True, event_loop=None):
        if mode not in ["sync", "async"]:
            raise ValueError("Mode must be either 'sync' or 'async'")
        if mode == "async" and not ASYNCIO_AVAILABLE:
            raise ImportError("Asyncio module is required for async mode")
        if mode == "sync" and not MACHINE_AVAILABLE:
            raise ImportError("Machine module is required for sync mode")
        if not BTREE_AVAILABLE:
            if client_db or offline_storage:
                if debug:
                    print("MicroTetherDB not available - disabling database features")
                    print("   Install full package for database support")
            client_db = False
            offline_storage = False
        self.mode = mode
        self.managed = managed
        self._user_event_loop = event_loop
        self.config = read_config()
        if not self.config.get("tendrl_version"):
            self.config["tendrl_version"] = "0.1.0"
        if not self.config.get("app_url"):
            self.config["app_url"] = "https://app.tendrl.com"
        self.network = (
            NetworkManager(self.config, debug, headless=not managed)
            if not managed
            else NetworkManager(self.config, debug)
        )
        # Always attempt to initialize MQTT (required for messaging and streaming online status)
        # If initialization fails, continue gracefully without MQTT
        try:
            self.mqtt = MQTTHandler(self.config, debug, callback)
        except (ImportError, Exception) as e:
            if debug:
                print(f"Warning: MQTT handler initialization failed: {e}")
                print("  Continuing without MQTT - messaging and streaming online status will be unavailable")
            self.mqtt = None
        self.queue = QueueManager(
            max_batch=max_batch_size,
            debug=debug,
        ) if managed else None
        self._offline_queue = QueueManager(
            max_batch=max_batch_size,
            debug=debug,
        ) if managed else None
        self.debug = debug
        self.check_msg_rate = check_msg_rate
        self.callback = callback
        self.client_enabled = False
        self.send_heartbeat = send_heartbeat and managed
        self._timer_id = timer
        self._timer_freq = freq
        self._db = None
        self._client_db = None
        self._last_msg_check = 0
        self._last_heartbeat = 0
        self._last_process_time = 0
        self._last_connect = 0
        self._last_cleanup = 0
        # Use ticks_ms for relative timing (more performant than time.time())
        self._last_heartbeat_ticks = 0
        self._last_msg_check_ticks = 0
        self._last_connect_ticks = 0
        self._last_cleanup_ticks = 0
        self._proc = False
        self._ntp_synced = False
        # Build client version string in format: tendrl-micropython/{version}
        # Store in both instance variable and config for access by handlers
        client_version = f"tendrl-micropython/{self.config['tendrl_version']}"
        self._e_type = client_version
        self.config['client_version'] = client_version  # Make available to handlers
        if callback and not callable(callback):
            raise TypeError("callback must be a function accepting dict")
        self._app_timer = None
        self._wdt = watchdog
        if mode == "async":
            if self._user_event_loop:
                asyncio.set_event_loop(self._user_event_loop)
                if debug:
                    print("Using user-provided event loop for client")
            self._stop_event = asyncio.Event()
            self._tasks = []
            self._streaming_task = None  # Store reference to streaming task for stop control
        if BTREE_AVAILABLE and managed:
            try:
                database_event_loop = None
                if mode == "async" and ASYNCIO_AVAILABLE:
                    if self._user_event_loop:
                        database_event_loop = self._user_event_loop
                        if debug:
                            print("Using user-provided event loop for databases")
                    else:
                        try:
                            database_event_loop = asyncio.get_running_loop()
                            if debug:
                                print("Using current running event loop for databases")
                        except RuntimeError:
                            if debug:
                                print("No running event loop found, databases will create one")
                if offline_storage:
                    try:
                        from tendrl.lib.microtetherdb.db import MicroTetherDB
                        from tendrl.config_manager import get_root_dir
                        root_dir = get_root_dir()
                        self._db = MicroTetherDB(
                            filename=f"{root_dir}/lib/tendrl/tether.db",
                            in_memory=False,
                            btree_pagesize=db_page_size,
                            event_loop=database_event_loop
                        )
                        if debug:
                            print("Offline storage database initialized")
                    except ImportError:
                        self._db = None
                        if debug:
                            print("MicroTetherDB not available - offline storage disabled")
                else:
                    self._db = None
                    if debug:
                        print("Offline storage disabled - no message queuing")
                if client_db:
                    try:
                        from tendrl.lib.microtetherdb.db import MicroTetherDB
                        from tendrl.config_manager import get_root_dir
                        root_dir = get_root_dir()
                        self._client_db = MicroTetherDB(
                            filename=f"{root_dir}/lib/tendrl/client_db.db",
                            in_memory=client_db_in_memory,
                            btree_pagesize=1024,
                            ram_percentage=10,
                            event_loop=database_event_loop
                        )
                        storage_type = "in-memory" if client_db_in_memory else "file-based"
                        if debug:
                            print(f"Client database initialized ({storage_type})")
                    except ImportError:
                        self._client_db = None
                        if debug:
                            print("MicroTetherDB not available - client database disabled")
                else:
                    self._client_db = None
                    if debug:
                        print("Client database disabled - no local data storage")
            except Exception as e:
                print(f"Storage initialization error: {e}")
                self._db = None
                self._client_db = None
        elif not managed:
            if debug:
                print("Unmanaged mode - databases disabled")
            self._db = None
            self._client_db = None
        else:
            if debug:
                print("MicroTetherDB not available - databases disabled")
                print("   Use minimal installation or install full package")
            self._db = None
            self._client_db = None

    @property
    def storage(self):
        return self._db

    @property
    def client_db(self):
        return self._client_db

    def _process_message(self, msg):
        print(msg)
        if not msg:
            return
        self._proc = True
        try:
            if isinstance(msg, str):
                try:
                    content = json.loads(msg)
                except Exception:
                    if self.debug:
                        print(f"Failed to parse message: {msg}")
                    return
            elif isinstance(msg, dict):
                content = msg
            elif isinstance(msg, bytes):
                try:
                    content = json.loads(msg.decode("utf-8"))
                except Exception:
                    if self.debug:
                        print(f"Failed to decode/parse bytes message: {msg}")
            else:
                raise ValueError("Unsupported message type")
            message = content.get("message") if isinstance(content, dict) else content
            if self.callback and callable(self.callback):
                try:
                    self.callback(message)
                except Exception as callback_err:
                    if self.debug:
                        print(f"Callback processing error: {callback_err}")
        finally:
            self._proc = False

    def _connect(self):
        try:
            if self.network.connect():
                gc.collect()
                # NTP sync happens in network.connect(), so mark as synced
                if not self._ntp_synced:
                    self._ntp_synced = True
                    self._update_queued_timestamps()

                # Only connect MQTT if it's enabled
                if self.mqtt:
                    if self.mqtt.connect():
                        self.client_enabled = True
                        if self.debug:
                            print("Connected to Tendrl Server")
                        return True
                    self.client_enabled, self.mqtt.connected = False, False
                else:
                    # MQTT disabled - network connection is sufficient for streaming
                    self.client_enabled = True
                    if self.debug:
                        print("Network connected (MQTT disabled)")
                    return True
            if self.mqtt:
                self.client_enabled, self.mqtt.connected = False, False
            else:
                self.client_enabled = False
            return False
        except Exception as e:
            self.client_enabled = False
            if self.debug:
                print(f"Connection error: {e}")
            return False
        finally:
            # Update both ticks (for relative timing) and time (for absolute timestamps if needed)
            self._last_connect_ticks = time.ticks_ms()
            self._last_connect = time.time()

    def _store_offline_message(self, message, db_ttl=86400):
        try:
            if not isinstance(message, dict):
                message = {"data": message}
            message["_offline_ttl"] = message.get("_offline_ttl", db_ttl)
            result = self._offline_queue.put(message)
            if not self.client_enabled or not self.storage:
                return result
            try:
                put_result = safe_storage_operation(
                    self.storage,
                    "put",
                    message,
                    ttl=message.get("_offline_ttl", db_ttl),
                )
                return put_result
            except Exception as db_err:
                if self.debug:
                    print(f"Offline message storage error: {db_err}")
                return False
        except Exception as e:
            if self.debug:
                print(f"Unexpected error in offline message storage: {e}")
            return False

    async def _cleanup_offline_messages(self):
        if not self.storage:
            return
        # Use ticks_ms for relative timing check (more performant)
        current_ticks = time.ticks_ms()
        if self._last_cleanup_ticks == 0 or time.ticks_diff(current_ticks, self._last_cleanup_ticks) >= 60000:
            try:
                self._last_cleanup_ticks = current_ticks
                # Still use time.time() for absolute timestamp if needed
                self._last_cleanup = time.time()
                async with self.storage as store:
                    cleanup_result = store.cleanup()
                    if self.debug and cleanup_result > 0:
                        print(
                            f"Cleaned up {cleanup_result} expired offline messages"
                        )
                if self.client_db:
                    async with self.client_db as store:
                        cleanup_result = store.cleanup()
                        if self.debug and cleanup_result > 0:
                            print(
                                f"Cleaned up {cleanup_result} expired offline messages"
                            )
            except Exception as e:
                if self.debug:
                    print(f"Offline message cleanup error: {e}")

    def _timer_callback(self, timer):
        if self._proc:
            return
        self._proc = True
        did_work = False
        try:
            # Use ticks_ms for relative timing checks (more performant)
            current_ticks = time.ticks_ms()

            # Heartbeat check (30 seconds = 30000ms)
            if self.send_heartbeat:
                if self._last_heartbeat_ticks == 0 or time.ticks_diff(current_ticks, self._last_heartbeat_ticks) >= 30000:
                    try:
                        self._last_heartbeat_ticks = current_ticks
                        # Still use time.time() for absolute timestamp in message
                        self._last_heartbeat = time.time()
                        msg = make_message(free(bytes_only=True), "heartbeat")
                        success, is_connection_error = self.mqtt.publish_message(msg)
                        if not success and is_connection_error:
                            if self.debug:
                                print("Heartbeat connection error - disabling client")
                            self.client_enabled, self.mqtt.connected = False, False
                        elif not success:
                            if self.debug:
                                print("Heartbeat validation error - client remains enabled")
                        did_work = True
                    except Exception:
                        self.client_enabled, self.mqtt.connected = False, False
                        return

            if not self.client_enabled:
                # Connection retry check (30 seconds = 30000ms)
                if self._last_connect_ticks == 0 or time.ticks_diff(current_ticks, self._last_connect_ticks) >= 30000:
                    if self._connect():
                        did_work = True
                        self._last_connect_ticks = current_ticks
                    else:
                        self.client_enabled = False
                else:
                    self._process_offline_queue()
                return

            try:
                batch = self.queue.process_batch()
                if batch:
                    try:
                        success = self.mqtt.send_batch(batch)
                        if not success:
                            self.client_enabled = False
                            if self.debug:
                                print("Batch send failed")
                        else:
                            did_work = True
                            if self.debug:
                                print(f"Batch sent successfully: {len(batch)} messages")
                    except Exception as batch_err:
                        if self.debug:
                            print(f"Error sending batch: {batch_err}")
                        for msg in batch:
                            self._store_offline_message(msg)
                        self.client_enabled = False
                        return
            except Exception as queue_err:
                if self.debug:
                    print(f"Queue processing error: {queue_err}")
                return

            # Message check (check_msg_rate seconds, convert to ms)
            check_msg_rate_ms = self.check_msg_rate * 1000
            if self._last_msg_check_ticks == 0 or time.ticks_diff(current_ticks, self._last_msg_check_ticks) >= check_msg_rate_ms:
                try:
                    self._last_msg_check_ticks = current_ticks
                    # Still use time.time() for absolute timestamp if needed
                    self._last_msg_check = time.time()
                    # check_messages() processes messages via callback, returns True on success
                    success = self.mqtt.check_messages()
                    if success:
                        did_work = True
                    else:
                        # If check failed, mark as disconnected
                        self.client_enabled, self.mqtt.connected = False, False
                except Exception as check_msg_err:
                    if self.debug:
                        print(f"Check messages error: {check_msg_err}")
                    self.client_enabled, self.mqtt.connected = False, False

            # Cleanup check (60 seconds = 60000ms)
            if self._last_cleanup_ticks == 0 or time.ticks_diff(current_ticks, self._last_cleanup_ticks) >= 60000:
                if self.storage or self._client_db:
                    self._sync_cleanup_offline_messages()
                self._last_cleanup_ticks = current_ticks
                # Still use time.time() for absolute timestamp if needed
                self._last_cleanup = time.time()
                did_work = True

            if self._process_offline_queue() > 0:
                did_work = True

        except KeyboardInterrupt:
            if self.debug:
                print("Keyboard interrupt received, stopping client")
            self.stop()
        except Exception as overall_err:
            if self.debug:
                print(f"Unexpected error in timer callback: {overall_err}")
            self._process_offline_queue()
        finally:
            if did_work:
                gc.collect()
            self._proc = False

    def _update_queued_timestamps(self):
        """Update timestamps for all queued messages after NTP sync"""
        import time
        from .utils.util_helpers import iso8601

        if not self.managed:
            return

        updated_count = 0
        current_timestamp = iso8601(time.gmtime())

        # Update timestamps in main queue
        if self.queue and len(self.queue) > 0:
            # Extract all messages, update timestamps, and re-queue
            queue_size = len(self.queue)
            temp_messages = []

            # Extract all messages from queue using get()
            for _ in range(queue_size):
                msg = self.queue.queue.get()
                if msg is None:
                    break
                if isinstance(msg, dict) and "timestamp" in msg:
                    # Update timestamp
                    msg["timestamp"] = current_timestamp
                    updated_count += 1
                temp_messages.append(msg)

            # Re-queue messages with updated timestamps
            for msg in temp_messages:
                try:
                    self.queue.put(msg)
                except Exception:
                    if self.debug:
                        print("Warning: Could not re-queue message after timestamp update")

        # Update timestamps in offline queue
        if self._offline_queue and len(self._offline_queue) > 0:
            queue_size = len(self._offline_queue)
            temp_messages = []

            # Extract all messages from offline queue using get()
            for _ in range(queue_size):
                msg = self._offline_queue.queue.get()
                if msg is None:
                    break
                if isinstance(msg, dict) and "timestamp" in msg:
                    # Update timestamp
                    msg["timestamp"] = current_timestamp
                    updated_count += 1
                temp_messages.append(msg)

            # Re-queue messages with updated timestamps
            for msg in temp_messages:
                try:
                    self._offline_queue.put(msg)
                except Exception:
                    if self.debug:
                        print("Warning: Could not re-queue offline message after timestamp update")

        if self.debug and updated_count > 0:
            print(f"Updated timestamps for {updated_count} queued messages after NTP sync")

    def _sync_cleanup_offline_messages(self):
        result = None
        if self.storage:
            result = safe_storage_operation(self.storage, "cleanup")
        if self._client_db:
            safe_storage_operation(self._client_db, "cleanup")
        return result

    async def _process_queue(self):
        if self.client_enabled:
            try:
                if len(self.queue.queue):
                    batch = self.queue.process_batch()
                    if batch:
                        success = self.mqtt.send_batch(batch)
                        if not success:
                            self.client_enabled, self.mqtt.connected = False, False
            except Exception as e:
                if self.debug:
                    print(f"Queue processing error: {e}")
                self.client_enabled, self.mqtt.connected = False, False

    async def _send_heartbeat(self):
        # Use ticks_ms for relative timing check (more performant)
        current_ticks = time.ticks_ms()
        if self._last_heartbeat_ticks == 0 or time.ticks_diff(current_ticks, self._last_heartbeat_ticks) >= 30000:
            try:
                self._last_heartbeat_ticks = current_ticks
                # Still use time.time() for absolute timestamp in message
                self._last_heartbeat = time.time()
                msg = make_message(free(bytes_only=True), "heartbeat")
                success, is_connection_error = self.mqtt.publish_message(msg)

                if not success and is_connection_error:
                    if self.debug:
                        print("Heartbeat connection error - disabling client")
                    self.client_enabled, self.mqtt.connected = False, False
                elif not success:
                    if self.debug:
                        print("Heartbeat validation error - client remains enabled")
            except Exception as e:
                if self.debug:
                    print(f"Heartbeat error: {e}")
                self.client_enabled, self.mqtt.connected = False, False

    async def _check_messages(self):
        # Use ticks_ms for relative timing check (more performant)
        current_ticks = time.ticks_ms()
        check_msg_rate_ms = self.check_msg_rate * 1000
        if self._last_msg_check_ticks == 0 or time.ticks_diff(current_ticks, self._last_msg_check_ticks) >= check_msg_rate_ms:
            try:
                self._last_msg_check_ticks = current_ticks
                # Still use time.time() for absolute timestamp if needed
                self._last_msg_check = time.time()
                # check_messages() processes messages via callback, returns True on success
                success = self.mqtt.check_messages()
                if not success:
                    # If check failed, mark as disconnected
                    self.client_enabled, self.mqtt.connected = False, False
            except Exception as e:
                if self.debug:
                    print(f"Message check error: {e}")
                self.client_enabled, self.mqtt.connected = False, False

    async def _async_callback(self):
        while not self._stop_event.is_set():
            did_work = False
            try:
                if self._proc:
                    await asyncio.sleep(0.1)
                    continue
                self._proc = True
                # Use ticks_ms for relative timing checks (more performant)
                current_ticks = time.ticks_ms()

                if not self.client_enabled:
                    # Connection retry check (30 seconds = 30000ms)
                    if self._last_connect_ticks == 0 or time.ticks_diff(current_ticks, self._last_connect_ticks) >= 30000:
                        try:
                            if await self._async_connect():
                                if self.debug:
                                    print("Connection successfully established")
                                did_work = True
                                self._last_connect_ticks = current_ticks
                            else:
                                self.client_enabled = False
                        except Exception as connect_err:
                            if self.debug:
                                print(f"Unexpected connection error: {connect_err}")
                    self._process_offline_queue()
                    await asyncio.sleep(0.5)
                    continue

                await self._process_queue()
                did_work = True

                # Heartbeat check (30 seconds = 30000ms)
                if self.send_heartbeat:
                    if self._last_heartbeat_ticks == 0 or time.ticks_diff(current_ticks, self._last_heartbeat_ticks) >= 30000:
                        try:
                            await self._send_heartbeat()
                            did_work = True
                        except Exception:
                            self.client_enabled, self.mqtt.connected = False, False
                            return

                await self._check_messages()
                did_work = True

                if self.storage or self._client_db:
                    await self._cleanup_offline_messages()
                    did_work = True

                if self._process_offline_queue() > 0:
                    did_work = True

                if self._wdt and MACHINE_AVAILABLE:
                    try:
                        self._wdt.feed()
                    except Exception:
                        pass

                await asyncio.sleep(1.0 / self._timer_freq)

            except Exception as e:
                if self.debug:
                    print(f"Timer loop error: {e}")
                await asyncio.sleep(0.5)
            finally:
                if did_work:
                    gc.collect()
                self._proc = False

    def add_background_task(self, coro):
        if self.mode != "async" or not ASYNCIO_AVAILABLE:
            if self.debug:
                print("Background tasks only available in async mode")
            return None

        try:
            # Use the same pattern as start() - try user loop first, then asyncio.create_task
            if self._user_event_loop:
                task = self._user_event_loop.create_task(coro)
            else:
                # Use asyncio.create_task() directly (same as in start() method)
                task = asyncio.create_task(coro)
            self._tasks.append(task)
            return task
        except RuntimeError as e:
            if self.debug:
                print(f"Error creating background task: {e}")
            return None
        except Exception as e:
            if self.debug:
                print(f"Unexpected error creating background task: {e}")
            return None

    def tether(self, write_offline=False, db_ttl=None, tags=None, entity=""):
        def wrapper(func):
            is_async = type(func).__name__ == "generator"
            async def async_wrapped_function(*args, **kwargs):
                try:
                    if not self.client_enabled:
                        self._connect()
                    result = await func(*args, **kwargs)
                    message = make_message(
                        result,
                        "publish",
                        tags=tags,
                        entity=entity,
                    )
                    queue_result = self.queue.put(message)
                    if not queue_result or not self.client_enabled:
                        if write_offline:
                            self._store_offline_message(message, db_ttl)
                    return result
                except Exception as e:
                    if write_offline:
                        error_message = make_message(
                            {"error": str(e)},
                            "publish",
                            tags=tags,
                            entity=entity
                        )
                        self._store_offline_message(error_message, db_ttl)
                    raise

            def sync_wrapped_function(*args, **kwargs):
                try:
                    if not self.client_enabled:
                        self._connect()
                    result = func(*args, **kwargs)
                    message = make_message(
                        result,
                        "publish",
                        tags=tags,
                        entity=entity,
                    )
                    queue_result = self.queue.put(message)
                    if not queue_result or not self.client_enabled:
                        if write_offline:
                            self._store_offline_message(message, db_ttl)
                    return result
                except Exception as e:
                    if write_offline:
                        error_message = make_message(
                            {"error": str(e)},
                            "publish",
                            tags=tags,
                            entity=entity
                        )
                        self._store_offline_message(error_message, db_ttl)
                    raise
            return async_wrapped_function if is_async else sync_wrapped_function
        return wrapper

    def start_streaming(self, capture_frame_func=None, target_fps=15,
                       quality=50, framesize="QVGA", stream_duration=-1):

        try:
            from .streaming import start_jpeg_stream
        except ImportError:
            raise ImportError(
                "JPEG streaming requires the optional streaming module. "
                "Install with: mip.install(..., extra_args=['--streaming']) "
                "or manually install tendrl/streaming.py"
            )

        # Handle camera setup and default capture function
        if capture_frame_func is None:
            # Try to use default camera capture if sensor module is available
            try:
                import sensor

                # Validate and map framesize parameter
                # Default is QVGA, but allow None for backward compatibility
                if framesize is None or framesize.upper() == "QVGA":
                    framesize = sensor.QVGA
                    framesize_name = "QVGA"
                elif framesize.upper() == "QQVGA":
                    framesize = sensor.QQVGA
                    framesize_name = "QQVGA"
                elif framesize.upper() == "VGA":
                    framesize = sensor.VGA
                    framesize_name = "VGA"
                else:
                    raise ValueError(
                        f"Invalid framesize '{framesize}'. Must be 'QQVGA', 'QVGA', or 'VGA'"
                    )

                # Setup camera with optimized static settings
                if self.debug:
                    print(f"Setting up camera: {framesize_name}, JPEG, Quality={quality}")
                sensor.reset()
                sensor.set_pixformat(sensor.JPEG)
                sensor.set_framesize(framesize)
                sensor.set_quality(quality)
                sensor.skip_frames(time=1500)

                # Create default capture function
                def default_capture_frame():
                    img = sensor.snapshot()
                    return img.bytearray()

                capture_frame_func = default_capture_frame
                if self.debug:
                    print("Using default camera capture function")

            except ImportError:
                raise ImportError(
                    "Camera capture function required. Either provide capture_frame_func, "
                    "or ensure sensor module is available for default camera support."
                )

        # Streaming requires MQTT to show entity as online before streaming starts
        # If MQTT failed to initialize, warn but allow streaming to continue
        if self.mqtt is None:
            if self.debug:
                print("Warning: MQTT not available - streaming will continue but entity may not show as online")

        # Ensure client is started and MQTT is connected before streaming
        # This is required for online entity status that is set when MQTT connects
        if not self.client_enabled:
            if self.debug:
                print("Client not started - attempting to start and connect...")
            # Try to connect if not already connected
            if self.mode == "async":
                # In async mode, we need to ensure connection is established
                # Check if we need to wait for connection
                if not self.mqtt or not self.mqtt.connected:
                    if self.debug:
                        print("MQTT not connected - will wait for connection in stream loop")
            else:
                # In sync mode, try to connect now
                if not self._connect():
                    if self.debug:
                        print("Failed to connect - streaming will retry in stream loop")
        elif self.mqtt and not self.mqtt.connected:
            if self.debug:
                print("MQTT not connected - will wait for connection in stream loop")

        if self.debug:
            print(f"Starting streaming with FPS={target_fps}, quality={quality}")

        stream_loop_func = start_jpeg_stream(
            self,
            capture_frame_func,
            target_fps,
            stream_duration,
            self.debug
        )

        # Automatically add to background tasks if in async mode
        if self.mode == "async":
            # Call the coroutine function to get the actual coroutine/generator
            try:
                stream_coro = stream_loop_func()
                # In MicroPython, async functions might return generators instead of coroutines
                # asyncio.create_task() can handle both in MicroPython
                # Just try to create the task - it will work if it's awaitable
                task = self.add_background_task(stream_coro)
                # Store reference for stop control
                self._streaming_task = task
                return task
            except Exception as e:
                if self.debug:
                    print(f"Error calling stream_loop_func() or creating task: {e}")
                    try:
                        import sys
                        sys.print_exception(e)
                    except:
                        pass
                return None
        else:
            # In sync mode, we can't run async coroutines directly
            # User would need to handle this differently or use async mode
            if self.debug:
                print("Warning: Streaming requires async mode. Use Client(mode='async')")
            return None

    def stop_streaming(self):
        if self._streaming_task is None:
            if self.debug:
                print("No streaming task to stop")
            return False

        try:
            if hasattr(self._streaming_task, "done") and not self._streaming_task.done():
                self._streaming_task.cancel()
                if self.debug:
                    print("Streaming task cancelled")
            # Remove from tasks list if it's there
            if self._streaming_task in self._tasks:
                self._tasks.remove(self._streaming_task)
            self._streaming_task = None
            return True
        except Exception as e:
            if self.debug:
                print(f"Error stopping streaming: {e}")
            self._streaming_task = None
            return False

    def is_streaming(self):
        if self._streaming_task is None:
            return False
        if hasattr(self._streaming_task, "done"):
            return not self._streaming_task.done()
        return True

    def publish(
        self,
        data,
        tags=None,
        entity="",
        write_offline=False,
        db_ttl=0,
    ):
        self._proc = True
        try:
            if write_offline and not self.managed:
                if self.debug:
                    print("Warning: write_offline is not supported in unmanaged mode")
                write_offline = False

            if not self.client_enabled:
                if not self._connect():
                    if self.debug:
                        print("Failed to establish connection")
                    return None

            if not isinstance(data, dict):
                data = {"data": str(data)}

            if self.managed:
                # Use make_message to ensure consistent timestamp generation
                message = make_message(
                    data, "publish", tags=tags, entity=entity
                )

                if not self.queue.put(message):
                    if self.debug:
                        print("Failed to queue message - queue full")
                    if self.storage and write_offline:
                        self._store_offline_message(message, db_ttl)
            else:
                if not self.mqtt:
                    if self.debug:
                        print("MQTT is disabled - cannot publish messages")
                    return None
                success, is_connection_error = self.mqtt.publish_message(data)
                if not success:
                    if self.debug:
                        if is_connection_error:
                            print("Connection error - disabling client")
                        else:
                            print("Message validation error - client remains enabled")
                    if is_connection_error:
                        self.client_enabled = False
                return success
            return ""
        finally:
            self._proc = False

    def _scheduled_timer_callback(self, timer):
        micropython.schedule(self._timer_callback, timer)

    def start(self, watchdog=0):
        if self.debug:
            print(f"Starting Tendrl Client in {self.mode} mode...")
        self.client_enabled = False
        if self.mode == "sync":
            time.sleep(3)
            self._connect()
            if MACHINE_AVAILABLE and self._timer_id <= 3:
                self._app_timer = machine.Timer(self._timer_id)
                self._app_timer.init(
                    mode=machine.Timer.PERIODIC,
                    freq=self._timer_freq,
                    callback=self._scheduled_timer_callback,
                )
            if watchdog and MACHINE_AVAILABLE:
                self._wdt = machine.WDT(timeout=min(max(watchdog, 1), 60) * 1000)
        else:
            asyncio.sleep(3)
            self._connect()
            self._stop_event.clear()
            self._tasks = []
            try:
                if self._user_event_loop:
                    main_task = self._user_event_loop.create_task(self._async_callback())
                    if self.debug:
                        print("Created client task on user-provided event loop")
                else:
                    main_task = asyncio.create_task(self._async_callback())
                self._tasks.append(main_task)
                if watchdog and MACHINE_AVAILABLE:
                    try:
                        self._wdt = machine.WDT(
                            timeout=min(max(watchdog, 1), 60) * 1000
                        )
                    except Exception:
                        if self.debug:
                            print("Watchdog not supported")
            except (RuntimeError, AttributeError) as e:
                if self.debug:
                    print(f"Async event loop error: {e}")
                if self._user_event_loop:
                    print("Error: Unable to create task on user-provided event loop")
                    print("Make sure the event loop is running when calling client.start()")
                else:
                    print("To use async mode properly:")
                    print("1. Call client.start() inside an async function, OR")
                    print("2. Provide an event_loop parameter: Client(mode='async', event_loop=your_loop)")
                return

    async def async_stop(self):
        self.client_enabled = False
        if ASYNCIO_AVAILABLE:
            self._stop_event.set()
            for task in self._tasks:
                if hasattr(task, "done") and not task.done():
                    task.cancel()
            self._tasks = []
        try:
            self.mqtt.cleanup()
        except Exception as e:
            if self.debug:
                print(f"Error closing MQTT connection: {e}")
        try:
            self.network.cleanup()
        except Exception as e:
            if self.debug:
                print(f"Error cleaning up network: {e}")

    def stop(self):
        self.client_enabled = False
        if self.mode == "sync":
            try:
                if hasattr(self, "app_timer") and self._app_timer:
                    self._app_timer.deinit()
            except Exception as e:
                if self.debug:
                    print(f"Error stopping timer: {e}")
        else:
            if ASYNCIO_AVAILABLE:
                self._stop_event.set()
                for task in self._tasks:
                    if hasattr(task, "done") and not task.done():
                        task.cancel()
                self._tasks = []
        if self.mqtt:
            try:
                self.mqtt.cleanup()
            except Exception as e:
                if self.debug:
                    print(f"Error closing MQTT connection: {e}")
        try:
            self.network.cleanup()
        except Exception as e:
            if self.debug:
                print(f"Error cleaning up network: {e}")

    def _process_offline_queue(self):
        if not self.storage or len(self._offline_queue) == 0:
            return 0
        if self._offline_queue.is_processing:
            return 0
        if self._offline_queue.get_load > 75:
            return 0
        stored_messages = retrieve_offline_messages(self.storage, self.debug)
        if stored_messages:
            for msg in stored_messages:
                try:
                    self._offline_queue.put(msg)
                except QueueFull:
                    time.sleep(.01)
                    return 0
                except Exception as e:
                    if self.debug:
                        print(f"Error adding message to offline queue: {e}")
        if not self.client_enabled:
            try:
                batch_messages = []
                batch_ttls = []
                while len(self._offline_queue) > 0 and len(batch_messages) < 10:
                    message = self._offline_queue.queue.get()
                    db_ttl = (
                        message.pop("_offline_ttl", 86400)
                        if isinstance(message, dict)
                        else 0
                    )
                    batch_messages.append(message)
                    batch_ttls.append(db_ttl)
                if batch_messages:
                    keys = safe_storage_operation(
                        self.storage,
                        "put_batch",
                        batch_messages,
                        ttl=batch_ttls[0] if len(set(batch_ttls)) == 1 else batch_ttls,
                    )
                    if keys is not None:
                        return len(batch_messages)
                    else:
                        for msg, ttl in zip(batch_messages, batch_ttls):
                            msg["_offline_ttl"] = ttl
                            self._offline_queue.put(msg)
            except Exception as e:
                if self.debug:
                    print(f"Offline queue processing error during network loss: {e}")
            return 0
        processed = 0
        batch_messages = []
        batch_ttls = []
        while len(self._offline_queue) > 0:
            try:
                if len(batch_messages) == 10:
                    break
                message = self._offline_queue.queue.get()
                db_ttl = (
                    message.pop("_offline_ttl") if isinstance(message, dict) else 86400
                )
                batch_messages.append(message)
                batch_ttls.append(db_ttl)
            except Exception as e:
                if self.debug:
                    print(f"Error processing offline queue: {e}")
                break
        if batch_messages:
            try:
                if self.client_enabled and not self._proc:
                    try:
                        success = self.mqtt.send_batch(batch_messages)
                        if success:
                            processed = len(batch_messages)
                        else:
                            for msg in batch_messages:
                                self._offline_queue.put(msg)
                    except Exception as send_err:
                        if self.debug:
                            print(f"message send failed: {send_err}")
                        for msg in batch_messages:
                            msg["_offline_ttl"] = batch_ttls[batch_messages.index(msg)]
                            self._offline_queue.put(msg)
                keys = safe_storage_operation(
                    self.storage,
                    "put_batch",
                    batch_messages,
                    ttl=batch_ttls[0] if len(set(batch_ttls)) == 1 else batch_ttls,
                )
                if keys is not None:
                    processed += len(batch_messages)
                else:
                    for msg, ttl in zip(batch_messages, batch_ttls):
                        msg["_offline_ttl"] = ttl
                        self._offline_queue.put(msg)
            except Exception as batch_err:
                if self.debug:
                    print(f"Batch Message Storage Error: {batch_err}")
                    for msg, ttl in zip(batch_messages, batch_ttls):
                        msg["_offline_ttl"] = ttl
                        self._offline_queue.put(msg)
        return processed

    def _send_offline_messages(self):
        if not self.client_enabled:
            return 0
        offline_messages = retrieve_offline_messages(self.storage, self.debug)
        return send_offline_messages(
            self.mqtt,
            offline_messages,
            debug=self.debug,
        )

    async def _async_connect(self):
        jti = self.network.connect()
        if jti:
            try:
                # NTP sync happens in network.connect(), so mark as synced
                if not self._ntp_synced:
                    self._ntp_synced = True
                    self._update_queued_timestamps()

                if self.mqtt.connect():
                    self.client_enabled = True
                    gc.collect()
                    if self.debug:
                        print("Connected to Tendrl Server")
                    return True
            except Exception as e:
                if self.debug:
                    print(f"Connection error: {e}")
        return False

    async def _async_process_message(self, msg):
        self._process_message(msg)

    async def _async_cleanup_offline_messages(self):
        await self._cleanup_offline_messages()

    def db_put(self, data, ttl=0, tags=None):
        if not self.client_db:
            try:
                from tendrl.lib.microtetherdb.db import MicroTetherDB
            except ImportError:
                raise DBError("Client database not available - install full package with MicroTetherDB")
            else:
                raise DBError("Client database disabled - set client_db=True in constructor")
        try:
            with self.client_db as store:
                return store.put(data, ttl=ttl, tags=tags)
        except Exception as e:
            if self.debug:
                print(f"Client database put error: {e}")
            return None

    def db_get(self, key):
        if not self.client_db:
            if not BTREE_AVAILABLE:
                raise DBError("Client database not available - install full package with MicroTetherDB")
            else:
                raise DBError("Client database disabled - set client_db=True in constructor")
        try:
            with self.client_db as store:
                return store.get(key)
        except Exception as e:
            if self.debug:
                print(f"Client database get error: {e}")
            return None

    def db_query(self, query_dict=None):
        if not self.client_db:
            if not BTREE_AVAILABLE:
                raise DBError("Client database not available - install full package with MicroTetherDB")
            else:
                raise DBError("Client database disabled - set client_db=True in constructor")
        try:
            with self.client_db as store:
                return store.query(query_dict or {})
        except Exception as e:
            if self.debug:
                print(f"Client database query error: {e}")
            return []

    def db_delete(self, key=None, purge=False):
        if not self.client_db:
            if not BTREE_AVAILABLE:
                raise DBError("Client database not available - install full package with MicroTetherDB")
            else:
                raise DBError("Client database disabled - set client_db=True in constructor")
        try:
            with self.client_db as store:
                return store.delete(key, purge=purge)
        except Exception as e:
            if self.debug:
                print(f"Client database delete error: {e}")
            return 0

    def db_list(self):
        if not self.client_db:
            if not BTREE_AVAILABLE:
                raise DBError("Client database not available - install full package with MicroTetherDB")
            else:
                raise DBError("Client database disabled - set client_db=True in constructor")
        try:
            with self.client_db as store:
                return store.all()
        except Exception as e:
            if self.debug:
                print(f"Client database list error: {e}")
            return []

    def db_cleanup(self):
        if not self.client_db:
            if not BTREE_AVAILABLE:
                raise DBError("Client database not available - install full package with MicroTetherDB")
            else:
                raise DBError("Client database disabled - set client_db=True in constructor")
        try:
            with self.client_db as store:
                result = store.cleanup()
                return result
        except Exception as e:
            if self.debug:
                print(f"Client database force cleanup error: {e}")
            return 0
