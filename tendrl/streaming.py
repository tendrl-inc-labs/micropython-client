def send_all(sock, data):
    mv = memoryview(data)
    sent = 0
    while sent < len(mv):
        n = sock.write(mv[sent:]) if hasattr(sock, "write") else sock.send(mv[sent:])
        if n:
            sent += n

def send_bytes_chunked(sock, data, chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    import time
    if len(data) < yield_every_bytes:
        send_all(sock, data)
        return

    mv = memoryview(data)
    sent_since_yield = 0

    for i in range(0, len(mv), chunk_size):
        chunk = mv[i:i + chunk_size]
        send_all(sock, chunk)
        sent_since_yield += len(chunk)

        # Yield less frequently - H7/RT1062 can handle larger sends
        if sent_since_yield >= yield_every_bytes:
            sent_since_yield = 0
            time.sleep_ms(yield_ms)

async def send_bytes_chunked_async(sock, data, chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    try:
        import asyncio
    except ImportError:
        # Fallback to sync version if asyncio not available
        send_bytes_chunked(sock, data, chunk_size, yield_every_bytes, yield_ms)
        return
    
    if len(data) < yield_every_bytes:
        send_all(sock, data)
        return

    mv = memoryview(data)
    sent_since_yield = 0

    for i in range(0, len(mv), chunk_size):
        chunk = mv[i:i + chunk_size]
        send_all(sock, chunk)
        sent_since_yield += len(chunk)

        # Yield to event loop periodically - allows other tasks to run
        if sent_since_yield >= yield_every_bytes:
            sent_since_yield = 0
            await asyncio.sleep(yield_ms / 1000.0)
        elif i + chunk_size < len(mv):
            # Also yield briefly between chunks for very large frames
            await asyncio.sleep(0)  # Yield to event loop

BOUNDARY = "tendrl"

def send_jpeg_frame(sock, jpeg_data, chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    header = (
        f"--{BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg_data)}\r\n"
        "\r\n"
    )
    send_all(sock, header)
    send_bytes_chunked(sock, jpeg_data, chunk_size, yield_every_bytes, yield_ms)
    send_all(sock, "\r\n")

async def send_jpeg_frame_async(sock, jpeg_data, chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    header = (
        f"--{BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg_data)}\r\n"
        "\r\n"
    )
    send_all(sock, header)
    await send_bytes_chunked_async(sock, jpeg_data, chunk_size, yield_every_bytes, yield_ms)
    send_all(sock, "\r\n")

def create_stream_request(server_host):
    return (
        "POST /stream HTTP/1.1\r\n"
        f"Host: {server_host}\r\n"
        "Connection: close\r\n"
        f"Content-Type: multipart/x-mixed-replace; boundary={BOUNDARY}\r\n"
        "\r\n"
    )


def _extract_hostname_from_url(url):
    """Extract hostname from URL (e.g., https://app.tendrl.com -> app.tendrl.com)"""
    # Remove protocol
    if "://" in url:
        url = url.split("://", 1)[1]
    # Remove path if present
    if "/" in url:
        url = url.split("/", 1)[0]
    # Remove port if present
    if ":" in url:
        url = url.split(":", 1)[0]
    return url


def jpeg_stream(client_instance, chunk_size=4096, yield_every_bytes=32*1024,
                yield_ms=1, target_fps=25, gc_interval=1024,
                reconnect_delay=5000, yield_interval=10, debug=False):

    import socket
    import ssl
    import time
    import gc

    try:
        import asyncio
        ASYNCIO_AVAILABLE = True
    except ImportError:
        ASYNCIO_AVAILABLE = False

    # Get server hostname from client config (always use TLS, port 443)
    app_url = client_instance.config.get("app_url", "https://app.tendrl.com")
    server_host = _extract_hostname_from_url(app_url)
    port = 443  # Always use TLS
    use_tls = True  # Always use TLS

    frame_ms = 1000 // target_fps if target_fps > 0 else 0

    def wrapper(func):
        async def stream_loop(*args, **kwargs):
            """Async stream loop that yields control periodically"""
            s = None
            while True:
                try:
                    # Ensure network connection
                    if not client_instance.network.connect():
                        if debug:
                            print("Failed to connect network")
                        await asyncio.sleep(reconnect_delay / 1000.0)
                        continue

                    # Create socket
                    s = socket.socket()
                    addr = socket.getaddrinfo(server_host, port)[0][-1]
                    s.connect(addr)

                    # Wrap with TLS if needed
                    if use_tls:
                        s = ssl.wrap_socket(s, server_hostname=server_host)

                    if debug:
                        print(f"Connected to {server_host}:{port}")

                    # Send HTTP request
                    request = create_stream_request(server_host)
                    send_all(s, request)

                    # Stream loop
                    frame_count = 0
                    while True:
                        t0 = time.ticks_ms()

                        # Get JPEG data from decorated function
                        # Handle both sync and async functions
                        try:
                            result = func(*args, **kwargs)
                            # If result is a coroutine (awaitable), await it
                            if ASYNCIO_AVAILABLE and hasattr(result, '__await__'):
                                result = await result
                        except Exception as func_err:
                            if debug:
                                print(f"Error in capture function: {func_err}")
                            await asyncio.sleep(frame_ms / 1000.0 if frame_ms > 0 else 0.1)
                            continue

                        # Handle tuple return (jpeg_data, timestamp) or just jpeg_data
                        if isinstance(result, tuple) and len(result) == 2:
                            jpeg_data, _ = result
                        else:
                            jpeg_data = result

                        if not isinstance(jpeg_data, (bytes, bytearray)):
                            if debug:
                                print(f"Warning: Function returned non-bytes: {type(jpeg_data)}")
                            await asyncio.sleep(frame_ms / 1000.0 if frame_ms > 0 else 0.1)
                            continue

                        # Send frame (using async version for cooperative yielding)
                        try:
                            await send_jpeg_frame_async(
                                s,
                                jpeg_data,
                                chunk_size=chunk_size,
                                yield_every_bytes=yield_every_bytes,
                                yield_ms=yield_ms
                            )
                        except Exception as send_err:
                            if debug:
                                print(f"Error sending frame: {send_err}")
                            break

                        frame_count += 1

                        # Light GC occasionally
                        if gc_interval > 0 and (frame_count % gc_interval) == 0:
                            gc.collect()

                        # Yield control periodically to allow other tasks
                        if yield_interval > 0 and (frame_count % yield_interval) == 0:
                            await asyncio.sleep(0)  # Yield to event loop

                        # Frame pacing
                        if frame_ms > 0:
                            elapsed = time.ticks_diff(time.ticks_ms(), t0)
                            delay = frame_ms - elapsed
                            if delay > 0:
                                await asyncio.sleep(delay / 1000.0)
                            else:
                                # Still yield even if we're behind schedule
                                await asyncio.sleep(0)

                except Exception as e:
                    if debug:
                        print(f"Stream ended: {e}")

                    # Close socket
                    try:
                        if s:
                            s.close()
                    except:
                        pass
                    s = None

                    # Wait before reconnecting
                    await asyncio.sleep(reconnect_delay / 1000.0)

        return stream_loop
    return wrapper

