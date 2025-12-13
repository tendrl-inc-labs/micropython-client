"""
JPEG Streaming Module for Tendrl Client

This module provides JPEG streaming functionality with performance tuning.
It's an optional module that can be installed separately to reduce code size
for users who don't need camera streaming.
"""

# =========================
# JPEG STREAMING HELPERS
# =========================

def send_all(sock, data):
    """Send all data through socket, handling both write() and send() methods"""
    mv = memoryview(data)
    sent = 0
    while sent < len(mv):
        n = sock.write(mv[sent:]) if hasattr(sock, "write") else sock.send(mv[sent:])
        if n:
            sent += n

def send_bytes_chunked(sock, data, chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    """
    Send bytes in chunks with periodic yielding for better throughput.
    
    For H7/RT1062, larger chunks reduce overhead.
    Only yield for very large frames to prevent blocking.
    For small frames (< yield_every_bytes), send directly without chunking overhead.
    
    Args:
        sock: Socket object
        data: Bytes data to send
        chunk_size: Size of each chunk to send (default: 4096)
        yield_every_bytes: Yield after sending this many bytes (default: 32KB)
        yield_ms: Milliseconds to sleep when yielding (default: 1)
    """
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
    """
    Async version: Send bytes in chunks with periodic async yielding for better throughput.
    
    This version uses asyncio.sleep() instead of blocking sleep_ms(), allowing
    other async tasks to run during large frame sends.
    
    Args:
        sock: Socket object
        data: Bytes data to send
        chunk_size: Size of each chunk to send (default: 4096)
        yield_every_bytes: Yield after sending this many bytes (default: 32KB)
        yield_ms: Milliseconds to sleep when yielding (default: 1)
    """
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

def send_jpeg_frame(sock, jpeg_data, boundary="openmvframe", 
                   chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    """
    Send a single JPEG frame with multipart HTTP headers (sync version).
    
    Args:
        sock: Socket object
        jpeg_data: JPEG image data as bytes
        boundary: Multipart boundary string (default: "openmvframe")
        chunk_size: Chunk size for sending (default: 4096)
        yield_every_bytes: Yield after sending this many bytes (default: 32KB)
        yield_ms: Milliseconds to sleep when yielding (default: 1)
    """
    header = (
        f"--{boundary}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg_data)}\r\n"
        "\r\n"
    )
    send_all(sock, header)
    send_bytes_chunked(sock, jpeg_data, chunk_size, yield_every_bytes, yield_ms)
    send_all(sock, "\r\n")

async def send_jpeg_frame_async(sock, jpeg_data, boundary="openmvframe", 
                                chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1):
    """
    Async version: Send a single JPEG frame with multipart HTTP headers.
    
    This version uses async chunked sending, allowing other tasks to run
    during large frame transmission.
    
    Args:
        sock: Socket object
        jpeg_data: JPEG image data as bytes
        boundary: Multipart boundary string (default: "openmvframe")
        chunk_size: Chunk size for sending (default: 4096)
        yield_every_bytes: Yield after sending this many bytes (default: 32KB)
        yield_ms: Milliseconds to sleep when yielding (default: 1)
    """
    header = (
        f"--{boundary}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg_data)}\r\n"
        "\r\n"
    )
    send_all(sock, header)
    await send_bytes_chunked_async(sock, jpeg_data, chunk_size, yield_every_bytes, yield_ms)
    send_all(sock, "\r\n")

def create_stream_request(server_host, boundary="openmvframe"):
    """
    Create HTTP multipart stream request headers.
    
    Args:
        server_host: Server hostname
        boundary: Multipart boundary string (default: "openmvframe")
    
    Returns:
        HTTP request string
    """
    return (
        "POST /stream HTTP/1.1\r\n"
        f"Host: {server_host}\r\n"
        "Connection: close\r\n"
        f"Content-Type: multipart/x-mixed-replace; boundary={boundary}\r\n"
        "\r\n"
    )


def jpeg_stream_decorator(client_instance, server_host, port=None, use_tls=True,
                          chunk_size=4096, yield_every_bytes=32*1024, yield_ms=1,
                          target_fps=25, boundary="openmvframe", gc_interval=1024,
                          reconnect_delay=5000, yield_interval=10, debug=False):
    """
    Decorator factory for JPEG streaming with performance tuning parameters.
    
    The decorated function should return JPEG image data (bytes) or a tuple
    (jpeg_data, timestamp_ms). The function will be called in a loop to
    stream frames continuously.
    
    Args:
        client_instance: The Client instance (for network access)
        server_host: Server hostname or IP address
        port: Server port (default: 443 if use_tls else 80)
        use_tls: Enable TLS/SSL (default: True)
        chunk_size: Size of chunks for sending data (default: 4096)
        yield_every_bytes: Yield after sending this many bytes (default: 32KB)
        yield_ms: Milliseconds to sleep when yielding (default: 1)
        target_fps: Target frames per second (default: 25)
        boundary: Multipart boundary string (default: "openmvframe")
        gc_interval: Run GC every N frames (default: 1024)
        reconnect_delay: Delay before reconnecting on error in ms (default: 5000)
        yield_interval: Yield control every N frames to allow other tasks (default: 10)
        debug: Enable debug output (default: False)
    
    Returns:
        Decorator function
    """
    import socket
    import ssl
    import time
    import gc
    
    try:
        import asyncio
        ASYNCIO_AVAILABLE = True
    except ImportError:
        ASYNCIO_AVAILABLE = False
    
    if port is None:
        port = 443 if use_tls else 80

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
                    request = create_stream_request(server_host, boundary)
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
                                boundary=boundary,
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

