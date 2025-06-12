import io

try:
    import deflate
    HAS_COMPRESSION = True
except ImportError:
    HAS_COMPRESSION = False


def compress_data(data, use_compression=True, min_size=256):
    if not use_compression  or len(data) < min_size:
        return data, False
    try:
        compressed_stream = io.BytesIO()
        with deflate.DeflateIO(compressed_stream, deflate.ZLIB, level=4) as d:
            d.write(data)
        compressed = compressed_stream.getvalue()
        if len(compressed) < len(data):
            return compressed, True
    except Exception as e:
        print(f"Compression error: {e}")
    return data, False

def decompress_data(data, is_compressed):
    if not is_compressed:
        return data
    try:
        compressed_stream = io.BytesIO(data)
        with deflate.DeflateIO(compressed_stream, deflate.ZLIB) as d:
            return d.read()
    except Exception as e:
        print(f"Decompression error: {e}")
        return data
