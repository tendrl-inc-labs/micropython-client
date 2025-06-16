import asyncio
from collections import deque
import gc
import io
import json
import time
import os

import btree

from .core.future import Future
from .core.exceptions import DBLock
from .core.utils import ensure_dirs
from .core.ttl_manager import TTLManager
from .core.query_engine import QueryEngine
from .core.flush_manager import FlushManager
from .core.key_generator import KeyGenerator


class MicroTetherDB:
    def __init__(self, filename="microtether.db", in_memory=True, ram_percentage=25,
                 max_retries=3, retry_delay=0.1, lock_timeout=5.0,
                 ttl_check_interval=60, btree_cachesize=32, btree_pagesize=512, adaptive_threshold=True,
                 event_loop=None):
        self.filename = filename
        self.in_memory = in_memory
        self.ram_percentage = ram_percentage
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.lock_timeout = lock_timeout

        self.ttl_check_interval = ttl_check_interval
        self.btree_cachesize = btree_cachesize
        self.btree_pagesize = btree_pagesize
        self.adaptive_threshold = adaptive_threshold

        # Core components
        self._db = None
        self._db_handle = None
        self._lock = None  # Will be initialized when we have a loop
        self._worker = None
        self._running = False
        self._queue = deque((), 50)

        # Event loop handling - be more careful about when we get it
        self._loop = event_loop
        self._loop_provided = event_loop is not None

        # Initialize managers
        self._ttl_manager = TTLManager()
        self._flush_manager = FlushManager(adaptive_threshold, in_memory)

        try:
            self._init_db()
            # Only start worker if we're in an async context or loop was provided
            if self._loop_provided or self._is_async_context():
                self._start_worker()
        except MemoryError:
            # If we get a memory error, try to fall back to file-based storage
            if self.in_memory:
                print("Warning: Not enough memory for in-memory storage. Falling back to file-based storage.")
                self.in_memory = False
                self._flush_manager = FlushManager(adaptive_threshold, False)
                self._init_db()
                if self._loop_provided or self._is_async_context():
                    self._start_worker()
            else:
                raise

    def _is_async_context(self):
        """Check if we're in an async context"""
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def _get_or_create_loop(self):
        """Safely get or create an event loop"""
        if self._loop is not None:
            return self._loop

        try:
            # Try to get the running loop first
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, try to get the event loop
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                # Create a new loop if none exists
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

        return self._loop

    def _ensure_async_components(self):
        """Ensure async components are initialized"""
        if self._lock is None:
            self._get_or_create_loop()
            self._lock = asyncio.Lock()

    def _init_db(self):
        try:
            gc.collect()
            if self.in_memory:
                self._db_handle = io.BytesIO()
            else:
                # File-based storage initialization
                ensure_dirs(self.filename)
                try:
                    self._db_handle = open(self.filename, "r+b")
                except OSError:
                    self._db_handle = open(self.filename, "w+b")
            try:
                self._db = btree.open(
                    self._db_handle,
                    cachesize=self.btree_cachesize,
                    pagesize=self.btree_pagesize
                )
                try:
                    next(self._db.keys(None, None, btree.INCL))
                except StopIteration:
                    pass
                except Exception as e:
                    print(f"Warning: Database verification failed: {e}")
            except Exception as e:
                print(f"Error creating btree database: {e}")
                raise
            # Build TTL index from existing data
            keys = list(self._db.keys(None, None, btree.INCL))
            self._ttl_manager.rebuild_index(keys)

            # Database initialization complete
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise

    def _start_worker(self):
        if self._running:
            return

        self._ensure_async_components()
        self._running = True

        loop = self._get_or_create_loop()
        self._worker = loop.create_task(self._worker_task())

    async def _worker_task(self):
        try:
            while self._running:
                try:
                    current_time = time.time()

                    # TTL expiry checks
                    if self._ttl_manager.should_check_ttl(self.ttl_check_interval):
                        deleted = await self._ttl_manager.check_expiry(
                            self._db,
                            lambda: self._db.flush()
                        )
                        if deleted > 0:
                            print(f"TTL cleanup: removed {deleted} expired items")

                    if not self._queue:
                        await asyncio.sleep(0.01)
                        continue
                    await self._process_next()
                except Exception as e:
                    print(f"Worker error: {e}")
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass

    async def _process_next(self):
        if not self._queue:
            return
        future, operation, args, kwargs = self._queue.popleft()
        try:
            if operation == "put":
                result = await self._put(args[0], **kwargs)
            elif operation == "get":
                result = await self._get(args[0])
            elif operation == "delete":
                result = await self._delete(args[0], **kwargs)
            elif operation == "query":
                result = await self._query(args[0])
            elif operation == "put_batch":
                result = await self._put_batch(args[0], ttls=kwargs.get("ttls"))
            elif operation == "delete_batch":
                result = await self._delete_batch(args[0])
            else:
                raise ValueError(f"Unknown operation: {operation}")
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)

    async def _acquire_lock(self):
        try:
            if self._lock.locked():
                raise DBLock("Database is already locked")
            await self._lock.acquire()
        except asyncio.TimeoutError:
            raise DBLock("Database is locked. Operation timed out.")
        except Exception as e:
            raise DBLock(f"Failed to acquire lock: {str(e)}")

    async def _put(self, data, ttl=None, tags=None, _id=None):
        try:
            await self._acquire_lock()
            try:
                if _id is None:
                    key = KeyGenerator.generate_key(ttl)
                    while key in self._db:
                        key = KeyGenerator.generate_key(ttl)
                else:
                    key = str(_id)
                key_bytes = key.encode()
                if tags:
                    data["_tags"] = tags
                json_data = json.dumps(data)
                if len(json_data) > 8192:  # 8KB limit
                    raise ValueError("Data too large: maximum size is 8KB after JSON serialization")
                encoded_data = json_data.encode()
                try:
                    self._db[key_bytes] = encoded_data
                    # Add to TTL index if has TTL
                    self._ttl_manager.add_to_index(key, ttl)
                except Exception:
                    raise

                self._flush_manager.record_operation("put")
                self._flush_manager.flush_if_needed(self._db)
                return key
            finally:
                self._lock.release()
        except Exception as e:
            raise

    async def _get(self, key):
        if not self._db or not self._db_handle:
            return None
        try:
            await self._acquire_lock()
            try:
                key_bytes = key.encode() if isinstance(key, str) else key
                try:
                    raw_data = self._db[key_bytes]
                    return json.loads(raw_data.decode())
                except KeyError:
                    return None
                except Exception as e:
                    raise
            finally:
                self._lock.release()
        except Exception as e:
            if isinstance(e, DBLock):
                return None
            raise

    async def _delete(self, key, purge=False):
        await self._acquire_lock()
        try:
            if purge:
                # Close current database and file handle
                if self._db:
                    try:
                        self._db.flush()
                    except Exception:
                        pass
                    self._db = None
                if self._db_handle:
                    try:
                        self._db_handle.close()
                    except Exception:
                        pass
                    self._db_handle = None
                # For file-based storage, delete the file
                if not self.in_memory:
                    try:
                        os.remove(self.filename)
                    except Exception:
                        pass
                # Reopen database
                if self.in_memory:
                    # Create fresh BytesIO for purged database
                    self._db_handle = io.BytesIO()
                else:
                    ensure_dirs(self.filename)
                    self._db_handle = open(self.filename, "w+b")
                try:
                    self._db = btree.open(
                        self._db_handle,
                        cachesize=self.btree_cachesize,
                        pagesize=self.btree_pagesize
                    )
                except Exception as e:
                    raise ValueError(f"Failed to recreate database: {e}")
                # Clear TTL index and flush manager
                self._ttl_manager = TTLManager()
                self._flush_manager.reset_counters()
                return 1  # Return 1 to indicate success

            key_bytes = key.encode() if isinstance(key, str) else key
            if key_bytes in self._db:
                del self._db[key_bytes]
                # Remove from TTL index (lazy removal)
                self._ttl_manager.remove_from_index(key)
                self._flush_manager.record_operation("delete")
                self._flush_manager.flush_if_needed(self._db)
                return 1
            return 0
        finally:
            self._lock.release()

    async def _query(self, query_dict):
        await self._acquire_lock()
        try:
            return await QueryEngine.execute_query(self._db, query_dict)
        finally:
            self._lock.release()

    async def _put_batch(self, items, ttls=None):
        await self._acquire_lock()
        try:
            if not items:
                return []
            if ttls is None:
                ttl_list = [0] * len(items)
            elif isinstance(ttls, (int, float)):
                ttl_list = [int(ttls)] * len(items)
            elif isinstance(ttls, list):
                if len(ttls) != len(items):
                    raise ValueError("TTL list must match the number of items")
                ttl_list = [int(t) for t in ttls]
            else:
                raise ValueError("TTL must be an integer, float, or list of numbers")
            batch_keys = []
            for item, item_ttl in zip(items, ttl_list):
                if not isinstance(item, dict):
                    continue
                json_data = json.dumps(item)
                if len(json_data) > 8192:  # 8KB limit
                    continue
                key = KeyGenerator.generate_key(int(item_ttl))
                encoded_data = json_data.encode()
                self._db[key] = encoded_data
                # Add to TTL index if has TTL
                self._ttl_manager.add_to_index(key, item_ttl)
                batch_keys.append(key)

            self._flush_manager.record_operation("batch_put", len(batch_keys))
            self._flush_manager.flush_if_needed(self._db)
            return batch_keys
        finally:
            self._lock.release()

    def delete_batch(self, keys):
        self._ensure_async_components()
        if not isinstance(keys, list):
            if hasattr(keys, '__iter__'):
                keys = list(keys)
            else:
                keys = [keys]
        future = Future()
        self._queue.append((future, "delete_batch", (keys,), {}))
        if len(self._queue) == 1:
            loop = self._get_or_create_loop()
            loop.run_until_complete(self._process_next())
        result = future.result()
        return result if result is not None else 0

    async def _delete_batch(self, keys):
        await self._acquire_lock()
        try:
            if not isinstance(keys, list):
                if hasattr(keys, '__iter__'):
                    keys = list(keys)
                else:
                    keys = [keys]
            deleted_count = 0
            for key in keys:
                if not isinstance(key, str):
                    key = str(key)
                if key in self._db:
                    del self._db[key]
                    deleted_count += 1

            self._flush_manager.record_operation("batch_delete", deleted_count)
            self._flush_manager.flush_if_needed(self._db)
            return deleted_count
        finally:
            self._lock.release()



    # Public API methods
    def put(self, *args, **kwargs):
        self._ensure_async_components()
        if len(args) == 2:
            key, data = args
            kwargs['_id'] = key
            data_arg = data
        else:
            data_arg = args[0] if args else {}
        future = Future()
        self._queue.append((future, "put", (data_arg,), kwargs))
        if len(self._queue) == 1:
            loop = self._get_or_create_loop()
            loop.run_until_complete(self._process_next())
        return future.result()

    def get(self, key):
        self._ensure_async_components()
        future = Future()
        try:
            self._queue.append((future, "get", (key,), {}))
            if len(self._queue) == 1:
                loop = self._get_or_create_loop()
                loop.run_until_complete(self._process_next())
            result = future.result()
            return result
        except Exception as e:
            raise

    def delete(self, key=None, purge=False):
        self._ensure_async_components()
        future = Future()
        self._queue.append((future, "delete", (key,), {"purge": purge}))
        if len(self._queue) == 1:
            loop = self._get_or_create_loop()
            loop.run_until_complete(self._process_next())
        return future.result()

    def query(self, query_dict):
        self._ensure_async_components()
        future = Future()
        self._queue.append((future, "query", (query_dict,), {}))
        if len(self._queue) == 1:
            loop = self._get_or_create_loop()
            loop.run_until_complete(self._process_next())
        return future.result()

    def put_batch(self, items, ttls=None):
        self._ensure_async_components()
        future = Future()
        self._queue.append((future, "put_batch", (items,), {"ttls": ttls}))
        if len(self._queue) == 1:
            loop = self._get_or_create_loop()
            loop.run_until_complete(self._process_next())
        return future.result()

    # Context managers
    async def __aenter__(self):
        self._start_worker()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __enter__(self):
        self._start_worker()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _stop_worker(self):
        if not self._running:
            return
        self._running = False
        if self._worker:
            self._worker.cancel()
            try:
                if self._loop:
                    self._loop.run_until_complete(self._worker)
            except asyncio.CancelledError:
                pass
            except RuntimeError:
                # Event loop might be closed
                pass
            self._worker = None

    def close(self):
        self._stop_worker()
        if self._db:
            try:
                self._db.flush()
            except Exception:
                pass
            self._db = None
        if self._db_handle:
            try:
                self._db_handle.close()
            except Exception:
                pass
            self._db_handle = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # Properties for backward compatibility and debugging
    @property
    def _ttl_index(self):
        """Backward compatibility property"""
        return self._ttl_manager._ttl_index

    @property
    def _operation_counts(self):
        """Backward compatibility property"""
        return self._flush_manager.operation_counts

    @property
    def _flush_counter(self):
        """Backward compatibility property"""
        return self._flush_manager.flush_counter
