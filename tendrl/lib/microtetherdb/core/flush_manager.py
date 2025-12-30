import time


class FlushManager:
    """Manages database flushing operations and operation counting"""
    
    def __init__(self, adaptive_threshold=True, in_memory=True):
        self.adaptive_threshold = adaptive_threshold
        self.in_memory = in_memory
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
        # Cache adaptive threshold calculation to avoid repeated sum() calls
        self._cached_threshold = None
        self._last_threshold_check_ops = 0
    
    def get_adaptive_flush_threshold(self):
        """Calculate adaptive flush threshold based on operation patterns"""
        if not self.adaptive_threshold:
            return self._flush_threshold
        
        # For in-memory operations, use moderate threshold for better individual performance
        # BytesIO doesn't need as aggressive flushing as VFS systems
        if self.in_memory:
            return max(5, self._flush_threshold // 2)  # Moderate threshold
        
        # Cache threshold calculation - only recalculate if operation counts changed significantly
        # (Avoid expensive sum() call on every check)
        total_ops = sum(self._operation_counts.values())
        # Only recalculate if ops changed by more than 10% (performance optimization)
        if (self._cached_threshold is None or 
            abs(total_ops - self._last_threshold_check_ops) > max(10, self._last_threshold_check_ops * 0.1)):
            if total_ops < 100:
                self._cached_threshold = 10
            elif total_ops < 1000:
                self._cached_threshold = 15
            else:
                self._cached_threshold = 20
            self._last_threshold_check_ops = total_ops
        return self._cached_threshold
    
    def should_flush(self, additional_ops=1):
        """Check if database should be flushed based on counters and time"""
        current_time = time.time()
        effective_threshold = self.get_adaptive_flush_threshold()
        
        return (
            (self._flush_counter + additional_ops) >= effective_threshold or
            current_time - self._last_flush_time >= self._auto_flush_seconds
        )
    
    def record_operation(self, operation_type, count=1):
        """Record an operation for counting and flush decision making"""
        if operation_type in self._operation_counts:
            self._operation_counts[operation_type] += 1
        self._flush_counter += count
    
    def flush_if_needed(self, db, force=False):
        """Flush database if needed and reset counters"""
        if force or self.should_flush():
            db.flush()
            self._flush_counter = 0
            self._last_flush_time = time.time()
            return True
        return False
    
    def reset_counters(self):
        """Reset flush counters (used after manual flush)"""
        self._flush_counter = 0
        self._last_flush_time = time.time()
    
    @property
    def operation_counts(self):
        """Get current operation counts"""
        return self._operation_counts.copy()
    
    @property
    def flush_counter(self):
        """Get current flush counter"""
        return self._flush_counter 