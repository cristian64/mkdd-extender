import struct 
from io import BytesIO, RawIOBase


def read_ubyte(f):
    return struct.unpack("B", f.read(1))[0]

def read_uint32(f):
    return struct.unpack(">I", f.read(4))[0]

def write_uint32(f, val):
    f.write(struct.pack(">I", val))

class UnmappedAddress(Exception):
    pass
    
class SectionCountFull(Exception):
    pass

class DolFile(object):
    def __init__(self, f):
        self._rawdata = BytesIO(f.read())
        f.seek(0)
        fileoffset = 0
        addressoffset = 0x48
        sizeoffset = 0x90 
        
        self._text = []
        self._data = []
        
        nomoretext = False 
        nomoredata = False
        
        self._current_end = None 
        
        # Read text and data section addresses and sizes 
        for i in range(18):
            f.seek(fileoffset+i*4)
            offset = read_uint32(f)
            f.seek(addressoffset+i*4)
            address = read_uint32(f)
            f.seek(sizeoffset+i*4)
            size = read_uint32(f)
            
            if i <= 6:
                if offset != 0:
                    self._text.append((offset, address, size))
                    # print("text{0}".format(i), hex(offset), hex(address), hex(size))
            else:
                datanum = i - 7
                if offset != 0:
                    self._data.append((offset, address, size))
                    # print("data{0}".format(datanum), hex(offset), hex(address), hex(size))
        
        f.seek(0xD8)
        self.bssaddr = read_uint32(f)
        self.bsssize = read_uint32(f)
        
        #self.bss = BytesIO(self._rawdata.getbuffer()[self._bssaddr:self._bssaddr+self.bsssize])
        
        self._curraddr = self._text[0][1]
        self.seek(self._curraddr)
    
    @property
    def sections(self):
        for i in self._text:
            yield i
        for i in self._data:
            yield i 
        
        return
    
    # Internal function for resolving a gc address 
    def _resolve_address(self, gc_addr):
        for offset, address, size in self.sections:
            if address <= gc_addr < address+size:
                return offset, address, size 
        """for offset, address, size in self._text:
            if address <= gc_addr < address+size:
                return offset, address, size 
        for offset, address, size in self._data:
            if address <= gc_addr < address+size:
                return offset, address, size """
        
        raise UnmappedAddress("Unmapped address: {0}".format(hex(gc_addr)))
    
    def _adjust_header(self):
        curr = self._rawdata.tell()
        fileoffset = 0
        addressoffset = 0x48
        sizeoffset = 0x90 
        f = self._rawdata 
        
        i = 0
        for offset, address, size in self._text:
            f.seek(fileoffset+i*4)
            write_uint32(f, offset)
            f.seek(addressoffset+i*4)
            write_uint32(f, address)
            f.seek(sizeoffset+i*4)
            write_uint32(f, size)
            i += 1 
            
        i = 7
        for offset, address, size in self._data:
            f.seek(fileoffset+i*4)
            write_uint32(f, offset)
            f.seek(addressoffset+i*4)
            write_uint32(f, address)
            f.seek(sizeoffset+i*4)
            write_uint32(f, size)
            i += 1 
                
        f.seek(0xD8)
        write_uint32(f, self.bssaddr)
        write_uint32(f, self.bsssize)
        
        f.seek(curr)
    
    # Unsupported: Reading an entire dol file 
    # Assumption: A read should not go beyond the current section 
    def read(self, size):
        if self._curraddr + size > self._current_end:
            raise RuntimeError("Read goes over current section")
            
        return self._rawdata.read(size)
        self._curraddr += size  
        
    # Assumption: A write should not go beyond the current section 
    def write(self, data):
        if self._curraddr + len(data) > self._current_end:
            raise RuntimeError("Write goes over current section")
            
        self._rawdata.write(data)
        self._curraddr += len(data)
    
    def seek(self, addr):
        offset, gc_start, gc_size = self._resolve_address(addr)
        self._rawdata.seek(offset + (addr-gc_start))
        
        self._curraddr = addr 
        self._current_end = gc_start + gc_size 
        
    def _add_section(self, newsize, section, addr=None):
        if addr is not None:
            last_addr = addr 
        else:
            last_addr = 0
        last_offset = 0 
        
        for offset, address, size in self.sections:
            if last_addr < address+size:
                last_addr = address+size 
            if last_offset < offset + size:
                last_offset = offset+size 
        
        if last_addr < self.bssaddr+self.bsssize:
            last_addr = self.bssaddr+self.bsssize 
        
        section.append((last_offset, last_addr, newsize))
        curr = self._rawdata.tell()
        self._rawdata.seek(last_offset)
        self._rawdata.write(b" "*newsize)
        self._rawdata.seek(curr)
        
        return (last_offset, last_addr, newsize)
        
    def allocate_text_section(self, size, addr=None):
        assert len(self._text) <= 7 
        if len(self._text) >= 7:
            raise SectionCountFull("Maximum amount of text sections reached!")
        
        return self._add_section(size, self._text, addr)
    
    def allocate_data_section(self, size, addr=None):
        assert len(self._data) <= 11 
        if len(self._data) >= 11:
            raise SectionCountFull("Maximum amount of data sections reached!")
        
        return self._add_section(size, self._data, addr=None)
        
        
    def tell(self):
        return self._curraddr
    
    def save(self, f):
        self._adjust_header()
        f.write(self._rawdata.getbuffer())
    
    
    def print_info(self):
        print("Dol Info:")
        i = 0
        for offset, addr, size in self._text:
            print("text{0}: fileoffset {1:x}, addr {2:x}, size {3:x}".format(i, offset, addr, size))
            i += 1
        i = 0
        
        for offset, addr, size in self._data:
            print("data{0}: fileoffset {1:x}, addr {2:x}, size {3:x}".format(i, offset, addr, size))
            i += 1
            
        print("bss addr: {0:x}, bss size: {1:x}, bss end: {2:x}".format(self.bssaddr, self.bsssize,
                                                                            self.bssaddr+ self.bsssize))
        
if __name__ == "__main__":
    with open("pikmin.dol", "rb") as f:
        dol = DolFile(f)
    
    dol.print_info()
    dol.allocate_text_section(4)
    dol.print_info()
    
        