def send_all(sock, data):
    mv = memoryview(data)
    sent = 0
    while sent < len(mv):
        n = sock.write(mv[sent:]) if hasattr(sock, "write") else sock.send(mv[sent:])
        if n:
            sent += n

async def send_all_async(sock, data, yield_every_bytes=32*1024, yield_ms=1):
    """Async version of send_all that yields periodically to avoid blocking"""
    try:
        import asyncio
    except ImportError:
        # Fallback to sync version if asyncio not available
        send_all(sock, data)
        return

    mv = memoryview(data)
    sent = 0
    sent_since_yield = 0

    while sent < len(mv):
        n = sock.write(mv[sent:]) if hasattr(sock, "write") else sock.send(mv[sent:])
        if n:
            sent += n
            sent_since_yield += n

            # Yield periodically to allow other tasks to run
            if sent_since_yield >= yield_every_bytes:
                sent_since_yield = 0
                await asyncio.sleep(yield_ms / 1000.0)

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
        await send_all_async(sock, data, yield_every_bytes, yield_ms)
        return

    mv = memoryview(data)
    sent_since_yield = 0

    for i in range(0, len(mv), chunk_size):
        chunk = mv[i:i + chunk_size]
        await send_all_async(sock, chunk, yield_every_bytes, yield_ms)
        sent_since_yield += len(chunk)

        # Yield to event loop periodically - allows other tasks to run
        if sent_since_yield >= yield_every_bytes:
            sent_since_yield = 0
            await asyncio.sleep(yield_ms / 1000.0)

BOUNDARY = "tendrl"

def send_jpeg_frame(sock, jpeg_data, chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    header = (
        f"--{BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg_data)}\r\n"
        "\r\n"
    )
    send_all(sock, header.encode('utf-8'))
    send_bytes_chunked(sock, jpeg_data, chunk_size, yield_every_bytes, yield_ms)
    send_all(sock, b"\r\n")

async def send_jpeg_frame_async(sock, jpeg_data, chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    # Optimize header building: only Content-Length changes, build efficiently
    # Pre-encode static parts to avoid repeated string operations
    header_prefix = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ".encode('utf-8')
    header_suffix = b"\r\n\r\n"
    content_length_str = str(len(jpeg_data)).encode('utf-8')
    header = header_prefix + content_length_str + header_suffix
    await send_all_async(sock, header, yield_every_bytes, yield_ms)
    await send_bytes_chunked_async(sock, jpeg_data, chunk_size, yield_every_bytes, yield_ms)
    await send_all_async(sock, b"\r\n", yield_every_bytes, yield_ms)

def create_stream_request(server_host, api_key):
    auth_header = ""
    if api_key:
        auth_header = f"Authorization: Bearer {api_key}\r\n"

    content_length = 10 * 1024 * 1024  # 10MB

    return (
        "POST /api/stream HTTP/1.1\r\n"
        f"Host: {server_host}\r\n"
        "Connection: keep-alive\r\n"  # Keep connection open for streaming
        f"Content-Type: multipart/x-mixed-replace; boundary={BOUNDARY}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"{auth_header}"
        "\r\n"
    ).encode('utf-8')


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


# Maximum FPS supported by the streaming server
MAX_FPS = 30

def start_jpeg_stream(client_instance, capture_frame_func, chunk_size=2048,
                     yield_every_bytes=8*1024, yield_ms=1, target_fps=25,
                     gc_interval=250, reconnect_delay=5000, yield_interval=3,
                     stream_duration=-1, debug=False):

    import socket
    import ssl
    import time
    import gc

    try:
        import asyncio
        ASYNCIO_AVAILABLE = True
    except ImportError:
        ASYNCIO_AVAILABLE = False

    # Validate target_fps against server maximum
    if target_fps > MAX_FPS:
        raise ValueError(
            f"Target FPS ({target_fps}) exceeds server maximum ({MAX_FPS} FPS). "
            f"Please set target_fps to {MAX_FPS} or lower."
        )
    elif target_fps <= 0:
        raise ValueError(
            f"Invalid target_fps ({target_fps}). Must be greater than 0 and not exceed {MAX_FPS} FPS."
        )

    # Get server hostname from client config (always use TLS, port 443)
    app_url = client_instance.config.get("app_url", "https://app.tendrl.com")
    server_host = _extract_hostname_from_url(app_url)
    port = 443
    frame_ms = 1000 // target_fps if target_fps > 0 else 0

    async def stream_loop():
        """Async stream loop that yields control periodically"""
        # Always print startup message to confirm task is running
        duration_msg = f" for {stream_duration}s" if stream_duration > 0 else " (indefinite)"
        print(f"📹 Streaming task started - target: {server_host}:{port}, FPS: {target_fps}{duration_msg}")
        if debug:
            print(f"📹 Streaming debug enabled")
        s = None
        # Convert duration to milliseconds for ticks_ms (more performant than time.time())
        duration_ms = int(stream_duration * 1000) if stream_duration > 0 else None
        start_time = time.ticks_ms() if duration_ms else None
        # Cache frame delay in seconds to avoid repeated division (performance optimization)
        frame_s = frame_ms / 1000.0 if frame_ms > 0 else 0.1
        while True:
            # Check if duration has elapsed (using ticks_ms for better performance)
            if duration_ms and start_time:
                elapsed_ms = time.ticks_diff(time.ticks_ms(), start_time)
                if elapsed_ms >= duration_ms:
                    if debug:
                        print(f"📹 Streaming duration ({stream_duration}s) elapsed, stopping...")
                    break
            try:
                # Ensure network connection via network manager (client handles networking)
                if not client_instance.network.connect():
                    if debug:
                        print("📹 Streaming: Failed to connect network, retrying...")
                    await asyncio.sleep(reconnect_delay / 1000.0)
                    continue
                
                if debug:
                    print(f"📹 Streaming: Network connected, attempting server connection...")

                # Create socket and connect
                try:
                    if debug:
                        print(f"📹 Streaming: Resolving {server_host}:{port}...")
                    s = socket.socket()
                    addr = socket.getaddrinfo(server_host, port)[0][-1]
                    if debug:
                        print(f"📹 Streaming: Connecting to {addr}...")
                    s.connect(addr)
                    if debug:
                        print(f"📹 Streaming: Wrapping with TLS...")
                    s = ssl.wrap_socket(s, server_hostname=server_host)
                    if debug:
                        print(f"📹 Streaming: Connected to server!")
                except Exception as e:
                    if debug:
                        print(f"📹 Streaming: Connection error: {e}")
                    if s:
                        try:
                            s.close()
                        except:
                            pass
                    s = None
                    await asyncio.sleep(reconnect_delay / 1000.0)
                    continue

                # Get API key from client config for authentication
                api_key = client_instance.config.get("api_key", "")
                if not api_key:
                    if debug:
                        print("Warning: No API key found in config")

                first_frame = None
                try:
                    if debug:
                        print("📹 Streaming: Capturing first frame...")
                    # Get first frame from capture function
                    result = capture_frame_func()
                    # If result is a coroutine (awaitable), await it
                    if ASYNCIO_AVAILABLE and hasattr(result, '__await__'):
                        result = await result

                    # Handle tuple return (jpeg_data, timestamp) or just jpeg_data
                    if isinstance(result, tuple) and len(result) == 2:
                        first_frame, _ = result
                    else:
                        first_frame = result

                    if not isinstance(first_frame, (bytes, bytearray)) or not first_frame or len(first_frame) == 0:
                        if debug:
                            print("📹 Streaming: Warning: Empty or invalid first frame, will retry...")
                        await asyncio.sleep(1.0)
                        continue  # Retry connection
                    if debug:
                        print(f"📹 Streaming: First frame captured ({len(first_frame)} bytes)")
                except Exception as func_err:
                    if debug:
                        print(f"📹 Streaming: Error capturing first frame: {func_err}")
                    await asyncio.sleep(1.0)
                    continue  # Retry connection

                # Build first frame multipart data (optimized: avoid repeated string operations)
                frame_header_prefix = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ".encode('utf-8')
                frame_header_suffix = b"\r\n\r\n"
                frame_header = frame_header_prefix + str(len(first_frame)).encode('utf-8') + frame_header_suffix

                request_headers = create_stream_request(server_host, api_key)

                # Combine: HTTP request + first frame boundary + frame data + boundary terminator
                # All sent in one operation to ensure it's part of the HTTP request body
                complete_request = request_headers + frame_header + first_frame + b"\r\n"

                try:
                    if debug:
                        print(f"📹 Streaming: Sending HTTP request + first frame ({len(complete_request)} bytes)...")
                    await send_all_async(s, complete_request, yield_every_bytes, yield_ms)
                    if debug:
                        print("✅ Streaming: HTTP request + first frame sent successfully! Starting stream...")
                except Exception as e:
                    if debug:
                        print(f"❌ Streaming: Error sending request+frame: {e}")
                    break

                # Stream remaining frames
                frame_count = 1  # First frame already sent
                while True:
                    t0 = time.ticks_ms()

                    # Get JPEG data from capture function
                    # Handle both sync and async functions
                    try:
                        result = capture_frame_func()
                        # If result is a coroutine (awaitable), await it
                        if ASYNCIO_AVAILABLE and hasattr(result, '__await__'):
                            result = await result
                    except Exception as func_err:
                        if debug:
                            print(f"Error in capture function: {func_err}")
                        await asyncio.sleep(frame_s)
                        continue

                    # Handle tuple return (jpeg_data, timestamp) or just jpeg_data
                    if isinstance(result, tuple) and len(result) == 2:
                        jpeg_data, _ = result
                    else:
                        jpeg_data = result

                    if not isinstance(jpeg_data, (bytes, bytearray)) or not jpeg_data or len(jpeg_data) == 0:
                        if debug:
                            print(f"Warning: Empty or invalid frame: {type(jpeg_data)}")
                        await asyncio.sleep(frame_s)
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

                    # Check if duration has elapsed (check periodically during frame loop)
                    # Using ticks_ms for better performance (integer-based, faster than time.time())
                    if duration_ms and start_time:
                        elapsed_ms = time.ticks_diff(time.ticks_ms(), start_time)
                        if elapsed_ms >= duration_ms:
                            if debug:
                                print(f"📹 Streaming duration ({stream_duration}s) elapsed, stopping...")
                            break

                    # Explicit GC to prevent large automatic GC freezes
                    # More frequent, smaller GCs reduce system-wide freeze duration
                    # At 25 FPS: 250 frames = ~10 seconds (predictable, smaller GCs)
                    # This works alongside client GC to keep memory pressure low
                    if gc_interval > 0 and (frame_count % gc_interval) == 0:
                        gc.collect()
                        await asyncio.sleep(0)  # Yield after GC to allow other tasks

                    # Yield control periodically to allow other tasks
                    if yield_interval > 0 and (frame_count % yield_interval) == 0:
                        await asyncio.sleep(0)  # Yield to event loop

                    # Frame pacing
                    if frame_ms > 0:
                        elapsed = time.ticks_diff(time.ticks_ms(), t0)
                        delay_ms = frame_ms - elapsed
                        if delay_ms > 0:
                            await asyncio.sleep(delay_ms / 1000.0)
                        else:
                            # Still yield even if we're behind schedule
                            await asyncio.sleep(0)

            except OSError as e:
                if debug:
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
                if debug:
                    print(f"Stream ended: {e} (type: {type(e).__name__})")

            finally:
                # Close socket if it was created
                try:
                    if s:
                        s.close()
                except Exception:
                    pass
                s = None

            if debug:
                reconnect_s = reconnect_delay / 1000.0
                print(f"Reconnecting in {reconnect_s} seconds...")

            # Wait before reconnecting
            await asyncio.sleep(reconnect_delay / 1000.0)

    return stream_loop
