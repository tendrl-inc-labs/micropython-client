"""
Example: Integrating Tendrl Client with User Application Event Loops

This example shows how to properly integrate the Tendrl client with user
applications that already have their own async event loops.
"""

import asyncio
import time
from tendrl import Client

async def sensor_reading_task():
    """Simulate a sensor reading task that runs independently"""
    counter = 0
    while True:
        # Simulate sensor reading
        temperature = 20 + (counter % 10)
        humidity = 50 + (counter % 20)
        
        print(f"📊 Sensor reading: {temperature}°C, {humidity}% humidity")
        counter += 1
        await asyncio.sleep(5)  # Read every 5 seconds

async def user_application_with_client():
    """
    Example 1: User application creates event loop and passes it to client
    
    This is the recommended approach when you have an existing async application.
    """
    print("=== Example 1: User App with Event Loop ===")
    
    # Get the current event loop (user's loop)
    loop = asyncio.get_event_loop()
    
    # Create client with user's event loop
    client = Client(
        mode="async",
        debug=True,
        event_loop=loop  # Pass user's event loop
    )
    
    # Define a tethered function
    @client.tether(tags=["sensors"])
    async def read_sensors():
        return {
            "temperature": 23.5,
            "humidity": 65.0,
            "timestamp": time.time()
        }
    
    try:
        # Start the client (it will use the provided event loop)
        client.start()
        
        # Start user's own tasks
        sensor_task = asyncio.create_task(sensor_reading_task())
        
        # Run both the client and user tasks concurrently
        print("🚀 Running client and sensor tasks concurrently...")
        
        # Simulate running for 30 seconds
        await asyncio.sleep(30)
        
        # Clean up
        sensor_task.cancel()
        await client.async_stop()
        
    except Exception as e:
        print(f"❌ Error: {e}")

async def client_in_existing_loop():
    """
    Example 2: Adding client to an already running event loop
    
    This shows how to add the client to an application that's already
    running its own async tasks.
    """
    print("\n=== Example 2: Client in Existing Loop ===")
    
    # Simulate that we already have tasks running
    sensor_task = asyncio.create_task(sensor_reading_task())
    
    # Create client without specifying event loop (will use current one)
    client = Client(
        mode="async",
        debug=True
        # No event_loop parameter - will use current running loop
    )
    
    try:
        # Start client in the existing loop
        client.start()
        
        # Publish some data
        await asyncio.sleep(2)
        client.publish({
            "message": "Client integrated into existing loop",
            "timestamp": time.time()
        })
        
        # Let it run for a bit
        await asyncio.sleep(15)
        
        # Clean up
        sensor_task.cancel()
        await client.async_stop()
        
    except Exception as e:
        print(f"❌ Error: {e}")

def sync_app_with_async_client():
    """
    Example 3: Sync application that wants to use async client
    
    This shows how a primarily synchronous application can still
    use the async client features.
    """
    print("\n=== Example 3: Sync App with Async Client ===")
    
    async def run_async_client():
        client = Client(
            mode="async",
            debug=True
        )
        
        try:
            client.start()
            
            # Publish some data
            client.publish({
                "message": "From sync app using async client",
                "timestamp": time.time()
            })
            
            # Run for a short time
            await asyncio.sleep(10)
            
            await client.async_stop()
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Run the async client from sync code
    asyncio.run(run_async_client())

def main():
    """
    Main function demonstrating different integration patterns
    """
    print("Tendrl Client Async Integration Examples")
    print("=" * 50)
    
    # Example 1: User app manages event loop
    asyncio.run(user_application_with_client())
    
    # Example 2: Client joins existing loop
    asyncio.run(client_in_existing_loop())
    
    # Example 3: Sync app using async client
    sync_app_with_async_client()
    
    print("\n✅ All examples completed!")
    print("\nKey Takeaways:")
    print("1. Pass your event loop to Client(event_loop=loop) for full control")
    print("2. Client will use current running loop if no event_loop provided")
    print("3. Both approaches avoid event loop conflicts")
    print("4. Client integrates seamlessly with existing async applications")

if __name__ == "__main__":
    main() 