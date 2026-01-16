import gc
import time
import collections

class QueueFull(Exception):
    pass


class Queue:
    __slots__ = ("max_len", "_queue")

    def __init__(self, max_len: int = 300):
        self.max_len = max_len
        self._queue = self._new_queue()

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self._queue.popleft()
        except IndexError:
            raise StopIteration

    def __len__(self):
        return len(self._queue)

    def _new_queue(self):
        return collections.deque((), self.max_len, 1)

    def put(self, item):
        try:
            self._queue.append(item)
        except IndexError:
            raise QueueFull()

    def get(self):
        try:
            return self._queue.popleft()
        except IndexError:
            return None

    def peek(self):
        try:
            return self._queue[0]
        except IndexError:
            return None

    def clear(self):
        self._queue = self._new_queue()

class QueueManager:
    def __init__(
        self,
        max_size=150,
        max_batch=75,
        debug=False,
    ):
        self.queue = Queue(max_size)
        self.max_batch_size = max_batch
        self.debug = debug
        self._processing = False
        # Cache last calculated batch size to avoid repeated gc.mem_free() calls
        self._last_batch_size = max_batch
        self._last_mem_check_ticks = 0

    def __len__(self):
        return len(self.queue)

    @property
    def max_size(self):
        return self.queue.max_len

    def put(self, msg):
        try:
            self.queue.put(msg)
            return True
        except QueueFull:
            time.sleep(.3)
            self.put(msg)
        except Exception as e:
            if self.debug:
                print(f"Queue full error: {e}")
            return False

    def process_batch(self):
        if self.is_processing:
            if self.debug:
                print("Already processing")
            return None
        if not self.queue:
            return None
        self.is_processing = True
        try:
            # Cache batch size calculation - only recalculate every 5 seconds
            # (gc.mem_free() is relatively expensive, and memory doesn't change that fast)
            import time
            current_ticks = time.ticks_ms()
            if (self._last_mem_check_ticks == 0 or 
                time.ticks_diff(current_ticks, self._last_mem_check_ticks) >= 5000):
                self._last_batch_size = min(round((gc.mem_free() / 1000) * 3), self.max_batch_size)
                self._last_mem_check_ticks = current_ticks
            max_messages = self._last_batch_size
            batch = []
            while len(self.queue) > 0 and len(batch) < max_messages:
                msg = next(self.queue)
                if msg is not None:
                    batch.append(msg)
            if batch:
                gc.collect()
                return batch
            return None
        except Exception as e:
            if self.debug:
                print(f"Batch error: {e}")
            for msg in reversed(batch):
                self.queue.put(msg)
            return None
        finally:
            self.is_processing = False

    @property
    def is_processing(self):
        return self._processing

    @is_processing.setter
    def is_processing(self, value):
        self._processing = value

    @property
    def get_load(self):
        return (len(self.queue) / self.queue.max_len) * 100 if self.queue else 0
