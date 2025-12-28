"""
Complete Example: Streaming + Messaging in Async Mode

This example demonstrates how to use JPEG streaming together with
MQTT messaging in async mode. Streaming requires async mode because
it needs to yield control to allow messaging operations.

Key Points:
- Must use Client(mode="async")
- Streaming automatically runs as a background task
- Messaging and streaming work together on the same event loop
- Messaging takes priority (as designed)
"""

import asyncio
import time

try:
    from tendrl import Client
    import sensor
except ImportError as e:
    print(f"Import error: {e}")
    print("This example requires the tendrl client")
    print("For camera support, also requires the sensor module")

def setup_camera():
    """Configure camera settings"""
    try:
        sensor.reset()
        sensor.set_pixformat(sensor.JPEG)
        sensor.set_framesize(sensor.QVGA)  # 320x240
        sensor.set_quality(45)
        sensor.skip_frames(time=1500)
        print("✅ Camera initialized")
        return True
    except ImportError:
        print("⚠️ Camera module not available - using mock capture")
        return False
    except Exception as e:
        print(f"⚠️ Camera setup error: {e}")
        return False

def capture_frame():
    """Capture a frame and return JPEG bytes (synchronous)"""

    img = sensor.snapshot()
    return img.bytearray()

async def capture_frame_async():
    """Capture a frame asynchronously (if your camera supports it)"""
    # If your capture function needs async operations, use this pattern
    await asyncio.sleep(0)  # Yield to event loop
    return capture_frame()

async def main():
    """
    Main async function - this is required for async mode
    """
    print("=" * 60)
    print("Tendrl Client: Streaming + Messaging Example")
    print("=" * 60)

    # Initialize camera
    camera_available = setup_camera()

    # Create client in async mode (REQUIRED for streaming)
    client = Client(
        mode="async",           # Must be async for streaming
        debug=True,              # Enable debug output
        enable_mqtt=True,        # Enable messaging (default)
        send_heartbeat=True,     # Send periodic heartbeats
    )

    # Optional: Define a message callback
    # def on_message(message):
    #     """Handle incoming MQTT messages"""
    #     print(f"📨 Received message: {message}")
    #
    # Set callback if you want to receive messages
    # client.mqtt.callback = on_message  # Uncomment if needed

    # Start the client (starts MQTT connection and background tasks)
    print("\n🚀 Starting client...")
    client.start()

    # Wait a moment for connection
    await asyncio.sleep(2)

    # Start streaming
    # This automatically adds streaming as a background task
    print("\n📹 Starting video stream...")
    if camera_available:
        stream_task = client.start_streaming(
            capture_frame,              # Capture function (can be sync or async)
            target_fps=25,              # Target 25 FPS
            chunk_size=4096,            # 4KB chunks
            yield_every_bytes=32*1024,  # Yield every 32KB
            yield_ms=1,                 # 1ms yield delay
            debug=True                  # Enable streaming debug
        )
        print("✅ Streaming started as background task")
    else:
        print("⚠️ Camera not available - skipping streaming")
        stream_task = None

    # Example: Publish some data while streaming
    print("\n📤 Publishing messages while streaming...")
    for i in range(5):
        client.publish({
            "message": f"Test message {i+1}",
            "streaming": "active" if stream_task else "inactive"
        }, tags=["test", "streaming"])
        await asyncio.sleep(2)

    # Example: Define a tethered function (runs periodically)
    @client.tether(tags=["sensors", "periodic"])
    async def read_sensors():
        """This function runs periodically and publishes data"""
        return {
            "temperature": 23.5 + (time.time() % 10),
            "humidity": 65.0 + (time.time() % 5),
            "streaming_active": stream_task is not None
        }

    print("\n✅ Client running with streaming and messaging")
    print("   - Streaming: Active" if stream_task else "   - Streaming: Inactive")
    print("   - Messaging: Active")
    print("   - Press Ctrl+C to stop\n")

    # Run for a while (or until interrupted)
    try:
        # Keep running - both streaming and messaging work together
        await asyncio.sleep(60)  # Run for 60 seconds
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping...")
    finally:
        # Clean shutdown
        print("🛑 Stopping client...")
        await client.async_stop()
        print("✅ Client stopped")

# Alternative: Simple example without async main function
def simple_example():
    """
    Simpler example if you don't need custom async logic
    """
    print("=" * 60)
    print("Simple Streaming + Messaging Example")
    print("=" * 60)

    # Setup camera
    setup_camera()

    # Create and start client
    client = Client(mode="async", debug=True)
    client.start()

    # Start streaming - that's it!
    client.start_streaming(capture_frame, target_fps=25, debug=True)

    print("✅ Streaming and messaging are running!")
    print("   Press Ctrl+C to stop")

    # Keep running (this blocks, but client tasks run in background)
    try:
        while True:
            # Publish messages periodically
            client.publish({
                "status": "running",
                "timestamp": time.time()
            })
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping...")
        # Note: In sync context, you'd need to handle cleanup differently
        # For proper cleanup, use the async main() example above

if __name__ == "__main__":
    # Use asyncio.run() to run the async main function
    asyncio.run(main())

    # Or use the simple example (less control):
    # simple_example()
