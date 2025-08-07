from .utils.util_helpers import network_connect, ntp_time


class NetworkManager:
    def __init__(self, config, debug=False, headless=False):
        self._station = None
        self.config = config
        self.debug = debug
        self.headless = headless

    def connect(self):
        try:
            if not self.headless:
                wlan = network_connect(
                    ssid=self.config["wifi_ssid"],
                    password=self.config["wifi_pw"],
                    debug=self.debug,
                )
                if not wlan.isconnected():
                    if self.debug:
                        print("Failed to establish network connection")
                    return None
                try:
                    ntp_time()
                except Exception as ntp_err:
                    print(f"NTP time sync failed: {ntp_err}")

            # Network connection successful
            if self.debug:
                print("Network connection established")
            return True
        except Exception as e:
            if self.debug:
                print(f"Unexpected connection error: {e}")
            return None

    def is_connected(self):
        if self.headless:
            return True
        return self._station and self._station.isconnected()

    def cleanup(self):
        if not self.headless and self._station:
            try:
                self._station.disconnect()
                self._station.active(False)
            except Exception:
                pass
            finally:
                self._station = None
