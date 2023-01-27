from .dolreader import write_uint32


def range_check(val, bits):
    if not val <= 2**bits - 1:
        raise RuntimeError("Value {0} exceeds size ({1} bits)".format(val, bits))


def calc_signed(val, bits):
    if val < 0:
        res = 2**bits + val
        if res <= 2**(bits - 1) - 1:
            raise RuntimeError("Value out of range: {0}".format(val))
    else:
        res = val
        if res > 2**(bits - 1) - 1:
            raise RuntimeError("Value out of range: {0}".format(val))
    assert res == res & (2**bits - 1)

    return res


def _branch(dol, from_addr, to_addr, link, absolute=False):
    out = 0
    if link:
        out |= 0b1
    if absolute:
        out |= 0b10  # do an absolute branch. Doesn't work on the Gamecube

    delta = to_addr - from_addr
    assert delta % 4 == 0
    delta = delta // 4
    res = calc_signed(delta, 24)

    out |= (res << 2)  # immediate value for branching
    out |= 18 << (2 + 24)  # Opcode for branch

    dol.seek(from_addr)
    write_uint32(dol, out)


def branchlink(dol, from_addr, to_addr):
    _branch(dol, from_addr, to_addr, True)


def branch(dol, from_addr, to_addr):
    _branch(dol, from_addr, to_addr, False)


def write_addi(dol, rD, rA, val, signed=True):
    if signed:
        simm = calc_signed(val, 16)
    else:
        simm = val

    out = simm
    range_check(rD, 5)
    range_check(rA, 5)
    out |= (rA << 16)
    out |= (rD << (16 + 5))
    out |= (14 << (16 + 5 + 5))
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
    out |= (rD << (16 + 5))
    out |= (15 << (16 + 5 + 5))
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
    out |= (rD << (16 + 5))
    out |= (24 << (16 + 5 + 5))
    write_uint32(dol, out)


def write_oris(dol, rD, rA, val):
    range_check(val, 16)

    out = val
    range_check(rD, 5)
    range_check(rA, 5)
    out |= (rA << 16)
    out |= (rD << (16 + 5))
    out |= (25 << (16 + 5 + 5))
    write_uint32(dol, out)


def write_nop(dol):
    write_ori(dol, 0, 0, 0)


def _read_line(line):
    line = line.strip()
    vals = line.split(" ")
    for _ in range(vals.count("")):
        vals.remove("")

    val1 = int(vals[0], 16)
    val2 = int(vals[1], 16)

    return val1, val2
