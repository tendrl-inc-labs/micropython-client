import errno
import os
import time

try:
    import vfs  # Your working example uses this
    HAS_VFS = True
except ImportError:
    vfs = None
    HAS_VFS = False


class RAMBlockDevice:
    def __init__(self, blocks=128, block_size=256):
        self.block_size = block_size
        self.blocks = blocks
        self.size = self.blocks * self.block_size
        self.data = bytearray(self.size)
        self.mount_point = "/mtdb_ramdisk"
        self.mounted = False
        print(f"RAM device initialized: {self.blocks} blocks of {self.block_size} bytes ({self.size / 1024:.1f} KB)")

    def readblocks(self, block_num, buf):
        start = block_num * self.block_size
        end = start + len(buf)
        buf[:] = self.data[start:end]

    def writeblocks(self, block_num, buf):
        start = block_num * self.block_size
        end = start + len(buf)
        self.data[start:end] = buf

    def ioctl(self, op, arg):
        if op == 4: return self.blocks         # Get number of blocks
        if op == 5: return self.block_size     # Get block size
        return 0                               # No-op for other ops

    def sync(self):
        return 0

    def mount(self):
        if not HAS_VFS:
            raise ImportError("VFS module not available")

        for attempt in range(3):
            try:
                print(f"Formatting RAM device with FAT (attempt {attempt + 1})...")
                vfs.VfsFat.mkfs(self)

                try:
                    os.mkdir(self.mount_point)
                except OSError as e:
                    if e.args[0] != errno.EEXIST:
                        raise

                vfs.mount(vfs.VfsFat(self), self.mount_point)
                self.mounted = True
                print(f"Mounted RAM device at {self.mount_point}")
                return
            except Exception as e:
                print(f"Mount attempt {attempt + 1} failed: {e}")
                time.sleep(0.25)

        raise OSError("Failed to mount RAM device after multiple attempts")

    def umount(self):
        if self.mounted and HAS_VFS:
            try:
                vfs.umount(self.mount_point)
                self.mounted = False
                try:
                    os.rmdir(self.mount_point)
                except Exception:
                    pass
                print(f"Unmounted and cleaned up: {self.mount_point}")
                return True
            except Exception as e:
                print(f"Error unmounting RAM device: {e}")
                return False
        return False

    def get_db_path(self):
        if self.mounted:
            return f"{self.mount_point}/microtetherdb.db"
        return None

    def __del__(self):
        self.umount()