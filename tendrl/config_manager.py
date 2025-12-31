import json
import time
import os

# Import OpenMV detection from utils
from .utils.util_helpers import is_openmv

def get_root_dir():
    """
    Detect the root directory for the filesystem.
    OpenMV uses /flash, regular MicroPython uses /.
    """
    # Use proper OpenMV detection instead of checking for /flash directory
    if is_openmv():
        return "/flash"
    else:
        return "/"

# Get root directory once at module load
_ROOT_DIR = get_root_dir()

FROZEN_CONFIG_PATH = f"{_ROOT_DIR}/lib/tendrl/config.json"
USER_CONFIG_PATH = f"{_ROOT_DIR}/config.json"
USER_CONFIG_KEYS = ["api_key", "wifi_ssid", "wifi_pw", "reset"]

def read_config():
    user_config = {}
    try:
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config_content = f.read()
            if user_config_content.strip():  # Only try to parse if file has content
                user_config = json.loads(user_config_content)
    except (OSError, ValueError) as e:
        print(f"Error reading user config: {e}")
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
        # Read existing config first
        try:
            with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                existing_config = json.load(f)
        except (OSError, ValueError):
            existing_config = {}

        # Update only specific keys
        user_config = {k: v for k, v in config.items() if k in USER_CONFIG_KEYS}

        # Preserve existing values if not explicitly set
        for key, value in user_config.items():
            if value is not None and value != "":
                existing_config[key] = value

        # Write back the updated config
        with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_config, f)
        return True
    except (OSError, ValueError) as e:
        print(f"Error saving config: {e}")
        return False


def update_config(api_key_id="", subject=""):
    try:
        config = read_config()

        # Only update entity claims (jti and subject) - don't touch main user config
        if api_key_id is not None:
            config["api_key_id"] = api_key_id
        if subject is not None:
            config["subject"] = subject

        return save_config(config)
    except Exception as e:
        print(f"Error updating config: {e}")
        return False

def update_entity_cache(api_key_id="", subject=""):
    """Simplified function to update only entity cache (jti and subject)"""
    try:
        # Use a separate cache file to avoid touching user config
        cache_file = f"{_ROOT_DIR}/lib/tendrl/entity_cache.json"
        cache_data = {
            "api_key_id": api_key_id,
            "subject": subject,
            "cached_at": time.time()
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        return True
    except Exception as e:
        print(f"Error updating entity cache: {e}")
        return False

def get_entity_cache():
    """Get cached entity info from separate cache file"""
    try:
        cache_file = f"{_ROOT_DIR}/lib/tendrl/entity_cache.json"
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            return cache_data.get("api_key_id"), cache_data.get("subject")
    except (OSError, ValueError):
        return None, None

def clear_entity_cache():
    try:
        # Remove the separate cache file
        cache_file = f"{_ROOT_DIR}/lib/tendrl/entity_cache.json"
        try:
            os.remove(cache_file)
        except OSError:
            pass  # File doesn't exist
        return True
    except Exception as e:
        print(f"Error clearing entity cache: {e}")
        return False
