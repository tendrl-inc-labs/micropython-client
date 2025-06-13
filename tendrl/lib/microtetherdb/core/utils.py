import os
import gc

def calculate_ram_size(ram_percentage):
    try:
        try:
            free_mem = gc.mem_free()
        except AttributeError:
            gc.collect()
            free_mem = 32768
        target_mem = int(free_mem * (ram_percentage / 100))
        target_mem = min(max(target_mem, 1024), 32768)
        
        # Use 512-byte blocks for FAT filesystem compatibility
        block_size = 512
        num_blocks = target_mem // block_size
        
        # Ensure we have at least 8 blocks
        if num_blocks < 8:
            num_blocks = 8
            
        return num_blocks, block_size
    except:
        return 16, 512  # Safe default with 512-byte blocks

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
