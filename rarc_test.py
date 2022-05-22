#!/usr/bin/env python3
"""
Unit tests for the `rarc` module.
"""
import filecmp
import os
import sys
import tempfile

import pytest

import rarc


def __cmpdir(dirpath_a: str, dirpath_b: str) -> bool:
    dircmp = filecmp.dircmp(dirpath_a, dirpath_b)
    if dircmp.diff_files or dircmp.left_only or dircmp.right_only or dircmp.funny_files:
        return False
    for sub_dircmp in dircmp.subdirs.values():
        if not __cmpdir(sub_dircmp.left, sub_dircmp.right):
            return False
    return True


def test_synthetic_data_set():
    """
    Each data set is a list of path and size tuples. If size is `None`, an empty directory is
    created; otherwise a file of the given size is created.
    """
    data_sets = (
        (),
        (('a', None), ),
        (('a.ext', 0), ),
        (('a.ext', 1), ),
        (
            ('a/b.ext', 100),
            ('a/c.ext', 0),
            ('a/d.ext', 300),
            ('e', None),
            ('f/g', 200),
            ('f/h', 200),
            ('f/iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii', 5000),
            ('j/k.ext', 10000),
            ('j/l.ext', 0),
            ('j/m.ext', 0),
            ('j/n', None),
            ('ooooooooooooooooooooo', None),
            ('p/q', None),
        ),
    )

    for i, data_set in enumerate(data_sets):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Generate file tree structure.
            test_name = f'test{i}'
            test_dir = os.path.join(tmp_dir, test_name)
            os.makedirs(test_dir, exist_ok=True)
            for relpath, size in data_set:
                path = os.path.join(test_dir, relpath)
                if size is None:
                    os.makedirs(path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'wb') as f:
                        f.write(os.urandom(size))

            # Pack directory.
            arc_filepath = f'{test_dir}.arc'
            rarc.pack(test_dir, arc_filepath)

            # Re-extract previously packed ARC file.
            with tempfile.TemporaryDirectory() as second_tmp_dir:
                rarc.extract(arc_filepath, second_tmp_dir)

                extracted_dirnames = os.listdir(second_tmp_dir)
                assert len(extracted_dirnames) == 1
                extracted_dirname = extracted_dirnames[0]
                assert extracted_dirname == test_name
                extracted_test_dir = os.path.join(second_tmp_dir, extracted_dirname)

                assert __cmpdir(test_dir, extracted_test_dir)


def test_stock_data_set():
    """
    Exercises the module by extracting, repacking, and re-extracting a set of RARC files generated
    by third-party tools.
    """
    if not os.getenv('RARC_TEST_DATA_SET_DIR'):
        pytest.fail('RARC_TEST_DATA_SET_DIR environment variable not set. A path to a directory '
                    'containing stock ARC files must be provided.')

    data_set_dir = os.environ['RARC_TEST_DATA_SET_DIR']
    if not os.path.isdir(data_set_dir):
        pytest.fail(f'"{data_set_dir}" is not a valid directory.')

    filepaths = []

    for dirpath, _dirnames, filenames in os.walk(data_set_dir):
        for filename in filenames:
            # # Yaz0 not yet supported (file seen in Mario Kart: Double Dash!!).
            if filename == 'JaiSeqs.arc':
                continue
            if filename.endswith('.arc'):
                filepath = os.path.join(dirpath, filename)
                filepaths.append(filepath)

    if not filepaths:
        pytest.fail(f'"{data_set_dir}" does not contain ARC files.')

    for filepath in filepaths:

        # Extract stock ARC file.
        with tempfile.TemporaryDirectory() as tmp_dir:
            rarc.extract(filepath, tmp_dir)

            extracted_dirnames = os.listdir(tmp_dir)
            assert len(extracted_dirnames) == 1
            extracted_dirname = extracted_dirnames[0]
            extracted_dirpath = os.path.join(tmp_dir, extracted_dirname)
            assert os.path.isdir(extracted_dirpath)

            # Repack previously extracted ARC file.
            with tempfile.TemporaryDirectory() as second_tmp_dir:
                filename = os.path.basename(filepath)
                packed_filepath = os.path.join(second_tmp_dir, filename)
                rarc.pack(extracted_dirpath, packed_filepath)
                if filename not in ('ARAM.arc', 'MRAM.arc', 'selectAnm.arc'):
                    # These three files from Mario Kart: Double Dash!! seem to be larger than the
                    # expected size. Technically, files can have extra padding between sections; the
                    # format does not require it.
                    assert os.path.getsize(filepath) == os.path.getsize(packed_filepath)

                # Re-extract the previously repacked ARC file.
                with tempfile.TemporaryDirectory() as third_tmp_dir:
                    rarc.extract(packed_filepath, third_tmp_dir)

                    reextracted_dirnames = os.listdir(third_tmp_dir)
                    assert len(reextracted_dirnames) == 1
                    reextracted_dirname = reextracted_dirnames[0]
                    reextracted_dirpath = os.path.join(third_tmp_dir, reextracted_dirname)
                    assert os.path.isdir(reextracted_dirpath)

                    assert __cmpdir(extracted_dirpath, reextracted_dirpath)


if __name__ == "__main__":
    sys.exit(pytest.main(sys.argv))
