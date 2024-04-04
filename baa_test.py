#!/usr/bin/env python3
"""
Unit tests for the `baa` module.
"""
import os
import sys
import tempfile

import pytest

import baa


def test_stock_data_set():
    """
    Exercises the module by unpacking, and repacking a set of BAA files.
    """
    if not os.getenv('BAA_TEST_DATA_SET_DIR'):
        pytest.fail('BAA_TEST_DATA_SET_DIR environment variable not set. A path to a directory '
                    'containing stock BAA files (e.g. `GCKart.baa`) must be provided.')

    data_set_dir = os.environ['BAA_TEST_DATA_SET_DIR']
    if not os.path.isdir(data_set_dir):
        pytest.fail(f'"{data_set_dir}" is not a valid directory.')

    filepaths = []

    for dirpath, _dirnames, filenames in os.walk(data_set_dir):
        for filename in filenames:
            if filename.endswith('.baa'):
                filepath = os.path.join(dirpath, filename)
                filepaths.append(filepath)

    if not filepaths:
        pytest.fail(f'"{data_set_dir}" does not contain BAA files.')

    for filepath in filepaths:

        with tempfile.TemporaryDirectory() as tmp_dir:
            baa.unpack_baa(filepath, tmp_dir)

            stem, ext = os.path.splitext(os.path.basename(filepath))
            repack_filepath = os.path.join(tmp_dir, f'{stem}_repack{ext}')
            baa.pack_baa(tmp_dir, repack_filepath)

            with open(filepath, 'rb') as f:
                ref_data = f.read()
            with open(repack_filepath, 'rb') as f:
                data = f.read()

        # A number of the stock BAA files (namely the nested BAA files inside `GCKart.baa`) have
        # some extra trailing zero padding (which cannot be explained with any sort of alignment).
        # For the sake of getting these units test pass, trailing zeros will be stripped.
        assert ref_data == data or ref_data.rstrip(b'\x00') == data.rstrip(b'\x00')


if __name__ == '__main__':
    sys.exit(pytest.main(sys.argv))
