# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for generating the bundles for the MKDD Extender.

On Linux, in a Bash terminal:

    cd /tmp
    rm -rf MKDDEXT_BUNDLE_TMP
    mkdir MKDDEXT_BUNDLE_TMP
    cd MKDDEXT_BUNDLE_TMP
    git clone git@github.com:cristian64/mkdd-extender.git
    cd mkdd-extender
    git submodule update --init
    python3 -m venv venv
    source venv/bin/activate
    export PYTHONNOUSERSITE=1
    python3 -m pip install -r requirements.txt
    python3 -m pip install pyinstaller
    pyinstaller mkdd_extender.spec
    cd dist
    python3 -c "import os, shutil; d = os.listdir()[0]; shutil.make_archive(d, 'bztar', '.', d)"

On Windows, in a cmd console:

    cd %TMP%
    rmdir /s /q MKDDEXT_BUNDLE_TMP
    mkdir MKDDEXT_BUNDLE_TMP
    cd MKDDEXT_BUNDLE_TMP
    git clone git@github.com:cristian64/mkdd-extender.git
    cd mkdd-extender
    git submodule update --init
    python3 -m venv venv
    call venv/Scripts/activate.bat
    set PYTHONNOUSERSITE=1
    python3 -m pip install -r requirements.txt
    python3 -m pip install pyinstaller
    pyinstaller mkdd_extender.spec
    cd dist
    python3 -c "import os, shutil; d = os.listdir()[0]; shutil.make_archive(d, 'zip', '.', d)"

"""

import platform
import re
import sys

linux = platform.system() == 'Linux'
windows = platform.system() == 'Windows'
macos = platform.system() == 'Darwin'

icon_path = None
icon_cli_path = None
if windows:
    icon_path = 'data/gui/logo256x256.png'
    icon_cli_path = 'data/gui/logocli256x256.png'

# To avoid importing the module, simply parse the file to find the version variable in it.
with open('mkdd_extender.py', 'r', encoding='utf-8') as f:
    data = f.read()
for line in data.splitlines():
    if '__version__' in line:
        version = re.search(r"'(.+)'", line).group(1)
        break
else:
    raise RuntimeError('Unable to parse product version.')

system = platform.system().lower()
if system != 'linux':
    system = system[:3]

arch = (sys.maxsize + 1).bit_length()

collection_name = f'mkdd-extender-{version}-{system}{arch}'

# Data files that will be copied verbatim.
datas = [
    ('COPYING', '.'),
    ('README.md', '.'),
    ('data', 'data'),
    ('tools/GeckoLoader/bin', 'bin'),
]
wimgt_filenames = []
if linux:
    wimgt_filenames = ['wimgt']
elif windows:
    wimgt_filenames = [
        'cygcrypto-1.1.dll', 'cygncursesw-10.dll', 'cygpng16-16.dll', 'cygwin1.dll', 'cygz.dll',
        'wimgt.exe'
    ]
elif macos:
    wimgt_filenames = ['wimgt-mac']
for wimgt_filename in wimgt_filenames:
    datas.append((f'tools/wimgt/{wimgt_filename}', 'tools/wimgt/'))

block_cipher = None

analysis = Analysis(
    ['mkdd_extender.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name='mkdd-extender',
    icon=icon_path,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=not windows,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if not windows:
    coll = COLLECT(
        exe,
        analysis.binaries,
        analysis.zipfiles,
        analysis.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=collection_name,
    )

else:
    # On Windows, a separate executable needs to be defined for the command-line mode.
    exe_cli = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name='mkdd-extender-cli',
        icon=icon_cli_path,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        exe_cli,
        analysis.binaries,
        analysis.zipfiles,
        analysis.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=collection_name,
    )
