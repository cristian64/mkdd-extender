import itertools
import os
import subprocess
import tempfile
from dataclasses import dataclass

from tools.gc_c_kit import devkit_tools
from tools.lan_choose_character_kart import symbols


def run_subprocess(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.check_output(arguments, text=True)


def prepare_symbols_inc_file(filename: str, equ_symbols: dict[str, str],
                             global_symbols: list[str]) -> None:
    with open(filename, 'w', encoding='utf-8') as symbolsfile:
        equ_symbol_lines = '\n'.join([f'.equ {sym}, {equ_symbols[sym]}'
                                      for sym in equ_symbols]) + '\n'
        global_symbol_lines = '\n'.join([f'.global {adr}' for adr in global_symbols]) + '\n'
        symbolsfile.write(equ_symbol_lines + global_symbol_lines)


def prepare_symbols_ld_file(temp_dir: tempfile.TemporaryDirectory, region: str,
                            start_adr: int) -> None:
    symbolsld_path = os.path.join(temp_dir, 'symbols.ld')

    funcsymbol_defs = '\n'.join([
        f"{k} = {symbols.asmfuncsymbols[region][k]} - {f'0x{start_adr:08x}'};"
        for k in symbols.asmfuncsymbols[region]
    ])
    with open(symbolsld_path, 'w', encoding='utf-8') as symbol_ldfile:
        symbol_ldfile.write(f'''\
SECTIONS
{{
    . = {f"0x{start_adr}"};
    .text : {{
        {funcsymbol_defs}
    }}
}}
''')


@dataclass
class CodeBlockInfo:
    curasmfile: str
    blockstartname: str
    startoffset: int
    addressestoresolve: tuple[str]
    funcaddressestoresolve: tuple[str]
    tablerowdata: list


def make_data_file(region: str, temp_dir: tempfile.TemporaryDirectory, asm_dir: str) -> bytes:
    symbolsinc_path = os.path.join(temp_dir, 'symbols.inc')
    symbolsld_path = os.path.join(temp_dir, 'symbols.ld')

    codeblocks = (CodeBlockInfo(
        curasmfile="patchlogoapp_part2.s",
        blockstartname="NewCalcCodeBlockStart",
        startoffset=symbols.symbols[region]["OsakoM____sinit_ResMgr_cpp"],
        addressestoresolve=(
            "NetGateAppAfterCt",
            "NewDrawCodeBlockStart",
            "LANEntrySkipEntryCheck",
            "LANPlayInfoConditionallyResetConsoleKartEntryArray",
        ),
        funcaddressestoresolve=("LANEntryCalcPrintMenu", "ResolveConsoleAndControllerIDs",
                                "PrepareKartInfo", "CheckIfAllKartsHaveFinished"),
        tablerowdata=[]),
                  CodeBlockInfo(
                      curasmfile="lanentrydraw_beforeseconddraw.s",
                      blockstartname=None,
                      startoffset=symbols.symbols[region]["DriverDataChild__mDriverDataDefault"],
                      addressestoresolve=("LANEntryDrawBeforeSecondDraw", ),
                      funcaddressestoresolve=(),
                      tablerowdata=[]))
    for cb in codeblocks:
        prepare_symbols_inc_file(symbolsinc_path, symbols.symbols[region], cb.addressestoresolve)
        curasmfilepath = os.path.join(asm_dir, cb.curasmfile)
        tempobj_path = os.path.join(temp_dir, 'temp.o')

        run_subprocess([
            devkit_tools.ASPATH, curasmfilepath, '-mregnames', '-I', temp_dir, '-I', asm_dir, '-o',
            tempobj_path
        ])
        objdumpoutput = run_subprocess([devkit_tools.OBJDUMPPATH, '-t', tempobj_path])

        tablestart: str = 'SYMBOL TABLE:'
        startidx = objdumpoutput.index(tablestart) + len(tablestart)

        table_rows = objdumpoutput[startidx:].strip().replace('\t', ' ').replace('\r',
                                                                                 ' ').split('\n')
        cb.tablerowdata = [row.split(' ') for row in table_rows]
        #Remove empty strings
        cb.tablerowdata = [[entry for entry in table_row_column if entry != '']
                           for table_row_column in cb.tablerowdata]
        # extract only the needed columns - address, type and name.
        cb.tablerowdata = [[table_row_column[0], table_row_column[-3], table_row_column[-1]]
                           for table_row_column in cb.tablerowdata]

    for cb in codeblocks:
        ########################
        # Obtain New Code Offset
        ########################
        if cb.blockstartname is not None:
            try:
                newcode_offset = next(row for row in cb.tablerowdata
                                      if row[2] == cb.blockstartname and row[1] == '.text')
            except StopIteration:
                print(f'Could not find {cb.blockstartname} in symbol table of file {cb.curasmfile}')
                raise
            newcode_offset = int(newcode_offset[0], 0x10)
            cb.startoffset -= newcode_offset
            symbols.symbols[region][cb.curasmfile] = cb.startoffset

    # Match the rows with parent start offset to obtain final resolved value
    data_withasmfile = [(rowdata, cb.startoffset) for cb in codeblocks
                        for _, rowdata in enumerate(cb.tablerowdata)]

    equsymbols_toresolve = set(
        row[2] for cb in codeblocks for _, row in enumerate(cb.tablerowdata) \
        if row[2].endswith("Resolved") and row[1] == '*UND*' and row[2].replace('Resolved', '') \
        not in itertools.chain.from_iterable(cb.funcaddressestoresolve for cb in codeblocks)
    )

    for cb in codeblocks:
        #############################################
        # Obtain the offset of the new code addresses
        #############################################
        for newcodeaddress in cb.addressestoresolve:
            try:
                rowdata_matched, startoffset_matched = next(
                    datapair for datapair in data_withasmfile
                    if datapair[0][2] == newcodeaddress and datapair[0][1] == '.text')
            except StopIteration:
                print(f'Could not find {newcodeaddress} in any of the symbol tables')
                raise

            codeoffset = int(rowdata_matched[0], 0x10) + startoffset_matched
            symbols.symbols[region][newcodeaddress + "Resolved"] = codeoffset

        #################################################
        # Obtain the offset of the new function addresses
        #################################################
        for newcodeaddress in cb.funcaddressestoresolve:
            try:
                rowdata_matched, startoffset_matched = next(datapair
                                                            for datapair in data_withasmfile
                                                            if datapair[0][2] == newcodeaddress)
            except StopIteration:
                print(f'Could not find {newcodeaddress} in any of the symbol tables')
                raise

            codeoffset = int(rowdata_matched[0], 0x10) + startoffset_matched
            symbols.asmfuncsymbols[region][newcodeaddress + "Resolved"] = codeoffset

    for newsymboldata in equsymbols_toresolve:
        offset_matched, type_matched, startoffset_matched = next(
            rowdata[:2] + [cb.startoffset] for cb in codeblocks
            for _, rowdata in enumerate(cb.tablerowdata)
            if rowdata[2] == newsymboldata.replace('Resolved', ''))
        codeoffset = int(offset_matched,
                         0x10) + (startoffset_matched if type_matched == '.text' else 0)
        symbols.symbols[region][newsymboldata] = codeoffset

    finaldata_output: bytes = b''

    for cb in codeblocks:
        curasmfilepath = os.path.join(asm_dir, cb.curasmfile)
        asmfileobj_path = os.path.join(temp_dir, cb.curasmfile.replace(".s", ".o"))
        asmfileldobj_path = os.path.join(temp_dir, cb.curasmfile.replace(".s", "_ld.o"))

        prepare_symbols_inc_file(symbolsinc_path, symbols.symbols[region], [])
        run_subprocess([
            devkit_tools.ASPATH, curasmfilepath, '-mregnames', '-I', temp_dir, '-I', asm_dir, '-o',
            asmfileobj_path
        ])

        prepare_symbols_ld_file(temp_dir, region, symbols.symbols[region][cb.curasmfile])
        run_subprocess(
            [devkit_tools.LDPATH, asmfileobj_path, '-T', symbolsld_path, '-o', asmfileldobj_path])

        # Extract only the machine code from the ELF file
        devkit_tools.objcopy(asmfileldobj_path, '-O', 'binary', '-S')

        with open(asmfileldobj_path, 'rb') as obj_file:
            machinecode = obj_file.read()
            assert len(
                machinecode) != 0, f'Error with {cb.curasmfile}, did not compile to anything!'
            finaldata_output += machinecode

    return finaldata_output


DOL_TEXTOFFSET: int = 0x800030c0


def patch_maindol(region: str, dol_path: str, temp_dir: tempfile.TemporaryDirectory,
                  asm_dir: str) -> None:
    patchconfig = (
        ("SceneLanEntry__SceneLanEntry_after_Scene__Scene_call", patchcmd_asmfile,
         'patchlogoapp.s'),
        (
            "LANEntry__waitEntry_before_LANEntry__endReceipt",
            patchcmd_asm,
            ("li r0, 0x3", "stw r0, 0x0(r25)")  # Prevent endReceipt from being called
        ),
        ("LANEntry__calc_cmpwi_3_bge", patchcmd_bge, "LANEntry__calc_LANEntry__setRaceInfo_call"),
        ("LANEntry__calc_LANEntry__setRaceInfo_call", patchcmd_asmfile,
         "lanentrycalc_setraceinfo.s"),
        ("LANEntry_alloc_size", patchcmd_asm,
         "li r3, 0x33c"),  # Adjust alloc size to account for new fields used by character/kart menu
        ("LANEntry__draw_LANEntry_blo_draw", patchcmd_bl, "LANEntryDrawBeforeSecondDrawResolved"),
        ("LANEntry__calcAnm_lwz_JUTFader_vtable", patchcmd_asmfile, "lanentrycalcanm_timerup.s"),
        ("NetGateApp__NetGateApp_blr", patchcmd_b, "NetGateAppAfterCtResolved"),
        ("NetGateApp_alloc_size", patchcmd_asm, "li r3, 0x34+0x8"
         ),  # Adjust alloc size to account for pointer to arrow and B button textures
        ("LANEntry__start_blr", patchcmd_b, "LANEntrySkipEntryCheckResolved"),
        ("NetGameMgr_alloc_size", patchcmd_asm, "li r3, 0x1310"),
        ("LANPlayInfo__saveInfo_consoleKartCount_stbx", patchcmd_b,
         "LANPlayInfoConditionallyResetConsoleKartEntryArrayResolved"),
    )

    with open(dol_path, 'rb') as dol:
        dol = bytearray(dol.read())

    for sym, cmd, arg in patchconfig:
        adr = symbols.symbols[region][sym]
        cmdret = cmd(adr, arg, region, temp_dir, asm_dir)
        adr_resolved = adr - DOL_TEXTOFFSET
        dol[adr_resolved:adr_resolved + len(cmdret)] = cmdret

    with open(dol_path, 'wb') as patcheddol:
        patcheddol.write(dol)


def patchcmd_asm(_adr: int, instructions: str | tuple[str], _region: str,
                 temp_dir: tempfile.TemporaryDirectory, asm_dir: str) -> bytes:
    asmfile_path = os.path.join(temp_dir, 'temp.s')
    asmfileobj_path = os.path.join(temp_dir, 'temp.o')

    if isinstance(instructions, str):
        instructions = (instructions, )
    assert isinstance(instructions, tuple), f'instructions variable {instructions} is not a tuple!'

    with open(asmfile_path, 'w', encoding='utf-8') as tempasm:
        tempasm.write('\n'.join(instructions) + '\n')
    run_subprocess([
        devkit_tools.ASPATH, asmfile_path, '-mregnames', '-I', temp_dir, '-I', asm_dir, '-o',
        asmfileobj_path
    ])

    run_subprocess([devkit_tools.OBJCOPYPATH, asmfileobj_path, '-O', 'binary', '-g', '-S'])
    with open(asmfileobj_path, 'rb') as asmbin:
        return asmbin.read()


def patchcmd_asmfile(adr: int, filename: str, region: str, temp_dir: tempfile.TemporaryDirectory,
                     asm_dir: str) -> bytes:
    asmfile_path = os.path.join(asm_dir, filename)
    asmfileobj_path = os.path.join(temp_dir, filename.replace(".s", ".o"))
    asmfileldobj_path = os.path.join(temp_dir, filename.replace(".s", "_ld.o"))
    symbolsld_path = os.path.join(temp_dir, 'symbols.ld')

    run_subprocess([
        devkit_tools.ASPATH, asmfile_path, '-mregnames', '-I', temp_dir, '-I', asm_dir, '-o',
        asmfileobj_path
    ])
    prepare_symbols_ld_file(temp_dir, region, adr)

    run_subprocess(
        (devkit_tools.LDPATH, asmfileobj_path, '-T', symbolsld_path, '-o', asmfileldobj_path))
    devkit_tools.objcopy(asmfileldobj_path, '-O', 'binary', '-g', '-S')

    with open(asmfileldobj_path, 'rb') as asmbin:
        return asmbin.read()


def patchcmd_bl(adr: int, targetadr_sym: str, region: str, _temp_dir: tempfile.TemporaryDirectory,
                _asm_dir: str) -> bytes:
    return patchcmd_branchcommon(adr, targetadr_sym, region, 0x48000001)


def patchcmd_b(adr: int, targetadr_sym: str, region: str, _temp_dir: tempfile.TemporaryDirectory,
               _asm_dir: str) -> bytes:
    return patchcmd_branchcommon(adr, targetadr_sym, region, 0x48000000)


def patchcmd_bge(adr: int, targetadr_sym: str, region: str, _temp_dir: tempfile.TemporaryDirectory,
                 _asm_dir: str) -> bytes:
    return patchcmd_branchcommon(adr, targetadr_sym, region, 0x40800000)


def patchcmd_branchcommon(adr: int, targetadr_sym: str, region: str, word: int) -> bytes:
    targetadr = symbols.symbols[region][targetadr_sym]
    displacement = targetadr - adr
    instruction = word + ((pow(2, 26) + displacement) & 0b11111111111111111111111111)
    return instruction.to_bytes(4, 'big')
