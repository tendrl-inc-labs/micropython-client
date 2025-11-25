import json
import time

FROZEN_CONFIG_PATH = "/lib/tendrl/config.json"
USER_CONFIG_PATH = "/config.json"
USER_CONFIG_KEYS = ["api_key", "wifi_ssid", "wifi_pw", "reset"]

def read_config():
    user_config = {}
    try:
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config_content = f.read()
            if user_config_content.strip():  # Only try to parse if file has content
                user_config = json.loads(user_config_content)
    except (OSError, ValueError) as e:
        print(f"❌ Error reading user config: {e}")
        user_config = {}

    frozen_config = {}
    try:
        with open(FROZEN_CONFIG_PATH, "r", encoding="utf-8") as f:
            frozen_config_content = f.read()
            frozen_config = json.loads(frozen_config_content)
    except Exception:
        raise

    try:
        merged_config = frozen_config.copy()
        merged_config.update(user_config)

        for key in USER_CONFIG_KEYS:
            if key not in merged_config:
                merged_config[key] = ""

        return merged_config
    except Exception:
        raise


def save_config(config):
    try:
        try:
            with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                existing_config = json.load(f)
        except (OSError, ValueError):
            existing_config = {}

        user_config = {k: v for k, v in config.items() if k in USER_CONFIG_KEYS}

        for key, value in user_config.items():
            if value is not None and value != "":
                existing_config[key] = value

        with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_config, f)
        return True
    except (OSError, ValueError) as e:
        print(f"❌ Error saving config: {e}")
        return False


def update_config(api_key_id="", subject=""):
    try:
        config = read_config()

        if api_key_id is not None:
            config["api_key_id"] = api_key_id
        if subject is not None:
            config["subject"] = subject

        return save_config(config)
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

# Cache TTL: 24 hours (86400 seconds)
ENTITY_CACHE_TTL = 86400

def _compute_api_key_hash(api_key):
    """Compute a simple hash of the API key for validation"""
    if not api_key:
        return None
    # Simple hash: length + first/last chars (lightweight for MicroPython)
    key_len = len(api_key)
    if key_len > 10:
        return f"{key_len}:{api_key[:3]}:{api_key[-3:]}"
    return f"{key_len}:{api_key}"

def update_entity_cache(api_key_id="", subject="", api_key_hash=""):
    """Update entity cache with validation data"""
    try:
        if not api_key_id or not subject:
            return False
        if not isinstance(api_key_id, str) or not isinstance(subject, str):
            return False
        if len(api_key_id.strip()) == 0 or len(subject.strip()) == 0:
            return False
        
        cache_file = "/lib/tendrl/entity_cache.json"
        cache_data = {
            "api_key_id": api_key_id,
            "subject": subject,
            "api_key_hash": api_key_hash,
            "cached_at": time.time()
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        return True
    except Exception as e:
        print(f"❌ Error updating entity cache: {e}")
        return False

def _get_api_key_from_config():
    """Read API key directly from config.json file"""
    try:
        user_config = {}
        try:
            with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config_content = f.read()
                if user_config_content.strip():
                    user_config = json.loads(user_config_content)
        except (OSError, ValueError):
            pass
        
        frozen_config = {}
        try:
            with open(FROZEN_CONFIG_PATH, "r", encoding="utf-8") as f:
                frozen_config_content = f.read()
                frozen_config = json.loads(frozen_config_content)
        except Exception:
            pass
        
        merged_config = frozen_config.copy()
        merged_config.update(user_config)
        
        return merged_config.get("api_key", "")
    except Exception:
        return ""

def get_entity_cache(api_key_hash=None, check_config_file=True, debug=False):
    """Get cached entity info with validation
    
    Args:
        api_key_hash: Hash of the API key to validate against cache
        check_config_file: If True, check config.json file for API key changes
        debug: If True, print debug messages
    """
    try:
        cache_file = "/lib/tendrl/entity_cache.json"
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            
            cached_api_key_id = cache_data.get("api_key_id")
            cached_subject = cache_data.get("subject")
            cached_hash = cache_data.get("api_key_hash")
            cached_at = cache_data.get("cached_at", 0)
            
            if cached_at and (time.time() - cached_at) > ENTITY_CACHE_TTL:
                return None, None
            
            if check_config_file:
                current_api_key = _get_api_key_from_config()
                if current_api_key:
                    current_api_key_hash = _compute_api_key_hash(current_api_key)
                    if cached_hash and current_api_key_hash != cached_hash:
                        if debug:
                            print("⚠️ API key in config.json changed - clearing entity cache")
                        clear_entity_cache()
                        return None, None
            
            if api_key_hash and cached_hash:
                if cached_hash != api_key_hash:
                    return None, None
            
            # Validate cached values are proper strings
            if (cached_api_key_id and cached_subject and
                isinstance(cached_api_key_id, str) and
                isinstance(cached_subject, str) and
                len(cached_api_key_id.strip()) > 0 and
                len(cached_subject.strip()) > 0):
                return cached_api_key_id, cached_subject
            
            # Cache has invalid data
            return None, None
            
    except (OSError, ValueError, KeyError, TypeError):
        # File doesn't exist, corrupted, or invalid format
        return None, None

def clear_entity_cache():
    try:
        # Remove the separate cache file
        cache_file = "/lib/tendrl/entity_cache.json"
        import os
        try:
            os.remove(cache_file)
        except OSError:
            pass  # File doesn't exist
        return True
    except Exception as e:
        print(f"❌ Error clearing entity cache: {e}")
        return False
