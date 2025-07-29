import json

FROZEN_CONFIG_PATH = "/lib/tendrl/config.json"
USER_CONFIG_PATH = "/config.json"
USER_CONFIG_KEYS = ["api_key", "wifi_ssid", "wifi_pw", "reset", "api_key_id", "subject"]

def read_config():
    user_config = {}
    try:
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config_content = f.read()
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
        user_config = {k: v for k, v in config.items() if k in USER_CONFIG_KEYS}
        with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(user_config, f, indent=2)
        return True
    except (OSError, ValueError) as e:
        print(f"Error saving config: {e}")
        return False


def update_config(api_key=None, wifi_ssid=None, wifi_pw=None, reset=None, api_key_id=None, subject=None):
    try:
        config = read_config()
        if api_key is not None:
            config["api_key"] = api_key
        if wifi_ssid is not None:
            config["wifi_ssid"] = wifi_ssid
        if wifi_pw is not None:
            config["wifi_pw"] = wifi_pw
        if reset is not None:
            config["reset"] = reset if isinstance(reset, bool) else False
        if api_key_id is not None:
            config["api_key_id"] = api_key_id
        if subject is not None:
            config["subject"] = subject

        return save_config(config)
    except Exception as e:
        print(f"Error updating config: {e}")
        return False


def clear_entity_cache():
    try:
        config = read_config()
        if "api_key_id" in config:
            del config["api_key_id"]
        if "subject" in config:
            del config["subject"]
        return save_config(config)
    except Exception as e:
        print(f"Error clearing entity cache: {e}")
        return False
