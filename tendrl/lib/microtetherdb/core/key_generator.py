import time
import random


class KeyGenerator:
    
    @staticmethod
    def generate_key(ttl=0):
        current_time = int(time.time())
        unique_id = random.getrandbits(16)
        ttl = int(ttl) if ttl is not None else 0
        return f"{current_time}:{ttl}:{unique_id}"
    
    @staticmethod
    def parse_key(key):
        try:
            # Optimize: use split with maxsplit=2 to avoid unnecessary splits
            parts = key.split(":", 2)
            if len(parts) < 3:
                return None
            return {
                'timestamp': int(parts[0]),
                'ttl': int(parts[1]),
                'unique_id': parts[2]
            }
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def validate_key(key):
        return KeyGenerator.parse_key(key) is not None 