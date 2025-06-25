"""
Example: Configuring Tendrl Client for Different Installation Types

This example shows how to properly configure the Tendrl client based on
whether you installed the full package (with MicroTetherDB) or the minimal
package (without database features).
"""

from tendrl import Client

def example_full_installation():
    """
    Example for full installation (includes MicroTetherDB)
    
    The client will automatically detect MicroTetherDB availability
    and enable database features by default.
    """
    print("=== Full Installation Example ===")

    # Default configuration - databases enabled automatically
    client = Client(
        debug=True,
        # client_db=True,          # Default: enabled if MicroTetherDB available
        # client_db_in_memory=True, # Default: in-memory for speed
        # offline_storage=True      # Default: enabled if MicroTetherDB available
    )

    try:
        # Use client database features
        key = client.db_put({"sensor": "temperature", "value": 23.5})
        print(f"Stored data with key: {key}")

        data = client.db_get(key)
        print(f"Retrieved data: {data}")

        # Query data
        results = client.db_query({"sensor": "temperature"})
        print(f"Query results: {list(results)}")

        # Publish data (with offline storage backup)
        client.publish(
            {"temperature": 23.5, "humidity": 60},
            write_offline=True,  # Store offline if connection fails
            tags=["sensor", "environment"]
        )

    except Exception as e:
        print(f"Error: {e}")

    print("Full installation features available!")

def example_minimal_installation():
    """
    Example for minimal installation (no MicroTetherDB)
    
    The client will automatically detect that MicroTetherDB is not available
    and disable database features. You can also explicitly disable them.
    """
    print("=== Minimal Installation Example ===")

    # Explicit configuration for minimal installation
    client = Client(
        debug=True,
        client_db=False,      # Explicitly disable (auto-disabled if no MicroTetherDB)
        offline_storage=False # Explicitly disable (auto-disabled if no MicroTetherDB)
    )

    try:
        # Database features will raise helpful errors
        try:
            client.db_put({"test": "data"})
        except Exception as e:
            print(f"Expected error: {e}")

        # Basic publishing still works
        client.publish(
            {"temperature": 23.5, "humidity": 60},
            write_offline=False,  # Must be False - no offline storage
            tags=["sensor", "environment"]
        )

    except Exception as e:
        print(f"Error: {e}")

    print("Minimal installation - basic features only!")

def example_mixed_configuration():
    """
    Example showing different database configuration options
    """
    print("=== Mixed Configuration Examples ===")

    # Client database only (no offline storage)
    client1 = Client(
        debug=True,
        client_db=True,           # Enable client database
        client_db_in_memory=True, # Use in-memory storage
        offline_storage=False     # Disable offline message storage
    )
    print("Configuration 1: Client DB only (in-memory)")

    # Offline storage only (no client database)
    client2 = Client(
        debug=True,
        client_db=False,      # Disable client database
        offline_storage=True  # Enable offline message storage
    )
    print("Configuration 2: Offline storage only")

    # File-based client database
    client3 = Client(
        debug=True,
        client_db=True,            # Enable client database
        client_db_in_memory=False, # Use file-based storage
        offline_storage=True       # Enable offline storage
    )
    print("Configuration 3: Both databases (client DB on flash)")

def main():
    """
    Main example function that demonstrates different configurations
    """
    print("Tendrl Client Configuration Examples")
    print("=" * 50)

    try:
        # Try full installation example
        example_full_installation()
        print()

    except ImportError as e:
        print(f"MicroTetherDB not available: {e}")
        print("Running minimal installation example instead...")
        example_minimal_installation()
        print()

    # Show configuration options
    example_mixed_configuration()

    print("\nConfiguration Summary:")
    print("- Full installation: All features available")
    print("- Minimal installation: ~50KB smaller, basic features only")
    print("- Client auto-detects available features")
    print("- Database features disabled gracefully when not available")

if __name__ == "__main__":
    main()
