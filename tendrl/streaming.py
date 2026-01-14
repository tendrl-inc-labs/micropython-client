import time
import asyncio
import gc

MAX_FPS = 30
BOUNDARY = "tendrl"
_FRAME_HEADER_PREFIX = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ".encode('utf-8')
_FRAME_HEADER_SUFFIX = b"\r\n\r\n"
_STREAM_CHUNK_SIZE = 8192
_STREAM_YIELD_EVERY_BYTES = 32 * 1024
_STREAM_YIELD_MS = 0
_STREAM_GC_INTERVAL = 250
_STREAM_RECONNECT_DELAY = 1000
_STREAM_YIELD_INTERVAL = 3

async def send_all_async(sock, data):
    mv = memoryview(data)
    sent = 0
    sent_since_yield = 0
    consecutive_zeros = 0
    max_consecutive_zeros = 10

    write_method = sock.write if hasattr(sock, "write") else (sock.send if hasattr(sock, "send") else None)
    if write_method is None:
        raise OSError(-1, "Socket is invalid")

    while sent < len(mv):
        try:
            n = write_method(mv[sent:])

            if n > 0:
                sent += n
                sent_since_yield += n
                consecutive_zeros = 0
                if sent_since_yield >= _STREAM_YIELD_EVERY_BYTES:
                    sent_since_yield = 0
                    await asyncio.sleep(0)
            elif n == 0:
                consecutive_zeros += 1
                if consecutive_zeros >= max_consecutive_zeros:
                    raise OSError(-1, "Socket write returned 0 multiple times - connection may be dead")
                wait_time = min(0.01 * consecutive_zeros, 0.1)  # Progressive backoff, max 100ms
                await asyncio.sleep(wait_time)
                continue
            else:
                raise OSError(-1, f"Socket write returned {n}")
        except OSError:
            raise
        except Exception as exc:
            raise OSError(-1, f"Error during socket write: {exc}")

async def send_bytes_chunked_async(sock, data):
    await send_all_async(sock, data)

async def send_jpeg_frame_async(sock, jpeg_data, perf_data=None):
    header = _FRAME_HEADER_PREFIX + str(len(jpeg_data)).encode('utf-8') + _FRAME_HEADER_SUFFIX

    t_frame_send = time.ticks_ms()
    try:
        frame_size = len(jpeg_data)
        header_size = len(header)
        terminator_size = 2

        max_first_chunk = _STREAM_CHUNK_SIZE - header_size - terminator_size

        if frame_size <= max_first_chunk:
            combined = header + jpeg_data + b"\r\n"
            await send_all_async(sock, combined)
        else:
            first_chunk_size = max_first_chunk if max_first_chunk > 0 else _STREAM_CHUNK_SIZE
            combined = header + jpeg_data[:first_chunk_size]
            await send_all_async(sock, combined)
            remaining = jpeg_data[first_chunk_size:] + b"\r\n"
            await send_all_async(sock, remaining)
    except OSError as exc:
        raise OSError(-104, f"Connection reset during frame transmission: {exc}")
    t_frame_send_end = time.ticks_ms()

    if perf_data:
        frame_send_time = time.ticks_diff(t_frame_send_end, t_frame_send)
        perf_data['frame_send_sum'] += frame_send_time

def create_stream_request(server_host, api_key):
    auth_header = ""
    if api_key:
        auth_header = f"Authorization: Bearer {api_key}\r\n"

    content_length = 10 * 1024 * 1024

    return (
        "POST /api/stream HTTP/1.1\r\n"
        f"Host: {server_host}\r\n"
        "Connection: keep-alive\r\n"
        f"Content-Type: multipart/x-mixed-replace; boundary={BOUNDARY}\r\n"
        f"Content-Length: {content_length}\r\n"
        f"{auth_header}"
        "\r\n"
    ).encode('utf-8')

def _extract_hostname_from_url(url):
    if "://" in url:
        url = url.split("://", 1)[1]
    if "/" in url:
        url = url.split("/", 1)[0]
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
    await asyncio.sleep(0)
    result = capture_frame_func()
    if hasattr(result, '__await__'):
        result = await result
    await asyncio.sleep(0)

    if isinstance(result, tuple):
        frame_data = result[0]
    else:
        frame_data = result

    if validate:
        if not isinstance(frame_data, (bytes, bytearray)) or not frame_data or len(frame_data) == 0:
            raise ValueError(f"Invalid frame: expected non-empty bytes/bytearray, got {type(frame_data).__name__}")

    return frame_data

def _check_duration_elapsed(duration_ms, start_time):
    if duration_ms and start_time:
        return time.ticks_diff(time.ticks_ms(), start_time) >= duration_ms
    return False

async def _connect_to_server(server_host, port, debug=False):
    import socket
    import ssl

    s = None
    try:
        await asyncio.sleep(0)
        s = socket.socket()
        addr = socket.getaddrinfo(server_host, port)[0][-1]
        await asyncio.sleep(0)

        await asyncio.sleep(0)
        s.connect(addr)
        await asyncio.sleep(0)

        await asyncio.sleep(0)
        s = ssl.wrap_socket(s, server_hostname=server_host)
        await asyncio.sleep(0)

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

async def _check_stream_permission(client_instance, debug=False):
    import requests

    app_url = client_instance.config.get("app_url", "https://app.tendrl.com")
    api_key = client_instance.config.get("api_key", "")

    if not api_key:
        if debug:
            print("Streaming: No API key configured - cannot check streaming permission")
        return True  # Continue anyway

    permission_url = f"{app_url}/api/stream/permission"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(permission_url, headers=headers)

        status_code = response.status_code
        try:
            response_data = response.json()
        except (ValueError, AttributeError):
            response_data = {}
        response.close()

        if status_code == 200:
            return True
        elif status_code == 401 or status_code == 403:
            error_message = response_data.get('reason', 'Unauthorized: Missing entity:Stream permission')
            if debug:
                print(f"Streaming: Permission check failed ({status_code}): {error_message}")
            return True  # Continue anyway
        else:
            error_message = response_data.get('reason', f"Server error ({status_code})")
            if debug:
                print(f"Streaming: Permission check error: {error_message}")
            return True  # Continue anyway
    except Exception as e:
        if debug:
            print(f"Streaming: Could not check permission ({e}), will attempt stream anyway")
        return True  # Continue anyway

async def _send_first_frame(sock, capture_frame_func, server_host, api_key, debug=False):
    try:
        first_frame = await _capture_frame(capture_frame_func)
    except Exception:
        raise

    content_length_str = str(len(first_frame)).encode('utf-8')
    frame_header = _FRAME_HEADER_PREFIX + content_length_str + _FRAME_HEADER_SUFFIX

    request_headers = create_stream_request(server_host, api_key)

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
        return True, 0
    except OSError:
        consecutive_errors += 1

        if consecutive_errors >= max_consecutive_errors:
            return False, consecutive_errors

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
        await asyncio.sleep(0)
        test_result = capture_frame_func()
        if hasattr(test_result, '__await__'):
            test_result = await test_result
        await asyncio.sleep(0)

        if isinstance(test_result, tuple) and len(test_result) == 2:
            test_frame, _ = test_result
        else:
            test_frame = test_result

        if not isinstance(test_frame, (bytes, bytearray)):
            raise TypeError(
                f"capture_frame_func must return bytes or bytearray, got {type(test_frame).__name__}. "
                f"It can also return a tuple of (bytes/bytearray, timestamp)."
            )

        if not test_frame or len(test_frame) == 0:
            raise ValueError(
                "capture_frame_func returned empty frame. "
                "The function must return non-empty bytes or bytearray."
            )
    except TypeError:
        raise
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Error testing capture_frame_func: {e}. "
            f"Please ensure the function is properly configured and returns bytes/bytearray."
        ) from e

def start_jpeg_stream(client_instance, capture_frame_func, target_fps=15,
                     stream_duration=-1, debug=False):
    if target_fps > MAX_FPS:
        raise ValueError(
            f"Target FPS ({target_fps}) exceeds server maximum ({MAX_FPS} FPS). "
            f"Please set target_fps to {MAX_FPS} or lower."
        )
    elif target_fps <= 0:
        raise ValueError(
            f"Invalid target_fps ({target_fps}). Must be greater than 0 and not exceed {MAX_FPS} FPS."
        )

    app_url = client_instance.config.get("app_url", "https://app.tendrl.com")
    server_host = _extract_hostname_from_url(app_url)
    port = 443
    frame_ms = 1000 // target_fps if target_fps > 0 else 0

    api_key = client_instance.config.get("api_key", "")

    async def stream_loop():
        s = None
        duration_ms = int(stream_duration * 1000) if stream_duration > 0 else None
        start_time = time.ticks_ms() if duration_ms else None
        frame_s = frame_ms / 1000.0 if frame_ms > 0 else 0.1

        if frame_ms > 0:
            min_delay_ms = max(1, int(frame_ms * 0.1))
            min_delay_s = min_delay_ms * 0.001
            chunk_25ms = 0.025
            chunk_50ms = 0.05
        else:
            min_delay_ms = 1
            min_delay_s = 0.001
            chunk_25ms = 0.025
            chunk_50ms = 0.05

        await validate_capture_function(capture_frame_func)
        await _check_stream_permission(client_instance, debug=debug)

        max_initial_wait = 10
        wait_start = time.ticks_ms()

        while True:
            elapsed = time.ticks_diff(time.ticks_ms(), wait_start)
            if elapsed > max_initial_wait * 1000:
                if debug:
                    print("Streaming: Initial connection wait timeout, proceeding anyway")
                break

            network_ready = not hasattr(client_instance, 'network') or client_instance.network.is_connected()
            mqtt_ready = client_instance.mqtt is None or client_instance.mqtt.connected
            client_ready = client_instance.client_enabled

            if network_ready and mqtt_ready and client_ready:
                if debug:
                    print("Streaming: All connections ready")
                break

            await asyncio.sleep(0.5)

        while True:
            if _check_duration_elapsed(duration_ms, start_time):
                if debug:
                    print(f"Streaming duration ({stream_duration}s) elapsed, stopping...")
                break

            if hasattr(client_instance, 'network') and not client_instance.network.is_connected():
                if debug:
                    print("Streaming: Waiting for network connection...")
                await asyncio.sleep(1.0)
                continue

            if client_instance.mqtt is not None and not client_instance.mqtt.connected:
                max_wait_time = 30
                wait_start = time.ticks_ms()
                while client_instance.mqtt is not None and not client_instance.mqtt.connected:
                    elapsed = time.ticks_diff(time.ticks_ms(), wait_start)
                    if elapsed > max_wait_time * 1000:
                        break
                    await asyncio.sleep(0.5)
            try:
                try:
                    s = await _connect_to_server(server_host, port, debug=debug)
                except Exception:
                    await asyncio.sleep(_STREAM_RECONNECT_DELAY / 1000.0)
                    continue

                if not api_key and debug:
                    print("Warning: No API key found in config")

                try:
                    await _send_first_frame(
                        s, capture_frame_func, server_host, api_key,
                        debug=debug
                    )
                except Exception:
                    raise

                frame_count = 1
                consecutive_errors = 0
                max_consecutive_errors = 3
                gc_check_interval = _STREAM_GC_INTERVAL if _STREAM_GC_INTERVAL > 0 else 0
                yield_check_interval = _STREAM_YIELD_INTERVAL if _STREAM_YIELD_INTERVAL > 0 else 0

                recent_send_times = []
                max_recent_times = 5
                recent_send_sum = 0
                frames_dropped = 0

                perf_data = None
                if debug:
                    perf_data = {
                        'send_sum': 0,
                        'total_sum': 0,
                        'size_sum': 0,
                        'frame_send_sum': 0,
                        'count': 0,
                        'max_total': 0,
                        'min_total': 999999,
                        'behind_count': 0,
                        'frames_dropped': 0,
                        'last_stats_time': time.ticks_ms(),
                        'last_stats_frame': 1,
                    }

                while True:
                    t0 = time.ticks_ms()

                    should_skip = False
                    if len(recent_send_times) >= 2:
                        avg_recent_send = recent_send_sum / len(recent_send_times)
                        last_send_time = recent_send_times[-1] if recent_send_times else 0

                        if avg_recent_send > frame_ms * 6 or last_send_time > frame_ms * 6:
                            should_skip = (frame_count % 4 != 0)
                        elif avg_recent_send > frame_ms * 4 or last_send_time > frame_ms * 4:
                            should_skip = (frame_count % 3 != 0)
                        elif avg_recent_send > frame_ms * 2 or last_send_time > frame_ms * 2:
                            should_skip = (frame_count % 2 == 0)

                    try:
                        jpeg_data = await _capture_frame(capture_frame_func, validate=False)
                    except Exception as func_err:
                        if debug:
                            print(f"Error in capture function: {func_err}")
                        await asyncio.sleep(frame_s)
                        continue

                    if should_skip:
                        frames_dropped += 1
                        if perf_data:
                            perf_data['frames_dropped'] = frames_dropped
                        frame_count += 1
                        if frame_ms > 0:
                            await asyncio.sleep(frame_s)
                        continue

                    t_send_start = time.ticks_ms()

                    success, consecutive_errors = await _send_frame_async(
                        s, jpeg_data,
                        consecutive_errors, max_consecutive_errors, debug=debug, perf_data=perf_data
                    )

                    if success:
                        send_duration = time.ticks_diff(time.ticks_ms(), t_send_start)
                        recent_send_times.append(send_duration)
                        recent_send_sum += send_duration
                        if len(recent_send_times) > max_recent_times:
                            removed = recent_send_times.pop(0)
                            recent_send_sum -= removed

                    if not success:
                        if consecutive_errors >= max_consecutive_errors:
                            break
                        continue

                    t_send_end = time.ticks_ms()
                    frame_count += 1

                    if perf_data:
                        send_time = time.ticks_diff(t_send_end, t_send_start)
                        total_time = time.ticks_diff(time.ticks_ms(), t0)
                        perf_data['send_sum'] += send_time
                        perf_data['total_sum'] += total_time
                        perf_data['size_sum'] += len(jpeg_data)
                        perf_data['count'] += 1
                        if perf_data['count'] == 1:
                            perf_data['max_total'] = total_time
                            perf_data['min_total'] = total_time
                        else:
                            if total_time > perf_data['max_total']:
                                perf_data['max_total'] = total_time
                            if total_time < perf_data['min_total']:
                                perf_data['min_total'] = total_time

                    if duration_ms and (frame_count % 10 == 0):
                        if _check_duration_elapsed(duration_ms, start_time):
                            if debug:
                                print(f"Streaming duration ({stream_duration}s) elapsed, stopping...")
                            break

                    if gc_check_interval > 0 and (frame_count % gc_check_interval) == 0:
                        await asyncio.sleep(0)
                        gc.collect()
                        await asyncio.sleep(0)

                    if yield_check_interval > 0 and (frame_count % yield_check_interval) == 0:
                        await asyncio.sleep(0)

                    if frame_ms > 0:
                        t_now = time.ticks_ms()
                        elapsed = time.ticks_diff(t_now, t0)
                        delay_ms = frame_ms - elapsed

                        if delay_ms > 0:
                            if delay_ms <= 20:
                                await asyncio.sleep(delay_ms * 0.001)
                            elif delay_ms <= 50:
                                await asyncio.sleep(delay_ms * 0.001)
                            elif delay_ms <= 100:
                                chunk_size = 25
                                chunks = int(delay_ms / chunk_size)
                                remainder = delay_ms % chunk_size
                                for _ in range(chunks):
                                    await asyncio.sleep(chunk_25ms)  # Pre-calculated constant
                                if remainder > 0:
                                    await asyncio.sleep(remainder * 0.001)
                            else:
                                chunk_size = 50
                                chunks = int(delay_ms / chunk_size)
                                remainder = delay_ms % chunk_size
                                for _ in range(chunks):
                                    await asyncio.sleep(chunk_50ms)  # Pre-calculated constant
                                if remainder > 0:
                                    await asyncio.sleep(remainder * 0.001)
                        else:
                            if perf_data:
                                perf_data['behind_count'] += 1
                            await asyncio.sleep(min_delay_s)

                    if debug and frame_count % 60 == 0:
                        elapsed_stats = time.ticks_diff(time.ticks_ms(), perf_data['last_stats_time'])
                        frames_in_period = frame_count - perf_data['last_stats_frame']
                        actual_fps = (frames_in_period * 1000.0) / elapsed_stats if elapsed_stats > 0 else 0

                        if perf_data['count'] > 0:
                            avg_send = perf_data['send_sum'] / perf_data['count']
                            avg_total = perf_data['total_sum'] / perf_data['count']
                            max_total = perf_data['max_total']
                            min_total = perf_data['min_total']
                            avg_size = perf_data['size_sum'] / perf_data['count']
                            behind_pct = (perf_data['behind_count'] / perf_data['count']) * 100 if perf_data['count'] > 0 else 0

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
                if debug:
                    errno = e.args[0] if e.args else 'unknown'
                    if errno != -104:
                        err_msg = _format_connection_error_message(errno)
                        if err_msg:
                            print(f"Stream error: {err_msg}")
            except Exception as e:
                if debug:
                    print(f"Stream ended: {e} (type: {type(e).__name__})")

            finally:
                try:
                    if s:
                        s.close()
                except Exception:
                    pass
                s = None

            await asyncio.sleep(_STREAM_RECONNECT_DELAY / 1000.0)

    return stream_loop
