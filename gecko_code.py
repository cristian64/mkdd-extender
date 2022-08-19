"""
Script that generates data-driven Gecko codes for extending the stock number of courses in
Mario Kart: Double Dash!!.
"""

import os
import struct
import textwrap

from tools.GeckoLoader import dolreader

BUTTONS_STATE_ADDRESSES = {
    'GM4E01': 0x003A4D6C,
    'GM4P01': 0x003AEB8C,
    'GM4J01': 0x003BF38C,
    'GM4E01dbg': 0x003FA764,
}
"""
These addresses point to a 6-byte structure that store the state of all buttons in the game pad.

For the NTSC and PAL versions, Dolphin already had codes that used this address, so it could be
borrowed. For the JAP version, it's been figured out by using the Dolphin Memory Engine tool,
searching first for the byte `0x11` (Z + D-pad Left), and then for `0x12` (Z + D-pad Right). Note
that these buttons are actually in the second byte.
"""

BUTTON_LEFT = 0x00000001
BUTTON_RIGHT = 0x00000002
BUTTON_UP = 0x00000008
BUTTON_DOWN = 0x00000004
BUTTON_Z = 0x00000010

REDRAW_COURSESELECT_SCREEN_ADDRESSES = {
    'GM4E01': 0x003CE5B4,
    'GM4P01': 0x003D83D4,
    'GM4J01': 0x003E8BD4,
    'GM4E01dbg': 0x00419954,
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
    'GM4E01': 0x002ED5F8,
    'GM4P01': 0x002F90EC,
    'GM4J01': 0x00309B6C,
    'GM4E01dbg': 0x0032B158,
}
"""
Memory address used to determine whether the button combination can be accepted. The intent is to
force the player to release the D-pad before the page can be changed, avoiding potentially dangerous
spam.

This is the address to the first "This is padding" string (starting at "padding") that can be found
in memory, to ensure that it can be overridden safely. (In the past, Gecko registers were used, but,
although things worked in Dolphin, the game would crash when running in real hardware.)
"""

SPAM_FLAG_VALUE = 0xC00010FF
"""
An arbitrary value ("cool off", in hexspeak) that is used for the comparison of the spam flag.
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
        'BabyLuigi': (0x003CDDEC, 0x003CDDF0, 0x003CDDF4, 0x003CDDF8, 0x00141E14),
        'Peach': (0x003CDE0C, 0x003CDE10, 0x003CDE14, 0x003CDE18, 0x00141EE0),
        'Daisy': (0x003CDE34, 0x003CDE38, 0x003CDE3C, 0x003CDE40, 0x0014200c),
        'Luigi': (0x003CDE5C, 0x003CDE60, 0x003CDE64, 0x003CDE68, 0x001420D8),
        'Mario': (0x003CDE74, 0x003CDE78, 0x003CDE7C, 0x003CDE80, 0x001421A4),
        'Yoshi': (0x003CDE90, 0x003CDE94, 0x003CDE98, 0x003CDE9C, 0x00142270),
        'Nokonoko': (0x003CDEB0, 0x003CDEB4, 0x003CDEB8, 0x003CDEBC, 0x0014233c),
        'Patapata': (0x003CDEC8, 0x003CDECC, 0x003CDED0, 0x003CDED4, 0x00142408),
        'Waluigi': (0x003CDEE8, 0x003CDEEC, 0x003CDEF0, 0x003CDEF4, 0x001424D4),
        'Wario': (0x003CDF0C, 0x003CDF10, 0x003CDF14, 0x003CDF18, 0x001425A0),
        'Diddy': (0x003CDF28, 0x003CDF2C, 0x003CDF30, 0x003CDF34, 0x0014266C),
        'Donkey': (0x003CDF40, 0x003CDF44, 0x003CDF48, 0x003CDF4C, 0x00142738),
        'Koopa': (0x003CDF5C, 0x003CDF60, 0x003CDF64, 0x003CDF68, 0x00142804),
        'Rainbow': (0x003CDF70, 0x003CDF74, 0x003CDF78, 0x003CDF7C, 0x001428D0),
        'Desert': (0x003CDF84, 0x003CDF88, 0x003CDF8C, 0x003CDF90, 0x0014299C),
        'Snow': (0x003CDFA4, 0x003CDFA8, 0x003CDFAC, 0x003CDFB0, 0x00142A68),
    },
    'GM4P01': {
        'BabyLuigi': (0x003D7C2C, 0x003D7C30, 0x003D7C34, 0x003D7C38, 0x00141E44),
        'Peach': (0x003D7C4C, 0x003D7C50, 0x003D7C54, 0x003D7C58, 0x00141F10),
        'Daisy': (0x003D7C74, 0x003D7C78, 0x003D7C7C, 0x003D7C80, 0x0014203C),
        'Luigi': (0x003D7C9C, 0x003D7CA0, 0x003D7CA4, 0x003D7CA8, 0x00142108),
        'Mario': (0x003D7CB4, 0x003D7CB8, 0x003D7CBC, 0x003D7CC0, 0x001421D4),
        'Yoshi': (0x003D7CD0, 0x003D7CD4, 0x003D7CD8, 0x003D7CDC, 0x001422A0),
        'Nokonoko': (0x003D7CF0, 0x003D7CF4, 0x003D7CF8, 0x003D7CFC, 0x0014236C),
        'Patapata': (0x003D7D08, 0x003D7D0C, 0x003D7D10, 0x003D7D14, 0x00142438),
        'Waluigi': (0x003D7D28, 0x003D7D2C, 0x003D7D30, 0x003D7D34, 0x00142504),
        'Wario': (0x003D7D4C, 0x003D7D50, 0x003D7D54, 0x003D7D58, 0x001425D0),
        'Diddy': (0x003D7D68, 0x003D7D6C, 0x003D7D70, 0x003D7D74, 0x0014269C),
        'Donkey': (0x003D7D80, 0x003D7D84, 0x003D7D88, 0x003D7D8C, 0x00142768),
        'Koopa': (0x003D7D9C, 0x003D7DA0, 0x003D7DA4, 0x003D7DA8, 0x00142834),
        'Rainbow': (0x003D7DB0, 0x003D7DB4, 0x003D7DB8, 0x003D7DBC, 0x00142900),
        'Desert': (0x003D7DC4, 0x003D7DC8, 0x003D7DCC, 0x003D7DD0, 0x001429CC),
        'Snow': (0x003D7DE4, 0x003D7DE8, 0x003D7DEC, 0x003D7DF0, 0x00142A98),
    },
    'GM4J01': {
        'BabyLuigi': (0x003E840C, 0x003E8410, 0x003E8414, 0x003E8418, 0x00141E14),
        'Peach': (0x003E842C, 0x003E8430, 0x003E8434, 0x003E8438, 0x00141EE0),
        'Daisy': (0x003E8454, 0x003E8458, 0x003E845C, 0x003E8460, 0x0014200C),
        'Luigi': (0x003E847C, 0x003E8480, 0x003E8484, 0x003E8488, 0x001420D8),
        'Mario': (0x003E8494, 0x003E8498, 0x003E849C, 0x003E84A0, 0x001421A4),
        'Yoshi': (0x003E84B0, 0x003E84B4, 0x003E84B8, 0x003E84BC, 0x00142270),
        'Nokonoko': (0x003E84D0, 0x003E84D4, 0x003E84D8, 0x003E84DC, 0x0014233C),
        'Patapata': (0x003E84E8, 0x003E84EC, 0x003E84F0, 0x003E84F4, 0x00142408),
        'Waluigi': (0x003E8508, 0x003E850C, 0x003E8510, 0x003E8514, 0x001424D4),
        'Wario': (0x003E852C, 0x003E8530, 0x003E8534, 0x003E8538, 0x001425A0),
        'Diddy': (0x003E8548, 0x003E854C, 0x003E8550, 0x003E8554, 0x0014266C),
        'Donkey': (0x003E8560, 0x003E8564, 0x003E8568, 0x003E856C, 0x00142738),
        'Koopa': (0x003E857C, 0x003E8580, 0x003E8584, 0x003E8588, 0x00142804),
        'Rainbow': (0x003E8590, 0x003E8594, 0x003E8598, 0x003E859C, 0x001428D0),
        'Desert': (0x003E85A4, 0x003E85A8, 0x003E85AC, 0x003E85B0, 0x0014299C),
        'Snow': (0x003E85C4, 0x003E85C8, 0x003E85CC, 0x003E85D0, 0x00142A68),
    },
    'GM4E01dbg': {
        'BabyLuigi': (0x00419100, 0x00419104, 0x00419108, 0x0041910C, 0x0015415c),
        'Peach': (0x00419120, 0x00419124, 0x00419128, 0x0041912C, 0x00154254),
        'Daisy': (0x00419148, 0x0041914C, 0x00419150, 0x00419154, 0x001543ac),
        'Luigi': (0x00419170, 0x00419174, 0x00419178, 0x0041917C, 0x001544a4),
        'Mario': (0x00419188, 0x0041918C, 0x00419190, 0x00419194, 0x0015459c),
        'Yoshi': (0x004191A4, 0x004191A8, 0x004191AC, 0x004191B0, 0x00154694),
        'Nokonoko': (0x004191C4, 0x004191C8, 0x004191CC, 0x004191D0, 0x0015478c),
        'Patapata': (0x004191DC, 0x004191E0, 0x004191E4, 0x004191E8, 0x00154884),
        'Waluigi': (0x004191FC, 0x00419200, 0x00419204, 0x00419208, 0x0015497c),
        'Wario': (0x00419220, 0x00419224, 0x00419228, 0x0041922C, 0x00154a74),
        'Diddy': (0x0041923C, 0x00419240, 0x00419244, 0x00419248, 0x00154b6c),
        'Donkey': (0x00419254, 0x00419258, 0x0041925C, 0x00419260, 0x00154c64),
        'Koopa': (0x00419270, 0x00419274, 0x00419278, 0x0041927C, 0x00154d5c),
        'Rainbow': (0x00419284, 0x00419288, 0x0041928C, 0x00419290, 0x00154e54),
        'Desert': (0x00419298, 0x0041929C, 0x004192A0, 0x004192A4, 0x00154f4c),
        'Snow': (0x004192B8, 0x004192BC, 0x004192C0, 0x004192C4, 0x00155044),
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
            dol_file.seek(0x80000000 + addresses[0])
            v0 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(0x80000000 + addresses[1])
            v1 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(0x80000000 + addresses[2])
            v2 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(0x80000000 + addresses[3])
            v3 = struct.unpack('>f', dol_file.read(4))[0]
            dol_file.seek(0x80000000 + addresses[4] + 3)
            v4 = struct.unpack('>B', dol_file.read(1))[0]

            for v in (v0, v1, v2, v3):
                if -10000000.0 <= v <= 10000000.0:
                    continue
                raise RuntimeError('Unable to extract minimap values values from DOL file. '
                                   f'Corner value ({v4}) is unexpectedly large.')

            if v4 not in (0, 1, 2, 3):
                raise RuntimeError('Unable to extract minimap orientation values from DOL file. '
                                   f'Orientation enum value ({v4}) not in [0, 3].')

            minimap_values[course] = (v0, v1, v2, v3, v4)

    return minimap_values


COURSE_TO_STREAM_FILE_INDEX_ADDRESSES = {
    'GM4E01': 0x0052EB04,
    'GM4P01': 0x00538944,
    'GM4J01': 0x0053FC5C,
    'GM4E01dbg': 0x0057AA64,
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
        '/Course/%s%s.arc': 0x00336D3C,
        '/Course/Luigi2%s.arc': 0x00336D24,
        '/CourseName/%s/%s_name.bti': 0x00336CF4,
        '/StaffGhosts/%s.ght': 0x00336D10,
        'COP_LUIGI_CIRCUIT.bti': 0x00331FEC,
        'COP_PEACH_BEACH.bti': 0x0033201C,
        'COP_BABY_PARK.bti': 0x00332048,
        'COP_KARA_KARA_DESERT.bti': 0x00332078,
        'COP_KINOKO_BRIDGE.bti': 0x003320B0,
        'COP_MARIO_CIRCUIT.bti': 0x003320E4,
        'COP_DAISY_SHIP.bti': 0x00332114,
        'COP_WALUIGI_STADIUM.bti': 0x00332144,
        'COP_SHERBET_LAND.bti': 0x00332174,
        'COP_KONOKO_CITY.bti': 0x003321A4,
        'COP_YOSHI_CIRCUIT.bti': 0x003321D4,
        'COP_DK_MOUNTAIN.bti': 0x00332204,
        'COP_WARIO_COLOSSEUM.bti': 0x00332234,
        'COP_DINO_DINO_JUNGLE.bti': 0x00332268,
        'COP_BOWSER_CASTLE.bti': 0x003322A0,
        'COP_RAINBOW_ROAD.bti': 0x003322D0,
        'CoName_LUIGI_CIRCUIT.bti': 0x00331FD0,
        'CoName_PEACH_BEACH.bti': 0x00332004,
        'CoName_BABY_PARK.bti': 0x00332030,
        'CoName_KARA_KARA_DESERT.bti': 0x0033205C,
        'CoName_KINOKO_BRIDGE.bti': 0x00332094,
        'CoName_MARIO_CIRCUIT.bti': 0x003320C8,
        'CoName_DAISY_SHIP.bti': 0x003320FC,
        'CoName_WALUIGI_STADIUM.bti': 0x00332128,
        'CoName_SHERBET_LAND.bti': 0x0033215C,
        'CoName_KINOKO_CITY.bti': 0x0033218C,
        'CoName_YOSHI_CIRCUIT.bti': 0x003321B8,
        'CoName_DK_MOUNTAIN.bti': 0x003321EC,
        'CoName_WARIO_COLOSSEUM.bti': 0x00332218,
        'CoName_DINO_DINO_JUNGLE.bti': 0x0033224C,
        'CoName_BOWSER_CASTLE.bti': 0x00332284,
        'CoName_RAINBOW_ROAD.bti': 0x003322B8,
        'CupName_MUSHROOM_CUP.bti': 0x00331EDC,
        'CupName_FLOWER_CUP.bti': 0x00331EF8,
        'CupName_STAR_CUP.bti': 0x00331F10,
        'CupName_SPECIAL_CUP.bti': 0x00331F28,
        'CupName_REVERSE2_CUP.bti': 0x00331F40,
        'LUIGI_CIRCUIT': 0x00337698,
        'PEACH_BEACH': 0x003376A8,
        'BABY_PARK': 0x003376B4,
        'KARA_KARA_DESERT': 0x003376C0,
        'KINOKO_BRIDGE': 0x003376D4,
        'MARIO_CIRCUIT': 0x003376E4,
        'DAISY_SHIP': 0x003376F4,
        'WALUIGI_STADIUM': 0x00337700,
        'SHERBET_LAND': 0x00337710,
        'KINOKO_CITY': 0x00337720,
        'YOSHI_CIRCUIT': 0x0033772C,
        'DK_MOUNTAIN': 0x0033773C,
        'WARIO_COLOSSEUM': 0x00337748,
        'DINO_DINO_JUNGLE': 0x00337758,
        'BOWSER_CASTLE': 0x0033776C,
        'RAINBOW_ROAD': 0x0033777C,
        'CupName_MUSHROOM_CUP': 0x00337624,
        'CupName_FLOWER_CUP': 0x0033763C,
        'CupName_STAR_CUP': 0x00337650,
        'CupName_SPECIAL_CUP': 0x00337664,
    },
    'GM4P01': {
        '/Course/%s%s.arc': 0x00340B7C,
        '/Course/Luigi2%s.arc': 0x00340B64,
        '/CourseName/%s/%s_name.bti': 0x00340B34,
        '/StaffGhosts/%s.ght': 0x00340B50,
        'COP_LUIGI_CIRCUIT.bti': 0x0033BDBC,
        'COP_PEACH_BEACH.bti': 0x0033BDEC,
        'COP_BABY_PARK.bti': 0x0033BE18,
        'COP_KARA_KARA_DESERT.bti': 0x0033BE48,
        'COP_KINOKO_BRIDGE.bti': 0x0033BE80,
        'COP_MARIO_CIRCUIT.bti': 0x0033BEB4,
        'COP_DAISY_SHIP.bti': 0x0033BEE4,
        'COP_WALUIGI_STADIUM.bti': 0x0033BF14,
        'COP_SHERBET_LAND.bti': 0x0033BF44,
        'COP_KONOKO_CITY.bti': 0x0033BF74,
        'COP_YOSHI_CIRCUIT.bti': 0x0033BFA4,
        'COP_DK_MOUNTAIN.bti': 0x0033BFD4,
        'COP_WARIO_COLOSSEUM.bti': 0x0033C004,
        'COP_DINO_DINO_JUNGLE.bti': 0x0033C038,
        'COP_BOWSER_CASTLE.bti': 0x0033C070,
        'COP_RAINBOW_ROAD.bti': 0x0033C0A0,
        'CoName_LUIGI_CIRCUIT.bti': 0x0033BDA0,
        'CoName_PEACH_BEACH.bti': 0x0033BDD4,
        'CoName_BABY_PARK.bti': 0x0033BE00,
        'CoName_KARA_KARA_DESERT.bti': 0x0033BE2C,
        'CoName_KINOKO_BRIDGE.bti': 0x0033BE64,
        'CoName_MARIO_CIRCUIT.bti': 0x0033BE98,
        'CoName_DAISY_SHIP.bti': 0x0033BECC,
        'CoName_WALUIGI_STADIUM.bti': 0x0033BEF8,
        'CoName_SHERBET_LAND.bti': 0x0033BF2C,
        'CoName_KINOKO_CITY.bti': 0x0033BF5C,
        'CoName_YOSHI_CIRCUIT.bti': 0x0033BF88,
        'CoName_DK_MOUNTAIN.bti': 0x0033BFBC,
        'CoName_WARIO_COLOSSEUM.bti': 0x0033BFE8,
        'CoName_DINO_DINO_JUNGLE.bti': 0x0033C01C,
        'CoName_BOWSER_CASTLE.bti': 0x0033C054,
        'CoName_RAINBOW_ROAD.bti': 0x0033C088,
        'CupName_MUSHROOM_CUP.bti': 0x0033BCAC,
        'CupName_FLOWER_CUP.bti': 0x0033BCC8,
        'CupName_STAR_CUP.bti': 0x0033BCE0,
        'CupName_SPECIAL_CUP.bti': 0x0033BCF8,
        'CupName_REVERSE2_CUP.bti': 0x0033BD10,
        'LUIGI_CIRCUIT': 0x003414D8,
        'PEACH_BEACH': 0x003414E8,
        'BABY_PARK': 0x003414F4,
        'KARA_KARA_DESERT': 0x00341500,
        'KINOKO_BRIDGE': 0x00341514,
        'MARIO_CIRCUIT': 0x00341524,
        'DAISY_SHIP': 0x00341534,
        'WALUIGI_STADIUM': 0x00341540,
        'SHERBET_LAND': 0x00341550,
        'KINOKO_CITY': 0x00341560,
        'YOSHI_CIRCUIT': 0x0034156C,
        'DK_MOUNTAIN': 0x0034157C,
        'WARIO_COLOSSEUM': 0x00341588,
        'DINO_DINO_JUNGLE': 0x00341598,
        'BOWSER_CASTLE': 0x003415AC,
        'RAINBOW_ROAD': 0x003415BC,
        'CupName_MUSHROOM_CUP': 0x00341464,
        'CupName_FLOWER_CUP': 0x0034147C,
        'CupName_STAR_CUP': 0x00341490,
        'CupName_SPECIAL_CUP': 0x003414A4,
    },
    'GM4J01': {
        '/Course/%s%s.arc': 0x0035135C,
        '/Course/Luigi2%s.arc': 0x00351344,
        '/CourseName/%s/%s_name.bti': 0x00351314,
        '/StaffGhosts/%s.ght': 0x00351330,
        'COP_LUIGI_CIRCUIT.bti': 0x0034C60C,
        'COP_PEACH_BEACH.bti': 0x0034C63C,
        'COP_BABY_PARK.bti': 0x0034C668,
        'COP_KARA_KARA_DESERT.bti': 0x0034C698,
        'COP_KINOKO_BRIDGE.bti': 0x0034C6D0,
        'COP_MARIO_CIRCUIT.bti': 0x0034C704,
        'COP_DAISY_SHIP.bti': 0x0034C734,
        'COP_WALUIGI_STADIUM.bti': 0x0034C764,
        'COP_SHERBET_LAND.bti': 0x0034C794,
        'COP_KONOKO_CITY.bti': 0x0034C7C4,
        'COP_YOSHI_CIRCUIT.bti': 0x0034C7F4,
        'COP_DK_MOUNTAIN.bti': 0x0034C824,
        'COP_WARIO_COLOSSEUM.bti': 0x0034C854,
        'COP_DINO_DINO_JUNGLE.bti': 0x0034C888,
        'COP_BOWSER_CASTLE.bti': 0x0034C8C0,
        'COP_RAINBOW_ROAD.bti': 0x0034C8F0,
        'CoName_LUIGI_CIRCUIT.bti': 0x0034C5F0,
        'CoName_PEACH_BEACH.bti': 0x0034C624,
        'CoName_BABY_PARK.bti': 0x0034C650,
        'CoName_KARA_KARA_DESERT.bti': 0x0034C67C,
        'CoName_KINOKO_BRIDGE.bti': 0x0034C6B4,
        'CoName_MARIO_CIRCUIT.bti': 0x0034C6E8,
        'CoName_DAISY_SHIP.bti': 0x0034C71C,
        'CoName_WALUIGI_STADIUM.bti': 0x0034C748,
        'CoName_SHERBET_LAND.bti': 0x0034C77C,
        'CoName_KINOKO_CITY.bti': 0x0034C7AC,
        'CoName_YOSHI_CIRCUIT.bti': 0x0034C7D8,
        'CoName_DK_MOUNTAIN.bti': 0x0034C80C,
        'CoName_WARIO_COLOSSEUM.bti': 0x0034C838,
        'CoName_DINO_DINO_JUNGLE.bti': 0x0034C86C,
        'CoName_BOWSER_CASTLE.bti': 0x0034C8A4,
        'CoName_RAINBOW_ROAD.bti': 0x0034C8D8,
        'CupName_MUSHROOM_CUP.bti': 0x0034C4FC,
        'CupName_FLOWER_CUP.bti': 0x0034C518,
        'CupName_STAR_CUP.bti': 0x0034C530,
        'CupName_SPECIAL_CUP.bti': 0x0034C548,
        'CupName_REVERSE2_CUP.bti': 0x0034C560,
        'LUIGI_CIRCUIT': 0x00351CB8,
        'PEACH_BEACH': 0x00351CC8,
        'BABY_PARK': 0x00351CD4,
        'KARA_KARA_DESERT': 0x00351CE0,
        'KINOKO_BRIDGE': 0x00351CF4,
        'MARIO_CIRCUIT': 0x00351D04,
        'DAISY_SHIP': 0x00351D14,
        'WALUIGI_STADIUM': 0x00351D20,
        'SHERBET_LAND': 0x00351D30,
        'KINOKO_CITY': 0x00351D40,
        'YOSHI_CIRCUIT': 0x00351D4C,
        'DK_MOUNTAIN': 0x00351D5C,
        'WARIO_COLOSSEUM': 0x00351D68,
        'DINO_DINO_JUNGLE': 0x00351D78,
        'BOWSER_CASTLE': 0x00351D8C,
        'RAINBOW_ROAD': 0x00351D9C,
        'CupName_MUSHROOM_CUP': 0x00351C44,
        'CupName_FLOWER_CUP': 0x00351C5C,
        'CupName_STAR_CUP': 0x00351C70,
        'CupName_SPECIAL_CUP': 0x00351C84,
    },
    'GM4E01dbg': {
        '/Course/%s%s.arc': 0x0037D4E0,
        '/Course/Luigi2%s.arc': 0x0037D4C8,
        '/CourseName/%s/%s_name.bti': 0x0037D498,
        '/StaffGhosts/%s.ght': 0x0037D4B4,
        'COP_LUIGI_CIRCUIT.bti': 0x0037548C,
        'COP_PEACH_BEACH.bti': 0x003754BC,
        'COP_BABY_PARK.bti': 0x003754E8,
        'COP_KARA_KARA_DESERT.bti': 0x00375518,
        'COP_KINOKO_BRIDGE.bti': 0x00375550,
        'COP_MARIO_CIRCUIT.bti': 0x00375584,
        'COP_DAISY_SHIP.bti': 0x003755B4,
        'COP_WALUIGI_STADIUM.bti': 0x003755E4,
        'COP_SHERBET_LAND.bti': 0x00375614,
        'COP_KONOKO_CITY.bti': 0x00375644,
        'COP_YOSHI_CIRCUIT.bti': 0x00375674,
        'COP_DK_MOUNTAIN.bti': 0x003756A4,
        'COP_WARIO_COLOSSEUM.bti': 0x003756D4,
        'COP_DINO_DINO_JUNGLE.bti': 0x00375708,
        'COP_BOWSER_CASTLE.bti': 0x00375740,
        'COP_RAINBOW_ROAD.bti': 0x00375770,
        'CoName_LUIGI_CIRCUIT.bti': 0x00375470,
        'CoName_PEACH_BEACH.bti': 0x003754A4,
        'CoName_BABY_PARK.bti': 0x003754D0,
        'CoName_KARA_KARA_DESERT.bti': 0x003754FC,
        'CoName_KINOKO_BRIDGE.bti': 0x00375534,
        'CoName_MARIO_CIRCUIT.bti': 0x00375568,
        'CoName_DAISY_SHIP.bti': 0x0037559C,
        'CoName_WALUIGI_STADIUM.bti': 0x003755C8,
        'CoName_SHERBET_LAND.bti': 0x003755FC,
        'CoName_KINOKO_CITY.bti': 0x0037562C,
        'CoName_YOSHI_CIRCUIT.bti': 0x00375658,
        'CoName_DK_MOUNTAIN.bti': 0x0037568C,
        'CoName_WARIO_COLOSSEUM.bti': 0x003756B8,
        'CoName_DINO_DINO_JUNGLE.bti': 0x003756EC,
        'CoName_BOWSER_CASTLE.bti': 0x00375724,
        'CoName_RAINBOW_ROAD.bti': 0x00375758,
        'CupName_MUSHROOM_CUP.bti': 0x0037537C,
        'CupName_FLOWER_CUP.bti': 0x00375398,
        'CupName_STAR_CUP.bti': 0x003753B0,
        'CupName_SPECIAL_CUP.bti': 0x003753C8,
        'CupName_REVERSE2_CUP.bti': 0x003753E0,
        'LUIGI_CIRCUIT': 0x0037E808,
        'PEACH_BEACH': 0x0037E818,
        'BABY_PARK': 0x0037E824,
        'KARA_KARA_DESERT': 0x0037E830,
        'KINOKO_BRIDGE': 0x0037E844,
        'MARIO_CIRCUIT': 0x0037E854,
        'DAISY_SHIP': 0x0037E864,
        'WALUIGI_STADIUM': 0x0037E870,
        'SHERBET_LAND': 0x0037E880,
        'KINOKO_CITY': 0x0037E890,
        'YOSHI_CIRCUIT': 0x0037E89C,
        'DK_MOUNTAIN': 0x0037E8AC,
        'WARIO_COLOSSEUM': 0x0037E8B8,
        'DINO_DINO_JUNGLE': 0x0037E8C8,
        'BOWSER_CASTLE': 0x0037E8DC,
        'RAINBOW_ROAD': 0x0037E8EC,
        'CupName_MUSHROOM_CUP': 0x0037E794,
        'CupName_FLOWER_CUP': 0x0037E7AC,
        'CupName_STAR_CUP': 0x0037E7C0,
        'CupName_SPECIAL_CUP': 0x0037E7D4,
    }
}

for _game_id, addresses in STRING_ADDRESSES.items():
    for string in addresses:
        assert string in DIR_STRINGS + FILE_STRINGS

for string in DIR_STRINGS + FILE_STRINGS:
    for _game_id, addresses in STRING_ADDRESSES.items():
        assert string in addresses

START_SOUND_ASSEMBLY = textwrap.dedent("""\
    .loc_0x0:
        mr r11, r0 #Copy r0's value to r11
        mflr r12 #Copy LR's value to r12
        stwu sp,-0x80 (sp) #Push stack, make space for 29 registers
        stmw r3, 0x8 (sp)

        lis       r3, 0x8050        # Set values in r3, r4, r5, and r6 as seen in
        ori       r3, r3, 0x0a90    # legitimate calls to the function.
        lis       r4, 0x803e
        ori       r4, r4, 0x2210
        lis       r5, 0x803b
        ori       r5, r5, 0x0758
        li        r6, 0x0
        lis       r0, 0x2           # 0x2000c (Sound ID)
        ori       r0, r0, 0xc
        stw       r0, 0x0(r4)       # Sound ID is stored in the address that is
                                    # currently sitting in r4.

        lis       r12, 0x8008       # 0x8008b3d0 JAISeMgr::startSound()
        ori       r12, r12, 0xb3d0

        mtlr r12 #Copy r12 to the Link Register
        blrl #Call the function via the LR and have it return back to us

        lmw r3, 0x8 (sp)
        addi sp, sp, 0x80 #Pop stack
        mtlr r12 #Restore LR's value
        mr r0, r11 #Restore r0's value
    """)
"""
This is the assembly code that plays a sound ID by invoking `JAISeMgr::startSound()`.

While that symbol is placed in the same memory address for all three regions (`0x8008b3d0`), the
addresses of the arguments it takes differ between regions.

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
JAISeMgr::startSound() 0x80089974
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

The assembly code merely sets the value of the relevant registers, and invokes the function.

Instructions for pushing/popping registry stack, and invoking the function, have been sourced from
https://mariokartwii.com/showthread.php?tid=1052.

Other nice sources:
- https://www.cs.uaf.edu/2011/fall/cs301/lecture/11_21_PowerPC.html
- https://mariapilot.noblogs.org/files/2021/01/CodeWarrior-C-C-and-Assembly-Language-Reference.pdf
  (but responds with 404 now)

Note that the address of the function in the debug build does change.
"""

START_SOUND_ASSEMBLED = {
    'GM4E01':
    textwrap.dedent("""\
        7C0B0378 7D8802A6
        9421FF80 BC610008
        3C608050 60630A90
        3C80803E 60842210
        3CA0803B 60A50758
        38C00000 3C000002
        6000000C 90040000
        3D808008 618CB3D0
        7D8803A6 4E800021
        B8610008 38210080
        7D8803A6 7D605B78
    """),
    'GM4P01':
    textwrap.dedent("""\
        7C0B0378 7D8802A6
        9421FF80 BC610008
        3C608050 6063A8D0
        3C80803E 6084C050
        3CA0803B 60A5A578
        38C00000 3C000002
        6000000C 90040000
        3D808008 618CB3D0
        7D8803A6 4E800021
        B8610008 38210080
        7D8803A6 7D605B78
    """),
    'GM4J01':
    textwrap.dedent("""\
        7C0B0378 7D8802A6
        9421FF80 BC610008
        3C608051 6063B0B0
        3C80803F 6084C830
        3CA0803C 60A5AD78
        38C00000 3C000002
        6000000C 90040000
        3D808008 618CB3D0
        7D8803A6 4E800021
        B8610008 38210080
        7D8803A6 7D605B78
    """),
    'GM4E01dbg':
    textwrap.dedent("""\
        7C0B0378 7D8802A6
        9421FF80 BC610008
        3C608054 6063C9F0
        3C808042 6084E170
        3CA0803F 60A5B2A4
        38C00000 3C000002
        6000000C 90040000
        3D808008 618C9974
        7D8803A6 4E800021
        B8610008 38210080
        7D8803A6 7D605B78
    """),
}
"""
Code in `START_SOUND_ASSEMBLY` that has been assembled with PyiiASMH 3.

Same code for all regions, except for the three memory addresses store in r3, r4, and r5.
"""

CURRENT_APP_ID_ADDRESSES = {
    'GM4E01': 0x003CBDA0,
    'GM4P01': 0x003D5BE0,
    'GM4J01': 0x003E63C0,
    'GM4E01dbg': 0x00416998,
}
"""
The address to the integer that holds the ID of the current "app". Some of these IDs are:
    - Nintendo logo: 0x04
    - In race:       0x08
    - Main menus:    0x0A
    - Demo video:    0x0C
    - LAN menus:     0x0B

The current values are necessary to determine when the LAN menus need to be refreshed, as otherwise
it is not safe to invoke the `setNextApp()` function to force a refresh.

These values are seen in `setNextApp()`, in the first part of the early-out check, which in the
NTSC region it is the value in r13 with the -0x5680 offset.
"""

CUE_NETGATE_APP_ASSEMBLY = textwrap.dedent("""\
    .loc_0x0:
        stwu sp,-0x80 (sp) #Push stack, make space for 29 registers
        stmw r3, 0x8 (sp)

        lis       r3, 0x803d       # Address to...
        ori       r3, r3, 0x1420   # ...the static memory (r13).

        li        r4, 0xB          # LAN menus app ID.
        stw       r4, -0x567c(r3)  # Set next app ID. First statement in the setNextApp() function.

        li        r4, 0x1
        stb       r4, -0x5666(r3)  # The last two statements...
        stb       r4, -0x5668(r3)  # ...in the setNextApp() function.

        li        r4, 0x0          # Set the LAN mode's SELECT MODE screen, or else...
        stb       r4, -0x55f4(r3)  # ...it may land on the main screen.

        lwz       r4, -0x566c(r3)  # To mark the current app...
        ori       r4, r4, 0x1      # ...for deletion, the last bit is...
        stw       r4, -0x566c(r3)  # ...set to 1.

        lmw r3, 0x8 (sp)
        addi sp, sp, 0x80 #Pop stack
    """)
"""
In the LAN menus, the images won't be refresh unless `setNextApp()` is called again. To replicate
that behavior, this assembly code is used, which matches in principle the body of the function
(except for its early-out check, that is omitted).

These are the last three statements in the `setNextApp()` function, which are replicated in the this
assembly code:

  *(int *)(in_r13 + -0x567c) = param_1;
  *(undefined *)(in_r13 + -0x5666) = 1;
  *(undefined *)(in_r13 + -0x5668) = 1;

Note that the first statement appears to be setting what appears to be the ID of "the next app".
That is, `param_1` (r3) is the next app ID, and is always 0x0B (LAN menus) for this use case. The
second statement seems to indicate that the app ID has changed (it is read in `AppMgr::calc()`). The
third/last statement is used to indicate that the next draw call needs to be skipped (see
`AppMgr::draw()`).

r13 is a pointer to some memory where many variables are stored, and that the assembly codes will be
modified, based on some offsets, as seen in the functions that the assembly code is replicating.

The assembly also includes another statement seen in `NetGateApp::call()`, that seems to be setting
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

CUE_NETGATE_APP_ASSEMBLED = {
    'GM4E01':
    textwrap.dedent("""\
        9421FF80 BC610008
        3C60803D 60631420
        3880000B 9083A984
        38800001 9883A99A
        9883A998 38800000
        9883AA0C 8083A994
        60840001 9083A994
        B8610008 38210080
    """),
    'GM4P01':
    textwrap.dedent("""\
        9421FF80 BC610008
        3C60803D 6063B240
        3880000B 9083A9A4
        38800001 9883A9BA
        9883A9B8 38800000
        9883AA2C 8083A9B4
        60840001 9083A9B4
        B8610008 38210080
    """),
    'GM4J01':
    textwrap.dedent("""\
        9421FF80 BC610008
        3C60803E 6063BA40
        3880000B 9083A984
        38800001 9883A99A
        9883A998 38800000
        9883AA0C 8083A994
        60840001 9083A994
        B8610008 38210080
    """),
    'GM4E01dbg':
    textwrap.dedent("""\
        9421FF80 BC610008
        3C608041 6063BF80
        3880000B 9083AA1C
        38800001 9883AA32
        9883AA30 38800000
        9883AAA4 8083AA2C
        60840001 9083AA2C
        B8610008 38210080
    """),
}
"""
Code in `CUE_NETGATE_APP_ASSEMBLY` that has been assembled with PyiiASMH 3.
"""


def encode_address(code_type: str, operand: int = None) -> int:
    """
    http://wiigeckocodes.github.io/codetypedocumentation.html
    """
    if code_type == 'write8':
        return operand
    if code_type == 'write32':
        return 0x04000000 | operand
    if code_type == 'if32':
        return 0x20000000 | operand
    if code_type == 'ifnot32':
        return 0x22000000 | operand
    if code_type == 'if16':
        return 0x28000000 | operand
    if code_type == 'terminator':
        return 0xE0000000
    if code_type == 'goto':
        return 0x66000000 | operand
    if code_type == 'end':
        return 0xF0000000

    raise RuntimeError(f'Unknown code type: "{code_type}".')


def encode_asm(text: str) -> 'list[str]':
    lines = text.splitlines()
    lines = [f'C0000000 {len(lines) + 1:08X}'] + lines
    lines.append('4E800020 00000000')
    return lines


def get_line(encoded_address: int, value: int) -> str:
    return f'{encoded_address:08X} {value:08X}'


def float_to_hex(value: float) -> int:
    return struct.unpack('>L', struct.pack('>f', value))[0]


def write_code(game_id: str, dol_path: str, minimap_data: dict, audio_track_data: tuple,
               filepath: str):

    encoded_buttons_state_address = encode_address('if16', BUTTONS_STATE_ADDRESSES[game_id])

    activator_lines = (
        get_line(encoded_buttons_state_address, BUTTON_Z | BUTTON_UP),
        get_line(encoded_buttons_state_address, BUTTON_Z | BUTTON_DOWN),
        get_line(encoded_buttons_state_address, BUTTON_Z | BUTTON_LEFT),
    )
    deactivator_line = get_line(encoded_buttons_state_address, BUTTON_Z | BUTTON_RIGHT)

    full_terminator_line = get_line(encode_address('terminator', None), 0x80008000)

    lines_for_activator = ([], [], [])
    lines_for_deactivator = []

    for page_index in range(3):
        suffix_value = str(page_index).encode('ascii')[0]

        # Directory strings.
        for dir_string in DIR_STRINGS:
            dir_string_address = STRING_ADDRESSES[game_id][dir_string]

            # Find the first slash (/) character (after position 1, as some strings start with a
            # forward slash, but that's not the one we are looking for).
            offset = dir_string.find('/', 1) - 1
            dir_string_address += offset
            encoded_dir_string_address = encode_address('write8', dir_string_address)
            dir_string_address_line = get_line(encoded_dir_string_address, suffix_value)

            lines_for_activator[page_index].append(dir_string_address_line)

            if page_index == 0:
                last_char = dir_string[offset]
                last_char_value = last_char.encode('ascii')[0]
                dir_string_address_line = get_line(encoded_dir_string_address, last_char_value)

                lines_for_deactivator.append(dir_string_address_line)

        # File strings.
        for file_string in FILE_STRINGS:
            file_string_address = STRING_ADDRESSES[game_id][file_string]

            # Find the last character before the extension.
            offset = len(os.path.splitext(file_string)[0]) - 1
            file_string_address += offset
            encoded_file_string_address = encode_address('write8', file_string_address)
            file_string_address_line = get_line(encoded_file_string_address, suffix_value)

            lines_for_activator[page_index].append(file_string_address_line)

            if page_index == 0:
                last_char = file_string[offset]
                last_char_value = last_char.encode('ascii')[0]
                file_string_address_line = get_line(encoded_file_string_address, last_char_value)

                lines_for_deactivator.append(file_string_address_line)

    # Minimap data.
    for page_index in range(3):
        for track_index in range(16):
            addresses = COURSE_TO_MINIMAP_ADDRESSES[game_id][COURSES[track_index]]
            values = minimap_data[(page_index, track_index)]

            lines_for_activator[page_index].extend((
                get_line(encode_address('write32', addresses[0]), float_to_hex(values[0])),
                get_line(encode_address('write32', addresses[1]), float_to_hex(values[1])),
                get_line(encode_address('write32', addresses[2]), float_to_hex(values[2])),
                get_line(encode_address('write32', addresses[3]), float_to_hex(values[3])),
                get_line(encode_address('write8', addresses[4] + 3), values[4]),
            ))
    initial_minimap_values = read_minimap_values(game_id, dol_path)
    for track_index in range(16):
        addresses = COURSE_TO_MINIMAP_ADDRESSES[game_id][COURSES[track_index]]
        values = initial_minimap_values[COURSES[track_index]]

        lines_for_deactivator.extend((
            get_line(encode_address('write32', addresses[0]), float_to_hex(values[0])),
            get_line(encode_address('write32', addresses[1]), float_to_hex(values[1])),
            get_line(encode_address('write32', addresses[2]), float_to_hex(values[2])),
            get_line(encode_address('write32', addresses[3]), float_to_hex(values[3])),
            get_line(encode_address('write8', addresses[4] + 3), values[4]),
        ))

    # Audio track data.
    for page_index in range(3):
        for i, value in enumerate(audio_track_data[page_index]):
            address = COURSE_TO_STREAM_FILE_INDEX_ADDRESSES[game_id] + i * 4
            lines_for_activator[page_index].append(
                get_line(encode_address('write32', address), value))
    for i, value in enumerate(audio_track_data[3]):
        address = COURSE_TO_STREAM_FILE_INDEX_ADDRESSES[game_id] + i * 4
        lines_for_deactivator.append(get_line(encode_address('write32', address), value))

    # Redraw course selection screen code.
    redraw_courseselect_address = REDRAW_COURSESELECT_SCREEN_ADDRESSES[game_id]
    encoded_redraw_courseselect_address = encode_address('write32', redraw_courseselect_address)
    redraw_courseselect_address_activator_line = get_line(encoded_redraw_courseselect_address,
                                                          0x41200000)  # 10.0f

    # The screen needs to be redrawn when activated or deactivated.
    for page_index in range(3):
        lines_for_activator[page_index].append(redraw_courseselect_address_activator_line)
    lines_for_deactivator.append(redraw_courseselect_address_activator_line)

    # Memory address to set/reset to prevent spam, and to later allow page selection again.
    encoded_spam_flag_address = encode_address('write32', SPAM_FLAG_ADDRESSES[game_id])
    spam_flag_address_activator_line = get_line(encoded_spam_flag_address, SPAM_FLAG_VALUE)

    # The flag needs to be set when activated or deactivated.
    for page_index in range(3):
        lines_for_activator[page_index].append(spam_flag_address_activator_line)
    lines_for_deactivator.append(spam_flag_address_activator_line)

    # Values to be reinstated when only the Z button is held.
    restoration_activator_line = get_line(encoded_buttons_state_address, BUTTON_Z)
    lines_for_restoration_activator = [
        get_line(encoded_redraw_courseselect_address, 0x41500000),  # 13.0f
        get_line(encoded_spam_flag_address, 0x00000000)  # Anything that is not SPAM_FLAG_VALUE.
    ]

    # Lines for playing the sound effect.
    for line in encode_asm(START_SOUND_ASSEMBLED[game_id]):
        for page_index in range(3):
            lines_for_activator[page_index].append(line)
        lines_for_deactivator.append(line)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='ascii') as f:
        f.write('$Page Selector [mkdd-extender]')
        f.write('\n')

        # To reinstate values when only Z is held.
        f.write(restoration_activator_line)
        f.write('\n')
        for line in lines_for_restoration_activator:
            f.write(line)
            f.write('\n')
        f.write('\n')
        f.write(full_terminator_line)
        f.write('\n')
        f.write('\n')

        # To check if the spam flag has been reset before accepting another change.
        f.write(get_line(encode_address('ifnot32', SPAM_FLAG_ADDRESSES[game_id]), SPAM_FLAG_VALUE))
        f.write('\n')
        f.write(get_line(encode_address('goto', 1), 0))  # Skips line below.
        f.write('\n')
        f.write(get_line(encode_address('end'), 0))
        f.write('\n')
        f.write(full_terminator_line)
        f.write('\n')
        f.write('\n')

        # To select a page.
        for page_index in range(3):
            f.write(activator_lines[page_index])
            f.write('\n')
            for line in lines_for_activator[page_index]:
                f.write(line)
                f.write('\n')
            f.write(full_terminator_line)
            f.write('\n')
            f.write('\n')

        # To switch back to the stock courses.
        f.write(deactivator_line)
        f.write('\n')
        for line in lines_for_deactivator:
            f.write(line)
            f.write('\n')
        f.write(full_terminator_line)
        f.write('\n')
        f.write('\n')

        # LAN mode from here.

        # If current app ID is not the NetGate, end.
        f.write(get_line(encode_address('if32', CURRENT_APP_ID_ADDRESSES[game_id]), 0x0000000B))
        f.write('\n')
        f.write(get_line(encode_address('goto', 1), 0))  # Skips line below.
        f.write('\n')
        f.write(get_line(encode_address('end'), 0))
        f.write('\n')
        f.write(full_terminator_line)
        f.write('\n')
        f.write('\n')

        for page_index in range(3):
            f.write(activator_lines[page_index])
            f.write('\n')
            for line in encode_asm(CUE_NETGATE_APP_ASSEMBLED[game_id]):
                f.write(line)
                f.write('\n')
            f.write(full_terminator_line)
            f.write('\n')
            f.write('\n')

        f.write(deactivator_line)
        f.write('\n')
        for line in encode_asm(CUE_NETGATE_APP_ASSEMBLED[game_id]):
            f.write(line)
            f.write('\n')
        f.write(full_terminator_line)
        f.write('\n')
