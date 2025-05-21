import gc

BASELINE_ALLOC = None

def init_baseline_alloc():
    global BASELINE_ALLOC
    gc.collect()
    BASELINE_ALLOC = gc.mem_alloc()

def get_baseline_alloc():
    return BASELINE_ALLOC or 0