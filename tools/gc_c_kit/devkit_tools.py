import subprocess 
import os 
from itertools import chain
from dolreader import DolFile, SectionCountFull
from doltools import branchlink, branch, apply_gecko

GCCPATH = "C:\\devkitPro\\devkitPPC\\bin\\powerpc-eabi-gcc.exe"
LDPATH = "C:\\devkitPro\\devkitPPC\\bin\\powerpc-eabi-ld.exe"
OBJDUMPPATH = "C:\\devkitPro\\devkitPPC\\bin\\powerpc-eabi-objdump.exe"
OBJCOPYPATH = "C:\\devkitPro\\devkitPPC\\bin\\powerpc-eabi-objcopy.exe"


def compile(inpath, outpath, mode, optimize="-O1", std="c99", warning="-w"):
    assert mode in ("-S", "-c") # turn into asm or compile 
    #args = [GCCPATH, inpath, mode, "-o", outpath, optimize, "-std="+std, warning]
    args = [GCCPATH, inpath, mode, "-o", outpath, optimize, warning]
    print(args)
    subprocess.call(args)
    
    
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
    print(arg)
    subprocess.call(arg)
    
    
def objdump(*args):
    arg = [OBJDUMPPATH]
    arg.extend(args)
    print(arg)
    subprocess.call(arg)


def objcopy(*args, attrs = []):
    arg = [OBJCOPYPATH]
    arg.extend(args)
    for attr in attrs:
        arg.extend(("-R", attr))
    print(arg)
    subprocess.call(arg)
    
    
def read_map(mappath):
    result = {}
    with open(mappath, "r") as f:
        for line in f:
            if line.startswith(".text"):
                break 
        
        next = f.readline()
        next2 = f.readline()
        assert next.startswith(" *(.text)")
        assert next2.startswith(" .text")
        next = f.readline()
        
        while next.strip() != "":
            vals = next.strip().split(" ")

            for i in range(vals.count("")):
                vals.remove("")
            
            addr = vals[0]
            func = vals[1]
            
            result[func] = int(addr, 16) 
            next = f.readline()
    
    return result 


class Project(object):
    def __init__(self, dolpath, address=None, offset=None):
        with open(dolpath,"rb") as f:
            tmp = DolFile(f)
        
        try:
            _offset, addr, size = tmp.allocate_text_section(4, address)
        except SectionCountFull as e:
            print(e)
            try:
                _offset, addr, size = tmp.allocate_data_section(4, address)
            except SectionCountFull as e:
                print(e)
                raise RuntimeError("Dol is full! Cannot allocate any new sections")
        
        self._address = addr

        if offset is not None:
            self._address += offset
        del tmp 
        with open(dolpath,"rb") as f:
            self.dol = DolFile(f)
        
        self.c_files = []
        self.asm_files = []
        
        self.linker_files = []
        
        self.branchlinks = []
        self.branches = []
        
        self.osarena_patcher = None 
        
        
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
        
    def apply_gecko(self, geckopath):
        with open(geckopath, "r") as f:
            apply_gecko(self.dol, f)
    
    def build(self, newdolpath, address=None, offset=None):
        os.makedirs("tmp", exist_ok=True)
        
        for fpath in self.c_files:
            compile(fpath, fpath+".s", mode="-S")
            compile(fpath, fpath+".o", mode="-c")
        
        for fpath in self.asm_files:
            compile(fpath, fpath+".o", mode="-c")
        
        inputobjects = [fpath+".o" for fpath in chain(self.c_files, self.asm_files)]
        with open("tmplink", "w") as f:
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
        link(   [fpath+".o" for fpath in chain(self.c_files, self.asm_files)], 
                "project.o", "project.map", linker_files)
        
        objdump("project.o", "--full-content")
        
        objcopy("project.o", "project.bin", "-O", "binary", "-g", "-S", attrs=[".eh_frame", ".comment", ".gnu.attributes"])
        
        with open("project.bin", "rb") as f:
            data = f.read()
        
        functions = read_map("project.map")
        
        offset, sectionaddr, size = self.dol.allocate_text_section(len(data), addr=self._address)
        
        self.dol.seek(sectionaddr)
        self.dol.write(data)
        
        #print(("{0}: 0x{1:x}".format(funct
        for addr, func in self.branches:
            if func not in functions:
                print("Function not found in symbol map: {0}. Skipping...".format(func))
                continue
                #raise RuntimeError("Function not found in symbol map: {0}".format(func))
            
            branch(self.dol, addr, functions[func])
        
        for addr, func in self.branchlinks:
            if func not in functions:
                print("Function not found in symbol map: {0}. Skipping...".format(func))
                continue
                #raise RuntimeError("Function not found in symbol map: {0}".format(func))
            
            branchlink(self.dol, addr, functions[func])
        
        if self.osarena_patcher is not None:
            self.osarena_patcher(self.dol, sectionaddr+size)
        
        with open(newdolpath, "wb") as f:
            self.dol.save(f)
        
if __name__ == "__main__":
    compile("main.c", "main.s", mode="-S")
    compile("main.c", "main.o", mode="-c")