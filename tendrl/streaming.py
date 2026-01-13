import time
import asyncio
import gc

MAX_FPS = 30
BOUNDARY = "tendrl"
_FRAME_HEADER_PREFIX = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ".encode('utf-8')
_FRAME_HEADER_SUFFIX = b"\r\n\r\n"
# Static streaming configuration - optimized values for maximum WiFi throughput
# Larger chunks reduce syscall overhead and better utilize TCP window sizes
_STREAM_CHUNK_SIZE = 8192  # 8KB - optimal for WiFi (was 2KB)
_STREAM_YIELD_EVERY_BYTES = 32 * 1024  # 32KB - reduce yield frequency (was 8KB)
_STREAM_YIELD_MS = 0  # Remove sleep on yield - just yield to event loop (was 1ms)
_STREAM_GC_INTERVAL = 250
_STREAM_RECONNECT_DELAY = 1000
_STREAM_YIELD_INTERVAL = 3

async def send_all_async(sock, data):
    mv = memoryview(data)
    sent = 0
    sent_since_yield = 0
    consecutive_zeros = 0  # Track consecutive zero returns (indicates connection issue)
    max_consecutive_zeros = 10  # Max zero returns before raising error
    
    # Cache socket method lookup for performance (avoid repeated hasattr checks)
    write_method = sock.write if hasattr(sock, "write") else (sock.send if hasattr(sock, "send") else None)
    if write_method is None:
        raise OSError(-1, "Socket is invalid")

    while sent < len(mv):
        try:
            # Socket write is blocking in MicroPython - blocks until data is transmitted
            # Write as much as possible in one call to maximize throughput
            n = write_method(mv[sent:])

            if n > 0:
                sent += n
                sent_since_yield += n
                consecutive_zeros = 0  # Reset counter on successful write
                
                # Yield periodically after write to allow other tasks to run
                # Only yield if threshold reached - no sleep to maximize throughput
                if sent_since_yield >= _STREAM_YIELD_EVERY_BYTES:
                    sent_since_yield = 0
                    await asyncio.sleep(0)  # Just yield, no sleep delay
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
        except OSError:
            # Re-raise OSError to be caught by caller
            raise
        except Exception as exc:
            # Wrap other exceptions as OSError for consistent handling
            raise OSError(-1, f"Error during socket write: {exc}")

async def send_bytes_chunked_async(sock, data):
    # Optimization: For small data, send directly without chunking overhead
    # For large data, send_all_async already handles efficient chunking internally
    # This function now just delegates to send_all_async to avoid double-chunking
    await send_all_async(sock, data)

async def send_jpeg_frame_async(sock, jpeg_data, perf_data=None):
    # Build header efficiently using pre-encoded static parts
    header = _FRAME_HEADER_PREFIX + str(len(jpeg_data)).encode('utf-8') + _FRAME_HEADER_SUFFIX

    # Throughput optimization: Combine header + first chunk of data to reduce syscalls
    # This reduces the number of socket write operations, improving WiFi efficiency
    # Only combine if first chunk is reasonably sized (not too large to avoid memory issues)
    t_frame_send = time.ticks_ms()
    try:
        # Throughput optimization: Batch header with data to reduce syscalls
        # For small frames: send header + data + terminator in one operation
        # For large frames: send header + first chunk, then remaining chunks
        frame_size = len(jpeg_data)
        header_size = len(header)
        terminator_size = 2  # b"\r\n"

        # Calculate how much data we can fit with header in first chunk
        max_first_chunk = _STREAM_CHUNK_SIZE - header_size - terminator_size

        if frame_size <= max_first_chunk:
            # Small frame: send everything together (header + data + terminator)
            # This is the most efficient - single syscall for entire frame
            combined = header + jpeg_data + b"\r\n"
            await send_all_async(sock, combined)
        else:
            # Large frame: send header + first chunk together, then rest
            # This reduces syscalls from 3 to 2 for most frames
            first_chunk_size = max_first_chunk if max_first_chunk > 0 else _STREAM_CHUNK_SIZE
            # Send header + first chunk together
            combined = header + jpeg_data[:first_chunk_size]
            await send_all_async(sock, combined)
            # Send remaining data + terminator
            remaining = jpeg_data[first_chunk_size:] + b"\r\n"
            await send_all_async(sock, remaining)
    except OSError as exc:
        # Connection died during frame transmission - this is the "unexpected EOF" case
        raise OSError(-104, f"Connection reset during frame transmission: {exc}")
    t_frame_send_end = time.ticks_ms()

    # Store frame send time (the bottleneck) - optimized: use running sum instead of list
    if perf_data:
        frame_send_time = time.ticks_diff(t_frame_send_end, t_frame_send)
        perf_data['frame_send_sum'] += frame_send_time

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
        
        # Pre-calculate sleep constants for multi-stage sleep optimization
        # These avoid repeated calculations and use multiplication instead of division
        if frame_ms > 0:
            min_delay_ms = max(1, int(frame_ms * 0.1))  # 10% of frame budget, at least 1ms
            min_delay_s = min_delay_ms * 0.001  # Pre-calculate in seconds
            chunk_25ms = 0.025  # 25ms chunk size in seconds
            chunk_50ms = 0.05   # 50ms chunk size in seconds
        else:
            min_delay_ms = 1
            min_delay_s = 0.001
            chunk_25ms = 0.025
            chunk_50ms = 0.05

        # Validate capture function once before streaming - fail fast with clear error
        await validate_capture_function(capture_frame_func)

        while True:
            # Check if duration has elapsed
            if _check_duration_elapsed(duration_ms, start_time):
                if debug:
                    print(f"Streaming duration ({stream_duration}s) elapsed, stopping...")
                break

            # Wait for network connection before attempting to stream
            # This prevents wasted connection attempts when network isn't ready
            if hasattr(client_instance, 'network') and not client_instance.network.is_connected():
                if debug:
                    print("Streaming: Waiting for network connection...")
                await asyncio.sleep(1.0)  # Check every 1 second
                continue

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
                # Optimized: use running sums instead of storing all values to reduce overhead
                perf_data = None
                if debug:
                    perf_data = {
                        'send_sum': 0,           # Running sum of send times
                        'total_sum': 0,         # Running sum of total times
                        'size_sum': 0,          # Running sum of frame sizes
                        'frame_send_sum': 0,    # Running sum of frame send times
                        'count': 0,             # Number of frames in current period
                        'max_total': 0,         # Maximum total time
                        'min_total': 999999,    # Minimum total time
                        'behind_count': 0,
                        'frames_dropped': 0,
                        'last_stats_time': time.ticks_ms(),
                        'last_stats_frame': 1,
                    }

                while True:
                    t0 = time.ticks_ms()

                    # Adaptive frame dropping: skip frames if network is congested
                    # More aggressive dropping to handle network congestion spikes
                    # Optimized: use running sum instead of sum() every frame
                    should_skip = False
                    if len(recent_send_times) >= 2:
                        # Check recent average send time
                        avg_recent_send = recent_send_sum / len(recent_send_times)
                        # Also check the most recent send time for immediate response to spikes
                        last_send_time = recent_send_times[-1] if recent_send_times else 0
                        
                        # Moderate congestion: skip every other frame (2x budget)
                        # Severe congestion: skip 2 out of 3 frames (4x budget)
                        # Extreme congestion: skip 3 out of 4 frames (6x budget)
                        # Raised thresholds slightly to avoid premature dropping while still protecting against severe congestion
                        if avg_recent_send > frame_ms * 6 or last_send_time > frame_ms * 6:
                            # Extreme: skip 3 out of 4 frames
                            should_skip = (frame_count % 4 != 0)
                        elif avg_recent_send > frame_ms * 4 or last_send_time > frame_ms * 4:
                            # Severe: skip 2 out of 3 frames
                            should_skip = (frame_count % 3 != 0)
                        elif avg_recent_send > frame_ms * 2 or last_send_time > frame_ms * 2:
                            # Moderate: skip every other frame
                            should_skip = (frame_count % 2 == 0)

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
                    # Optimized: use running sums instead of lists to reduce overhead
                    if perf_data:
                        send_time = time.ticks_diff(t_send_end, t_send_start)
                        total_time = time.ticks_diff(time.ticks_ms(), t0)
                        perf_data['send_sum'] += send_time
                        perf_data['total_sum'] += total_time
                        perf_data['size_sum'] += len(jpeg_data)
                        perf_data['count'] += 1
                        # Track min/max as we go (no list needed)
                        if perf_data['count'] == 1:
                            # First frame: initialize min/max
                            perf_data['max_total'] = total_time
                            perf_data['min_total'] = total_time
                        else:
                            if total_time > perf_data['max_total']:
                                perf_data['max_total'] = total_time
                            if total_time < perf_data['min_total']:
                                perf_data['min_total'] = total_time

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

                    # Frame pacing - optimized multi-stage sleep with pre-calculated constants
                    # This ensures consistent timing regardless of target FPS (5-30 FPS)
                    # Uses multiplication instead of division and caches time.ticks_ms() call
                    if frame_ms > 0:
                        # Cache time.ticks_ms() call to avoid double call overhead
                        t_now = time.ticks_ms()
                        elapsed = time.ticks_diff(t_now, t0)
                        delay_ms = frame_ms - elapsed

                        if delay_ms > 0:
                            # Ahead of schedule - multi-stage sleep for optimal responsiveness
                            # Stage 1: Very small delays (<=20ms) - single sleep, minimal overhead
                            if delay_ms <= 20:
                                await asyncio.sleep(delay_ms * 0.001)
                            # Stage 2: Small delays (20-50ms) - single sleep, typical at 20 FPS
                            elif delay_ms <= 50:
                                await asyncio.sleep(delay_ms * 0.001)
                            # Stage 3: Medium delays (50-100ms) - 25ms chunks for better responsiveness
                            # Common at 15 FPS, allows other tasks to run more frequently
                            elif delay_ms <= 100:
                                chunk_size = 25
                                chunks = int(delay_ms / chunk_size)
                                remainder = delay_ms % chunk_size
                                for _ in range(chunks):
                                    await asyncio.sleep(chunk_25ms)  # Pre-calculated constant
                                if remainder > 0:
                                    await asyncio.sleep(remainder * 0.001)
                            # Stage 4: Large delays (>100ms) - 50ms chunks for very low FPS
                            else:
                                chunk_size = 50
                                chunks = int(delay_ms / chunk_size)
                                remainder = delay_ms % chunk_size
                                for _ in range(chunks):
                                    await asyncio.sleep(chunk_50ms)  # Pre-calculated constant
                                if remainder > 0:
                                    await asyncio.sleep(remainder * 0.001)
                        else:
                            # Behind schedule - maintain minimum spacing to prevent bursts
                            # This prevents overwhelming the network with back-to-back frames
                            # which can make congestion worse. Minimum delay is 10% of frame budget
                            # (e.g., ~6.6ms for 15 FPS, ~5ms for 20 FPS) to allow network to process
                            if perf_data:
                                perf_data['behind_count'] += 1
                            # Always maintain minimum spacing to prevent network bursts
                            # Uses pre-calculated min_delay_s to avoid repeated calculation
                            await asyncio.sleep(min_delay_s)

                    # Print performance statistics periodically (only if debug enabled)
                    # Optimized: use running sums instead of lists to reduce overhead
                    if debug and frame_count % 60 == 0:  # Every 60 frames (~2.4s at 25 FPS)
                        elapsed_stats = time.ticks_diff(time.ticks_ms(), perf_data['last_stats_time'])
                        frames_in_period = frame_count - perf_data['last_stats_frame']
                        actual_fps = (frames_in_period * 1000.0) / elapsed_stats if elapsed_stats > 0 else 0

                        if perf_data['count'] > 0:
                            # Calculate averages from running sums (no sum() overhead)
                            avg_send = perf_data['send_sum'] / perf_data['count']
                            avg_total = perf_data['total_sum'] / perf_data['count']
                            max_total = perf_data['max_total']
                            min_total = perf_data['min_total']
                            avg_size = perf_data['size_sum'] / perf_data['count']
                            behind_pct = (perf_data['behind_count'] / perf_data['count']) * 100 if perf_data['count'] > 0 else 0

                            # Calculate effective network bandwidth from frame send times
                            avg_frame_send = 0
                            effective_bandwidth_mbps = 0
                            if perf_data['frame_send_sum'] > 0:
                                avg_frame_send = perf_data['frame_send_sum'] / perf_data['count']
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
                            
                            # Reset stats for next period (optimized: reset running sums)
                            perf_data['send_sum'] = 0
                            perf_data['total_sum'] = 0
                            perf_data['size_sum'] = 0
                            perf_data['frame_send_sum'] = 0
                            perf_data['count'] = 0
                            perf_data['max_total'] = 0
                            perf_data['min_total'] = 999999
                            perf_data['behind_count'] = 0
                            perf_data['frames_dropped'] = 0
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
