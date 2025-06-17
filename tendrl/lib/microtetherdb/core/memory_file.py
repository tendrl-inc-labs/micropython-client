class MemoryFile:
    """
    A simple in-memory file-like object optimized for btree operations.
    This avoids the overhead of VFS/FAT filesystem layers.
    """
    
    def __init__(self, initial_size=8192):
        self._buffer = bytearray(initial_size)
        self._size = 0  # Actual data size
        self._pos = 0   # Current position
        self._closed = False
    
    def _ensure_capacity(self, needed_size):
        """Ensure buffer has enough capacity"""
        if needed_size > len(self._buffer):
            # Grow by 1.5x or needed size, whichever is larger
            new_size = max(needed_size, int(len(self._buffer) * 1.5))
            new_buffer = bytearray(new_size)
            new_buffer[:self._size] = self._buffer[:self._size]
            self._buffer = new_buffer
    
    def read(self, size=-1):
        """Read up to size bytes from the file"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if size is None or size < 0:
            # Read all remaining data
            data = bytes(self._buffer[self._pos:self._size])
            self._pos = self._size
        else:
            # Read up to size bytes
            end_pos = min(self._pos + size, self._size)
            data = bytes(self._buffer[self._pos:end_pos])
            self._pos = end_pos
        
        return data
    
    def write(self, data):
        """Write data to the file"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes or bytearray")
        
        write_end = self._pos + len(data)
        self._ensure_capacity(write_end)
        
        # Write the data
        self._buffer[self._pos:write_end] = data
        self._pos = write_end
        
        # Update size if we wrote beyond current size
        if self._pos > self._size:
            self._size = self._pos
        
        return len(data)
    
    def seek(self, offset, whence=0):
        """Change stream position"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if whence == 0:  # SEEK_SET
            new_pos = offset
        elif whence == 1:  # SEEK_CUR
            new_pos = self._pos + offset
        elif whence == 2:  # SEEK_END
            new_pos = self._size + offset
        else:
            raise ValueError("whence must be 0, 1, or 2")
        
        if new_pos < 0:
            new_pos = 0
        
        self._pos = new_pos
        return self._pos
    
    def tell(self):
        """Return current stream position"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        return self._pos
    
    def flush(self):
        """Flush write buffers (no-op for memory file)"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        # No-op for memory file
        pass
    
    def close(self):
        """Close the file"""
        self._closed = True
    
    def closed(self):
        """Return whether file is closed"""
        return self._closed
    
    def readable(self):
        """Return whether file is readable"""
        return not self._closed
    
    def writable(self):
        """Return whether file is writable"""
        return not self._closed
    
    def seekable(self):
        """Return whether file supports seek operations"""
        return not self._closed
    
    def truncate(self, size=None):
        """Truncate file to at most size bytes"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if size is None:
            size = self._pos
        
        if size < 0:
            raise ValueError("negative truncate size")
        
        if size < self._size:
            self._size = size
            if self._pos > self._size:
                self._pos = self._size
        
        return self._size
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 