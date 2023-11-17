@REM To be executed in a clean Windows installation with Git and Python 3 provided by the system.

cd C:\
rmdir /s /q MKDDEXT_BUNDLE_TMP
mkdir MKDDEXT_BUNDLE_TMP
cd MKDDEXT_BUNDLE_TMP
git clone https://github.com/cristian64/mkdd-extender.git --depth=1
cd mkdd-extender
python3 -m venv venv
call venv/Scripts/activate.bat
set PYTHONNOUSERSITE=1
python3 -m pip install -r requirements.txt
python3 -m pip install altgraph==0.17.3 pefile==2023.2.7 pyinstaller==5.13.2 pyinstaller-hooks-contrib==2023.8 pywin32-ctypes==0.2.2
pyinstaller mkdd_extender.spec
cd dist
python3 -c "import os, shutil; d = os.listdir()[0]; shutil.rmtree(os.path.join(d, 'data', 'extender_cup', 'model'))"
python3 -c "import os; d = os.listdir()[0]; os.remove(os.path.join(d, 'data', 'extender_cup', 'cup_logo.svg'))"
python3 -c "import os, shutil; d = os.listdir()[0]; shutil.make_archive(d, 'zip', '.', d)"
start .
