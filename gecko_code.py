"""
Script that generates data-driven Gecko codes for extending the stock number of courses in
Mario Kart: Double Dash!!.
"""

import os

BUTTONS_STATE_ADDRESSES = {
    'GM4E01': 0x003A4D6C,
    'GM4P01': 0x003AEB8C,
    'GM4J01': 0x003BF38C,
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

    for file_string in FILE_STRINGS:
        address = data.find(file_string.encode('ascii'))
        assert address > 0
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
    }
}

for _game_id, addresses in STRING_ADDRESSES.items():
    for string in addresses:
        assert string in DIR_STRINGS + FILE_STRINGS

for string in DIR_STRINGS + FILE_STRINGS:
    for _game_id, addresses in STRING_ADDRESSES.items():
        assert string in addresses


def encode_address(code_type: str, code_address: int) -> int:
    """
    http://wiigeckocodes.github.io/codetypedocumentation.html
    """
    if code_type == 'write8':
        return code_address
    if code_type == 'write32':
        return 0x04000000 | code_address
    if code_type == 'if16':
        return 0x28000000 | code_address
    if code_type == 'terminator':
        return 0xE0000000


def get_line(encoded_address: int, value: int) -> str:
    return f'{encoded_address:08X} {value:08X}'


def write_code(game_id: str, filepath: str):

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

            last_char = file_string[offset]
            last_char_value = last_char.encode('ascii')[0]
            file_string_address_line = get_line(encoded_file_string_address, last_char_value)

            lines_for_deactivator.append(file_string_address_line)

    # Redraw course selection screen code.
    redraw_courseselect_address = REDRAW_COURSESELECT_SCREEN_ADDRESSES[game_id]
    encoded_redraw_courseselect_address = encode_address('write32', redraw_courseselect_address)
    redraw_courseselect_address_activator_line = get_line(encoded_redraw_courseselect_address,
                                                          0x41200000)  # 10.0f

    # The screen needs to be redrawn when activated or deactivated.
    for page_index in range(3):
        lines_for_activator[page_index].append(redraw_courseselect_address_activator_line)
    lines_for_deactivator.append(redraw_courseselect_address_activator_line)

    # The value is reinstated when only the Z button is held.
    redraw_courseselect_deactivator_line = get_line(encoded_buttons_state_address, BUTTON_Z)
    redraw_courseselect_address_deactivator_line = get_line(encoded_redraw_courseselect_address,
                                                            0x41500000)  # 13.0f

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='ascii') as f:
        f.write('$Page Selector [mkdd-extender]')
        f.write('\n')
        for page_index in range(3):
            f.write(activator_lines[page_index])
            f.write('\n')
            for line in lines_for_activator[page_index]:
                f.write(line)
                f.write('\n')
            f.write(full_terminator_line)
            f.write('\n')
            f.write('\n')

        f.write(deactivator_line)
        f.write('\n')
        for line in lines_for_deactivator:
            f.write(line)
            f.write('\n')
        f.write(full_terminator_line)
        f.write('\n')
        f.write('\n')

        f.write(redraw_courseselect_deactivator_line)
        f.write('\n')
        f.write(redraw_courseselect_address_deactivator_line)
        f.write('\n')
        f.write(full_terminator_line)
        f.write('\n')
