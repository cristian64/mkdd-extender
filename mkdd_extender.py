#!/usr/bin/env python3
"""
MKDD Extender is a tool that extends Mario Kart: Double Dash!! with 48 extra courses.
"""
import argparse
import configparser
import contextlib
import hashlib
import itertools
import logging
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

import gecko_code
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

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(module)-15s %(message)s',
                    level=logging.INFO,
                    datefmt='%Y-%m-%d %H:%M:%S')

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


def add_controls_to_title_image(src_filepath: str, dst_filepath: str, language: str):
    with tempfile.TemporaryDirectory() as tmp_dir:
        title_filename = os.path.basename(src_filepath)
        tmp_filepath = os.path.join(tmp_dir, title_filename[:-len('.bti')] + '.png')

        convert_bti_to_png(src_filepath, tmp_filepath)

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

        convert_png_to_bti(tmp_filepath, dst_filepath, 'RGB5A3')


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


def patch_bnr_file(gcm_tmp_dir: str):
    files_dirpath = os.path.join(gcm_tmp_dir, 'files')
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


def patch_title_lines(gcm_tmp_dir: str):
    files_dirpath = os.path.join(gcm_tmp_dir, 'files')
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
            add_controls_to_title_image(title_filepath, title_filepath, language)

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


def meld_courses(tracks_dirpath: str, gcm_tmp_dir: str):
    files_dirpath = os.path.join(gcm_tmp_dir, 'files')

    stream_dirpath = os.path.join(files_dirpath, 'AudioRes', 'Stream')
    course_dirpath = os.path.join(files_dirpath, 'Course')
    coursename_dirpath = os.path.join(files_dirpath, 'CourseName')
    staffghosts_dirpath = os.path.join(files_dirpath, 'StaffGhosts')
    scenedata_dirpath = os.path.join(files_dirpath, 'SceneData')

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

                patch_music_id_in_bol_file(page_track_filepath, track_index)
                patch_music_id_in_bol_file(page_track_mp_filepath, track_index)
                patch_music_id_in_bol_file(page_track_50cc_filepath, track_index)
                patch_music_id_in_bol_file(page_track_mp_50cc_filepath, track_index)
            else:
                page_track_filepath = os.path.join(page_course_dirpath,
                                                   f'{COURSES[track_index]}.arc')
                page_track_mp_filepath = os.path.join(page_course_dirpath,
                                                      f'{COURSES[track_index]}L.arc')
                shutil.copy2(track_filepath, page_track_filepath)
                shutil.copy2(track_mp_filepath, page_track_mp_filepath)

                patch_music_id_in_bol_file(page_track_filepath, track_index)
                patch_music_id_in_bol_file(page_track_mp_filepath, track_index)

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

            try:
                trackinfo_filepath = os.path.join(track_dirpath, 'trackinfo.ini')
                trackinfo = configparser.ConfigParser()
                trackinfo.read(trackinfo_filepath)
                trackname = trackinfo['Config']['trackname']
                main_language = trackinfo['Config']['main_language']
            except Exception:
                log.warning(f'Unable to locate `trackinfo.ini` in "{zip_filename}".')
                trackinfo = None
                trackname = prefix
                main_language = None

            def find_or_generate_image_path(language: str, filename: str, width: int, height: int,
                                            image_format: str,
                                            background: 'tuple[int, int, int, int]') -> str:
                course_images_dirpath = os.path.join(track_dirpath, 'course_images')

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
                        log.warning(f'Unable to locate `{filename}` in "{zip_filename}" for '
                                    f'current language ({language}). Image for {l} will be used.')
                        return filepath

                log.warning(f'Unable to locate `{filename}` in "{zip_filename}" for {language}. '
                            'An auto-generated image will be provided.')

                filepath = os.path.join(course_images_dirpath, language, filename)
                generate_bti_image(trackname, width, height, image_format, background, filepath)
                return filepath

            # Copy course logo.
            expected_languages = os.listdir(page_coursename_dirpath)
            expected_languages = tuple(l for l in LANGUAGES if l in expected_languages)
            if not expected_languages:
                log.error(f'Unable to locate language directories in "{zip_filename}" for course '
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

            # Copy preview image and label image.
            expected_languages = os.listdir(scenedata_dirpath)
            expected_languages = tuple(l for l in LANGUAGES if l in expected_languages)
            if not expected_languages:
                log.error(f'Unable to locate `SceneData/language` directories in "{zip_filename}". '
                          'This is fatal.')
                sys.exit(1)
            preview_filename = f'cop_{COURSE_TO_PREVIEW_IMAGE_NAME[COURSES[track_index]]}.bti'
            label_filename = f'coname_{COURSE_TO_LABEL_IMAGE_NAME[COURSES[track_index]]}.bti'
            page_preview_filename = with_page_index_suffix(preview_filename)
            page_label_filename = with_page_index_suffix(label_filename)
            for language in expected_languages:
                courseselect_dirpath = os.path.join(scenedata_dirpath, language, 'courseselect',
                                                    'timg')
                lanplay_dirpath = os.path.join(scenedata_dirpath, language, 'lanplay', 'timg')

                # preview_filepath = find_or_generate_image_path(language, 'track_image.bti', 256,
                #                                                184, 'CMPR', (0, 0, 0, 255))
                # TODO(CA): RARC file gets too big. For now, generate smaller placeholders.
                course_images_dirpath = os.path.join(track_dirpath, 'course_images')
                preview_filepath = os.path.join(course_images_dirpath, language, 'track_image.bti')
                generate_bti_image(trackname, 256 // 2, 184 // 2, 'CMPR', (0, 0, 0, 255),
                                   preview_filepath)
                page_preview_filepath = os.path.join(courseselect_dirpath, page_preview_filename)
                shutil.copy2(preview_filepath, page_preview_filepath)

                label_filepath = find_or_generate_image_path(language, 'track_name.bti', 256, 32,
                                                             'IA4', (0, 0, 0, 0))
                page_label_filepath = os.path.join(courseselect_dirpath, page_label_filename)
                shutil.copy2(label_filepath, page_label_filepath)
                page_label_filepath = os.path.join(lanplay_dirpath, page_label_filename)
                shutil.copy2(label_filepath, page_label_filepath)

        if melded > 0:
            log.info(f'{melded} directories melded.')
        else:
            log.warning(f'No directory has been melded.')


def patch_dol_file(gcm_tmp_dir: str):
    sys_dirpath = os.path.join(gcm_tmp_dir, 'sys')
    dol_path = os.path.join(sys_dirpath, 'main.dol')

    assert os.path.isfile(dol_path)

    checksum = md5sum(dol_path)
    if checksum not in ('edb478baec557381d10137035a72bdcc', '3a8e73b977368d1e53293d36f634e3c7',
                        '81f1b05c6650d65326f757bb25bad604'):
        log.error(f'Checksum failed: DOL file ("{dol_path}") is not original. This is fatal.')
        sys.exit(1)

    with open(dol_path, 'rb') as f:
        data = f.read()
        game_id_offset = data.find(b'DOL-GM4')
        assert game_id_offset >= 0
        game_id_offset += len('DOL-')
        game_id = data[game_id_offset:game_id_offset + len('GM4x')] + b'01'
        game_id = game_id.decode('ascii')
        assert game_id in ('GM4E01', 'GM4P01', 'GM4J01')

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_gecko_code_filepath = os.path.join(tmp_dir, 'gecko_code.txt')
        log.info(f'Generating Gecko codes to "{tmp_gecko_code_filepath}"...')

        gecko_code.write_code(game_id, tmp_gecko_code_filepath)

        log.info(f'Injecting Gecko code into "{dol_path}"...')

        geckoloader_filepath = os.path.join(tools_dir, 'GeckoLoader', 'GeckoLoader.py')
        command = (sys.executable, geckoloader_filepath, dol_path, tmp_gecko_code_filepath,
                   '--dest', dol_path, '--hooktype', 'GX')
        if 0 != run(command):
            raise RuntimeError(f'Error occurred while injecting Gecko code into DOL file.')


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

        patch_bnr_file(gcm_tmp_dir)
        patch_title_lines(gcm_tmp_dir)
        meld_courses(args.tracks, gcm_tmp_dir)
        patch_dol_file(gcm_tmp_dir)

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
