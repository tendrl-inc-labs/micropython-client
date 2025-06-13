import os
import vfs

class RAMBlockDevice:
    def __init__(self, block_size=512, block_count=128):
        self.block_size = block_size
        self.block_count = block_count
        self.storage = bytearray(block_size * block_count)
        print(f"RAMBlockDevice initialized with block_size={block_size}, block_count={block_count}, total_size={len(self.storage)}")

    def readblocks(self, block_num, buf):
        if block_num < 0 or block_num >= self.block_count:
            raise OSError(22)  # Invalid argument
        start = block_num * self.block_size
        end = start + len(buf)
        if end > len(self.storage):
            raise OSError(22)  # Invalid argument
        buf[:] = self.storage[start:end]

    def writeblocks(self, block_num, buf):
        if block_num < 0 or block_num >= self.block_count:
            raise OSError(22)  # Invalid argument
        start = block_num * self.block_size
        end = start + len(buf)
        if end > len(self.storage):
            raise OSError(22)  # Invalid argument
        self.storage[start:end] = buf

    def ioctl(self, cmd, arg):
        if cmd == 4:  # get number of blocks
            return self.block_count
        if cmd == 5:  # get block size
            return self.block_size
        if cmd == 6:  # erase block
            if arg < 0 or arg >= self.block_count:
                raise OSError(22)  # Invalid argument
            start = arg * self.block_size
            end = start + self.block_size
            self.storage[start:end] = bytearray(self.block_size)
            return 0
        return 0

    def mount(self, mount_point):
        try:
            print(f"Attempting to mount at {mount_point}")
            print(f"Block device info: size={self.block_size}, count={self.block_count}")
            
            # Try to unmount first if already mounted
            try:
                os.umount(mount_point)
            except Exception:
                pass

            # Create mount point if it doesn't exist
            try:
                os.mkdir(mount_point)
            except Exception:
                pass

            # Format the filesystem
            print("Formatting filesystem...")
            vfs.VfsFat.mkfs(self)
            print("Filesystem formatted successfully")

            # Mount it
            print("Mounting filesystem...")
            os.mount(vfs.VfsFat(self), mount_point)
            print("Filesystem mounted successfully")
        except Exception as e:
            print(f"Error in mount process: {e}")
            raise

    def umount(self, mount_point):
        try:
            os.umount(mount_point)
        except Exception as e:
            print(f"Warning: Error unmounting: {e}")
