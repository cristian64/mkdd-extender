# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for generating the bundles for the MKDD Extender.
"""

import datetime
import platform
import re

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

ARCH_USER_FRIENDLY_ALIASES = {'AMD64': 'x64', 'x86_64': 'x64'}
machine = platform.machine()
arch = ARCH_USER_FRIENDLY_ALIASES.get(machine) or machine.lower()

collection_name = f'mkdd-extender-{version}-{system}-{arch}'

# Insert build date.
with open('gui.py', 'r', encoding='utf-8') as f:
    data = f.read()
build_date = datetime.datetime.now().strftime('%Y-%m-%d')
data = data.replace("build_date = ''", f"build_date = '{build_date}'")
with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(data)

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
datas.append(('tools/wimgt/gpl-2.0.txt', 'tools/wimgt/'))
datas.append(('tools/wimgt/README.txt', 'tools/wimgt/'))
datas.append((f'tools/devkitPPC/{platform.system().lower()}',
              f'tools/devkitPPC/{platform.system().lower()}'))
datas.append(('tools/devkitPPC/buildscripts-devkitPPC_r41.tar.gz', 'tools/devkitPPC/'))
datas.append(('tools/devkitPPC/README.txt', 'tools/devkitPPC/'))
datas.append(('tools/lan_choose_character_kart/asm', 'tools/lan_choose_character_kart/asm'))

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
