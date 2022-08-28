#!/usr/bin/env python3
"""
Module that includes functions for extracting and packing RARC files.

Details of the RARC format:
- https://kuribo64.net/wiki/?page=RARC
- https://wiki.tockdom.com/wiki/RARC_(File_Format)
- https://mk8.tockdom.com/wiki/SARC_(File_Format) (related)

When executed as a command-line tool, two paths need to be provided: one for the input file or input
directory, and one for the output directory or output file.

If the input path is a file, an extraction operation will be assumed. If the input path is a
directory, a packing operation will be assumed.
"""
import argparse
import os
import platform
import struct
import logging

log = logging.getLogger(__name__)

__MAGIC = b'RARC'

__HEADER_SIZE = 0x20
__INFO_BLOCK_SIZE = 0x20
__NODE_SIZE = 0x10
__ENTRY_SIZE = 0x14
__ID_SIZE = 0x04

__FILE_FORMAT_VERSION = 0x0100

__FILE_TYPE = 0x1100
__DIR_TYPE = 0x0200

__ALIGNMENT = 0x20

windows = platform.system() == 'Windows'


def __hash_string(text: bytes) -> int:
    h = 0
    for c in text:
        h *= 3
        h += c
    h = h & 0x0000FFFF
    return h


if windows:

    def __cleanup_name(name: bytes) -> bytes:
        INVALID_CHARS = b'<>:"\\|?*'
        for char in INVALID_CHARS:
            name = name.replace(bytes((char, )), b'_')
        return name
else:

    def __cleanup_name(name: bytes) -> bytes:
        return name


def extract(src_filepath: str, dst_dirpath: str):
    # Read all file into nearby memory.
    with open(src_filepath, 'rb') as f:
        data = memoryview(f.read())

    # Parse header.
    magic = data[:len(__MAGIC)]
    assert magic == __MAGIC

    (
        file_size,
        header_size,
        entry_data_section_offset,
        entry_data_section_size,
        entry_data_section_size2,
        padding,
    ) = struct.unpack('>LLLLLQ', data[len(__MAGIC):__HEADER_SIZE])

    assert file_size == len(data)
    assert header_size == __HEADER_SIZE
    assert entry_data_section_size == entry_data_section_size2
    assert padding == 0x0000000000000000

    # Parse info block.
    (
        node_count,
        node_section_offset,
        entry_count,
        entry_section_offset,
        string_table_size,
        string_table_offset,
        file_count,
        file_format_version,
        padding,
    ) = struct.unpack('>LLLLLLHHL', data[__HEADER_SIZE:__HEADER_SIZE + __INFO_BLOCK_SIZE])

    assert node_count
    if file_count != entry_count:
        # NOTE: They seem to always match, but docs suggest otherwise, and some RARC archives in the
        # wild report file count as 0, which doesn't really make much sense.
        log.warning(f'File count in header ({file_count}) and entry count in header '
                    f'({entry_count}) do not match.')
    if file_format_version != __FILE_FORMAT_VERSION:
        log.warning(f'Expected format version {__FILE_FORMAT_VERSION}, but encountered '
                    f'{file_format_version}.')
    assert padding == 0x00000000

    # Make offsets relative to the start of the RARC file.
    entry_data_section_offset += __HEADER_SIZE
    node_section_offset += __HEADER_SIZE
    entry_section_offset += __HEADER_SIZE
    string_table_offset += __HEADER_SIZE

    assert entry_data_section_offset % __ALIGNMENT == 0
    assert node_section_offset % __ALIGNMENT == 0
    assert entry_section_offset % __ALIGNMENT == 0
    assert string_table_offset % __ALIGNMENT == 0
    assert entry_data_section_size % __ALIGNMENT == 0
    if string_table_size % __ALIGNMENT != 0:
        # NOTE: Again, there is a tool out there that fails to pad the string table. Instead of
        # raising an assertion error, a warning will be reported.
        log.warning(f'String table\'s size ({string_table_size} bytes) is not a multiple of '
                    f'{__ALIGNMENT}; it should have been padded.')

    entry_data_section = data[entry_data_section_offset:entry_data_section_offset +
                              entry_data_section_size]
    string_table = data[string_table_offset:string_table_offset + string_table_size]

    def get_string(string_offset: int) -> bytes:
        for i in range(string_offset, string_table_size):
            if string_table[i] == 0:
                return bytes(string_table[string_offset:i])
        raise RuntimeError(f'String at offset {string_offset} not found.')

    # In the RARC files seen in Mario Kart: Double Dash!!, these two strings always appear first.
    assert get_string(0) == b'.'
    assert get_string(2) == b'..'

    # Parse nodes.
    nodes = []
    for i in range(node_count):
        node_offset = node_section_offset + i * __NODE_SIZE
        identifier = data[node_offset:node_offset + __ID_SIZE]
        (
            string_offset,
            string_hash,
            child_count,
            first_child_index,
        ) = struct.unpack('>LHHL', data[node_offset + __ID_SIZE:node_offset + __NODE_SIZE])

        name = get_string(string_offset)

        # NOTE: There is a tool out there that sets wrong string offsets for the node names. It
        # seems, however, that this is not fatal, and the node name may be corrected in the entry
        # section. A warning will be printed.
        calculated_hash = __hash_string(name)
        if calculated_hash != string_hash:
            log.warning(f'Hash for "{name.decode("ascii")}" is 0x{calculated_hash:02X}, but hash '
                        f'in header is 0x{string_hash:02X}.')

        name = __cleanup_name(name)

        if i == 0:
            if identifier != b'ROOT':
                str_identifier = bytes(identifier).decode("ascii")
                log.warning('Identifier in root directory should be "ROOT", but is '
                            f'"{str_identifier}".')
        else:
            calculated_identifier = name.upper()[0:4].ljust(4)
            if calculated_identifier != identifier:
                str_identifier = bytes(identifier).decode("ascii")
                str_calculated_identifier = calculated_identifier.decode("ascii")
                str_name = name.decode("ascii")
                log.warning(f'Identifier in header ("{str_identifier}") does not match first four '
                            f'bytes ("{str_calculated_identifier}") of the name ("{str_name}").')

        nodes.append((name, child_count, first_child_index))

    # Parse entries.
    entries = []
    for i in range(entry_count):
        entry_offset = entry_section_offset + i * __ENTRY_SIZE

        (
            entry_index,
            string_hash,
            entry_type,
            string_offset,
            entry_data_offset,
            entry_data_size,
            padding,
        ) = struct.unpack('>HHHHLLL', data[entry_offset:entry_offset + __ENTRY_SIZE])

        assert entry_type in (__FILE_TYPE, __DIR_TYPE)

        if __debug__:
            if entry_type == __FILE_TYPE:
                if entry_index != i:
                    # NOTE: It seems some RARC archives in the wild set the index in the header
                    # wrong, but ignoring this issue doesn't cause problems, meaning that apending
                    # this entry in the `entries` directory at index i is correct.
                    log.warning(f'Entry index in header is {entry_index}, but {i} was expected. '
                                f'Entry index in header will be ignored; {i} will be used.')
                assert entry_data_offset % __ALIGNMENT == 0
                assert entry_data_offset + entry_data_size <= entry_data_section_size
            else:
                assert entry_index == 0xFFFF
                assert entry_data_size == __NODE_SIZE

        name = get_string(string_offset)
        assert __hash_string(name) == string_hash

        name = __cleanup_name(name)

        assert padding == 0x00000000

        if __debug__:
            if name in (b'.', b'..'):
                assert entry_type == __DIR_TYPE

        if entry_type == __FILE_TYPE:
            entry_data = entry_data_section[entry_data_offset:entry_data_offset + entry_data_size]
            entries.append((entry_type, name, entry_data))
        else:
            node_index = entry_data_offset
            assert node_index == 0xFFFFFFFF or 0 <= node_index < len(nodes)

            if node_index != 0xFFFFFFFF:
                if name in (b'.', b'..'):
                    pass
                elif name != nodes[node_index][0]:
                    str_name_node_section = nodes[node_index][0].decode('ascii')
                    str_name_entry_section = name.decode('ascii')
                    log.warning(f'Node name from node section ("{str_name_node_section}") does '
                                'not match node name in the entry section '
                                f'("{str_name_entry_section}"). It will be updated.')
                    node = list(nodes[node_index])
                    node[0] = name
                    nodes[node_index] = tuple(node)

            entries.append((entry_type, name, node_index))

    # Iteratively create directories and their files (breadth-first search).
    pending_nodes = [(nodes[0], dst_dirpath)]
    visited_nodes = set()
    while pending_nodes:
        node, parent_dirpath = pending_nodes.pop(0)
        visited_nodes.add(node)

        dirname, child_count, first_child_index = node

        current_dirpath = os.path.join(parent_dirpath, dirname.decode('ascii'))
        os.makedirs(current_dirpath, exist_ok=True)

        for entry in entries[first_child_index:first_child_index + child_count]:
            entry_type, *args = entry

            if entry_type == __FILE_TYPE:
                filename, entry_data = args

                with open(os.path.join(current_dirpath, filename.decode('ascii')), 'wb') as f:
                    f.write(entry_data)
            else:
                dirname, node_index = args

                if node_index != 0xFFFFFFFF:
                    node = nodes[node_index]
                    if __debug__:
                        if dirname not in (b'.', b'..'):
                            assert dirname == node[0]
                    if node not in visited_nodes:
                        pending_nodes.append((node, current_dirpath))


def pack(src_dirpath: str, dst_filepath: str):
    if not os.path.isdir(src_dirpath):
        raise ValueError(f'"{src_dirpath}" is not a valid directory.')

    src_dirpath = os.path.normpath(src_dirpath)  # Trailing slashes not wanted.

    nodes = []
    nodes_indices = {}
    entries = []

    string_table_size = 0
    string_offsets = {}
    string_list = []

    entry_data_section_size = 0
    entry_data_sizes = []

    def register_string(text: str) -> int:
        nonlocal string_table_size
        string_offset = string_offsets.get(text)
        if string_offset is None:
            string_offset = string_table_size
            string_offsets[text] = string_offset
            string_table_size += len(text) + 1
            string_list.append(text.encode('ascii'))
            assert len(text) == len(string_list[-1])
        return string_offset

    # In the RARC files seen in Mario Kart: Double Dash!!, these two strings always appear first in
    # the string table, although they are in fact appended to the directory list.
    register_string('.')
    register_string('..')

    def aligned(value: int) -> int:
        return (value | __ALIGNMENT - 1) + 1 if value % __ALIGNMENT else value

    for parentpath, dirnames, filenames in os.walk(src_dirpath):
        # In the known RARC files, files come before directories. However, the order in the known
        # samples is arbitrary. A sorted list is better than a *different* arbitrary order.
        # Besides the arbitrary order, it seems known RARC files process files in directories in
        # a depth-first search, while we are doing breadth-first search.
        dirnames.sort()
        filenames = sorted(filenames)
        dirnames = dirnames + ['.', '..']

        parentname = os.path.basename(parentpath)
        string_offset = register_string(parentname)
        string_hash = __hash_string(parentname.encode('ascii'))
        child_count = len(filenames) + len(dirnames)
        first_child_index = len(entries)

        node_index = len(nodes)
        nodes.append((parentpath, string_offset, string_hash, child_count, first_child_index))
        nodes_indices[parentpath] = node_index

        for filename in filenames:
            filepath = os.path.join(parentpath, filename)
            string_offset = register_string(filename)
            string_hash = __hash_string(filename.encode('ascii'))
            entry_data_size = os.path.getsize(filepath)
            entry_data_offset = entry_data_section_size
            entry_data_section_size = aligned(entry_data_section_size + entry_data_size)
            entry_data_sizes.append(entry_data_size)
            entries.append((__FILE_TYPE, filepath, string_offset, string_hash, entry_data_size,
                            entry_data_offset))

        for dirname in dirnames:
            dirpath = os.path.join(parentpath, dirname)
            string_offset = register_string(dirname)
            string_hash = __hash_string(dirname.encode('ascii'))
            entries.append((__DIR_TYPE, dirpath, string_offset, string_hash))

    string_table_size = aligned(string_table_size)

    node_section_offset = aligned(__HEADER_SIZE + __INFO_BLOCK_SIZE)
    entry_section_offset = aligned(node_section_offset + len(nodes) * __NODE_SIZE)
    string_table_offset = aligned(entry_section_offset + len(entries) * __ENTRY_SIZE)
    entry_data_section_offset = aligned(string_table_offset + string_table_size)

    assert entry_data_section_offset % __ALIGNMENT == 0
    assert node_section_offset % __ALIGNMENT == 0
    assert entry_section_offset % __ALIGNMENT == 0
    assert string_table_offset % __ALIGNMENT == 0
    assert entry_data_section_size % __ALIGNMENT == 0
    assert string_table_size % __ALIGNMENT == 0

    file_size = entry_data_section_offset + entry_data_section_size
    header_size = __HEADER_SIZE

    node_count = len(nodes)
    entry_count = len(entries)
    file_count = entry_count

    if os.path.splitdrive(os.path.dirname(dst_filepath))[1]:
        os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

    with open(dst_filepath, 'wb') as f:
        f.write(__MAGIC)

        f.write(
            struct.pack(
                '>LLLLLQ',
                file_size,
                header_size,
                entry_data_section_offset - __HEADER_SIZE,
                entry_data_section_size,
                entry_data_section_size,
                0x0000000000000000,
            ))

        f.write(
            struct.pack(
                '>LLLLLLHHL',
                node_count,
                node_section_offset - __HEADER_SIZE,
                entry_count,
                entry_section_offset - __HEADER_SIZE,
                string_table_size,
                string_table_offset - __HEADER_SIZE,
                file_count,
                __FILE_FORMAT_VERSION,
                0x00000000,
            ))

        dirpath_indices = {}

        for i, (dirpath, string_offset, string_hash, child_count,
                first_child_index) in enumerate(nodes):
            if i == 0:
                identifier = b'ROOT'
            else:
                dirname = os.path.basename(dirpath).encode('ascii')
                identifier = dirname[:__ID_SIZE].upper().ljust(__ID_SIZE)

            f.write(identifier)
            f.write(
                struct.pack(
                    '>LHHL',
                    string_offset,
                    string_hash,
                    child_count,
                    first_child_index,
                ))

            dirpath_indices[dirpath] = i

        f.write(b'\x00' * (entry_section_offset - f.tell()))

        for i, (entry_type, *args) in enumerate(entries):
            if entry_type == __FILE_TYPE:
                entry_index = i
                _filepath, string_offset, string_hash, entry_data_size, entry_data_offset = args

                f.write(
                    struct.pack(
                        '>HHHHLLL',
                        entry_index,
                        string_hash,
                        entry_type,
                        string_offset,
                        entry_data_offset,
                        entry_data_size,
                        0x00000000,
                    ))
            else:
                dirpath, string_offset, string_hash = args

                # Resolve relative paths (`.` and `..``), and check if the directory has been keyed.
                node_index = dirpath_indices.get(os.path.normpath(dirpath), 0xFFFFFFFF)

                f.write(
                    struct.pack(
                        '>HHHHLLL',
                        0xFFFF,
                        string_hash,
                        entry_type,
                        string_offset,
                        node_index,
                        __NODE_SIZE,
                        0x00000000,
                    ))

        f.write(b'\x00' * (string_table_offset - f.tell()))

        for text in string_list:
            f.write(text + b'\x00')

        f.write(b'\x00' * (entry_data_section_offset - f.tell()))

        for i, (entry_type, *args) in enumerate(entries):
            if entry_type != __FILE_TYPE:
                continue
            filepath, _string_offset, _string_hash, entry_data_size, entry_data_offset = args

            with open(filepath, 'rb') as g:
                f.write(g.read())

            f.write(b'\x00' * (aligned(entry_data_size) - entry_data_size))


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                        level=logging.INFO,
                        datefmt='%Y-%m-%d %H:%M:%S')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',
                        type=str,
                        help='Path to the file or directory that is to be extracted or packed.')
    parser.add_argument('output',
                        type=str,
                        help='Path to the file or directory that is to be written.')
    args = parser.parse_args()

    if os.path.isfile(args.input):
        extract(args.input, args.output)

    elif os.path.isdir(args.input):
        pack(args.input, args.output)

    else:
        raise ValueError(f'Input path ("{args.input}") cannot be extracted or packed because it is '
                         'not a valid file or directory.')


if __name__ == '__main__':
    main()
