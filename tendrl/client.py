import json
import sys
import time
import gc

from .utils.memory import init_baseline_alloc

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
    from tendrl.lib.microtetherdb.MicroTetherDB import MicroTetherDB as DB
    BTREE_AVAILABLE = True
except ImportError:
    BTREE_AVAILABLE = False

from .network_manager import NetworkManager
from .websocket_handler import WSHandler
from .queue_manager import QueueManager
from .utils.util_helpers import (
    safe_storage_operation,
    retrieve_offline_messages,
    send_offline_messages,
    make_message,
    free,
    QueueFull
)
from .config_manager import read_config

class DBError(Exception):
    pass

class Client:
    def __init__(self,mode="sync",debug=False,timer=0,freq=3,callback=None,
        check_msg_rate=5,max_batch_size=15,db_page_size=1024,watchdog=0,
        send_heartbeat=True, client_db=True, managed=True):
        if mode not in ["sync", "async"]:
            raise ValueError("Mode must be either 'sync' or 'async'")
        if mode == "async" and not ASYNCIO_AVAILABLE:
            raise ImportError("Asyncio module is required for async mode")
        if mode == "sync" and not MACHINE_AVAILABLE:
            raise ImportError("Machine module is required for sync mode")
        self.mode = mode
        self.managed = managed
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
        self.websocket = WSHandler(self.config, debug)
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
        self.client_enabled = False  # Start disabled in both modes
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
        self._proc = False
        self._e_type = f"mp:{self.config['tendrl_version']}:" + ".".join(
            [str(i) for i in sys.implementation.version[:-1]]
        )
        if callback and not callable(callback):
            raise TypeError("callback must be a function accepting dict")
        self._app_timer = None
        self._wdt = watchdog
        if mode == "async":
            self._stop_event = asyncio.Event()
            self._tasks = []
        if BTREE_AVAILABLE and managed:
            try:
                self._db = DB("/lib/tendrl/tether.db", btree_pagesize=db_page_size)
                if client_db:
                    self._client_db = DB("/lib/tendrl/client_db.db",btree_pagesize=1024)
            except Exception as e:
                print(f"Storage initialization error: {e}")
        else:
            print("btree module not available or unmanaged mode, database disabled")

    @property
    def storage(self):
        return self._db

    @property
    def client_db(self):
        return self._client_db

    def _process_message(self, msg):
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
            jti = self.network.connect()
            if jti:
                if self.websocket.connect(jti, e_type=self._e_type):
                    self.client_enabled = True
                    gc.collect()
                    if self.debug:
                        print("Connected to Tendrl Server")
                    return True
            self.client_enabled, self.websocket.connected = False, False
            return False
        except Exception as e:
            self.client_enabled = False
            if self.debug:
                print(f"Connection error: {e}")
            return False
        finally:
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
        if (self._last_cleanup - time.time()) >= 60:
            try:
                async with self.storage as store:
                    cleanup_result = store.ttl_cleanup()
                    if self.debug and cleanup_result.get("deleted", 0) > 0:
                        print(
                            f"Cleaned up {cleanup_result['deleted']} expired offline messages"
                        )
                if self.client_db:
                    async with self.client_db as store:
                        cleanup_result = store.ttl_cleanup()
                        if self.debug and cleanup_result.get("deleted", 0) > 0:
                            print(
                                f"Cleaned up {cleanup_result['deleted']} expired offline messages"
                            )
            except Exception as e:
                if self.debug:
                    print(f"Offline message cleanup error: {e}")

    # ===== SYNC MODE IMPLEMENTATION =====
    def _timer_callback(self, timer):
        if self._proc:
            return
        self._proc = True
        did_work = False
        try:
            current_time = time.time()

            # Send heartbeat
            if self.send_heartbeat and (current_time - self._last_heartbeat) >= 30:
                try:
                    self._last_heartbeat = current_time
                    msg = make_message(free(bytes_only=True), "heartbeat")
                    response = self.websocket.send_message(msg)
                    if response.get("code") >= 400:
                        self.client_enabled, self.websocket.connected = False, False
                    did_work = True
                except Exception:
                    self.client_enabled, self.websocket.connected = False, False
                    return

            # Attempt reconnect if not connected
            if not self.client_enabled:
                if (current_time - self._last_connect) >= 30:
                    if self._connect():
                        did_work = True
                    else:
                        self.client_enabled = False
                else:
                    self._process_offline_queue()
                return

            # Process queue
            try:
                batch = self.queue.process_batch()
                if batch:
                    try:
                        response = self.websocket.send_batch(batch)
                        if (not response or 
                            (isinstance(response, dict) and response.get("code") == 401)):
                            self.client_enabled = False
                            if self.debug:
                                print("Unauthorized or no response")
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

            # Check messages
            if current_time - self._last_msg_check >= self.check_msg_rate:
                try:
                    self._last_msg_check = current_time
                    msg = self.websocket.check_messages()
                    if msg:
                        self._process_message(msg)
                        did_work = True
                except Exception as check_msg_err:
                    if self.debug:
                        print(f"Check messages error: {check_msg_err}")
                    self.client_enabled, self.websocket.connected = False, False

            # Cleanup
            if current_time - self._last_cleanup >= 60:
                self._sync_cleanup_offline_messages()
                self._last_cleanup = current_time
                did_work = True

            # Process offline queue
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

    def _sync_cleanup_offline_messages(self):
        result = safe_storage_operation(self.storage, "ttl_cleanup")
        if self._client_db:
            safe_storage_operation(self._client_db, "ttl_cleanup")
        return result

    # ===== ASYNC MODE IMPLEMENTATION =====
    async def _process_queue(self):
        if self.client_enabled:
            try:
                if len(self.queue.queue):
                    batch = self.queue.process_batch()
                    if batch:
                        response = self.websocket.send_batch(batch)
                        if not response:
                            self.client_enabled, self.websocket.connected = False, False
                        elif isinstance(response, dict):
                            if response.get("code") == 401:
                                if self.debug:
                                    print("Unauthorized: Disabling client")
                                    self.stop()
                                self.client_enabled, self.websocket.connected = False, False
            except Exception as e:
                if self.debug:
                    print(f"Queue processing error: {e}")
                self.client_enabled, self.websocket.connected = False, False

    async def _send_heartbeat(self):
        current_time = time.time()
        if (current_time - self._last_heartbeat) >= 30:
            try:
                self._last_heartbeat = current_time
                msg = make_message(free(bytes_only=True), "heartbeat")
                send_result = self.websocket.send_message(msg)

                if not send_result:
                    self.client_enabled, self.websocket.connected = False, False
            except Exception as e:
                if self.debug:
                    print(f"Heartbeat error: {e}")
                self.client_enabled, self.websocket.connected = False, False

    async def _check_messages(self):
        current_time = time.time()
        if (current_time - self._last_msg_check) >= self.check_msg_rate:
            try:
                self._last_msg_check = current_time
                msg = self.websocket.check_messages()
                if msg:
                    self._process_message(msg)
            except Exception as e:
                if self.debug:
                    print(f"Message check error: {e}")

    async def _async_callback(self):
        while not self._stop_event.is_set():
            did_work = False
            try:
                if self._proc:
                    await asyncio.sleep(0.1)
                    continue
                self._proc = True
                current_time = time.time()

                # Reconnect if not enabled
                if not self.client_enabled:
                    if (current_time - self._last_connect) >= 30:
                        try:
                            if await self._async_connect():
                                if self.debug:
                                    print("Connection successfully established")
                                did_work = True
                            else:
                                self.client_enabled = False
                        except Exception as connect_err:
                            if self.debug:
                                print(f"Unexpected connection error: {connect_err}")
                    self._process_offline_queue()
                    await asyncio.sleep(0.5)
                    continue

                # Process queue
                await self._process_queue()
                did_work = True

                # Send heartbeat
                if self.send_heartbeat and (current_time - self._last_heartbeat) >= 30:
                    try:
                        await self._send_heartbeat()
                        did_work = True
                    except Exception:
                        self.client_enabled, self.websocket.connected = False, False
                        return

                # Check messages
                await self._check_messages()
                did_work = True

                # Cleanup expired messages
                await self._cleanup_offline_messages()
                did_work = True

                # Process offline queue
                if self._process_offline_queue() > 0:
                    did_work = True

                # Feed watchdog if active
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

        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

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
                        wait_response=False,
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
                            entity=entity,
                            wait_response=False,
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
                        wait_response=False,
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
                            entity=entity,
                            wait_response=False,
                        )
                        self._store_offline_message(error_message, db_ttl)
                    raise
            return async_wrapped_function if is_async else sync_wrapped_function
        return wrapper

    def publish(
        self,
        data,
        wait_response=False,
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

            # Ensure we're connected before sending
            if not self.client_enabled:
                if not self._connect():
                    if self.debug:
                        print("Failed to establish connection")
                    return None

            if not isinstance(data, dict):
                data = {"data": str(data)}
            message = make_message(
                data, "publish", tags=tags, entity=entity, wait_response=wait_response
            )
            if wait_response:
                r = self.websocket.send_message(message)
                if r.get("code") != 200:
                    if self.debug:
                        print(f"Error publishing message: {r}")
                return r.get("content")
            if self.managed:
                if not self.queue.put(message):
                    if self.debug:
                        print("Failed to queue message - queue full")
                    if self.storage and write_offline:
                        self._store_offline_message(message, db_ttl)
            else:
                # In unmanaged mode, send directly
                r = self.websocket.send_message(message)
                if r.get("code") != 200:
                    if self.debug:
                        print(f"Error publishing message: {r}")
                    self.client_enabled = False  # Disable client on error
                return r.get("content", "")
            return ""
        finally:
            self._proc = False

    def _scheduled_timer_callback(self, timer):
        # Use micropython.schedule to run the actual timer callback
        micropython.schedule(self._timer_callback, timer)

    def start(self, watchdog=0):
        if self.debug:
            print(f"Starting Tendrl Client in {self.mode} mode...")
        self.client_enabled = False
        if self.mode == "sync":
            self._connect()
            if MACHINE_AVAILABLE and self._timer_id <= 3:
                self._app_timer = machine.Timer(self._timer_id)
                init_baseline_alloc()
                self._app_timer.init(
                    mode=machine.Timer.PERIODIC,
                    freq=self._timer_freq,
                    callback=self._scheduled_timer_callback,  # Use the new scheduled callback
                )
            if watchdog and MACHINE_AVAILABLE:
                self._wdt = machine.WDT(timeout=min(max(watchdog, 1), 60) * 1000)
        else:
            self._connect()
            self._stop_event.clear()
            self._tasks = []
            init_baseline_alloc()
            try:
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
                print(
                    "To use async mode properly, call client.start() inside an async function"
                )
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
            self.websocket.cleanup()
        except Exception as e:
            if self.debug:
                print(f"Error closing websocket: {e}")
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
        try:
            self.websocket.cleanup()
        except Exception as e:
            if self.debug:
                print(f"Error closing websocket: {e}")
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
                # will this ever not be a dict?
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
                        response = self.websocket.send_batch(batch_messages)
                        if response:
                            if response.get("code") != 200:
                                for msg in batch_messages:
                                    self._offline_queue.put(msg)
                            else:
                                processed = len(batch_messages)
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
            self.websocket,
            offline_messages,
            debug=self.debug,
        )

    async def _async_connect(self):
        jti = self.network.connect()
        if jti:
            try:
                if self.websocket.connect(jti, e_type=self._e_type):
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

    # ===== CLIENT DATABASE =====
    def db_put(self, data, ttl=0, tags=None):
        if not self.client_db:
            raise DBError(f"client_db config: {self.client_db}")
        try:
            with self.client_db as store:
                return store.put(data, ttl=ttl, tags=tags)
        except Exception as e:
            if self.debug:
                print(f"Client database put error: {e}")
            return None

    def db_get(self, key):
        if not self.client_db:
            raise DBError(f"client_db config: {self.client_db}")
        try:
            with self.client_db as store:
                return store.get(key)
        except Exception as e:
            if self.debug:
                print(f"Client database get error: {e}")
            return None

    def db_query(self, query_dict=None):
        if not self.client_db:
            raise DBError(f"client_db config: {self.client_db}")
        try:
            with self.client_db as store:
                return store.query(query_dict or {})
        except Exception as e:
            if self.debug:
                print(f"Client database query error: {e}")
            return []

    def db_delete(self, key=None, purge=False):
        if not self.client_db:
            raise DBError(f"client_db config: {self.client_db}")
        try:
            with self.client_db as store:
                return store.delete(key, purge=purge)
        except Exception as e:
            if self.debug:
                print(f"Client database delete error: {e}")
            return 0

    # returns a generator of all messages in the database
    def db_list(self):
        if not self.client_db:
            raise DBError(f"client_db config: {self.client_db}")
        try:
            with self.client_db as store:
                return store.all()
        except Exception as e:
            if self.debug:
                print(f"Client database list error: {e}")
            return []

    def db_cleanup(self):
        if not self.client_db:
            raise DBError(f"client_db config: {self.client_db}")
        try:
            with self.client_db as store:
                result = store.ttl_cleanup()
                return result
        except Exception as e:
            if self.debug:
                print(f"Client database force cleanup error: {e}")
            return 0
