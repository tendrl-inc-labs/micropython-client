import os
import gc

def calculate_ram_size(percentage=15):
    """Calculate RAM size based on percentage of free memory"""
    try:
        free_memory = gc.mem_free()
        total_memory = free_memory + gc.mem_alloc()
        
        # Calculate target memory size
        target_memory = int((free_memory * percentage) / 100)
        
        # Set dynamic limits based on total memory
        min_memory = min(2048, total_memory // 64)  # 2KB or 1/64 of total memory
        max_memory = min(total_memory // 4, target_memory)  # 25% of total memory or target
        
        # Ensure we stay within limits
        memory_size = max(min_memory, min(max_memory, target_memory))
        
        # Use smaller block size for better memory management
        block_size = 512  # Reduced from 1024 to 512 bytes
        
        # Calculate number of blocks
        num_blocks = max(16, memory_size // block_size)  # Minimum 16 blocks
        
        print(f"Memory allocation: {memory_size} bytes ({memory_size/1024:.1f}KB) from {total_memory} bytes total")
        return num_blocks, block_size
    except Exception as e:
        print(f"Error calculating RAM size: {e}")
        return 32, 512  # Safe default values

def ensure_dirs(path):
    if "/" not in path:
        return
    if not path.startswith("/"):
        path = "/" + path
    parts = path.split("/")
    curr_path = ""
    for i in range(len(parts) - 1):
        part = parts[i]
        if part:
            curr_path += "/" + part
            try:
                os.mkdir(curr_path)
            except OSError:
                pass
