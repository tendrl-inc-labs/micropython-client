import asyncio
from collections import deque
import gc
import json
import random
import time
import os

import btree


from .core.future import Future
from .core.exceptions import DBLock
from .core.utils import ensure_dirs

class MicroTetherDB:
    def __init__(self, filename="microtether.db", in_memory=True, ram_percentage=25,
                 max_retries=3, retry_delay=0.1, lock_timeout=5.0, cleanup_interval=3600,
                 btree_cachesize=32, btree_pagesize=512, adaptive_threshold=True):
        self.filename = filename
        self.in_memory = in_memory
        self.ram_percentage = ram_percentage
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.lock_timeout = lock_timeout
        self.cleanup_interval = cleanup_interval
        self.btree_cachesize = btree_cachesize
        self.btree_pagesize = btree_pagesize
        self.adaptive_threshold = adaptive_threshold
        self._db = None
        self._db_handle = None
        self._lock = asyncio.Lock()
        self._last_cleanup = 0
        self._worker = None
        self._running = False
        self._queue = deque((), 50)
        self._loop = asyncio.get_event_loop()
        self._operation_counts = {
            "put": 0,
            "delete": 0,
            "batch_put": 0,
            "batch_delete": 0
        }
        self._flush_counter = 0
        self._flush_threshold = 10  # Keep lower flush threshold
        self._last_flush_time = time.time()
        # Smart auto-flush: memory doesn't need aggressive time-based flushing
        self._auto_flush_seconds = 10 if self.in_memory else 5
        try:
            self._init_db()
            self._start_worker()
        except MemoryError:
            # If we get a memory error, try to fall back to file-based storage
            if self.in_memory:
                print("Warning: Not enough memory for in-memory storage. Falling back to file-based storage.")
                self.in_memory = False
                self._init_db()
                self._start_worker()
            else:
                raise

    def _init_db(self):
        try:
            gc.collect()
            if self.in_memory:
                # Use MicroPython's built-in BytesIO - officially supported by btree
                try:
                    import io
                    self._db_handle = io.BytesIO()
                except ImportError:
                    # Fallback to uio if io not available
                    import uio
                    self._db_handle = uio.BytesIO()
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
            self._loop.run_until_complete(self._cleanup())
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise

    def _start_worker(self):
        if self._running:
            return
        self._running = True
        self._worker = asyncio.create_task(self._worker_task())

    async def _worker_task(self):
        try:
            while self._running:
                try:
                    current_time = time.time()
                    if (current_time - self._last_cleanup) >= self.cleanup_interval:
                        await self._cleanup()
                        self._last_cleanup = current_time
                    if not self._queue:
                        await asyncio.sleep(0.01)
                        continue
                    await self._process_next()
                except Exception as e:
                    print(f"Worker error: {e}")
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

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

    def _adaptive_flush_threshold(self):
        if not self.adaptive_threshold:
            return self._flush_threshold
        # For in-memory operations, use moderate threshold for better individual performance
        # BytesIO doesn't need as aggressive flushing as VFS systems
        if self.in_memory:
            return max(5, self._flush_threshold // 2)  # Moderate threshold
        # Calculate based on operation counts for file operations
        total_ops = sum(self._operation_counts.values())
        if total_ops < 100:
            return 10
        elif total_ops < 1000:
            return 15
        else:
            return 20

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
                    key = self._generate_key(ttl)
                    while key in self._db:
                        key = self._generate_key(ttl)
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
                except Exception:
                    raise
                self._operation_counts["put"] += 1
                self._flush_counter += 1
                current_time = time.time()
                effective_threshold = self._adaptive_flush_threshold()
                
                # For in-memory, be much more aggressive with flushing to avoid buildup
                # For file operations, use adaptive thresholds
                should_flush = (
                    self._flush_counter >= effective_threshold or
                    current_time - self._last_flush_time >= self._auto_flush_seconds
                )
                if should_flush:
                    self._db.flush()
                    self._flush_counter = 0
                    self._last_flush_time = current_time
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
                    try:
                        import io
                        self._db_handle = io.BytesIO()
                    except ImportError:
                        import uio
                        self._db_handle = uio.BytesIO()
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
                self._flush_counter = 0
                self._last_flush_time = time.time()
                return 1  # Return 1 to indicate success

            key_bytes = key.encode() if isinstance(key, str) else key
            if key_bytes in self._db:
                del self._db[key_bytes]
                self._operation_counts["delete"] += 1
                self._flush_counter += 1
                current_time = time.time()
                effective_threshold = self._adaptive_flush_threshold()
                should_flush = (
                    self._flush_counter >= effective_threshold or
                    current_time - self._last_flush_time >= self._auto_flush_seconds
                )
                if should_flush:
                    self._db.flush()
                    self._flush_counter = 0
                    self._last_flush_time = current_time
                return 1
            return 0
        finally:
            self._lock.release()

    async def _query(self, query_dict):
        await self._acquire_lock()
        try:
            results = []
            limit = query_dict.pop("$limit", None)
            if limit is not None:
                limit = int(limit)

            def get_field_value(doc, field):
                keys = field.split(".")
                current = doc
                for key in keys:
                    if not isinstance(current, dict):
                        return None
                    current = current.get(key)
                return current

            def matches_query(doc):
                if not query_dict:
                    return True
                for field, condition in query_dict.items():
                    if field == "tags":
                        field_value = doc.get("_tags", [])
                        if not isinstance(condition, dict):
                            if condition not in field_value:
                                return False
                            continue
                    else:
                        field_value = get_field_value(doc, field)
                    if not isinstance(condition, dict):
                        if field_value != condition:
                            return False
                        continue
                    for op, op_value in condition.items():
                        if op == "$eq" and field_value != op_value:
                            return False
                        if op == "$gt" and (
                            not isinstance(field_value, (int, float)) or
                            field_value <= op_value
                        ):
                            return False
                        if op == "$gte" and (
                            not isinstance(field_value, (int, float)) or
                            field_value < op_value
                        ):
                            return False
                        if op == "$lt" and (
                            not isinstance(field_value, (int, float)) or
                            field_value >= op_value
                        ):
                            return False
                        if op == "$lte" and (
                            not isinstance(field_value, (int, float)) or
                            field_value > op_value
                        ):
                            return False
                        if op == "$in" and field_value not in op_value:
                            return False
                        if op == "$ne" and field_value == op_value:
                            return False
                        if op == "$exists" and (field_value is None) == op_value:
                            return False
                        if op == "$contains":
                            contains = False
                            if isinstance(field_value, list) and op_value in field_value:
                                contains = True
                            elif isinstance(field_value, str) and op_value in field_value:
                                contains = True
                            if not contains:
                                return False
                return True
            batch_size = 20
            current_batch = []
            for key in self._db.keys(None, None, btree.INCL):
                try:
                    raw_data = self._db[key]
                    doc = json.loads(raw_data.decode())
                    if matches_query(doc):
                        current_batch.append(doc)
                        if len(current_batch) >= batch_size:
                            results.extend(current_batch)
                            current_batch = []
                            if limit is not None and len(results) >= limit:
                                results = results[:limit]
                                break
                except Exception as e:
                    print(f"Error processing document: {e}")
                    continue
            if current_batch:
                results.extend(current_batch)
                if limit is not None:
                    results = results[:limit]
            return results
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
                key = self._generate_key(int(item_ttl))
                encoded_data = json_data.encode()
                self._db[key] = encoded_data
                batch_keys.append(key)
            self._operation_counts["batch_put"] += 1
            self._flush_counter += len(batch_keys)
            current_time = time.time()
            effective_threshold = self._adaptive_flush_threshold()
            should_flush = (
                self._flush_counter >= effective_threshold or
                current_time - self._last_flush_time >= self._auto_flush_seconds
            )
            if should_flush:
                self._db.flush()
                self._flush_counter = 0
                self._last_flush_time = current_time
            return batch_keys
        finally:
            self._lock.release()

    def delete_batch(self, keys):
        if not isinstance(keys, list):
            if hasattr(keys, '__iter__'):
                keys = list(keys)
            else:
                keys = [keys]
        future = Future()
        self._queue.append((future, "delete_batch", (keys,), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
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
            self._operation_counts["batch_delete"] += 1
            self._flush_counter += deleted_count
            current_time = time.time()
            effective_threshold = self._adaptive_flush_threshold()
            should_flush = (
                self._flush_counter >= effective_threshold or
                current_time - self._last_flush_time >= self._auto_flush_seconds
            )
            if should_flush:
                self._db.flush()
                self._flush_counter = 0
                self._last_flush_time = current_time
            return deleted_count
        finally:
            self._lock.release()

    def _generate_key(self, ttl=0):
        current_time = int(time.time())
        unique_id = random.getrandbits(16)
        ttl = int(ttl) if ttl is not None else 0
        return f"{current_time}:{ttl}:{unique_id}"

    def _is_expired(self, key):
        try:
            timestamp_str, ttl_str, _ = key.split(":")
            timestamp = int(timestamp_str)
            ttl = int(ttl_str)
            if ttl == 0:
                return False
            current_time = int(time.time())
            return current_time > (timestamp + ttl)
        except (ValueError, IndexError):
            return True

    async def _cleanup(self):
        await self._acquire_lock()
        try:
            deleted = 0
            keys = list(self._db.keys(None, None, btree.INCL))
            for key in keys:
                try:
                    key_str = key.decode()
                    if self._is_expired(key_str):
                        del self._db[key]
                        deleted += 1
                except (UnicodeDecodeError, ValueError):
                    continue
            if deleted > 0:
                self._db.flush()
            return {"deleted": deleted}
        finally:
            self._lock.release()

    def cleanup(self):
        result = self._loop.run_until_complete(self._cleanup())
        self._last_cleanup = time.time()
        return result["deleted"] if result else 0

    def put(self, *args, **kwargs):
        if len(args) == 2:
            key, data = args
            kwargs['_id'] = key
            data_arg = data
        else:
            data_arg = args[0] if args else {}
        future = Future()
        self._queue.append((future, "put", (data_arg,), kwargs))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    def get(self, key):
        future = Future()
        try:
            self._queue.append((future, "get", (key,), {}))
            if len(self._queue) == 1:
                self._loop.run_until_complete(self._process_next())
            result = future.result()
            return result
        except Exception as e:
            raise

    def delete(self, key=None, purge=False):
        future = Future()
        self._queue.append((future, "delete", (key,), {"purge": purge}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    def query(self, query_dict):
        future = Future()
        self._queue.append((future, "query", (query_dict,), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    def put_batch(self, items, ttls=None):
        future = Future()
        self._queue.append((future, "put_batch", (items,), {"ttls": ttls}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

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
                self._loop.run_until_complete(self._worker)
            except asyncio.CancelledError:
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
