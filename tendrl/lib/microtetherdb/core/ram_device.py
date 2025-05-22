class RAMBlockDevice:
    """RAM-based block device for in-memory storage"""
    
    def __init__(self, blocks=128, block_size=512):
        self.block_size = block_size
        self.blocks = blocks
        self.data = bytearray(blocks * block_size)

    def readblocks(self, block_num, buf, offset=0):
        start = block_num * self.block_size + offset
        end = start + len(buf)
        buf[:] = self.data[start:end]
        return 0

    def writeblocks(self, block_num, buf, offset=0):
        start = block_num * self.block_size + offset
        end = start + len(buf)
        self.data[start:end] = buf
        return 0

    def ioctl(self, op, arg):
        if op == 4:  # get number of blocks
            return self.blocks
        if op == 5:  # get block size
            return self.block_size
        return 0 