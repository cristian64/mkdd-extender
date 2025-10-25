# MKDD Extender

A tool that extends Mario Kart: Double Dash!! with 144 extra race tracks and 54 extra battle stages.

## Usage

MKDD Extender needs to be provided with the following items:

- A retail ISO file of the original Mario Kart: Double Dash!! game. All regions are supported.
- The custom courses that will be inserted in the game. Custom courses can be downloaded from the
  community-powered [Custom Mario Kart: Double Dash Wiki!!](https://mkdd.org).

Once the directory containing the custom courses is specified, drag & drop the custom courses from
the left-hand side pane onto each of the empty slots in the main area.

Screenshot of the graphical user interface:

![MKDD Extender](https://github.com/user-attachments/assets/708256c1-4cc8-4a3e-a91f-ef5baab6c6f1)

Further details on how the tool is used can be found under the **Help > Instructions** menu.

> **NOTE:** Like other tools in the community (e.g. Dolphin Emulator), MKDD Extender has a portable
mode that can be enabled by creating an empty `portable.txt` file in the same directory that
contains the MKDD Extender executable. When portable mode is enabled, the application configuration
file will be saved next to the executable, instead of in the global user directory.

> **NOTE:** The tool can be used also in command-line mode. Run with `--help` to print a list of the
available arguments. On Windows, use `mkdd-extender-cli.exe` to launch the application in
command-line mode.

## Downloads

### Official Releases

Stand-alone precompiled bundles for Linux and Windows can be found in the
[**Releases**](https://github.com/cristian64/mkdd-extender/releases) section.

### Development Version

Clone the Git repository along with its submodules:

```shell
git clone https://github.com/cristian64/mkdd-extender.git --recurse-submodules
cd mkdd-extender
```

Create a Python virtual environment via `venv`:

```shell
python3 -m venv venv
```

Enable the virtual environment:

_**Windows**_
```batch
venv\Scripts\activate.bat
```

_**Unix or macOS**_
```bash
source venv/bin/activate
```

Install the required dependencies (see [`requirements.txt`](requirements.txt)):

```shell
python -m pip install -r requirements.txt
```

Launch the application by executing the `mkdd_extender.py` file:

```shell
python mkdd_extender.py
```

## References

- https://github.com/RenolY2/mkdd-track-patcher
- https://github.com/RenolY2/gc-c-kit
- https://github.com/JoshuaMKW/GeckoLoader
- https://szs.wiimm.de/wimgt/
- https://github.com/LagoLunatic/wwrando
- https://devkitpro.org
