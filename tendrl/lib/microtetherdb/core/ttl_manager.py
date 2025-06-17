import time
import heapq


class TTLManager:
    """Manages TTL (Time-To-Live) functionality for database keys"""
    
    def __init__(self):
        self._ttl_index = []  # Min-heap of (expiry_time, key) tuples
        self._last_ttl_check = 0
    
    def rebuild_index(self, db_keys):
        """Rebuild TTL index from existing database keys"""
        self._ttl_index = []
        try:
            for key_bytes in db_keys:
                try:
                    key_str = key_bytes.decode()
                    expiry_time = self.get_expiry_time(key_str)
                    if expiry_time is not None:  # Has TTL
                        heapq.heappush(self._ttl_index, (expiry_time, key_str))
                except (UnicodeDecodeError, ValueError):
                    continue
        except Exception as e:
            print(f"Warning: Failed to rebuild TTL index: {e}")
    
    def get_expiry_time(self, key):
        """Get expiry timestamp for a key, or None if no TTL"""
        try:
            timestamp_str, ttl_str, _ = key.split(":")
            timestamp = int(timestamp_str)
            ttl = int(ttl_str)
            if ttl == 0:
                return None  # No TTL
            return timestamp + ttl
        except (ValueError, IndexError):
            return None
    
    def add_to_index(self, key, ttl):
        """Add a key with TTL to the index"""
        if ttl and ttl > 0:
            current_time = int(time.time())
            expiry_time = current_time + int(ttl)
            heapq.heappush(self._ttl_index, (expiry_time, key))
    
    def remove_from_index(self, key):
        """Remove a key from TTL index (lazy removal - will be cleaned up during check)"""
        # Note: We don't actively remove from heap as it's expensive
        # Instead, we'll check if key exists when processing the heap
        pass
    
    def is_expired(self, key):
        """Check if a key is expired based on its embedded TTL"""
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
    
    async def check_expiry(self, db, flush_callback=None):
        """Check and remove expired items from TTL index - much more efficient"""
        if not self._ttl_index:
            return 0
            
        current_time = int(time.time())
        deleted = 0
        
        # Process expired items from the front of the heap
        while self._ttl_index and self._ttl_index[0][0] <= current_time:
            expiry_time, key = heapq.heappop(self._ttl_index)
            
            # Check if key still exists (handles lazy deletion)
            key_bytes = key.encode()
            if key_bytes in db:
                # Double-check expiry in case of clock changes
                if self.is_expired(key):
                    try:
                        del db[key_bytes]
                        deleted += 1
                    except KeyError:
                        pass  # Already deleted
        
        if deleted > 0 and flush_callback:
            flush_callback()
            
        return deleted
    
    def should_check_ttl(self, ttl_check_interval):
        """Check if it's time to run TTL expiry check"""
        current_time = time.time()
        if (current_time - self._last_ttl_check) >= ttl_check_interval:
            self._last_ttl_check = current_time
            return True
        return False
    
    @property
    def index_size(self):
        """Get the current size of the TTL index"""
        return len(self._ttl_index) 