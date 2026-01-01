"""
Simple JPEG Streaming Example

This example demonstrates the simplest way to start streaming video
from an OpenMV camera to the Tendrl platform.

Key Points:
- Camera is automatically configured with optimized settings (VGA, JPEG, quality 55)
- Performance stats are printed every 60 frames when debug=True
- Streaming runs as a background task in async mode
"""

import asyncio
from tendrl import Client

async def main():
    # Initialize client in async mode (REQUIRED for streaming)
    client = Client(
        mode="async",  # REQUIRED: Streaming only works in async mode
        debug=True     # OPTIONAL: Enable debug output (shows performance stats)
    )

    # Start the client (establishes WiFi/MQTT connection)
    client.start()

    # Wait for the client to connect to the network
    await asyncio.sleep(5)

    # Start streaming - camera is automatically configured with optimized settings:
    # - VGA (640x480) resolution
    # - JPEG format
    # - Quality 50 (good balance of quality and performance)
    # - 1500ms frame skip for camera stabilization
    # 
    # Defaults: target_fps=15, quality=50 (optimized for consistent performance)
    # You can adjust these if needed:
    # - Lower quality (45-50) = smaller files, faster transmission
    # - Higher quality (55-60) = better image quality, larger files
    # - Lower FPS (10-15) = less bandwidth, more stable on slower networks
    # - Higher FPS (18-20) = smoother video, requires better network
    client.start_streaming()  # Uses defaults: FPS=15, quality=50

    # With debug=True, performance stats will be printed every 60 frames
    # showing: FPS, send times, frame sizes, network bandwidth, etc.

    try:
        # Run for 1 hour (or until interrupted)
        await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        # Clean shutdown
        await client.async_stop()

if __name__ == "__main__":
    asyncio.run(main())
