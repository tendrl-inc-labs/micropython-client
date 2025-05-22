"""
Main database implementation
"""

import os
import json
import time
import gc
import asyncio
import random
from collections import deque
try:
    import btree
except ImportError:
    btree = None

from .core.ram_device import RAMBlockDevice
from .core.future import Future
from .core.exceptions import DBLock
from .core.compression import compress_data, decompress_data, HAS_UZLIB

class MicroTetherDB:
    """A lightweight key-value database for MicroPython"""
    
    def _calculate_ram_size(self, ram_percentage):
        """Calculate appropriate RAM block size based on available memory and percentage
        
        Args:
            ram_percentage (int): Percentage of free memory to use (1-100)
        """
        try:
            # Get memory info
            total_mem = gc.mem_alloc() + gc.mem_free()
            free_mem = gc.mem_free()
            
            # Calculate target memory based on percentage
            target_mem = int(free_mem * (ram_percentage / 100))
            
            # Ensure minimum and maximum constraints
            target_mem = min(max(target_mem, 1024), 32768)  # Between 1KB and 32KB
            
            # Calculate block size and count
            # Prefer smaller blocks for better memory management
            block_size = min(256, target_mem // 16)  # Max 256 bytes per block
            num_blocks = target_mem // block_size
            
            # Ensure we have at least 8 blocks
            if num_blocks < 8:
                block_size = target_mem // 8
                num_blocks = 8
                
            print(f"Memory info - Total: {total_mem}, Free: {free_mem}")
            print(f"Using {num_blocks} blocks of {block_size} bytes each ({ram_percentage}% of free memory)")
            
            return num_blocks, block_size
        except:
            # Fallback to conservative defaults if memory info is unavailable
            return 16, 128

    def __init__(self, filename=None, in_memory=True, ram_percentage=15, 
                 use_compression=True, min_compress_size=256, max_retries=3, 
                 retry_delay=0.1, lock_timeout=5.0, cleanup_interval=3600,
                 btree_cachesize=32, btree_pagesize=512, adaptive_threshold=True):

        if not in_memory and not filename:
            raise ValueError("filename is required for file-based storage")
            
        self.filename = filename
        self.in_memory = in_memory
        
        # Calculate RAM size based on percentage
        if in_memory:
            self.ram_blocks, self.ram_block_size = self._calculate_ram_size(ram_percentage)
        else:
            self.ram_blocks = None
            self.ram_block_size = None
            
        self.use_compression = use_compression and HAS_UZLIB
        self.min_compress_size = min_compress_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.lock_timeout = lock_timeout
        self.cleanup_interval = cleanup_interval
        self.btree_cachesize = btree_cachesize
        self.btree_pagesize = btree_pagesize
        self.adaptive_threshold = adaptive_threshold
        
        if use_compression and not HAS_UZLIB:
            print("Warning: Compression requested but uzlib not available. Compression disabled.")
            
        self._db = None
        self._ram_device = None
        self._lock = asyncio.Lock()
        self._last_cleanup = 0
        self._worker = None
        self._running = False
        self._queue = deque((), 50)  # Reduced queue size
        self._loop = asyncio.get_event_loop()
        self._operation_counts = {
            "put": 0,
            "delete": 0,
            "batch_put": 0,
            "batch_delete": 0
        }
        self._flush_counter = 0
        self._flush_threshold = 10  # Reduced flush threshold
        self._last_flush_time = time.time()
        self._auto_flush_seconds = 5
        
        try:
            self._init_db()
            self._start_worker()
        except MemoryError:
            # If we get a memory error, try to fall back to file-based storage
            if self.in_memory:
                print("Warning: Not enough memory for in-memory storage. Falling back to file-based storage.")
                self.in_memory = False
                if not self.filename:
                    self.filename = "microtetherdb.db"
                self._init_db()
                self._start_worker()
            else:
                raise
                
    def _init_db(self):
        """Initialize the database connection"""
        try:
            gc.collect()  # Force garbage collection before initialization
            if self.in_memory:
                try:
                    self._ram_device = RAMBlockDevice(self.ram_blocks, self.ram_block_size)
                    os.VfsLfs2.mkfs(self._ram_device)
                    os.mount(self._ram_device, "/ram")
                    self._db_handle = open("/ram/db", "r+b")
                except MemoryError:
                    # If we still get a memory error, try with smaller blocks
                    if self.ram_blocks > 16 or self.ram_block_size > 128:
                        print("Warning: Reducing RAM block size due to memory constraints")
                        self.ram_blocks = min(16, self.ram_blocks)
                        self.ram_block_size = min(128, self.ram_block_size)
                        self._ram_device = RAMBlockDevice(self.ram_blocks, self.ram_block_size)
                        os.VfsLfs2.mkfs(self._ram_device)
                        os.mount(self._ram_device, "/ram")
                        self._db_handle = open("/ram/db", "r+b")
                    else:
                        raise
            else:
                self._db_handle = open(self.filename, "r+b")
                
            self._db = btree.open(
                self._db_handle,
                cachesize=self.btree_cachesize,
                pagesize=self.btree_pagesize
            )
            self._loop.run_until_complete(self._cleanup())
        except OSError:
            if self.in_memory:
                self._db_handle = open("/ram/db", "wb")
            else:
                self._db_handle = open(self.filename, "wb")
            self._db_handle.write(b"")
            self._db_handle.close()
            
            if self.in_memory:
                self._db_handle = open("/ram/db", "r+b")
            else:
                self._db_handle = open(self.filename, "r+b")
                
            self._db = btree.open(
                self._db_handle,
                cachesize=self.btree_cachesize,
                pagesize=self.btree_pagesize
            )
            
    def _start_worker(self):
        """Start the background worker task"""
        if self._running:
            return
        self._running = True
        self._worker = asyncio.create_task(self._worker_task())
        
    async def _worker_task(self):
        """Background worker task for async operations"""
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
        """Process the next operation in the queue"""
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
        """Calculate adaptive flush threshold based on operation patterns"""
        if not self.adaptive_threshold:
            return self._flush_threshold
            
        total_ops = sum(self._operation_counts.values())
        batch_ops = self._operation_counts["batch_put"] + self._operation_counts["batch_delete"]
        
        if total_ops < 100:
            return self._flush_threshold
            
        batch_ratio = batch_ops / total_ops if total_ops > 0 else 0
        if batch_ratio > 0.8:
            return max(50, self._flush_threshold * 2)
        elif batch_ratio > 0.5:
            return max(30, self._flush_threshold * 1.5)
        return self._flush_threshold
        
    async def _acquire_lock(self):
        """Acquire the database lock with timeout"""
        try:
            await asyncio.wait_for(self._lock.acquire(), self.lock_timeout)
        except asyncio.TimeoutError:
            raise DBLock("Database is locked. Operation timed out.")

    async def _put(self, data, ttl=None, tags=None, _id=None):
        """Store a value in the database"""
        await self._acquire_lock()
        try:
            if _id is None:
                key = self._generate_key(ttl)
                while key in self._db:
                    key = self._generate_key(ttl)
            else:
                key = str(_id)
                
            if tags:
                data["_tags"] = tags
                
            json_data = json.dumps(data)
            if len(json_data) > 1024:
                raise ValueError("Data too large")
                
            encoded_data = json_data.encode()
            compressed_data, is_compressed = compress_data(
                encoded_data,
                self.use_compression,
                self.min_compress_size
            )
            
            if is_compressed:
                final_data = b"\x01" + compressed_data
            else:
                final_data = b"\x00" + encoded_data
                
            self._db[key] = final_data
            self._operation_counts["put"] += 1
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
                
            return key
        finally:
            self._lock.release()

    async def _get(self, key):
        """Retrieve a value from the database"""
        await self._acquire_lock()
        try:
            if not isinstance(key, str):
                key = str(key)
            if key not in self._db:
                return None
                
            raw_data = self._db[key]
            is_compressed = raw_data[0] == 1
            data_bytes = raw_data[1:]
            decompressed_data = decompress_data(data_bytes, is_compressed)
            return json.loads(decompressed_data.decode())
        finally:
            self._lock.release()

    async def _delete(self, key, purge=False):
        """Delete a value from the database"""
        await self._acquire_lock()
        try:
            if purge:
                # Instead of using clear(), delete all keys one by one
                count = 0
                for k in self._db.keys(None, None, btree.INCL):
                    del self._db[k]
                    count += 1
                self._db.flush()
                self._flush_counter = 0
                self._last_flush_time = time.time()
                return count
                
            if key in self._db:
                del self._db[key]
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
        """Query the database with complex conditions"""
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
                    # Special handling for tags
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
                        elif op == "$gt" and (
                            not isinstance(field_value, (int, float)) or
                            field_value <= op_value
                        ):
                            return False
                        elif op == "$gte" and (
                            not isinstance(field_value, (int, float)) or
                            field_value < op_value
                        ):
                            return False
                        elif op == "$lt" and (
                            not isinstance(field_value, (int, float)) or
                            field_value >= op_value
                        ):
                            return False
                        elif op == "$lte" and (
                            not isinstance(field_value, (int, float)) or
                            field_value > op_value
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
                
            for key in self._db.keys(None, None, btree.INCL):
                try:
                    raw_data = self._db[key]
                    is_compressed = raw_data[0] == 1
                    data_bytes = raw_data[1:]
                    decompressed_data = decompress_data(data_bytes, is_compressed)
                    doc = json.loads(decompressed_data.decode())
                    if matches_query(doc):
                        results.append(doc)
                        if limit is not None and len(results) == limit:
                            break
                except Exception as e:
                    print(f"Error processing document: {e}")
                    continue
            return results
        finally:
            self._lock.release()

    async def _put_batch(self, items, ttls=None):
        """Store multiple values in the database"""
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
                if len(json_data) > 1024:
                    continue
                key = self._generate_key(int(item_ttl))
                encoded_data = json_data.encode()
                compressed_data, is_compressed = compress_data(
                    encoded_data,
                    self.use_compression,
                    self.min_compress_size
                )
                if is_compressed:
                    final_data = b"\x01" + compressed_data
                else:
                    final_data = b"\x00" + encoded_data
                self._db[key] = final_data
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
        """Delete multiple values from the database"""
        # Convert keys to list if it's not already
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
        """Delete multiple values from the database"""
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
        """Generate a unique key with timestamp and TTL"""
        current_time = int(time.time())
        unique_id = random.getrandbits(8)
        return f"{current_time}:{ttl}:{unique_id}"
        
    def _is_expired(self, key):
        """Check if a key has expired based on its TTL"""
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
        """Clean up expired entries"""
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
        """Force cleanup of expired entries"""
        result = self._loop.run_until_complete(self._cleanup())
        self._last_cleanup = time.time()
        return result["deleted"] if result else 0
        
    def put(self, *args, **kwargs):
        """Store a value in the database
        
        Can be called in two ways:
        1. put(data, ttl=None, tags=None, _id=None)
        2. put(key, data, ttl=None, tags=None)
        """
        if len(args) == 2:  # Called as put(key, data, ...)
            key, data = args
            kwargs['_id'] = key
            data_arg = data
        else:  # Called as put(data, ...)
            data_arg = args[0] if args else {}
            
        future = Future()
        self._queue.append((future, "put", (data_arg,), kwargs))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()
        
    def get(self, key):
        """Retrieve a value from the database"""
        future = Future()
        self._queue.append((future, "get", (key,), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()
        
    def delete(self, key=None, purge=False):
        """Delete a value from the database"""
        future = Future()
        self._queue.append((future, "delete", (key,), {"purge": purge}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()
        
    def query(self, query_dict):
        """Query the database with complex conditions"""
        future = Future()
        self._queue.append((future, "query", (query_dict,), {}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()
        
    def put_batch(self, items, ttls=None):
        """Store multiple values in the database"""
        future = Future()
        self._queue.append((future, "put_batch", (items,), {"ttls": ttls}))
        if len(self._queue) == 1:
            self._loop.run_until_complete(self._process_next())
        return future.result()
        
    async def __aenter__(self):
        """Async context manager entry"""
        self._start_worker()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self._stop_worker()
        
    def __enter__(self):
        """Context manager entry"""
        self._start_worker()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self._stop_worker()
        
    def _stop_worker(self):
        """Stop the background worker task"""
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
            
    def __del__(self):
        """Cleanup when the database is destroyed"""
        self._stop_worker()
        if self._db_handle:
            self._db_handle.close()
        if self.in_memory and self._ram_device:
            try:
                os.umount("/ram")
            except:
                pass 