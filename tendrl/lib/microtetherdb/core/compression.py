"""
Compression utilities for MicroTetherDB
"""

try:
    import uzlib
    HAS_UZLIB = True
except ImportError:
    uzlib = None
    HAS_UZLIB = False

def compress_data(data, use_compression=True, min_size=256):
    """Compress data if it meets the size threshold and compression is available
    
    Args:
        data (bytes): Data to compress
        use_compression (bool): Whether to attempt compression
        min_size (int): Minimum size for compression attempt
        
    Returns:
        tuple: (compressed_data, is_compressed)
    """
    if not use_compression or not HAS_UZLIB or len(data) < min_size:
        return data, False
        
    try:
        compressed = uzlib.compress(data, 9)  # Max compression
        if len(compressed) < len(data):
            return compressed, True
    except Exception as e:
        print(f"Compression error: {e}")
    return data, False

def decompress_data(data, is_compressed):
    """Decompress data if it was compressed and compression is available
    
    Args:
        data (bytes): Data to decompress
        is_compressed (bool): Whether the data is compressed
        
    Returns:
        bytes: Decompressed data
    """
    if is_compressed and HAS_UZLIB:
        try:
            return uzlib.decompress(data, 32768)  # 32KB limit
        except Exception as e:
            print(f"Decompression error: {e}")
            return data
    return data 