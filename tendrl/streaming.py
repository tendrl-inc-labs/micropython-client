import time
import asyncio
import gc

MAX_FPS = 30
BOUNDARY = "tendrl"
_FRAME_HEADER_PREFIX = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ".encode('utf-8')
_FRAME_HEADER_SUFFIX = b"\r\n\r\n"
# Static streaming configuration - optimized values
_STREAM_CHUNK_SIZE = 2048
_STREAM_YIELD_EVERY_BYTES = 8 * 1024
_STREAM_YIELD_MS = 1
_STREAM_GC_INTERVAL = 250
_STREAM_RECONNECT_DELAY = 1000
_STREAM_YIELD_INTERVAL = 3

async def send_all_async(sock, data):
    mv = memoryview(data)
    sent = 0
    sent_since_yield = 0
    consecutive_zeros = 0  # Track consecutive zero returns (indicates connection issue)
    max_consecutive_zeros = 10  # Max zero returns before raising error

    while sent < len(mv):
        try:
            # Check if socket is still valid before writing
            if not hasattr(sock, 'write') and not hasattr(sock, 'send'):
                raise OSError(-1, "Socket is invalid")

            # Socket write is blocking in MicroPython - blocks until data is transmitted
            n = sock.write(mv[sent:]) if hasattr(sock, "write") else sock.send(mv[sent:])

            if n > 0:
                sent += n
                sent_since_yield += n
                consecutive_zeros = 0  # Reset counter on successful write
            elif n == 0:
                # Socket buffer full or connection issue - wait briefly and retry
                consecutive_zeros += 1
                if consecutive_zeros >= max_consecutive_zeros:
                    raise OSError(-1, "Socket write returned 0 multiple times - connection may be dead")
                # Increase wait time progressively to avoid tight loop that feels like freeze
                # Also yield to event loop to allow other tasks
                wait_time = min(0.01 * consecutive_zeros, 0.1)  # Progressive backoff, max 100ms
                await asyncio.sleep(wait_time)
                continue
            else:
                # Negative return value indicates error
                raise OSError(-1, f"Socket write returned {n}")

            # Yield periodically after write to allow other tasks to run
            if sent_since_yield >= _STREAM_YIELD_EVERY_BYTES:
                sent_since_yield = 0
                await asyncio.sleep(_STREAM_YIELD_MS / 1000.0)
        except OSError:
            # Re-raise OSError to be caught by caller
            raise
        except Exception as exc:
            # Wrap other exceptions as OSError for consistent handling
            raise OSError(-1, f"Error during socket write: {exc}")

async def send_bytes_chunked_async(sock, data):
    if len(data) < _STREAM_YIELD_EVERY_BYTES:
        await send_all_async(sock, data)
        return

    mv = memoryview(data)
    sent_since_yield = 0

    for i in range(0, len(mv), _STREAM_CHUNK_SIZE):
        chunk = mv[i:i + _STREAM_CHUNK_SIZE]
        await send_all_async(sock, chunk)
        sent_since_yield += len(chunk)

        # Yield to event loop periodically - allows other tasks to run
        if sent_since_yield >= _STREAM_YIELD_EVERY_BYTES:
            sent_since_yield = 0
            await asyncio.sleep(_STREAM_YIELD_MS / 1000.0)

async def send_jpeg_frame_async(sock, jpeg_data, perf_data=None):
    # Build header efficiently using pre-encoded static parts
    header = _FRAME_HEADER_PREFIX + str(len(jpeg_data)).encode('utf-8') + _FRAME_HEADER_SUFFIX

    # Send header - if this fails, connection is definitely dead
    try:
        await send_all_async(sock, header)
    except OSError:
        raise  # Re-raise to be caught by caller

    # Send frame data - if this fails mid-transmission, connection died during frame send
    t_frame_send = time.ticks_ms()
    try:
        await send_bytes_chunked_async(sock, jpeg_data)
    except OSError as exc:
        # Connection died during frame transmission - this is the "unexpected EOF" case
        raise OSError(-104, f"Connection reset during frame transmission: {exc}")
    t_frame_send_end = time.ticks_ms()

    # Send boundary terminator - if this fails, connection died after frame
    try:
        await send_all_async(sock, b"\r\n")
    except OSError:
        raise  # Re-raise to be caught by caller

    # Store frame send time (the bottleneck) - always track to identify network issues
    if perf_data:
        if 'frame_send_times' not in perf_data:
            perf_data['frame_send_times'] = []
        perf_data['frame_send_times'].append(time.ticks_diff(t_frame_send_end, t_frame_send))

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

def _format_connection_error_message(errno):
    error_messages = {
        -6: "EHOSTUNREACH - Host unreachable (network/DNS issue)",
        -2: "ENOENT - Name or service not known (DNS resolution failed)",
        -1: "EIO - I/O error",
        -5: "EIO - I/O error",
        110: "ETIMEDOUT - Connection timed out",
        111: "ECONNREFUSED - Connection refused",
    }
    return error_messages.get(errno, f"OSError {errno}")

async def _capture_frame(capture_frame_func, validate=True):
    # Yield before potentially blocking camera capture
    await asyncio.sleep(0)
    result = capture_frame_func()
    # If result is a coroutine (awaitable), await it
    if hasattr(result, '__await__'):
        result = await result
    # Yield after camera capture to allow other tasks
    await asyncio.sleep(0)

    # Handle tuple return (jpeg_data, timestamp) or just jpeg_data
    # Fast path: avoid isinstance check if we know it's not a tuple
    if isinstance(result, tuple):
        frame_data = result[0]  # Direct index access is faster than unpacking
    else:
        frame_data = result

    # Validate frame data only if requested (skip in hot path for speed)
    if validate:
        if not isinstance(frame_data, (bytes, bytearray)) or not frame_data or len(frame_data) == 0:
            raise ValueError(f"Invalid frame: expected non-empty bytes/bytearray, got {type(frame_data).__name__}")

    return frame_data

def _check_duration_elapsed(duration_ms, start_time):
    if duration_ms and start_time:
        return time.ticks_diff(time.ticks_ms(), start_time) >= duration_ms
    return False

async def _connect_to_server(server_host, port, debug=False):
    # Import inside function for faster local lookups (MicroPython optimization)
    import socket
    import ssl

    s = None
    try:
        # Yield before blocking DNS lookup to allow other tasks to run
        await asyncio.sleep(0)
        s = socket.socket()
        # DNS lookup is blocking - yield after to allow event loop to process
        addr = socket.getaddrinfo(server_host, port)[0][-1]
        await asyncio.sleep(0)  # Yield after DNS lookup

        # Socket connect is blocking - yield before and after
        await asyncio.sleep(0)
        s.connect(addr)
        await asyncio.sleep(0)  # Yield after connect

        # SSL handshake is blocking and can take time - yield before and after
        await asyncio.sleep(0)
        s = ssl.wrap_socket(s, server_hostname=server_host)
        await asyncio.sleep(0)  # Yield after SSL handshake

        if debug:
            print("Streaming: Connected to server")
        return s
    except Exception as e:
        if debug:
            print(f"Streaming: Connection error: {e}")
        if s:
            try:
                s.close()
            except:
                pass
        raise

async def _send_first_frame(sock, capture_frame_func, server_host, api_key, debug=False):
    # Capture first frame
    try:
        first_frame = await _capture_frame(capture_frame_func)
    except Exception:
        # If first frame capture fails, retry will happen in outer loop
        raise

    # Build first frame multipart data (optimized: use pre-encoded static parts)
    content_length_str = str(len(first_frame)).encode('utf-8')
    frame_header = _FRAME_HEADER_PREFIX + content_length_str + _FRAME_HEADER_SUFFIX

    request_headers = create_stream_request(server_host, api_key)

    # Combine: HTTP request + first frame boundary + frame data + boundary terminator
    # All sent in one operation to ensure it's part of the HTTP request body
    complete_request = request_headers + frame_header + first_frame + b"\r\n"

    await send_all_async(sock, complete_request)
    if debug:
        print("Streaming: Starting stream...")

async def _send_frame_async(sock, jpeg_data, consecutive_errors,
                            max_consecutive_errors, debug=False,
                            perf_data=None):
    try:
        await send_jpeg_frame_async(
            sock,
            jpeg_data,
            perf_data=perf_data
        )
        # Reset error counter on successful send
        return True, 0
    except OSError:
        # Handle socket errors during frame sending
        consecutive_errors += 1

        # If we've had too many consecutive errors, give up on this connection
        if consecutive_errors >= max_consecutive_errors:
            return False, consecutive_errors

        # For single errors, wait briefly and try next frame
        # This handles transient network issues
        await asyncio.sleep(0.1)
        return False, consecutive_errors
    except Exception as send_err:
        if debug:
            print(f"Error sending frame: {send_err} (type: {type(send_err).__name__})")
        consecutive_errors += 1
        if consecutive_errors >= max_consecutive_errors:
            return False, consecutive_errors
        await asyncio.sleep(0.1)
        return False, consecutive_errors

async def validate_capture_function(capture_frame_func):
    try:
        await asyncio.sleep(0)  # Yield before potentially blocking capture
        test_result = capture_frame_func()
        # If result is a coroutine (awaitable), await it
        if hasattr(test_result, '__await__'):
            test_result = await test_result
        await asyncio.sleep(0)  # Yield after capture

        # Handle tuple return (jpeg_data, timestamp) or just jpeg_data
        if isinstance(test_result, tuple) and len(test_result) == 2:
            test_frame, _ = test_result
        else:
            test_frame = test_result

        # Validate return type - must be bytes or bytearray
        if not isinstance(test_frame, (bytes, bytearray)):
            raise TypeError(
                f"capture_frame_func must return bytes or bytearray, got {type(test_frame).__name__}. "
                f"It can also return a tuple of (bytes/bytearray, timestamp)."
            )

        # Validate frame is not empty
        if not test_frame or len(test_frame) == 0:
            raise ValueError(
                "capture_frame_func returned empty frame. "
                "The function must return non-empty bytes or bytearray."
            )
    except TypeError:
        # Re-raise TypeError (our validation error) as-is
        raise
    except ValueError:
        # Re-raise ValueError (our validation error) as-is
        raise
    except Exception as e:
        # Wrap other exceptions from the capture function
        raise RuntimeError(
            f"Error testing capture_frame_func: {e}. "
            f"Please ensure the function is properly configured and returns bytes/bytearray."
        ) from e

def start_jpeg_stream(client_instance, capture_frame_func, target_fps=15,
                     stream_duration=-1, debug=False):
    # Always collect performance data to identify network bottlenecks
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

    # Cache API key lookup - avoid repeated config access in hot path
    api_key = client_instance.config.get("api_key", "")

    async def stream_loop():
        """Async stream loop that yields control periodically"""
        s = None
        # Convert duration to milliseconds for ticks_ms (more performant than time.time())
        duration_ms = int(stream_duration * 1000) if stream_duration > 0 else None
        start_time = time.ticks_ms() if duration_ms else None
        # Cache frame delay in seconds to avoid repeated division (performance optimization)
        frame_s = frame_ms / 1000.0 if frame_ms > 0 else 0.1

        # Validate capture function once before streaming - fail fast with clear error
        await validate_capture_function(capture_frame_func)

        while True:
            # Check if duration has elapsed
            if _check_duration_elapsed(duration_ms, start_time):
                if debug:
                    print(f"Streaming duration ({stream_duration}s) elapsed, stopping...")
                break

            # Wait for MQTT connection before streaming (ensures entity shows as online)
            # This is important so the server knows the client is online before streaming starts
            # Only wait if MQTT is enabled (mqtt is not None)
            if client_instance.mqtt is not None and not client_instance.mqtt.connected:
                # Wait for MQTT connection with periodic checks and timeout
                max_wait_time = 30  # Maximum 30 seconds to wait for MQTT
                wait_start = time.ticks_ms()
                while client_instance.mqtt is not None and not client_instance.mqtt.connected:
                    elapsed = time.ticks_diff(time.ticks_ms(), wait_start)
                    if elapsed > max_wait_time * 1000:
                        break
                    await asyncio.sleep(0.5)  # Check every 500ms
            try:
                # Connect to server
                try:
                    s = await _connect_to_server(server_host, port, debug=debug)
                except Exception:
                    await asyncio.sleep(_STREAM_RECONNECT_DELAY / 1000.0)
                    continue

                # API key already cached above, just check for debug warning
                if not api_key and debug:
                    print("Warning: No API key found in config")

                # Send first frame and initial request
                try:
                    await _send_first_frame(
                        s, capture_frame_func, server_host, api_key,
                        debug=debug
                    )
                except Exception:
                    # If first frame fails, close socket and retry connection
                    try:
                        s.close()
                    except:
                        pass
                    s = None
                    await asyncio.sleep(1.0)
                    continue

                # Stream remaining frames - optimized hot path
                frame_count = 1  # First frame already sent
                consecutive_errors = 0
                max_consecutive_errors = 3  # Allow a few errors before giving up on this connection
                # Cache modulo checks for better performance
                gc_check_interval = _STREAM_GC_INTERVAL if _STREAM_GC_INTERVAL > 0 else 0
                yield_check_interval = _STREAM_YIELD_INTERVAL if _STREAM_YIELD_INTERVAL > 0 else 0

                # Adaptive frame dropping - track recent performance to skip frames when network is slow
                recent_send_times = []  # Track last 5 send times
                max_recent_times = 5
                recent_send_sum = 0  # Track running sum to avoid sum() overhead
                frames_dropped = 0

                # Performance statistics - only collected if debug enabled to avoid overhead
                perf_data = None
                if debug:
                    perf_data = {
                        'send_times': [],
                        'total_times': [],
                        'frame_sizes': [],
                        'behind_count': 0,
                        'frames_dropped': 0,
                        'last_stats_time': time.ticks_ms(),
                        'last_stats_frame': 1,
                        'frame_send_times': [] # Specific for network bottleneck
                    }

                while True:
                    t0 = time.ticks_ms()

                    # Adaptive frame dropping: skip frames if we're way behind
                    # Only check if we have enough data and it's worth checking
                    # Optimized: use running sum instead of sum() every frame
                    should_skip = False
                    if len(recent_send_times) >= 3:
                        # Quick check: if recent average is very high, skip every other frame
                        # Use cached sum instead of recalculating
                        avg_recent_send = recent_send_sum / len(recent_send_times)
                        if avg_recent_send > frame_ms * 2.5:
                            should_skip = (frame_count % 2 == 0)  # Skip every other frame

                    # Capture frame - use fast path (skip validation after first frame)
                    try:
                        jpeg_data = await _capture_frame(capture_frame_func, validate=False)
                    except Exception as func_err:
                        if debug:
                            print(f"Error in capture function: {func_err}")
                        await asyncio.sleep(frame_s)
                        continue

                    # Skip frame if network is too slow
                    if should_skip:
                        frames_dropped += 1
                        if perf_data:
                            perf_data['frames_dropped'] = frames_dropped
                        # Still increment frame count and do pacing
                        frame_count += 1
                        # Fast path pacing for skipped frames
                        if frame_ms > 0:
                            await asyncio.sleep(frame_s)
                        continue

                    t_send_start = time.ticks_ms()

                    # Send frame with error handling
                    success, consecutive_errors = await _send_frame_async(
                        s, jpeg_data,
                        consecutive_errors, max_consecutive_errors, debug=debug, perf_data=perf_data
                    )

                    # Track recent send times for adaptive dropping (only if successful)
                    # Optimized: maintain running sum to avoid sum() overhead
                    if success:
                        send_duration = time.ticks_diff(time.ticks_ms(), t_send_start)
                        recent_send_times.append(send_duration)
                        recent_send_sum += send_duration
                        if len(recent_send_times) > max_recent_times:
                            # Remove oldest value from sum when list is full
                            removed = recent_send_times.pop(0)
                            recent_send_sum -= removed

                    if not success:
                        if consecutive_errors >= max_consecutive_errors:
                            break  # Break to reconnect
                        continue  # Try next frame

                    t_send_end = time.ticks_ms()
                    frame_count += 1

                    # Collect performance data (only if debug enabled)
                    if perf_data:
                        send_time = time.ticks_diff(t_send_end, t_send_start)
                        total_time = time.ticks_diff(time.ticks_ms(), t0)
                        perf_data['send_times'].append(send_time)
                        perf_data['total_times'].append(total_time)
                        perf_data['frame_sizes'].append(len(jpeg_data))

                    # Check if duration has elapsed (only check periodically to reduce overhead)
                    if duration_ms and (frame_count % 10 == 0):
                        if _check_duration_elapsed(duration_ms, start_time):
                            if debug:
                                print(f"Streaming duration ({stream_duration}s) elapsed, stopping...")
                            break

                    # Explicit GC to prevent large automatic GC freezes
                    # More frequent, smaller GCs reduce system-wide freeze duration
                    # At 25 FPS: 250 frames = ~10 seconds (predictable, smaller GCs)
                    # This works alongside client GC to keep memory pressure low
                    if gc_check_interval > 0 and (frame_count % gc_check_interval) == 0:
                        # Yield before GC to allow other tasks to finish current operations
                        await asyncio.sleep(0)
                        gc.collect()
                        # Yield after GC to allow other tasks to resume
                        await asyncio.sleep(0)

                    # Yield control periodically to allow other tasks
                    if yield_check_interval > 0 and (frame_count % yield_check_interval) == 0:
                        await asyncio.sleep(0)  # Yield to event loop

                    # Frame pacing - dynamically handle any FPS efficiently
                    # This ensures consistent timing regardless of target FPS (5-30 FPS)
                    if frame_ms > 0:
                        elapsed = time.ticks_diff(time.ticks_ms(), t0)
                        delay_ms = frame_ms - elapsed

                        if delay_ms > 0:
                            # Ahead of schedule - sleep to maintain frame rate
                            # For long delays (low FPS < 10), chunk sleep to stay responsive
                            if delay_ms > 100:  # Very low FPS (< 10 FPS)
                                # Sleep in 50ms chunks to allow other tasks to run
                                # This prevents long blocking sleeps that feel unresponsive
                                chunks = int(delay_ms / 50)
                                remainder = delay_ms % 50
                                for _ in range(chunks):
                                    await asyncio.sleep(0.05)  # 50ms chunks
                                if remainder > 0:
                                    await asyncio.sleep(remainder / 1000.0)
                            else:
                                # Normal delay - single sleep (most common case)
                                await asyncio.sleep(delay_ms / 1000.0)
                        else:
                            # Behind schedule - but still maintain minimum spacing to prevent bursts
                            # This prevents overwhelming the network with back-to-back frames
                            # which can make congestion worse. Minimum delay is 10% of frame budget
                            # (e.g., ~6.6ms for 15 FPS, ~5ms for 20 FPS) to allow network to process
                            if perf_data:
                                perf_data['behind_count'] += 1
                            # Always maintain minimum spacing to prevent network bursts
                            # This creates more stable streaming even when network is slow
                            min_delay_ms = max(1, int(frame_ms * 0.1))  # At least 1ms, or 10% of budget
                            await asyncio.sleep(min_delay_ms / 1000.0)

                    # Print performance statistics periodically (only if debug enabled)
                    if debug and frame_count % 60 == 0:  # Every 60 frames (~2.4s at 25 FPS)
                        elapsed_stats = time.ticks_diff(time.ticks_ms(), perf_data['last_stats_time'])
                        frames_in_period = frame_count - perf_data['last_stats_frame']
                        actual_fps = (frames_in_period * 1000.0) / elapsed_stats if elapsed_stats > 0 else 0

                        if perf_data['send_times']:
                            avg_send = sum(perf_data['send_times']) / len(perf_data['send_times'])
                            avg_total = sum(perf_data['total_times']) / len(perf_data['total_times'])
                            max_total = max(perf_data['total_times'])
                            min_total = min(perf_data['total_times'])
                            avg_size = sum(perf_data['frame_sizes']) / len(perf_data['frame_sizes'])
                            behind_pct = (perf_data['behind_count'] / len(perf_data['total_times'])) * 100

                            # Calculate effective network bandwidth from frame send times
                            avg_frame_send = 0
                            effective_bandwidth_mbps = 0
                            if 'frame_send_times' in perf_data and perf_data['frame_send_times']:
                                avg_frame_send = sum(perf_data['frame_send_times']) / len(perf_data['frame_send_times'])
                                effective_bandwidth_kbps = (avg_size * 8) / avg_frame_send if avg_frame_send > 0 else 0
                                effective_bandwidth_mbps = effective_bandwidth_kbps / 1000

                            print(f"\n📊 Performance Stats (last {frames_in_period} frames, {elapsed_stats}ms):")
                            print(f"   Target FPS: {target_fps} | Actual FPS: {actual_fps:.1f}")
                            print(f"   Avg Send: {avg_send:.1f}ms | Avg Total: {avg_total:.1f}ms | Range: {min_total:.1f}ms - {max_total:.1f}ms")
                            print(f"   Avg Frame Size: {avg_size/1024:.1f}KB | Behind Schedule: {behind_pct:.1f}%")
                            print(f"   Budget: {frame_ms}ms | Utilization: {(avg_total/frame_ms)*100:.1f}%")

                            if avg_frame_send > 0:
                                print(f"   Network: {avg_frame_send:.1f}ms to send frame | Effective Bandwidth: {effective_bandwidth_mbps:.2f} Mbps")

                            if perf_data and perf_data.get('frames_dropped', 0) > 0:
                                drop_pct = (perf_data['frames_dropped'] / frames_in_period) * 100
                                print(f"   Frames Dropped: {perf_data['frames_dropped']} ({drop_pct:.1f}%)")

                            # Performance recommendations
                            if avg_send > frame_ms * 0.8:
                                print(f"   ⚠️  Network is bottleneck ({avg_send:.1f}ms > {frame_ms*0.8:.1f}ms)")
                                print(f"      Consider: reduce frame size/quality or lower FPS to {int(actual_fps * 0.9)}")
                            if behind_pct > 30:
                                print(f"   ⚠️  High behind schedule rate ({behind_pct:.1f}%)")
                                print(f"      Consider: reduce target_fps to {int(actual_fps * 0.9)}")
                            if max_total > frame_ms * 3:
                                print(f"   ⚠️  Large frame time spikes (max {max_total:.1f}ms)")
                                print(f"      Possible network congestion or GC pauses")
                            
                            # Reset stats for next period
                            perf_data['send_times'] = []
                            perf_data['total_times'] = []
                            perf_data['frame_sizes'] = []
                            perf_data['behind_count'] = 0
                            perf_data['frames_dropped'] = 0
                            if 'frame_send_times' in perf_data:
                                perf_data['frame_send_times'] = []
                            perf_data['last_stats_time'] = time.ticks_ms()
                            perf_data['last_stats_frame'] = frame_count

            except OSError as e:
                # Connection errors are handled automatically by reconnection
                # Only log non-ECONNRESET errors (connection resets are expected)
                if debug:
                    errno = e.args[0] if e.args else 'unknown'
                    # ECONNRESET (-104) is expected and handled automatically
                    if errno != -104:
                        err_msg = _format_connection_error_message(errno)
                        if err_msg:
                            print(f"Stream error: {err_msg}")
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

            # Wait before reconnecting
            await asyncio.sleep(_STREAM_RECONNECT_DELAY / 1000.0)

    return stream_loop
