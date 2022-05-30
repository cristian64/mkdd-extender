#!/usr/bin/env python3
"""
Module that includes functions for converting AST files to and from WAV files.

Details of the AST format:
- https://wiki.tockdom.com/wiki/AST_(File_Format)
- https://wiibrew.org/wiki/AST_file

When executed as a command-line tool, two paths need to be provided. Conversion will be based on the
extensions of the paths.
"""
import argparse
import logging
import os
import struct
import wave

log = logging.getLogger('ast')

try:
    import numpy
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

_MAGIC = struct.unpack('>L', b'STRM')[0]
_HEADER_SIZE = 0x40
_PCM_FORMAT = 0x0001
_BLOCK_SIZE = 10080
_BLOCK_MAGIC = struct.unpack('>L', b'BLCK')[0]
_BLOCK_HEADER_SIZE = 0x20
_ALIGNMENT = 0x20


def get_ast_info(filepath: str) -> 'dict[str, int]':
    filesize = os.path.getsize(filepath)

    with open(filepath, 'rb') as f:
        data = f.read(_HEADER_SIZE)

        (
            magic_bytes,
            block_data_size,
            audio_format,
            bit_depth,
            channel_count,
            looped,
            sample_rate,
            sample_count,
            loop_start,
            loop_end,
            block_size,
            padding0,
            volume,
            padding1,
            padding2,
            padding3,
            padding4,
            padding5,
        ) = struct.unpack('>LLHHHHLLLLLLbBHLQQ', data)

        # A number of notes after studying all the stock files present in Mario Kart: Double Dash!!,
        # Super Mario Galaxy, and Super Mario Galaxy 2:
        #
        # - Audio format is always 0x0001 (PCM, presumably).
        # - Bit depth is always 16.
        # - Channel count is always 2 or 4.
        # - The looped value is set to 0xFFFF to make the audio loop after reaching the loop-end
        #   sample. If the value is 0x0000, the audio ends instead. (In fact, any value that is not
        #   0x0000 makes the audio loop indefinitely, at least in Mario Kart: Double Dash!!)
        # - Sample rate is always 32000.
        # - Loop end always matches sample count.
        # - Block size is always 10080 (except the last block, that is only the remainder).
        # - Volume is usually 127, and in a few rare cases, 100.

        assert magic_bytes == _MAGIC
        assert filesize == _HEADER_SIZE + block_data_size
        assert audio_format == _PCM_FORMAT
        assert bit_depth in (8, 16, 32)
        assert looped in (0x0000, 0xFFFF)
        assert loop_start < sample_count
        assert loop_start < loop_end
        assert loop_end == sample_count
        assert block_size == _BLOCK_SIZE
        assert not (padding0 or padding1 or padding2 or padding3 or padding4 or padding5)

        block_offset = last_block_offset = _HEADER_SIZE
        while block_offset < filesize:
            last_block_offset = block_offset
            block_offset += _BLOCK_HEADER_SIZE + block_size * channel_count

        f.seek(last_block_offset)
        data = f.read(_BLOCK_HEADER_SIZE)

    (
        block_magic_bytes,
        last_block_size,
        padding0,
        padding1,
        padding2,
    ) = struct.unpack('>LLQQQ', data)

    assert block_magic_bytes == _BLOCK_MAGIC
    assert last_block_size <= block_size
    assert not (padding0 or padding1 or padding2)

    last_block_real_size = (filesize - last_block_offset - _BLOCK_HEADER_SIZE) // channel_count

    # As mentioned in another inline comment below, for unknown reasons, some stock audio files have
    # fewer bytes than expected in the last block. Having more bytes (padding?) would be reasonable,
    # but having less data is utterly odd... Instead of ==, <= is used in this check.
    assert last_block_real_size <= last_block_size

    return {
        'block_data_size': block_data_size,
        'bit_depth': bit_depth,
        'channel_count': channel_count,
        'looped': looped,
        'sample_rate': sample_rate,
        'sample_count': sample_count,
        'loop_start': loop_start,
        'loop_end': loop_end,
        'block_size': block_size,
        'volume': volume,
        'last_block_size': last_block_size,
        'last_block_real_size': last_block_real_size,
    }


def _print_mapping(mapping: 'dict[str, int]'):
    max_label_length = max(len(entry) + 1 for entry in mapping)
    for entry, value in mapping.items():
        label = entry.title().replace('_', ' ') + ':'
        print(f'{label: <{max_label_length}} {value}')


def _swap_bytes_naive(data: bytearray, bit_depth: int):
    if bit_depth == 8:
        return

    if bit_depth == 16:
        for offset in range(0, len(data), 2):
            data[offset], data[offset + 1] = data[offset + 1], data[offset]

    elif bit_depth == 32:
        for offset in range(0, len(data), 4):
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3] = \
                data[offset + 3], data[offset + 2], data[offset + 1], data[offset]

    else:
        raise ValueError(f'Unsupported bit depth: {bit_depth}')


def _swap_bytes_numpy(data: bytearray, bit_depth: int):
    if bit_depth == 8:
        return

    if bit_depth == 16:
        dtype = numpy.int16
    elif bit_depth == 32:
        dtype = numpy.int32
    else:
        raise ValueError(f'Unsupported bit depth: {bit_depth}')

    array = numpy.frombuffer(data, dtype=dtype)
    array.byteswap(inplace=True)
    data[:] = array.tobytes()


def _interleave_channels_naive(data: memoryview, channel_count: int, bit_depth: int) -> bytearray:
    result_data = bytearray()

    bytes_per_channel = len(data) // channel_count
    bytes_per_sample = bit_depth // 8

    channel_chunks = []
    for channel in range(channel_count):
        channel_chunks.append(data[channel * bytes_per_channel:(channel + 1) * bytes_per_channel])

    for sample_offset in range(0, bytes_per_channel, bytes_per_sample):
        for channel_chunk in channel_chunks:
            result_data.extend(channel_chunk[sample_offset:sample_offset + bytes_per_sample])

    return result_data


def _interleave_channels_numpy(data: memoryview, channel_count: int, bit_depth: int) -> bytearray:
    if bit_depth == 8:
        dtype = numpy.uint8
    elif bit_depth == 16:
        dtype = numpy.int16
    elif bit_depth == 32:
        dtype = numpy.int32
    else:
        raise ValueError(f'Unsupported bit depth: {bit_depth}')

    bytes_per_channel = len(data) // channel_count

    arrays = []
    for i in range(channel_count):
        array = numpy.frombuffer(data[i * bytes_per_channel:(i + 1) * bytes_per_channel],
                                 dtype=dtype)
        arrays.append(array)

    placeholder = numpy.empty(sum(a.size for a in arrays), dtype=dtype)
    for i, a in enumerate(arrays):
        placeholder[i::channel_count] = a

    return bytearray(placeholder.tobytes())


def _deinterleave_channels_naive(data: memoryview, channel_count: int,
                                 bit_depth: int) -> 'tuple[memoryview]':
    result_data = tuple(bytearray() for _ in range(channel_count))

    bytes_per_sample = bit_depth // 8

    channel_idx = 0
    for sample_offset in range(0, len(data), bytes_per_sample):
        result_data[channel_idx].extend(data[sample_offset:sample_offset + bytes_per_sample])
        channel_idx = (channel_idx + 1) % channel_count

    return tuple(map(memoryview, result_data))


def _deinterleave_channels_numpy(data: memoryview, channel_count: int,
                                 bit_depth: int) -> 'tuple[memoryview]':
    if bit_depth == 8:
        dtype = numpy.uint8
    elif bit_depth == 16:
        dtype = numpy.int16
    elif bit_depth == 32:
        dtype = numpy.int32
    else:
        raise ValueError(f'Unsupported bit depth: {bit_depth}')

    array = numpy.frombuffer(data, dtype=dtype)

    # A copy of the slice is made to ensure it is in contiguous memory; then a view of the array
    # (as unsigned chars) is created, which can then be wrapped up with a `memoryview` object.
    # Note that the reason for not converting the slice to bytes (via `numpy.ndarray.tobytes()`) is
    # that it performs poorly.
    return tuple(
        memoryview(array[i::channel_count].copy().view(dtype=numpy.uint8))
        for i in range(channel_count))


if _NUMPY_AVAILABLE:
    _swap_bytes = _swap_bytes_numpy
    _interleave_channels = _interleave_channels_numpy
    _deinterleave_channels = _deinterleave_channels_numpy
else:
    _swap_bytes = _swap_bytes_naive
    _interleave_channels = _interleave_channels_naive
    _deinterleave_channels = _deinterleave_channels_naive


def convert_to_wav(src_filepath: str, dst_filepath: str):
    filesize = os.path.getsize(src_filepath)

    with open(src_filepath, 'rb') as f:
        data = memoryview(f.read())

    (
        magic_bytes,
        block_data_size,
        audio_format,
        bit_depth,
        channel_count,
        looped,
        sample_rate,
        sample_count,
        loop_start,
        loop_end,
        block_size,
        padding0,
        _volume,
        padding1,
        padding2,
        padding3,
        padding4,
        padding5,
    ) = struct.unpack('>LLHHHHLLLLLLbBHLQQ', data[:_HEADER_SIZE])

    assert magic_bytes == _MAGIC
    assert filesize == _HEADER_SIZE + block_data_size
    assert audio_format == _PCM_FORMAT
    assert bit_depth in (8, 16, 32)
    assert looped in (0x0000, 0xFFFF)
    assert loop_start < sample_count
    assert loop_start < loop_end
    assert loop_end == sample_count
    assert block_size == _BLOCK_SIZE
    assert not (padding0 or padding1 or padding2 or padding3 or padding4 or padding5)

    block_data = data[_HEADER_SIZE:]
    assert len(block_data) == block_data_size

    if os.path.splitdrive(os.path.dirname(dst_filepath))[1]:
        os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

    with wave.open(dst_filepath, 'wb') as f:
        f.setsampwidth(bit_depth // 8)
        f.setnchannels(channel_count)
        f.setframerate(sample_rate)
        f.setnframes(sample_count)

        block_offset = 0
        block_count = 0
        bytes_written = 0

        while block_offset < block_data_size:
            (
                block_magic_bytes,
                block_size,
                padding0,
                padding1,
                padding2,
            ) = struct.unpack('>LLQQQ', block_data[block_offset:block_offset + _BLOCK_HEADER_SIZE])

            assert block_magic_bytes == _BLOCK_MAGIC
            assert not (padding0 or padding1 or padding2)

            expected_payload_size = block_size * channel_count
            payload_data = block_data[block_offset + _BLOCK_HEADER_SIZE:block_offset +
                                      _BLOCK_HEADER_SIZE + expected_payload_size]
            payload_size = len(payload_data)

            assert payload_size % channel_count == 0
            assert payload_size % (bit_depth // 8) == 0

            payload_data = _interleave_channels(payload_data, channel_count, bit_depth)
            _swap_bytes(payload_data, bit_depth)
            f.writeframesraw(payload_data)

            # In some stock audio files, there seems to be less data than expected, according to
            # what the block header states. When it happens, it is always in the last block.
            assert payload_size <= expected_payload_size

            if payload_size != expected_payload_size:
                payload_delta = payload_size - expected_payload_size
                payload_delta_sign = '+' if payload_delta > 0 else ''

                log.warning(f'Inconsistent last block size. Expected {expected_payload_size} '
                            f'bytes, but read {payload_size} bytes '
                            f'({payload_delta_sign}{payload_delta}).')

            bytes_written += payload_size
            block_count += 1
            block_offset += _BLOCK_HEADER_SIZE + payload_size

        samples_written = bytes_written // channel_count // (bit_depth // 8)
        assert samples_written * channel_count * (bit_depth // 8) == bytes_written
        assert sample_count <= samples_written
        assert block_offset == block_data_size


def convert_to_ast(src_filepath: str,
                   dst_filepath: str,
                   looped: int = None,
                   sample_count: int = None,
                   loop_start: int = None,
                   loop_end: int = None,
                   volume: int = None,
                   last_block_size: int = None):

    if looped is None:
        looped = 0xFFFF
    if loop_start is None:
        loop_start = 0
    if volume is None:
        volume = 127

    with wave.open(src_filepath, 'rb') as f:
        bit_depth = f.getsampwidth() * 8
        channel_count = f.getnchannels()
        sample_rate = f.getframerate()
        if sample_count is None:
            sample_count = f.getnframes()
        if loop_end is None:
            loop_end = sample_count

        assert bit_depth in (8, 16, 32)
        assert looped in (0x0000, 0xFFFF)
        assert loop_start < sample_count
        assert loop_start < loop_end
        assert loop_end == sample_count

        data = f.readframes(f.getnframes())

    data = bytearray(data)
    _swap_bytes(data, bit_depth)
    channel_data = _deinterleave_channels(memoryview(data), channel_count, bit_depth)

    block_chunks = []

    bytes_per_channel = len(channel_data[0])

    def aligned(value: int) -> int:
        return (value | _ALIGNMENT - 1) + 1 if value % _ALIGNMENT else value

    for offset in range(0, bytes_per_channel, _BLOCK_SIZE):
        last_block = offset + _BLOCK_SIZE >= bytes_per_channel
        block_size = min(_BLOCK_SIZE, bytes_per_channel - offset)

        block_header = struct.pack(
            '>LLQQQ',
            _BLOCK_MAGIC,
            last_block_size if last_block and last_block_size is not None else aligned(block_size),
            0x0000000000000000,
            0x0000000000000000,
            0x0000000000000000,
        )
        block_chunks.append(block_header)

        if last_block_size is None:
            padding = aligned(block_size) - block_size
        else:
            padding = 0

        for i in range(channel_count):
            block_chunks.append(channel_data[i][offset:offset + block_size])
            if padding:
                block_chunks.append(b'\x00' * padding)

        if last_block:
            break

    block_data = bytes().join(block_chunks)
    block_data_size = len(block_data)

    if os.path.splitdrive(os.path.dirname(dst_filepath))[1]:
        os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

    with open(dst_filepath, 'wb') as f:
        header_data = struct.pack(
            '>LLHHHHLLLLLLbBHLQQ',
            _MAGIC,
            block_data_size,
            _PCM_FORMAT,
            bit_depth,
            channel_count,
            looped,
            sample_rate,
            sample_count,
            loop_start,
            loop_end,
            _BLOCK_SIZE,
            0x00000000,
            volume,
            0x00,
            0x0000,
            0x00000000,
            0x0000000000000000,
            0x0000000000000000,
        )
        f.write(header_data)
        f.write(block_data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=str, help='Path to the AST/WAV file to converted.')
    parser.add_argument('output',
                        type=str,
                        help='Path to the WAV/AST file that is going to be written.')

    def int_hex(x):
        return int(x, 0)

    ast_to_wav_group = parser.add_argument_group('WAV to AST only')
    ast_to_wav_group.add_argument(
        '--looped',
        '-l',
        type=int_hex,
        help='If set to 0x0000 (0), disables the loop functionality. If set to 0xFFFF (65535), or '
        'any other value that is not 0x0000 (0), the audio will loop after reaching the loop-end '
        'sample. Default is 0xFFFF (65535).')
    ast_to_wav_group.add_argument(
        '--sample-count',
        '-c',
        type=int,
        help='If provided, the sample count field in the AST header (offset: 0x14) will be '
        'overridden by this value. If not provided, the sample count in the WAV file is used. This '
        'argument is offered as it\'s been noticed that some of the stock AST files seen in Mario '
        'Kart: Double Dash!!, Super Mario Galaxy, and Super Mario Galaxy 2 contain more samples '
        'than the count specified in the AST header.')
    ast_to_wav_group.add_argument(
        '--loop-start',
        '-s',
        type=int,
        help='The sample number where the audio track continues playing after reaching the end of '
        'the loop. If not provided, 0 is used.')
    ast_to_wav_group.add_argument(
        '--loop-end',
        '-e',
        type=int,
        help='The number of the last sample that will be played before jumping to the start '
        'of the loop. If not provided, the sample count is used.')
    ast_to_wav_group.add_argument(
        '--volume',
        '-v',
        type=int,
        help='Commonly 127 is used. In rare cases, 100 is used. If not specified, 127 is used.')
    ast_to_wav_group.add_argument(
        '--last-block-size',
        '-b',
        type=int,
        help='If provided, the block size field (offset: 0x04) in the block header of the last '
        'block will be overridden. This argument is offered as it\'s been noticed that a number of '
        'the stock AST files seen in Mario Kart: Double Dash!! and Super Mario Galaxy have an '
        'inconsistent number of bytes in the last block: fewer bytes than what the header states. '
        'This argument lets the user replicate stock courses with their inconsistent last block '
        'size.')

    args = parser.parse_args()

    extension = os.path.splitext(args.input)[1]
    if extension == '.ast':
        _print_mapping(get_ast_info(args.input))
        convert_to_wav(args.input, args.output)
    elif extension == '.wav':
        convert_to_ast(args.input, args.output, args.looped, args.sample_count, args.loop_start,
                       args.loop_end, args.volume, args.last_block_size)
    else:
        raise ValueError(
            f'Input path ("{args.input}") does not have a recognizable file extension. '
            'Expect either `.ast` or `.wav`.')


if __name__ == '__main__':
    main()
