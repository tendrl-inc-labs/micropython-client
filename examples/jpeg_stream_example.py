"""
JPEG Streaming Example

This example demonstrates how to use the start_streaming method
for streaming JPEG frames with configurable performance settings.

IMPORTANT: Streaming REQUIRES async mode!
- Use Client(mode="async") 
- Streaming automatically runs as a background task
- Works with messaging (MQTT) on the same event loop

NOTE: This requires the optional streaming module to be installed.
Install it by:
1. Setting INSTALL_STREAMING=True in install_script.py, OR
2. Manually: mip.install("github:tendrl-inc-labs/micropython-client/package-streaming.json", target="/lib")
"""

import asyncio

try:
    from tendrl import Client
    import sensor
except ImportError as e:
    print(f"Import error: {e}")
    print("This example requires the tendrl client and sensor module")

def setup_camera():
    """Configure camera settings"""
    sensor.reset()
    sensor.set_pixformat(sensor.JPEG)
    sensor.set_framesize(sensor.QVGA)  # 320x240
    sensor.set_quality(45)
    sensor.skip_frames(time=1500)

def capture_frame():
    """Capture a frame and return JPEG bytes"""
    img = sensor.snapshot()
    return img.bytearray()

def capture_frame_fast():
    """Capture frame optimized for speed (lower quality, higher FPS)"""
    img = sensor.snapshot()
    # Lower quality for faster encoding
    img.compress(quality=30)
    return img.bytearray()

async def main():
    """Main async function - required for async mode"""
    # Setup camera first
    setup_camera()

    # Initialize the Tendrl client in ASYNC mode (REQUIRED for streaming)
    # You can enable or disable MQTT messaging:
    client = Client(
        mode="async",        # REQUIRED: Streaming only works in async mode
        debug=True,          # Enable debug output
        enable_mqtt=True,    # Enable messaging (set False for streaming-only)
    )

    # Start the client (starts MQTT connection and background tasks)
    client.start()

    # Wait a moment for connection
    await asyncio.sleep(2)

    # Start streaming with default settings (25 FPS)
    # Automatically handles background task - no need to call add_background_task()
    client.start_streaming(capture_frame)

    print("✅ Streaming started. Press Ctrl+C to stop.")
    print("   Streaming and messaging are running together on the event loop.")

    # Keep running (or do other async work here)
    try:
        await asyncio.sleep(3600)  # Run for 1 hour (or until interrupted)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
    finally:
        await client.async_stop()

# Example 1: Basic streaming with default settings
if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())

# Example 2: High-performance streaming with custom tuning
# client.start_streaming(
#     capture_frame,
#     chunk_size=4096,           # Larger chunks for better throughput
#     yield_every_bytes=32*1024, # Minimize yields for better throughput
#     yield_ms=1,                 # Minimal yield delay
#     target_fps=25,              # Target 25 FPS
#     gc_interval=1024,            # Run GC every 1024 frames
#     reconnect_delay=5000,        # 5 second delay before reconnecting
#     debug=True
# )

# Example 3: Lower quality, higher FPS streaming
# client.start_streaming(
#     capture_frame_fast,
#     chunk_size=8192,            # Even larger chunks
#     yield_every_bytes=64*1024,  # Less frequent yields
#     target_fps=30,              # Higher FPS target
#     debug=False
# )
