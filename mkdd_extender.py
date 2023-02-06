#!/usr/bin/env python3
"""
MKDD Extender is a tool that extends Mario Kart: Double Dash!! with up to 144 extra courses.
"""
import argparse
import audioop
import collections
import configparser
import contextlib
import difflib
import hashlib
import itertools
import json
import logging
import math
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave
import zipfile

from PIL import Image, ImageDraw, ImageFont

import ast_converter
import code_patcher
import gecko_code
import rarc
from tools import bti, gcm
from tools.GeckoLoader import GeckoLoader

__version__ = '0.5.0'

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

COURSE_TO_NAME = {
    'BabyLuigi': 'Baby Park',
    'Koopa': 'Bowser\'s Castle',
    'Daisy': 'Daisy Cruiser',
    'Diddy': 'Dino Dino Jungle',
    'Donkey': 'DK Mountain',
    'Desert': 'Dry Dry Desert',
    'Nokonoko': 'Mushroom Bridge',
    'Patapata': 'Mushroom City',
    'Luigi': 'Luigi Circuit',
    'Mario': 'Mario Circuit',
    'Peach': 'Peach Beach',
    'Rainbow': 'Rainbow Road',
    'Snow': 'Sherbet Land',
    'Waluigi': 'Waluigi Stadium',
    'Wario': 'Wario Colosseum',
    'Yoshi': 'Yoshi Circuit',
}
"""
Map from the course internal name to the course natural name.
"""

COURSE_TO_PREVIEW_IMAGE_NAME = {
    'BabyLuigi': 'baby_park',
    'Koopa': 'bowser_castle',
    'Daisy': 'daisy_ship',
    'Diddy': 'dino_dino_jungle',
    'Donkey': 'dk_mountain',
    'Desert': 'kara_kara_desert',
    'Nokonoko': 'kinoko_bridge',
    'Patapata': 'konoko_city',
    'Luigi': 'luigi_circuit',
    'Mario': 'mario_circuit',
    'Peach': 'peach_beach',
    'Rainbow': 'rainbow_road',
    'Snow': 'sherbet_land',
    'Waluigi': 'waluigi_stadium',
    'Wario': 'wario_colosseum',
    'Yoshi': 'yoshi_circuit',
}
"""
A dictionary to map the internal course name to the [partial] name of the preview images in the
`SceneData/<language>/courseselect.arc` archive, which is `cop_<partial_name>.bti`.
"""

COURSE_TO_LABEL_IMAGE_NAME = {**dict(COURSE_TO_PREVIEW_IMAGE_NAME), **{'Patapata': 'kinoko_city'}}
"""
A dictionary to map the internal course name to the [partial] name of the label images in the
`SceneData/<language>/courseselect.arc` archive, which is `coname_<partial_name>.bti`.

This is identical to `COURSE_TO_PREVIEW_IMAGE_NAME`, except for the `Patapata` entry, which differs.
"""

MAX_EXTRA_PAGES = 9
"""
The maximum number of extra pages that can be added to the game, to a total of 10 pages, including
the first page that features the stock courses.
"""

PREFIXES = tuple(f'{chr(ord("A") + page_index)}{i + 1:02}'
                 for page_index, i in itertools.product(range(MAX_EXTRA_PAGES), range(16)))
"""
A list of the "prefixes" that are used when naming the track archives. First letter states the page,
and the next two digits indicate the track index in the page (from `01` to `16`).
"""

CUP_NAMES = ('Mushroom Cup', 'Flower Cup', 'Star Cup', 'Special Cup')
"""
English names of the four cups.
"""

MAX_ISO_SIZE = 1459978240
"""
The maximum size of the GameCube ISO files that GameCube or Wii can support.
"""

linux = platform.system() == 'Linux'
windows = platform.system() == 'Windows'
macos = platform.system() == 'Darwin'

frozen = getattr(sys, 'frozen', False)


class _CustomFormatter(logging.Formatter):
    yellow = '\x1b[0;33m' if not windows else ''
    bold_red = '\x1b[1;91m' if not windows else ''
    bold_fucsia = '\x1b[1;95m' if not windows else ''
    reset = '\x1b[0m' if not windows else ''

    def __init__(self):
        super().__init__()

        fmt = '%(asctime)s %(levelname)-8s %(name)-15s %(message)s'
        self.__formatters = {
            logging.DEBUG: logging.Formatter(fmt),
            logging.INFO: logging.Formatter(fmt),
            logging.WARNING: logging.Formatter(self.yellow + fmt + self.reset),
            logging.ERROR: logging.Formatter(self.bold_red + fmt + self.reset),
            logging.CRITICAL: logging.Formatter(self.bold_fucsia + fmt + self.reset),
        }

    def format(self, record):
        return self.__formatters[record.levelno].format(record)


class NoInternalModuleFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno > logging.WARNING or record.module not in ('rarc', 'ast_converter')


console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(_CustomFormatter())
console_handler.addFilter(NoInternalModuleFilter())

logging.basicConfig(datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO, handlers=(console_handler, ))

log = logging.getLogger('mkdd-extender')

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
tools_dir = os.path.join(script_dir, 'tools')
data_dir = os.path.join(script_dir, 'data')

TEMP_DIR_PREFIX = 'mkddext'

try:
    RESAMPLING_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    # If the Pillow version is old, the enum class won't be available. Fall back to the deprecated
    # value for now.
    RESAMPLING_FILTER = Image.LANCZOS


class MKDDExtenderError(Exception):
    pass


@contextlib.contextmanager
def current_directory(dirpath):
    cwd = os.getcwd()
    try:
        os.chdir(dirpath)
        yield
    finally:
        os.chdir(cwd)


def remove_file(filepath: str):
    try:
        os.remove(filepath)
    except Exception:
        pass


def make_link(src_filepath: str, dst_filepath: str):
    remove_file(dst_filepath)
    os.link(src_filepath, dst_filepath)


def clean_stale_temp_dirs():
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        user_tmp_dir = os.path.dirname(tmp_dir)

    for name in os.listdir(user_tmp_dir):
        if name.startswith(TEMP_DIR_PREFIX):
            try:
                shutil.rmtree(os.path.join(user_tmp_dir, name))
            except Exception:
                pass


def run(command: list, verbose: bool = False, cwd: str = None) -> int:
    creationflags = 0
    if windows:
        creationflags |= subprocess.CREATE_NO_WINDOW

    with subprocess.Popen(command,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          cwd=cwd,
                          text=True,
                          creationflags=creationflags) as process:
        output, errors = process.communicate()
        if output and (verbose or (process.returncode and not errors)):
            log.info(output)
        if errors:
            log.error(errors)
        return process.returncode


def md5sum(filepath: str) -> str:
    return hashlib.md5(open(filepath, 'rb').read()).hexdigest()


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


def get_custom_track_name(path: str) -> str:

    def name_from_trackinfo(trackinfo_filepath: str) -> str:
        trackinfo = configparser.ConfigParser()
        try:
            trackinfo.read(trackinfo_filepath)
            return trackinfo['Config']['trackname']
        except Exception:
            return str()

    # If it's a directory, check if it contains the `trackinfo.ini` file. If it contains a single
    # directory, check also in that directory.
    if os.path.isdir(path):
        names = os.listdir(path)
        if 'trackinfo.ini' in names:
            return name_from_trackinfo(os.path.join(path, 'trackinfo.ini'))
        if len(names) == 1:
            return get_custom_track_name(os.path.join(path, names[0]))

    # If it's an archive, check if the `trackinfo.ini` file can be found in the entry list.
    elif path.endswith('.zip'):
        with zipfile.ZipFile(path, 'r') as f:
            names = f.namelist()

            trackinfo_entries = []
            for name in names:
                if os.path.basename(name) == 'trackinfo.ini':
                    trackinfo_entries.append(name)

            # Only accepted if there is a single entry.
            if len(trackinfo_entries) == 1:
                trackinfo_entry = trackinfo_entries[0]
                with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
                    f.extract(trackinfo_entry, tmp_dir)
                    f.close()

                    return name_from_trackinfo(os.path.join(tmp_dir, trackinfo_entry))

    return str()


def scan_custom_tracks_directory(dirpath: str) -> 'dict[str, str]':
    try:
        names = sorted(os.listdir(dirpath))
    except Exception:
        return None

    paths_to_track_name = {}
    for name in names:
        path = os.path.join(dirpath, name)

        try:
            track_name = get_custom_track_name(path)
            if track_name:
                paths_to_track_name[path] = track_name
                continue
        except Exception:
            pass

        if os.path.isdir(path):
            pathsd_names_to_track_name = scan_custom_tracks_directory(path)
            if pathsd_names_to_track_name:
                paths_to_track_name.update(pathsd_names_to_track_name)

    return paths_to_track_name


def extract_and_flatten(src_path: str, dst_dirpath: str):
    # Extracts a ZIP archive into the given directory. If the archive contains a single directory,
    # it will be unwrapped. If the archive contains a nested archive, it will be extracted too.
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        if os.path.isfile(src_path):
            shutil.unpack_archive(src_path, tmp_dir)
        else:
            shutil.copytree(src_path, os.path.join(tmp_dir, os.path.basename(src_path)))

        paths = tuple(os.path.join(tmp_dir, p) for p in os.listdir(tmp_dir))

        while len(paths) == 1:
            # If there is only one entry, and it's another archive, apply action recursively.
            path = paths[0]
            if path.endswith('.zip') and os.path.isfile(path):
                extract_and_flatten(path, dst_dirpath)
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


def course_name_to_course(course_name: str) -> str:
    # A distance between strings is used for the comparison, as there are some courses names that
    # are often used inaccurately (e.g. missing apostrophe in Bowser's Castle).
    courses_weight = [(course, difflib.SequenceMatcher(None, other_course_name,
                                                       course_name).ratio())
                      for course, other_course_name in COURSE_TO_NAME.items()]
    return sorted(courses_weight, key=lambda e: e[1])[-1][0]


def patch_music_id_in_bol_file(course_filepath: str, track_index: int):
    assert course_filepath.endswith('.arc')
    assert 0 <= track_index <= 15

    MUSIC_IDS = (36, 34, 33, 50, 40, 37, 35, 42, 51, 41, 38, 45, 43, 44, 47, 49)
    assert len(MUSIC_IDS) == 16 == len(set(MUSIC_IDS))

    music_id = MUSIC_IDS[track_index]

    BOL_MAGIC = b'0015'
    MUSIC_ID_OFFSET = 0x19  # https://wiki.tockdom.com/wiki/BOL_(File_Format)

    with open(course_filepath, 'rb') as f:
        data = f.read()

    # If the start of the BOL file can be located [once] in the archive, the BOL file can be edited
    # directly without having to extract the archive first, which would be slower.
    bol_offset = data.find(BOL_MAGIC)
    if bol_offset > 0:
        if data.find(BOL_MAGIC, bol_offset + len(BOL_MAGIC)) < 0:
            with open(course_filepath, 'r+b') as f:
                f.seek(bol_offset + MUSIC_ID_OFFSET)
                f.write(bytes([music_id]))
            return

    # Otherwise, extract the RARC file, locate the BOL file in the directory, patch the BOL file,
    # and re-pack the RARC archive.
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        rarc.extract(course_filepath, tmp_dir)

        course_dirpath = os.path.join(tmp_dir, os.listdir(tmp_dir)[0])
        bol_filepath = os.path.join(
            course_dirpath,
            tuple(p for p in os.listdir(course_dirpath) if p.endswith('.bol'))[0])

        with open(bol_filepath, 'r+b') as f:
            f.seek(MUSIC_ID_OFFSET)
            f.write(bytes([music_id]))

        remove_file(course_filepath)  # It may be a hard link; unlink early.

        rarc.pack(course_dirpath, course_filepath)


def repack_course_arc_file(archive_filepath: str, new_dirname: str):
    """
    Extracts a RARC archive, renames its root directory and its files, and re-packs it.
    """
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        rarc.extract(archive_filepath, tmp_dir)

        dirnames = os.listdir(tmp_dir)
        if len(dirnames) != 1:
            raise MKDDExtenderError(f'Unable to rename entries in "{archive_filepath}". Unexpected '
                                    'number of root entries in directory.')

        dirname = dirnames[0]
        dirpath = os.path.join(tmp_dir, dirname)
        new_dirpath = os.path.join(tmp_dir, new_dirname)
        os.rename(dirpath, new_dirpath)

        course_name = new_dirname
        if course_name.endswith('l'):
            course_name = course_name[:-1]
        if course_name.endswith('2'):
            course_name = course_name[:-1]

        # Files that contain "_" in their names need to be renamed as well to the course name.
        for filename in os.listdir(new_dirpath):
            if '_' in filename:
                filepath = os.path.join(new_dirpath, filename)
                if os.path.isfile(filepath):
                    parts = filename.split('_', maxsplit=1)
                    new_filename = f'{course_name}_{parts[1]}'
                    new_filepath = os.path.join(new_dirpath, new_filename)
                    os.rename(filepath, new_filepath)

        remove_file(archive_filepath)  # It may be a hard link; unlink early.

        rarc.pack(new_dirpath, archive_filepath)


def convert_bti_to_image(filepath: str) -> Image.Image:
    assert filepath.endswith('.bti')

    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        filename = os.path.basename(filepath)
        tmp_filepath = os.path.join(tmp_dir, filename[:-len('.bti')] + '.png')

        wimgt_name = 'wimgt.exe' if windows else 'wimgt-mac' if macos else 'wimgt'
        wimgt_path = os.path.join(tools_dir, 'wimgt', wimgt_name)
        command = (wimgt_path, 'decode', filepath, '-o', '-d', tmp_filepath)

        try:
            if 0 == run(command):
                return Image.open(tmp_filepath).copy()
        except Exception:
            pass

    try:
        return bti.BTI(open(filepath, 'rb')).render()
    except Exception:
        return None


def convert_bti_to_png(src_filepath: str, dst_filepath: str):
    assert src_filepath.endswith('.bti')

    os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

    wimgt_name = 'wimgt.exe' if windows else 'wimgt-mac' if macos else 'wimgt'
    wimgt_path = os.path.join(tools_dir, 'wimgt', wimgt_name)
    command = (wimgt_path, 'decode', src_filepath, '-o', '-d', dst_filepath)

    if 0 != run(command) or not os.path.isfile(dst_filepath):
        # Fall back to the `bti` module if `wimgt` fails.
        with open(src_filepath, 'rb') as f:
            bti.BTI(f).render().save(dst_filepath)
        if not os.path.isfile(dst_filepath):
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


def crop_image_sides(image: Image.Image) -> Image.Image:
    bbox = list(image.getbbox())
    bbox[1] = 0
    bbox[3] = image.height
    return image.crop(bbox)


def split_image(image: Image.Image) -> 'list[Image.Image]':
    image = crop_image_sides(image)

    width = image.width
    height = image.height

    for w in range(width):
        for h in range(height):
            r, g, b, a = image.getpixel((w, h))
            if (r, g, b, a) != (0, 0, 0, 0):
                break
        else:
            left_image = image.crop((0, 0, w, height))
            right_images = split_image(image.crop((w + 1, 0, width, height)))
            return [left_image] + right_images

    return [image]


def add_controls_to_title_image(args: argparse.Namespace, filepath: str, language: str):
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        title_filename = os.path.basename(filepath)
        tmp_filepath = os.path.join(tmp_dir, title_filename[:-len('.bti')] + '.png')

        convert_bti_to_png(filepath, tmp_filepath)

        controls_filename = 'controls.png' if args.legacy_gecko_codes else 'dpad_up_down.png'
        controls_filepath = os.path.join(data_dir, 'controls', controls_filename)
        controls_image = Image.open(controls_filepath)
        slash_filepath = os.path.join(data_dir, 'controls', 'slash.png')
        slash_image = Image.open(slash_filepath)
        slash_image = slash_image.convert('RGBA')

        title_image = Image.open(tmp_filepath)
        title_image = title_image.convert('RGBA')

        canvas_width = title_image.width
        canvas_height = title_image.height

        words = split_image(title_image)
        if language == 'Spanish':
            words = words[0::2]  # Drop "UN" and "UNA" in Spanish, as otherwise it's too crowded.
        words.append(slash_image)
        words.append(controls_image)

        effective_width = sum(img.width for img in words)

        available_width = canvas_width - effective_width

        MAX_SPACING = 10
        spaces = len(words) - 1
        spacing = min(MAX_SPACING, available_width // spaces)
        spacing_width = spacing * spaces

        margin_width = max(0, available_width - spacing_width)
        offset = max(0, margin_width // 2)

        ops = []
        for word in words:
            ops.append((word, (offset, 0)))
            offset += spacing + word.width

        image = Image.new('RGBA', (canvas_width, canvas_height))
        for word, box in reversed(ops):
            image.alpha_composite(word, dest=box)
        image.save(tmp_filepath)

        remove_file(filepath)  # It may be a hard link; unlink early.

        convert_png_to_bti(tmp_filepath, filepath, 'RGB5A3')


def add_dpad_to_cup_name_image(filepath: str, page_index: int):
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        cupname_filename = os.path.basename(filepath)
        tmp_filepath = os.path.join(tmp_dir, cupname_filename[:-len('.bti')] + '.png')

        convert_bti_to_png(filepath, tmp_filepath)

        dpad_filepath = os.path.join(data_dir, 'controls', 'dpad.png')
        dpad_image = Image.open(dpad_filepath)

        # It is assumed that the D-pad image is set to the initial state (that is, pointing to the
        # right). Only for the extra custom pages a rotation is needed.
        if page_index == 0:
            dpad_image = dpad_image.rotate(90)  # Up
        elif page_index == 1:
            dpad_image = dpad_image.rotate(-90)  # Down
        elif page_index == 2:
            dpad_image = dpad_image.rotate(180)  # Left

        cupname_image = Image.open(tmp_filepath)
        original_mode = cupname_image.mode  # Original mode is 'LA'.
        cupname_image = cupname_image.convert('RGBA')

        canvas_width = cupname_image.width - dpad_image.width
        canvas_height = cupname_image.height

        words = split_image(cupname_image)

        effective_width = sum(img.width for img in words)
        available_width = canvas_width - effective_width

        MAX_SPACING = 3
        spaces = len(words) - 1
        spacing = min(MAX_SPACING, available_width // spaces) if spaces > 0 else 0
        spacing_width = spacing * spaces

        margin_width = max(0, available_width - spacing_width)
        offset = max(0, margin_width // 2)
        if not spacing:
            offset += min(dpad_image.width, cupname_image.width - effective_width)
        else:
            offset += dpad_image.width

        ops = []
        for word in words:
            ops.append((word, (offset, 0)))
            offset += spacing + word.width

        image = Image.new('RGBA', (canvas_width + dpad_image.width, canvas_height))
        for word, box in reversed(ops):
            image.alpha_composite(word, dest=box)
        image.alpha_composite(dpad_image)
        image = image.convert(original_mode)
        image.save(tmp_filepath)

        remove_file(filepath)  # It may be a hard link; unlink early.

        convert_png_to_bti(tmp_filepath, filepath, 'IA4')


def build_page_numbers_image(page_number: int, page_count: int) -> Image.Image:
    image, _overflow = build_text_image_from_bitmap_font(f'{page_number}/{page_count}', 80, 16, 2,
                                                         0, 0.6, 0.5)
    image = crop_image_sides(image)
    image = pad_image_sides(image, 80 - image.width, 0)
    return image


def add_page_number_to_cup_name_image(filepath: str, page_number: int, page_count: int):
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        cupname_filename = os.path.basename(filepath)
        tmp_filepath = os.path.join(tmp_dir, cupname_filename[:-len('.bti')] + '.png')

        convert_bti_to_png(filepath, tmp_filepath)

        cupname_image = Image.open(tmp_filepath)
        original_mode = cupname_image.mode  # Original mode is 'LA'.
        cupname_image = cupname_image.convert('RGBA')

        numbers_image = build_page_numbers_image(page_number, page_count)

        margin = int(numbers_image.width / 1.5)
        canvas_width = cupname_image.width + margin * 2
        canvas_height = cupname_image.height

        image = Image.new('RGBA', (canvas_width, canvas_height))
        image.paste(cupname_image, (margin, 0))
        image.alpha_composite(numbers_image,
                              dest=(canvas_width - numbers_image.width,
                                    canvas_height - numbers_image.height))
        image = image.convert(original_mode)
        image.save(tmp_filepath)

        remove_file(filepath)  # It may be a hard link; unlink early.

        convert_png_to_bti(tmp_filepath, filepath, 'IA4')


CHARACTERS = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '-', ':', '!', '.', '?', '/',
              'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q',
              'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', "'", '"', '&', 'Ä', 'Ë', 'Ï', 'Ö', 'Ü',
              'Á', 'É', 'Í', 'Ó', 'Ú', 'À', 'È', 'Ì', 'Ò', 'Ù', 'Â', 'Ê', 'Î', 'Ô', 'Û', 'Ç', 'ẞ',
              'Ñ', '¡', '¿')
CHARACTER_SET = set(CHARACTERS)
CHARACTER_INDEX = {c: i for i, c in enumerate(CHARACTERS)}
CHARACTER_IMAGE_MAP = {}
CHARACTER_DEFAULT_PADDING = 8
CHARACTER_PADDING_REMOVAL = {
    ':': (3, 3),
    '!': (3, 3),
    '¡': (3, 3),
    '.': (3, 3),
    '/': (2, 2),
    'A': (2, 0),
    'Á': (2, 0),
    'À': (1, 0),
    'F': (0, 1),
    'I': (4, 4),
    'Í': (4, 2),
    'Ì': (2, 4),
    'J': (1, 0),
    'L': (0, 2),
    'P': (0, 1),
    'T': (0, 3),
    'V': (1, 1),
    "'": (8, 8),
    '"': (3, 3),
}
"""
Some characters, due to their shape, can benefit from a smaller padding. It makes some letter
combination such as "TA" less awkward, as otherwise the gap between the lower part in "T", and the
upper part in "A" is too great; it would almost look like as a word separation.
"""

FOREGROUND_CHARACTERS = set(("'", ))
"""
Set of characters that will be drawn on top of the rest. This idea is seen in the stock Bowser's
Castle text image, where the apostrophe doesn't respect the depth of its position in the list of
letters from right to left.
"""


def pad_image_sides(image: Image.Image, left_padding: int, right_padding: int):
    result = Image.new(image.mode, (image.width + left_padding + right_padding, image.height))
    result.paste(image, (left_padding, 0))
    return result


def build_text_image_from_bitmap_font(text: str, width: int, height: int, character_spacing: int,
                                      word_spacing: int, horizontal_scaling: float,
                                      vertical_scaling: float) -> (Image.Image, bool):
    text = text.upper()
    character_spacing -= CHARACTER_DEFAULT_PADDING * 2
    word_spacing -= CHARACTER_DEFAULT_PADDING * 2
    if horizontal_scaling <= 0.0 or 1.0 < horizontal_scaling:
        horizontal_scaling = 1.0
    if vertical_scaling <= 0.0 or 1.0 < vertical_scaling:
        vertical_scaling = 1.0

    image_groups = []
    for word in text.split():
        word_images = []

        for c in word.strip():
            if c not in CHARACTER_SET:
                continue

            if c not in CHARACTER_IMAGE_MAP:
                index = CHARACTER_INDEX[c]
                character_filepath = os.path.join(data_dir, 'fonts', 'mkdd', f'{index:0>4}.png')
                character_image = Image.open(character_filepath).convert('RGBA')
                padding_removal = CHARACTER_PADDING_REMOVAL.get(c, (0, 0))
                left_padding = CHARACTER_DEFAULT_PADDING - padding_removal[0]
                right_padding = CHARACTER_DEFAULT_PADDING - padding_removal[1]
                character_image = pad_image_sides(character_image, left_padding, right_padding)
                CHARACTER_IMAGE_MAP[c] = character_image
            else:
                character_image = CHARACTER_IMAGE_MAP[c]

            if (horizontal_scaling, vertical_scaling) != (1.0, 1.0):
                new_width = max(1, round(character_image.width * horizontal_scaling))
                new_height = max(1, round(character_image.height * vertical_scaling))
                character_image = character_image.resize((new_width, new_height),
                                                         resample=RESAMPLING_FILTER,
                                                         reducing_gap=3.0)

            character_image.character = c

            word_images.append(character_image)

        if word_images:
            image_groups.append(word_images)

    required_width = 0
    if word_spacing > 0 and image_groups:
        required_width += word_spacing * (len(image_groups) - 1)
    for word_images in image_groups:
        for image in word_images:
            required_width += image.width
        if character_spacing > 0 and word_images:
            required_width += character_spacing * (len(word_images) - 1)
    required_height = (image_groups[0][0].height if image_groups[0] else 0) if image_groups else 0
    if required_width < 1 or required_height < 1:
        return Image.new('RGBA', (width, height)), False

    offset = 0
    ops = []
    for i, word_images in enumerate(image_groups):
        offset += word_spacing if i else 0
        for j, character_image in enumerate(word_images):
            offset += character_spacing if j else 0
            ops.append((character_image, (offset, 0)))
            offset += character_image.width

    placeholder = Image.new('RGBA', (required_width, required_height))
    for character_image, box in reversed(ops):
        if character_image.character not in FOREGROUND_CHARACTERS:
            placeholder.alpha_composite(character_image, source=(0, 0), dest=box)
    for character_image, box in reversed(ops):
        if character_image.character in FOREGROUND_CHARACTERS:
            placeholder.alpha_composite(character_image, source=(0, 0), dest=box)
    placeholder = placeholder.crop(placeholder.getbbox())

    image = Image.new('RGBA', (width, height))
    image.paste(placeholder, ((width - placeholder.width) // 2, (height - placeholder.height) // 2))
    overflow = placeholder.width > width or placeholder.height > height
    return image, overflow


def generate_bti_image_from_bitmap_font(text: str, width: int, height: int, image_format: str,
                                        background: 'tuple[int, int, int, int]', filepath: str):
    assert filepath.endswith('.bti')

    words = text.split()
    multiline = height > 32 and len(words) > 1

    if height <= 32:
        default_scale = 0.95  # Close to the scale in the stock images when height is 32 pixels.
    else:
        default_scale = 1.0

    if multiline:
        lines = None
        diff = None
        for i in range(len(words) - 1):
            candidate = (' '.join(words[:i + 1]), ' '.join(words[i + 1:]))
            candidate_diff = abs(len(candidate[0]) - len(candidate[1]))
            if lines is None or candidate_diff < diff:
                diff = candidate_diff
                lines = candidate
    else:
        lines = (' '.join(words), )

    FONT_HEIGHT = 32

    vertical_scale = min(default_scale, height / len(lines) / FONT_HEIGHT)

    line_image_height = math.ceil(FONT_HEIGHT * vertical_scale)

    line_images = []
    for line in lines:
        # Some heuristics that seem to provide good results for a wide variety of lengths.
        margin = 0
        if width >= 208:
            if len(line) < 7:
                spacing = -12, 2
                margin = 15
            elif len(line) < 10:
                spacing = -12, 2
                margin = 10
            elif len(line) < 14:
                spacing = -12, 2
                margin = 5
            elif len(line) < 20:
                spacing = -5, 5
            else:
                spacing = 1, 9
        else:
            if len(line) < 7:
                spacing = -12, 2
                margin = 3
            elif len(line) < 10:
                spacing = -3, 3
                margin = 1
            elif len(line) < 14:
                spacing = -1, 6
            elif len(line) < 20:
                spacing = 1, 7
            else:
                spacing = 1, 9

        line_image_width = width - margin * 2

        # Iteratively find a scale that makes the line fit in the image of the requested dimensions.
        for scale in range(100, 40, -1):
            image, overflow = build_text_image_from_bitmap_font(line, line_image_width,
                                                                line_image_height, *spacing,
                                                                scale / 100, vertical_scale)
            if not overflow:
                line_images.append((image, margin))
                break
        else:
            break

    if len(line_images) == len(lines):
        image_with_background = Image.new('RGBA', (width, height), background)

        offset_y = (height - len(lines) * line_image_height) // 2
        for line_image, margin in line_images:
            image_with_background.alpha_composite(line_image, dest=(margin, offset_y))
            offset_y += line_image.height

        with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
            tmp_filepath = os.path.join(tmp_dir,
                                        f'{os.path.splitext(os.path.basename(filepath))[0]}.png')
            image_with_background.save(tmp_filepath)

            remove_file(filepath)  # It may be a hard link; unlink early.

            convert_png_to_bti(tmp_filepath, filepath, image_format)

        return

    # Fallback to implementation based on the TrueType font.
    generate_bti_image(text, width, height, image_format, background, filepath)


def generate_bti_image(text: str, width: int, height: int, image_format: str,
                       background: 'tuple[int, int, int, int]', filepath: str):
    assert filepath.endswith('.bti')

    filtered_text = ''
    for c in text:
        if c.lower() in ' abcdefghijklmnopqrstuvwxyz0123456789$!?:#%@+-':
            filtered_text += c

    filtered_text = ' '.join(filtered_text.split())

    if not filtered_text:
        filtered_text = '?'
    filtered_text = filtered_text.upper()

    text_image = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(text_image)

    font_filepath = os.path.join(data_dir, 'fonts', 'SuperMario256.ttf')

    # Add some margin so that the text is not too close to the edges.
    HORIZNOTAL_MARGIN = 1
    VERTICAL_MARGIN = 1

    for size in range(2, 100):
        font = ImageFont.truetype(font_filepath, size)
        stroke_width = max(3, size // 10)
        left, top, right, bottom = draw.textbbox((width // 2, height // 2),
                                                 filtered_text,
                                                 font=font,
                                                 anchor='mm',
                                                 stroke_width=stroke_width)
        w = right - left
        h = bottom - top
        if w + HORIZNOTAL_MARGIN >= width or h + VERTICAL_MARGIN >= height:
            size -= 1
            font = ImageFont.truetype(font_filepath, size)
            stroke_width = max(3, size // 10)
            break

    # NOTE: Besides the efforts to draw the text in the middle of the image, it's still slightly
    # misaligned. This could be Pillow's fault, or flaws in the font file. To ensure that it's
    # centered, and that it's not cropped slightly in any edge, it will be drawn on a slightly
    # larger canvas, then stripped, then pasted in the center of an empty canvas with the final
    # size, and then composited with the final background color.

    TEXT_IMAGE_MARGIN = 50

    text_image = Image.new('RGBA', (width + TEXT_IMAGE_MARGIN, height + TEXT_IMAGE_MARGIN))
    draw = ImageDraw.Draw(text_image)
    draw.text(((width + TEXT_IMAGE_MARGIN) // 2, (height + TEXT_IMAGE_MARGIN) // 2),
              filtered_text,
              font=font,
              anchor='mm',
              fill=(255, 255, 255, 255),
              stroke_width=stroke_width,
              stroke_fill=(0, 0, 0, 255))

    text_image = text_image.crop(text_image.getbbox())
    offset_x = (width - text_image.size[0]) // 2
    offset_y = (height - text_image.size[1]) // 2

    tmp_image = Image.new('RGBA', (width, height))
    tmp_image.paste(text_image, (offset_x, offset_y))

    image = Image.new('RGBA', (width, height), background)
    image = Image.alpha_composite(image, tmp_image)

    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        tmp_filepath = os.path.join(tmp_dir,
                                    f'{os.path.splitext(os.path.basename(filepath))[0]}.png')
        image.save(tmp_filepath)

        remove_file(filepath)  # It may be a hard link; unlink early.

        convert_png_to_bti(tmp_filepath, filepath, image_format)


def downscale_bti_image(image_size: 'tuple[int]', image_format: str, filepath: str):
    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        png_tmp_filepath = os.path.join(tmp_dir,
                                        os.path.splitext(os.path.basename(filepath))[0] + '.png')

        failed = False
        try:
            convert_bti_to_png(filepath, png_tmp_filepath)
        except Exception:
            failed = True
        if not os.path.isfile(png_tmp_filepath):
            failed = True
        if failed:
            # If the attempt fails (unlikely but possible), we won't be able to downscale the BTI
            # image, and that cannot be allowed, or else the size of the archive would grow too
            # great. If neither `wimgt`` nor the `bti`` module succeeded on converting the image,
            # this is considered fatal.
            raise MKDDExtenderError(f'Unable to convert BTI image to PNG ("{filepath}") Image '
                                    'cannot be downscaled.')

        with Image.open(png_tmp_filepath) as image:
            if image.size[0] <= image_size[0] and image.size[1] <= image_size[1]:
                return
            downscaled_image = image.resize(image_size,
                                            resample=RESAMPLING_FILTER,
                                            reducing_gap=3.0)
        downscaled_image.save(png_tmp_filepath)

        remove_file(filepath)  # It may be a hard link; unlink early.

        convert_png_to_bti(png_tmp_filepath, filepath, image_format)


def conform_audio_file(filepath: str, mix_to_mono: bool, downsample_sample_rate: int):
    if not mix_to_mono and not downsample_sample_rate:
        return

    ast_info = ast_converter.get_ast_info(filepath)

    bit_depth = ast_info['bit_depth']
    channel_count = ast_info['channel_count']
    sample_rate = ast_info['sample_rate']

    if channel_count not in (1, 2, 4):
        raise MKDDExtenderError(f'Unsupported channel count ({channel_count}) in "{filepath}". '
                                'Expected 1, 2, or 4 channels.')

    needs_mixing = mix_to_mono and channel_count != 1
    needs_downsampling = downsample_sample_rate and sample_rate != downsample_sample_rate

    if not needs_mixing and not needs_downsampling:
        return

    log.info(f'Conforming audio file ("{filepath}")...')

    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
        wav_filepath = os.path.join(tmp_dir,
                                    os.path.splitext(os.path.basename(filepath))[0] + '.wav')
        ast_converter.convert_to_wav(filepath, wav_filepath)

        with wave.open(wav_filepath, 'rb') as f:
            real_sample_count = f.getnframes()
            data = f.readframes(real_sample_count)

        if needs_mixing:
            if channel_count == 4:
                data = audioop.tomono(data, bit_depth // 8, 0.5, 0.5)
                channel_count = 2
            if channel_count == 2:
                data = audioop.tomono(data, bit_depth // 8, 0.5, 0.5)
                channel_count = 1

        sample_rate_ratio = 1
        if needs_downsampling:
            data, _state = audioop.ratecv(data, bit_depth // 8, channel_count, sample_rate,
                                          downsample_sample_rate, None)
            sample_rate_ratio = downsample_sample_rate / sample_rate
            sample_rate = downsample_sample_rate

        with wave.open(wav_filepath, 'wb') as f:
            f: wave.Wave_write
            f.setsampwidth(bit_depth // 8)
            f.setnchannels(channel_count)
            f.setframerate(sample_rate)
            f.writeframes(data)
            new_real_sample_count = f.getnframes()

        sample_count = ast_info['sample_count']
        loop_start = ast_info['loop_start']
        loop_end = ast_info['loop_end']

        sample_count = min(new_real_sample_count, round(sample_rate_ratio * sample_count))
        loop_start = min(new_real_sample_count, round(sample_rate_ratio * loop_start))
        loop_end = min(new_real_sample_count, round(sample_rate_ratio * loop_end))

        # If the audio has been resampled, let the last block size be auto-determined.
        last_block_size = ast_info['last_block_size'] if sample_rate_ratio == 1 else None

        remove_file(filepath)  # It may be a hard link; unlink early.

        ast_converter.convert_to_ast(wav_filepath,
                                     filepath,
                                     looped=ast_info['looped'],
                                     sample_count=sample_count,
                                     loop_start=loop_start,
                                     loop_end=loop_end,
                                     volume=ast_info['volume'],
                                     last_block_size=last_block_size)


def patch_bnr_file(iso_tmp_dir: str):
    files_dirpath = os.path.join(iso_tmp_dir, 'files')
    bnr_filepath = os.path.join(files_dirpath, 'opening.bnr')

    checksum = md5sum(bnr_filepath)
    if checksum == '1b187557206eb4ea072a4882f37a4966':
        region = 'E'
    elif checksum == '953470f151856f512fc08ef36cc872e6':
        region = 'P'
    elif checksum == 'a5315f8bdd9bc56331bac1a6af5e195c':
        region = 'J'
    else:
        region = None

    # Replace the image data with the pre-generated raw data. The raw data was generated with the
    # `bnrparser.py` tool (part of pyisotools), after converting the `banner.png` file and isolating
    # the image data (bytes between 0x0020 and 0x1820).

    log.info(f'Replacing banner image in BNR file ("{bnr_filepath}")...')

    raw_filepath = os.path.join(data_dir, 'banner', 'banner.raw')
    with open(raw_filepath, 'rb') as f:
        raw_data = f.read()

    IMAGE_OFFSET = 0x0020
    IMAGE_LENGTH = 0x1800

    with open(bnr_filepath, 'r+b') as f:
        f.seek(IMAGE_OFFSET)
        f.write(raw_data)
        assert f.tell() == IMAGE_OFFSET + IMAGE_LENGTH

    log.info('Banner image replaced.')

    if region is None:
        log.warning('Unrecognized BNR file. Game title will not be modified.')
        return

    log.info(f'Tweaking game title in BNR file ("{bnr_filepath}")...')

    # If the BNR file is an original, "Extended!!" will be appended to the game title (or titles, in
    # the PAL version).

    with open(bnr_filepath, 'rb') as f:
        data = bytearray(f.read())

    TITLE_OFFSET = 0x1860
    NEXT_TITLE_OFFSET_STEP = 0x0140

    title_offsets = []
    for title_offset in range(TITLE_OFFSET, len(data), NEXT_TITLE_OFFSET_STEP):
        title_offsets.append(title_offset)

    if region != 'J':
        EXCLAMATION_MARKS = b'!!'
        LABEL = b' Extended!!'
    else:
        EXCLAMATION_MARKS = bytes((0x81, 0x49, 0x81, 0x49))
        LABEL = b'\x20\x83G\x83N\x83X\x83e\x83\x93\x83h' + bytes((0x81, 0x49, 0x81, 0x49))

    for title_offset in title_offsets:
        title_end_idx = data.find(EXCLAMATION_MARKS, title_offset) + len(EXCLAMATION_MARKS)
        for i, c in enumerate(LABEL):
            data[title_end_idx + i] = c

    with open(bnr_filepath, 'wb') as f:
        f.write(data)

    log.info('Game title tweaked.')


def patch_title_lines(args: argparse.Namespace, iso_tmp_dir: str):
    files_dirpath = os.path.join(iso_tmp_dir, 'files')
    scenedata_dirpath = os.path.join(files_dirpath, 'SceneData')

    log.info('Patching title lines...')

    for language in LANGUAGES:
        language_dirpath = os.path.join(scenedata_dirpath, language)
        if not os.path.isdir(language_dirpath):
            continue

        titleline_dirpath = os.path.join(language_dirpath, 'titleline')
        timg_dir = os.path.join(titleline_dirpath, 'timg')
        scrn_dir = os.path.join(titleline_dirpath, 'scrn')

        for title_filename in ('selectcourse.bti', 'selectcup.bti'):
            title_filepath = os.path.join(timg_dir, title_filename)
            log.info(f'Modifying {title_filepath}...')
            add_controls_to_title_image(args, title_filepath, language)

        # Gradient colors are specified in the BLO file, which we want to avoid in the controls
        # icons. Also, avoid the game blurrying the images.
        menu_title_line_blo_filepath = os.path.join(scrn_dir, 'menu_title_line.blo')

        log.info(f'Patching BLO file ("{menu_title_line_blo_filepath}")...')

        with open(menu_title_line_blo_filepath, 'r+b') as f:
            # For some reason, the game was setting the dimensions to 654x38, but the actual
            # resolution of the BTI files is 512x32. This was making the text blurry unnecessarily,
            # and we can use the extra space gain for the controls icon.
            f.seek(0x22C8)
            width, height = struct.unpack('>ff', f.read(4 * 2))
            if (width, height) == (654.0, 38.0):
                f.seek(0x22C8)
                f.write(struct.pack('>ff', 512.0, 32.0))
            else:
                log.warning('Unexpected dimensions in BLO file. Titles\' dimensions will not be '
                            'updated.')

            # Each corner has its own color, although only the two at the top (the first
            # two) were yellow.
            f.seek(0x2310)
            top_left, top_right, bottom_left, bottom_right = struct.unpack('>LLLL', f.read(4 * 4))
            if (top_left, top_right, bottom_left, bottom_right) == (0xFFFF00FF, 0xFFFF00FF,
                                                                    0xFFFFFFFF, 0xFFFFFFFF):
                f.seek(0x2310)
                f.write(struct.pack('>LLLL', 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF))
            else:
                log.warning('Unexpected colors in BLO file. Titles\' color gradient will not be '
                            'desaturated.')

    log.info('Title lines patched.')


def with_page_index_suffix(page_index: int, path: str) -> str:
    stem, ext = os.path.splitext(path)
    stem = stem[:-len(str(page_index))] + str(page_index)
    return stem + ext


def patch_cup_names(args: argparse.Namespace, page_count: int, iso_tmp_dir: str):
    files_dirpath = os.path.join(iso_tmp_dir, 'files')
    scenedata_dirpath = os.path.join(files_dirpath, 'SceneData')

    log.info('Patching cup names...')

    for language in LANGUAGES:
        language_dirpath = os.path.join(scenedata_dirpath, language)
        if not os.path.isdir(language_dirpath):
            continue

        courseselect_dirpath = os.path.join(language_dirpath, 'courseselect')
        timg_dir = os.path.join(courseselect_dirpath, 'timg')

        cupname_filenames = ('cupname_flower_cup.bti', 'cupname_mushroom_cup.bti',
                             'cupname_reverse2_cup.bti', 'cupname_special_cup.bti',
                             'cupname_star_cup.bti')

        for cupname_filename in cupname_filenames:
            cupname_filepath = os.path.join(timg_dir, cupname_filename)
            log.info(f'Modifying {cupname_filepath}...')

            if not args.legacy_gecko_codes:
                new_cupname_filepath = with_page_index_suffix(0, cupname_filepath)
                os.rename(cupname_filepath, new_cupname_filepath)
                cupname_filepath = new_cupname_filepath

            for page_index in range(page_count - 1):
                if not args.legacy_gecko_codes:
                    page_index += 1

                page_cupname_filepath = with_page_index_suffix(page_index, cupname_filepath)
                make_link(cupname_filepath, page_cupname_filepath)

                if not args.skip_cup_names:
                    if args.legacy_gecko_codes:
                        add_dpad_to_cup_name_image(page_cupname_filepath, page_index)
                    else:
                        add_page_number_to_cup_name_image(page_cupname_filepath, page_index + 1,
                                                          page_count)
                make_link(page_cupname_filepath,
                          page_cupname_filepath.replace('courseselect', 'lanplay'))

            if not args.skip_cup_names:
                if args.legacy_gecko_codes:
                    add_dpad_to_cup_name_image(cupname_filepath, -1)
                else:
                    add_page_number_to_cup_name_image(cupname_filepath, 1, page_count)
            make_link(cupname_filepath, cupname_filepath.replace('courseselect', 'lanplay'))

    log.info('Cup names patched.')


def meld_courses(args: argparse.Namespace, iso_tmp_dir: str) -> 'tuple[dict | list]':
    minimap_data = {}
    alternative_audio_data = {}
    matching_audio_override_data = {}
    added_course_names = []

    files_dirpath = os.path.join(iso_tmp_dir, 'files')

    stream_dirpath = os.path.join(files_dirpath, 'AudioRes', 'Stream')
    course_dirpath = os.path.join(files_dirpath, 'Course')
    coursename_dirpath = os.path.join(files_dirpath, 'CourseName')
    staffghosts_dirpath = os.path.join(files_dirpath, 'StaffGhosts')
    scenedata_dirpath = os.path.join(files_dirpath, 'SceneData')

    if isinstance(args.tracks, str):
        paths = tuple(os.path.join(args.tracks, p) for p in sorted(os.listdir(args.tracks)))
        tracks_is_dir = True
    elif isinstance(args.tracks, collections.abc.Sequence) and args.tracks:
        if len(args.tracks) % 16 != 0:
            raise MKDDExtenderError(
                f'Number of items in the `tracks` argument not a multiple of 16: {args.tracks}')
        paths = args.tracks
        tracks_is_dir = False
    else:
        raise MKDDExtenderError('Unexpected value in `tracks` argument.')

    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tracks_tmp_dir:
        # Unpack ZIP archives (or copy directory is pre-unpacked) to their respective directories.
        prefix_to_nodename = {}
        processed = 0
        log.info('Preparing custom tracks...')
        if tracks_is_dir:
            for prefix in PREFIXES:
                for path in paths:
                    filename = os.path.basename(path)
                    if filename.startswith(prefix):
                        track_dirpath = os.path.join(tracks_tmp_dir, prefix)
                        log.info(f'Extracting and flattening "{path}" into "{track_dirpath}"...')
                        extract_and_flatten(path, track_dirpath)
                        prefix_to_nodename[prefix] = filename
                        processed += 1
                        break
                else:
                    # Check whether full pages have been sourced on the first missing prefix.
                    if prefix_to_nodename and len(prefix_to_nodename) % 16 == 0:
                        break

                    raise MKDDExtenderError(f'No track assigned to slot {prefix}.')
        else:
            for i, path in enumerate(paths):
                prefix = PREFIXES[i]
                filename = os.path.basename(path)
                track_dirpath = os.path.join(tracks_tmp_dir, prefix)
                log.info(f'Extracting and flattening "{path}" into "{track_dirpath}"...')
                extract_and_flatten(path, track_dirpath)
                prefix_to_nodename[prefix] = filename
                processed += 1
        if processed > 0:
            log.info(f'{processed} custom tracks have been processed.')
        else:
            log.warning('No archive has been processed.')
        if args.legacy_gecko_codes and processed != 48:
            raise MKDDExtenderError(
                'With the legacy Gecko codes, exactly 48 custom tracks are required.')

        extra_page_count = len(prefix_to_nodename) // 16
        total_page_count = extra_page_count + 1

        # RARC file gets too large, and causes a crash. Reducing image size is a workaround.
        # However, if extended memory has been set, the retail dimensions can be used instead.
        PREVIEW_IMAGE_SIZE = 256, 184
        LABEL_IMAGE_SIZE = 256, 32
        if not args.extended_memory:
            if total_page_count <= 2:
                preview_image_factor = 1
            else:
                preview_image_factor = 2 / total_page_count
            preview_image_size = (round(PREVIEW_IMAGE_SIZE[0] * preview_image_factor),
                                  round(PREVIEW_IMAGE_SIZE[1] * preview_image_factor))

            if total_page_count <= 7:
                label_image_factor = 1
            else:
                label_image_factor = 7 / total_page_count
            label_image_size = (round(LABEL_IMAGE_SIZE[0] * label_image_factor),
                                round(LABEL_IMAGE_SIZE[1] * label_image_factor))
        else:
            preview_image_size = PREVIEW_IMAGE_SIZE
            label_image_size = LABEL_IMAGE_SIZE

        downscale_preview_images = tuple(preview_image_size) != PREVIEW_IMAGE_SIZE
        downscale_label_images = tuple(label_image_size) != LABEL_IMAGE_SIZE

        # Populate dictionary with checksums from all the stock AST files.
        audio_tracks_checksums = {}
        for filename in os.listdir(stream_dirpath):
            ast_filepath = os.path.join(stream_dirpath, filename)
            checksum = md5sum(ast_filepath)
            audio_tracks_checksums[checksum] = filename

        # Rename original directories if needed.
        if not args.legacy_gecko_codes:
            new_course_dirpath = with_page_index_suffix(0, course_dirpath)
            new_coursename_dirpath = with_page_index_suffix(0, coursename_dirpath)
            new_staffghosts_dirpath = with_page_index_suffix(0, staffghosts_dirpath)
            os.rename(course_dirpath, new_course_dirpath)
            os.rename(coursename_dirpath, new_coursename_dirpath)
            os.rename(staffghosts_dirpath, new_staffghosts_dirpath)
            course_dirpath = new_course_dirpath
            coursename_dirpath = new_coursename_dirpath
            staffghosts_dirpath = new_staffghosts_dirpath

        # Copy files into the ISO temporariy directory.
        log.info('Melding directories...')
        melded = 0
        for prefix in PREFIXES[:len(prefix_to_nodename)]:
            track_dirpath = os.path.join(tracks_tmp_dir, prefix)
            page_index = ord(prefix[0]) - ord('A')
            if not args.legacy_gecko_codes:
                page_index += 1
            track_index = int(prefix[1:3]) - 1
            assert 0 <= track_index <= 15

            nodename = prefix_to_nodename[prefix]

            log.info(f'Melding "{nodename}" ("{track_dirpath}")...')
            melded += 1

            page_course_dirpath = with_page_index_suffix(page_index, course_dirpath)
            page_coursename_dirpath = with_page_index_suffix(page_index, coursename_dirpath)
            page_staffghosts_dirpath = with_page_index_suffix(page_index, staffghosts_dirpath)

            # Start off with a copy of the original directories. Relevant files will be replaced
            # next.
            if not os.path.isdir(page_course_dirpath):
                shutil.copytree(course_dirpath, page_course_dirpath, copy_function=make_link)
            if not os.path.isdir(page_coursename_dirpath):
                shutil.copytree(coursename_dirpath,
                                page_coursename_dirpath,
                                copy_function=make_link)
            if not os.path.isdir(page_staffghosts_dirpath):
                shutil.copytree(staffghosts_dirpath,
                                page_staffghosts_dirpath,
                                copy_function=make_link)

            # Parse INI file.
            try:
                trackinfo_filepath = os.path.join(track_dirpath, 'trackinfo.ini')
                trackinfo = configparser.ConfigParser()
                trackinfo.read(trackinfo_filepath)
                trackname = trackinfo['Config']['trackname'] or 'Unnamed'
                main_language = trackinfo['Config']['main_language']
                replaces = trackinfo['Config'].get('replaces')
                auxiliary_audio_track = trackinfo['Config'].get('auxiliary_audio_track')
            except Exception:
                log.warning(f'Unable to locate `trackinfo.ini` in "{nodename}", or it is missing '
                            'the `trackname` field or `main_language` field.')
                trackinfo = None
                trackname = prefix
                main_language = None
                replaces = None
                auxiliary_audio_track = None

            added_course_names.append(trackname)

            if auxiliary_audio_track:
                alternative_audio_data[prefix] = course_name_to_course(auxiliary_audio_track)
            elif replaces:
                alternative_audio_data[prefix] = course_name_to_course(replaces)

            # Copy course files.
            track_filepath = os.path.join(track_dirpath, 'track.arc')
            if not os.path.isfile(track_filepath):
                raise MKDDExtenderError(f'Unable to locate `track.arc` file in "{nodename}".')
            track_mp_filepath = os.path.join(track_dirpath, 'track_mp.arc')
            if not os.path.isfile(track_mp_filepath):
                track_mp_filepath = track_filepath
            else:
                log.info(f'Located `track_mp.arc` file in "{nodename}".')
            if track_index == 0:
                track_50cc_filepath = os.path.join(track_dirpath, 'track_50cc.arc')
                if not os.path.isfile(track_50cc_filepath):
                    track_50cc_filepath = track_filepath
                else:
                    log.info(f'Located `track_50cc.arc` file in "{nodename}".')
                track_mp_50cc_filepath = os.path.join(track_dirpath, 'track_mp_50cc.arc')
                if not os.path.isfile(track_mp_50cc_filepath):
                    track_mp_50cc_filepath = track_mp_filepath
                else:
                    log.info(f'Located `track_mp_50cc.arc` file in "{nodename}".')
            if track_index == 0:
                page_track_filepath = os.path.join(page_course_dirpath,
                                                   f'{COURSES[track_index]}2.arc')
                page_track_mp_filepath = os.path.join(page_course_dirpath,
                                                      f'{COURSES[track_index]}2L.arc')
                page_track_50cc_filepath = os.path.join(page_course_dirpath,
                                                        f'{COURSES[track_index]}.arc')
                page_track_mp_50cc_filepath = os.path.join(page_course_dirpath,
                                                           f'{COURSES[track_index]}L.arc')
                make_link(track_filepath, page_track_filepath)
                make_link(track_mp_filepath, page_track_mp_filepath)
                make_link(track_50cc_filepath, page_track_50cc_filepath)
                make_link(track_mp_50cc_filepath, page_track_mp_50cc_filepath)

                patch_music_id_in_bol_file(page_track_filepath, track_index)
                patch_music_id_in_bol_file(page_track_mp_filepath, track_index)
                patch_music_id_in_bol_file(page_track_50cc_filepath, track_index)
                patch_music_id_in_bol_file(page_track_mp_50cc_filepath, track_index)

                repack_course_arc_file(page_track_filepath, f'{COURSES[track_index].lower()}2')
                repack_course_arc_file(page_track_mp_filepath, f'{COURSES[track_index].lower()}2l')
                repack_course_arc_file(page_track_50cc_filepath, f'{COURSES[track_index].lower()}')
                repack_course_arc_file(page_track_mp_50cc_filepath,
                                       f'{COURSES[track_index].lower()}l')
            else:
                page_track_filepath = os.path.join(page_course_dirpath,
                                                   f'{COURSES[track_index]}.arc')
                page_track_mp_filepath = os.path.join(page_course_dirpath,
                                                      f'{COURSES[track_index]}L.arc')
                make_link(track_filepath, page_track_filepath)
                make_link(track_mp_filepath, page_track_mp_filepath)

                patch_music_id_in_bol_file(page_track_filepath, track_index)
                patch_music_id_in_bol_file(page_track_mp_filepath, track_index)

                repack_course_arc_file(page_track_filepath, f'{COURSES[track_index].lower()}')
                repack_course_arc_file(page_track_mp_filepath, f'{COURSES[track_index].lower()}l')

            # Copy GHT file.
            ght_filepath = os.path.join(track_dirpath, 'staffghost.ght')
            if os.path.isfile(ght_filepath):
                page_ght_filepath = os.path.join(page_staffghosts_dirpath,
                                                 f'{COURSES[track_index]}.ght')
                make_link(ght_filepath, page_ght_filepath)
            else:
                log.warning(f'Unable to locate `staffghost.ght` file in "{nodename}".')

            # Force use of auxiliary audio track if argument has been provided and the custo track
            # has the field defined.
            use_auxiliary_audio_track = auxiliary_audio_track and args.use_auxiliary_audio_track
            use_replacee_audio_track = replaces and args.use_replacee_audio_track
            use_alternative_audio_track = use_auxiliary_audio_track or use_replacee_audio_track

            def conform_and_copy_if_not_cached(src_ast_filepath, dst_ast_filepath, args):
                # Before copying a AST file to destination, check whether its checksum already
                # exists, and, if so, insert an entry in the override table instead of copying the
                # file over.

                checksum = md5sum(src_ast_filepath)
                dst_ast_filename = os.path.basename(dst_ast_filepath)

                if checksum in audio_tracks_checksums:
                    cached_filename = audio_tracks_checksums[checksum]
                    matching_audio_override_data[dst_ast_filename] = cached_filename
                    log.info(f'Reusing "{dst_ast_filename}" in place of "{cached_filename}" '
                             f'(shared checksum: "{checksum})."')
                    return

                audio_tracks_checksums[checksum] = dst_ast_filename

                make_link(src_ast_filepath, dst_ast_filepath)
                conform_audio_file(dst_ast_filepath, args.mix_to_mono, args.sample_rate)

            if not use_alternative_audio_track:
                # Copy audio files. Unlike with the previous files, audio files are stored in the
                # stock directory. The names of the audio files strategically start with a "X_"
                # prefix to ensure they are inserted after the stock audio files.
                lap_music_normal_filepath = os.path.join(track_dirpath, 'lap_music_normal.ast')
                if not os.path.isfile(lap_music_normal_filepath):
                    # If there is only the fast version (single-lap course?), it will be used for
                    # both, and no warning is needed.
                    lap_music_normal_filepath = os.path.join(track_dirpath, 'lap_music_fast.ast')
                if os.path.isfile(lap_music_normal_filepath):
                    dst_ast_filepath = os.path.join(stream_dirpath, f'X_COURSE_{prefix}.ast')
                    conform_and_copy_if_not_cached(lap_music_normal_filepath, dst_ast_filepath,
                                                   args)

                    lap_music_fast_filepath = os.path.join(track_dirpath, 'lap_music_fast.ast')
                    if os.path.isfile(lap_music_fast_filepath):
                        dst_ast_filepath = os.path.join(stream_dirpath, f'X_FINALLAP_{prefix}.ast')
                        conform_and_copy_if_not_cached(lap_music_fast_filepath, dst_ast_filepath,
                                                       args)
                    else:
                        log.warning(f'Unable to locate `lap_music_fast.ast` in "{nodename}". '
                                    '`lap_music_normal.ast` will be used.')
                else:
                    if auxiliary_audio_track:
                        course_name = COURSE_TO_NAME[course_name_to_course(auxiliary_audio_track)]
                        log.info(
                            f'Unable to locate `lap_music_normal.ast` in "{nodename}". Auxiliary '
                            f'audio track ("{course_name}") will be used.')
                    elif replaces:
                        course_name = COURSE_TO_NAME[course_name_to_course(replaces)]
                        log.info(
                            f'Unable to locate `lap_music_normal.ast` in "{nodename}". Replacee\'s '
                            f'audio track ("{course_name}") will be used.')
                    else:
                        log.warning(
                            f'Unable to locate `lap_music_normal.ast` in "{nodename}". Luigi '
                            'Circuit\'s sound track will be used.')
            else:
                if auxiliary_audio_track:
                    course_name = COURSE_TO_NAME[course_name_to_course(auxiliary_audio_track)]
                    log.info(f'Auxiliary audio track ("{course_name}") will be used.')
                else:
                    course_name = COURSE_TO_NAME[course_name_to_course(replaces)]
                    log.info(f'Replacee\'s audio track ("{course_name}") will be used.')

            course_images_dirpath = os.path.join(track_dirpath, 'course_images')

            def find_or_generate_image_path(language: str, filename: str, width: int, height: int,
                                            image_format: str,
                                            background: 'tuple[int, int, int, int]') -> str:
                # pylint: disable=cell-var-from-loop

                filepath = os.path.join(course_images_dirpath, language, filename)
                if os.path.isfile(filepath):
                    return filepath

                if main_language:
                    filepath = os.path.join(course_images_dirpath, main_language, filename)
                    if os.path.isfile(filepath):
                        # No need to generate warning in this case. This is acceptable.
                        return filepath

                for l in LANGUAGES:
                    filepath = os.path.join(course_images_dirpath, l, filename)
                    if os.path.isfile(filepath):
                        log.warning(f'Unable to locate `{filename}` in "{nodename}" for '
                                    f'current language ({language}). Image for {l} will be used.')
                        return filepath

                log.warning(f'Unable to locate `{filename}` in "{nodename}" for {language}. '
                            'An auto-generated image will be provided.')

                filepath = os.path.join(course_images_dirpath, language, filename)
                generate_bti_image_from_bitmap_font(trackname, width, height, image_format,
                                                    background, filepath)
                return filepath

            # Copy course logo.
            expected_languages = os.listdir(page_coursename_dirpath)
            expected_languages = tuple(l for l in LANGUAGES if l in expected_languages)
            if not expected_languages:
                raise MKDDExtenderError(f'Unable to locate language directories in "{nodename}" '
                                        'for course logo.')
            for language in expected_languages:
                logo_filepath = find_or_generate_image_path(language, 'track_big_logo.bti', 208,
                                                            104, 'RGB5A3', (0, 0, 0, 0))

                page_coursename_language_dirpath = os.path.join(page_coursename_dirpath, language)
                os.makedirs(page_coursename_language_dirpath, exist_ok=True)

                page_coursename_filepath = os.path.join(page_coursename_language_dirpath,
                                                        f'{COURSES[track_index]}_name.bti')
                make_link(logo_filepath, page_coursename_filepath)

            expected_languages = os.listdir(scenedata_dirpath)
            expected_languages = tuple(l for l in LANGUAGES if l in expected_languages)
            if not expected_languages:
                raise MKDDExtenderError('Unable to locate `SceneData/language` directories in '
                                        f'"{nodename}".')

            preview_filename = f'cop_{COURSE_TO_PREVIEW_IMAGE_NAME[COURSES[track_index]]}.bti'
            label_filename = f'coname_{COURSE_TO_LABEL_IMAGE_NAME[COURSES[track_index]]}.bti'

            # Rename original directories if needed.
            if not args.legacy_gecko_codes:
                new_preview_filename = with_page_index_suffix(0, preview_filename)
                new_label_filename = with_page_index_suffix(0, label_filename)

                if page_index == 1:
                    for language in expected_languages:
                        courseselect_dirpath = os.path.join(scenedata_dirpath, language,
                                                            'courseselect', 'timg')
                        lanplay_dirpath = os.path.join(scenedata_dirpath, language, 'lanplay',
                                                       'timg')
                        os.rename(os.path.join(courseselect_dirpath, preview_filename),
                                  os.path.join(courseselect_dirpath, new_preview_filename))
                        os.rename(os.path.join(courseselect_dirpath, label_filename),
                                  os.path.join(courseselect_dirpath, new_label_filename))
                        os.rename(os.path.join(lanplay_dirpath, label_filename),
                                  os.path.join(lanplay_dirpath, new_label_filename))

                preview_filename = new_preview_filename
                label_filename = new_label_filename

            # Copy preview image and label image.
            page_preview_filename = with_page_index_suffix(page_index, preview_filename)
            page_label_filename = with_page_index_suffix(page_index, label_filename)
            for language in expected_languages:
                courseselect_dirpath = os.path.join(scenedata_dirpath, language, 'courseselect',
                                                    'timg')
                lanplay_dirpath = os.path.join(scenedata_dirpath, language, 'lanplay', 'timg')

                preview_filepath = find_or_generate_image_path(language, 'track_image.bti',
                                                               *preview_image_size, 'CMPR',
                                                               (0, 0, 0, 255))
                page_preview_filepath = os.path.join(courseselect_dirpath, page_preview_filename)
                make_link(preview_filepath, page_preview_filepath)

                label_filepath = find_or_generate_image_path(language, 'track_name.bti',
                                                             *label_image_size, 'IA4', (0, 0, 0, 0))
                page_label_filepath = os.path.join(courseselect_dirpath, page_label_filename)
                make_link(label_filepath, page_label_filepath)
                page_label_filepath = os.path.join(lanplay_dirpath, page_label_filename)
                make_link(label_filepath, page_label_filepath)

            # Gather minimap values.
            minimap_filepath = os.path.join(track_dirpath, 'minimap.json')
            try:
                with open(minimap_filepath, 'r', encoding='ascii') as f:
                    minimap_json = json.loads(f.read())
                minimap_data[(page_index, track_index)] = (
                    float(minimap_json['Top Left Corner X']),
                    float(minimap_json['Top Left Corner Z']),
                    float(minimap_json['Bottom Right Corner X']),
                    float(minimap_json['Bottom Right Corner Z']),
                    int(minimap_json['Orientation']),
                )
            except Exception as e:
                raise MKDDExtenderError(f'Unable to parse minimap data in "{nodename}": '
                                        f'{str(e)}.') from e

        # Downscale images to ensure space limits are met.
        if downscale_preview_images:
            log.info(
                f'Downscaling preview images to {preview_image_size[0]}x{preview_image_size[1]}...')

            for language in LANGUAGES:
                courseselect_dirpath = os.path.join(scenedata_dirpath, language, 'courseselect',
                                                    'timg')
                if os.path.isdir(courseselect_dirpath):
                    for filename in os.listdir(courseselect_dirpath):
                        if filename.startswith('cop_') and filename.endswith('.bti'):
                            filepath = os.path.join(courseselect_dirpath, filename)
                            downscale_bti_image(preview_image_size, 'CMPR', filepath)
        if downscale_label_images:
            log.info(f'Downscaling label images to {label_image_size[0]}x{label_image_size[1]}...')

            for language in LANGUAGES:
                courseselect_dirpath = os.path.join(scenedata_dirpath, language, 'courseselect',
                                                    'timg')
                if os.path.isdir(courseselect_dirpath):
                    for filename in os.listdir(courseselect_dirpath):
                        if filename.startswith('coname_') and filename.endswith('.bti'):
                            filepath = os.path.join(courseselect_dirpath, filename)
                            downscale_bti_image(label_image_size, 'IA4', filepath)

        if melded > 0:
            log.info(f'{melded} directories melded.')
        else:
            log.warning('No directory has been melded.')

    return minimap_data, alternative_audio_data, matching_audio_override_data, added_course_names


def gather_audio_file_indices(args: argparse.Namespace, iso_tmp_dir: str,
                              alternative_audio_data: 'dict[str, str]',
                              matching_audio_override_data: 'dict[str, str]') -> tuple:
    # The Gecko code generator needs the list of 32 integers with the file index of each audio track
    # mapped to each track.

    file_list = build_file_list(iso_tmp_dir)

    COURSE_STREAM_ORDER = {
        'BabyLuigi': ('BABY', ),
        'Peach': ('BEACH', ),
        'Daisy': ('CRUISER', 'BEACH'),  # With fallback.
        'Luigi': ('CIRCUIT', ),
        'Mario': ('MCIRCUIT', 'CIRCUIT'),  # With fallback.
        'Yoshi': ('YCIRCUIT', 'CIRCUIT'),  # With fallback.
        'Nokonoko': ('HIWAY', ),
        'Patapata': ('CITY', 'HIWAY'),  # With fallback.
        'Waluigi': ('STADIUM', ),
        'Wario': ('COLOSSEUM', 'STADIUM'),  # With fallback.
        'Diddy': ('JUNGLE', ),
        'Donkey': ('MOUNTAIN', 'JUNGLE'),  # With fallback.
        'Koopa': ('CASTLE', ),
        'Rainbow': ('RAINBOW', ),
        'Desert': ('DESERT', ),
        'Snow': ('SNOW', ),
    }

    SPEED_TYPES = ('COURSE', 'FINALLAP')

    stock_audio_track_indices = []
    for speed_type in SPEED_TYPES:
        for _course, subnames in COURSE_STREAM_ORDER.items():
            filenames = tuple(f'{speed_type}_{subname}' for subname in subnames)
            for filename in filenames:
                appended = False
                for file_index, filepath in enumerate(file_list):
                    if filepath.endswith('.ast') and filename in filepath:
                        stock_audio_track_indices.append(file_index)
                        appended = True
                        break
                if appended:
                    break
            else:
                raise MKDDExtenderError('Unable to locate a valid audio track candidate in the '
                                        f'file list: {filenames}.')
    stock_audio_track_indices = tuple(stock_audio_track_indices)

    FALLBACK_AUDIO_COURSE = 'Luigi'
    course_stream_order = tuple(COURSE_STREAM_ORDER.keys())
    fallback_index = stock_audio_track_indices[course_stream_order.index(FALLBACK_AUDIO_COURSE)]
    fallback_finallap_index = stock_audio_track_indices[
        course_stream_order.index(FALLBACK_AUDIO_COURSE) + 16]

    extra_page_count = len(alternative_audio_data) // 16

    audio_track_data = []
    for _ in range(extra_page_count):
        audio_track_data.append([fallback_index] * 16 + [fallback_finallap_index] * 16)
    audio_track_data.append(stock_audio_track_indices)

    for prefix, auxiliary_audio_track in alternative_audio_data.items():
        page_index = ord(prefix[0]) - ord('A')
        track_index = int(prefix[1:3]) - 1
        auxiliary_audio_index = course_stream_order.index(auxiliary_audio_track)
        mapped_offset = course_stream_order.index(COURSES[track_index])
        audio_track_data_page = audio_track_data[page_index]
        audio_track_data_page[mapped_offset] = stock_audio_track_indices[auxiliary_audio_index]
        audio_track_data_page[mapped_offset + 16] = \
            stock_audio_track_indices[auxiliary_audio_index + 16]

    for prefix in PREFIXES[:len(alternative_audio_data)]:
        page_index = ord(prefix[0]) - ord('A')
        track_index = int(prefix[1:3]) - 1
        assert 0 <= track_index <= 15

        for i, speed_type in enumerate(SPEED_TYPES):
            speed_type = f'X_{speed_type}'
            filename = f'{speed_type}_{prefix}.ast'

            if filename in matching_audio_override_data:
                filename = matching_audio_override_data[filename]

            for file_index, filepath in enumerate(file_list):
                if filepath.endswith('.ast') and filename in filepath:
                    mapped_offset = course_stream_order.index(COURSES[track_index])
                    audio_track_data[page_index][mapped_offset + i * 16] = file_index
                    break
            else:
                pass  # Fallback audio file index will be used.

    # Move stock indices to the front.
    if not args.legacy_gecko_codes:
        audio_track_data = [audio_track_data[-1]] + list(audio_track_data[:-1])

    return tuple(tuple(l) for l in audio_track_data)


def verify_dol_checksum(args: argparse.Namespace, iso_tmp_dir: str):
    sys_dirpath = os.path.join(iso_tmp_dir, 'sys')
    dol_path = os.path.join(sys_dirpath, 'main.dol')

    assert os.path.isfile(dol_path)

    checksum = md5sum(dol_path)
    if checksum not in (
            'edb478baec557381d10137035a72bdcc',  # GM4E01
            '3a8e73b977368d1e53293d36f634e3c7',  # GM4P01
            '81f1b05c6650d65326f757bb25bad604',  # GM4J01
            'bfb79b2e98fb632d863bb39cb3ca6e08',  # GM4E01 (debug)
    ):
        message = (f'DOL file ("{dol_path}") is not original. Unrecognized checksum: {checksum}.')
        if args.skip_dol_checksum_check:
            log.warning(message)
        else:
            raise MKDDExtenderError(f'{message} Re-run with --skip-dol-checksum-check to '
                                    'circumvent this safety measure.')


def patch_dol_file(args: argparse.Namespace, minimap_data: dict,
                   alternative_audio_data: 'dict[str, str]',
                   matching_audio_override_data: 'dict[str, str]', iso_tmp_dir: str):
    sys_dirpath = os.path.join(iso_tmp_dir, 'sys')
    dol_path = os.path.join(sys_dirpath, 'main.dol')
    bi2_path = os.path.join(sys_dirpath, 'bi2.bin')

    assert os.path.isfile(dol_path)
    assert os.path.isfile(bi2_path)

    with open(dol_path, 'rb') as f:
        data = f.read()
        game_id_offset = data.find(b'DOL-GM4')
        assert game_id_offset >= 0
        game_id_offset += len('DOL-')
        game_id = data[game_id_offset:game_id_offset + len('GM4x')] + b'01'
        game_id = game_id.decode('ascii')
        assert game_id in ('GM4E01', 'GM4P01', 'GM4J01')

    if game_id == 'GM4E01':
        boot_path = os.path.join(sys_dirpath, 'boot.bin')

        with open(boot_path, 'rb') as f:
            f.seek(0x23)
            DEBUG_BUILD_DATE = b'2004.07.05'
            data = f.read(len(DEBUG_BUILD_DATE))
            if data == DEBUG_BUILD_DATE:
                game_id += 'dbg'

    audio_track_data = gather_audio_file_indices(args, iso_tmp_dir, alternative_audio_data,
                                                 matching_audio_override_data)

    if not args.legacy_gecko_codes:
        code_patcher.patch_dol_file(game_id, minimap_data, audio_track_data, dol_path, log)

        for language in LANGUAGES:
            scenedata_dirpath = os.path.join(iso_tmp_dir, 'files', 'SceneData', language)
            if not os.path.isdir(scenedata_dirpath):
                continue
            for blo_path in (os.path.join(scenedata_dirpath, 'courseselect', 'scrn',
                                          'courseselect_under.blo'),
                             os.path.join(scenedata_dirpath, 'lanplay', 'scrn',
                                          'lanselectmode.blo')):
                log.info(f'Patching BLO file ("{blo_path}")...')
                code_patcher.patch_bti_filenames_in_blo_file(game_id, blo_path)

    if args.extended_memory:
        # The simulated memory size in the disk information header needs to be updated to the new
        # value. See http://hitmen.c02.at/files/yagcd/yagcd/chap13.html.
        # NOTE: The change in the `bi2.bin` file doesn't seem to be required. For correctness, and
        # in case it becomes relevant in the future, it will be updated regardless.
        ORIGINAL_SIMULATED_MEMORY_SIZE = 24 * 1024 * 1024
        EXTENDED_SIMULATED_MEMORY_SIZE = 32 * 1024 * 1024
        log.info('Simulated memory size will be extended from {} MiB to {} MiB...'.format(
            ORIGINAL_SIMULATED_MEMORY_SIZE // 1024 // 1024,
            EXTENDED_SIMULATED_MEMORY_SIZE // 1024 // 1024,
        ))
        with open(bi2_path, 'r+b') as f:
            f.seek(0x04)
            f.write(struct.pack('>L', EXTENDED_SIMULATED_MEMORY_SIZE))

        # In the DOL file, a heap needs to be extended from 6656 KiB to 10752 KiB. This value is
        # hardcoded in `SequenceApp::__ct()` (at `0x801d93c4` in the NTSC version) to `0x00680000`,
        # and will be changed to `0x00C80000`. The instruction is:
        #
        #   801d93dc 3c 80 00 68     lis        r4,0x68
        #
        # The instruction is pretty specific, and is unique in the instruction set (including the
        # debug build), so it can be replaced safely (assuming that the input DOL file is unedited).
        #
        # The instruction in the PAL version varies slightly. `SequenceApp::__ct()` is located at
        # `0x801d93a4`, which was found by searching for functions that look like the decompiled
        # function in Ghidra of the NTSC version (basically, sorting by number of instructions in
        # the **Functions** view, and comparing the decompiled source of functions of similar size).
        # In this case, the heap size is hardcoded to 6525 KiB (`0x0065F400`):
        #
        #   801d93b0 3c c0 00 66     lis        r6,0x66
        #   801d93b4 90 01 00 14     stw        r0,local_res4(r1)
        #   801d93b8 38 a4 0e d8     addi       r5=>s_Sequence_80340ed8,r4,0xed8      = "Sequence"
        #   801d93bc 38 86 f4 00     subi       r4,r6,0xc00
        #
        # Note that the value in PAL is set in two instructions. Only the first one will need to be
        # modified, though.
        ORIGINAL_HEAP_SIZE = 0x00680000 if game_id != 'GM4P01' else 0x0065F400
        EXTENDED_HEAP_SIZE = ORIGINAL_HEAP_SIZE + 0x00600000
        log.info('Heap memory size will be extended from {} KiB to {} KiB...'.format(
            ORIGINAL_HEAP_SIZE // 1024,
            EXTENDED_HEAP_SIZE // 1024,
        ))
        if game_id != 'GM4P01':
            ORIGINAL_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0x80, 0x00, 0x68))
            EXTENDED_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0x80, 0x00, 0xC8))
        else:
            ORIGINAL_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0xc0, 0x00, 0x66))
            EXTENDED_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0xc0, 0x00, 0xC6))
        with open(dol_path, 'rb') as f:
            data = f.read()
        assert data.count(ORIGINAL_HEAP_SIZE_INSTRUCTION) == 1
        offset = data.find(ORIGINAL_HEAP_SIZE_INSTRUCTION)
        with open(dol_path, 'r+b') as f:
            f.seek(offset)
            f.write(EXTENDED_HEAP_SIZE_INSTRUCTION)

        # NOTE: After this change, it will be mandatory to increase the emulated memory size in
        # Dolphin to 32 MiB, or else the game will crash to a green screen.

    if not args.skip_minimap_transforms_removal:
        # The game has some logic for modifying the scale and position of the minimaps. This logic
        # uses hardcoded float values for each course, and for each layout (1P, 2P, and 3P/4P).
        # Obviously, the hardcoded float values will not suit all custom tracks.
        #
        # The float values live in static memory, and it's uncertain from which places these values
        # are referenced; they cannot be changed. The MKDD Track Patcher modifies the `lfs`
        # instructions that load the float values to pick and choose some of the smaller values
        # among the available float values that are hardcoded in the static memory. This is tedious
        # work that we'd have to do implement with Gecko codes, and there is no guarantee that other
        # arbitrary numbers will be better (or worse).
        #
        # For the MKDD Extender, instead of replacing the `lfs` instructions, the setter functions
        # that store the values (`Race2DParam::setX()`, `Race2DParam::setY()`, and
        # `Race2DParam::setS()`) will be incapacitated (no-op). According to Ghidra, functions are
        # only used from `Race2D::__ct()`, and only for the purpose of setting the float values for
        # the minimap transforms.
        #
        # Luckily, the functions only have two instructions (`stfs` and `blr`), and match in all
        # regions. The first instruction will be turned into a no-op.

        FUNCTIONS_INSTRUCTIONS = bytes(
            (0xd0, 0x23, 0x00, 0x14, 0x4e, 0x80, 0x00, 0x20, 0xd0, 0x23, 0x00, 0x10, 0x4e, 0x80,
             0x00, 0x20, 0xd0, 0x23, 0x00, 0x0c, 0x4e, 0x80, 0x00, 0x20))

        NEW_FUNCTIONS_INSTRUCTIONS = bytes(
            (0x60, 0x00, 0x00, 0x00, 0x4e, 0x80, 0x00, 0x20, 0x60, 0x00, 0x00, 0x00, 0x4e, 0x80,
             0x00, 0x20, 0x60, 0x00, 0x00, 0x00, 0x4e, 0x80, 0x00, 0x20))

        log.info('Removing minimap transforms...')

        with open(dol_path, 'rb') as f:
            data = f.read()

        functions_offset = data.find(FUNCTIONS_INSTRUCTIONS)
        if functions_offset < 0:
            raise MKDDExtenderError(
                'Unable to locate minimap transforms functions in DOL file. Re-run with '
                '--skip-minimap-transforms-removal to proceed.')

        with open(dol_path, 'r+b') as f:
            f.seek(functions_offset)
            f.write(NEW_FUNCTIONS_INSTRUCTIONS)

    if args.legacy_gecko_codes:
        with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as tmp_dir:
            tmp_gecko_code_filepath = os.path.join(tmp_dir, 'gecko_code.txt')
            log.info(f'Generating Gecko codes to "{tmp_gecko_code_filepath}"...')

            gecko_code.write_code(game_id, dol_path, minimap_data, audio_track_data,
                                  tmp_gecko_code_filepath)

            log.info(f'Injecting Gecko code into "{dol_path}"...')

            cli = GeckoLoader.GeckoLoaderCli('GeckoLoader')
            args = cli.parse_args((dol_path, tmp_gecko_code_filepath, '--dest', dol_path,
                                   '--hooktype', 'GX', '--quiet'))
            # pylint: disable=protected-access
            cli._exec(args, tmp_dir)
            # pylint: enable=protected-access


def write_description_file(args: argparse.Namespace, added_course_names: 'list[str]',
                           iso_tmp_dir: str):
    lines = []

    lines.append('# MKDD Extender - Description File')
    lines.append('')
    lines.append('```')
    lines.append(f'Application version:  {__version__}')
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    lines.append(f'Creation time:        {timestamp}')
    lines.append('```')
    lines.append('')

    lines.append('## Options')
    lines.append('')
    option_lines = []
    for _group_name, group_options in OPTIONAL_ARGUMENTS.items():
        for option_label, option_type, _option_help in group_options:
            option_member_name = f'{option_label.lower().replace(" ", "_")}'
            option_value = getattr(args, option_member_name)
            option_as_argument = f'--{option_label.lower().replace(" ", "-")}'
            if option_type is bool and option_value:
                option_lines.append(f'- `{option_as_argument}`')
            if option_type is int and option_value:
                option_lines.append(f'-  `{option_as_argument}={option_value}`')
    if option_lines:
        lines.extend(option_lines)
    else:
        lines.append('Default options.')
    lines.append('')

    lines.append('## Custom Tracks')
    lines.append('')
    extra_page_count = len(added_course_names) // 16
    for page in range(extra_page_count):
        if page != 0:
            lines.append('')
        lines.append(f'### Page {page + 2}/{extra_page_count + 1}')
        for i in range(16):
            if i % 4 == 0:
                lines.append('')
                lines.append(f'#### {CUP_NAMES[i // 4]}')
                lines.append('')
            lines.append(f'- {added_course_names[page * 16 + i]}')

    description_filepath = os.path.join(iso_tmp_dir, 'files', 'DESCRIPTION.md')
    with open(description_filepath, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(f'{line}\n')


OPTIONAL_ARGUMENTS = {
    'General options': (
        (
            'Skip Banner',
            bool,
            'If specified, the BNR file will be left untouched.\n\n'
            'By default, the banner image is replaced with a custom bitmap, and "Extended!!" is '
            'appended to the game title.',
        ),
        (
            'Skip Menu Titles',
            bool,
            'If specified, menu titles will be left untouched.\n\n'
            'By default, the menu titles in the **SELECT COURSE** and **SELECT CUP** screens are '
            'modified to include an icon that shows the controls to switch between course pages.',
        ),
        (
            'Skip Cup Names',
            bool,
            'If specified, cup names will be left untouched.\n\n'
            'By default, cup names are modified to include an icon that indicates the currently '
            'selected course page.',
        ),
        (
            'Skip Minimap Transforms Removal',
            bool,
            'If specified, minimap transforms will be left untouched.\n\n'
            'By default, minimap transforms are removed.\n\n'
            'These transforms, that depend on hardcoded float values, are used in the game to make '
            'the minimaps in the stock courses look larger and better aligned. However, custom '
            'tracks will rarely benefit from these specialized transforms; preserving these '
            'transforms will likely make some minimaps in custom tracks be cut off screen.',
        ),
        (
            'Add Description File',
            bool,
            'If specified, a plain text file (`DESCRIPTION.md`) containing the description of the '
            'extended game will be written to the `files` directory in the ISO image.\n\n'
            'The description file includes the application version, the creation time, the options '
            'that were used to generate the ISO image, and the name of added custom tracks.',
        ),
    ),
    'Audio options': (
        (
            'Sample Rate',
            int,
            'If set (in Hz), custom audio tracks that have a greater sample rate than the provided '
            'value will be downsampled. This can be used to reduce the size of the ISO image '
            'notably. Stock courses use 32000 Hz.',
        ),
        (
            'Use Auxiliary Audio Track',
            bool,
            'If specified, audio files of the custom tracks that provide the '
            '`auxiliary_audio_track` field in their `trackinfo.ini` file will be excluded from the '
            'ISO image. Instead, the audio track of the defined retail course will be used. This '
            'can be used to reduce the size of the ISO image.',
        ),
        (
            'Use Replacee Audio Track',
            bool,
            'If specified, all custom audio tracks will be disregarded from the ISO image. '
            'Instead, the audio track of the retail course defined by the `replaces` field in the '
            '`trackinfo.ini` file will be used. If the `auxiliary_audio_track` field is defined, '
            'its value will be used instead. This can be used to reduce the size of the ISO image.',
        ),
        (
            'Mix to Mono',
            bool,
            'If enabled, custom audio tracks will be mixed into mono audio.\n\n'
            'Although this reduces the size of the ISO image considerably, the game will only play '
            'mono AST files on the left speaker. As a workaround, the in-game **SOUND** option can '
            'be switched to `MONO`.',
        ),
    ),
    'Expert options': (
        (
            'Extended Memory',
            bool,
            'If specified, the simulated memory size in the ISO image will be extended from 24 MiB '
            'to 32 MiB. This permits a greater heap size in the game, which is incremented too '
            'from 6656 KiB to 12800 KiB (or from 6525 KiB to 12669 KiB in the PAL version), '
            'allowing certain files to grow larger without causing crashes.'
            '\n\n'
            'By default, preview and label images are downscaled due to limited space in the '
            '`courseselect.arc` file. When `--extended-memory` is provided, the full size is used.'
            '\n\n'
            'IMPORTANT: The resulting ISO image will only work in Dolphin, and it is mandatory to '
            'also extend the emulated memory size to 32 MiB. See **Config > Advanced > Memory '
            'Override** in Dolphin. Failing to enable the emulated memory size in Dolphin will '
            'make the game crash to a green screen.',
        ),
        (
            'Legacy Gecko Codes',
            bool,
            'If specified, the legacy Gecko codes will be injected in the DOL file instead of the '
            'more modern code patch that superseded them.'
            '\n\n'
            'In the modern system, course pages are numbered from 1 to 4, with the first page '
            'holding the stock courses. The user can cycle through pages by pressing either '
            '`D-pad Up` or `D-pad Down`. '
            '\n\n'
            'In the legacy system, course pages are labeled as **Right Page** (stock courses), '
            '**Up Page**, **Down Page**, and **Left Page**, with their corresponding icon in the '
            'cups names. The user can switch between pages by holding `Z` and pressing any of the '
            'directions in the `D-pad`.',
        ),
    ),
    'Dangerous options': (
        (
            'Skip DOL Checksum Check',
            bool,
            'If specified, unrecognized checksums of the DOL file will not fail the program. '
            'Unexpected errors or misbehavior may occur when a non-retail DOL file is encountered.',
        ),
        (
            'Skip Filesize Check',
            bool,
            'If specified, no filesize check will be performed. It is known that certain files '
            'need to remain under a specific size (e.g. `courseselect.arc`), and unexpected '
            'crashes can occur when the limits are exceeded.',
        ),
    ),
}


def create_args_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=str, help='Path to the original ISO file.')
    parser.add_argument(
        'tracks',
        type=str,
        help='Path to the directory containing the files for each of the custom tracks that will '
        'be added to the game.\n\n'
        'Custom tracks must be provided in the MKDD Track Patcher format: either compressed in a '
        'ZIP archive, or as a directory that contains the relevant files for the custom track.\n\n'
        'Each archive name (or directory name) needs to be prefixed with a letter (A, B, C, ..., '
        'I), and a number in the range `[01, 16]` (one-digit numbers padded with a 0).\n\n'
        'The number of custom tracks provided must be multiple of 16: "A01...", "A02...", ..., '
        '"C16...".')
    parser.add_argument('output',
                        type=str,
                        help='Path where the modified ISO file will be written.')

    if not windows or not frozen:
        parser.add_argument(
            '--gui',
            action='store_true',
            help='If specified, the application will be launched in GUI mode.\n\n'
            'This argument is provided for discoverability and documentation purposes; when the '
            'application is executed with no arguments, it will be launched in GUI mode by '
            'default.')

    for group_name, group_options in OPTIONAL_ARGUMENTS.items():
        argument_group = parser.add_argument_group(group_name)
        for option_label, option_type, option_help in group_options:
            option_as_argument = f'--{option_label.lower().replace(" ", "-")}'

            if option_type is bool:
                argument_group.add_argument(option_as_argument,
                                            action='store_true',
                                            help=option_help)

            if option_type is int:
                argument_group.add_argument(option_as_argument, type=int, help=option_help)

    return parser


def extend_game(args: argparse.Namespace):
    start_time = time.monotonic()

    if not args.input:
        raise MKDDExtenderError('Path to the input ISO file cannot be empty.')
    if not args.output:
        raise MKDDExtenderError('Path to the output ISO file cannot be empty.')

    if args.input == args.output:
        raise MKDDExtenderError('Paths to the input and output ISO files must be different.')

    with tempfile.TemporaryDirectory(prefix=TEMP_DIR_PREFIX) as iso_tmp_dir:
        # Extract the ISO file entirely for now. In the future, only extracting the files that need
        # to be read might be ideal performance-wise.
        log.info(f'Extracting "{args.input}" image to "{iso_tmp_dir}"...')
        gcm_file = gcm.GCM(args.input)
        try:
            gcm_file.read_entire_disc()
        except Exception as e:
            raise MKDDExtenderError(f'Unable to read input ISO image: {str(e)}') from e
        if 'files/Cours0' in gcm_file.dirs_by_path:
            raise MKDDExtenderError('The input ISO image appears to have been extended already.')
        files_extracted = 0
        for _filepath, files_done in gcm_file.export_disc_to_folder_with_changed_files(iso_tmp_dir):
            if files_done > 0:
                files_extracted = files_done
        log.info(f'Image extracted ({files_extracted} files).')

        # Verify whether the DOL file is authentic or has been externally modified already.
        verify_dol_checksum(args, iso_tmp_dir)

        # To determine which have been added, build the initial list now.
        log.info('Building initial file list...')
        initial_file_list = build_file_list(iso_tmp_dir)
        log.info(f'File list built ({len(initial_file_list)} entries).')

        # Extract the relevant RARC files that will be modified.
        log.info('Extracting RARC files...')
        RARC_FILENAMES = ('courseselect.arc', 'LANPlay.arc', 'titleline.arc')
        scenedata_dirpath = os.path.join(iso_tmp_dir, 'files', 'SceneData')
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

        if not args.skip_banner:
            patch_bnr_file(iso_tmp_dir)
        if not args.skip_menu_titles:
            patch_title_lines(args, iso_tmp_dir)

        (
            minimap_data,
            alternative_audio_data,
            matching_audio_override_data,
            added_course_names,
        ) = meld_courses(args, iso_tmp_dir)

        page_count = len(alternative_audio_data) // 16 + 1
        patch_cup_names(args, page_count, iso_tmp_dir)

        patch_dol_file(args, minimap_data, alternative_audio_data, matching_audio_override_data,
                       iso_tmp_dir)

        # Re-pack RARC files, and erase directories.
        log.info('Packing RARC files...')
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

        # Verify that the `courseselect.arc` files haven't grown too large.
        for language in LANGUAGES:
            if language not in scenedata_filenames:
                continue
            filepath = os.path.join(scenedata_dirpath, language, 'courseselect.arc')
            filesize = os.path.getsize(filepath)
            COURSESELECT_MAX_FILESIZE = 1792 * 1024
            courseselect_max_filesize = COURSESELECT_MAX_FILESIZE
            if args.extended_memory:
                # The emulated memory has been extended by 6 MiB. Allow the file to grow a larger.
                courseselect_max_filesize += 5 * 1024 * 1024
            if filesize > courseselect_max_filesize:
                message = (f'Size of the "{filepath}" file ({filesize} bytes) is greater than '
                           f'the maximum size that is considered safe ({courseselect_max_filesize} '
                           'bytes).')
                if args.skip_filesize_check:
                    log.warning(message)
                    continue
                raise MKDDExtenderError(f'{message}. Re-run with --skip-filesize-check to '
                                        'circumvent this safety measure.')

        # Generate description file.
        if args.add_description_file:
            write_description_file(args, added_course_names, iso_tmp_dir)

        # Cross-check which files have been added, and then import all files from disk. While it
        # could be more efficient to compare timestamps and import only the ones that have really
        # changed, the truth is that the ISO image is going to be written straight away, and every
        # file will have to be read regardless.
        log.info('Preparing ISO image...')
        final_file_list = build_file_list(iso_tmp_dir)
        # Also drop from the list those directories and files that no longer exist in the image.
        for path in initial_file_list:
            if path not in final_file_list:
                dir_entry = gcm_file.dirs_by_path_lowercase.get(path.lower())
                if dir_entry is not None:
                    gcm_file.delete_directory(dir_entry)
                    continue
                file_entry = gcm_file.files_by_path_lowercase.get(path.lower())
                if file_entry is not None:
                    gcm_file.delete_file(file_entry)
        for path in final_file_list:
            if path not in initial_file_list:
                if os.path.isfile(os.path.join(iso_tmp_dir, path)):
                    gcm_file.add_new_file(path)
                else:
                    gcm_file.add_new_directory(path)
        gcm_file.import_all_files_from_disk(iso_tmp_dir)
        log.info('ISO image prepared.')

        # It is paramount that the file list is sorted in the same order that has been used to
        # compute file indexes of the AST files in the Stream folder. Stock ISO files are sorted in
        # the correct order, but modified ISO files may have AST files in a different order.
        log.info('Sorting file list in asciibetical order...')
        gcm_file.file_entries = sorted(gcm_file.file_entries, key=lambda e: e.file_path.lower())
        for file_entry in gcm_file.file_entries:
            if hasattr(file_entry, 'children'):
                file_entry.children = sorted(file_entry.children, key=lambda e: e.file_path.lower())
        gcm_file.files_by_path = {
            k: gcm_file.files_by_path[k]
            for k in sorted(gcm_file.files_by_path.keys(), key=str.lower)
        }
        gcm_file.files_by_path_lowercase = {
            k: gcm_file.files_by_path_lowercase[k]
            for k in sorted(gcm_file.files_by_path_lowercase.keys())
        }
        gcm_file.changed_files = {
            k: gcm_file.changed_files[k]
            for k in sorted(gcm_file.changed_files.keys(), key=str.lower)
        }
        gcm_file.dirs_by_path = {
            k: gcm_file.dirs_by_path[k]
            for k in sorted(gcm_file.dirs_by_path.keys(), key=str.lower)
        }
        gcm_file.dirs_by_path_lowercase = {
            k: gcm_file.dirs_by_path_lowercase[k]
            for k in sorted(gcm_file.dirs_by_path_lowercase.keys())
        }

        # Write the extended ISO file to the final location.
        log.info(f'Writing extended ISO image to "{args.output}"...')
        files_written = 0
        for _filepath, files_done in gcm_file.export_disc_to_iso_with_changed_files(args.output):
            if files_done > 0:
                files_written = files_done
        iso_size = os.path.getsize(args.output)
        human_readable_iso_size = round(os.path.getsize(args.output) / 1024.0 / 1024.0)
        log.info(f'ISO image written ({files_written} files - {human_readable_iso_size} MiB).')

        if iso_size > MAX_ISO_SIZE:
            log.warning(f'ISO file ({iso_size} bytes) is larger than the size that GameCube or Wii '
                        f'support ({MAX_ISO_SIZE} bytes). The game will work on Dolphin, but will '
                        'likely not work on real hardware.')

        elapsed_time = time.monotonic() - start_time
        log.info(f'Process completed in {elapsed_time:.2f} seconds.')


def main():
    clean_stale_temp_dirs()

    # When no arguments are provided, the application will be launched in GUI mode. On Windows, if
    # the application is frozen, the mode is determined by the executable name.
    if not windows or not frozen:
        gui_mode = len(sys.argv) == 1 or '--gui' in sys.argv
    else:
        gui_mode = '-cli' not in os.path.basename(sys.executable)

    if gui_mode:
        try:
            import gui  # pylint: disable=import-outside-toplevel
            sys.exit(gui.run())
        except ImportError as e:
            log.warning(f'Unable to launch GUI ("{str(e)}"). Switching to command-line mode...')

    args = create_args_parser().parse_args()

    try:
        extend_game(args)
    except MKDDExtenderError as e:
        log.error(str(e))
        sys.exit(1)
    except AssertionError as e:
        log.exception(str(e) or 'Assertion error.')
        sys.exit(1)
    except Exception as e:
        log.exception(str(e) or 'Unknown error.')
        sys.exit(1)


if __name__ == '__main__':
    main()
