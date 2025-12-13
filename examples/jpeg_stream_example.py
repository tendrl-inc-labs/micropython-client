"""
JPEG Streaming Example with Performance Tuning

This example demonstrates how to use the jpeg_stream decorator
for streaming JPEG frames with configurable performance settings.

NOTE: This requires the optional streaming module to be installed.
Install it by:
1. Setting INSTALL_STREAMING=True in install_script.py, OR
2. Manually: mip.install("github:tendrl-inc-labs/micropython-client/package-streaming.json", target="/lib")
"""

# Example usage with OpenMV or similar camera sensor

try:
    from tendrl import Client
    import sensor
    import time
except ImportError as e:
    print(f"Import error: {e}")
    print("This example requires the tendrl client and sensor module")

# Initialize the Tendrl client
client = Client(debug=True, managed=True)
client.start()

# Example 1: Basic streaming with default settings
@client.jpeg_stream(
    server_host="your.server.com",
    use_tls=True,
    port=443
)
def capture_frame():
    """Capture a frame and return JPEG bytes"""
    img = sensor.snapshot()
    return img.bytearray()

# Example 2: High-performance streaming with custom tuning
@client.jpeg_stream(
    server_host="your.server.com",
    use_tls=True,
    port=443,
    chunk_size=4096,           # Larger chunks for better throughput
    yield_every_bytes=32*1024,  # Minimize yields for better throughput
    yield_ms=1,                 # Minimal yield delay
    target_fps=25,              # Target 25 FPS
    boundary="openmvframe",     # Multipart boundary
    gc_interval=1024,            # Run GC every 1024 frames
    reconnect_delay=5000,        # 5 second delay before reconnecting
    debug=True
)
def capture_frame_optimized():
    """Capture a frame with optimized settings"""
    img = sensor.snapshot()
    return img.bytearray()

# Example 3: Lower quality, higher FPS streaming
@client.jpeg_stream(
    server_host="your.server.com",
    use_tls=True,
    chunk_size=8192,            # Even larger chunks
    yield_every_bytes=64*1024,  # Less frequent yields
    target_fps=30,              # Higher FPS target
    debug=False
)
def capture_frame_fast():
    """Capture frame optimized for speed"""
    img = sensor.snapshot()
    # Lower quality for faster encoding
    img.compress(quality=30)
    return img.bytearray()

# Example 4: With sensor configuration
def setup_camera():
    """Configure camera settings"""
    sensor.reset()
    sensor.set_pixformat(sensor.JPEG)
    sensor.set_framesize(sensor.QVGA)  # 320x240
    sensor.set_quality(45)
    sensor.skip_frames(time=1500)

# To start streaming, use the async function with asyncio:
if __name__ == "__main__":
    import asyncio
    
    # Setup camera first
    setup_camera()
    
    # The decorator returns an async coroutine that yields control periodically
    # Use add_background_task to run it cooperatively with the client
    client.add_background_task(capture_frame_optimized())
    
    # Or manually create a task:
    # asyncio.create_task(capture_frame_optimized())
    
    # Or await it in an async function:
    # await capture_frame_optimized()
    
    print("Streaming started. Press Ctrl+C to stop.")

