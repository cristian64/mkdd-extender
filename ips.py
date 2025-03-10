"""
Module that includes functions for dealing with IPS binary patches.

Details of the IPS format:
- https://zerosoft.zophar.net/ips.php
- http://justsolve.archiveteam.org/wiki/IPS_(binary_patch_format)
"""

import struct


def read_ips_file(filepath: str) -> list[tuple[int, bytes]]:
    blocks = []

    with open(filepath, 'rb') as f:
        assert f.read(5) == b'PATCH'

        while True:
            offset = f.read(3)
            if offset == b'EOF':
                break
            offset = struct.unpack('>I', b'\x00' + offset)[0]

            size = struct.unpack('>H', f.read(2))[0]
            assert size >= 0

            if size > 0:
                # Regular block
                chunk = f.read(size)
            else:
                # Encoded block
                size = struct.unpack('>H', f.read(2))[0]
                datum = f.read(1)
                chunk = datum * size

            blocks.append((offset, chunk))

    return blocks


def apply_ips_file(ips_filepath: str, filepath: str):
    blocks = read_ips_file(ips_filepath)
    if not blocks:
        return

    with open(filepath, 'r+b') as f:
        for offset, chunk in blocks:
            f.seek(offset)
            f.write(chunk)
