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
            timestamp_str, ttl_str, unique_id = key.split(":")
            return {
                'timestamp': int(timestamp_str),
                'ttl': int(ttl_str),
                'unique_id': unique_id
            }
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def validate_key(key):
        return KeyGenerator.parse_key(key) is not None 