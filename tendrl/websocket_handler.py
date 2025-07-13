import json
import time
import _thread
from .lib.websockets import connect, ConnectionError, ConnectionClosed


class WSHandler:
    def __init__(self, config, debug=False):
        self._ws = None
        self._ws_lock = _thread.allocate_lock()
        self.config = config
        self.debug = debug
        self.connected = False
        self._consecutive_errors = 0
        self._max_batch_size = 4096
        self._max_messages_per_batch = 50
        self._reconnect_delay = 5

    def connect(self, jti, e_type):
        self.connected = False
        self._consecutive_errors = 0
        if not jti or not e_type:
            print("Invalid JTI or entity type")
            return False
        app_url = (
            self.config.get("app_url", "")
            .replace("http://", "ws://")
            .replace("https://", "wss://")
        )
        if not app_url:
            print("Missing app_url in configuration")
            return False
        api_key = self.config.get("api_key")
        if not api_key:
            print("Missing API key in configuration")
            return False
        ws_url = f"{app_url}/api/entities/ws/{jti}?e_type={e_type}"
        self._last_jti = jti
        self._last_e_type = e_type
        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if self._ws:
                        try:
                            self._ws.close()
                        except Exception as close_err:
                            print(f"Error closing existing websocket: {close_err}")
                    self._ws = connect(
                        ws_url,
                        api_key,
                    )
                    if not self._ws:
                        self.connected = False
                        print(
                            f"Websocket connection failed: No socket created (Attempt {attempt + 1})"
                        )
                        time.sleep(2**attempt)  # Exponential backoff
                        continue
                    if hasattr(self._ws, "sock") and not self._ws.sock:
                        self.connected = False
                        print(
                            f"Websocket connection failed: No underlying socket (Attempt {attempt + 1})"
                        )
                        time.sleep(2**attempt)  # Exponential backoff
                        continue
                    self.connected = True
                    self._consecutive_errors = 0
                    return True
                except (ConnectionError, ConnectionClosed) as conn_err:
                    print(
                        f"Websocket connection error (Attempt {attempt + 1}): {conn_err}"
                    )
                    self.connected = False
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                except Exception as e:
                    print(
                        f"Unexpected websocket connection error (Attempt {attempt + 1}): {e}"
                    )
                    self.connected = False
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
            self._ws = None
            self.connected = False
            return False
        except Exception as overall_err:
            print(f"Critical websocket connection failure: {overall_err}")
            self._ws = None
            self.connected = False
            return False

    def _try_reconnect(self):
        self.connected = False
        try:
            if self._ws:
                print("Closing existing WebSocket")
                self._ws.close()
        except Exception as close_err:
            print(f"Error closing existing socket: {close_err}")
        self._ws = None
        if not hasattr(self, "_last_jti") or not hasattr(self, "_last_e_type"):
            return False
        reconnect_delays = [1, 2, 5, 10]  # Increasing delay between attempts
        for attempt, delay in enumerate(reconnect_delays, 1):
            time.sleep(delay)
            try:
                connection_result = self.connect(self._last_jti, self._last_e_type)
                if connection_result:
                    self._consecutive_errors = 0
                    return True
                else:
                    print(f"Reconnection attempt {attempt} failed")
            except ConnectionClosed:
                print("Websocket connection closed during reconnection attempt")
                self._ws = None
                self.connected = False
                return False
            except Exception as reconnect_err:
                print(
                    f"Reconnection attempt {attempt} failed with error: {reconnect_err}"
                )
        self.connected = False
        return False

    def send_message(self, msg, max_retries=1):
        if not self._ws or not self.connected:
            if max_retries <= 0:
                return {
                    "code": 500,
                    "content": "Connection failed after multiple attempts",
                }
            try:
                if not self._try_reconnect():
                    print("Reconnection failed")
                    return {"code": 500, "content": "Connection failed"}
            except Exception as reconnect_err:
                print(f"Unexpected reconnection error: {reconnect_err}")
                return {
                    "code": 500,
                    "content": f"Reconnection error: {str(reconnect_err)}",
                }
        with self._ws_lock:
            try:
                encoded_msg = json.dumps(msg).encode("utf-8")
                print(f"[WSHandler] Sending message: {encoded_msg}")
            except Exception as encode_err:
                print(f"Encoding error: {encode_err}")
                return {"code": 400, "content": f"Encoding error: {str(encode_err)}"}
            if len(encoded_msg) > self._max_batch_size:
                error_msg = f"Message too large: {len(encoded_msg)} bytes (max: {self._max_batch_size})"
                print(f"{error_msg}")
                return {"code": 413, "content": error_msg}
            try:
                self._ws.send(encoded_msg)
                print("[WSHandler] Message sent, waiting for response...")
                time.sleep(0.02)
                try:
                    response = self._ws.recv()
                    print(f"[WSHandler] Received response: {response}")
                    if response == "":
                        # No data available, treat as non-fatal (wait for next message)
                        return {"code": 204, "content": "No response data (empty frame)"}
                    try:
                        parsed_response = json.loads(response)
                        return parsed_response
                    except Exception:
                        print(f"[WSHandler] Invalid response format: {response}")
                        return {"code": 500, "content": "Invalid response format"}
                except Exception as recv_err:
                    # Only treat as error if not NoDataException
                    if hasattr(recv_err, '__class__') and recv_err.__class__.__name__ == 'NoDataException':
                        print("No data available after send, not closing connection.")
                        return {"code": 204, "content": "No response data (NoDataException)"}
                    print(f"[WSHandler] Response receive error: {recv_err}")
                    # Attempt to resend with one retry
                    if max_retries > 0:
                        return self.send_message(msg, max_retries - 1)
                    return {
                        "code": 500,
                        "content": f"Response receive error: {str(recv_err)}",
                    }
            except (ConnectionError, ConnectionClosed) as conn_err:
                if self.debug:
                    print(f"Connection error: {conn_err}")
                self._ws = None
                self.connected = False
                if max_retries > 0:
                    return self.send_message(msg, max_retries - 1)
                return {"code": 500, "content": f"Connection error: {str(conn_err)}"}
            except Exception as send_err:
                print(f"[WSHandler] Error details: {str(send_err)}")
                self.connected = False
                if max_retries > 0:
                    return self.send_message(msg, max_retries - 1)
                return {"code": 500, "content": f"Send error: {str(send_err)}"}

    def _chunk_messages(self, messages):
        chunks = []
        current_chunk = []
        array_overhead = 2
        for msg in messages:
            msg_json = json.dumps(msg)
            msg_size = len(msg_json.encode("utf-8")) + 1
            current_size = array_overhead
            if current_chunk:
                current_size += sum(
                    len(json.dumps(m).encode("utf-8")) + 1 for m in current_chunk
                )
            if current_chunk and (
                current_size + msg_size > self._max_batch_size - 10
            ):
                chunks.append(current_chunk)
                current_chunk = [msg]
            else:
                current_chunk.append(msg)
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def send_batch(self, messages):
        if not self._ws or not self.connected:
            if self._try_reconnect():
                return self.send_batch(messages)
            return None
        try:
            from .utils.util_helpers import make_message

            processed_messages = []
            for msg in messages:
                if isinstance(msg, dict) and "msg_type" in msg:
                    processed_messages.append(msg)
                else:
                    processed_messages.append(make_message(msg, "publish"))
            chunks = self._chunk_messages(processed_messages)
            all_responses = []
            with self._ws_lock:
                for chunk_index, chunk in enumerate(chunks, 1):
                    try:
                        encoded_chunk = json.dumps(chunk).encode("utf-8")
                        print(f"[WSHandler] Sending batch chunk {chunk_index}: {encoded_chunk}")
                        if len(encoded_chunk) > self._max_batch_size:
                            chunk_responses = []
                            for msg in chunk:
                                try:
                                    msg_response = self.send_message(msg)
                                    chunk_responses.append(msg_response)
                                except Exception as individual_send_err:
                                    print(
                                        f"Error sending individual message: {individual_send_err}"
                                    )
                                    # Store failed message back to offline queue if needed
                                    chunk_responses.append(
                                        {
                                            "code": 500,
                                            "content": f"Send error: {str(individual_send_err)}",
                                        }
                                    )
                            all_responses.extend(chunk_responses)
                            continue
                        self._ws.send(encoded_chunk)
                        print(f"[WSHandler] Batch chunk {chunk_index} sent, waiting for response...")
                        try:
                            response = self._ws.recv()
                            print(f"[WSHandler] Received batch response: {response}")
                            resp_data = json.loads(response)
                            if isinstance(resp_data, dict):
                                code = resp_data.get("code")
                                if code == 401:
                                    print("Unauthorized access")
                                    self.connected = False
                                    return resp_data
                                elif code == 400:
                                    print(f"Bad request: {resp_data.get('content')}")
                                    return resp_data
                            all_responses.append(resp_data)
                        except Exception as recv_err:
                            self._consecutive_errors += 1
                            self.connected = False
                            print(f"[WSHandler] Batch response receive error: {recv_err}")
                            return {"code": 500, "content": str(recv_err)}
                    except Exception as send_err:
                        self._consecutive_errors += 1
                        self.connected = False
                        print(f"[WSHandler] Error sending batch chunk {chunk_index}: {send_err}")
                        chunk_responses = []
                        for msg in chunk:
                            try:
                                msg_response = self.send_message(msg)
                                chunk_responses.append(msg_response)
                            except Exception as individual_send_err:
                                print(f"Error sending individual message: {individual_send_err}")
                                chunk_responses.append(
                                    {
                                        "code": 500,
                                        "content": f"Send error: {str(individual_send_err)}",
                                    }
                                )
                        all_responses.extend(chunk_responses)
                self._consecutive_errors = 0
                if not all_responses:
                    return {"code": 200, "content": ""}
                if len(all_responses) > 1:
                    combined_content = []
                    for resp in all_responses:
                        if isinstance(resp, dict) and "content" in resp:
                            if isinstance(resp["content"], list):
                                combined_content.extend(resp["content"])
                            else:
                                combined_content.append(resp["content"])
                    return {"code": 200, "content": combined_content}
                return all_responses[0]
        except Exception as overall_err:
            self._consecutive_errors += 1
            self.connected = False
            print(f"[WSHandler] Overall batch send error: {overall_err}")
            return {"code": 500, "content": str(overall_err)}

    def check_messages(self):
        return self.send_message({"msg_type": "msg_check"})

    def cleanup(self):
        if self._ws:
            try:
                self._ws.close()
            except:
                pass
            self._ws = None
            self.connected = False


