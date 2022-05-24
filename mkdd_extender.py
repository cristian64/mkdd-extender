#!/usr/bin/env python3
"""
MKDD Extender is a tool that extends Mario Kart: Double Dash!! with 48 extra courses.
"""
import argparse
import contextlib
import itertools
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile

import rarc
from tools import gcm

LANGUAGES = ('English', 'French', 'German', 'Italian', 'Japanese', 'Spanish')
"""
List of all the known languages in the three regions.
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

PREFIXES = tuple(f'{c}{i + 1:02}' for c, i in itertools.product(('A', 'B', 'C'), range(16)))
"""
A list of the "prefixes" that are used when naming the track archives. First letter states the page,
and the next two digits indicate the track index in the page (from `01` to `16`).
"""

linux = platform.system() == 'Linux'
windows = platform.system() == 'Windows'
macos = platform.system() == 'Darwin'

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(module)-15s %(message)s',
                    level=logging.INFO,
                    datefmt='%Y-%m-%d %H:%M:%S')

log = logging.getLogger('mkdd-extender')

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
tools_dir = os.path.join(script_dir, 'tools')


@contextlib.contextmanager
def current_directory(dirpath):
    cwd = os.getcwd()
    try:
        os.chdir(dirpath)
        yield
    finally:
        os.chdir(cwd)


def run(command: list, verbose: bool = False, cwd: str = None) -> int:
    with subprocess.Popen(command,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          cwd=cwd,
                          text=True) as process:
        output, errors = process.communicate()
        if output and (verbose or (process.returncode and not errors)):
            log.info(output)
        if errors:
            log.error(errors)
        return process.returncode


def build_file_list(dirpath: str) -> 'tuple[str]':

    def _build_file_list(dirpath):
        result = []
        for name in sorted(os.listdir(dirpath) if dirpath else os.listdir()):
            path = os.path.normpath(os.path.join(dirpath, name))
            result.append(path)
            if os.path.isdir(path):
                result.extend(_build_file_list(path))
        return tuple(result)

    with current_directory(dirpath):
        return _build_file_list('')


def extract_and_flatten_archive(src_filepath: str, dst_dirpath: str):
    # Extracts a ZIP archive into the given directory. If the archive contains a single directory,
    # it will be unwrapped. If the archive contains a nested archive, it will be extracted too.
    with tempfile.TemporaryDirectory() as tmp_dir:
        shutil.unpack_archive(src_filepath, tmp_dir)

        paths = tuple(os.path.join(tmp_dir, p) for p in os.listdir(tmp_dir))

        while len(paths) == 1:
            # If there is only one entry, and it's another archive, apply action recursively.
            path = paths[0]
            if path.endswith('.zip') and os.path.isfile(path):
                extract_and_flatten_archive(path, dst_dirpath)
                return

            # If there is only one entry, and it's a directory, make it current.
            if os.path.isdir(path):
                paths = tuple(os.path.join(path, p) for p in os.listdir(path))
                continue

            break

        if paths:
            os.makedirs(dst_dirpath, exist_ok=True)
            for path in paths:
                shutil.move(path, dst_dirpath)


def convert_bti_to_png(src_filepath: str, dst_filepath: str):
    assert src_filepath.endswith('.bti')

    os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

    wimgt_name = 'wimgt.exe' if windows else 'wimgt-mac' if macos else 'wimgt'
    wimgt_path = os.path.join(tools_dir, 'wimgt', wimgt_name)
    command = (wimgt_path, 'decode', src_filepath, '-o', '-d', dst_filepath)

    if 0 != run(command):
        raise RuntimeError(f'Error occurred while converting image file ("{src_filepath}").')


def convert_png_to_bti(src_filepath: str, dst_filepath: str, image_format: str):
    assert src_filepath.endswith('.png')

    os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

    wimgt_name = 'wimgt.exe' if windows else 'wimgt-mac' if macos else 'wimgt'
    wimgt_path = os.path.join(tools_dir, 'wimgt', wimgt_name)
    command = (wimgt_path, 'encode', src_filepath, '--n-mipmaps=0', '-o', '-d', dst_filepath, '-x',
               f'BTI.{image_format}')

    if 0 != run(command):
        raise RuntimeError(f'Error occurred while converting image file ("{src_filepath}").')

    # Wrap S/T fields will be zeroed. It's been advised to do this:
    #
    #   > After converting with wimgt, hex edit the bytes at 0x06 and 0x07 to both be “00”. This
    #   > will ensure that the images are not messed up on Nintendont.
    #
    # Dolphin does not show any difference with or without these bytes set.
    with open(dst_filepath, 'r+b') as f:
        f.seek(0x06)
        f.write(bytes((0x00, 0x00)))


def meld_courses(tracks_dirpath: str, gcm_tmp_dir: str):
    files_dirpath = os.path.join(gcm_tmp_dir, 'files')

    stream_dirpath = os.path.join(files_dirpath, 'AudioRes', 'Stream')
    course_dirpath = os.path.join(files_dirpath, 'Course')
    coursename_dirpath = os.path.join(files_dirpath, 'CourseName')
    staffghosts_dirpath = os.path.join(files_dirpath, 'StaffGhosts')

    with tempfile.TemporaryDirectory() as tracks_tmp_dir:
        # Extract all ZIP archives to their respective directories.
        zip_filepaths = tuple(
            os.path.join(tracks_dirpath, p) for p in sorted(os.listdir(tracks_dirpath))
            if p.endswith('.zip'))
        prefix_to_zip_filename = {}
        extracted = 0
        log.info(f'Extracting ZIP archives...')
        for prefix in PREFIXES:
            for zip_filepath in zip_filepaths:
                zip_filename = os.path.basename(zip_filepath)
                if zip_filename.startswith(prefix):
                    track_dirpath = os.path.join(tracks_tmp_dir, prefix)
                    log.info(f'Extracting "{zip_filepath}" into "{track_dirpath}"...')
                    extract_and_flatten_archive(zip_filepath, track_dirpath)
                    prefix_to_zip_filename[prefix] = zip_filename
                    extracted += 1
                    break
            else:
                # For now, missing an archive will be considered an error. Perhaps a program
                # argument (e.g. `--on-missing`) can be added, so that the user can choose between:
                # - Print error and exit script. Default?
                # - Fall back to the stock course in the slot that he missing track would occupy.
                # - Disable slot by making the label and preview images transparent or black, and
                #   replacing the course with the smallest, viable track that doesn't make the game
                #   crash if the player ends up selecting the track.
                log.error(f'No track assigned to {prefix}. This is fatal.')
                sys.exit(1)
        if extracted > 0:
            log.info(f'{extracted} archives extracted.')
        else:
            log.warning(f'No archive has been extracted.')

        # Copy files into the GCM temporariy dirctory.
        log.info(f'Melding extracted directories...')
        melded = 0
        for prefix in PREFIXES:
            track_dirpath = os.path.join(tracks_tmp_dir, prefix)
            page_index = ord(prefix[0]) - ord('A')
            track_index = int(prefix[1:3]) - 1
            assert 0 <= page_index <= 2
            assert 0 <= track_index <= 15

            zip_filename = prefix_to_zip_filename[prefix]

            log.info(f'Melding "{nodename}" ("{track_dirpath}")...')
            melded += 1

            def with_page_index_suffix(path: str) -> str:
                stem, ext = os.path.splitext(path)
                stem = stem[:-len(str(page_index))] + str(page_index)
                return stem + ext

            page_course_dirpath = with_page_index_suffix(course_dirpath)
            page_coursename_dirpath = with_page_index_suffix(coursename_dirpath)
            page_staffghosts_dirpath = with_page_index_suffix(staffghosts_dirpath)

            # Start off with a copy of the original directories. Relevant files will be replaced
            # next.
            if not os.path.isdir(page_course_dirpath):
                shutil.copytree(course_dirpath, page_course_dirpath)
            if not os.path.isdir(page_coursename_dirpath):
                shutil.copytree(coursename_dirpath, page_coursename_dirpath)
            if not os.path.isdir(page_staffghosts_dirpath):
                shutil.copytree(staffghosts_dirpath, page_staffghosts_dirpath)

            # Copy course files.
            track_filepath = os.path.join(track_dirpath, 'track.arc')
            if not os.path.isfile(track_filepath):
                log.error(f'Unable to locate `track.arc` file in "{zip_filename}". This is fatal.')
                sys.exit(1)
            track_mp_filepath = os.path.join(track_dirpath, 'track_mp.arc')
            if not os.path.isfile(track_mp_filepath):
                log.warning(f'Unable to locate `track_mp.arc` file in "{zip_filename}". '
                            '`track.arc` will be used.')
                track_mp_filepath = track_filepath
            if track_index == 0:
                track_50cc_filepath = os.path.join(track_dirpath, 'track_50cc.arc')
                if not os.path.isfile(track_50cc_filepath):
                    log.warning(f'Unable to locate `track_50cc.arc` file in "{zip_filename}". '
                                '`track.arc` will be used.')
                    track_50cc_filepath = track_filepath
                track_mp_50cc_filepath = os.path.join(track_dirpath, 'track_mp_50cc.arc')
                if not os.path.isfile(track_mp_50cc_filepath):
                    log.warning(f'Unable to locate `track_mp_50cc.arc` file in "{zip_filename}". '
                                '`track_mp.arc` will be used.')
                    track_mp_50cc_filepath = track_mp_filepath
            if track_index == 0:
                page_track_filepath = os.path.join(page_course_dirpath,
                                                   f'{COURSES[track_index]}2.arc')
                page_track_mp_filepath = os.path.join(page_course_dirpath,
                                                      f'{COURSES[track_index]}2L.arc')
                page_track_50cc_filepath = os.path.join(page_course_dirpath,
                                                        f'{COURSES[track_index]}.arc')
                page_track_mp_50cc_filepath = os.path.join(page_course_dirpath,
                                                           f'{COURSES[track_index]}L.arc')
                shutil.copy2(track_filepath, page_track_filepath)
                shutil.copy2(track_mp_filepath, page_track_mp_filepath)
                shutil.copy2(track_50cc_filepath, page_track_50cc_filepath)
                shutil.copy2(track_mp_50cc_filepath, page_track_mp_50cc_filepath)
            else:
                page_track_filepath = os.path.join(page_course_dirpath,
                                                   f'{COURSES[track_index]}.arc')
                page_track_mp_filepath = os.path.join(page_course_dirpath,
                                                      f'{COURSES[track_index]}L.arc')
                shutil.copy2(track_filepath, page_track_filepath)
                shutil.copy2(track_mp_filepath, page_track_mp_filepath)

            # Copy GHT file.
            ght_filepath = os.path.join(track_dirpath, 'staffghost.ght')
            if os.path.isfile(ght_filepath):
                page_ght_filepath = os.path.join(page_staffghosts_dirpath,
                                                 f'{COURSES[track_index]}.ght')
                shutil.copy2(ght_filepath, page_ght_filepath)
            else:
                log.warning(f'Unable to locate `staffghost.ght` file in "{zip_filename}".')

            # Copy audio files. Unlike with the previous files, audio files are stored in the stock
            # directory. The names of the audio files strategically start with a "X_" prefix to
            # ensure they are inserted after the stock audio files.
            lap_music_normal_filepath = os.path.join(track_dirpath, 'lap_music_normal.ast')
            if not os.path.isfile(lap_music_normal_filepath):
                # If there is only the fast version (single-lap course?), it will be used for both,
                # and no warning is needed.
                lap_music_normal_filepath = os.path.join(track_dirpath, 'lap_music_fast.ast')
            if os.path.isfile(lap_music_normal_filepath):
                dst_ast_filepath = os.path.join(stream_dirpath, f'X_COURSE_{prefix}.ast')
                shutil.copy2(lap_music_normal_filepath, dst_ast_filepath)

                lap_music_fast_filepath = os.path.join(track_dirpath, 'lap_music_fast.ast')
                if os.path.isfile(lap_music_fast_filepath):
                    dst_ast_filepath = os.path.join(stream_dirpath, f'X_FINALLAP_{prefix}.ast')
                    shutil.copy2(lap_music_fast_filepath, dst_ast_filepath)
                else:
                    log.warning(f'Unable to locate `lap_music_fast.ast` in "{zip_filename}". '
                                '`lap_music_normal.ast` will be used.')
            else:
                log.warning(f'Unable to locate `lap_music_normal.ast` in "{zip_filename}". Luigi '
                            'Circuit\'s sound track will be used.')

        if melded > 0:
            log.info(f'{melded} directories melded.')
        else:
            log.warning(f'No directory has been melded.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=str, help='Path to the original ISO/GCM file.')
    parser.add_argument('tracks',
                        type=str,
                        help='Path to the directory containing the ZIP archives for each of the '
                        'tracks that will be added to the game.')
    parser.add_argument('output',
                        type=str,
                        help='Filepath where the modified ISO/GCM file will be written.')
    args = parser.parse_args()

    gcm_tmp_dir = tempfile.mkdtemp()
    try:
        # Extract the GCM file entirely for now. In the future, only extracting the files that need
        # to be read might be ideal performance-wise.
        log.info(f'Extracting "{args.input}" image to "{gcm_tmp_dir}"...')
        gcm_file = gcm.GCM(args.input)
        gcm_file.read_entire_disc()
        files_extracted = 0
        for _filepath, files_done in gcm_file.export_disc_to_folder_with_changed_files(gcm_tmp_dir):
            if files_done > 0:
                files_extracted = files_done
        log.info(f'Image extracted ({files_extracted} files).')

        # To determine which have been added, build the initial list now.
        log.info('Building initial file list...')
        initial_file_list = build_file_list(gcm_tmp_dir)
        log.info(f'File list built ({len(initial_file_list)} entries).')

        # Extract the relevant RARC files that will be modified.
        log.info(f'Extracting RARC files...')
        RARC_FILENAMES = ('courseselect.arc', 'LANPlay.arc', 'titleline.arc')
        scenedata_dirpath = os.path.join(gcm_tmp_dir, 'files', 'SceneData')
        scenedata_filenames = os.listdir(scenedata_dirpath)
        rarc_extracted = 0
        for language in LANGUAGES:
            if language not in scenedata_filenames:
                continue
            for filename in RARC_FILENAMES:
                filepath = os.path.join(scenedata_dirpath, language, filename)
                rarc.extract(filepath, os.path.dirname(filepath))
                rarc_extracted += 1
        log.info(f'{rarc_extracted} files extracted.')

        meld_courses(args.tracks, gcm_tmp_dir)

        # Re-pack RARC files, and erase directories.
        log.info(f'Packing RARC files...')
        rarc_packed = 0
        for language in LANGUAGES:
            if language not in scenedata_filenames:
                continue
            for filename in RARC_FILENAMES:
                filepath = os.path.join(scenedata_dirpath, language, filename)
                dirname = os.path.splitext(filename)[0].lower()
                dirpath = os.path.join(scenedata_dirpath, language, dirname)
                rarc.pack(dirpath, filepath)
                shutil.rmtree(dirpath)
                rarc_packed += 1
        log.info(f'{rarc_packed} files packed.')

        # Cross-check which files have been added, and then import all files from disk. While it
        # could be more efficient to compare timestamps and import only the ones that have really
        # changed, the truth is that the ISO image is going to be written straight away, and every
        # file will have to be read regardless.
        log.info('Preparing ISO/GCM image...')
        final_file_list = build_file_list(gcm_tmp_dir)
        for path in final_file_list:
            if path not in initial_file_list:
                if os.path.isfile(os.path.join(gcm_tmp_dir, path)):
                    gcm_file.add_new_file(path)
                else:
                    gcm_file.add_new_directory(path)
        gcm_file.import_all_files_from_disk(gcm_tmp_dir)
        log.info('ISO/GCM image prepared.')

        # Write extended GCM file to final location.
        log.info(f'Writing extended ISO/GCM image to "{args.output}"...')
        files_written = 0
        for _filepath, files_done in gcm_file.export_disc_to_iso_with_changed_files(args.output):
            if files_done > 0:
                files_written = files_done
        log.info(f'ISO/GCM image written ({files_written} files).')

    finally:
        shutil.rmtree(gcm_tmp_dir)


if __name__ == '__main__':
    main()
