# MicroTetherDB

A simple, lightweight database for MicroPython devices.

## Installation

1. Copy the `MicroTetherDB.py` file to your MicroPython device
2. Import the database class:
```python
from MicroTetherDB import MicroTetherDB
```

## Usage

### Basic Operations

```python
# Create a new database
db = MicroTetherDB("my_database.db")

# Store data
db["key"] = "value"

# Retrieve data
value = db["key"]

# Delete data
del db["key"]

# Check if key exists
if "key" in db:
    print("Key exists!")

# Iterate over all keys
for key in db:
    print(key, db[key])

# Close the database
db.close()
```

### Transactions

```python
# Start a transaction
with db.transaction():
    db["key1"] = "value1"
    db["key2"] = "value2"
    # If any operation fails, all changes are rolled back
```

### Locking

```python
# Acquire a lock
with db.lock():
    # Perform operations that need to be atomic
    db["key1"] = "value1"
    db["key2"] = "value2"
```

## Features

- Simple key-value storage
- Transaction support
- Locking mechanism
- Automatic file handling
- Memory efficient
- Thread-safe operations

## Limitations

- Keys must be strings
- Values must be serializable
- No complex queries
- No indexing
- No relationships

## Best Practices

1. Always close the database when done
2. Use transactions for multiple operations
3. Use locks when needed
4. Keep keys and values small
5. Regular backups recommended

## Example

```python
from MicroTetherDB import MicroTetherDB

# Create or open database
db = MicroTetherDB("my_database.db")

try:
    # Store some data
    db["user1"] = {"name": "John", "age": 30}
    db["user2"] = {"name": "Jane", "age": 25}

    # Retrieve data
    user1 = db["user1"]
    print(f"User 1: {user1}")

    # Update data
    db["user1"]["age"] = 31

    # Delete data
    del db["user2"]

    # List all users
    print("\nAll users:")
    for key in db:
        print(f"{key}: {db[key]}")

finally:
    # Always close the database
    db.close()
```

## Contributing

Feel free to submit issues and pull requests.

## License

MIT License
