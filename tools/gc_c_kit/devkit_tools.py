import subprocess
import os
import platform
from itertools import chain

from .dolreader import DolFile, SectionCountFull
from .doltools import branchlink, branch

GCCPATH = os.environ.get("GCCKIT_GCCPATH")
LDPATH = os.environ.get("GCCKIT_LDPATH")
OBJDUMPPATH = os.environ.get("GCCKIT_OBJDUMPPATH")
OBJCOPYPATH = os.environ.get("GCCKIT_OBJCOPYPATH")


def get_creation_flags():
    creationflags = 0
    if platform.system() == "Windows":
        creationflags |= subprocess.CREATE_NO_WINDOW
    return creationflags


def compile_(inpath, outpath, mode, optimize="-O1", warnings=('-W', '-Wall', '-Wextra')):
    assert mode in ("-S", "-c")
    args = [GCCPATH, inpath, mode, "-o", outpath, optimize]
    args += warnings
    subprocess.check_call(args, creationflags=get_creation_flags())


def link(infiles, outfile, outmap, linker_files):
    arg = [LDPATH]
    arg.append("-Os")
    for file in linker_files:
        arg.append("-T")
        arg.append(file)

    arg.extend(("-o", outfile))

    for file in infiles:
        arg.append(file)

    arg.extend(("-Map", outmap))
    subprocess.check_call(arg, creationflags=get_creation_flags())


def objdump(*args):
    arg = [OBJDUMPPATH]
    arg.extend(args)
    subprocess.check_call(arg, creationflags=get_creation_flags())


def objcopy(*args, attrs=tuple()):
    arg = [OBJCOPYPATH]
    arg.extend(args)
    for attr in attrs:
        arg.extend(("-R", attr))
    subprocess.check_call(arg, creationflags=get_creation_flags())


def read_map(mappath):
    result = {}
    with open(mappath, "r", encoding='ascii') as f:
        for line in f:
            if line.startswith(".text"):
                break

        next1 = f.readline()
        next2 = f.readline()
        assert next1.startswith(" *(.text)")
        assert next2.startswith(" .text")
        next1 = f.readline()

        while next1.strip() != "":
            vals = next1.strip().split(" ")

            for _ in range(vals.count("")):
                vals.remove("")

            addr = vals[0]
            func = vals[1]

            result[func] = int(addr, 16)
            next1 = f.readline()

    return result


def read_data(mappath):
    result = {}
    with open(mappath, "r", encoding='ascii') as f:
        for line in f:
            if line.startswith(".data"):
                break

        next1 = f.readline()
        next2 = f.readline()
        assert next1.startswith(" *(.data)")
        assert next2.startswith(" .data")
        next1 = f.readline()

        while next1.strip() != "":
            vals = next1.strip().split(" ")

            for _ in range(vals.count("")):
                vals.remove("")

            addr = vals[0]
            func = vals[1]

            result[func] = int(addr, 16)
            next1 = f.readline()

    return result


class Project:

    def __init__(self, dolpath, address=None, offset=None):
        with open(dolpath, "rb") as f:
            tmp = DolFile(f)

        try:
            _offset, addr, _size = tmp.allocate_text_section(4, address)
        except SectionCountFull as e:
            try:
                _offset, addr, _size = tmp.allocate_data_section(4, address)
            except SectionCountFull as e:
                raise RuntimeError("Dol is full! Cannot allocate any new sections") from e

        self._address = addr

        if offset is not None:
            self._address += offset
        del tmp
        with open(dolpath, "rb") as f:
            self.dol = DolFile(f)

        self.c_files = []
        self.asm_files = []

        self.linker_files = []

        self.branchlinks = []
        self.branches = []

        self.osarena_patcher = None
        self.functions = None

    def add_file(self, filepath):
        self.c_files.append(filepath)

    def add_asm_file(self, filepath):
        self.asm_files.append(filepath)

    def add_linker_file(self, filepath):
        self.linker_files.append(filepath)

    def branchlink(self, addr, funcname):
        self.branchlinks.append((addr, funcname))

    def branch(self, addr, funcname):
        self.branches.append((addr, funcname))

    def set_osarena_patcher(self, function):
        self.osarena_patcher = function

    def append_to_symbol_map(self, symbols, map_, newmap):
        addresses = []
        for k, v in symbols.items():
            addresses.append((k, v))
        addresses.sort(key=lambda x: x[1])

        with open(map_, "r", encoding='ascii') as f:
            data = f.read()

        with open(newmap, "w", encoding='ascii') as f:
            f.write(data)
            for i, v in enumerate(addresses):
                if i + 1 < len(addresses):
                    f.write("\n")
                    size = addresses[i + 1][1] - v[1]
                    f.write("{0:x} {1:08x} {0:x} 0 {2}".format(v[1], size, v[0]))

    def build(self, newdolpath):
        os.makedirs("tmp", exist_ok=True)

        for fpath in self.c_files:
            compile_(fpath, fpath + ".s", mode="-S")
            compile_(fpath, fpath + ".o", mode="-c")

        for fpath in self.asm_files:
            compile_(fpath, fpath + ".o", mode="-c")

        with open("tmplink", "w", encoding='ascii') as f:
            f.write("""SECTIONS
{{
    . = 0x{0:x};
    .text :
    {{
        *(.text)
    }}
	.rodata :
	{{
		*(.rodata*)
	}}
	.data :
	{{
		*(.data)
	}}
	. += 0x08;
	.sdata :
	{{
		*(.sdata)
	}}
}}""".format(self._address))
        linker_files = ["tmplink"]
        for fpath in self.linker_files:
            linker_files.append(fpath)
        link([fpath + ".o" for fpath in chain(self.c_files, self.asm_files)], "project.o",
             "project.map", linker_files)

        objcopy("project.o",
                "project.bin",
                "-O",
                "binary",
                "-g",
                "-S",
                attrs=[".eh_frame", ".comment", ".gnu.attributes"])

        with open("project.bin", "rb") as f:
            data = f.read()

        functions = read_map("project.map")

        _offset, sectionaddr, size = self.dol.allocate_text_section(len(data), addr=self._address)

        self.dol.seek(sectionaddr)
        self.dol.write(data)

        for addr, func in self.branches:
            if func not in functions:
                raise RuntimeError("Function not found in symbol map: {0}".format(func))

            branch(self.dol, addr, functions[func])

        for addr, func in self.branchlinks:
            if func not in functions:
                raise RuntimeError("Function not found in symbol map: {0}".format(func))

            branchlink(self.dol, addr, functions[func])

        if self.osarena_patcher is not None:
            self.osarena_patcher(self.dol, sectionaddr + size)

        with open(newdolpath, "wb") as f:
            self.dol.save(f)
