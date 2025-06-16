"""

This script handles the installation of the Tendrl library and configuration setup.

The installation process involves two configuration files:

1. Library Config (/lib/tendrl/config.json):
   - Contains default library settings
   - Installed automatically with the library
   - Should not be modified by users
   - Includes tendrl_version and app_url

2. User Config (/config.json):
   - Contains user-specific settings
   - Created automatically if it doesn't exist
   - Must be edited with your credentials:
     {
        "api_key": "<your-entity-api-key>",
        "wifi_ssid": "<your-wifi-network>",
        "wifi_pw": "<your-wifi-password>"
     }

The script will create a template for the user config if it doesn't exist.
You must edit this file with your actual credentials before the library will work.

Installation Options:
- Full installation: Set INSTALL_DB = True (default) - includes MicroTetherDB
- Minimal installation: Set INSTALL_DB = False - excludes MicroTetherDB (saves ~50KB)

Usage:
1. Edit the INSTALL_DB variable below to choose installation type
2. Run: exec(open("install_script.py").read())
"""

import json
import time
import os

import network
import mip


"""

This script requires this below example file saved in the root of the device
as config.json

{
    "api_key": "<entity-api-key-will-go-here>",
    "wifi_ssid": "<wifi-ssid>",
    "wifi_pw": "<wifi-password>"
}
"""

CONFIG_FILE = "/config.json"
LIBRARY_CONFIG_FILE = "/lib/tendrl/config.json"
CLIENT_REPO = "https://raw.githubusercontent.com/tendrl-inc-labs/micropython-client/main"
MAX_WIFI_RETRIES = 3
MAX_INSTALL_RETRIES = 3
WIFI_RETRY_DELAY = 5  # seconds
INSTALL_RETRY_DELAY = 10  # seconds

# Configuration - Modify this before running the script
INSTALL_DB = True  # Set to False for minimal installation (saves ~50KB)

# Print installation type
if INSTALL_DB:
    print("🗃️ Installing full Tendrl SDK with MicroTetherDB")
else:
    print("🗃️ Installing minimal Tendrl SDK (no database)")

# Use the INSTALL_DB variable for the rest of the script
INCLUDE_DB = INSTALL_DB

def create_user_config_template():
    """Create a template user config file if it doesn't exist."""
    if not file_exists(CONFIG_FILE):
        template = {
            "api_key": "",
            "wifi_ssid": "",
            "wifi_pw": ""
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                # Format JSON with specific indentation
                formatted_json = "{\n \"api_key\": \"\",\n \"wifi_ssid\": \"\",\n \"wifi_pw\": \"\"\n}"
                f.write(formatted_json)
            print("✅ Created user config template at /config.json")
            print("⚠️ Please edit /config.json with your WiFi credentials")
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
        wlan.active(False)  # First ensure it's inactive
        time.sleep(1)  # Give it time to fully deactivate
        wlan.active(True)  # Then activate it
        time.sleep(1)  # Give it time to fully activate

        # Disconnect if already connected
        if wlan.isconnected():
            wlan.disconnect()
            time.sleep(1)

        for attempt in range(MAX_WIFI_RETRIES):
            try:
                print(f"🌐 Attempt {attempt + 1}/{MAX_WIFI_RETRIES}: Connecting to Wi-Fi: {ssid} ...")
                wlan.connect(ssid, password)

                # Wait for connection with timeout
                start = time.time()
                while not wlan.isconnected():
                    if time.time() - start > timeout:
                        raise RuntimeError("Wi-Fi connection timed out")
                    time.sleep(0.5)

                # Double check we're actually connected
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
        # Cleanup if we failed
        if wlan and not wlan.isconnected():
            try:
                wlan.disconnect()
                wlan.active(False)
            except:
                pass

    return False

def file_exists(path):
    """Check if a file exists using MicroPython's file system functions."""
    try:
        with open(path, 'r'):
            return True
    except:
        return False

def verify_installation():
    """Verify that tendrl was installed correctly by checking for key files."""
    try:
        # Check for core required files (included in both full and minimal)
        required_files = [
            "/lib/tendrl/__init__.py",
            "/lib/tendrl/client.py",
            "/lib/tendrl/config_manager.py",
            "/lib/tendrl/network_manager.py",
            "/lib/tendrl/queue_manager.py",
            "/lib/tendrl/websocket_handler.py",
            "/lib/tendrl/lib/shutil.py",
            "/lib/tendrl/lib/websockets.py",
            "/lib/tendrl/utils/__init__.py",
            "/lib/tendrl/utils/auth.py",
            "/lib/tendrl/utils/memory.py",
            "/lib/tendrl/utils/util_helpers.py",
            "/lib/tendrl/manifest.py",
            "/lib/tendrl/config.json"
        ]

        # Add database files only if database was included
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

        for file in required_files:
            if not file_exists(file):
                print(f"❌ Required file not found: {file}")
                return False

        return True
    except Exception as e:
        print(f"❌ Error verifying installation: {e}")
        return False

def ensure_directory_exists(path):
    """Create directory if it doesn't exist."""
    try:
        os.mkdir(path)
    except:
        pass

def create_library_config():
    """Create the library config file with default settings if it doesn't exist."""
    try:
        # Check if config already exists
        if file_exists(LIBRARY_CONFIG_FILE):
            print("✅ Library config already exists at /lib/tendrl/config.json")
            return True

        # Ensure the directory exists
        ensure_directory_exists("/lib/tendrl")

        # Create the library config with all required fields
        formatted_json = "{\n  \"app_url\": \"https://app.tendrl.com\",\n  \"wifi_pw\": \"\",\n  \"wifi_ssid\": \"\",\n  \"tendrl_version\": \"0.1.0\",\n  \"api_key\": \"\",\n  \"reset\": false\n}"

        with open(LIBRARY_CONFIG_FILE, 'w') as f:
            f.write(formatted_json)
        print("✅ Created library config at /lib/tendrl/config.json")
        return True
    except Exception as e:
        print(f"❌ Failed to create library config: {e}")
        return False

def ensure_required_directories():
    """Create all required directories for the installation."""
    try:
        # Create /lib directory if it doesn't exist
        ensure_directory_exists("/lib")

        # Create /lib/tendrl directory if it doesn't exist
        ensure_directory_exists("/lib/tendrl")

        # Create /lib/tendrl/lib directory if it doesn't exist
        ensure_directory_exists("/lib/tendrl/lib")

        # Only create MicroTetherDB directories for full installation
        if INCLUDE_DB:
            # Create /lib/tendrl/lib/microtetherdb directory if it doesn't exist
            ensure_directory_exists("/lib/tendrl/lib/microtetherdb")
            # Create /lib/tendrl/lib/microtetherdb/core directory if it doesn't exist
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

            # Ensure all required directories exist
            if not ensure_required_directories():
                raise RuntimeError("Failed to create required directories")

            # Install using appropriate package.json
            if INCLUDE_DB:
                # Full installation with database
                mip.install("github:tendrl-inc-labs/micropython-client/package.json", target="/lib")
            else:
                # Minimal installation without database
                mip.install("github:tendrl-inc-labs/micropython-client/package-minimal.json", target="/lib")

            # Create the library config file
            if not create_library_config():
                raise RuntimeError("Failed to create library config")

            # Verify the installation
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
        # Check for user config first
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

        # Load user config
        config = load_config()

        # Verify required fields are filled
        ssid = config.get("wifi_ssid")
        pw = config.get("wifi_pw")
        if not ssid or not pw:
            print("⚠️ Missing Wi-Fi credentials in config.json")
            print("Please edit /config.json with your WiFi credentials and API key")
            return

        # Ensure all required directories exist
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
        print("⚠️ If you haven't already, please edit /config.json with your API key")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return

if __name__ == "__main__":
    main()
