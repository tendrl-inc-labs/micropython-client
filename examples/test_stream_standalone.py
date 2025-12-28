"""
Standalone JPEG Streaming Test Script

This script tests the streaming backend and frontend by directly
streaming JPEG frames from a camera without using the full client code.

Usage:
1. Set your API_KEY and APP_URL below
2. Run this script on your device with a camera
3. Open the entity detail page in the frontend to view the stream
"""

import socket
import ssl
import time

# Configuration - UPDATE THESE VALUES
API_KEY = "your_api_key_here"  # Your entity API key
APP_URL = "https://app.tendrl.com"  # Your app URL (or https://app.tendrl.com for dev)


# WiFi Configuration (if network interface needs to be activated)
WIFI_SSID = ""  # Leave empty if already connected, or set your WiFi SSID
WIFI_PASSWORD = ""  # Leave empty if already connected, or set your WiFi password

# Streaming settings
BOUNDARY = "tendrl"
CHUNK_SIZE = 4096
TARGET_FPS = 25
DEBUG = True

def extract_hostname_from_url(url):
    """Extract hostname from URL"""
    if "://" in url:
        url = url.split("://", 1)[1]
    if "/" in url:
        url = url.split("/", 1)[0]
    if ":" in url:
        url = url.split(":", 1)[0]
    return url

def send_all(sock, data):
    """Send all data through socket"""
    mv = memoryview(data) if isinstance(data, (bytes, bytearray)) else data
    sent = 0
    while sent < len(mv):
        n = sock.write(mv[sent:]) if hasattr(sock, "write") else sock.send(mv[sent:])
        if n:
            sent += n
    # For SSL sockets, we might need to ensure data is flushed
    # Note: MicroPython SSL sockets don't always support flush, so we'll just send

def send_jpeg_frame(sock, jpeg_data):
    """Send a single JPEG frame in multipart format"""
    header = (
        f"--{BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg_data)}\r\n"
        "\r\n"
    )
    send_all(sock, header.encode('utf-8'))

    # Send frame data in chunks
    mv = memoryview(jpeg_data)
    for i in range(0, len(mv), CHUNK_SIZE):
        chunk = mv[i:i + CHUNK_SIZE]
        send_all(sock, chunk)
        time.sleep_ms(1)  # Small yield between chunks

    send_all(sock, b"\r\n")

def create_stream_request(server_host, api_key):
    """Create HTTP request for streaming with Authorization header"""
    auth_header = f"Authorization: Bearer {api_key}\r\n" if api_key else ""

    CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    return (
        "POST /api/stream HTTP/1.1\r\n"
        f"Host: {server_host}\r\n"
        "Connection: keep-alive\r\n"  # Keep connection open for streaming
        f"Content-Type: multipart/x-mixed-replace; boundary={BOUNDARY}\r\n"
        f"Content-Length: {CONTENT_LENGTH}\r\n"
        f"{auth_header}"
        "\r\n"
    ).encode('utf-8')

def capture_frame():
    """Capture a frame from the camera"""
    import sensor
    img = sensor.snapshot()
    return img.bytearray()

def stream_loop():
    """Main streaming loop"""
    server_host = extract_hostname_from_url(APP_URL)
    port = 443
    frame_ms = 1000 // TARGET_FPS if TARGET_FPS > 0 else 40

    if DEBUG:
        print(f"Starting stream to {server_host}:{port}")
        print(f"Extracted hostname from '{APP_URL}': '{server_host}'")
        api_key_display = f"{API_KEY[:10]}..." if API_KEY and len(API_KEY) > 10 else "No API key!"
        print(f"API Key: {api_key_display}")

    while True:
        s = None
        try:
            # Check network connectivity and DNS configuration
            dns_configured = False
            try:
                import network
                wlan = network.WLAN(network.STA_IF)

                # Activate network interface if not active
                if not wlan.active():
                    if DEBUG:
                        print("Network interface not active - activating...")
                    wlan.active(True)
                    time.sleep_ms(500)  # Give it a moment to activate

                # Connect to WiFi if not connected and credentials provided
                if not wlan.isconnected():
                    if WIFI_SSID and WIFI_PASSWORD:
                        if DEBUG:
                            print(f"Connecting to WiFi: {WIFI_SSID}...")
                        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
                        # Wait for connection (up to 10 seconds)
                        max_wait = 10
                        while not wlan.isconnected() and max_wait > 0:
                            time.sleep(1)
                            max_wait -= 1
                            if DEBUG and max_wait % 2 == 0:
                                print(f"  Waiting for connection... ({max_wait}s)")
                    else:
                        if DEBUG:
                            print("Network interface active but not connected")
                            print("  To connect automatically, set WIFI_SSID and WIFI_PASSWORD in the script")
                            print("  Or connect manually before running the script")
                
                # Check connection status
                if wlan.isconnected():
                    config = wlan.ifconfig()
                    if DEBUG:
                        print(f"Network connected: IP={config[0]}, Netmask={config[1]}, Gateway={config[2]}, DNS={config[3]}")
                    
                    # Check if DNS is configured
                    if config[3] == '0.0.0.0' or not config[3]:
                        if DEBUG:
                            print("  WARNING: DNS server not configured! Attempting to configure...")
                        # Try to configure DNS automatically
                        try:
                            # Use Google DNS as fallback
                            new_config = (config[0], config[1], config[2], '8.8.8.8')
                            wlan.ifconfig(new_config)
                            # Verify it was set
                            updated_config = wlan.ifconfig()
                            if updated_config[3] == '8.8.8.8':
                                if DEBUG:
                                    print("  ✓ DNS configured to 8.8.8.8")
                                dns_configured = True
                            else:
                                if DEBUG:
                                    print(f"  ✗ Failed to configure DNS (still {updated_config[3]})")
                        except Exception as dns_err:
                            if DEBUG:
                                print(f"  ✗ Could not configure DNS automatically: {dns_err}")
                    else:
                        dns_configured = True
                        if DEBUG:
                            print(f"  ✓ DNS already configured: {config[3]}")
                else:
                    if DEBUG:
                        print("  ✗ Network not connected - DNS resolution will likely fail")
                        print("  Please connect to WiFi first or set WIFI_SSID/WIFI_PASSWORD")
            except ImportError:
                # Network module not available (not on MicroPython) - assume connected
                if DEBUG:
                    print("Network module not available, assuming connected")
                dns_configured = True  # Assume DNS works if we can't check
            except Exception as e:
                if DEBUG:
                    print(f"Network check error (continuing anyway): {e}")

            # Check if server_host is already an IP address
            is_ip = False
            try:
                # Try to parse as IP address
                parts = server_host.split('.')
                if len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts):
                    is_ip = True
                    addr = (server_host, port)
                    if DEBUG:
                        print(f"Using IP address directly: {addr}")
            except:
                pass
            
            # Resolve address if not already an IP
            if not is_ip:
                if DEBUG:
                    print(f"Resolving {server_host}:{port}...")
                
                addr = None
                try:
                    # Try IPv4 first (socket.AF_INET)
                    addr_info = socket.getaddrinfo(server_host, port, socket.AF_INET, socket.SOCK_STREAM)
                    if addr_info:
                        addr = addr_info[0][-1]
                        if DEBUG:
                            print(f"Resolved to IPv4: {addr}")
                except OSError as e1:
                    if DEBUG:
                        errno1 = e1.args[0] if e1.args else 'unknown'
                        print(f"IPv4 resolution failed: {e1} (errno: {errno1})")
                    
                    # Try without specifying address family (let system decide)
                    try:
                        addr_info = socket.getaddrinfo(server_host, port)
                        if addr_info:
                            addr = addr_info[0][-1]
                            if DEBUG:
                                print(f"Resolved (any family): {addr}")
                    except OSError as e2:
                        errno2 = e2.args[0] if e2.args else 'unknown'
                        if DEBUG:
                            print(f"DNS resolution error: {e2} (errno: {errno2})")
                            if errno2 == -6:
                                print("  -> EHOSTUNREACH: Host unreachable")
                                print("  -> Possible causes:")
                                print("     - DNS server not configured on device")
                                print("     - DNS server not reachable")
                                print("     - Device on different network than server")
                                print("  -> SOLUTIONS:")
                                print("     1. Configure DNS on device:")
                                print("        import network")
                                print("        wlan = network.WLAN(network.STA_IF)")
                                print("        ip, netmask, gateway, dns = wlan.ifconfig()")
                                print("        wlan.ifconfig((ip, netmask, gateway, '8.8.8.8'))")
                                print("     2. Use IP address instead of hostname in APP_URL")
                                print("     3. Check if device can reach the server network")
                        time.sleep_ms(5000)
                        continue
                    except Exception as e:
                        if DEBUG:
                            print(f"DNS resolution error: {e} (type: {type(e).__name__})")
                        time.sleep_ms(5000)
                        continue

                if not addr:
                    if DEBUG:
                        print(f"Failed to resolve {server_host} - no address returned")
                    time.sleep_ms(5000)
                    continue

            # Create socket
            s = socket.socket()

            if DEBUG:
                print(f"Connecting to {addr}...")

            try:
                s.connect(addr)
            except OSError as e:
                errno = e.args[0] if e.args else 'unknown'
                if DEBUG:
                    print(f"Connection error: {e} (errno: {errno})")
                if s:
                    try:
                        s.close()
                    except:
                        pass
                s = None
                time.sleep_ms(5000)
                continue
            except Exception as e:
                if DEBUG:
                    print(f"Connection error: {e} (type: {type(e).__name__})")
                if s:
                    try:
                        s.close()
                    except:
                        pass
                s = None
                time.sleep_ms(5000)
                continue

            # Wrap with TLS
            try:
                s = ssl.wrap_socket(s, server_hostname=server_host)
            except Exception as e:
                if DEBUG:
                    print(f"TLS handshake error: {e}")
                if s:
                    try:
                        s.close()
                    except:
                        pass
                s = None
                time.sleep_ms(5000)
                continue

            if DEBUG:
                print("Connected! Capturing first frame before sending request...")

            try:
                first_frame = capture_frame()
                if not first_frame or len(first_frame) == 0:
                    if DEBUG:
                        print("Warning: Empty first frame, will retry...")
                    time.sleep_ms(1000)
                    continue  # Retry connection
            except Exception as e:
                if DEBUG:
                    print(f"Error capturing first frame: {e}")
                time.sleep_ms(1000)
                continue  # Retry connection

            if DEBUG:
                print(f"First frame captured ({len(first_frame)} bytes). Sending stream request...")

            # Build first frame multipart data
            frame_header = (
                f"--{BOUNDARY}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(first_frame)}\r\n"
                "\r\n"
            ).encode('utf-8')

            request_headers = create_stream_request(server_host, API_KEY)
            complete_request = request_headers + frame_header + first_frame + b"\r\n"

            try:
                send_all(s, complete_request)
                if DEBUG:
                    print(f"✓ HTTP request + first frame sent successfully!")
            except Exception as e:
                if DEBUG:
                    print(f"Error sending request+frame: {e}")
                    if hasattr(e, 'errno'):
                        print(f"  Error code: {e.errno}")
                break

            # Stream remaining frames
            frame_count = 1  # First frame already sent
            while True:
                t0 = time.ticks_ms()

                # Capture next frame
                try:
                    jpeg_data = capture_frame()
                    if not jpeg_data or len(jpeg_data) == 0:
                        if DEBUG:
                            print("Warning: Empty frame captured")
                        time.sleep_ms(frame_ms)
                        continue
                except Exception as e:
                    if DEBUG:
                        print(f"Error capturing frame: {e}")
                    time.sleep_ms(frame_ms)
                    continue

                # Send frame
                try:
                    send_jpeg_frame(s, jpeg_data)
                    frame_count += 1

                    if DEBUG and frame_count % 30 == 0:
                        print(f"Sent {frame_count} frames")
                except Exception as e:
                    if DEBUG:
                        print(f"Error sending frame: {e}")
                        if hasattr(e, 'errno'):
                            print(f"  Error code: {e.errno}")
                    break

                # Frame pacing
                elapsed = time.ticks_diff(time.ticks_ms(), t0)
                delay = frame_ms - elapsed
                if delay > 0:
                    time.sleep_ms(delay)

        except OSError as e:
            if DEBUG:
                errno = e.args[0] if e.args else 'unknown'
                err_msg = {
                    -6: "EHOSTUNREACH - Host unreachable (network/DNS issue)",
                    -2: "ENOENT - Name or service not known (DNS resolution failed)",
                    -1: "EIO - I/O error",
                    -5: "EIO - I/O error",
                    110: "ETIMEDOUT - Connection timed out",
                    111: "ECONNREFUSED - Connection refused",
                }.get(errno, f"OSError {errno}")
                print(f"Stream error: {e} ({err_msg})")
        except Exception as e:
            if DEBUG:
                print(f"Stream error: {e} (type: {type(e).__name__})")

        finally:
            # Clean up socket if it was created
            try:
                if 's' in locals() and s is not None:
                    s.close()
            except:
                pass

        if DEBUG:
            print("Reconnecting in 5 seconds...")
        time.sleep_ms(5000)

# Setup camera if available
def setup_camera():
    """Setup camera settings"""
    try:
        import sensor
        sensor.reset()
        sensor.set_pixformat(sensor.JPEG)
        sensor.set_framesize(sensor.QVGA)  # 320x240
        sensor.set_quality(45)
        sensor.skip_frames(time=1500)
        if DEBUG:
            print("Camera initialized")
        return True
    except ImportError:
        if DEBUG:
            print("Camera module not available, using test frame")
        return False
    except Exception as e:
        if DEBUG:
            print(f"Camera setup error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Standalone JPEG Stream Test")
    print("=" * 50)
    print(f"Target: {APP_URL}")
    print(f"FPS: {TARGET_FPS}")
    print("=" * 50)

    # Validate configuration
    if API_KEY == "your_api_key_here" or not API_KEY:
        print("ERROR: Please set API_KEY in the script!")
        print("Edit the API_KEY variable at the top of this file.")
        exit(1)

    # Setup camera
    setup_camera()

    print("\nStarting stream...")
    print("Open the entity detail page in the frontend to view the stream.")
    print("Press Ctrl+C to stop.\n")

    try:
        stream_loop()
    except KeyboardInterrupt:
        print("\n\nStream stopped by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
