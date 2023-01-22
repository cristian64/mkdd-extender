"""
Module for generating and injecting the game logic that makes possible the course page selection.
The GC-C-Kit tool is used for building and extracting the symbols that are then injected in the
input DOL file.
"""

import contextlib
import logging
import os
import shutil
import struct
import subprocess
import tempfile
import textwrap

from tools.gc_c_kit import devkit_tools
from tools.gc_c_kit import dolreader
from tools.gc_c_kit import doltools

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
data_dir = os.path.join(script_dir, 'data')
code_dir = os.path.join(data_dir, 'code')

BUTTONS_STATE_ADDRESSES = {
    'GM4E01': 0x803A4D6C,
    'GM4P01': 0x803AEB8C,
    'GM4J01': 0x803BF38C,
    'GM4E01dbg': 0x803FA764,
}
"""
These addresses point to a 6-byte structure that store the state of all buttons in the game pad.

For the NTSC and PAL versions, Dolphin already had codes that used this address, so it could be
borrowed. For the JAP version, it's been figured out by using the Dolphin Memory Engine tool,
searching first for the byte `0x11` (Z + D-pad Left), and then for `0x12` (Z + D-pad Right). Note
that these buttons are actually in the second byte.
"""

REDRAW_COURSESELECT_SCREEN_ADDRESSES = {
    'GM4E01': 0x803CE5B4,
    'GM4P01': 0x803D83D4,
    'GM4J01': 0x803E8BD4,
    'GM4E01dbg': 0x80419954,
}
"""
This is the address of a "variable" (likely a constant in static memory) that usually holds the
value `13.0f`.

It is used in `SceneCourseSelect::calcAnm()` to determine when `SceneCourseSelect::setTexture()`
needs to be invoked. This "variable" is then compared with another operand (given as a parameter),
which does change its value as the user navigates the courses in the course selection screen. Its
idle value is `10.0f`, and that's the value that the "variable" will be temporarily changed to to
force a redraw.

In NTSC, `calcAnm()` is located at `0x8016b6e0`, and invokes `setTexture` (located at `0x8016bd68`)
from `0x8016b70c`, after a single `if` condition described in the previous paragraph. This `if`
condition can be seen really well in Ghidra's decompilation of the ELF file.

To find these addresses in the other two regions, a memory breakpoint is set in a string of one of
the filepaths to any of the course labels (e.g. `CoName_BABY_PARK.bti`). While in the course
selection screen, scroll down to another course to hit the breakpoint, and Dolphin will take you to
the `setTexture()` function. Check the callstack until the following instructions are recognized in
it:

8016b6f8 7c 7f 1b 78     or         r31,r3,r3
8016b6fc c0 22 a0 14     lfs        f1,-0x5fec(r2)   # Or rtoc in Dolphin.
8016b700 c0 03 00 14     lfs        f0,0x14(r3)
8016b704 fc 01 00 00     fcmpu      cr0,f1,f0
8016b708 40 82 00 08     bne        LAB_8016b710
8016b70c 48 00 06 5d     bl         FUN_8016bd68

It is known that `calcAnm()` is the caller. Add then a breakpoint before the call to
`setTexture()` (e.g. in the `fcmpu` instruction), and change courses again to hit it. The value of
the `r2` register (+ the offset seen in the assembly), should tell which is the address of the
"variable" that we are after.
"""

SPAM_FLAG_ADDRESSES = {
    'GM4E01': 0x802ED5F8,
    'GM4P01': 0x802F90EC,
    'GM4J01': 0x80309B6C,
    'GM4E01dbg': 0x8032B158,
}
"""
Memory address used to determine whether the button combination can be accepted. The intent is to
force the player to release the D-pad before the page can be changed, avoiding potentially dangerous
spam.

This is the address to the first "This is padding" string (starting at "padding") that can be found
in memory, to ensure that it can be overridden safely.
"""

CURRENT_PAGE_ADDRESSES = {k: v + 1 for k, v in SPAM_FLAG_ADDRESSES.items()}
"""
Memory address where the currently selected page index is stored. Defined as the next byte after
the spam flag.
"""

COURSES = (
    'Luigi',
    'Peach',
    'BabyLuigi',
    'Desert',
    'Nokonoko',
    'Mario',
    'Daisy',
    'Waluigi',
    'Snow',
    'Patapata',
    'Yoshi',
    'Donkey',
    'Wario',
    'Diddy',
    'Koopa',
    'Rainbow',
)
"""
Internal names of the courses, in order of appearance.
"""

COURSE_TO_MINIMAP_ADDRESSES = {
    'GM4E01': {
        'BabyLuigi': (0x803CDDEC, 0x803CDDF0, 0x803CDDF4, 0x803CDDF8, 0x80141E14),
        'Peach': (0x803CDE0C, 0x803CDE10, 0x803CDE14, 0x803CDE18, 0x80141EE0),
        'Daisy': (0x803CDE34, 0x803CDE38, 0x803CDE3C, 0x803CDE40, 0x8014200c),
        'Luigi': (0x803CDE5C, 0x803CDE60, 0x803CDE64, 0x803CDE68, 0x801420D8),
        'Mario': (0x803CDE74, 0x803CDE78, 0x803CDE7C, 0x803CDE80, 0x801421A4),
        'Yoshi': (0x803CDE90, 0x803CDE94, 0x803CDE98, 0x803CDE9C, 0x80142270),
        'Nokonoko': (0x803CDEB0, 0x803CDEB4, 0x803CDEB8, 0x803CDEBC, 0x8014233c),
        'Patapata': (0x803CDEC8, 0x803CDECC, 0x803CDED0, 0x803CDED4, 0x80142408),
        'Waluigi': (0x803CDEE8, 0x803CDEEC, 0x803CDEF0, 0x803CDEF4, 0x801424D4),
        'Wario': (0x803CDF0C, 0x803CDF10, 0x803CDF14, 0x803CDF18, 0x801425A0),
        'Diddy': (0x803CDF28, 0x803CDF2C, 0x803CDF30, 0x803CDF34, 0x8014266C),
        'Donkey': (0x803CDF40, 0x803CDF44, 0x803CDF48, 0x803CDF4C, 0x80142738),
        'Koopa': (0x803CDF5C, 0x803CDF60, 0x803CDF64, 0x803CDF68, 0x80142804),
        'Rainbow': (0x803CDF70, 0x803CDF74, 0x803CDF78, 0x803CDF7C, 0x801428D0),
        'Desert': (0x803CDF84, 0x803CDF88, 0x803CDF8C, 0x803CDF90, 0x8014299C),
        'Snow': (0x803CDFA4, 0x803CDFA8, 0x803CDFAC, 0x803CDFB0, 0x80142A68),
    },
    'GM4P01': {
        'BabyLuigi': (0x803D7C2C, 0x803D7C30, 0x803D7C34, 0x803D7C38, 0x80141E44),
        'Peach': (0x803D7C4C, 0x803D7C50, 0x803D7C54, 0x803D7C58, 0x80141F10),
        'Daisy': (0x803D7C74, 0x803D7C78, 0x803D7C7C, 0x803D7C80, 0x8014203C),
        'Luigi': (0x803D7C9C, 0x803D7CA0, 0x803D7CA4, 0x803D7CA8, 0x80142108),
        'Mario': (0x803D7CB4, 0x803D7CB8, 0x803D7CBC, 0x803D7CC0, 0x801421D4),
        'Yoshi': (0x803D7CD0, 0x803D7CD4, 0x803D7CD8, 0x803D7CDC, 0x801422A0),
        'Nokonoko': (0x803D7CF0, 0x803D7CF4, 0x803D7CF8, 0x803D7CFC, 0x8014236C),
        'Patapata': (0x803D7D08, 0x803D7D0C, 0x803D7D10, 0x803D7D14, 0x80142438),
        'Waluigi': (0x803D7D28, 0x803D7D2C, 0x803D7D30, 0x803D7D34, 0x80142504),
        'Wario': (0x803D7D4C, 0x803D7D50, 0x803D7D54, 0x803D7D58, 0x801425D0),
        'Diddy': (0x803D7D68, 0x803D7D6C, 0x803D7D70, 0x803D7D74, 0x8014269C),
        'Donkey': (0x803D7D80, 0x803D7D84, 0x803D7D88, 0x803D7D8C, 0x80142768),
        'Koopa': (0x803D7D9C, 0x803D7DA0, 0x803D7DA4, 0x803D7DA8, 0x80142834),
        'Rainbow': (0x803D7DB0, 0x803D7DB4, 0x803D7DB8, 0x803D7DBC, 0x80142900),
        'Desert': (0x803D7DC4, 0x803D7DC8, 0x803D7DCC, 0x803D7DD0, 0x801429CC),
        'Snow': (0x803D7DE4, 0x803D7DE8, 0x803D7DEC, 0x803D7DF0, 0x80142A98),
    },
    'GM4J01': {
        'BabyLuigi': (0x803E840C, 0x803E8410, 0x803E8414, 0x803E8418, 0x80141E14),
        'Peach': (0x803E842C, 0x803E8430, 0x803E8434, 0x803E8438, 0x80141EE0),
        'Daisy': (0x803E8454, 0x803E8458, 0x803E845C, 0x803E8460, 0x8014200C),
        'Luigi': (0x803E847C, 0x803E8480, 0x803E8484, 0x803E8488, 0x801420D8),
        'Mario': (0x803E8494, 0x803E8498, 0x803E849C, 0x803E84A0, 0x801421A4),
        'Yoshi': (0x803E84B0, 0x803E84B4, 0x803E84B8, 0x803E84BC, 0x80142270),
        'Nokonoko': (0x803E84D0, 0x803E84D4, 0x803E84D8, 0x803E84DC, 0x8014233C),
        'Patapata': (0x803E84E8, 0x803E84EC, 0x803E84F0, 0x803E84F4, 0x80142408),
        'Waluigi': (0x803E8508, 0x803E850C, 0x803E8510, 0x803E8514, 0x801424D4),
        'Wario': (0x803E852C, 0x803E8530, 0x803E8534, 0x803E8538, 0x801425A0),
        'Diddy': (0x803E8548, 0x803E854C, 0x803E8550, 0x803E8554, 0x8014266C),
        'Donkey': (0x803E8560, 0x803E8564, 0x803E8568, 0x803E856C, 0x80142738),
        'Koopa': (0x803E857C, 0x803E8580, 0x803E8584, 0x803E8588, 0x80142804),
        'Rainbow': (0x803E8590, 0x803E8594, 0x803E8598, 0x803E859C, 0x801428D0),
        'Desert': (0x803E85A4, 0x803E85A8, 0x803E85AC, 0x803E85B0, 0x8014299C),
        'Snow': (0x803E85C4, 0x803E85C8, 0x803E85CC, 0x803E85D0, 0x80142A68),
    },
    'GM4E01dbg': {
        'BabyLuigi': (0x80419100, 0x80419104, 0x80419108, 0x8041910C, 0x8015415c),
        'Peach': (0x80419120, 0x80419124, 0x80419128, 0x8041912C, 0x80154254),
        'Daisy': (0x80419148, 0x8041914C, 0x80419150, 0x80419154, 0x801543ac),
        'Luigi': (0x80419170, 0x80419174, 0x80419178, 0x8041917C, 0x801544a4),
        'Mario': (0x80419188, 0x8041918C, 0x80419190, 0x80419194, 0x8015459c),
        'Yoshi': (0x804191A4, 0x804191A8, 0x804191AC, 0x804191B0, 0x80154694),
        'Nokonoko': (0x804191C4, 0x804191C8, 0x804191CC, 0x804191D0, 0x8015478c),
        'Patapata': (0x804191DC, 0x804191E0, 0x804191E4, 0x804191E8, 0x80154884),
        'Waluigi': (0x804191FC, 0x80419200, 0x80419204, 0x80419208, 0x8015497c),
        'Wario': (0x80419220, 0x80419224, 0x80419228, 0x8041922C, 0x80154a74),
        'Diddy': (0x8041923C, 0x80419240, 0x80419244, 0x80419248, 0x80154b6c),
        'Donkey': (0x80419254, 0x80419258, 0x8041925C, 0x80419260, 0x80154c64),
        'Koopa': (0x80419270, 0x80419274, 0x80419278, 0x8041927C, 0x80154d5c),
        'Rainbow': (0x80419284, 0x80419288, 0x8041928C, 0x80419290, 0x80154e54),
        'Desert': (0x80419298, 0x8041929C, 0x804192A0, 0x804192A4, 0x80154f4c),
        'Snow': (0x804192B8, 0x804192BC, 0x804192C0, 0x804192C4, 0x80155044),
    }
}
"""
The addresses (for each region) where the minimap values are stored.

Addresses (except the ones for the debug build) have been borrowed from the MKDD Track Patcher:

https://github.com/RenolY2/mkdd-track-patcher/blob/c0a8c7c97a9d9519888d7374c13cf31e010d82c4/src/resources/minimap_locations.json
"""

COURSE_TO_MINIMAP_VALUES = {
    'BabyLuigi': (-16572.30078125, -8286.099609375, 16572.30078125, 8286.099609375, 3),
    'Peach': (-22321.359375, -34855.83984375, 12534.3994140625, 34855.83984375, 2),
    'Daisy': (-42000.0, -20000.0, 38000.0, 20000.0, 3),
    'Luigi': (-18519.01953125, -37634.34765625, 16332.9404296875, 32069.701171875, 2),
    'Mario': (-19360.0, -38720.0, 19360.0, 38720.0, 2),
    'Yoshi': (-22050.0, -43050.0, 28350.0, 57750.0, 0),
    'Nokonoko': (-32285.599609375, -16658.701171875, 45813.0, 22390.6015625, 3),
    'Patapata': (-35800.0, -22500.0, 54200.0, 22500.0, 3),
    'Waluigi': (-25000.0, -13000.0, 27000.0, 13000.0, 1),
    'Wario': (-27000.0, -14500.0, 33000.0, 15500.0, 3),
    'Diddy': (-53460.0, -26730.0, 35640.0, 17820.0, 3),
    'Donkey': (-28636.720703125, -68430.875, 17479.201171875, 23800.958984375, 2),
    'Koopa': (-32400.0, -39600.0, 7200.0, 39600.0, 0),
    'Rainbow': (-28797.119140625, -54394.2890625, 25597.169921875, 54394.2890625, 0),
    'Desert': (-34715.8984375, -63251.5, 28535.69921875, 63251.5, 0),
    'Snow': (-15298.3203125, -42345.6796875, 29461.521484375, 47174.0, 0),
}
"""
The stock minimap values for each course.
"""


def read_minimap_values(game_id: str,
                        dol_path: str) -> 'dict[str, tuple[float, float, float, float, int]]':
    """
    Helper function that reads the minimap values from the DOL file.

    For unmodified, retail DOL files, it is expected that the return dictionary should match the
    dictionary held in the `COURSE_TO_MINIMAP_VALUES` constant.
    """
    minimap_values = {}

    with open(dol_path, 'rb') as f:
        dol_file = dolreader.DolFile(f)

        for course, addresses in COURSE_TO_MINIMAP_ADDRESSES[game_id].items():
            dol_file.seek(addresses[0])
            v0 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(addresses[1])
            v1 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(addresses[2])
            v2 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(addresses[3])
            v3 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(addresses[4] + 3)
            v4 = struct.unpack('>B', dol_file.read(1))[0]

            for v in (v0, v1, v2, v3):
                if -100000000.0 <= v <= 100000000.0:
                    continue
                raise RuntimeError('Unable to extract minimap values values from DOL file. '
                                   f'Corner value ({v4}) is unexpectedly large.')

            if v4 not in (0, 1, 2, 3):
                raise RuntimeError('Unable to extract minimap orientation values from DOL file. '
                                   f'Orientation enum value ({v4}) not in [0, 3].')

            minimap_values[course] = (v0, v1, v2, v3, v4)

    return minimap_values


COURSE_TO_STREAM_FILE_INDEX_ADDRESSES = {
    'GM4E01': 0x8052EB04,
    'GM4P01': 0x80538944,
    'GM4J01': 0x8053FC5C,
    'GM4E01dbg': 0x8057AA64,
}
"""
This address points to a `int[50]` structure where the file index of each audio track is stored for
each course. This is the array where the 50 values returned by the 50 calls to
`DVDConvertPathToEntrynum()` from within `JAUSection::newStreamFileTable()` are stored.

In the unedited game, the stock values for the first 32 integers are:

    Offset  Value  Description
    -------------------------------------------
    0x00    14     Baby Park
    0x04    15     Peach Beach
    0x08    15     Daisy Cruiser
    0x0C    17     Luigi Circuit
    0x10    17     Mario Circuit
    0x14    17     Yoshi Circuit
    0x18    19     Mushroom Bridge
    0x1C    19     Mushroom City
    0x20    23     Waluigi Stadium
    0x24    23     Wario Colosseum
    0x28    20     Dino Dino Jungle
    0x2C    20     DK Mountain
    0x30    16     Bowser's Castle
    0x34    21     Rainbow Road
    0x38    18     Dry Dry Desert
    0x3C    22     Sherbet Land
    0x40    25     Baby Park (final lap)
    0x44    26     Peach Beach (final lap)
    0x48    26     Daisy Cruiser (final lap)
    0x4C    28     Luigi Circuit (final lap)
    0x50    28     Mario Circuit (final lap)
    0x54    28     Yoshi Circuit (final lap)
    0x58    30     Mushroom Bridge (final lap)
    0x5C    30     Mushroom City (final lap)
    0x60    34     Waluigi Stadium (final lap)
    0x64    34     Wario Colosseum (final lap)
    0x68    31     Dino Dino Jungle (final lap)
    0x6C    31     DK Mountain (final lap)
    0x70    27     Bowser's Castle (final lap)
    0x74    32     Rainbow Road (final lap)
    0x78    29     Dry Dry Desert (final lap)
    0x7C    33     Sherbet Land (final lap)

This list matches the order in the BSFT file (and in the BSFT section in the BAA file). The rest of
the values in the integer array relate to other file indices such as the goal sound or the
commemoration sound, but they are not relevant at this point.

For the JAP and PAL versions, the address has been figured out by searching for
"00 00 00 0E 00 00 00 0F 00 00 00 0F 00 00 00 11 00 00 00 11 00 00 00 11 00 00 00 13" with the
Dolphin Memory Engine tool. For the PAL version, because the tree structure has two more files, an
offset of +2 has been added to each integer before searching for it.
"""

DIR_STRINGS = (
    '/Course/%s%s.arc',
    '/Course/Luigi2%s.arc',
    '/CourseName/%s/%s_name.bti',
    '/StaffGhosts/%s.ght',
)

FILE_STRINGS = (
    'COP_LUIGI_CIRCUIT.bti',
    'COP_PEACH_BEACH.bti',
    'COP_BABY_PARK.bti',
    'COP_KARA_KARA_DESERT.bti',
    'COP_KINOKO_BRIDGE.bti',
    'COP_MARIO_CIRCUIT.bti',
    'COP_DAISY_SHIP.bti',
    'COP_WALUIGI_STADIUM.bti',
    'COP_SHERBET_LAND.bti',
    'COP_KONOKO_CITY.bti',
    'COP_YOSHI_CIRCUIT.bti',
    'COP_DK_MOUNTAIN.bti',
    'COP_WARIO_COLOSSEUM.bti',
    'COP_DINO_DINO_JUNGLE.bti',
    'COP_BOWSER_CASTLE.bti',
    'COP_RAINBOW_ROAD.bti',
    'CoName_LUIGI_CIRCUIT.bti',
    'CoName_PEACH_BEACH.bti',
    'CoName_BABY_PARK.bti',
    'CoName_KARA_KARA_DESERT.bti',
    'CoName_KINOKO_BRIDGE.bti',
    'CoName_MARIO_CIRCUIT.bti',
    'CoName_DAISY_SHIP.bti',
    'CoName_WALUIGI_STADIUM.bti',
    'CoName_SHERBET_LAND.bti',
    'CoName_KINOKO_CITY.bti',
    'CoName_YOSHI_CIRCUIT.bti',
    'CoName_DK_MOUNTAIN.bti',
    'CoName_WARIO_COLOSSEUM.bti',
    'CoName_DINO_DINO_JUNGLE.bti',
    'CoName_BOWSER_CASTLE.bti',
    'CoName_RAINBOW_ROAD.bti',
    'CupName_MUSHROOM_CUP.bti',
    'CupName_FLOWER_CUP.bti',
    'CupName_STAR_CUP.bti',
    'CupName_SPECIAL_CUP.bti',
    'CupName_REVERSE2_CUP.bti',
    # LAN mode.
    'LUIGI_CIRCUIT',
    'PEACH_BEACH',
    'BABY_PARK',
    'KARA_KARA_DESERT',
    'KINOKO_BRIDGE',
    'MARIO_CIRCUIT',
    'DAISY_SHIP',
    'WALUIGI_STADIUM',
    'SHERBET_LAND',
    'KINOKO_CITY',
    'YOSHI_CIRCUIT',
    'DK_MOUNTAIN',
    'WARIO_COLOSSEUM',
    'DINO_DINO_JUNGLE',
    'BOWSER_CASTLE',
    'RAINBOW_ROAD',
    'CupName_MUSHROOM_CUP',
    'CupName_FLOWER_CUP',
    'CupName_STAR_CUP',
    'CupName_SPECIAL_CUP',
)


def find_addresses():
    """
    Helper function for finding the relevant strings in a memory dump for each region.

    If the set of strings change, `STRING_ADDRESSES` will need to be regenerated again.
    """
    raw_filepath = os.path.join(os.path.expanduser('~'), '.local', 'share', 'dolphin-emu', 'Dump',
                                'mem1.raw')
    with open(raw_filepath, 'rb') as f:
        data = f.read()

    game_id = data[:6].decode('ascii')

    print(f'    {game_id}: {{')

    for dir_string in DIR_STRINGS:
        address = data.find(dir_string.encode('ascii'))
        assert address > 0
        print(f'        \'{dir_string}\': 0x{address:08X},')

    unique_addresses = set()

    for file_string in FILE_STRINGS:
        address = data.find(file_string.encode('ascii'))
        assert address > 0
        if address in unique_addresses:
            # Some substrings (LAN mode) may find strings previously assigned to longer strings.
            ARBITRARY_OFFSET = 100  # Long enough to skip the used one.
            address = data.find(file_string.encode('ascii'), address + ARBITRARY_OFFSET)
            assert address > 0
        for i in range(len(file_string)):
            unique_addresses.add(address + i)
        print(f'        \'{file_string}\': 0x{address:08X},')

    print('    }')


STRING_ADDRESSES = {
    'GM4E01': {
        '/Course/%s%s.arc': 0x80336D3C,
        '/Course/Luigi2%s.arc': 0x80336D24,
        '/CourseName/%s/%s_name.bti': 0x80336CF4,
        '/StaffGhosts/%s.ght': 0x80336D10,
        'COP_LUIGI_CIRCUIT.bti': 0x80331FEC,
        'COP_PEACH_BEACH.bti': 0x8033201C,
        'COP_BABY_PARK.bti': 0x80332048,
        'COP_KARA_KARA_DESERT.bti': 0x80332078,
        'COP_KINOKO_BRIDGE.bti': 0x803320B0,
        'COP_MARIO_CIRCUIT.bti': 0x803320E4,
        'COP_DAISY_SHIP.bti': 0x80332114,
        'COP_WALUIGI_STADIUM.bti': 0x80332144,
        'COP_SHERBET_LAND.bti': 0x80332174,
        'COP_KONOKO_CITY.bti': 0x803321A4,
        'COP_YOSHI_CIRCUIT.bti': 0x803321D4,
        'COP_DK_MOUNTAIN.bti': 0x80332204,
        'COP_WARIO_COLOSSEUM.bti': 0x80332234,
        'COP_DINO_DINO_JUNGLE.bti': 0x80332268,
        'COP_BOWSER_CASTLE.bti': 0x803322A0,
        'COP_RAINBOW_ROAD.bti': 0x803322D0,
        'CoName_LUIGI_CIRCUIT.bti': 0x80331FD0,
        'CoName_PEACH_BEACH.bti': 0x80332004,
        'CoName_BABY_PARK.bti': 0x80332030,
        'CoName_KARA_KARA_DESERT.bti': 0x8033205C,
        'CoName_KINOKO_BRIDGE.bti': 0x80332094,
        'CoName_MARIO_CIRCUIT.bti': 0x803320C8,
        'CoName_DAISY_SHIP.bti': 0x803320FC,
        'CoName_WALUIGI_STADIUM.bti': 0x80332128,
        'CoName_SHERBET_LAND.bti': 0x8033215C,
        'CoName_KINOKO_CITY.bti': 0x8033218C,
        'CoName_YOSHI_CIRCUIT.bti': 0x803321B8,
        'CoName_DK_MOUNTAIN.bti': 0x803321EC,
        'CoName_WARIO_COLOSSEUM.bti': 0x80332218,
        'CoName_DINO_DINO_JUNGLE.bti': 0x8033224C,
        'CoName_BOWSER_CASTLE.bti': 0x80332284,
        'CoName_RAINBOW_ROAD.bti': 0x803322B8,
        'CupName_MUSHROOM_CUP.bti': 0x80331EDC,
        'CupName_FLOWER_CUP.bti': 0x80331EF8,
        'CupName_STAR_CUP.bti': 0x80331F10,
        'CupName_SPECIAL_CUP.bti': 0x80331F28,
        'CupName_REVERSE2_CUP.bti': 0x80331F40,
        'LUIGI_CIRCUIT': 0x80337698,
        'PEACH_BEACH': 0x803376A8,
        'BABY_PARK': 0x803376B4,
        'KARA_KARA_DESERT': 0x803376C0,
        'KINOKO_BRIDGE': 0x803376D4,
        'MARIO_CIRCUIT': 0x803376E4,
        'DAISY_SHIP': 0x803376F4,
        'WALUIGI_STADIUM': 0x80337700,
        'SHERBET_LAND': 0x80337710,
        'KINOKO_CITY': 0x80337720,
        'YOSHI_CIRCUIT': 0x8033772C,
        'DK_MOUNTAIN': 0x8033773C,
        'WARIO_COLOSSEUM': 0x80337748,
        'DINO_DINO_JUNGLE': 0x80337758,
        'BOWSER_CASTLE': 0x8033776C,
        'RAINBOW_ROAD': 0x8033777C,
        'CupName_MUSHROOM_CUP': 0x80337624,
        'CupName_FLOWER_CUP': 0x8033763C,
        'CupName_STAR_CUP': 0x80337650,
        'CupName_SPECIAL_CUP': 0x80337664,
    },
    'GM4P01': {
        '/Course/%s%s.arc': 0x80340B7C,
        '/Course/Luigi2%s.arc': 0x80340B64,
        '/CourseName/%s/%s_name.bti': 0x80340B34,
        '/StaffGhosts/%s.ght': 0x80340B50,
        'COP_LUIGI_CIRCUIT.bti': 0x8033BDBC,
        'COP_PEACH_BEACH.bti': 0x8033BDEC,
        'COP_BABY_PARK.bti': 0x8033BE18,
        'COP_KARA_KARA_DESERT.bti': 0x8033BE48,
        'COP_KINOKO_BRIDGE.bti': 0x8033BE80,
        'COP_MARIO_CIRCUIT.bti': 0x8033BEB4,
        'COP_DAISY_SHIP.bti': 0x8033BEE4,
        'COP_WALUIGI_STADIUM.bti': 0x8033BF14,
        'COP_SHERBET_LAND.bti': 0x8033BF44,
        'COP_KONOKO_CITY.bti': 0x8033BF74,
        'COP_YOSHI_CIRCUIT.bti': 0x8033BFA4,
        'COP_DK_MOUNTAIN.bti': 0x8033BFD4,
        'COP_WARIO_COLOSSEUM.bti': 0x8033C004,
        'COP_DINO_DINO_JUNGLE.bti': 0x8033C038,
        'COP_BOWSER_CASTLE.bti': 0x8033C070,
        'COP_RAINBOW_ROAD.bti': 0x8033C0A0,
        'CoName_LUIGI_CIRCUIT.bti': 0x8033BDA0,
        'CoName_PEACH_BEACH.bti': 0x8033BDD4,
        'CoName_BABY_PARK.bti': 0x8033BE00,
        'CoName_KARA_KARA_DESERT.bti': 0x8033BE2C,
        'CoName_KINOKO_BRIDGE.bti': 0x8033BE64,
        'CoName_MARIO_CIRCUIT.bti': 0x8033BE98,
        'CoName_DAISY_SHIP.bti': 0x8033BECC,
        'CoName_WALUIGI_STADIUM.bti': 0x8033BEF8,
        'CoName_SHERBET_LAND.bti': 0x8033BF2C,
        'CoName_KINOKO_CITY.bti': 0x8033BF5C,
        'CoName_YOSHI_CIRCUIT.bti': 0x8033BF88,
        'CoName_DK_MOUNTAIN.bti': 0x8033BFBC,
        'CoName_WARIO_COLOSSEUM.bti': 0x8033BFE8,
        'CoName_DINO_DINO_JUNGLE.bti': 0x8033C01C,
        'CoName_BOWSER_CASTLE.bti': 0x8033C054,
        'CoName_RAINBOW_ROAD.bti': 0x8033C088,
        'CupName_MUSHROOM_CUP.bti': 0x8033BCAC,
        'CupName_FLOWER_CUP.bti': 0x8033BCC8,
        'CupName_STAR_CUP.bti': 0x8033BCE0,
        'CupName_SPECIAL_CUP.bti': 0x8033BCF8,
        'CupName_REVERSE2_CUP.bti': 0x8033BD10,
        'LUIGI_CIRCUIT': 0x803414D8,
        'PEACH_BEACH': 0x803414E8,
        'BABY_PARK': 0x803414F4,
        'KARA_KARA_DESERT': 0x80341500,
        'KINOKO_BRIDGE': 0x80341514,
        'MARIO_CIRCUIT': 0x80341524,
        'DAISY_SHIP': 0x80341534,
        'WALUIGI_STADIUM': 0x80341540,
        'SHERBET_LAND': 0x80341550,
        'KINOKO_CITY': 0x80341560,
        'YOSHI_CIRCUIT': 0x8034156C,
        'DK_MOUNTAIN': 0x8034157C,
        'WARIO_COLOSSEUM': 0x80341588,
        'DINO_DINO_JUNGLE': 0x80341598,
        'BOWSER_CASTLE': 0x803415AC,
        'RAINBOW_ROAD': 0x803415BC,
        'CupName_MUSHROOM_CUP': 0x80341464,
        'CupName_FLOWER_CUP': 0x8034147C,
        'CupName_STAR_CUP': 0x80341490,
        'CupName_SPECIAL_CUP': 0x803414A4,
    },
    'GM4J01': {
        '/Course/%s%s.arc': 0x8035135C,
        '/Course/Luigi2%s.arc': 0x80351344,
        '/CourseName/%s/%s_name.bti': 0x80351314,
        '/StaffGhosts/%s.ght': 0x80351330,
        'COP_LUIGI_CIRCUIT.bti': 0x8034C60C,
        'COP_PEACH_BEACH.bti': 0x8034C63C,
        'COP_BABY_PARK.bti': 0x8034C668,
        'COP_KARA_KARA_DESERT.bti': 0x8034C698,
        'COP_KINOKO_BRIDGE.bti': 0x8034C6D0,
        'COP_MARIO_CIRCUIT.bti': 0x8034C704,
        'COP_DAISY_SHIP.bti': 0x8034C734,
        'COP_WALUIGI_STADIUM.bti': 0x8034C764,
        'COP_SHERBET_LAND.bti': 0x8034C794,
        'COP_KONOKO_CITY.bti': 0x8034C7C4,
        'COP_YOSHI_CIRCUIT.bti': 0x8034C7F4,
        'COP_DK_MOUNTAIN.bti': 0x8034C824,
        'COP_WARIO_COLOSSEUM.bti': 0x8034C854,
        'COP_DINO_DINO_JUNGLE.bti': 0x8034C888,
        'COP_BOWSER_CASTLE.bti': 0x8034C8C0,
        'COP_RAINBOW_ROAD.bti': 0x8034C8F0,
        'CoName_LUIGI_CIRCUIT.bti': 0x8034C5F0,
        'CoName_PEACH_BEACH.bti': 0x8034C624,
        'CoName_BABY_PARK.bti': 0x8034C650,
        'CoName_KARA_KARA_DESERT.bti': 0x8034C67C,
        'CoName_KINOKO_BRIDGE.bti': 0x8034C6B4,
        'CoName_MARIO_CIRCUIT.bti': 0x8034C6E8,
        'CoName_DAISY_SHIP.bti': 0x8034C71C,
        'CoName_WALUIGI_STADIUM.bti': 0x8034C748,
        'CoName_SHERBET_LAND.bti': 0x8034C77C,
        'CoName_KINOKO_CITY.bti': 0x8034C7AC,
        'CoName_YOSHI_CIRCUIT.bti': 0x8034C7D8,
        'CoName_DK_MOUNTAIN.bti': 0x8034C80C,
        'CoName_WARIO_COLOSSEUM.bti': 0x8034C838,
        'CoName_DINO_DINO_JUNGLE.bti': 0x8034C86C,
        'CoName_BOWSER_CASTLE.bti': 0x8034C8A4,
        'CoName_RAINBOW_ROAD.bti': 0x8034C8D8,
        'CupName_MUSHROOM_CUP.bti': 0x8034C4FC,
        'CupName_FLOWER_CUP.bti': 0x8034C518,
        'CupName_STAR_CUP.bti': 0x8034C530,
        'CupName_SPECIAL_CUP.bti': 0x8034C548,
        'CupName_REVERSE2_CUP.bti': 0x8034C560,
        'LUIGI_CIRCUIT': 0x80351CB8,
        'PEACH_BEACH': 0x80351CC8,
        'BABY_PARK': 0x80351CD4,
        'KARA_KARA_DESERT': 0x80351CE0,
        'KINOKO_BRIDGE': 0x80351CF4,
        'MARIO_CIRCUIT': 0x80351D04,
        'DAISY_SHIP': 0x80351D14,
        'WALUIGI_STADIUM': 0x80351D20,
        'SHERBET_LAND': 0x80351D30,
        'KINOKO_CITY': 0x80351D40,
        'YOSHI_CIRCUIT': 0x80351D4C,
        'DK_MOUNTAIN': 0x80351D5C,
        'WARIO_COLOSSEUM': 0x80351D68,
        'DINO_DINO_JUNGLE': 0x80351D78,
        'BOWSER_CASTLE': 0x80351D8C,
        'RAINBOW_ROAD': 0x80351D9C,
        'CupName_MUSHROOM_CUP': 0x80351C44,
        'CupName_FLOWER_CUP': 0x80351C5C,
        'CupName_STAR_CUP': 0x80351C70,
        'CupName_SPECIAL_CUP': 0x80351C84,
    },
    'GM4E01dbg': {
        '/Course/%s%s.arc': 0x8037D4E0,
        '/Course/Luigi2%s.arc': 0x8037D4C8,
        '/CourseName/%s/%s_name.bti': 0x8037D498,
        '/StaffGhosts/%s.ght': 0x8037D4B4,
        'COP_LUIGI_CIRCUIT.bti': 0x8037548C,
        'COP_PEACH_BEACH.bti': 0x803754BC,
        'COP_BABY_PARK.bti': 0x803754E8,
        'COP_KARA_KARA_DESERT.bti': 0x80375518,
        'COP_KINOKO_BRIDGE.bti': 0x80375550,
        'COP_MARIO_CIRCUIT.bti': 0x80375584,
        'COP_DAISY_SHIP.bti': 0x803755B4,
        'COP_WALUIGI_STADIUM.bti': 0x803755E4,
        'COP_SHERBET_LAND.bti': 0x80375614,
        'COP_KONOKO_CITY.bti': 0x80375644,
        'COP_YOSHI_CIRCUIT.bti': 0x80375674,
        'COP_DK_MOUNTAIN.bti': 0x803756A4,
        'COP_WARIO_COLOSSEUM.bti': 0x803756D4,
        'COP_DINO_DINO_JUNGLE.bti': 0x80375708,
        'COP_BOWSER_CASTLE.bti': 0x80375740,
        'COP_RAINBOW_ROAD.bti': 0x80375770,
        'CoName_LUIGI_CIRCUIT.bti': 0x80375470,
        'CoName_PEACH_BEACH.bti': 0x803754A4,
        'CoName_BABY_PARK.bti': 0x803754D0,
        'CoName_KARA_KARA_DESERT.bti': 0x803754FC,
        'CoName_KINOKO_BRIDGE.bti': 0x80375534,
        'CoName_MARIO_CIRCUIT.bti': 0x80375568,
        'CoName_DAISY_SHIP.bti': 0x8037559C,
        'CoName_WALUIGI_STADIUM.bti': 0x803755C8,
        'CoName_SHERBET_LAND.bti': 0x803755FC,
        'CoName_KINOKO_CITY.bti': 0x8037562C,
        'CoName_YOSHI_CIRCUIT.bti': 0x80375658,
        'CoName_DK_MOUNTAIN.bti': 0x8037568C,
        'CoName_WARIO_COLOSSEUM.bti': 0x803756B8,
        'CoName_DINO_DINO_JUNGLE.bti': 0x803756EC,
        'CoName_BOWSER_CASTLE.bti': 0x80375724,
        'CoName_RAINBOW_ROAD.bti': 0x80375758,
        'CupName_MUSHROOM_CUP.bti': 0x8037537C,
        'CupName_FLOWER_CUP.bti': 0x80375398,
        'CupName_STAR_CUP.bti': 0x803753B0,
        'CupName_SPECIAL_CUP.bti': 0x803753C8,
        'CupName_REVERSE2_CUP.bti': 0x803753E0,
        'LUIGI_CIRCUIT': 0x8037E808,
        'PEACH_BEACH': 0x8037E818,
        'BABY_PARK': 0x8037E824,
        'KARA_KARA_DESERT': 0x8037E830,
        'KINOKO_BRIDGE': 0x8037E844,
        'MARIO_CIRCUIT': 0x8037E854,
        'DAISY_SHIP': 0x8037E864,
        'WALUIGI_STADIUM': 0x8037E870,
        'SHERBET_LAND': 0x8037E880,
        'KINOKO_CITY': 0x8037E890,
        'YOSHI_CIRCUIT': 0x8037E89C,
        'DK_MOUNTAIN': 0x8037E8AC,
        'WARIO_COLOSSEUM': 0x8037E8B8,
        'DINO_DINO_JUNGLE': 0x8037E8C8,
        'BOWSER_CASTLE': 0x8037E8DC,
        'RAINBOW_ROAD': 0x8037E8EC,
        'CupName_MUSHROOM_CUP': 0x8037E794,
        'CupName_FLOWER_CUP': 0x8037E7AC,
        'CupName_STAR_CUP': 0x8037E7C0,
        'CupName_SPECIAL_CUP': 0x8037E7D4,
    }
}
"""
List of strings (and their addresses in static memory) that need to be modified by the injected
code.
"""

for _game_id, addresses in STRING_ADDRESSES.items():
    for string in addresses:
        assert string in DIR_STRINGS + FILE_STRINGS

for string in DIR_STRINGS + FILE_STRINGS:
    for _game_id, addresses in STRING_ADDRESSES.items():
        assert string in addresses

PLAY_SOUND_ADDRESSES = {
    'GM4E01': (0x80500A90, 0x803E2210, 0x803B0758),
    'GM4P01': (0x8050A8D0, 0x803EC050, 0x803BA578),
    'GM4J01': (0x8051B0B0, 0x803FC830, 0x803CAD78),
    'GM4E01dbg': (0x8054C9F0, 0x8042E170, 0x803FB2A4),
}
"""
These are the addresses of the pointers that are used as arguments to the `JAISeMgr::startSound()`
function, which will need to be passed to the C code to invoke the function with the correct
arguments.

That function's symbol is placed in the same memory address for all three regions (`0x8008b3d0`),
but the arguments it takes differ between regions. Also, in the debug build the symbol is at another
location (`0x80089974`).

In order to determine the value of these arguments (stored in r3, r4, r5, and r6), a breakpoint is
set in `JAUSoundMgr::startSound()` on the instruction where `JAISeMgr::startSound()` is invoked,
which is `0x800a4e2c`. Go to the course/cup selection screen, and switch between courses or cups
to hit the breakpoint. These should be the relevant addresses:

NTSC:
r3 0x80500a90
r4 0x803e2210
r5 0x803b0758
r6 0x00000000

PAL:
r3 0x8050a8d0
r4 0x803ec050
r5 0x803ba578
r6 0x00000000

JAP:
r3 0x8051b0b0
r4 0x803fc830
r5 0x803cad78
r6 0x00000000

NTSC (debug):
r3 0x8054c9f0
r4 0x8042e170
r5 0x803fb2a4
r6 0x00000000

Note that the address in r4 changes when the sound is played from a different screen (e.g. from the
select mode screen). It's not really relevant to us, because we only want to play sounds from the
course/cup selection screen. The address in r3 and r5 don't seem to change regardless of the screen.
The memory pointed by r5 holds `0x0`. And r6 is `0x0` always (my bet is this is the pointer to the
optional 3D position that `JAISeMgr::startSound()` accepts, which is not needed for 2D sounds).

The memory addressed by r4 needs to hold the sound ID (`0x20000` is the sound that is played when
the player navigates courses or cups; `0x2000c` can be used for a different sound, the one that is
played when the player accepts a letter in the initialism screen).
"""

LAN_STRUCT_ADDRESSES_AND_OFFSETS = {
    'GM4E01': (0x803D1420, 0x567C, 0x5666, 0x5668, 0x55F4, 0x566C),
    'GM4P01': (0x803DB240, 0x565C, 0x5646, 0x5648, 0x55D4, 0x564C),
    'GM4J01': (0x803EBA40, 0x567C, 0x5666, 0x5668, 0x55F4, 0x566C),
    'GM4E01dbg': (0x8041BF80, 0x55E4, 0x55CE, 0x55D0, 0x555C, 0x55D4),
}
"""
In the LAN menus, the images won't be refresh unless `setNextApp()` is called again. To replicate
that behavior, the instructions in that function are executed in our `refresh_lanselectmode()`
function, which matches in principle the body of the function (except for its early-out check, that
is omitted).

These are the last three statements in the `setNextApp()` function, which are replicated in our
code:

  *(int *)(in_r13 + -0x567c) = param_1;
  *(undefined *)(in_r13 + -0x5666) = 1;
  *(undefined *)(in_r13 + -0x5668) = 1;

Note that the first statement appears to be setting what appears to be the ID of "the next app".
That is, `param_1` (r3) is the next app ID, and is always 0x0B (LAN menus) for this use case. The
second statement seems to indicate that the app ID has changed (it is read in `AppMgr::calc()`). The
third/last statement is used to indicate that the next draw call needs to be skipped (see
`AppMgr::draw()`).

r13 is a pointer to some memory where many variables are stored, and that the assembly codes will be
modified, based on some offsets, as seen in the function that the assembly code is replicating.

Our function also includes another statement seen in `NetGateApp::call()`, that seems to be setting
another substate: 0x0 (SELECT MODE screen; the one with the options), 0x1 (main screen in the LAN
menus; the one with three entries: START GAME, SELECT MODE, QUIT LAN MODE). The one we want is 0x0.
(This part becomes relevant after the first race, as the value is changed to 0x1.)

The last offset was spotted in use in `AppMgr::calc()`, and it seems to be used as the last check
to determine whether the current app needs to be deleted. That is, it is used to mark the app for
deletion. It appears nested under two if conditions; the ones testing the first two offsets. This
offset can be seen in `AppMgr::deleteCurrentApp()`, a function (only seen in the debug build) that
all it does is set that bit to 1. There are also other places that do not use the function but also
set the bit to 1.

The offsets, as well as the content of r13, vary between regions, and are:

    NTSC:         0x803d1420  -0x567c  -0x5666  -0x5668  -0x55f4  -0x566C
    PAL:          0x803db240  -0x565c  -0x5646  -0x5648  -0x55d4  -0x564C
    JAP:          0x803eba40  -0x567c  -0x5666  -0x5668  -0x55f4  -0x566C
    NTSC (debug): 0x8041bf80  -0x55e4  -0x55ce  -0x55d0  -0x555c  -0x55d4

Hypothetical variables names for these "r13 + offset" variables:
    #1: eNextAppID
    #2: bAppIDChanged
    #3: bSkipNextDraw
    #4: eNetGateAppSubstateID
    #5: bMarkForDeletion

Basically, a breakpoint is set in `setNextApp()` to write down the first three offsets, and r13. In
the regions without symbols, `setNextApp()` is found by searching for
`28 00 00 00 41 82 00 1c 80 0d` (two instructions and a half), which returns a single result; these
are the addresses to the `setNextApp()` symbol:

    NTSC:         0x801d1d78
    PAL:          0x801d1d04
    JAP:          0x801d1d78
    NTSC (debug): 0x80200c90

`NetGateApp::call()` can be located by searching for the place where `setNextApp()` is invoked with
the argument set to `0xB`. The forth offset is sourced from this function, whose addresses are:

    NTSC:         0x801d9b58
    PAL:          0x801d9b3c
    JAP:          0x801d9b80
    NTSC (debug): 0x80209474

`AppMgr::calc()` can be located by searching for `54 80 07 fa 54 83 07 f8 90 0d` (two instructions
and a half). The fifth and final offset is sourced from this function, and can be spotted in a
[nested] condition after two other conditions that evaluate some variables using the first two
offsets. The addresses of the function are:

    NTSC:         0x801d1b68
    PAL:          0x801d1af4
    JAP:          0x801d1b68
    NTSC (debug): 0x80200a80
"""

SCENECOURSESELECT_CALCANM_CALL_ADDRESSES = {
    'GM4E01': 0x8016B110,
    'GM4P01': 0x80169FB4,
    'GM4J01': 0x8016B110,
    'GM4E01dbg': 0x80188CD0,
}
"""
The address within `SceneCourseSelect::course()` from where `SceneCourseSelect::calcAnm()` is
invoked. Easy to locate in the debugger if a breakpoint is set, or in Ghidra when looking for
references to `SceneCourseSelect::calcAnm()`.

This is one of the `bl` instructions that will be hijacked.
"""

LANSELECTMODE_CALCANM_CALL_ADDRESSES = {
    'GM4E01': 0x801E4258,
    'GM4P01': 0x801E4230,
    'GM4J01': 0x801E4280,
    'GM4E01dbg': 0x80215FF4,
}
"""
The address within `LANSelectMode::calc()` from where `LANSelectMode::calcAnm()` is invoked. Easy to
locate in the debugger if a breakpoint is set, or in Ghidra when looking for references to
`LANSelectMode::calcAnm()`.

This is one of the `bl` instructions that will be hijacked.
"""

OSARENALO_INSTRUCTIONS_ADDRESSES = {
    'GM4E01': 0x800E5CD4,
    'GM4P01': 0x800E5C98,
    'GM4J01': 0x800E5CD4,
    'GM4E01dbg': 0x800EC6C8,
}
"""
The addresses to the instruction sequence where the OS Arena's low value is loaded into r3 before
`SetOSArenaLo()` is invoked.
"""

OSARENALO_ADDRESSES = {
    'GM4E01': 0x803E2300,
    'GM4P01': 0x803EC140,
    'GM4J01': 0x803FC920,
    'GM4E01dbg': 0x8042E260,
}
"""
The retail OS Arena's low values. These are the values that are calculated in `OSInit()` in the
retail ISO images when the instruction sequence (see `OSARENALO_INSTRUCTIONS_ADDRESSES`) is
executed.
"""

for address in OSARENALO_ADDRESSES.values():
    assert address % 32 == 0

SYMBOLS_MAP = {
    'GM4E01':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        JAISeMgr__startSound = 0x8008b3d0;
        SceneCourseSelect__calcAnm = 0x8016b6e0;
        LANSelectMode__calcAnm = 0x801e428c;
        """),
    'GM4P01':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        JAISeMgr__startSound = 0x8008b3d0;
        SceneCourseSelect__calcAnm = 0x8016a584;
        LANSelectMode__calcAnm = 0x801e4264;
        """),
    'GM4J01':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        JAISeMgr__startSound = 0x8008b3d0;
        SceneCourseSelect__calcAnm = 0x8016b6e0;
        LANSelectMode__calcAnm = 0x801e42b4;
        """),
    'GM4E01dbg':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        JAISeMgr__startSound = 0x80089974;
        SceneCourseSelect__calcAnm = 0x80189448;
        LANSelectMode__calcAnm = 0x80216028;
        """),
}
"""
Minimal symbols map for each region.
"""


@contextlib.contextmanager
def current_directory(dirpath):
    cwd = os.getcwd()
    try:
        os.chdir(dirpath)
        yield
    finally:
        os.chdir(cwd)


def aligned(value: int, alignment: int = 32) -> int:
    return (value | alignment - 1) + 1 if value % alignment else value


def find_char_offset_in_string(string: str) -> int:
    if string.startswith('/'):
        # Find the first slash (/) character (after position 1, as some strings start with a forward
        # slash, but that's not the one we are looking for).
        return string.find('/', 1) - 1

    # The last character before the extension.
    return len(os.path.splitext(string)[0]) - 1


def read_osarena(dol_path, game_id) -> int:
    with open(dol_path, 'rb') as f:
        dol_file = dolreader.DolFile(f)
        dol_file.seek(OSARENALO_INSTRUCTIONS_ADDRESSES[game_id])

        instruction = struct.unpack('>H', dol_file.read(2))[0]
        if instruction != 0x3C60:  # lis r3, _
            raise RuntimeError(f'Unexpected instruction: 0x{instruction:04X}')
        value_high = struct.unpack('>H', dol_file.read(2))[0]

        instruction = struct.unpack('>H', dol_file.read(2))[0]
        if instruction == 0x3863:  # addi/subi r3, r3, _ (seen in stock DOL files)
            value_low = struct.unpack('>h', dol_file.read(2))[0]
            value = (value_high << 16) + value_low
        elif instruction == 0x6063:  # ori r3, r3, _ (can be seen in the wild)
            value_low = struct.unpack('>H', dol_file.read(2))[0]
            value = (value_high << 16) | value_low
        else:
            raise RuntimeError(f'Unexpected instruction: 0x{instruction:04X}')

        instruction = struct.unpack('>I', dol_file.read(4))[0]
        if instruction == 0x3803001F:  # addi r0, r3, 0x1f
            value += 31
        else:
            raise RuntimeError(f'Unexpected instruction: 0x{instruction:08X}')

        instruction = struct.unpack('>I', dol_file.read(4))[0]
        if instruction == 0x54030034:  # rlwinm r3, r0, 0x0, 0x0, 0x1a
            value &= 0xFFFFFFE0
        else:
            raise RuntimeError(f'Unexpected instruction: 0x{instruction:08X}')

        return value


def patch_bti_filenames_in_blo_file(game_id: str, blo_path: str):
    with open(blo_path, 'rb') as f:
        data = f.read()

    for string in STRING_ADDRESSES[game_id]:
        char_offset = find_char_offset_in_string(string)
        new_string = bytearray(string, encoding='ascii')
        new_string[char_offset] = ord('0')
        string = bytes(string, encoding='ascii')
        data = data.replace(string, new_string)

    with open(blo_path, 'wb') as f:
        f.write(data)


def patch_dol_file(game_id: str, minimap_data: dict, audio_track_data: 'tuple[tuple[int]]',
                   dol_path: str, log: logging.Logger):
    log.info('Generating and injecting C code...')

    page_count = len(audio_track_data)

    unaligned_previous_osarena_value = read_osarena(dol_path, game_id)
    dol_section_address = aligned(unaligned_previous_osarena_value)
    unaligned_new_osarena_value = 0
    injected_code_size = 0

    def patch_osarena(dol_file, dol_section_address_plus_size):
        nonlocal unaligned_new_osarena_value
        nonlocal injected_code_size
        nonlocal injected_code_size
        unaligned_new_osarena_value = dol_section_address_plus_size
        injected_code_size = dol_section_address_plus_size - dol_section_address

        dol_file.seek(OSARENALO_INSTRUCTIONS_ADDRESSES[game_id])
        doltools.write_lis(dol_file, 3, unaligned_new_osarena_value >> 16, signed=False)
        doltools.write_ori(dol_file, 3, 3, unaligned_new_osarena_value & 0xFFFF)

    # String data.
    string_data_code_lines = []
    char_addresses = []
    for string, address in STRING_ADDRESSES[game_id].items():
        char_offset = find_char_offset_in_string(string)
        char_address = address + char_offset
        char_addresses.append(f'(char*)0x{char_address:08X}')
    char_addresses = ', '.join(char_addresses)
    string_data_code_lines.append(f'char* char_addresses[] = {{{char_addresses}}};')
    string_data_code = '\n'.join(string_data_code_lines)

    # Minimap data.
    initial_minimap_values = read_minimap_values(game_id, dol_path)
    minimap_data_code_lines = []
    minimap_data_code_lines.append('float* coordinates_addresses[16 * 4] = {')
    for track_index in range(16):
        if track_index > 0:
            minimap_data_code_lines.append(',')
        addresses = COURSE_TO_MINIMAP_ADDRESSES[game_id][COURSES[track_index]]
        for i in range(4):
            comma = '' if i == 0 else ', '
            minimap_data_code_lines.append(f'{comma}(float*)0x{addresses[i]:08X}')
    minimap_data_code_lines.append('};')
    minimap_data_code_lines.append('char* orientations_addresses[16] = {')
    for track_index in range(16):
        if track_index > 0:
            minimap_data_code_lines.append(',')
        addresses = COURSE_TO_MINIMAP_ADDRESSES[game_id][COURSES[track_index]]
        minimap_data_code_lines.append(f'(char*)0x{addresses[4] + 3:08X}')
    minimap_data_code_lines.append('};')
    minimap_data_code_lines.append('const float coordinates[PAGE_COUNT][16 * 4] = {')
    for page_index in range(page_count):
        minimap_data_code_lines.append('{' if page_index == 0 else ', {')
        for track_index in range(16):
            if track_index > 0:
                minimap_data_code_lines.append(',')
            if page_index == 0:
                values = initial_minimap_values[COURSES[track_index]]
            else:
                values = minimap_data[(page_index, track_index)]
            for i in range(4):
                comma = '' if i == 0 else ', '
                minimap_data_code_lines.append(f'{comma}{values[i]}f')
        minimap_data_code_lines.append('}')
    minimap_data_code_lines.append('};')
    minimap_data_code_lines.append('const char orientations[PAGE_COUNT][16] = {')
    for page_index in range(page_count):
        minimap_data_code_lines.append('{' if page_index == 0 else ', {')
        for track_index in range(16):
            if track_index > 0:
                minimap_data_code_lines.append(',')
            if page_index == 0:
                values = initial_minimap_values[COURSES[track_index]]
            else:
                values = minimap_data[(page_index, track_index)]
            minimap_data_code_lines.append(f'{values[4]}')
        minimap_data_code_lines.append('}')
    minimap_data_code_lines.append('};')
    minimap_data_code = '\n'.join(minimap_data_code_lines)

    # Audio track indices.
    audio_data_code_lines = []
    audio_data_code_lines.append('const char audio_indexes[PAGE_COUNT][32] = {')
    for page_index, audio_indexes in enumerate(audio_track_data):
        audio_data_code_lines.append('{' if page_index == 0 else ', {')
        for i, audio_index in enumerate(audio_indexes):
            if i > 0:
                audio_data_code_lines.append(',')
            assert 0 <= audio_index < 256
            audio_data_code_lines.append(f'{audio_index}')
        audio_data_code_lines.append('}')
    audio_data_code_lines.append('};')
    audio_data_code = '\n'.join(audio_data_code_lines)

    for pass_number in range(2):
        # The project is going to be built twice; the size of the new DOL section needs to be known
        # to determine the OS Arena, which needs too be known to determine the offset required for
        # certain of the addresses that appear in the C code that refer to dynamic memory. When the
        # OS Arena changes, these addresses need to be offset too, based on the new value, and the
        # retail value.
        offset = aligned(unaligned_new_osarena_value) - OSARENALO_ADDRESSES[game_id]

        # Load the C file and replace constants and placeholders.
        replacements = (
            ('__BUTTONS_STATE_ADDRESS__', f'0x{BUTTONS_STATE_ADDRESSES[game_id]:08X}'),
            ('__COURSE_TO_STREAM_FILE_INDEX_ADDRESS__',
             f'0x{COURSE_TO_STREAM_FILE_INDEX_ADDRESSES[game_id] + offset:08X}'),
            ('__CURRENT_PAGE_ADDRESS__', f'0x{CURRENT_PAGE_ADDRESSES[game_id]:08X}'),
            ('__LAN_STRUCT_ADDRESS__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][0]:08X}'),
            ('__LAN_STRUCT_OFFSET1__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][1]:04X}'),
            ('__LAN_STRUCT_OFFSET2__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][2]:04X}'),
            ('__LAN_STRUCT_OFFSET3__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][3]:04X}'),
            ('__LAN_STRUCT_OFFSET4__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][4]:04X}'),
            ('__LAN_STRUCT_OFFSET5__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][5]:04X}'),
            ('__PAGE_COUNT__', f'{page_count}'),
            ('__PLAY_SOUND_R3__', f'0x{PLAY_SOUND_ADDRESSES[game_id][0] + offset:08X}'),
            ('__PLAY_SOUND_R4__', f'0x{PLAY_SOUND_ADDRESSES[game_id][1]:08X}'),
            ('__PLAY_SOUND_R5__', f'0x{PLAY_SOUND_ADDRESSES[game_id][2]:08X}'),
            ('__REDRAW_COURSESELECT_SCREEN_ADDRESS__',
             f'0x{REDRAW_COURSESELECT_SCREEN_ADDRESSES[game_id]:08X}'),
            ('__SPAM_FLAG_ADDRESS__', f'0x{SPAM_FLAG_ADDRESSES[game_id]:08X}'),
            ('// __AUDIO_DATA_PLACEHOLDER__', audio_data_code),
            ('// __MINIMAP_DATA_PLACEHOLDER__', minimap_data_code),
            ('// __STRING_DATA_PLACEHOLDER__', string_data_code),
        )
        with open(os.path.join(code_dir, 'lib.c'), 'r', encoding='ascii') as f:
            code = f.read()
        for name, value in replacements:
            code = code.replace(name, value)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with current_directory(tmp_dir):
                project = devkit_tools.Project(dol_path, address=dol_section_address)
                project.set_osarena_patcher(patch_osarena)

                # Initialize static variables.
                for address in (SPAM_FLAG_ADDRESSES[game_id], CURRENT_PAGE_ADDRESSES[game_id]):
                    project.dol.seek(address)
                    project.dol.write(b'\0')

                # Initialize the strings with the character of the first page ('0').
                for string, address in STRING_ADDRESSES[game_id].items():
                    char_offset = find_char_offset_in_string(string)
                    char_address = address + char_offset
                    project.dol.seek(char_address)
                    project.dol.write(b'0')

                with open('symbols.txt', 'w', encoding='ascii') as f:
                    f.write(SYMBOLS_MAP[game_id])
                project.add_linker_file('symbols.txt')

                with open('lib.c', 'w', encoding='ascii') as f:
                    f.write(code)

                project.add_file('lib.c')
                project.branchlink(SCENECOURSESELECT_CALCANM_CALL_ADDRESSES[game_id],
                                   "scenecourseselect_calcanm_ex")
                project.branchlink(LANSELECTMODE_CALCANM_CALL_ADDRESSES[game_id],
                                   "lanselectmode_calcanm_ex")
                project.build('main.dol' if pass_number == 0 else dol_path)

                # Diagnosis logging only if enabled on the user end.
                if pass_number == 1 and os.environ.get('MKDDEXTENDER_VERBOSE'):
                    # If Clang-Format is available in the system, run the C file through it.
                    shutil.copyfile(os.path.join(code_dir, '.clang-format'), '.clang-format')
                    try:
                        subprocess.call(('clang-format', '-i', 'lib.c'))
                    except Exception:
                        pass

                    with open('lib.c', 'r', encoding='ascii') as f:
                        print('#' * 80)
                        print(f'{" C Code ":#^80}')
                        print('#' * 80)
                        print(f.read())

                    with open('lib.c.s', 'r', encoding='ascii') as f:
                        print('#' * 80)
                        print(f'{" Assembly Code ":#^80}')
                        print('#' * 80)
                        print(f.read())

                    with open('project.map', 'r', encoding='ascii') as f:
                        print('#' * 80)
                        print(f'{" Symbols Map ":#^80}')
                        print('#' * 80)
                        print(f.read())

                    print('#' * 80)
                    print(f'{" Object Dump ":#^80}')
                    print('#' * 80)
                    devkit_tools.objdump('project.o', '--full-content')

    log.info(f'Injected {injected_code_size} bytes of new code. '
             f'OS Arena: 0x{aligned(unaligned_previous_osarena_value):08X} (previous) -> '
             f'0x{aligned(unaligned_new_osarena_value):08X} (new).')
