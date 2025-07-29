from .utils.util_helpers import network_connect, ntp_time
from .utils.auth import get_claims


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

            claims = get_claims(
                self.config.get("app_url"),
                self.config.get("api_key"),
                self.config.get("e_type")
            )
            if claims is None:
                if self.debug:
                    print("Authentication claims retrieval failed")
                return None
            if claims and claims.get("jti"):
                if self.debug:
                    print("Authentication successful")
                return claims.get("jti")
            if self.debug:
                print("Authentication failed")
                print(claims.get('error'))
            return None
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
