from struct import pack 
from math import ceil 
from binascii import unhexlify

from dolreader import write_uint32

def range_check(val, bits):
    if not (val <= 2**bits - 1):
        raise RuntimeError("Value {0} exceeds size ({1} bits)".format(val, bits))

def calc_signed(val, bits):
    if val < 0:
        res = 2**bits + val 
        if res <= 2**(bits-1) - 1:
            raise RuntimeError("Value out of range: {0}".format(val))
    else:
        res = val 
        if res > 2**(bits-1) - 1:
            raise RuntimeError("Value out of range: {0}".format(val))
    assert res == res & (2**bits - 1)
    
    return res 

def _branch(dol, from_addr, to_addr, link, absolute=False):
    out = 0
    if link:
        out |= 0b1 
    if absolute:
        out |= 0b10 # do an absolute branch. Doesn't work on the Gamecube
    
    delta = to_addr - from_addr 
    print("Making branch: from {0:x} to {1:x}".format(from_addr, to_addr))
    print("delta:", hex(delta))
    assert delta % 4 == 0
    delta = delta // 4
    res = calc_signed(delta, 24)
    """if delta < 0:
        res = 2**24 + delta 
        if res <= 2**23 - 1:
            raise RuntimeError("Branch out of range: from {0} to {1}".format(from_addr, to_addr))
    else:
        res = delta  
        if res > 2**23 - 1:
            raise RuntimeError("Branch out of range: from {0} to {1}".format(from_addr, to_addr))"""
    #res = res & (2**24 - 1)
    
    out |= (res << 2) # immediate value for branching 
    out |= 18 << (2+24) # Opcode for branch 
    
    dol.seek(from_addr)
    write_uint32(dol, out)
    
    

def branchlink(dol, from_addr, to_addr):
    _branch(dol, from_addr, to_addr, True)
    
def branch(dol, from_addr, to_addr):
    _branch(dol, from_addr, to_addr, False )

def write_addi(dol, rD, rA, val, signed=True):
    if signed:
        simm = calc_signed(val, 16)
    else:
        simm = val 
    
    out = simm 
    range_check(rD, 5)
    range_check(rA, 5)
    out |= (rA << 16)
    out |= (rD << (16+5))
    out |= (14 << (16+5+5))
    write_uint32(dol, out)

def write_addis(dol, rD, rA, val, signed=True):
    if signed:
        simm = calc_signed(val, 16)
    else:
        simm = val 
        
    out = simm 
    range_check(rD, 5)
    range_check(rA, 5)
    out |= (rA << 16)
    out |= (rD << (16+5))
    out |= (15 << (16+5+5))
    write_uint32(dol, out)

def write_li(dol, rD, val, signed=True):
    write_addi(dol, rD, 0, val, signed)

def write_lis(dol, rD, val, signed=True):
    write_addis(dol, rD, 0, val, signed)

def write_ori(dol, rD, rA, val):
    range_check(val, 16)
    
    out = val
    range_check(rD, 5)
    range_check(rA, 5)
    out |= (rA << 16)
    out |= (rD << (16+5))
    out |= (24 << (16+5+5))
    write_uint32(dol, out)

def write_oris(dol, rD, rA, val):
    range_check(val, 16)
    
    out = val
    range_check(rD, 5)
    range_check(rA, 5)
    out |= (rA << 16)
    out |= (rD << (16+5))
    out |= (25 << (16+5+5))
    write_uint32(dol, out)
    
def write_nop(dol):
    write_ori(dol, 0, 0, 0)


def _read_line(line):
    line = line.strip()
    vals = line.split(" ")
    for i in range(vals.count("")):
        vals.remove("")
    
    val1 = int(vals[0], 16)
    val2 = int(vals[1], 16)
    
    return val1, val2

def apply_gecko(dol, f):
    while True:
        line = f.readline()
        if line == "":
            break 
        if line.strip() == "" or line.startswith("$") or line.startswith("*"):
            continue 
        
        val1, val2 = _read_line(line)
        
        codetype = val1 >> 24
        addr = 0x80000000 + (val1 & 0xFFFFFF)
        
        hi = codetype & 0b1
        if hi:
            addr += 0x01000000
            
        
        if codetype == 0x00:
            amount = (val2 >> 16) + 1 
            value = val2 & 0xFF
            
            dol.seek(addr)
            for i in range(amount):
                dol.write(pack("B", value))
                
        elif codetype == 0x02:
            amount = (val2 >> 8) + 1 
            value = val2 & 0xFFFF
            
            dol.seek(addr)
            for i in range(amount):
                dol.write(pack(">H", value))
                
        elif codetype == 0x04: 
            dol.seek(addr)
            dol.write(pack(">I", val2))
        
        elif codetype == 0x06:
            bytecount = val2 
            dol.seek(addr)
            for i in range(int(ceil(bytecount/8.0))):
                datalen = bytecount % 8
                line = f.readline().strip()
                assert line != ""
                vals = line.split(" ")
                for j in range(vals.count("")):
                    vals.remove("")
                data = "".join(vals)
                
                dol.write(unhexlify(data)[:datalen])
                bytecount -= 8 
        
        elif codetype == 0xC6:
            branch(dol, addr, val2)
                
                
            
            
