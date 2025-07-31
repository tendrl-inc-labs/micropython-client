import json
import time

FROZEN_CONFIG_PATH = "/lib/tendrl/config.json"
USER_CONFIG_PATH = "/config.json"
USER_CONFIG_KEYS = ["api_key", "wifi_ssid", "wifi_pw", "reset", "api_key_id", "subject"]

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
            json.dump(existing_config, f, indent=2)
        return True
    except (OSError, ValueError) as e:
        print(f"Error saving config: {e}")
        return False


def update_config(api_key=None, wifi_ssid=None, wifi_pw=None, reset=None, api_key_id=None, subject=None):
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

def update_entity_cache(jti, sub):
    """Simplified function to update only entity cache (jti and subject)"""
    try:
        # Use a separate cache file to avoid touching user config
        cache_file = "/entity_cache.json"
        cache_data = {
            "api_key_id": jti,
            "subject": sub,
            "cached_at": time.time()
        }
        
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error updating entity cache: {e}")
        return False

def get_entity_cache():
    """Get cached entity info from separate cache file"""
    try:
        cache_file = "/entity_cache.json"
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            return cache_data.get("api_key_id"), cache_data.get("subject")
    except (OSError, ValueError):
        return None, None

def clear_entity_cache():
    try:
        # Remove the separate cache file
        cache_file = "/entity_cache.json"
        import os
        try:
            os.remove(cache_file)
        except OSError:
            pass  # File doesn't exist
        return True
    except Exception as e:
        print(f"Error clearing entity cache: {e}")
        return False





def create_default_config():
    """Create a default config.json if it doesn't exist or is corrupted"""
    default_config = {
        "tendrl_version": "0.1.0",
        "app_url": "https://app.tendrl.com",
        "api_key": "",
        "wifi_ssid": "",
        "wifi_pw": "",
        "reset": False,
        "mqtt_host": "mqtt.tendrl.com",
        "mqtt_port": 1883,
        "mqtt_ssl": False,
        "api_key_id": "",
        "subject": ""
    }
    
    try:
        with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        print("✅ Created default config.json")
        return True
    except Exception as e:
        print(f"❌ Failed to create default config: {e}")
        return False


def validate_and_fix_config():
    """Validate config and recreate if corrupted"""
    try:
        config = read_config()
        # Check if essential keys exist
        required_keys = ["api_key", "wifi_ssid", "wifi_pw", "mqtt_host", "mqtt_port"]
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"⚠️ Missing config keys: {missing_keys}")
            print("🔄 Recreating config...")
            return create_default_config()
        
        return True
    except Exception as e:
        print(f"❌ Config validation failed: {e}")
        print("🔄 Recreating config...")
        return create_default_config()
