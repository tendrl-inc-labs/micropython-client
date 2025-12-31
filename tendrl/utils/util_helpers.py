def iso8601(timestamp=None):
    import time
    if timestamp is None:
        timestamp = time.gmtime()
    # Use f-string instead of .format() for better performance in MicroPython
    return f"{timestamp[0]:04d}-{timestamp[1]:02d}-{timestamp[2]:02d}T{timestamp[3]:02d}:{timestamp[4]:02d}:{timestamp[5]:02d}Z"

def parse_iso8601(iso8601_str):
    import time
    if not iso8601_str:
        return 0
    try:
        iso8601_str = iso8601_str.rstrip("Z")
        year, month, day = map(int, iso8601_str[0:10].split("-"))
        hour, minute, second = map(int, iso8601_str[11:].split(":"))
        return int(time.mktime((year, month, day, hour, minute, second, 0, 0, 0)))
    except Exception as e:
        print(f"Error parsing ISO8601 time: {e}")
        return 0

def make_message(
    data,
    msg_type,
    tags=None,
    entity="",
    timestamp=None,
):
    import time
    if not isinstance(data, (str, dict)):
        raise TypeError("Allowed types: ['str', 'dict']")
    if not tags:
        tags = []
    else:
        if not all(isinstance(i, str) for i in tags):
            raise TypeError("tags must be of type 'str'")
    # Build message dict efficiently - only include non-empty values
    # Avoid dict comprehension overhead by building conditionally
    m = {"msg_type": msg_type, "data": data}
    if tags:
        m["context"] = {"tags": tags}
    if entity:
        m["dest"] = entity
    m["timestamp"] = iso8601(timestamp if timestamp else time.gmtime())
    return m

def get_wifi_status(station):
    import network

    status_map = {
        network.STAT_IDLE: "Idle",
        network.STAT_CONNECTING: "Connecting",
        network.STAT_GOT_IP: "Connected",
        network.STAT_WRONG_PASSWORD: "Wrong Password",
        network.STAT_NO_AP_FOUND: "No Access Point",
        network.STAT_ASSOC_FAIL: "Association Failed",
        network.STAT_BEACON_TIMEOUT: "Beacon Timeout",
        network.STAT_HANDSHAKE_TIMEOUT: "Handshake Timeout",
        network.STAT_NO_AP_FOUND_IN_AUTHMODE_THRESHOLD: "No AP in Auth Mode Threshold",
        network.STAT_NO_AP_FOUND_IN_RSSI_THRESHOLD: "No AP in RSSI Threshold",
        network.STAT_NO_AP_FOUND_W_COMPATIBLE_SECURITY: "No Compatible Security AP",
    }
    try:
        if hasattr(station, "status"):
            status = station.status()
            return status_map.get(status)
        return "Unknown WiFi Status"
    except Exception as e:
        print(f"Error getting connection status: {e}", "ERROR")
        return "Status Error"

def get_mac(sta):
    import binascii
    m = binascii.hexlify(sta.config("mac")).decode()
    return ":".join(m[i : i + 2] for i in range(0, 12, 2))

def convert(num):
    units = [
        (1 << 30, "GB"),
        (1 << 20, "MB"),
        (1 << 10, "KB"),
        (1, ("byte", "bytes")),
    ]
    for factor, suffix in units:
        if num >= factor:
            break
    amount = round(num / factor, 2)
    if isinstance(suffix, tuple):
        singular, multiple = suffix
        if amount == 1:
            suffix = singular
        else:
            suffix = multiple
    return [amount, suffix]

def starmap(function, iterable):
    for args in iterable:
        yield function(*args)

def ntp_time(retry=0):
    import time

    if retry < 4:
        try:
            import ntptime
            ntptime.settime()
        except OSError:
            retry += 1
            time.sleep(1)
            ntp_time(retry)

def network_connect(ssid, password, max_retries=3, retry=0, debug=False):
    import network
    import time

    try:
        station = network.WLAN(network.STA_IF)
        station.active(True)
        if retry < max_retries:
            station.connect(ssid, password)
            time.sleep(1.5)
            if station.isconnected():
                if debug:
                    print("WiFi Status: ", get_wifi_status(station))
                return station
            if debug:
                print("WiFi Status: ", get_wifi_status(station))
            retry += 1
            if debug:
                print("Retrying WiFi Connection...")
            return network_connect(ssid, password, retry=retry, debug=debug)
        return station
    except OSError as e:
        if e == "WiFi Internal Error":
            if debug:
                print("Unable to connect to WiFi")
        return station
    except AttributeError:
        return station
    except KeyboardInterrupt:
        if station:
            station.disconnect()
            station.active(False)

def network_scan(station=None):
    import network

    if station:
        station.disconnect()
    else:
        station = network.WLAN(network.STA_IF)
    station.active(True)
    network_list = []
    a_mode = ("open", "WEP", "WPA-PSK", "WPA2-PSK", "WPA/WPA2-PSK")
    for signal in station.scan():
        rssi = signal[3]
        if -67 <= rssi <= 0:
            s = 4
        elif -70 <= rssi <= -68:
            s = 3
        elif -76 <= rssi <= -71:
            s = 2
        elif -82 <= rssi <= -77:
            s = 1
        else:
            s = 0
        network_list.append(
            {
                "ssid": signal[0].decode(),
                "signal_strength": s,
                "hidden": bool(signal[5]),
                "auth_mode": a_mode[signal[4]],
                "channel": signal[2],
            }
        )
    return network_list

def t_convert(t):
    if t < 1000:
        return f"{round(t, 1)} Milliseconds"
    if 1000 <= t <= 60000:
        return f"{round((t / 1000), 1)} Seconds"
    return f"{round((t / 60000), 1)} Minutes"

def is_openmv():
    """
    Detect if running on an OpenMV board.
    Uses sys.implementation._machine to check for 'OpenMV' string.
    """
    try:
        import sys
        return 'OpenMV' in sys.implementation._machine
    except (AttributeError, ImportError):
        return False

def free(bytes_only=False):
    import gc
    import os

    gc.collect()

    mem_free = gc.mem_free()
    mem_used = gc.mem_alloc()
    mem_total = mem_free + mem_used

    # Use correct root directory based on platform
    # OpenMV uses /flash, regular MicroPython uses /
    root_dir = "/flash" if is_openmv() else "/"
    fs_stat = os.statvfs(root_dir)
    block_size = fs_stat[0]
    total_blocks = fs_stat[2]
    free_blocks = fs_stat[3]
    fs_size = block_size * total_blocks
    fs_free = block_size * free_blocks

    if bytes_only:
        return {
            "mem_free": mem_free,
            "mem_total": mem_total,
            "disk_free": fs_free,
            "disk_size": fs_size,
        }
    else:
        return {
            "mem_free": convert(mem_free),
            "mem_total": convert(mem_total),
            "disk_free": convert(fs_free),
            "disk_size": convert(fs_size),
        }

def gen_key():
    import binascii
    import os

    return binascii.hexlify(os.urandom(16))

def encrypt_str(data, key):
    import cryptolib

    aes = cryptolib.aes
    return aes(key, 1).encrypt(
        data.encode("utf-8") + (b"\x00" * ((16 - (len(data) % 16)) % 16))
    )


def decrypt_str(data, key):
    import cryptolib

    aes = cryptolib.aes
    return aes(key, 1).decrypt(data).decode().split("\x00")[0]

def hash_dir(dir_path):
    import binascii
    import hashlib
    import os

    ilist = os.ilistdir
    hxly = binascii.hexlify
    sha1 = hashlib.sha1
    for file in ilist(dir_path):
        if file[1] == 32768:
            print(f"Filename: {file[0]}")
            try:
                with open(file[0], "rb") as f:
                    f_hash = hxly(sha1(f.read()).digest())
                    print(f"File Hash: {f_hash}\n")
            except OSError as e:
                print(e)

def hash_check(file_hash, filepath):
    import hashlib

    with open(filepath, "rb") as f:
        if hashlib.sha1(f.read()) == file_hash:
            return True

def safe_storage_operation(storage, operation, *args, **kwargs):
    if storage is None:
        print("CRITICAL: Storage is None, cannot perform operation")
        return None
    try:
        if operation == "ttl_cleanup":
            return storage.cleanup()
        method = getattr(storage, operation)
        result = method(*args, **kwargs)

        return result
    except AttributeError as e:
        print(f"CRITICAL: Storage method '{operation}' not found: {e}")
        return None
    except Exception as e:
        print(f"CRITICAL: Storage operation '{operation}' failed")
        print(f"Arguments: {args}")
        print(f"Keyword Arguments: {kwargs}")
        print(f"Error details: {type(e).__name__}: {e}")
        return None

def retrieve_offline_messages(storage, debug=False):
    try:
        offline_messages = safe_storage_operation(storage, "query", {"limit": 10})
        if not offline_messages:
            return []
        messages = [
            msg.get("data")
            for msg in offline_messages
            if "data" in msg and isinstance(msg.get("data"), dict)
        ]
        if debug:
            print(f"Retrieved {len(messages)} offline messages from storage")
        return messages
    except Exception as e:
        if debug:
            print(f"CRITICAL: Error retrieving offline messages: {e}")
        return []

def send_offline_messages(mqtt_handler, messages, max_batch_size=10, debug=False):
    sent_count = 0
    for i in range(0, len(messages), max_batch_size):
        batch = messages[i : i + max_batch_size]
        try:
            if debug:
                print(
                    f"Attempting to send offline message batch of {len(batch)} messages"
                )
            success = mqtt_handler.send_batch(batch)
            if success:
                sent_count += len(batch)
                if debug:
                    print(f"Successfully sent {len(batch)} offline messages")
            else:
                if debug:
                    print("Batch send failed")
                break
        except Exception as e:
            if debug:
                print(f"Error sending offline batch: {e}")
            break
    if debug:
        print(f"Total offline messages sent: {sent_count}")
    return sent_count
