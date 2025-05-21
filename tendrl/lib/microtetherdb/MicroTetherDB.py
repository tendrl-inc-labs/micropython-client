import json
import random
import time
import asyncio
import sys
from collections import deque
import os

import gc

try:
    import uzlib
except ImportError:
    uzlib = None

try:
    import btree
except ImportError:
    sys.exit("btree module not found")


class Future:
    def __init__(self):
        self._result = None
        self._exception = None
        self._done = False
        self._callbacks = []

    def set_result(self, result):
        self._result = result
        self._done = True
        for callback in self._callbacks:
            callback(self)

    def set_exception(self, exception):
        self._exception = exception
        self._done = True
        for callback in self._callbacks:
            callback(self)

    def done(self):
        return self._done

    def result(self):
        if self._exception:
            raise self._exception
        return self._result

    def add_done_callback(self, fn):
        if self._done:
            fn(self)
        else:
            self._callbacks.append(fn)

    def __iter__(self):
        yield self
        return self.result()

    def __await__(self):
        return self.__iter__()


class DBLock(Exception):
    pass


class MicroTetherDB:
    """Main database class"""

    __slots__ = (
        "_filename",
        "_worker",
        "_running",
        "_queue",
        "_db",
        "_lock",
        "_last_data_load",
        "_cache_ttl",
        "_len_cache",
        "_loop",
        "_db_handle",
        "_data_cache",
        "_cache_size_limit",  # Maximum number of items to cache
        "_last_operation",  # Track last operation type
        "_flush_counter",  # Counter for delayed flushing
        "_flush_threshold",  # Threshold for flushing
        "_last_flush_time",  # Last time database was flushed
        "_auto_flush_seconds",  # Seconds between auto-flushes
        "_use_compression",  # Whether to use compression
        "_compress_min_size",  # Minimum size for compression
        "_btree_cachesize",  # BTree cache size
        "_btree_pagesize",  # BTree page size
        "_operation_counts",  # Track operations for adaptive threshold
        "_adaptive_threshold",  # Whether to use adaptive threshold
        "_last_cleanup",  # Last time cleanup was run
    )

    def __init__(
        self,
        filename,
        flush_threshold=20,
        auto_flush_seconds=5,
        btree_cachesize=128,
        btree_pagesize=1024,
        use_compression=True,
        compress_min_size=256,
        adaptive_threshold=True,
    ):
        """Initialize the database

        :param filename: Database filename
        :param flush_threshold: Number of operations before auto-flushing
        :param auto_flush_seconds: Seconds between auto-flushes
        :param btree_cachesize: Size of BTree cache (larger = faster, more memory)
        :param btree_pagesize: Size of BTree pages (larger = better for large data)
        :param use_compression: Whether to compress data (requires uzlib)
        :param compress_min_size: Minimum size in bytes for compression
        :param adaptive_threshold: Automatically adjust flush threshold based on workload
        """
        self._filename = filename
        self._worker = None
        self._running = False
        self._queue = deque((), 100)  # Use deque instead of Queue
        self._db = None
        self._lock = asyncio.Lock()  # For async operations
        self._last_data_load = 0
        self._cache_ttl = 60  # seconds
        self._len_cache = 0
        self._loop = asyncio.get_event_loop()  # Get current event loop
        self._db_handle = None
        self._data_cache = None
        self._cache_size_limit = 100  # Maximum items to cache
        self._last_operation = None
        self._last_cleanup = 0
        # BTree configuration
        self._btree_cachesize = btree_cachesize
        self._btree_pagesize = btree_pagesize
        # Compression settings
        self._use_compression = use_compression and uzlib is not None
        self._compress_min_size = compress_min_size
        # Delayed flush settings
        self._flush_counter = 0
        self._flush_threshold = flush_threshold
        self._auto_flush_seconds = auto_flush_seconds
        self._last_flush_time = time.time()
        # Adaptive threshold settings
        self._adaptive_threshold = adaptive_threshold
        self._operation_counts = {
            "put": 0,
            "delete": 0,
            "batch_put": 0,
            "batch_delete": 0,
        }
        self._init_db()
        self._start_worker()

    def _init_db(self):
        try:
            gc.collect()
            # Try to open existing database
            self._db_handle = open(self._filename, "r+b")
            self._db = btree.open(
                self._db_handle,
                cachesize=self._btree_cachesize,
                pagesize=self._btree_pagesize,
            )
            self._loop.run_until_complete(self._cleanup())
        except OSError:
            # Create new database if not found
            self._db_handle = open(self._filename, "wb")
            self._db_handle.write(b"")
            self._db_handle.close()
            self._db_handle = open(self._filename, "r+b")
            self._db = btree.open(
                self._db_handle,
                cachesize=self._btree_cachesize,
                pagesize=self._btree_pagesize,
            )

    def _compress_data(self, data):
        if (
            not self._use_compression
            or uzlib is None
            or len(data) < self._compress_min_size
        ):
            return data, False
        try:
            compressed = uzlib.compress(data, 9)  # Max compression
            if len(compressed) < len(data):
                return compressed, True
        except Exception as e:
            print(f"Compression error: {e}")
        return data, False

    def _decompress_data(self, data, is_compressed):
        if is_compressed and uzlib is not None:
            try:
                return uzlib.decompress(data, 32768)  # 32KB limit
            except Exception as e:
                print(f"Decompression error: {e}")
                return data
        return data

    def _adaptive_flush_threshold(self):
        if not self._adaptive_threshold:
            return self._flush_threshold
        total_ops = sum(self._operation_counts.values())
        batch_ops = (
            self._operation_counts["batch_put"] + self._operation_counts["batch_delete"]
        )
        if total_ops < 100:
            return self._flush_threshold
        batch_ratio = batch_ops / total_ops if total_ops > 0 else 0
        if batch_ratio > 0.8:
            return max(50, self._flush_threshold * 2)
        elif batch_ratio > 0.5:
            return max(30, self._flush_threshold * 1.5)
        else:
            return self._flush_threshold

    def _start_worker(self):
        if self._running:
            return
        self._running = True
        self._worker = asyncio.create_task(self._worker_task())

    async def _process_next(self):
        if not self._queue:
            return
        future, operation, args, kwargs = self._queue.popleft()
        try:
            if operation == "put":
                data = args[0] if args else {}
                ttl = kwargs.get("ttl", 0)
                tags = kwargs.get("tags", None)
                _id = kwargs.get("_id", None)
                result = await self._put(data, ttl=ttl, tags=tags, _id=_id)
                future.set_result(result)
            elif operation == "put_batch":
                # Extract items and ttl from kwargs.
                items = args[0] if args else []
                if not items:
                    future.set_result([])
                    return
                ttl = kwargs.get("ttl", None)
                result = await self._put_batch(items, ttl=ttl)
                future.set_result(result)
            elif operation == "get":
                key = args[0] if args else None
                result = await self._get(key)
                future.set_result(result)
            elif operation == "delete":
                key = args[0] if args else None
                purge = kwargs.get("purge", False)
                result = await self._delete(key, purge)
                future.set_result(result)
            elif operation == "delete_batch":
                keys = args[0] if args else []
                result = await self._delete_batch(keys)
                future.set_result(result)
            elif operation == "query":
                if not args or len(args) != 1 or not isinstance(args[0], dict):
                    print("Invalid query arguments!")
                    query_dict = {}
                else:
                    query_dict = args[0]
                result = await self._query(query_dict)
                future.set_result(result)
            else:
                future.set_exception(ValueError(f"Unknown operation: {operation}"))
        except Exception as e:
            print(f"Exception type: {type(e)}")
            print(f"Exception args: {e.args}")
            future.set_exception(e)
        if self._queue:
            await self._process_next()

    def __del__(self):
        self._stop_worker()
        if self._db_handle:
            self._db_handle.close()

    async def _worker_task(self):
        try:
            while self._running:
                try:
                    current_time = time.time()
                    if (current_time - self._last_cleanup) >= 60:
                        await self._cleanup()
                        self._cleanup_db_file()
                        self._last_cleanup = current_time
                    if not self._queue:
                        await asyncio.sleep(0.01)
                        continue
                    future, operation, args, kwargs = self._queue.popleft()
                    try:
                        if operation == "all":
                            result = await self._all()
                        elif operation == "put":
                            result = await self._put(args[0], **kwargs)
                        elif operation == "put_batch":
                            result = await self._put_batch(args[0], **kwargs)
                        elif operation == "get":
                            result = await self._get(args[0])
                        elif operation == "delete":
                            result = await self._delete(args[0])
                        elif operation == "delete_batch":
                            result = await self._delete_batch(args[0])
                        elif operation == "query":
                            if (
                                not args
                                or len(args) != 1
                                or not isinstance(args[0], dict)
                            ):
                                query_dict = {}
                            else:
                                query_dict = args[0]
                            result = await self._query(query_dict)
                        else:
                            raise ValueError(f"Unknown operation: {operation}")
                        future.set_result(result)
                    except Exception as e:
                        print(f"Error in {operation} operation: {e}")
                        future.set_exception(e)
                except Exception as e:
                    print(f"Worker error: {e}")
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Worker task error: {e}")
        finally:
            self._running = False

    async def _put(
        self, data: dict, ttl: int = 0, tags: list = None, _id: str = None
    ) -> str:
        """Perform a put operation with an optional TTL."""
        if data is None:
            data = {}

        if _id is not None:
            key = str(_id)
        else:
            key = self._generate_key(ttl)
            while key in self._db:
                key = self._generate_key(ttl)

        if tags:
            data["_tags"] = tags

        json_data = json.dumps(data)
        if len(json_data) > 1024:
            raise ValueError("Data too large")

        encoded_data = json_data.encode()
        compressed_data, is_compressed = self._compress_data(encoded_data)
        if is_compressed:
            final_data = b"\x01" + compressed_data
        else:
            final_data = b"\x00" + encoded_data

        async with self._lock:
            self._db[key] = final_data
            if _id is None:
                self._len_cache += 1
            self._last_operation = "put"
            self._operation_counts["put"] += 1
            self._flush_counter += 1
            current_time = time.time()
            effective_threshold = (
                self._adaptive_flush_threshold()
                if self._adaptive_threshold
                else self._flush_threshold
            )
            should_flush = (
                self._flush_counter >= effective_threshold
                or current_time - self._last_flush_time >= self._auto_flush_seconds
            )
            if should_flush:
                self._db.flush()
                self._flush_counter = 0
                self._last_flush_time = current_time
            self._data_cache = None
            return key

    async def _get(self, key: str, scan=False) -> dict:
        if scan:
            return (msg for msg in self._db.values())
        else:
            try:
                if not isinstance(key, str):
                    key = str(key)
                if key not in self._db:
                    return None

                raw_data = self._db[key]
                is_compressed = raw_data[0] == 1
                data_bytes = raw_data[1:]
                decompressed_data = self._decompress_data(data_bytes, is_compressed)
                result = json.loads(decompressed_data.decode())
                return result
            except KeyError:
                return None
            except Exception as e:
                print(f"Unexpected error in get operation: {type(e)}")
                print(f"Error details: {str(e)}")
                return None

    async def _delete(self, key: str = None, purge: bool = False) -> int:
        async with self._lock:
            if purge:
                count = sum(1 for _ in self._db)
                self._db.clear()
                self._len_cache = 0
                self._db.flush()
                self._flush_counter = 0
                self._last_flush_time = time.time()
                return count
            else:
                if key in self._db:
                    del self._db[key]
                    self._len_cache -= 1
                    self._operation_counts["delete"] += 1
                    self._flush_counter += 1
                    current_time = time.time()
                    effective_threshold = (
                        self._adaptive_flush_threshold()
                        if self._adaptive_threshold
                        else self._flush_threshold
                    )
                    should_flush = (
                        self._flush_counter >= effective_threshold
                        or current_time - self._last_flush_time
                        >= self._auto_flush_seconds
                    )
                    if should_flush:
                        self._db.flush()
                        self._flush_counter = 0
                        self._last_flush_time = current_time
                    count = 1
                else:
                    count = 0
            self._last_operation = "delete"
            self._data_cache = None
            return count

    async def _query(self, query_dict):
        results = []
        processed = 0
        matched = 0

        # Extract and remove limit from query_dict
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
                field_value = get_field_value(doc, field)
                if not isinstance(condition, dict):
                    if field_value != condition:
                        return False
                    continue
                for op, op_value in condition.items():
                    if op == "$eq" and field_value != op_value:
                        return False
                    elif op == "$gt" and (
                        not isinstance(field_value, (int, float))
                        or field_value <= op_value
                    ):
                        return False
                    elif op == "$gte" and (
                        not isinstance(field_value, (int, float))
                        or field_value < op_value
                    ):
                        return False
                    elif op == "$lt" and (
                        not isinstance(field_value, (int, float))
                        or field_value >= op_value
                    ):
                        return False
                    elif op == "$lte" and (
                        not isinstance(field_value, (int, float))
                        or field_value > op_value
                    ):
                        return False
                    elif op == "$in" and field_value not in op_value:
                        return False
                    elif op == "$ne" and field_value == op_value:
                        return False
                    elif op == "$exists" and (field_value is None) == op_value:
                        return False
                    elif op == "$contains":
                        contains = False
                        if isinstance(field_value, list) and op_value in field_value:
                            contains = True
                        elif isinstance(field_value, str) and op_value in field_value:
                            contains = True
                        if not contains:
                            return False
            return True
        try:
            for key in self._db.keys(None, None, btree.INCL):
                processed += 1
                try:
                    raw_data = self._db[key]
                    is_compressed = raw_data[0] == 1
                    data_bytes = raw_data[1:]
                    decompressed_data = self._decompress_data(data_bytes, is_compressed)
                    doc = json.loads(decompressed_data.decode())
                    if matches_query(doc):
                        matched += 1
                        results.append(doc)
                        if limit is not None and len(results) == limit:
                            break
                except Exception as e:
                    continue
            return results
        except Exception:
            return []

    async def _all(self):
        return (msg for msg in self._db.values())

    async def _cleanup(self) -> dict:
        async with self._lock:
            deleted = 0
            keys = list(self._db.keys(None, None, btree.INCL))
            for key in keys:
                try:
                    key_str = key.decode()
                    if self._is_expired(key_str):
                        del self._db[key]
                        deleted += 1
                except (UnicodeDecodeError, ValueError) as e:
                    print(f"Error processing key: {e}")
                    continue
            if deleted > 0:
                self._db.flush()
                self._len_cache -= deleted
            return {"deleted": deleted}

    def cleanup(self) -> int:
        result = self._loop.run_until_complete(self._cleanup())
        if not result:
            self._cleanup_db_file()
        self._last_cleanup = time.time()

        return result["deleted"] if result else 0

    def _generate_key(self, ttl: int = 0) -> str:
        current_time = int(time.time())
        unique_id = random.getrandbits(8)
        return f"{current_time}:{ttl}:{unique_id}"

    def _is_expired(self, key: str) -> bool:
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

    async def __aenter__(self):
        self._start_worker()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._stop_worker()

    def __enter__(self):
        self._start_worker()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_worker()

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

    def put(self, data: dict, ttl: int = 0, tags: list = None, _id: str = None) -> str:
        future = Future()
        self._queue.append(
            (future, "put", (data,), {"ttl": ttl, "tags": tags, "_id": _id})
        )
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    def get(self, key: str) -> dict:
        future = Future()
        self._queue.append((future, "get", (key,), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    def delete(self, key: str = None, purge: bool = False) -> int:
        future = Future()
        self._queue.append((future, "delete", (key,), {"purge": purge}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    def query(self, query_dict: dict) -> list:
        future = Future()
        self._queue.append((future, "query", (query_dict,), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    def all(self):
        future = Future()
        self._queue.append((future, "all", (), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()

    async def _put_batch(self, items, ttl=None):
        if not hasattr(items, "__len__"):
            items = list(items)
        # Now items is a list.
        if not items:
            return []
        if ttl is None:
            ttl_list = [0] * len(items)
        elif isinstance(ttl, (int, float)):
            ttl_list = [int(ttl)] * len(items)
        elif isinstance(ttl, list):
            if not hasattr(ttl, "__len__"):
                ttl = list(ttl)
            if len(ttl) != len(items):
                raise ValueError("TTL list must match the number of items")
            ttl_list = [int(t) for t in ttl]
        else:
            raise ValueError("TTL must be an integer, float, or list of numbers")
        batch_keys = []
        async with self._lock:
            for item, item_ttl in zip(items, ttl_list):
                if not isinstance(item, dict):
                    print(f"Skipping invalid item: {item}")
                    continue
                json_data = json.dumps(item)
                if len(json_data) > 1024:
                    print(f"Skipping item larger than 1KB: {item}")
                    continue
                key = self._generate_key(int(item_ttl))
                encoded_data = json_data.encode()
                compressed_data, is_compressed = self._compress_data(encoded_data)
                if is_compressed:
                    final_data = b"\x01" + compressed_data
                else:
                    final_data = b"\x00" + encoded_data
                self._db[key] = final_data
                batch_keys.append(key)
            self._operation_counts["batch_put"] += 1
            self._flush_counter += len(batch_keys)
            current_time = time.time()
            effective_threshold = (
                self._adaptive_flush_threshold()
                if self._adaptive_threshold
                else self._flush_threshold
            )
            should_flush = (
                self._flush_counter >= effective_threshold
                or current_time - self._last_flush_time >= self._auto_flush_seconds
            )
            if should_flush:
                self._db.flush()
                self._flush_counter = 0
                self._last_flush_time = current_time
            self._len_cache += len(batch_keys)
            self._last_operation = "put_batch"
            self._data_cache = None
        return batch_keys

    async def _delete_batch(self, keys: list) -> int:
        if not isinstance(keys, list):
            raise ValueError("Keys must be a list")
        deleted_count = 0
        async with self._lock:
            for key in keys:
                if not isinstance(key, str):
                    print(f"Skipping invalid key: {key}")
                    continue
                if key in self._db:
                    del self._db[key]
                    deleted_count += 1
            self._operation_counts["batch_delete"] += 1
            self._flush_counter += deleted_count
            current_time = time.time()
            effective_threshold = (
                self._adaptive_flush_threshold()
                if self._adaptive_threshold
                else self._flush_threshold
            )
            should_flush = (
                self._flush_counter >= effective_threshold
                or current_time - self._last_flush_time >= self._auto_flush_seconds
            )
            if should_flush:
                self._db.flush()
                self._flush_counter = 0
                self._last_flush_time = current_time
            self._len_cache -= deleted_count
            self._last_operation = "delete_batch"
            self._data_cache = None
        return deleted_count

    def put_batch(self, items, ttls=None):
        if not hasattr(items, "__len__"):
            items = list(items)
        if not items:
            return []
        if ttls is not None and not hasattr(ttls, "__len__"):
            ttls = list(ttls)
        future = Future()
        self._queue.append((future, "put_batch", (items,), {"ttl": ttls}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        result = future.result()
        return result if result is not None else []

    def delete_batch(self, keys):
        future = Future()
        self._queue.append((future, "delete_batch", (keys,), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        result = future.result()
        return result if result is not None else 0

    def _cleanup_db_file(self):
        try:
            try:
                file_size = os.stat(self._filename)[6]
            except OSError:
                return False
            if file_size > 1024:
                keys = list(self._db.keys(None, None, btree.INCL))
                if not keys:
                    try:
                        os.unlink(self._filename)
                    except OSError:
                        print(f"Could not remove file: {self._filename}")
                    self._init_db()
                    return True
            return False
        except Exception as e:
            print(f"Error during database file cleanup: {e}")
            return False
