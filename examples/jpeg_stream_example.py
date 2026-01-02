"""
Simple JPEG Streaming Example

This example demonstrates the simplest way to start streaming video
from an OpenMV camera to the Tendrl platform.

Key Points:
- Camera is automatically configured with optimized settings (QVGA, JPEG, quality 70)
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
    # - QVGA (320x240) resolution (default)
    # - JPEG format
    # - Quality 70 (excellent balance of quality and stability)
    # - 1500ms frame skip for camera stabilization

    # Defaults: target_fps=15, quality=70, framesize="QVGA" (optimized for quality and stability)
    # You can adjust these if needed:
    # - Lower quality (45-60) = smaller files, faster transmission, more headroom
    # - Higher quality (75-90) = better image quality, larger files, less headroom
    # - Lower FPS (10-12) = less bandwidth, more stable on slower networks
    # - Higher FPS (18-25) = smoother video, requires better network
    # - Smaller framesize ("QQVGA") = smaller files, faster transmission
    # - Larger framesize ("VGA") = better image quality, larger files, less headroom
    client.start_streaming()  # Uses defaults: FPS=15, quality=70, framesize="QVGA"

    # Example: Use larger resolution for better image quality
    # client.start_streaming(framesize="VGA", quality=45, target_fps=15)

    # Example: Use smaller resolution for very slow networks
    # client.start_streaming(framesize="QQVGA", quality=50, target_fps=15)

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
