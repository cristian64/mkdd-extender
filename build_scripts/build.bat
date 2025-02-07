@REM To be executed in a clean Windows installation with Git and Python 3 provided by the system.

@REM Prepare working directory.
cd C:\
rmdir /s /q MKDDEXT_BUNDLE_TMP
mkdir MKDDEXT_BUNDLE_TMP
cd MKDDEXT_BUNDLE_TMP

@REM Check out code.
git clone https://github.com/cristian64/mkdd-extender.git --depth=1
cd mkdd-extender

@REM Install dependencies.
python3.12 -m venv venv
call venv/Scripts/activate.bat
set PYTHONNOUSERSITE=1
python -m pip install -r requirements.txt
python -m pip install -r requirements-build-windows.txt

@REM Create standalone Python application.
pyinstaller mkdd_extender.spec

@REM Remove unnecessary files and copy license.
cd dist
python -c "import os, shutil; d = os.listdir()[0]; shutil.rmtree(os.path.join(d, '_internal', 'data', 'extender_cup', 'model'))"
python -c "import os; d = os.listdir()[0]; os.remove(os.path.join(d, '_internal', 'data', 'extender_cup', 'cup_logo.svg'))"
python -c "import os, shutil; d = os.listdir()[0]; shutil.copyfile(os.path.join(d, '_internal', 'COPYING'), os.path.join(d, 'COPYING'))"
python -c "import os, shutil; d = os.listdir()[0]; shutil.copyfile(os.path.join(d, '_internal', 'README.md'), os.path.join(d, 'README.md'))"

@REM Create tarball.
python -c "import os, shutil; d = os.listdir()[0]; shutil.make_archive(d, 'zip', '.', d)"

start .
