#!/usr/bin/env python3
"""
MKDD Extender is a tool that extends Mario Kart: Double Dash!! with 48 extra courses.
"""
import argparse
import audioop
import configparser
import contextlib
import difflib
import hashlib
import itertools
import json
import logging
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFont

import ast_converter
import gecko_code
import rarc
from tools import bti, gcm

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

PREFIXES = tuple(f'{c}{i + 1:02}' for c, i in itertools.product(('A', 'B', 'C'), range(16)))
"""
A list of the "prefixes" that are used when naming the track archives. First letter states the page,
and the next two digits indicate the track index in the page (from `01` to `16`).
"""

linux = platform.system() == 'Linux'
windows = platform.system() == 'Windows'
macos = platform.system() == 'Darwin'


class _CustomFormatter(logging.Formatter):
    yellow = '\x1b[0;33m' if not windows else ''
    bold_red = '\x1b[1;91m' if not windows else ''
    bold_fucsia = '\x1b[1;95m' if not windows else ''
    reset = '\x1b[0m' if not windows else ''

    def __init__(self):
        super().__init__()

        fmt = '%(asctime)s %(levelname)-8s %(module)-15s %(message)s'
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


def extract_and_flatten(src_path: str, dst_dirpath: str):
    # Extracts a ZIP archive into the given directory. If the archive contains a single directory,
    # it will be unwrapped. If the archive contains a nested archive, it will be extracted too.
    with tempfile.TemporaryDirectory() as tmp_dir:
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
    if bol_offset > 0 and data.find(BOL_MAGIC, bol_offset + len(BOL_MAGIC)) < 0:
        with open(course_filepath, 'r+b') as f:
            f.seek(bol_offset + MUSIC_ID_OFFSET)
            f.write(bytes([music_id]))
        return

    # Otherwise, extract the RARC file, locate the BOL file in the directory, patch the BOL file,
    # and re-pack the RARC archive.
    with tempfile.TemporaryDirectory() as tmp_dir:
        rarc.extract(course_filepath, tmp_dir)

        course_dirpath = os.path.join(tmp_dir, os.listdir(tmp_dir)[0])
        bol_filepath = os.path.join(
            course_dirpath,
            tuple(p for p in os.listdir(course_dirpath) if p.endswith('.bol'))[0])

        with open(bol_filepath, 'r+b') as f:
            f.seek(MUSIC_ID_OFFSET)
            f.write(bytes([music_id]))

        rarc.pack(course_dirpath, course_filepath)


def repack_course_arc_file(archive_filepath: str, new_dirname: str):
    """
    Extracts a RARC archive, renames its root directory and its files, and re-packs it.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        rarc.extract(archive_filepath, tmp_dir)

        dirnames = os.listdir(tmp_dir)
        if len(dirnames) != 1:
            log.error(f'Unable to rename entries in "{archive_filepath}". Unexpected number of '
                      'root entries in directory. This is fatal.')
            sys.exit(1)

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
                    if len(parts) > 2:
                        log.error(
                            f'Unable to rename entries in "{archive_filepath}". Unrecognized '
                            f'filename with multiple "_" characters ("{filename}"). This is fatal.')
                        sys.exit(1)
                    new_filename = f'{course_name}_{parts[1]}'
                    new_filepath = os.path.join(new_dirpath, new_filename)
                    os.rename(filepath, new_filepath)

        rarc.pack(new_dirpath, archive_filepath)


def convert_bti_to_png(src_filepath: str, dst_filepath: str):
    assert src_filepath.endswith('.bti')

    os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)

    wimgt_name = 'wimgt.exe' if windows else 'wimgt-mac' if macos else 'wimgt'
    wimgt_path = os.path.join(tools_dir, 'wimgt', wimgt_name)
    command = (wimgt_path, 'decode', src_filepath, '-o', '-d', dst_filepath)

    if 0 != run(command) or not os.path.isfile(dst_filepath):
        # Fall back to the `bti` module if `wimgt` fails.
        bti.BTI(open(src_filepath, 'rb')).render().save(dst_filepath)
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


def add_controls_to_title_image(filepath: str, language: str):
    with tempfile.TemporaryDirectory() as tmp_dir:
        title_filename = os.path.basename(filepath)
        tmp_filepath = os.path.join(tmp_dir, title_filename[:-len('.bti')] + '.png')

        convert_bti_to_png(filepath, tmp_filepath)

        controls_filepath = os.path.join(data_dir, 'controls', 'controls.png')
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
            image.paste(word, box, word)
        image.save(tmp_filepath)

        convert_png_to_bti(tmp_filepath, filepath, 'RGB5A3')


def add_dpad_to_cup_name_image(filepath: str, page_index: int):
    with tempfile.TemporaryDirectory() as tmp_dir:
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

        ops = []
        for word in words:
            ops.append((word, (offset + dpad_image.width, 0)))
            offset += spacing + word.width

        image = Image.new('RGBA', (canvas_width + dpad_image.width, canvas_height))
        image.paste(dpad_image, (0, 0), dpad_image)
        for word, box in reversed(ops):
            image.paste(word, box, word)
        image = image.convert(original_mode)
        image.save(tmp_filepath)

        convert_png_to_bti(tmp_filepath, filepath, 'IA4')


def generate_bti_image(text: str, width: int, height: int, image_format: str,
                       background: 'tuple[int, int, int, int]', filepath: str):
    assert filepath.endswith('.bti')

    filtered_text = ''
    for c in text:
        if c.lower() in ' abcdefghijklmnopqrstuvwxyz0123456789$!?@':
            filtered_text += c

    filtered_text = ' '.join(filtered_text.split())

    if not filtered_text:
        filtered_text = '?'

    image = Image.new('RGBA', (width, height), background)
    draw = ImageDraw.Draw(image)

    font_filepath = os.path.join(data_dir, 'fonts', 'SuperMario256.ttf')

    padded_text = f'{filtered_text}-'  # So it's not close to the edge

    for size in range(2, 100):
        font = ImageFont.truetype(font_filepath, size)
        w, h = font.getsize(padded_text)
        if w >= width or h >= height:
            font = ImageFont.truetype(font_filepath, size - 1)
            break

    w, h = font.getsize(filtered_text)
    x, y = (width - w) // 2, (height - h) // 2

    for offset, alpha in ((1, 255), (2, 250), (3, 245)):
        draw.text((x - offset, y - 0), filtered_text, font=font, fill=(0, 0, 0, alpha))
        draw.text((x + offset, y - 0), filtered_text, font=font, fill=(0, 0, 0, alpha))
        draw.text((x - 0, y - offset), filtered_text, font=font, fill=(0, 0, 0, alpha))
        draw.text((x + 0, y - offset), filtered_text, font=font, fill=(0, 0, 0, alpha))
        draw.text((x - offset, y - offset), filtered_text, font=font, fill=(0, 0, 0, alpha - 20))
        draw.text((x - offset, y + offset), filtered_text, font=font, fill=(0, 0, 0, alpha - 20))
        draw.text((x + offset, y + offset), filtered_text, font=font, fill=(0, 0, 0, alpha - 20))
        draw.text((x + offset, y - offset), filtered_text, font=font, fill=(0, 0, 0, alpha - 20))

    draw.text((x, y), filtered_text, font=font, fill=(255, 255, 255, 255))

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_filepath = os.path.join(tmp_dir,
                                    f'{os.path.splitext(os.path.basename(filepath))[0]}.png')
        image.save(tmp_filepath)

        convert_png_to_bti(tmp_filepath, filepath, image_format)


def conform_audio_file(filepath: str, mix_to_mono: bool, downsample_sample_rate: int):
    if not mix_to_mono and not downsample_sample_rate:
        return

    ast_info = ast_converter.get_ast_info(filepath)

    bit_depth = ast_info['bit_depth']
    channel_count = ast_info['channel_count']
    sample_rate = ast_info['sample_rate']

    if channel_count not in (1, 2, 4):
        log.error(f'Unsupported channel count ({channel_count}) in "{filepath}". '
                  'Expected 1, 2, or 4 channels.')
        sys.exit(1)

    needs_mixing = mix_to_mono and channel_count != 1
    needs_downsampling = downsample_sample_rate and sample_rate != downsample_sample_rate

    if not needs_mixing and not needs_downsampling:
        return

    log.info(f'Conforming audio file ("{filepath}")...')

    with tempfile.TemporaryDirectory() as tmp_dir:
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
    IMAGE_OFFSET = 0x0020
    IMAGE_LENGTH = 0x1800

    with open(bnr_filepath, 'r+b') as f:
        f.seek(IMAGE_OFFSET)
        f.write(open(raw_filepath, 'rb').read())
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

    log.info(f'Game title tweaked.')


def patch_title_lines(iso_tmp_dir: str):
    files_dirpath = os.path.join(iso_tmp_dir, 'files')
    scenedata_dirpath = os.path.join(files_dirpath, 'SceneData')

    log.info(f'Patching title lines...')

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
            add_controls_to_title_image(title_filepath, language)

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
                log.warning(f'Unexpected dimensions in BLO file. Titles\' dimensions will not be '
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
                log.warning(f'Unexpected colors in BLO file. Titles\' color gradient will not be '
                            'desaturated.')

    log.info('Title lines patched.')


def patch_cup_names(iso_tmp_dir: str):
    files_dirpath = os.path.join(iso_tmp_dir, 'files')
    scenedata_dirpath = os.path.join(files_dirpath, 'SceneData')

    log.info(f'Patching cup names...')

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

            for page_index in range(3):

                def with_page_index_suffix(path: str) -> str:
                    stem, ext = os.path.splitext(path)
                    stem = stem[:-len(str(page_index))] + str(page_index)
                    return stem + ext

                page_cupname_filepath = with_page_index_suffix(cupname_filepath)
                shutil.copyfile(cupname_filepath, page_cupname_filepath)
                add_dpad_to_cup_name_image(page_cupname_filepath, page_index)
                shutil.copyfile(page_cupname_filepath,
                                page_cupname_filepath.replace('courseselect', 'lanplay'))

            add_dpad_to_cup_name_image(cupname_filepath, -1)
            shutil.copyfile(cupname_filepath, cupname_filepath.replace('courseselect', 'lanplay'))

    log.info('Cup names patched.')


def meld_courses(args: argparse.Namespace, iso_tmp_dir: str) -> dict:
    tracks_dirpath = args.tracks

    minimap_data = {}
    auxiliary_audio_data = {}

    files_dirpath = os.path.join(iso_tmp_dir, 'files')

    stream_dirpath = os.path.join(files_dirpath, 'AudioRes', 'Stream')
    course_dirpath = os.path.join(files_dirpath, 'Course')
    coursename_dirpath = os.path.join(files_dirpath, 'CourseName')
    staffghosts_dirpath = os.path.join(files_dirpath, 'StaffGhosts')
    scenedata_dirpath = os.path.join(files_dirpath, 'SceneData')

    with tempfile.TemporaryDirectory() as tracks_tmp_dir:
        # Extract all ZIP archives to their respective directories.
        paths = tuple(os.path.join(tracks_dirpath, p) for p in sorted(os.listdir(tracks_dirpath)))
        prefix_to_nodename = {}
        extracted = 0
        log.info(f'Extracting ZIP archives...')
        for prefix in PREFIXES:
            for path in paths:
                filename = os.path.basename(path)
                if filename.startswith(prefix):
                    track_dirpath = os.path.join(tracks_tmp_dir, prefix)
                    log.info(f'Extracting "{path}" into "{track_dirpath}"...')
                    extract_and_flatten(path, track_dirpath)
                    prefix_to_nodename[prefix] = filename
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

        # Copy files into the ISO temporariy directory.
        log.info(f'Melding extracted directories...')
        melded = 0
        for prefix in PREFIXES:
            track_dirpath = os.path.join(tracks_tmp_dir, prefix)
            page_index = ord(prefix[0]) - ord('A')
            track_index = int(prefix[1:3]) - 1
            assert 0 <= page_index <= 2
            assert 0 <= track_index <= 15

            nodename = prefix_to_nodename[prefix]

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

            # Parse INI file.
            try:
                trackinfo_filepath = os.path.join(track_dirpath, 'trackinfo.ini')
                trackinfo = configparser.ConfigParser()
                trackinfo.read(trackinfo_filepath)
                trackname = trackinfo['Config']['trackname']
                main_language = trackinfo['Config']['main_language']
                auxiliary_audio_track = trackinfo['Config'].get('auxiliary_audio_track')
            except Exception:
                log.warning(f'Unable to locate `trackinfo.ini` in "{nodename}", or it is missing '
                            'the `trackname` field or `main_language` field.')
                trackinfo = None
                trackname = prefix
                main_language = None
                auxiliary_audio_track = None

            if auxiliary_audio_track:
                auxiliary_audio_data[prefix] = course_name_to_course(auxiliary_audio_track)

            # Copy course files.
            track_filepath = os.path.join(track_dirpath, 'track.arc')
            if not os.path.isfile(track_filepath):
                log.error(f'Unable to locate `track.arc` file in "{nodename}". This is fatal.')
                sys.exit(1)
            track_mp_filepath = os.path.join(track_dirpath, 'track_mp.arc')
            if not os.path.isfile(track_mp_filepath):
                log.warning(f'Unable to locate `track_mp.arc` file in "{nodename}". '
                            '`track.arc` will be used.')
                track_mp_filepath = track_filepath
            if track_index == 0:
                track_50cc_filepath = os.path.join(track_dirpath, 'track_50cc.arc')
                if not os.path.isfile(track_50cc_filepath):
                    log.warning(f'Unable to locate `track_50cc.arc` file in "{nodename}". '
                                '`track.arc` will be used.')
                    track_50cc_filepath = track_filepath
                track_mp_50cc_filepath = os.path.join(track_dirpath, 'track_mp_50cc.arc')
                if not os.path.isfile(track_mp_50cc_filepath):
                    log.warning(f'Unable to locate `track_mp_50cc.arc` file in "{nodename}". '
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
                shutil.copy2(track_filepath, page_track_filepath)
                shutil.copy2(track_mp_filepath, page_track_mp_filepath)

                patch_music_id_in_bol_file(page_track_filepath, track_index)
                patch_music_id_in_bol_file(page_track_mp_filepath, track_index)

                repack_course_arc_file(page_track_filepath, f'{COURSES[track_index].lower()}')
                repack_course_arc_file(page_track_mp_filepath, f'{COURSES[track_index].lower()}l')

            # Copy GHT file.
            ght_filepath = os.path.join(track_dirpath, 'staffghost.ght')
            if os.path.isfile(ght_filepath):
                page_ght_filepath = os.path.join(page_staffghosts_dirpath,
                                                 f'{COURSES[track_index]}.ght')
                shutil.copy2(ght_filepath, page_ght_filepath)
            else:
                log.warning(f'Unable to locate `staffghost.ght` file in "{nodename}".')

            # Force use of auxiliary audio track if argument has been provided and the custo track
            # has the field defined.
            use_auxiliary_audio_track = auxiliary_audio_track and args.use_auxiliary_audio_track

            if not use_auxiliary_audio_track:
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
                    shutil.copy2(lap_music_normal_filepath, dst_ast_filepath)
                    conform_audio_file(dst_ast_filepath, args.mix_to_mono, args.sample_rate)

                    lap_music_fast_filepath = os.path.join(track_dirpath, 'lap_music_fast.ast')
                    if os.path.isfile(lap_music_fast_filepath):
                        dst_ast_filepath = os.path.join(stream_dirpath, f'X_FINALLAP_{prefix}.ast')
                        shutil.copy2(lap_music_fast_filepath, dst_ast_filepath)
                        conform_audio_file(dst_ast_filepath, args.mix_to_mono, args.sample_rate)
                    else:
                        log.warning(f'Unable to locate `lap_music_fast.ast` in "{nodename}". '
                                    '`lap_music_normal.ast` will be used.')
                else:
                    if auxiliary_audio_track:
                        course_name = COURSE_TO_NAME[course_name_to_course(auxiliary_audio_track)]
                        log.info(
                            f'Unable to locate `lap_music_normal.ast` in "{nodename}". Auxiliary '
                            f'audio track ("{course_name}") will be used.')
                    else:
                        log.warning(
                            f'Unable to locate `lap_music_normal.ast` in "{nodename}". Luigi '
                            'Circuit\'s sound track will be used.')
            else:
                course_name = COURSE_TO_NAME[course_name_to_course(auxiliary_audio_track)]
                log.info(f'Auxiliary audio track ("{course_name}") will be used.')

            course_images_dirpath = os.path.join(track_dirpath, 'course_images')

            def find_or_generate_image_path(language: str, filename: str, width: int, height: int,
                                            image_format: str,
                                            background: 'tuple[int, int, int, int]') -> str:
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
                generate_bti_image(trackname, width, height, image_format, background, filepath)
                return filepath

            # Copy course logo.
            expected_languages = os.listdir(page_coursename_dirpath)
            expected_languages = tuple(l for l in LANGUAGES if l in expected_languages)
            if not expected_languages:
                log.error(f'Unable to locate language directories in "{nodename}" for course '
                          'logo. This is fatal.')
                sys.exit(1)
            for language in expected_languages:
                logo_filepath = find_or_generate_image_path(language, 'track_big_logo.bti', 208,
                                                            104, 'RGB5A3', (0, 0, 0, 0))

                page_coursename_language_dirpath = os.path.join(page_coursename_dirpath, language)
                os.makedirs(page_coursename_language_dirpath, exist_ok=True)

                page_coursename_filepath = os.path.join(page_coursename_language_dirpath,
                                                        f'{COURSES[track_index]}_name.bti')
                shutil.copy2(logo_filepath, page_coursename_filepath)

            # RARC file gets too large, and causes a crash. Reducing image size is a workaround.
            # However, if extended memory has been set, the retail dimensions can be used instead.
            if args.extended_memory:
                PREVIEW_IMAGE_SIZE = 256, 184
            else:
                PREVIEW_IMAGE_SIZE = 256 // 2, 184 // 2

            def resize_preview_image(filepath: str):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    png_tmp_filepath = os.path.join(
                        tmp_dir,
                        os.path.splitext(os.path.basename(filepath))[0] + '.png')

                    # At this time, there are a number of images that `wimgt` cannot convert. If the
                    # attempt fails, we won't be able to downscale the BTI image, and that cannot be
                    # allowed, or else the size of the archive would grow too great. In those cases,
                    # the BTI image will be deleted; an auto-geneated image will be provided later.
                    failed = False
                    try:
                        convert_bti_to_png(filepath, png_tmp_filepath)
                    except Exception:
                        failed = True
                    if not os.path.isfile(png_tmp_filepath):
                        failed = True
                    if failed:
                        log.warning(f'Unable to downscale BTI image ("{filepath}"). This mage will '
                                    'be discarded.')
                        os.remove(filepath)
                        return

                    image = Image.open(png_tmp_filepath)
                    image.convert('RGBA')

                    try:
                        resampling_filter = Image.Resampling.HAMMING
                    except AttributeError:
                        # If the Pillow version is old, the enum class won't be available. Fall back
                        # to the deprecated value for now.
                        resampling_filter = Image.HAMMING

                    image = image.resize(PREVIEW_IMAGE_SIZE,
                                         resample=resampling_filter,
                                         reducing_gap=3.0)
                    image.save(png_tmp_filepath)

                    convert_png_to_bti(png_tmp_filepath, filepath, 'CMPR')

            expected_languages = os.listdir(scenedata_dirpath)
            expected_languages = tuple(l for l in LANGUAGES if l in expected_languages)
            if not expected_languages:
                log.error(f'Unable to locate `SceneData/language` directories in "{nodename}". '
                          'This is fatal.')
                sys.exit(1)

            # Downscale preview images in all available languages.
            if not args.extended_memory:
                for language in expected_languages:
                    language_dirpath = os.path.join(course_images_dirpath, language)
                    if not os.path.isdir(language_dirpath):
                        continue
                    for filename in os.listdir(language_dirpath):
                        if filename == 'track_image.bti':
                            filepath = os.path.join(language_dirpath, filename)
                            resize_preview_image(filepath)

            # Copy preview image and label image.
            preview_filename = f'cop_{COURSE_TO_PREVIEW_IMAGE_NAME[COURSES[track_index]]}.bti'
            label_filename = f'coname_{COURSE_TO_LABEL_IMAGE_NAME[COURSES[track_index]]}.bti'
            page_preview_filename = with_page_index_suffix(preview_filename)
            page_label_filename = with_page_index_suffix(label_filename)
            for language in expected_languages:
                courseselect_dirpath = os.path.join(scenedata_dirpath, language, 'courseselect',
                                                    'timg')
                lanplay_dirpath = os.path.join(scenedata_dirpath, language, 'lanplay', 'timg')

                preview_filepath = find_or_generate_image_path(language, 'track_image.bti',
                                                               PREVIEW_IMAGE_SIZE[0],
                                                               PREVIEW_IMAGE_SIZE[1], 'CMPR',
                                                               (0, 0, 0, 255))
                page_preview_filepath = os.path.join(courseselect_dirpath, page_preview_filename)
                shutil.copy2(preview_filepath, page_preview_filepath)

                label_filepath = find_or_generate_image_path(language, 'track_name.bti', 256, 32,
                                                             'IA4', (0, 0, 0, 0))
                page_label_filepath = os.path.join(courseselect_dirpath, page_label_filename)
                shutil.copy2(label_filepath, page_label_filepath)
                page_label_filepath = os.path.join(lanplay_dirpath, page_label_filename)
                shutil.copy2(label_filepath, page_label_filepath)

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
                log.error(f'Unable to parse minimap data in "{nodename}": {str(e)}. This is '
                          'fatal.')
                sys.exit(1)

        if melded > 0:
            log.info(f'{melded} directories melded.')
        else:
            log.warning(f'No directory has been melded.')

    return minimap_data, auxiliary_audio_data


def gather_audio_file_indices(iso_tmp_dir: str, auxiliary_audio_data: 'dict[str, str]') -> tuple:
    # The Gecko code generator needs the list of 32 integers with the file index of each audio track
    # mapped to each track.

    file_list = build_file_list(iso_tmp_dir)

    COURSE_STREAM_ORDER = {
        'BabyLuigi': 'BABY',
        'Peach': 'BEACH',
        'Daisy': 'BEACH',  # Reused.
        'Luigi': 'CIRCUIT',
        'Mario': 'CIRCUIT',  # Reused.
        'Yoshi': 'CIRCUIT',  # Reused.
        'Nokonoko': 'HIWAY',
        'Patapata': 'HIWAY',  # Reused.
        'Waluigi': 'STADIUM',
        'Wario': 'STADIUM',  # Reused.
        'Diddy': 'JUNGLE',
        'Donkey': 'JUNGLE',  # Reused.
        'Koopa': 'CASTLE',
        'Rainbow': 'RAINBOW',
        'Desert': 'DESERT',
        'Snow': 'SNOW',
    }

    SPEED_TYPES = ('COURSE', 'FINALLAP')

    stock_audio_track_indices = []
    for speed_type in SPEED_TYPES:
        for _course, subname in COURSE_STREAM_ORDER.items():
            filename = f'{speed_type}_{subname}'
            for file_index, filepath in enumerate(file_list):
                if filepath.endswith('.ast') and filename in filepath:
                    stock_audio_track_indices.append(file_index)
                    break
            else:
                log.error(f'Unable to locate audio track "{filename}" in file list. This is fatal.')
                sys.exit(1)
    stock_audio_track_indices = tuple(stock_audio_track_indices)

    FALLBACK_AUDIO_COURSE = 'Luigi'
    course_stream_order = tuple(COURSE_STREAM_ORDER.keys())
    fallback_index = stock_audio_track_indices[course_stream_order.index(FALLBACK_AUDIO_COURSE)]
    fallback_finallap_index = stock_audio_track_indices[
        course_stream_order.index(FALLBACK_AUDIO_COURSE) + 16]

    audio_track_data = (
        [fallback_index] * 16 + [fallback_finallap_index] * 16,  # Page 0
        [fallback_index] * 16 + [fallback_finallap_index] * 16,  # Page 1
        [fallback_index] * 16 + [fallback_finallap_index] * 16,  # Page 2
        stock_audio_track_indices,
    )

    for prefix, auxiliary_audio_track in auxiliary_audio_data.items():
        page_index = ord(prefix[0]) - ord('A')
        track_index = int(prefix[1:3]) - 1
        auxiliary_audio_index = course_stream_order.index(auxiliary_audio_track)
        mapped_offset = course_stream_order.index(COURSES[track_index])
        audio_track_data_page = audio_track_data[page_index]
        audio_track_data_page[mapped_offset] = stock_audio_track_indices[auxiliary_audio_index]
        audio_track_data_page[mapped_offset + 16] = \
            stock_audio_track_indices[auxiliary_audio_index + 16]

    for prefix in PREFIXES:
        page_index = ord(prefix[0]) - ord('A')
        track_index = int(prefix[1:3]) - 1
        assert 0 <= page_index <= 2
        assert 0 <= track_index <= 15

        for i, speed_type in enumerate(SPEED_TYPES):
            speed_type = f'X_{speed_type}'
            filename = f'{speed_type}_{prefix}'
            for file_index, filepath in enumerate(file_list):
                if filepath.endswith('.ast') and filename in filepath:
                    mapped_offset = course_stream_order.index(COURSES[track_index])
                    audio_track_data[page_index][mapped_offset + i * 16] = file_index
                    break
            else:
                pass  # Fallback audio file index will be used.

    return tuple(tuple(l) for l in audio_track_data)


def patch_dol_file(args: argparse.Namespace, minimap_data: dict,
                   auxiliary_audio_data: 'dict[str, str]', iso_tmp_dir: str):
    sys_dirpath = os.path.join(iso_tmp_dir, 'sys')
    dol_path = os.path.join(sys_dirpath, 'main.dol')
    bi2_path = os.path.join(sys_dirpath, 'bi2.bin')

    assert os.path.isfile(dol_path)
    assert os.path.isfile(bi2_path)

    checksum = md5sum(dol_path)
    if checksum not in (
            'edb478baec557381d10137035a72bdcc',  # GM4E01
            '3a8e73b977368d1e53293d36f634e3c7',  # GM4P01
            '81f1b05c6650d65326f757bb25bad604',  # GM4J01
            'bfb79b2e98fb632d863bb39cb3ca6e08',  # GM4E01 (debug)
    ):
        log.error(f'Checksum failed: DOL file ("{dol_path}") is not original (checksum: '
                  f'{checksum}). This is fatal.')
        sys.exit(1)

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
        # and will be changed to `0x00A80000`. The instruction is:
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
        EXTENDED_HEAP_SIZE = ORIGINAL_HEAP_SIZE + 0x00400000
        log.info('Heap memory size will be extended from {} KiB to {} KiB...'.format(
            ORIGINAL_HEAP_SIZE // 1024,
            EXTENDED_HEAP_SIZE // 1024,
        ))
        if game_id != 'GM4P01':
            ORIGINAL_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0x80, 0x00, 0x68))
            EXTENDED_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0x80, 0x00, 0xA8))
        else:
            ORIGINAL_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0xc0, 0x00, 0x66))
            EXTENDED_HEAP_SIZE_INSTRUCTION = bytes((0x3c, 0xc0, 0x00, 0xA6))
        with open(dol_path, 'rb') as f:
            data = f.read()
        assert data.count(ORIGINAL_HEAP_SIZE_INSTRUCTION) == 1
        offset = data.find(ORIGINAL_HEAP_SIZE_INSTRUCTION)
        with open(dol_path, 'r+b') as f:
            f.seek(offset)
            f.write(EXTENDED_HEAP_SIZE_INSTRUCTION)

        # NOTE: After this change, it will be mandatory to increase the emulated memory size in
        # Dolphin to 32 MiB, or else the game will crash to a green screen.

    audio_track_data = gather_audio_file_indices(iso_tmp_dir, auxiliary_audio_data)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_gecko_code_filepath = os.path.join(tmp_dir, 'gecko_code.txt')
        log.info(f'Generating Gecko codes to "{tmp_gecko_code_filepath}"...')

        gecko_code.write_code(game_id, minimap_data, audio_track_data, tmp_gecko_code_filepath)

        log.info(f'Injecting Gecko code into "{dol_path}"...')

        geckoloader_filepath = os.path.join(tools_dir, 'GeckoLoader', 'GeckoLoader.py')
        command = (sys.executable, geckoloader_filepath, dol_path, tmp_gecko_code_filepath,
                   '--dest', dol_path, '--hooktype', 'GX')
        if 0 != run(command):
            raise RuntimeError(f'Error occurred while injecting Gecko code into DOL file.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=str, help='Path to the original ISO file.')
    parser.add_argument('tracks',
                        type=str,
                        help='Path to the directory containing the archives for each of the tracks '
                        'that will be added to the game.')
    parser.add_argument('output',
                        type=str,
                        help='Path where the modified ISO file will be written.')

    audio_group = parser.add_argument_group('Audio options')
    audio_group.add_argument('--mix-to-mono',
                             action='store_true',
                             help='If enabled, custom audio tracks will be mixed into mono audio. '
                             'Whilst this reduces the size of the ISO image considerably, the game '
                             'will only play mono AST files from the left speaker. As a '
                             'workaround, the in-game **SOUND** option can be switched to `MONO`.')
    audio_group.add_argument('--sample-rate',
                             type=int,
                             help='If set (in Hz), custom audio tracks that have a greater sample '
                             'rate than the provided value will be downsampled. This can be used '
                             'to reduce the size of the ISO image notably. Stock courses use 32000 '
                             'Hz.')
    audio_group.add_argument(
        '--use-auxiliary-audio-track',
        action='store_true',
        help='If specified, audio files of the custom tracks that provide the '
        '`auxiliary_audio_track` field in their `trackinfo.ini` file will be excluded from the ISO '
        'image. Instead, the audio track of the defined retail course will be used. This can be '
        'used to reduce the size of the ISO image.')

    expert_group = parser.add_argument_group('Expert options')
    expert_group.add_argument(
        '--extended-memory',
        action='store_true',
        help='If specified, the simulated memory size in the ISO image will be extended from '
        '24 MiB to 32 MiB. This permits a greater heap size in the game, which is incremented too '
        'from 6656 KiB to 10752 KiB (or from 6525 KiB to 10621 KiB in the PAL version), allowing '
        'certain files to grow larger without causing crashes.'
        '\n\n'
        'By default, preview images of the extra courses are halved due to limited space in the '
        '`courseselect.arc` file. When --extended-memory is provided, the full size is used.'
        '\n\n'
        'IMPORTANT: The resulting ISO image will only work in Dolphin, and it is mandatory to also '
        'extend the emulated memory size to 32 MiB. See **Config > Advanced > Memory Override** in '
        'Dolphin. Failing to enable the emulated memory size in Dolphin will make the game crash '
        'to a green screen.')

    dangerous_group = parser.add_argument_group('Dangerous options')
    dangerous_group.add_argument(
        '--skip-filesize-check',
        action='store_true',
        help='If specified, no filesize check will be performed. It is known that certain files '
        'need to remain under a specific size (e.g. `courseselect.arc`), and unexpected crashes '
        'can occur when the limits are exceeded.')

    args = parser.parse_args()

    iso_tmp_dir = tempfile.mkdtemp()
    try:
        # Extract the ISO file entirely for now. In the future, only extracting the files that need
        # to be read might be ideal performance-wise.
        log.info(f'Extracting "{args.input}" image to "{iso_tmp_dir}"...')
        gcm_file = gcm.GCM(args.input)
        gcm_file.read_entire_disc()
        files_extracted = 0
        for _filepath, files_done in gcm_file.export_disc_to_folder_with_changed_files(iso_tmp_dir):
            if files_done > 0:
                files_extracted = files_done
        log.info(f'Image extracted ({files_extracted} files).')

        # To determine which have been added, build the initial list now.
        log.info('Building initial file list...')
        initial_file_list = build_file_list(iso_tmp_dir)
        log.info(f'File list built ({len(initial_file_list)} entries).')

        # Extract the relevant RARC files that will be modified.
        log.info(f'Extracting RARC files...')
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

        patch_bnr_file(iso_tmp_dir)
        patch_title_lines(iso_tmp_dir)
        patch_cup_names(iso_tmp_dir)
        minimap_data, auxiliary_audio_data = meld_courses(args, iso_tmp_dir)
        patch_dol_file(args, minimap_data, auxiliary_audio_data, iso_tmp_dir)

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

        # Verify that the `courseselect.arc` files haven't grown too large.
        for language in LANGUAGES:
            if language not in scenedata_filenames:
                continue
            filepath = os.path.join(scenedata_dirpath, language, 'courseselect.arc')
            filesize = os.path.getsize(filepath)
            COURSESELECT_MAX_FILESIZE = 1792 * 1024
            courseselect_max_filesize = COURSESELECT_MAX_FILESIZE
            if args.extended_memory:
                courseselect_max_filesize += 2048 * 1024
            if filesize > courseselect_max_filesize:
                message = (f'Size of the "{filepath}" file ({filesize} bytes) is greater than '
                           f'the maximum size that is considered safe ({courseselect_max_filesize} '
                           'bytes).')
                if args.skip_filesize_check:
                    log.warning(message)
                    continue
                log.error(f'{message} This is fatal. Re-run with --skip-filesize-check to '
                          'circumvent this safety measure.')
                sys.exit(1)

        # Cross-check which files have been added, and then import all files from disk. While it
        # could be more efficient to compare timestamps and import only the ones that have really
        # changed, the truth is that the ISO image is going to be written straight away, and every
        # file will have to be read regardless.
        log.info('Preparing ISO image...')
        final_file_list = build_file_list(iso_tmp_dir)
        for path in final_file_list:
            if path not in initial_file_list:
                if os.path.isfile(os.path.join(iso_tmp_dir, path)):
                    gcm_file.add_new_file(path)
                else:
                    gcm_file.add_new_directory(path)
        gcm_file.import_all_files_from_disk(iso_tmp_dir)
        log.info('ISO image prepared.')

        # Write the extended ISO file to the final location.
        log.info(f'Writing extended ISO image to "{args.output}"...')
        files_written = 0
        for _filepath, files_done in gcm_file.export_disc_to_iso_with_changed_files(args.output):
            if files_done > 0:
                files_written = files_done
        log.info(f'ISO image written ({files_written} files).')

    finally:
        shutil.rmtree(iso_tmp_dir)


if __name__ == '__main__':
    main()
