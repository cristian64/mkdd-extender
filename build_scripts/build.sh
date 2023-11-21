#!/usr/bin/env bash
# To be launched in a container that features Git and Python 3, as well as all basic dependencies
# for a desktop application. Artifacts will be copied to the `/output` directory, which must be
# mapped in advance before spawning the container.

ls /output || exit 1
cd /tmp
rm -rf MKDDEXT_BUNDLE_TMP
mkdir MKDDEXT_BUNDLE_TMP
cd MKDDEXT_BUNDLE_TMP
git clone https://github.com/cristian64/mkdd-extender.git --depth=1
cd mkdd-extender
python3 -m venv venv
source venv/bin/activate
export PYTHONNOUSERSITE=1
python3 -m pip install -r requirements.txt
python3 -m pip install altgraph==0.17.3 pyinstaller==5.13.2 pyinstaller-hooks-contrib==2023.8
pyinstaller mkdd_extender.spec
cd dist
python3 -c "import os, shutil; d = os.listdir()[0]; shutil.rmtree(os.path.join(d, 'data', 'extender_cup', 'model'))"
python3 -c "import os; d = os.listdir()[0]; os.remove(os.path.join(d, 'data', 'extender_cup', 'cup_logo.svg'))"
cd mkdd-extender*
rm libgdk*  # Remove to ensure the system's are used.
cd -
python3 -c "import os, shutil; d = os.listdir()[0]; shutil.make_archive(d, 'xztar', '.', d)"
cp *.tar.xz /output
