import asyncio
import sensor


from tendrl import Client


def setup_camera():
    """Configure camera settings"""
    sensor.reset()
    sensor.set_pixformat(sensor.JPEG)
    sensor.set_framesize(sensor.QVGA)  # 320x240
    sensor.set_quality(75)
    sensor.skip_frames(time=1500)

def capture_frame():
    """Capture a frame and return JPEG bytes"""
    img = sensor.snapshot()
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
    await asyncio.sleep(10)


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

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
