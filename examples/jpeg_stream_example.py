import asyncio
import sensor

from tendrl import Client

async def main():
    """Main async function - required for async mode"""
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
    await asyncio.sleep(10)

    # Option 1: Simplest usage - uses default camera settings
    # Camera is automatically set up with defaults (VGA, quality 60)
    client.start_streaming()
    
    # Option 2: Configurable usage with camera_config
    # client.start_streaming(
    #     camera_config={
    #         "framesize": sensor.VGA,  # 640x480
    #         "quality": 65,            # JPEG quality 0-100
    #         "skip_frames_time": 1500  # Stabilization time in ms
    #     }
    # )
    
    # Option 3: Custom setup function
    # def setup_camera():
    #     sensor.reset()
    #     sensor.set_pixformat(sensor.JPEG)
    #     sensor.set_framesize(sensor.VGA)
    #     sensor.set_quality(65)
    #     sensor.skip_frames(time=1500)
    # client.start_streaming(camera_setup_func=setup_camera)
    
    # Option 4: Custom capture function (most control)
    # def capture_frame():
    #     img = sensor.snapshot()
    #     return img.bytearray()
    # client.start_streaming(capture_frame)

    print("✅ Streaming started. Press Ctrl+C to stop.")
    print("   Streaming and messaging are running together on the event loop.")

    # Keep running (or do other async work here)
    try:
        await asyncio.sleep(3600)  # Run for 1 hour (or until interrupted)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
    finally:
        await client.async_stop()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
