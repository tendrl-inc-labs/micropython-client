import os

def rmtree(d):
    """Recursively remove a directory and its contents"""
    assert d
    for name, f_type, *_ in os.ilistdir(d):
        path = d + "/" + name
        if f_type == 16384:
            rmtree(path)
        else:
            os.remove(path)
    os.rmdir(d)

def copyfileobj(src: str, dest:str, length: int = 512):
    """Copy contents from one file-like object to another"""
    if hasattr(src, "readinto"):
        buf = bytearray(length)
        while True:
            sz = src.readinto(buf)
            if not sz:
                break
            if sz == length:
                dest.write(buf)
            else:
                b = memoryview(buf)[:sz]
                dest.write(b)
    else:
        while True:
            buf = src.read(length)
            if not buf:
                break
            dest.write(buf)

def copy(source, destination):
    """Copy a file from source to destination"""
    with open(source, 'rb') as src, open(destination, 'wb') as dst:
        copyfileobj(src, dst)
    return destination

def copytree(source, destination):
    """Recursively copy a directory tree"""
    # Create destination directory
    os.mkdir(destination)
    
    # Iterate through source directory contents
    for name, f_type, *_ in os.ilistdir(source):
        src_path = source + "/" + name
        dst_path = destination + "/" + name
        
        if f_type == 16384:  # Directory
            # Recursively copy subdirectories
            copytree(src_path, dst_path)
        else:
            # Copy files
            copy(src_path, dst_path)
    
    return destination
