# Tendrl WebSocket Client
# 
# Based on: uwebsockets (https://github.com/danni/uwebsockets)
# Original License: MIT
#
# Copyright (c) Tendrl, Inc. 2025
#
# This file includes substantial modifications by Tendrl, Inc. to enhance
# robustness, SSL support, reconnection behavior, and error logging.
# These modifications are licensed under the MIT License + Commons Clause + Client Usage Restriction.
#
# Original MIT License:
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above rights are conditioned on the following restrictions:
# 1. The Software may not be sold or used to provide or host a commercial
#    service, such as SaaS, without explicit permission from Tendrl, Inc.
# 2. The Software is licensed for use exclusively with services operated by
#    or on behalf of Tendrl, Inc. Use with any other service is prohibited.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND...

import binascii
from collections import namedtuple
import random
import re
import socket
import ssl
import struct
import time


# Opcodes
OP_CONT = 0x0
OP_TEXT = 0x1
OP_BYTES = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

# Close codes
CLOSE_OK = 1000
CLOSE_GOING_AWAY = 1001
CLOSE_PROTOCOL_ERROR = 1002
CLOSE_DATA_NOT_SUPPORTED = 1003
CLOSE_BAD_DATA = 1007
CLOSE_POLICY_VIOLATION = 1008
CLOSE_TOO_BIG = 1009
CLOSE_MISSING_EXTN = 1010
CLOSE_BAD_CONDITION = 1011

URL_RE = re.compile(r"(wss|ws)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(/.+)?")
URI = namedtuple("URI", ("protocol", "hostname", "port", "path"))


class NoDataException(Exception):
    pass

class ConnectionClosed(Exception):
    pass

class ConnectionError(Exception):
    pass

def urlparse(uri):
    match = URL_RE.match(uri)
    if match:
        protocol = match.group(1)
        host = match.group(2)
        port = match.group(3)
        path = match.group(4)
        if protocol == "wss":
            if port is None:
                port = 443
        elif protocol == "ws":
            if port is None:
                port = 80
        else:
            raise ValueError("Scheme {} is invalid".format(protocol))
        return URI(protocol, host, int(port), path)

class Websocket:
    __slots__ = ("sock", "open", "_buffer_size", "_last_ping")
    is_client = False
    def __init__(self, sock, buffer_size=1024):
        self.sock = sock
        self.open = True
        self._buffer_size = buffer_size
        self._last_ping = 0
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        self.close()
    def settimeout(self, timeout):
        self.sock.settimeout(timeout)
    def read_frame(self, max_size=None):
        try:
            try:
                two_bytes = self.sock.read(2)
            except Exception as read_err:
                try:
                    print(f"[READ_FRAME] Error details: {repr(read_err)}")
                except:
                    pass
                raise
            if not two_bytes:
                raise NoDataException("No bytes could be read from socket")
            try:
                byte1, byte2 = struct.unpack("!BB", two_bytes)
            except struct.error as unpack_err:
                raise
            fin = bool(byte1 & 0x80)
            opcode = byte1 & 0x0F
            mask = bool(byte2 & (1 << 7))
            length = byte2 & 0x7F
            if length == 126:
                (length,) = struct.unpack("!H", self.sock.read(2))
            elif length == 127:
                (length,) = struct.unpack("!Q", self.sock.read(8))
            if max_size and length > max_size:
                print(f"[READ_FRAME] Frame of length {length} exceeds max_size {max_size}")
                self.close(code=CLOSE_TOO_BIG)
                return True, OP_CLOSE, None
            if mask:
                mask_bits = self.sock.read(4)
            data = bytearray()
            chunk_size = min(self._buffer_size, length)
            remaining = length
            while remaining > 0:
                chunk = self.sock.read(min(chunk_size, remaining))
                if not chunk:
                    raise ConnectionClosed("Empty chunk during frame read")
                data.extend(chunk)
                remaining -= len(chunk)
            if mask:
                for i in range(length):
                    data[i] ^= mask_bits[i % 4]
            return fin, opcode, bytes(data)
        except OSError as e:
            print(f"[READ_FRAME] Socket error: {e}")
            self._close()
            raise ConnectionClosed(f"OSError during frame read: {e}")
        except Exception as e:
            print(f"[READ_FRAME] Unexpected error: {type(e).__name__}")
            print(f"[READ_FRAME] Error details: {str(e)}")
            try:
                print(f"[READ_FRAME] Error repr: {repr(e)}")
            except:
                pass
            self._close()
            raise

    def write_frame(self, opcode, data=b""):
        fin = True
        mask = self.is_client
        length = len(data)
        byte1 = 0x80 if fin else 0
        byte1 |= opcode
        byte2 = 0x80 if mask else 0
        if length < 126:
            byte2 |= length
            self.sock.write(struct.pack("!BB", byte1, byte2))
        elif length < (1 << 16):
            byte2 |= 126
            self.sock.write(struct.pack("!BBH", byte1, byte2, length))
        elif length < (1 << 64):
            byte2 |= 127
            self.sock.write(struct.pack("!BBQ", byte1, byte2, length))
        else:
            raise ValueError()
        if mask:
            mask_bits = struct.pack("!I", random.getrandbits(32))
            self.sock.write(mask_bits)
            data = bytes(b ^ mask_bits[i % 4] for i, b in enumerate(data))
        self.sock.write(data)

    def recv(self, post_read_sleep=0.005, max_retries=3):
        assert self.open
        for attempt in range(max_retries):
            try:
                try:
                    import select
                    readiness_timeouts = [0, 0.1, 0.5, 1.0]
                    readable = False
                    for timeout in readiness_timeouts:
                        try:
                            readable, _, _ = select.select([self.sock], [], [], timeout)
                            if readable:
                                break
                        except Exception as select_err:
                            print(f"[RECV] Select error at {timeout}s timeout: {type(select_err).__name__}")
                            print(f"[RECV] Detailed error: {str(select_err)}")               
                    if not readable:
                        print("[RECV] Socket not readable, adding delay")
                        time.sleep(0.1 * (attempt + 1))
                        continue
                except Exception as select_err:
                    print(f"[RECV] Overall select error: {type(select_err).__name__}")
                    print(f"[RECV] Detailed error: {str(select_err)}")
                    time.sleep(0.5 * (attempt + 1))
                    continue
                try:
                    fin, opcode, data = self.read_frame()
                    if not fin:
                        print("[RECV] Received incomplete frame")
                        raise NotImplementedError("Incomplete frame received")
                    if opcode == OP_TEXT:
                        try:
                            decoded_data = data.decode("utf-8")
                            time.sleep(post_read_sleep)
                            return decoded_data
                        except Exception as decode_err:
                            print(f"[RECV] Text decoding error: {type(decode_err).__name__}")
                            print(f"[RECV] Detailed error: {str(decode_err)}")
                            time.sleep(0.1 * (attempt + 1))
                            continue
                    elif opcode == OP_BYTES:
                        time.sleep(post_read_sleep)
                        return data
                    elif opcode == OP_CLOSE:
                        self._close()
                        return ""
                    elif opcode == OP_PONG:
                        return ""
                    elif opcode == OP_PING:
                        self.write_frame(OP_PONG, data)
                        return ""
                    elif opcode == OP_CONT:
                        raise NotImplementedError("Continuation frame received")
                    else:
                        raise ValueError(f"Unknown opcode: {opcode}")
                except NoDataException:
                    print("[RECV] No data available")
                    time.sleep(0.1 * (attempt + 1))
                    continue
                except ValueError as val_err:
                    print(f"[RECV] Frame read error: {type(val_err).__name__}")
                    print(f"[RECV] Detailed error: {str(val_err)}")
                    time.sleep(0.1 * (attempt + 1))
                    continue
            except Exception as overall_err:
                print(f"[RECV] Overall receive error (Attempt {attempt + 1}): {type(overall_err).__name__}")
                print(f"[RECV] Detailed error: {str(overall_err)}")
                try:
                    print(f"[RECV] Error repr: {repr(overall_err)}")
                except:
                    pass
                time.sleep(0.1 * (attempt + 1))
                continue
        return ""

    def send(self, buf):
        assert self.open
        if isinstance(buf, str):
            opcode = OP_TEXT
            buf = buf.encode("utf-8")
        elif isinstance(buf, bytes):
            opcode = OP_BYTES
        else:
            raise TypeError()
        self.write_frame(opcode, buf)

    def close(self, code=CLOSE_OK, reason=""):
        if not self.open:
            return
        buf = struct.pack("!H", code) + reason.encode("utf-8")
        self.write_frame(OP_CLOSE, buf)
        self._close()

    def _close(self):
        print("Connection closed")
        self.open = False
        self.sock.close()

class WebsocketClient(Websocket):
    is_client = True

def connect(uri, api_key):
    uri = urlparse(uri)
    assert uri
    sock = socket.socket()
    try:
        try:
            addr = socket.getaddrinfo(uri.hostname, uri.port)
        except Exception as addr_err:
            print(f"Address Resolution Error: {addr_err}")
            raise
        try:
            sock.connect(addr[0][4])
        except Exception as conn_err:
            print(f"Connection Error: {conn_err}")
            sock.close()
            raise ConnectionError(f"Socket connection failed: {conn_err}")
        if uri.protocol == "wss":
            try:
                sock = ssl.wrap_socket(
                    sock,
                    cert_reqs=ssl.CERT_NONE  #TODO Test with cert verification
                )
            except Exception as ssl_err:
                print(f"SSL Handshake Error: {ssl_err}")
                sock.close()
                raise ConnectionError(f"SSL Connection failed: {ssl_err}")

        def send_header(header, *args):
            try:
                if isinstance(header, str):
                    header = header.encode()
                full_header = header % args + b"\r\n"
                sock.write(full_header)
            except OSError as e:
                print(f"Header Sending Error: {e}")
                raise
        # Sec-WebSocket-Key is 16 bytes of random base64 encoded
        key = binascii.b2a_base64(bytes(random.getrandbits(8) for _ in range(16)))[:-1]
        # Comprehensive WebSocket handshake headers
        send_header(b"GET %s HTTP/1.1", uri.path or b"/")
        send_header(b"Host: %s:%d", uri.hostname.encode(), uri.port)
        send_header("Authorization: Bearer %s", api_key)
        send_header(b"Connection: Upgrade")
        send_header(b"Upgrade: websocket")
        send_header(b"Sec-WebSocket-Key: %s", key)
        send_header(b"Sec-WebSocket-Version: 13")
        if uri.protocol == "wss":
            send_header(b"Origin: https://%s", uri.hostname.encode())
        else:
            send_header(b"Origin: http://%s", uri.hostname.encode())
        send_header(b"")
        try:
            header = sock.readline()[:-2]
            # Handle redirects
            if header.startswith(b"HTTP/1.1 301") or header.startswith(b"HTTP/1.1 302"):
                headers = {}
                while True:
                    line = sock.readline()[:-2]
                    if not line:
                        break
                    if b":" in line:
                        key, value = line.split(b":", 1)
                        headers[key.strip().lower()] = value.strip()
                if b"location" in headers:
                    new_url = headers[b"location"].decode("utf-8")
                    sock.close()
                    if new_url.startswith("https://"):
                        new_url = "wss://" + new_url[8:]
                    return connect(new_url, api_key)
                else:
                    raise ConnectionError("Received redirect response without Location header")
            if not header.startswith(b"HTTP/1.1 101"):
                full_response = header
                while True:
                    next_line = sock.readline()[:-2]
                    if not next_line:
                        break
                    full_response += b"\n" + next_line
                raise ConnectionError(f"Unexpected WebSocket upgrade response: {full_response}")
            while True:
                header = sock.readline()[:-2]
                if not header:
                    break
            return WebsocketClient(sock)
        except Exception as upgrade_err:
            print(f"WebSocket Upgrade Error: {upgrade_err}")
            sock.close()
            raise
    except OSError as e:
        print(f"OSError during WebSocket connection: {e}")
        sock.close()
        raise ConnectionError(f"WebSocket connection failed: {e}")
    except Exception as e:
        print(f"Unexpected WebSocket connection error: {e}")
        sock.close()
        raise ConnectionError(f"WebSocket connection failed: {e}")


