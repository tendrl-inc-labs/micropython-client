"""
Push Mode Streaming Example

This example demonstrates how to use push mode streaming, where you have
full control over when frames are captured and sent to the stream.

Key Points:
- Use accept_frames=True to enable push mode
- Call stream.send_frame(frame_data) to send frames manually
- Full control over frame capture timing and processing
- Works with any capture mechanism, not just camera
"""

import asyncio

try:
    from tendrl import Client
    import sensor
except ImportError as e:
    print(f"Import error: {e}")
    print("This example requires the tendrl client")
    print("For camera support, also requires the sensor module")

async def main():
    """
    Main async function demonstrating push mode streaming
    """
    print("=" * 60)
    print("Tendrl Client: Push Mode Streaming Example")
    print("=" * 60)

    # Create client in async mode (REQUIRED for streaming)
    client = Client(
        mode="async",           # Must be async for streaming
        debug=True,              # Enable debug output
        send_heartbeat=True,     # Send periodic heartbeats
    )

    # Start the client (starts MQTT connection and background tasks)
    print("\n🚀 Starting client...")
    client.start()

    # Wait a moment for connection
    await asyncio.sleep(2)

    # Enable push mode - stream will wait for frames via send_frame()
    print("\n📹 Starting push mode stream...")
    try:
        stream = client.start_streaming(
            accept_frames=True,    # Enable push mode
            target_fps=15,         # Target 15 FPS
            stream_duration=60     # Stream for 60 seconds (optional)
        )
        print("✅ Push mode stream started")
        print("   - Use stream.send_frame(frame_data) to send frames")
        print("   - You control when frames are captured and sent")
    except Exception as e:
        print(f"⚠️ Error starting stream: {e}")
        stream = None

    if stream:
        # Setup camera with custom settings
        try:
            sensor.reset()
            sensor.set_pixformat(sensor.JPEG)
            sensor.set_framesize(sensor.QVGA)
            sensor.set_quality(70)
            sensor.skip_frames(time=1500)
            print("✅ Camera initialized")
        except ImportError:
            print("⚠️ Camera module not available - using mock frames")
            sensor = None

        # User controls when frames are captured and sent
        frame_count = 0
        max_frames = 900  # ~60 seconds at 15 FPS
        
        print("\n📸 Capturing and sending frames...")
        print("   - Frame capture timing is controlled by you")
        print("   - You can process frames before sending")
        print("   - Stream will stop after 60 seconds or when stopped manually\n")

        try:
            while frame_count < max_frames:
                # Capture frame (your custom logic here)
                if sensor:
                    img = sensor.snapshot()
                    frame_data = img.bytearray()
                else:
                    # Mock frame for testing without camera
                    frame_data = b'\xff\xd8\xff\xe0' + b'\x00' * 1000  # Minimal JPEG header
                
                # Optional: Process frame before sending
                # - Add overlays, text, timestamps
                # - Apply filters or transformations
                # - Combine with other data sources
                # frame_data = process_frame(frame_data)
                
                # Check if stream is still running before sending
                if not stream.is_running():
                    print("\n⏹️  Stream has stopped")
                    break
                
                # Send frame to stream
                try:
                    await stream.send_frame(frame_data)
                    frame_count += 1
                    
                    if frame_count % 30 == 0:  # Print every 30 frames
                        print(f"   Sent {frame_count} frames...")
                except RuntimeError as e:
                    # Stream has stopped (duration elapsed or stopped)
                    print(f"\n⏹️  Stream stopped: {e}")
                    break
                
                # Control frame rate manually (15 FPS = ~66ms per frame)
                await asyncio.sleep(1.0 / 15)
            
            print(f"\n✅ Completed: Sent {frame_count} frames")
        except KeyboardInterrupt:
            print("\n\n⏹️  Interrupted by user")
        finally:
            # Stop the stream
            if stream:
                stream.stop()
                print("🛑 Stream stopped")

    # Clean shutdown
    print("\n🛑 Stopping client...")
    await client.async_stop()
    print("✅ Client stopped")

# Alternative: Push mode with custom processing
async def push_mode_with_processing():
    """
    Example showing push mode with frame processing
    """
    client = Client(mode="async", debug=True)
    client.start()
    await asyncio.sleep(2)
    
    stream = client.start_streaming(accept_frames=True, target_fps=10)
    
    # Setup camera
    sensor.reset()
    sensor.set_pixformat(sensor.JPEG)
    sensor.set_framesize(sensor.QVGA)
    sensor.set_quality(60)
    
    # Custom capture loop with processing
    for i in range(100):
        # Capture
        img = sensor.snapshot()
        frame = img.bytearray()
        
        # Example: Only send every other frame (custom logic)
        if i % 2 == 0:
            await stream.send_frame(frame)
        
        await asyncio.sleep(0.1)  # 10 FPS
    
    stream.stop()
    await client.async_stop()

if __name__ == "__main__":
    # Run main example
    asyncio.run(main())
    
    # Or run processing example:
    # asyncio.run(push_mode_with_processing())

