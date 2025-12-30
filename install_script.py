import json
import time
import os

import network
import mip

CONFIG_FILE = "/config.json"
LIBRARY_CONFIG_FILE = "/lib/tendrl/config.json"
CLIENT_REPO = "https://raw.githubusercontent.com/tendrl-inc-labs/micropython-client/main"
MAX_WIFI_RETRIES = 3
MAX_INSTALL_RETRIES = 3
WIFI_RETRY_DELAY = 5
INSTALL_RETRY_DELAY = 10

INSTALL_DB = True  # Set to False for minimal installation (no database)
INSTALL_STREAMING = False  # Set to True to include JPEG streaming support (adds ~35KB flash)

if INSTALL_DB:
    print("🗃️ Installing full Tendrl SDK with MicroTetherDB")
else:
    print("🗃️ Installing minimal Tendrl SDK (no database)")

if INSTALL_STREAMING:
    print("📹 Including JPEG streaming support")

INCLUDE_DB = INSTALL_DB
INCLUDE_STREAMING = INSTALL_STREAMING

def create_user_config_template():
    if not file_exists(CONFIG_FILE):
        template = {
            "api_key": "",
            "wifi_ssid": "",
            "wifi_pw": ""
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                formatted_json = "{\n \"api_key\": \"\",\n \"wifi_ssid\": \"\",\n \"wifi_pw\": \"\"\n}"
                f.write(formatted_json)
            print("✅ Created user config template at /config.json")
            print("⚠️ Please edit /config.json with your API key and WiFi credentials")
            print("📋 Note: API key ID and subject will be cached automatically after first connection")
        except Exception as e:
            print(f"❌ Failed to create user config template: {e}")
            return False
    return True

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load config file: {e}")
        raise RuntimeError(f"Failed to load config file: {e}")

def connect_wifi(ssid, password, timeout=10):
    wlan = None
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(False)
        time.sleep(1)
        wlan.active(True)
        time.sleep(1)

        if wlan.isconnected():
            wlan.disconnect()
            time.sleep(1)

        for attempt in range(MAX_WIFI_RETRIES):
            try:
                print(f"🌐 Attempt {attempt + 1}/{MAX_WIFI_RETRIES}: Connecting to Wi-Fi: {ssid} ...")
                wlan.connect(ssid, password)

                start = time.time()
                while not wlan.isconnected():
                    if time.time() - start > timeout:
                        raise RuntimeError("Wi-Fi connection timed out")
                    time.sleep(0.5)

                if wlan.isconnected():
                    print("✅ Connected:", wlan.ifconfig())
                    return True
                else:
                    raise RuntimeError("Connection failed")

            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if attempt < MAX_WIFI_RETRIES - 1:
                    print(f"⏳ Waiting {WIFI_RETRY_DELAY} seconds before retrying...")
                    time.sleep(WIFI_RETRY_DELAY)
                else:
                    print("❌ All WiFi connection attempts failed")
                    return False

    except Exception as e:
        print(f"❌ WiFi setup failed: {e}")
        return False
    finally:
        if wlan and not wlan.isconnected():
            try:
                wlan.disconnect()
                wlan.active(False)
            except:
                pass

    return False

def file_exists(path):
    try:
        with open(path, 'r'):
            return True
    except:
        return False

def verify_installation():
    try:
        required_files = [
            "/lib/tendrl/__init__.py",
            "/lib/tendrl/client.py",
            "/lib/tendrl/config_manager.py",
            "/lib/tendrl/network_manager.py",
            "/lib/tendrl/queue_manager.py",
            "/lib/tendrl/mqtt_handler.py",
            "/lib/tendrl/lib/shutil.py",
            "/lib/tendrl/utils/__init__.py",
            "/lib/tendrl/utils/auth.py",
            "/lib/tendrl/utils/util_helpers.py",
            "/lib/tendrl/manifest.py",
            "/lib/tendrl/config.json"
        ]

        if INCLUDE_DB:
            db_files = [
                "/lib/tendrl/lib/microtetherdb/__init__.py",
                "/lib/tendrl/lib/microtetherdb/db.py",
                "/lib/tendrl/lib/microtetherdb/core/__init__.py",
                "/lib/tendrl/lib/microtetherdb/core/exceptions.py",
                "/lib/tendrl/lib/microtetherdb/core/flush_manager.py",
                "/lib/tendrl/lib/microtetherdb/core/future.py",
                "/lib/tendrl/lib/microtetherdb/core/key_generator.py",
                "/lib/tendrl/lib/microtetherdb/core/memory_file.py",
                "/lib/tendrl/lib/microtetherdb/core/query_engine.py",
                "/lib/tendrl/lib/microtetherdb/core/ttl_manager.py",
                "/lib/tendrl/lib/microtetherdb/core/utils.py"
            ]
            required_files.extend(db_files)

        if INCLUDE_STREAMING:
            streaming_files = [
                "/lib/tendrl/streaming.py"
            ]
            required_files.extend(streaming_files)

        for file in required_files:
            if not file_exists(file):
                print(f"❌ Required file not found: {file}")
                return False

        return True
    except Exception as e:
        print(f"❌ Error verifying installation: {e}")
        return False

def ensure_directory_exists(path):
    try:
        os.mkdir(path)
    except:
        pass

def create_library_config():
    try:
        if file_exists(LIBRARY_CONFIG_FILE):
            print("✅ Library config already exists at /lib/tendrl/config.json")
            return True

        ensure_directory_exists("/lib/tendrl")

        formatted_json = "{\n  \"tendrl_version\": \"0.1.0\",\n  \"app_url\": \"https://app.tendrl.com\",\n  \"api_key\": \"\",\n  \"wifi_ssid\": \"\",\n  \"wifi_pw\": \"\",\n  \"reset\": false,\n  \"mqtt_host\": \"mqtt.tendrl.com\",\n  \"mqtt_port\": 1883,\n  \"mqtt_ssl\": false\n}"

        with open(LIBRARY_CONFIG_FILE, 'w') as f:
            f.write(formatted_json)
        print("✅ Created library config at /lib/tendrl/config.json")
        return True
    except Exception as e:
        print(f"❌ Failed to create library config: {e}")
        return False

def ensure_required_directories():
    try:
        ensure_directory_exists("/lib")
        ensure_directory_exists("/lib/tendrl")
        ensure_directory_exists("/lib/tendrl/lib")

        if INCLUDE_DB:
            ensure_directory_exists("/lib/tendrl/lib/microtetherdb")
            ensure_directory_exists("/lib/tendrl/lib/microtetherdb/core")

        print("✅ Verified required directories")
        return True
    except Exception as e:
        print(f"❌ Failed to create required directories: {e}")
        return False

def install_tendrl():
    for attempt in range(MAX_INSTALL_RETRIES):
        try:
            if INCLUDE_DB:
                print(f"⬇️ Attempt {attempt + 1}/{MAX_INSTALL_RETRIES}: Installing full Tendrl SDK...")
            else:
                print(f"⬇️ Attempt {attempt + 1}/{MAX_INSTALL_RETRIES}: Installing minimal Tendrl SDK...")

            if not ensure_required_directories():
                raise RuntimeError("Failed to create required directories")

            if INCLUDE_DB:
                mip.install("github:tendrl-inc-labs/micropython-client/package.json", target="/lib")
            else:
                mip.install("github:tendrl-inc-labs/micropython-client/package-minimal.json", target="/lib")

            # Install streaming module if requested
            if INCLUDE_STREAMING:
                print("📹 Installing JPEG streaming module...")
                mip.install("github:tendrl-inc-labs/micropython-client/package-streaming.json", target="/lib")

            if not create_library_config():
                raise RuntimeError("Failed to create library config")

            if verify_installation():
                if INCLUDE_DB:
                    print("✅ Full Tendrl SDK installed and verified successfully")
                    print("📊 Includes MicroTetherDB for local data storage")
                else:
                    print("✅ Minimal Tendrl SDK installed and verified successfully")
                    print("⚠️ Note: Local database features disabled (client_db=False required)")
                return True
            else:
                raise RuntimeError("Installation verification failed")

        except Exception as e:
            print(f"❌ Installation attempt {attempt + 1} failed: {e}")
            if attempt < MAX_INSTALL_RETRIES - 1:
                print(f"⏳ Waiting {INSTALL_RETRY_DELAY} seconds before retrying...")
                time.sleep(INSTALL_RETRY_DELAY)
            else:
                print("❌ All installation attempts failed")
                return False
    return False

def main():
    try:
        if not file_exists(CONFIG_FILE):
            print("⚠️ User config not found")
            if not create_user_config_template():
                print("❌ Failed to create user config template")
                return
            print("Required fields:")
            print("  - wifi_ssid: Your WiFi network name")
            print("  - wifi_pw: Your WiFi password")
            print("\nAfter filling in these details, run this script again.")
            return

        config = load_config()

        ssid = config.get("wifi_ssid")
        pw = config.get("wifi_pw")
        if not ssid or not pw:
            print("⚠️ Missing Wi-Fi credentials in config.json")
            print("Please edit /config.json with your WiFi credentials and API key")
            return

        if not ensure_required_directories():
            print("❌ Failed to create required directories")
            return

        if not connect_wifi(ssid, pw):
            print("❌ Failed to establish WiFi connection after all retries")
            return

        if not install_tendrl():
            print("❌ Failed to install tendrl after all retries")
            return

        print("✨ Installation completed successfully!")
        if INCLUDE_DB:
            print("📊 MicroTetherDB is available for local data storage")
            print("💡 Use client_db=True in Client() constructor (default)")
        else:
            print("⚠️ MicroTetherDB not installed - use client_db=False in Client() constructor")
            print("💡 This saves ~50KB flash space but disables local database features")
        if INCLUDE_STREAMING:
            print("📹 JPEG streaming module installed")
            print("💡 Use client.start_streaming() for camera streaming")
        else:
            print("💡 To enable JPEG streaming, set INSTALL_STREAMING=True in install_script.py")
            print("   Streaming adds ~35KB flash storage and works with both minimal and full installations")
        print("⚠️ If you haven't already, please edit /config.json with your API key")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return

if __name__ == "__main__":
    main()
