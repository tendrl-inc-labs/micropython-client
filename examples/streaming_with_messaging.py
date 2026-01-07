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
    """Configure camera settings (optional - can use camera_config instead)"""
    try:
        sensor.reset()
        sensor.set_pixformat(sensor.JPEG)
        sensor.set_framesize(sensor.VGA)
        sensor.set_quality(60)
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
    """Capture a frame and return JPEG bytes (optional - default capture used if not provided)"""
    img = sensor.snapshot()
    return img.bytearray()

async def main():
    """
    Main async function - this is required for async mode
    """
    print("=" * 60)
    print("Tendrl Client: Streaming + Messaging Example")
    print("=" * 60)

    # Create client in async mode (REQUIRED for streaming)
    client = Client(
        mode="async",           # Must be async for streaming
        debug=True,              # Enable debug output
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

    # Start streaming - Option 1: Simplest usage (uses default camera settings)
    # Camera is automatically set up with optimized settings (QVGA, quality 70)
    # Defaults: target_fps=15, quality=70, framesize="QVGA" (optimized for quality and stability)
    print("\n📹 Starting video stream...")
    try:
        stream = client.start_streaming()  # Uses defaults: FPS=15, quality=70, framesize="QVGA"
        print("✅ Streaming started as background task")
        stream_task = stream.task if stream else None
    except ImportError:
        print("⚠️ Camera module not available - skipping streaming")
        stream = None
        stream_task = None
    
    # Option 2: Adjust quality and FPS for your network
    # stream_task = client.start_streaming(
    #     target_fps=15,              # Lower FPS for slower networks
    #     quality=50                   # Lower quality for more headroom
    # )
    
    # Option 3: Custom capture function (pull mode - most control)
    # setup_camera()  # Setup camera first with your custom settings
    # stream = client.start_streaming(
    #     capture_frame_func=capture_frame,
    #     target_fps=13,  # Use default or adjust as needed
    #     quality=80      # Note: quality parameter not used with custom capture
    # )
    
    # Option 4: Push mode - manual frame control (maximum flexibility)
    # stream = client.start_streaming(
    #     accept_frames=True,  # Enable push mode
    #     target_fps=15
    # )
    # # Then in your loop:
    # # frame = capture_frame()
    # # await stream.send_frame(frame)

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

    # Create and start client
    client = Client(mode="async", debug=True)
    client.start()

    # Start streaming - simplest usage (uses default camera settings)
    # Camera is automatically set up with optimized settings (QVGA, quality 80)
    # Defaults: target_fps=13, quality=80, framesize="QVGA" (optimized for quality and stability)
    client.start_streaming()  # Uses defaults
    
    # Or adjust for your network:
    # client.start_streaming(
    #     target_fps=12,      # Lower FPS for slower networks
    #     quality=60            # Lower quality for more headroom
    # )

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
