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
        block_size = min(256, target_mem // 16)
        num_blocks = target_mem // block_size
        if num_blocks < 8:
            block_size = target_mem // 8
            num_blocks = 8
        return num_blocks, block_size
    except:
        return 16, 128

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
