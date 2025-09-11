"""
Module for generating and injecting the game logic that makes possible the course page selection,
as well as other code patches.

The GC-C-Kit tool is used for building and extracting the symbols that are then injected in the
input DOL file.
"""
import argparse
import collections
import contextlib
import logging
import os
import platform
import shutil
import struct
import subprocess
import tempfile
import textwrap

import baa
from tools.gc_c_kit import devkit_tools
from tools.gc_c_kit import dolreader
from tools.gc_c_kit import doltools
from tools.lan_choose_character_kart import lan_choose_character_kart

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
data_dir = os.path.join(script_dir, 'data')
code_dir = os.path.join(data_dir, 'code')
tools_dir = os.path.join(script_dir, 'tools')

# Set up the GC-C-Kit module with the paths to the compiler.
if (not devkit_tools.GCCPATH and not devkit_tools.LDPATH and not devkit_tools.OBJDUMPPATH
        and not devkit_tools.OBJCOPYPATH and not devkit_tools.ASPATH):
    devkitppc_dir = os.path.join(tools_dir, 'devkitPPC', platform.system().lower(), 'bin')
    exe_extension = '.exe' if platform.system() == 'Windows' else ''
    devkit_tools.GCCPATH = os.path.join(devkitppc_dir, f'powerpc-eabi-gcc{exe_extension}')
    devkit_tools.LDPATH = os.path.join(devkitppc_dir, f'powerpc-eabi-ld{exe_extension}')
    devkit_tools.OBJDUMPPATH = os.path.join(devkitppc_dir, f'powerpc-eabi-objdump{exe_extension}')
    devkit_tools.OBJCOPYPATH = os.path.join(devkitppc_dir, f'powerpc-eabi-objcopy{exe_extension}')

    powerpc_eabi_dir = os.path.join(tools_dir, 'devkitPPC',
                                    platform.system().lower(), 'powerpc-eabi', 'bin')
    devkit_tools.ASPATH = os.path.join(powerpc_eabi_dir, f'as{exe_extension}')

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

ALT_BUTTONS_STATE_ADDRESSES = {
    'GM4E01': 0x8036B053,
    'GM4P01': 0x80374E93,
    'GM4J01': 0x80385673,
    'GM4E01dbg': 0x803B5353,
}
"""
These addresses point to a 1-byte structure that stores the state of all buttons in the game pad
(excluding the joystick). This is a reduced structure that is only used in LAN mode.

To find these addresses in all regions, a LAN session is started; then the Dolphin Memory Engine
is used to find the very first address that reacts to button presses (`A` is `1`, `B` is `2`, etc.).
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

GP_INITIAL_PAGE_ADDRESSES = {k: v + 1 for k, v in CURRENT_PAGE_ADDRESSES.items()}
"""
Memory address where the initial page in GP mode is stored. Defined as the next byte after the
current page. Used in the Extender Cup.
"""

LAN_MENU_TITLE_INDEX_INSTRUCTION_ADDRESSES = {
    'GM4E01': 0x801E457C,
    'GM4P01': 0x801E4554,
    'GM4J01': 0x801E45A4,
    'GM4E01dbg': 0x80216318,
}
"""
Address to a `li` instruction that precedes the call to `MenuTitleLine::drop()` and that stores the
index (`3`) of the menu title image that is loaded for the **SELECT MODE** screen in LAN mode.

The array that includes the pointers to the C strings is located at 0x80353158 in NTSC-U.

Note that the "SELECT MODE" menu title image is shared between multiplayer and LAN mode. In order to
provide the menu title image with the controls image in LAN mode without altering the other screen,
another image would have to be introduced or repurposed.

Instead, the index will be changed to the "SELECT COURSE" image (index `4`), which users have argue
is a better text for the screen anyway.
"""

GP_GLOBAL_COURSE_INDEX_ADDRESSES = {k: v + 1 for k, v in GP_INITIAL_PAGE_ADDRESSES.items()}
"""
Memory address where the global course index in the Extender Cup code patch is stored. Defined as
the next byte after the initial page.
"""

PLAYER_ITEM_ROLLS_ADDRESSES = {
    'GM4E01': 0x802ED64F,
    'GM4P01': 0x802F9D06,
    'GM4J01': 0x8030A786,
    'GM4E01dbg': 0x8032B1AF,
}
"""
Memory address for the **Type-specific Item Boxes** code patch, where the players' item rolls will
be temporarily stored. 8 bytes are used (one for each kart in the race).

This is the address to the second "This is padding" string in the game.
"""

SKIP_MOVIE_TRAILER_INSTRUCTIONS_ADDRESSES = {
    'GM4E01': (0x801B0D58, 0x801B10AC, 0x8012E1EC),
    'GM4P01': (0x801AFBE8, 0x801AFF3C, 0x8012E210),
    'GM4J01': (0x801B0D58, 0x801B10AC, 0x8012E1EC),
    'GM4E01dbg': (0x801D7C94, 0x801D8024, 0x8013D588, (0x801D8298, 0x801D83C4)),
}
"""
A set of instructions that will be replaced in the game to skip the movie trailer:

- First instruction, located in `MovieApp::calc()`, is replaced with a `li` instruction to set `3`
  in `r0`, forcing the execution of `MovieApp::doEnding()`.
- Second instruction, located in `MovidApp::doEnding()`, is turned into a no-op so that the ending
  is not delayed for 119 frames.
- Third instruction, located in `SceneTitle::demo()`, is changed so that it writes `1` instead of
  `0`. The address where it writes to holds the information for the next thing that will be demoed
  in the title screen if the player continues to remain idle. When set to `0`, it ends up loading
  the `MovieApp`, which we are aiming to avoid; `1`, `2`, and `3` will load the `RaceApp` demo, in
  1P, 2P, or 4P mode respectively. With this change, when the value reaches `3`, it jumps back to
  `1`; avoiding `0`.
- (Debug only) The other two instructions, located in `MoviePlayer::MoviePlayer()` and in
  `MoviePlayer::reset()`, are changed from `bne` to `b`, to avoid hitting assertions when the game
  cannot find the now-removed movie trailer files.
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
    'Mini7',
    'Mini2',
    'Mini3',
    'Mini8',
    'Mini1',
    'Mini5',
)
"""
Internal names of the courses, in order of appearance.
"""

COURSES_TO_COURSE_ID = {
    'Luigi': 0x24,
    'Peach': 0x22,
    'BabyLuigi': 0x21,
    'Desert': 0x32,
    'Nokonoko': 0x28,
    'Mario': 0x25,
    'Daisy': 0x23,
    'Waluigi': 0x2A,
    'Snow': 0x33,
    'Patapata': 0x29,
    'Yoshi': 0x26,
    'Donkey': 0x2D,
    'Wario': 0x2B,
    'Diddy': 0x2C,
    'Koopa': 0x2F,
    'Rainbow': 0x31,
    'Mini7': 0x3A,
    'Mini2': 0x35,
    'Mini3': 0x36,
    'Mini8': 0x3B,
    'Mini1': 0x34,
    'Mini5': 0x38,
}
"""
Course ID as defined internally in the game.
"""

COURSE_TO_MINIMAP_ADDRESSES = {
    'GM4E01': {
        'BabyLuigi': (0x803CDDEC, 0x803CDDF0, 0x803CDDF4, 0x803CDDF8, 0x80141E14),
        'Peach': (0x803CDE0C, 0x803CDE10, 0x803CDE14, 0x803CDE18, 0x80141EE0),
        'Daisy': (0x803CDE34, 0x803CDE38, 0x803CDE3C, 0x803CDE40, 0x8014200C),
        'Luigi': (0x803CDE5C, 0x803CDE60, 0x803CDE64, 0x803CDE68, 0x801420D8),
        'Mario': (0x803CDE74, 0x803CDE78, 0x803CDE7C, 0x803CDE80, 0x801421A4),
        'Yoshi': (0x803CDE90, 0x803CDE94, 0x803CDE98, 0x803CDE9C, 0x80142270),
        'Nokonoko': (0x803CDEB0, 0x803CDEB4, 0x803CDEB8, 0x803CDEBC, 0x8014233C),
        'Patapata': (0x803CDEC8, 0x803CDECC, 0x803CDED0, 0x803CDED4, 0x80142408),
        'Waluigi': (0x803CDEE8, 0x803CDEEC, 0x803CDEF0, 0x803CDEF4, 0x801424D4),
        'Wario': (0x803CDF0C, 0x803CDF10, 0x803CDF14, 0x803CDF18, 0x801425A0),
        'Diddy': (0x803CDF28, 0x803CDF2C, 0x803CDF30, 0x803CDF34, 0x8014266C),
        'Donkey': (0x803CDF40, 0x803CDF44, 0x803CDF48, 0x803CDF4C, 0x80142738),
        'Koopa': (0x803CDF5C, 0x803CDF60, 0x803CDF64, 0x803CDF68, 0x80142804),
        'Rainbow': (0x803CDF70, 0x803CDF74, 0x803CDF78, 0x803CDF7C, 0x801428D0),
        'Desert': (0x803CDF84, 0x803CDF88, 0x803CDF8C, 0x803CDF90, 0x8014299C),
        'Snow': (0x803CDFA4, 0x803CDFA8, 0x803CDFAC, 0x803CDFB0, 0x80142A68),
        'Mini1': (0x803CDFB4, 0x803CDFB8, 0x803CDFBC, 0x803CDFC0, 0x80142B34),
        'Mini2': (0x803CDFC4, 0x803CDFC8, 0x803CDFCC, 0x803CDFD0, 0x80142B6C),
        'Mini3': (0x803CDFD4, 0x803CDFD8, 0x803CDFDC, 0x803CDFE0, 0x80142BA4),
        'Mini5': (0x803CDFE4, 0x803CDFE8, 0x803CDFEC, 0x803CDFF0, 0x80142BDC),
        'Mini7': (0x803CDFF4, 0x803CDFF8, 0x803CDFFC, 0x803CE000, 0x80142C14),
        'Mini8': (0x803CDFE4, 0x803CDFE8, 0x803CDFEC, 0x803CDFF0, 0x80142C4C),
        'Mini8 (2)': (0x803CE004, 0x803CE008, 0x803CE00C, 0x803CE010, 0x80142C4C),
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
        'Mini1': (0x803D7DF4, 0x803D7DF8, 0x803D7DFC, 0x803D7E00, 0x80142B64),
        'Mini2': (0x803D7E04, 0x803D7E08, 0x803D7E0C, 0x803D7E10, 0x80142B9C),
        'Mini3': (0x803D7E14, 0x803D7E18, 0x803D7E1C, 0x803D7E20, 0x80142BD4),
        'Mini5': (0x803D7E24, 0x803D7E28, 0x803D7E2C, 0x803D7E30, 0x80142C0C),
        'Mini7': (0x803D7E34, 0x803D7E38, 0x803D7E3C, 0x803D7E40, 0x80142C44),
        'Mini8': (0x803D7E24, 0x803D7E28, 0x803D7E2C, 0x803D7E30, 0x80142C7C),
        'Mini8 (2)': (0x803D7E44, 0x803D7E48, 0x803D7E4C, 0x803D7E50, 0x80142C7C),
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
        'Mini1': (0x803E85D4, 0x803E85D8, 0x803E85DC, 0x803E85E0, 0x80142B34),
        'Mini2': (0x803E85E4, 0x803E85E8, 0x803E85EC, 0x803E85F0, 0x80142B6C),
        'Mini3': (0x803E85F4, 0x803E85F8, 0x803E85FC, 0x803E8600, 0x80142BA4),
        'Mini5': (0x803E8604, 0x803E8608, 0x803E860C, 0x803E8610, 0x80142BDC),
        'Mini7': (0x803E8614, 0x803E8618, 0x803E861C, 0x803E8620, 0x80142C14),
        'Mini8': (0x803E8604, 0x803E8608, 0x803E860C, 0x803E8610, 0x80142C4C),
        'Mini8 (2)': (0x803E8624, 0x803E8628, 0x803E862C, 0x803E8630, 0x80142C4C),
    },
    'GM4E01dbg': {
        'BabyLuigi': (0x80419100, 0x80419104, 0x80419108, 0x8041910C, 0x8015415C),
        'Peach': (0x80419120, 0x80419124, 0x80419128, 0x8041912C, 0x80154254),
        'Daisy': (0x80419148, 0x8041914C, 0x80419150, 0x80419154, 0x801543AC),
        'Luigi': (0x80419170, 0x80419174, 0x80419178, 0x8041917C, 0x801544A4),
        'Mario': (0x80419188, 0x8041918C, 0x80419190, 0x80419194, 0x8015459C),
        'Yoshi': (0x804191A4, 0x804191A8, 0x804191AC, 0x804191B0, 0x80154694),
        'Nokonoko': (0x804191C4, 0x804191C8, 0x804191CC, 0x804191D0, 0x8015478C),
        'Patapata': (0x804191DC, 0x804191E0, 0x804191E4, 0x804191E8, 0x80154884),
        'Waluigi': (0x804191FC, 0x80419200, 0x80419204, 0x80419208, 0x8015497C),
        'Wario': (0x80419220, 0x80419224, 0x80419228, 0x8041922C, 0x80154A74),
        'Diddy': (0x8041923C, 0x80419240, 0x80419244, 0x80419248, 0x80154B6C),
        'Donkey': (0x80419254, 0x80419258, 0x8041925C, 0x80419260, 0x80154C64),
        'Koopa': (0x80419270, 0x80419274, 0x80419278, 0x8041927C, 0x80154D5C),
        'Rainbow': (0x80419284, 0x80419288, 0x8041928C, 0x80419290, 0x80154E54),
        'Desert': (0x80419298, 0x8041929C, 0x804192A0, 0x804192A4, 0x80154F4C),
        'Snow': (0x804192B8, 0x804192BC, 0x804192C0, 0x804192C4, 0x80155044),
        'Mini1': (0x804192C8, 0x804192CC, 0x804192D0, 0x804192D4, 0x8015513C),
        'Mini2': (0x804192D8, 0x804192DC, 0x804192E0, 0x804192E4, 0x80155174),
        'Mini3': (0x804192E8, 0x804192EC, 0x804192F0, 0x804192F4, 0x801551AC),
        'Mini5': (0x804192F8, 0x804192FC, 0x80419300, 0x80419304, 0x801551E4),
        'Mini7': (0x80419308, 0x8041930C, 0x80419310, 0x80419314, 0x8015521C),
        'Mini8': (0x804192F8, 0x804192FC, 0x80419300, 0x80419304, 0x80155254),
        'Mini8 (2)': (0x80419318, 0x8041931C, 0x80419320, 0x80419324, 0x80155254),
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
    'Mini1': (-7425.0, -16250.0, 8825.0, 16250.0, 0),
    'Mini2': (-5750.0, -11500.0, 5750.0, 11500.0, 0),
    'Mini3': (-9000.0, -18000.0, 9000.0, 18000.0, 0),
    'Mini5': (-10500.0, -21000.0, 10500.0, 21000.0, 0),
    'Mini7': (-8350.7001953125, -16701.30078125, 8350.7001953125, 16701.30078125, 0),
    'Mini8': (-10500.0, -21000.0, 10500.0, 21000.0, 0),
    'Mini8 (2)': (-12500.0, 12500.0, 25000.0, -18519.0, 0),
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

BATTLE_STAGES_FILE_STRINGS = (
    'BattleMapSnap1.bti',
    'BattleMapSnap2.bti',
    'BattleMapSnap3.bti',
    'BattleMapSnap4.bti',
    'BattleMapSnap5.bti',
    'BattleMapSnap6.bti',
    'Mozi_Map1.bti',
    'Mozi_Map2.bti',
    'Mozi_Map3.bti',
    'Mozi_Map4.bti',
    'Mozi_Map5.bti',
    'Mozi_Map6.bti',
    # LAN MODE.
    'Mozi_Map%d.bti',
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
    *BATTLE_STAGES_FILE_STRINGS,
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
        'BattleMapSnap1.bti': 0x803329D0,
        'BattleMapSnap2.bti': 0x80332A18,
        'BattleMapSnap3.bti': 0x803329F4,
        'BattleMapSnap4.bti': 0x80332A3C,
        'BattleMapSnap5.bti': 0x80332A84,
        'BattleMapSnap6.bti': 0x80332A60,
        'Mozi_Map1.bti': 0x803329E4,
        'Mozi_Map2.bti': 0x80332A2C,
        'Mozi_Map3.bti': 0x80332A08,
        'Mozi_Map4.bti': 0x80332A50,
        'Mozi_Map5.bti': 0x80332A98,
        'Mozi_Map6.bti': 0x80332A74,
        'Mozi_Map%d.bti': 0x8033784D,
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
        'BattleMapSnap1.bti': 0x8033C7A0,
        'BattleMapSnap2.bti': 0x8033C7E8,
        'BattleMapSnap3.bti': 0x8033C7C4,
        'BattleMapSnap4.bti': 0x8033C80C,
        'BattleMapSnap5.bti': 0x8033C854,
        'BattleMapSnap6.bti': 0x8033C830,
        'Mozi_Map1.bti': 0x8033C7B4,
        'Mozi_Map2.bti': 0x8033C7FC,
        'Mozi_Map3.bti': 0x8033C7D8,
        'Mozi_Map4.bti': 0x8033C820,
        'Mozi_Map5.bti': 0x8033C868,
        'Mozi_Map6.bti': 0x8033C844,
        'Mozi_Map%d.bti': 0x8034168D,
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
        'BattleMapSnap1.bti': 0x8034CFF0,
        'BattleMapSnap2.bti': 0x8034D038,
        'BattleMapSnap3.bti': 0x8034D014,
        'BattleMapSnap4.bti': 0x8034D05C,
        'BattleMapSnap5.bti': 0x8034D0A4,
        'BattleMapSnap6.bti': 0x8034D080,
        'Mozi_Map1.bti': 0x8034D004,
        'Mozi_Map2.bti': 0x8034D04C,
        'Mozi_Map3.bti': 0x8034D028,
        'Mozi_Map4.bti': 0x8034D070,
        'Mozi_Map5.bti': 0x8034D0B8,
        'Mozi_Map6.bti': 0x8034D094,
        'Mozi_Map%d.bti': 0x80351E6D,
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
        'BattleMapSnap1.bti': 0x80376238,
        'BattleMapSnap2.bti': 0x80376280,
        'BattleMapSnap3.bti': 0x8037625C,
        'BattleMapSnap4.bti': 0x803762A4,
        'BattleMapSnap5.bti': 0x803762EC,
        'BattleMapSnap6.bti': 0x803762C8,
        'Mozi_Map1.bti': 0x8037624C,
        'Mozi_Map2.bti': 0x80376294,
        'Mozi_Map3.bti': 0x80376270,
        'Mozi_Map4.bti': 0x803762B8,
        'Mozi_Map5.bti': 0x80376300,
        'Mozi_Map6.bti': 0x803762DC,
        'Mozi_Map%d.bti': 0x8037E9BD,
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


def get_string_addresses(game_id: str, battle_stages_enabled: bool):
    string_addresses = STRING_ADDRESSES[game_id]

    if battle_stages_enabled:
        return string_addresses

    return {
        string: address
        for string, address in string_addresses.items() if string not in BATTLE_STAGES_FILE_STRINGS
    }


GAMEAUDIO_MAIN_ADDRESSES = {
    'GM4E01': 0x803B06D4,
    'GM4P01': 0x803BA4F4,
    'GM4J01': 0x803CACF4,
    'GM4E01dbg': 0x803FB220,
}
"""
The address in static memory that is passed to the `GameAudio::Main::startSystemSe()` function; it
appears to be a singleton class.

The function is used to play sounds. The second argument is the sound ID (e.g. `0x20000` is the
sound that is played when the player navigates courses or cups).
"""

LUIGIS_MANSION_AUDIO_STREAM_ADDRESSES = {
    'GM4E01': 0x8017C4CC,
    'GM4P01': 0x8017B370,
    'GM4J01': 0x8017C4CC,
    'GM4E01dbg': 0x8019DAB4,
}
"""
The address to the `addi` instruction in `Course::getCourseBGM()` where the audio stream for Luigi's
Mansion (which reuses the audio stream in Bowser's Castle) is selected.
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

SCENEMAPSELECT_CALCANM_CALL_ADDRESSES = {
    'GM4E01': 0x80174614,
    'GM4P01': 0x801734B8,
    'GM4J01': 0x80174614,
    'GM4E01dbg': 0x80193CB4,
}
"""
The address within `SceneMapSelect::map()` from where `SceneMapSelect::calcAnm()` is invoked.
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

LANPLAYINFO_INIT_CALL_ADDRESSES = {
    'GM4E01': 0x801731D8,
    'GM4P01': 0x8017207C,
    'GM4J01': 0x801731D8,
    'GM4E01dbg': 0x80192590,
}
"""
The address to the one place from where `LANPlayInfo::init()` is called. The function will be
hijacked to reset the course page when the LAN session is initialized.
"""

SCENETITLE_INIT_VTABLE_INDEX_ADDRESSES = {
    'GM4E01': 0x8034AB9C,
    'GM4P01': 0x803549DC,
    'GM4J01': 0x803651BC,
    'GM4E01dbg': 0x80394BAC,
}
"""
The address to the vtable index that points to `SceneTitle::init()` symbol. The method will be
hijacked to reset the course page when the title screen is entered.
"""

IS_TILTING_COURSE_CALL_ADDRESSES = {
    'GM4E01': 0x80178FAC,
    'GM4P01': 0x80177E50,
    'GM4J01': 0x80178FAC,
    'GM4E01dbg': 0x801992A8,
}
"""
The address to a `lwz` instruction in `Course::reset()` that will be replaced with a function call
that leaves in `r3` whether the course in the current slot and in the current page is a tilting
course. The next instruction to this address will be replaced, too, to compare whether `r3` is `1`.
"""

CUP_FILENAMES_ARRAY_INSTRUCTION_ADDRESSES = {
    'GM4E01': 0x8016BDC0,
    'GM4P01': 0x8016AC64,
    'GM4J01': 0x8016BDC0,
    'GM4E01dbg': 0x80189C4C,
}
"""
Memory address to the first of two non-consecutive instructions in `SceneCourseSelect::setTexture()`
that load the address to the string array that holds the filenames to the cup name images that are
shown for the All-Cup Tour. The instructions will be replaced to point to a different array that
holds the filenames for the Extender Cup.
"""

PREVIEW_FILENAMES_ARRAY_INSTRUCTIONS_ADDRESSES = {
    'GM4E01': (0x8016A978, 0x8016AA50, 0x8016AB10, 0x8016BE38),
    'GM4P01': (0x8016981C, 0x801698F4, 0x801699B4, 0x8016ACDC),
    'GM4J01': (0x8016A978, 0x8016AA50, 0x8016AB10, 0x8016BE38),
    'GM4E01dbg': (0x801884B8, 0x80188590, 0x80188650, 0x80189CC4),
}
"""
Memory addresses to four pairs of two consecutive instructions that put in `r4` the filename of the
preview image that is to be loaded by a `J2DPictureEx::changeTexture()` call in the All-Cup Tour.
For the Extender cup, these strings are replaced with a single preview image with static text.
"""

GP_CUP_INDEX_ADDRESSES = {
    'GM4E01': 0x803B0FC7,
    'GM4P01': 0x803BADE7,
    'GM4J01': 0x803CB5E7,
    'GM4E01dbg': 0x803FBB13,
}
"""
Memory address where the index of the selected cup in GP mode is stored.
"""

GP_COURSE_INDEX_ADDRESSES = {
    'GM4E01': 0x803B0FCB,
    'GM4P01': 0x803BADEB,
    'GM4J01': 0x803CB5EB,
    'GM4E01dbg': 0x803FBB17,
}
"""
Memory address where the course index in GP mode is stored.
"""

GP_TOTAL_COURSE_COUNT_INSTRUCTION_ADDRESSES = {
    'GM4E01': 0x80154C74,
    'GM4P01': 0x80153C00,
    'GM4J01': 0x80154C74,
    'GM4E01dbg': 0x8016DD6C,
}
"""
The address to the `li` instruction that loads the hardcoded course count in the All-Cup Tour that
is then shown in the HUD at the start of the race. For the Extender Cup, the hardcoded value is
multiplied by the number of course pages.
"""

SEQUENCEINFO_SETCLRGPCOURSE_CALL_ADDRESSES = {
    'GM4E01': 0x80126088,
    'GM4P01': 0x801260AC,
    'GM4J01': 0x80126088,
    'GM4E01dbg': 0x80133CE0,
}
"""
The address to the one place from where `SequenceInfo::setClrGPCourse()` is called. This `bl`
instruction will be hijacked to adjust the course index and course page in the Extender Cup at the
end of each race.
"""

ON_GP_ABOUT_TO_START_INSERTION_ADDRESSES = {
    'GM4E01': 0x8016B27C,
    'GM4P01': 0x8016A120,
    'GM4J01': 0x8016B27C,
    'GM4E01dbg': 0x80188E3C,
}
"""
The address to an instruction in `SceneCourseSelect::buttonA()` that is replaced with a function
call to run a few more extra instructions before the GP starts (e.g. to reset the global course
index for the Extender Cup). The hijacked instruction is the instruction that resets the local
course index, so it somewhat pertinent to replace that instruction.
"""

GET_GP_COURSE_INDEX_INSERTION_ADDRESSES = {
    'GM4E01': 0x80154D18,
    'GM4P01': 0x80153CA4,
    'GM4J01': 0x80154D18,
    'GM4E01dbg': 0x8016DE10,
}
"""
The address to the instruction in `PreRace2D::setGP()` that loads the course index to be shown in
the HUD at the start of the race. The instruction is replaced with a function call that returns a
different value for the Extender Cup, while keeping the original value for the rest of the cups.
"""

GP_AWARDED_SCORES_ADDRESSES = {
    'GM4E01': 0x8032C890,
    'GM4P01': 0x803366D0,
    'GM4J01': 0x80346EB0,
    'GM4E01dbg': 0x8036F410,
}
"""
The address to a 8-integer array (`SequenceInfo::RANKPOINT`) that stores the scores that are awarded
to each player after each race in GP mode. For the Extender Cup, these scores are lowered to limit
the maximum score that can be achieved by a single player. The game can only show up to 999 points
in the scoreboard, which is a limit that would be exceeded when there are more than 6 configured
course pages. If the 999 limit in the scoreboard is ever solved, this logic can be removed.
"""

ITEMOBJMGR_ISAVAILABLEROLLINGSLOT_CALL_ADDRESSES = {
    'GM4E01': 0x801FBE84,
    'GM4P01': 0x801FBE54,
    'GM4J01': 0x801FBEAC,
    'GM4E01dbg': 0x8022ED1C,
}
"""
The address to one of the two places from where `ItemObjMgr::IsAvailableRollingSlot()` is called.
This `bl` instruction will be hijacked to add support for type-specific item boxes.
"""

ITEMSHUFFLEMGR_CALCSLOT_CALL_ADDRESSES = {
    'GM4E01': 0x8020CBC4,
    'GM4P01': 0x8020CB94,
    'GM4J01': 0x8020CBEC,
    'GM4E01dbg': 0x80243000,
}
"""
The address to the one place from where `ItemShuffleMgr::calcSlot()` is called. This `bl`
instruction will be hijacked to add support for type-specific item boxes.
"""

RESET_SECTION_COUNT_CALL_ADDRESSES = {
    'GM4E01': 0x80179298,
    'GM4P01': 0x8017813C,
    'GM4J01': 0x80179298,
    'GM4E01dbg': 0x801996D8,
}
"""
The address to the area in memory where the branch-link to `reset_section_count` will be inserted.
This is called during `loadCrsData` to reset the section counter.
"""

COUNT_SECTION_POINT_CALL_ADDRESSES = {
    'GM4E01': 0x8017C7D4,
    'GM4P01': 0x8017B678,
    'GM4J01': 0x8017C7D4,
    'GM4E01dbg': 0x8019DE28,
}
"""
The address to the area in memory where the branch-link to `count_section_point` will be inserted.
This is called during `setPointData` and increments the section counter in memory.
"""

OVERRIDE_TOTAL_LAP_COUNT_CALL_ADDRESSES = {
    'GM4E01': 0x80187E24,
    'GM4P01': 0x80186CC8,
    'GM4J01': 0x80187E24,
    'GM4E01dbg': 0x801ACB1C,
}
"""
The address to the area in memory where the branch-link to `override_total_lap_count()` will be
inserted.
This hijacks assigning r3 to r0 to run a system for forcing lap counts in a section course.
In the Debug build, the hijacked instruction targets r22 instead of r0.
"""

CHECK_LAP_EX_CALL_ADDRESSES = {
    'GM4E01': 0x80186648,
    'GM4P01': 0x801854EC,
    'GM4J01': 0x80186648,
    'GM4E01dbg': 0x801AA9A4,
}
"""
The address to the area in memory where the branch-link to `check_lap_ex` will be inserted.
This is called directly after the branch to `setPass` and forces a lap-increment depending
on an unused sector parameter.
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

KART_EXTENDED_TERRAIN_FLAG_ADDRESSES = {
    'GM4E01': 0x802EDFC8,
    'GM4P01': 0x80308588,
    'GM4J01': 0x80319008,
    'GM4E01dbg': 0x8032BB28,
}
"""
Padding used to store a Char that functions as a flag for every Kart in the race.

This is the address to the "This is padding to SCRNblo2" string.
"""

KART_BOUNCE_DEFAULT_READ_ADDRESSES = {
    k: v + 8
    for k, v in KART_EXTENDED_TERRAIN_FLAG_ADDRESSES.items()
}
"""
Padding used by bounce logic to read movement vector data from if nothing was set up for the
material in the .BCO file. Very useful for developing a CC with Bouncy if you don't know
how much force you require. Loccation defined is KART_EXTENDED_TERRAIN_FLAG[game_id] + 0x8.
"""

DO_SPD_CTRL_CALL_HIJACK_ADDRESSES = {
    'GM4E01': 0x802aa8c8,
    'GM4P01': 0x802aa8a4,
    'GM4J01': 0x802aa8f0,
    'GM4E01dbg': 0x802ec054,
}
"""
A call to the function DoSpeedCtrl, done after the game calculates the Kart's status.
This call is from the default case, which encompasses any driving state where the kart is not
incapacitated/unable to move. This is hijacked to stop the Kart's Momentum from being clamped.
"""

GET_SPLASH_HEIGHT_INLINE_ADDRESSES = {
    'GM4E01': 0x8018160c,
    'GM4P01': 0x801804B0,
    'GM4J01': 0x8018160c,
    'GM4E01dbg': 0x801a33b0,
}
"""
A lwz instruction in the function getSplashHeight. This occurs before the material's splash code,
which I refer to as the material's hash, is read. It ordinarily loads the location of the hash
into r3, but r3 is set to 0 instead if the ground material is one used by mods.
"""

GET_SPLASH_ID_INLINE_ADDRESSES = {
    'GM4E01': 0x801816A8,
    'GM4P01': 0x8018054C,
    'GM4J01': 0x801816A8,
    'GM4E01dbg': 0x801a33b0,
}
"""
A lwz instruction in the function getSplashId. This occurs before the material's splash code,
which I refer to as the material's hash, is read. It ordinarily loads the location of the hash
into r3, but r3 is set to 0 instead if the ground material is one used by mods.
"""

IS_ITEM_INVAL_GROUND_HIJACK_ADDRESSES = {
    'GM4E01': 0x8021857c,
    'GM4P01': 0x80218558,
    'GM4J01': 0x802185a4,
    'GM4E01dbg': 0x8024f714,
}
"""
A call to the function isItemInvalGround, which ordinarily returns false when it reads vanilla
ground material used by the game. When it reads custom materials, it may return true. It is
hijacked to nullify this behaviour, so that items may collide with custom materials.
"""

GET_ADD_THICKNESS_INLINE_ADDRESSES = {
    'GM4E01': 0x8017de14,
    'GM4P01': 0x8017ccb8,
    'GM4J01': 0x8017de14,
    'GM4E01dbg': 0x801a0064,
}
"""
Inserted into the function "getAddThickness", over a lbz instruction reading from the material
hash. It presumably does something to the ground based on what it reads, and it is called from
Ground::checkPosition. It is better to stop it from reading errant data.
"""

GET_STAGGER_CODE_HIJACK_AIR_CHECK_ADDRESSES = {
    'GM4E01': 0x802adbd4,
    'GM4P01': 0x802adbb0,
    'GM4J01': 0x802adbfc,
    'GM4E01dbg': 0x802efb04,
}
"""
A call to the function getStaggerCode, which ordinarily returns true when the material hash's 
second byte is set to 1. 0x50000000 would not trigger it, but 0x50000100 would. This call to 
the function is from "KartGame::DoAirCheck".
"""

GET_STAGGER_CODE_HIJACK_DANGER_LOOP_ADDRESSES = {
    'GM4E01': 0x802b90c8,
    'GM4P01': 0x802b908c,
    'GM4J01': 0x802b90f0,
    'GM4E01dbg': 0x802fa140,
}
"""
A call to the function getStaggerCode, from "KartAnime::IsDangerLoopAnime". This call is also
hijacked, just in case. It seems the first hijack is enough, but it's better to not read
errant data if it can be helped.
"""

CFS_ITEMOBJMGR_OCCURITEM_CALL_ADDRESSES = {
    'GM4E01': 0x802889A0,
    'GM4P01': 0x80288980,
    'GM4J01': 0x802889C8,
    'GM4E01dbg': 0x802CAA10,
}
"""
Address to a `bl` instruction in `TMapObjMeteor::showItem()` from where `ItemObjMgr::occurItem()`
is called. It is hijacked to add support for customizable item types in falling stars.
"""

CFS_GEOGRAPHYOBJ_GETGEORND_CALL_ADDRESSES = {
    'GM4E01': 0x80288940,
    'GM4P01': 0x80288920,
    'GM4J01': 0x80288968,
    'GM4E01dbg': 0x802CA9B0,
}
"""
Address to a `bl` instruction in `TMapObjMeteor::showItem()` from where `GeographyObj::getGeoRnd()`
is called. It is hijacked with a function that returns `true` if the object needs to be dropped
based on a custom data field (0x3A) in the falling star object. `this` (`r31`) will be put in `r3`
before the `bl` call.

Note that the instructions between the new `bl` instruction and the preexisting `bne` instruction
are now redundant and will be turned into no-op. An extra `cmpw` instruction against the `r3`
register (return value from the new function) will be added immediately above the `bne` instruction
that determines the jump.
"""

CFS_JPEFFECTMGR_CREATEEMT_CALLS_ADDRESSES = {
    'GM4E01': (0x802883DC, 0x8028877C, 0x802889D0),
    'GM4P01': (0x802883BC, 0x8028875C, 0x802889B0),
    'GM4J01': (0x80288404, 0x802887A4, 0x802889F8),
    'GM4E01dbg': (0x802CA424, 0x802CA7EC, 0x802CAA40),
}
"""
Addresses to `bl` instructions in `TMapObjMeteor` from where `JPEffectMgr::createEmt()` is called.
They are hijacked with a function that checks a custom data field (0x3C) to determine whether
particles need to be created for the current falling object.
"""

CFS_KARTGAME_ITEMWATCHMAN_CALLS_ADDRESSES = {
    'GM4E01': (0x802C39E0, 0x802C40D0, 0x802C8D88, 0x802C9014, 0x802C9860, 0x802C9B84, 0x802C9E58),
    'GM4P01': (0x802C39A4, 0x802C4094, 0x802C8D4C, 0x802C8FD8, 0x802C9824, 0x802C9B48, 0x802C9E1C),
    'GM4J01': (0x802C3A08, 0x802C40F8, 0x802C8DB0, 0x802C903C, 0x802C9888, 0x802C9BAC, 0x802C9E80),
    'GM4E01dbg':
    (0x80304AD8, 0x80304EC4, 0x80308F04, 0x80309110, 0x8030984C, 0x80309B60, 0x80309E4C),
}
"""
Addresses to `bl` instructions in `KartTumble` and `KartCrash` from where `KartGame::ItemWatchMan()`
is called. They are hijacked with a function that checks whether the subject item object was dropped
by a real kart (i.e. it has a kart owner index), or was synthetically generated (e.g. from a falling
star configured with a custom item type).
"""

for address in OSARENALO_ADDRESSES.values():
    assert address % 32 == 0

SYMBOLS_MAP = {
    'GM4E01':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        GameAudio_Main_startSystemSe = 0x80115E74;
        SceneCourseSelect__calcAnm = 0x8016B6E0;
        SceneMapSelect__calcAnm = 0x80174AD0;
        SceneMapSelect__map_init = 0x801741FC;
        SceneMapSelect__reset = 0x8017398C;
        SceneTitle__init = 0x8012D6C8;
        KartChecker__setLapTime = 0x80186868;
        LANSelectMode__calcAnm = 0x801E428C;
        LANPlayInfo__init = 0x801E66E4;
        SequenceInfo__setClrGPCourse = 0x8013FCE4;
        ItemObjMgr__IsAvailableRollingSlot = 0x8020B62C;
        ItemShuffleMgr__calcSlot = 0x8020CFEC;
        ItemObj__getSpecialKind = 0x8021A024;
        ItemObjMgr__occurItem = 0x8020929C;
        GeographyObj__getGeoRnd = 0x801F7E78;
        JPEffectMgr__createEmt = 0x801FD6B8;
        KartGame__ItemWatchMan = 0x802AEC2C;
        ObjUtility__getKartZdir = 0x80225864;
        KartStrat__DoSpeedCrl = 0x802a77f4;
        CrsGround__isItemInvalGround = 0x80181524;
        CrsGround__getStaggerCode = 0x80181564;
        """),
    'GM4P01':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        GameAudio_Main_startSystemSe = 0x80115EA4;
        SceneCourseSelect__calcAnm = 0x8016A584;
        SceneMapSelect__calcAnm = 0x80173974;
        SceneMapSelect__map_init = 0x801730A0;
        SceneMapSelect__reset = 0x80172830;
        SceneTitle__init = 0x8012D6EC;
        KartChecker__setLapTime = 0x8018570C;
        LANSelectMode__calcAnm = 0x801E4264;
        LANPlayInfo__init = 0x801E66B4;
        SequenceInfo__setClrGPCourse = 0x8013FD14;
        ItemObjMgr__IsAvailableRollingSlot = 0x8020B5FC;
        ItemShuffleMgr__calcSlot = 0x8020CFBC;
        ItemObj__getSpecialKind = 0x8021A008;
        ItemObjMgr__occurItem = 0x8020926C;
        GeographyObj__getGeoRnd = 0x801F7E48;
        JPEffectMgr__createEmt = 0x801FD688;
        KartGame__ItemWatchMan = 0x802AEBF0;
        ObjUtility__getKartZdir = 0x80225848;
        KartStrat__DoSpeedCrl = 0x802a77d0;
        CrsGround__isItemInvalGround = 0x801803c8;
        CrsGround__getStaggerCode = 0x80180408;
        """),
    'GM4J01':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        GameAudio_Main_startSystemSe = 0x80115E74;
        SceneCourseSelect__calcAnm = 0x8016B6E0;
        SceneMapSelect__calcAnm = 0x80174AD0;
        SceneMapSelect__map_init = 0x801741FC;
        SceneMapSelect__reset = 0x8017398C;
        SceneTitle__init = 0x8012D6C8;
        KartChecker__setLapTime = 0x80186868;
        LANSelectMode__calcAnm = 0x801E42B4;
        LANPlayInfo__init = 0x801E670C;
        SequenceInfo__setClrGPCourse = 0x8013FCE4;
        ItemObjMgr__IsAvailableRollingSlot = 0x8020B654;
        ItemShuffleMgr__calcSlot = 0x8020D014;
        ItemObj__getSpecialKind = 0x8021A04C;
        ItemObjMgr__occurItem = 0x802092C4;
        GeographyObj__getGeoRnd = 0x801F7EA0;
        JPEffectMgr__createEmt = 0x801FD6E0;
        KartGame__ItemWatchMan = 0x802AEC54;
        ObjUtility__getKartZdir = 0x8022588c;
        KartStrat__DoSpeedCrl = 0x802a781c;
        CrsGround__isItemInvalGround = 0x80181524;
        CrsGround__getStaggerCode = 0x80181564;
        """),
    'GM4E01dbg':
    textwrap.dedent("""\
        memcpy = 0x80003540;
        GameAudio_Main_startSystemSe = 0x8011E540;
        SceneCourseSelect__calcAnm = 0x80189448;
        SceneMapSelect__calcAnm = 0x801943D0;
        SceneMapSelect__map_init = 0x80193824;
        SceneMapSelect__reset = 0x80192D44;
        SceneTitle__init = 0x8013C9A8;
        KartChecker__setLapTime = 0x801AADD0;
        KartChecker__isGoal = 0x801AACD8;
        KartChecker__incLap = 0x801AACE0;
        LANSelectMode__calcAnm = 0x80216028;
        LANPlayInfo__init = 0x80218580;
        SequenceInfo__setClrGPCourse = 0x801517D0;
        ItemObjMgr__IsAvailableRollingSlot = 0x80241360;
        ItemShuffleMgr__calcSlot = 0x80243508;
        ItemObj__getSpecialKind = 0x802512DC;
        ItemObjMgr__occurItem = 0x8023E5C4;
        GeographyObj__getGeoRnd = 0x8022AC14;
        JPEffectMgr__createEmt = 0x80230544;
        KartGame__ItemWatchMan = 0x802F09C4;
        ObjUtility__getKartZdir = 0x8025e39c;
        KartStrat__DoSpeedCrl = 0x802ea110;
        CrsGround__isItemInvalGround = 0x801a3204;
        CrsGround__getStaggerCode = 0x801a32c0;
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

    # Image filenames of the battle stages end with a number; an infix (second character) is used.
    if any(string.startswith(name) for name in ('BattleMapSnap', 'Mozi_Map', 'Mozi_Battle')):
        return 1

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


def patch_bti_filenames_in_blo_file(game_id: str, battle_stages_enabled: bool, blo_path: str):
    with open(blo_path, 'rb') as f:
        data = f.read()

    for string in get_string_addresses(game_id, battle_stages_enabled):
        char_offset = find_char_offset_in_string(string)
        new_string = bytearray(string, encoding='ascii')
        new_string[char_offset] = ord('0')
        string = bytes(string, encoding='ascii')
        data = data.replace(string, new_string)

    with open(blo_path, 'wb') as f:
        f.write(data)


def patch_dol_file(
    iso_tmp_dir: str,
    game_id: str,
    args: argparse.Namespace,
    initial_page_number: int,
    use_alternative_buttons: bool,
    replaces_data: dict,
    minimap_data: dict,
    tilt_setting_data: dict,
    audio_track_data: 'tuple[tuple[int]]',
    battle_stages_enabled: bool,
    remove_movie_trailer: bool,
    extender_cup: bool,
    type_specific_item_boxes: bool,
    customizable_falling_stars: bool,
    sectioned_courses: bool,
    tilting_courses: bool,
    bouncy_terrain_type: bool,
    dol_path: str,
    log: logging.Logger,
    debug_output: bool,
):
    import mkdd_extender  # pylint: disable=import-outside-toplevel

    log.info('Generating and injecting C code...')

    if bouncy_terrain_type and game_id == 'GM4E01dbg':
        raise mkdd_extender.MKDDExtenderError(
            'The **Bouncy Terrain Type** code patch is not currently compatible with the NTSC-U '
            'Debug build.')

    if args.lan_choose_character_and_kart:
        with tempfile.TemporaryDirectory(prefix=mkdd_extender.TEMP_DIR_PREFIX) as temp_dir:
            asm_dir = os.path.join(tools_dir, 'lan_choose_character_kart', 'asm')
            data_file = lan_choose_character_kart.make_data_file(game_id, temp_dir, asm_dir)

            with open(os.path.join(iso_tmp_dir, 'files', 'DATA'), 'wb') as f:
                f.write(data_file)

            lan_choose_character_kart.patch_maindol(game_id, dol_path, temp_dir, asm_dir)

    initial_page_index = initial_page_number - 1
    page_count = len(audio_track_data)
    page_course_count = (mkdd_extender.RACE_AND_BATTLE_COURSE_COUNT
                         if battle_stages_enabled else mkdd_extender.RACE_TRACK_COUNT)
    string_addresses = get_string_addresses(game_id, battle_stages_enabled)

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
    for string, address in string_addresses.items():
        char_offset = find_char_offset_in_string(string)
        char_address = address + char_offset
        char_addresses.append(f'(char*)0x{char_address:08X}')
    char_addresses = ', '.join(char_addresses)
    string_data_code_lines.append(f'char* char_addresses[] = {{{char_addresses}}};')
    string_data_code = '\n'.join(string_data_code_lines)

    # Read initial minimap values.
    initial_minimap_values = read_minimap_values(game_id, dol_path)
    course_to_minimap_addresses = COURSE_TO_MINIMAP_ADDRESSES[game_id].copy()

    # Pipe Plaza, which in the original game shares minimap coordinates addresses with Tilt-A-Kart,
    # will be set to use an alternative minimap coordinates array.
    alternative_already_used = (initial_minimap_values['Mini8 (2)']
                                != COURSE_TO_MINIMAP_VALUES['Mini8 (2)'])
    if alternative_already_used:
        # If the initial values are already custom, those are the initial values for Pipe Plaza.
        initial_minimap_values['Mini8'] = initial_minimap_values['Mini8 (2)']
    course_to_minimap_addresses['Mini8'] = course_to_minimap_addresses['Mini8 (2)']

    # Minimap data.
    minimap_data_code_lines = []
    minimap_data_code_lines.append('float* const coordinates_addresses[] = {')
    for track_index in range(page_course_count):
        if track_index > 0:
            minimap_data_code_lines.append(',')
        addresses = course_to_minimap_addresses[COURSES[track_index]]
        for i in range(4):
            comma = '' if i == 0 else ', '
            minimap_data_code_lines.append(f'{comma}(float*)0x{addresses[i]:08X}')
    minimap_data_code_lines.append('};')
    minimap_data_code_lines.append('char* const orientations_addresses[] = {')
    for track_index in range(page_course_count):
        if track_index > 0:
            minimap_data_code_lines.append(',')
        addresses = course_to_minimap_addresses[COURSES[track_index]]
        minimap_data_code_lines.append(f'(char*)0x{addresses[4] + 3:08X}')
    minimap_data_code_lines.append('};')
    minimap_data_code_lines.append(
        f'const float coordinates[PAGE_COUNT][{page_course_count} * 4] = {{')
    for page_index in range(page_count):
        minimap_data_code_lines.append('{' if page_index == 0 else ', {')
        for track_index in range(page_course_count):
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
    minimap_data_code_lines.append(f'const char orientations[PAGE_COUNT][{page_course_count}] = {{')
    for page_index in range(page_count):
        minimap_data_code_lines.append('{' if page_index == 0 else ', {')
        for track_index in range(page_course_count):
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
    max_audio_index = -1
    audio_data_code_lines = []
    for page_index, audio_indexes in enumerate(audio_track_data):
        audio_data_code_lines.append('{' if page_index == 0 else ', {')
        for i, audio_index in enumerate(audio_indexes):
            if i > 0:
                audio_data_code_lines.append(',')
            max_audio_index = max(max_audio_index, audio_index)
            audio_data_code_lines.append(f'{audio_index}')
        audio_data_code_lines.append('}')
    audio_data_code_lines.append('};')
    audio_data_type = 'char' if max_audio_index <= 255 else 'short'
    audio_data_code_lines.insert(0, f'const {audio_data_type} audio_indexes[PAGE_COUNT][32] = {{')
    audio_data_code_lines.append(f'const unsigned {audio_data_type}* const page_audio_indexes = '
                                 f'(const unsigned {audio_data_type}*)audio_indexes[(int)page];')
    audio_data_code = '\n'.join(audio_data_code_lines)

    # Tilting courses data.
    page_tilting_courses = collections.defaultdict(list)
    page_tilting_courses[0].append(COURSES.index('Mini5'))  # Just Tilt-A-Kart in first page.
    for page_index in range(page_count):
        if page_index == 0:  # First page already handled.
            continue
        for track_index in range(page_course_count):
            key = (page_index, track_index)
            # Tilting courses are those that replace Tilt-A-Kart, or, if the Tilting Courses code
            # patch has been enabled, those whose tilt setting in the BOL header has been set to
            # "entire course".
            if (replaces_data[key] == 'Mini5'
                    or (tilting_courses and tilt_setting_data[key] == 0x02)):
                page_tilting_courses[page_index].append(track_index)
    tilting_data_code_lines = []
    for page_index, track_indexes in page_tilting_courses.items():
        tilting_data_code_lines.append('else if' if tilting_data_code_lines else 'if')
        tilting_data_code_lines.append(f' (page == {page_index}) {{')
        for track_index in track_indexes:
            course_id = COURSES_TO_COURSE_ID[COURSES[track_index]]
            tilting_data_code_lines.append(f'if (course_id == {course_id}) {{ return true; }}')
        tilting_data_code_lines.append('}')
    tilting_data_code = '\n'.join(tilting_data_code_lines)

    # Addresses to symbols that are only known after the first pass.
    extender_cup_cup_filenames_address = None
    extender_cup_preview_filename_address = None
    scenetitle_init_ex_address = None

    for pass_number in range(2):
        # The project is going to be built twice; the size of the new DOL section needs to be known
        # to determine the OS Arena, which needs too be known to determine the offset required for
        # certain of the addresses that appear in the C code that refer to dynamic memory. When the
        # OS Arena changes, these addresses need to be offset too, based on the new value, and the
        # retail value.
        offset = aligned(unaligned_new_osarena_value) - OSARENALO_ADDRESSES[game_id]

        # Load the C file and replace constants and placeholders.
        replacements = (
            ('__ALT_BUTTONS_STATE_ADDRESS__', f'0x{ALT_BUTTONS_STATE_ADDRESSES[game_id]:08X}'),
            ('__BATTLE_STAGES__', str(int(battle_stages_enabled))),
            ('__BUTTONS_STATE_ADDRESS__', f'0x{BUTTONS_STATE_ADDRESSES[game_id]:08X}'),
            ('__COURSE_TO_STREAM_FILE_INDEX_ADDRESS__',
             f'0x{COURSE_TO_STREAM_FILE_INDEX_ADDRESSES[game_id] + offset:08X}'),
            ('__CURRENT_PAGE_ADDRESS__', f'0x{CURRENT_PAGE_ADDRESSES[game_id]:08X}'),
            ('__EXTENDER_CUP__', str(int(extender_cup))),
            ('__GAMEAUDIO_MAIN_ADDRESS__', f'0x{GAMEAUDIO_MAIN_ADDRESSES[game_id]:08X}'),
            ('__GM4E01_DEBUG_BUILD__', str(int(game_id == 'GM4E01dbg'))),
            ('__GM4P01_PAL__', str(int(game_id == 'GM4P01'))),
            ('__GP_AWARDED_SCORES_ADDRESS__', f'0x{GP_AWARDED_SCORES_ADDRESSES[game_id]:08X}'),
            ('__GP_COURSE_INDEX_ADDRESS__', f'0x{GP_COURSE_INDEX_ADDRESSES[game_id]:08X}'),
            ('__GP_CUP_INDEX_ADDRESS__', f'0x{GP_CUP_INDEX_ADDRESSES[game_id]:08X}'),
            ('__GP_GLOBAL_COURSE_INDEX_ADDRESS__',
             f'0x{GP_GLOBAL_COURSE_INDEX_ADDRESSES[game_id]:08X}'),
            ('__GP_INITIAL_PAGE_ADDRESS__', f'0x{GP_INITIAL_PAGE_ADDRESSES[game_id]:08X}'),
            ('__LAN_STRUCT_ADDRESS__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][0]:08X}'),
            ('__LAN_STRUCT_OFFSET1__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][1]:04X}'),
            ('__LAN_STRUCT_OFFSET2__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][2]:04X}'),
            ('__LAN_STRUCT_OFFSET3__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][3]:04X}'),
            ('__LAN_STRUCT_OFFSET4__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][4]:04X}'),
            ('__LAN_STRUCT_OFFSET5__', f'0x{LAN_STRUCT_ADDRESSES_AND_OFFSETS[game_id][5]:04X}'),
            ('__PAGE_COUNT__', f'{page_count}'),
            ('__PLAYER_ITEM_ROLLS_ADDRESS__', f'0x{PLAYER_ITEM_ROLLS_ADDRESSES[game_id]:08X}'),
            ('__REDRAW_COURSESELECT_SCREEN_ADDRESS__',
             f'0x{REDRAW_COURSESELECT_SCREEN_ADDRESSES[game_id]:08X}'),
            ('__SPAM_FLAG_ADDRESS__', f'0x{SPAM_FLAG_ADDRESSES[game_id]:08X}'),
            ('__USE_ALT_BUTTONS__', str(int(use_alternative_buttons))),
            ('__RESET_COURSE_PAGE_ON_LAN_INITIALIZATION__',
             str(initial_page_index) if args.reset_course_page_on_lan_initialization else '-1'),
            ('__RESET_COURSE_PAGE_ON_TITLE_SCREEN__',
             str(initial_page_index) if args.reset_course_page_on_title_screen else '-1'),
            ('__TILTING_COURSES__', str(int(tilting_courses))),
            ('__TYPE_SPECIFIC_ITEM_BOXES__', str(int(type_specific_item_boxes))),
            ('__CUSTOMIZABLE_FALLING_STARS__', str(int(customizable_falling_stars))),
            ('__SECTIONED_COURSES__', str(int(sectioned_courses))),
            ('__BOUNCY_TERRAIN_TYPE__', str(int(bouncy_terrain_type))),
            ('__KART_EXTENDED_TERRAIN_FLAG_ADDRESS__',
             f'0x{KART_EXTENDED_TERRAIN_FLAG_ADDRESSES[game_id]:04X}'),
            ('__KART_BOUNCE_DEFAULT_READ_ADDRESS__',
             f'0x{KART_BOUNCE_DEFAULT_READ_ADDRESSES[game_id]:04X}'),
            ('// __AUDIO_DATA_PLACEHOLDER__', audio_data_code),
            ('// __MINIMAP_DATA_PLACEHOLDER__', minimap_data_code),
            ('// __STRING_DATA_PLACEHOLDER__', string_data_code),
            ('// __TILTING_DATA_PLACEHOLDER__', tilting_data_code),
        )
        with open(os.path.join(code_dir, 'lib.c'), 'r', encoding='ascii') as f:
            code = f.read()
        for name, value in replacements:
            code = code.replace(name, value)

        with tempfile.TemporaryDirectory(prefix=mkdd_extender.TEMP_DIR_PREFIX) as tmp_dir:
            with current_directory(tmp_dir):
                project = devkit_tools.Project(dol_path, address=dol_section_address)
                project.set_osarena_patcher(patch_osarena)

                # Initialize static variables.
                if page_count > 1:
                    project.dol.seek(SPAM_FLAG_ADDRESSES[game_id])
                    project.dol.write(b'\0')
                    project.dol.seek(CURRENT_PAGE_ADDRESSES[game_id])
                    project.dol.write(initial_page_index.to_bytes(1, 'big'))
                if extender_cup:
                    project.dol.seek(GP_GLOBAL_COURSE_INDEX_ADDRESSES[game_id])
                    project.dol.write(b'\0')
                if type_specific_item_boxes:
                    project.dol.seek(PLAYER_ITEM_ROLLS_ADDRESSES[game_id])
                    project.dol.write(b'\xff\xff\xff\xff\xff\xff\xff\xff')

                if bouncy_terrain_type:
                    project.dol.seek(KART_EXTENDED_TERRAIN_FLAG_ADDRESSES[game_id])
                    project.dol.write(b'\x00\x00\x00\x00\x00\x00\x00\x00')
                    project.dol.seek(KART_BOUNCE_DEFAULT_READ_ADDRESSES[game_id])
                    project.dol.write(b'\x50\x00\x50\x00')

                # Initialize the strings with the character of the first page ('0').
                if page_count > 1:
                    for string, address in string_addresses.items():
                        char_offset = find_char_offset_in_string(string)
                        char_address = address + char_offset
                        project.dol.seek(char_address)
                        project.dol.write(str(initial_page_index).encode('utf-8'))

                # Set up minimap coordinates for the selected initial page.
                if page_count > 1:
                    for track_index in range(page_course_count):
                        addresses = course_to_minimap_addresses[COURSES[track_index]]
                        if initial_page_index == 0:
                            values = initial_minimap_values[COURSES[track_index]]
                        else:
                            values = minimap_data[(initial_page_index, track_index)]
                        for i in range(4):
                            project.dol.seek(addresses[i])
                            project.dol.write(struct.pack('>f', values[i]))
                        project.dol.seek(addresses[4] + 3)
                        project.dol.write(struct.pack('>B', values[4]))

                if not args.skip_menu_titles:
                    project.dol.seek(LAN_MENU_TITLE_INDEX_INSTRUCTION_ADDRESSES[game_id] + 3)
                    project.dol.write(b'\4')

                if page_count > 1:
                    # When custom courses are present, there is no guarantee that the custom courses
                    # in the Bowser's Castle and Luigi's Mansion slots (which share the same music
                    # file) would have a similar music theme. To avoid playing an unfit music track
                    # in the battle stage, the regular battle stage music will be used for the
                    # Luigi's Mansion slot.
                    project.dol.seek(LUIGIS_MANSION_AUDIO_STREAM_ADDRESSES[game_id] + 3)
                    project.dol.write(b'\x23')

                if battle_stages_enabled:
                    # The four offsets to Pipe Plaza's coordinates array can be seen in a number of
                    # `lfs` instructions near the `li` instruction that defines the orientation.
                    # These instructions need to be tweaked to point to the unused array. The base
                    # offset is hardcoded: it's the first offset seen in the `default:` case in the
                    # `switch` in `Race2D::__ct()`.
                    pipe_plaza_orientation_address = course_to_minimap_addresses['Mini8'][4]
                    base_offset = 0x9A70 if game_id != 'GM4E01dbg' else 0xA164
                    for i, offset_from_li_instruction_address in enumerate((24, 16, 4, -4)):
                        lfs_instruction_address = \
                            pipe_plaza_orientation_address + offset_from_li_instruction_address
                        project.dol.seek(lfs_instruction_address)
                        lfs_instruction = dolreader.read_uint32(project.dol)
                        lfs_instruction = (lfs_instruction & 0xFFFF0000) | (base_offset - i * 4)
                        project.dol.seek(lfs_instruction_address)
                        dolreader.write_uint32(project.dol, lfs_instruction)

                with open('symbols.txt', 'w', encoding='ascii') as f:
                    f.write(SYMBOLS_MAP[game_id])
                project.add_linker_file('symbols.txt')

                with open('lib.c', 'w', encoding='ascii') as f:
                    f.write(code)

                project.add_file('lib.c')

                # Page selection logic.
                if page_count > 1:
                    project.branchlink(SCENECOURSESELECT_CALCANM_CALL_ADDRESSES[game_id],
                                       'scenecourseselect_calcanm_ex')
                    if battle_stages_enabled:
                        project.branchlink(SCENEMAPSELECT_CALCANM_CALL_ADDRESSES[game_id],
                                           'scenemapselect_calcanm_ex')
                    if battle_stages_enabled or tilting_courses:
                        project.branchlink(IS_TILTING_COURSE_CALL_ADDRESSES[game_id],
                                           'is_tilting_course')
                        project.dol.seek(IS_TILTING_COURSE_CALL_ADDRESSES[game_id] + 4)
                        project.dol.write(struct.pack('>I', 0x2C030001))  # cmpwi r3, 0x1
                    project.branchlink(LANSELECTMODE_CALCANM_CALL_ADDRESSES[game_id],
                                       'lanselectmode_calcanm_ex')
                    if args.reset_course_page_on_lan_initialization:
                        project.branchlink(LANPLAYINFO_INIT_CALL_ADDRESSES[game_id],
                                           'lanplayinfo_init_ex')
                    if pass_number == 1:
                        if args.reset_course_page_on_title_screen:
                            project.dol.seek(SCENETITLE_INIT_VTABLE_INDEX_ADDRESSES[game_id])
                            doltools.write_uint32(project.dol, scenetitle_init_ex_address)

                if remove_movie_trailer:
                    project.dol.seek(SKIP_MOVIE_TRAILER_INSTRUCTIONS_ADDRESSES[game_id][0])
                    doltools.write_li(project.dol, 0, 3)
                    project.dol.seek(SKIP_MOVIE_TRAILER_INSTRUCTIONS_ADDRESSES[game_id][1])
                    doltools.write_nop(project.dol)
                    project.dol.seek(SKIP_MOVIE_TRAILER_INSTRUCTIONS_ADDRESSES[game_id][2])
                    doltools.write_li(project.dol, 0, 1)
                    if game_id == 'GM4E01dbg':
                        for address in SKIP_MOVIE_TRAILER_INSTRUCTIONS_ADDRESSES[game_id][3]:
                            project.dol.seek(address)
                            dolreader.write_uint32(project.dol, 0x48000038)  # b +14

                # Code extensions.
                if extender_cup:
                    project.dol.seek(GP_TOTAL_COURSE_COUNT_INSTRUCTION_ADDRESSES[game_id])
                    doltools.write_li(project.dol, 24, page_count * 16)
                    project.branchlink(ON_GP_ABOUT_TO_START_INSERTION_ADDRESSES[game_id],
                                       'on_gp_about_to_start')
                    project.branchlink(GET_GP_COURSE_INDEX_INSERTION_ADDRESSES[game_id],
                                       'get_gp_course_index')
                    project.branchlink(SEQUENCEINFO_SETCLRGPCOURSE_CALL_ADDRESSES[game_id],
                                       'sequenceinfo_setclrgpcourse_ex')

                    if pass_number == 1:
                        project.dol.seek(CUP_FILENAMES_ARRAY_INSTRUCTION_ADDRESSES[game_id])
                        doltools.write_lis(project.dol,
                                           3,
                                           extender_cup_cup_filenames_address >> 16,
                                           signed=False)
                        project.dol.seek(CUP_FILENAMES_ARRAY_INSTRUCTION_ADDRESSES[game_id] + 8)
                        doltools.write_ori(project.dol, 3, 28,
                                           extender_cup_cup_filenames_address & 0x0000FFFF)

                        for address in PREVIEW_FILENAMES_ARRAY_INSTRUCTIONS_ADDRESSES[game_id]:
                            project.dol.seek(address)
                            doltools.write_lis(project.dol,
                                               4,
                                               extender_cup_preview_filename_address >> 16,
                                               signed=False)
                            project.dol.seek(address + 0x04)
                            doltools.write_ori(project.dol, 4, 4,
                                               extender_cup_preview_filename_address & 0x0000FFFF)

                if type_specific_item_boxes:
                    project.branchlink(ITEMOBJMGR_ISAVAILABLEROLLINGSLOT_CALL_ADDRESSES[game_id],
                                       'itemobjmgr_isavailablerollingslot_ex')
                    project.branchlink(ITEMSHUFFLEMGR_CALCSLOT_CALL_ADDRESSES[game_id],
                                       'itemshufflemgr_calcslot_ex')

                if customizable_falling_stars:
                    project.branchlink(CFS_ITEMOBJMGR_OCCURITEM_CALL_ADDRESSES[game_id],
                                       'cfs_itemobjmgr_occuritem_ex')

                    project.dol.seek(CFS_GEOGRAPHYOBJ_GETGEORND_CALL_ADDRESSES[game_id] - 4)
                    doltools.write_nop(project.dol)  # Allow falling stars to drop items in TT mode.
                    project.dol.seek(CFS_GEOGRAPHYOBJ_GETGEORND_CALL_ADDRESSES[game_id])
                    doltools.write_uint32(project.dol, 0x7FE3FB78)  # or r3, r31, r31
                    project.branchlink(CFS_GEOGRAPHYOBJ_GETGEORND_CALL_ADDRESSES[game_id] + 0x04,
                                       'cfs_should_drop_item')
                    for i in range(2, 17):
                        project.dol.seek(CFS_GEOGRAPHYOBJ_GETGEORND_CALL_ADDRESSES[game_id] +
                                         0x04 * i)
                        doltools.write_nop(project.dol)
                    project.dol.seek(CFS_GEOGRAPHYOBJ_GETGEORND_CALL_ADDRESSES[game_id] + 0x04 * 17)
                    doltools.write_uint32(project.dol, 0x2C030001)  # cmpwi r3, 0x1

                    for address in CFS_JPEFFECTMGR_CREATEEMT_CALLS_ADDRESSES[game_id]:
                        project.branchlink(address, 'cfs_jpeffectmgr_createemt_ex')
                    if game_id == 'GM4E01dbg':
                        project.dol.seek(0x802CA42C)
                        doltools.write_li(project.dol, 0, 1)  # Neutralize assertion.

                    for address in CFS_KARTGAME_ITEMWATCHMAN_CALLS_ADDRESSES[game_id]:
                        project.branchlink(address, 'cfs_kartgame_itemwatchman_ex')

                if sectioned_courses:
                    project.branchlink(RESET_SECTION_COUNT_CALL_ADDRESSES[game_id],
                                       'reset_section_count')
                    project.branchlink(COUNT_SECTION_POINT_CALL_ADDRESSES[game_id],
                                       'count_section_point')
                    project.branchlink(OVERRIDE_TOTAL_LAP_COUNT_CALL_ADDRESSES[game_id],
                                       'override_total_lap_count')
                    project.branchlink(CHECK_LAP_EX_CALL_ADDRESSES[game_id], 'check_lap_ex')

                if bouncy_terrain_type:
                    project.branchlink(DO_SPD_CTRL_CALL_HIJACK_ADDRESSES[game_id],
                                       'do_spd_ctrl_call_hijack')
                    project.branchlink(GET_SPLASH_HEIGHT_INLINE_ADDRESSES[game_id],
                                       'get_splash_code_inline')
                    project.branchlink(GET_SPLASH_ID_INLINE_ADDRESSES[game_id],
                                       'get_splash_code_inline')
                    project.branchlink(IS_ITEM_INVAL_GROUND_HIJACK_ADDRESSES[game_id],
                                       'is_item_inval_ground_hijack')
                    project.branchlink(GET_ADD_THICKNESS_INLINE_ADDRESSES[game_id],
                                       'get_add_thickness_inline')
                    project.branchlink(GET_STAGGER_CODE_HIJACK_AIR_CHECK_ADDRESSES[game_id],
                                       'get_stagger_code_hijack')
                    project.branchlink(GET_STAGGER_CODE_HIJACK_DANGER_LOOP_ADDRESSES[game_id],
                                       'get_stagger_code_hijack')

                project.build('main.dol' if pass_number == 0 else dol_path)

                # Further symbol post-processing once the map is available.
                if pass_number == 0:
                    if extender_cup or args.reset_course_page_on_title_screen:
                        with open('project.map', 'r', encoding='ascii') as f:
                            for line in f:
                                if 'g_extender_cup_cup_filenames' in line:
                                    extender_cup_cup_filenames_address = int(line.split()[0],
                                                                             base=16)
                                elif 'g_extender_cup_preview_filenames' in line:
                                    extender_cup_preview_filename_address = int(line.split()[0],
                                                                                base=16)
                                elif 'scenetitle_init_ex' in line:
                                    scenetitle_init_ex_address = int(line.split()[0], base=16)
                    if extender_cup:
                        assert extender_cup_cup_filenames_address is not None
                        assert extender_cup_preview_filename_address is not None
                    if args.reset_course_page_on_title_screen:
                        assert scenetitle_init_ex_address is not None

                # Diagnosis logging only if enabled on the user end.
                if pass_number == 1 and debug_output:
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

    if initial_page_index > 0:
        # Audio track indexes need to be adjusted for the selected initial page. This is done by
        # rewriting the BSFT file where each course's audio ID is mapped to a file in the `Stream`
        # directory. This makes the game load the audio indexes of the selected initial page.

        files_dirpath = os.path.join(iso_tmp_dir, 'files')
        baa_filepath = os.path.join(files_dirpath, 'AudioRes', 'GCKart.baa')

        with tempfile.TemporaryDirectory(prefix=mkdd_extender.TEMP_DIR_PREFIX) as tmp_dir:
            baa.unpack_baa(baa_filepath, tmp_dir)

            for name in os.listdir(tmp_dir):
                if name.endswith('.bsft'):
                    bsft_filepath = os.path.join(tmp_dir, name)
                    break
            else:
                raise RuntimeError('Unable to locate BSFT file in GCKart.baa.')

            paths = [path for _offset, path in baa.read_bsft(bsft_filepath)]

            audio_indexes = audio_track_data[initial_page_index]
            file_list = mkdd_extender.build_file_list(iso_tmp_dir)
            for i, audio_index in enumerate(audio_indexes):
                paths[i] = file_list[audio_index].lstrip('files/')

            baa.write_bsft(paths, bsft_filepath)

            # Although the standalone GCKart.bsft file (next to the GCKart.baa file) is not accessed
            # in the game, it will be updated too for correctness.
            standalone_bsft_filepath = os.path.join(f'{os.path.splitext(baa_filepath)[0]}.bsft')
            shutil.copy2(bsft_filepath, standalone_bsft_filepath)

            baa.pack_baa(tmp_dir, baa_filepath)

    log.info(f'Injected {injected_code_size} bytes of new code. '
             f'OS Arena: 0x{aligned(unaligned_previous_osarena_value):08X} (previous) -> '
             f'0x{aligned(unaligned_new_osarena_value):08X} (new).')
