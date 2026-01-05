from .utils.util_helpers import network_connect, ntp_time


class NetworkManager:
    def __init__(self, config, debug=False, headless=False, net_type="wifi"):
        self._station = None
        self.config = config
        self.debug = debug
        self.headless = headless
        self.net_type = net_type.lower()  # Normalize to lowercase

    def connect(self):
        try:
            if not self.headless:
                if self.net_type == "eth":
                    # Ethernet connection - no SSID/password needed
                    self._station = network_connect(
                        ssid="",  # Not used for ethernet
                        password="",  # Not used for ethernet
                        debug=self.debug,
                        net_type="eth"
                    )
                else:
                    # WiFi connection (default)
                    self._station = network_connect(
                        ssid=self.config["wifi_ssid"],
                        password=self.config["wifi_pw"],
                        debug=self.debug,
                        net_type="wifi"
                    )
                
                if not self._station or not self._station.isconnected():
                    if self.debug:
                        print("Failed to establish network connection")
                    return None
                try:
                    ntp_time()
                except Exception as ntp_err:
                    if self.debug:
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
                if self.net_type == "eth":
                    # Ethernet: just deactivate
                    self._station.active(False)
                else:
                    # WiFi: disconnect and deactivate
                    self._station.disconnect()
                    self._station.active(False)
            except Exception:
                pass
            finally:
                self._station = None
