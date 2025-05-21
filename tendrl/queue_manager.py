import gc
import time
from .utils.util_helpers import Queue, QueueFull


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
                print("Already processing") #TODO: Remove
            return None
        if not self.queue:
            return None
        self.is_processing = True
        try:
            # Calculate max messages based on memory
            max_messages = min(round((gc.mem_free() / 1000) * 3), self.max_batch_size)
            # Collect all messages up to max_messages
            batch = []
            while len(self.queue) > 0 and len(batch) < max_messages:
                msg = next(self.queue)
                if msg is not None:
                    batch.append(msg)
            if batch:
                if self.debug:
                    print(f"Collected {len(batch)} messages, queue size: {len(self.queue)}") #TODO: Remove
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
