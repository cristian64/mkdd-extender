# MKDD Extender

A tool that extends Mario Kart: Double Dash!! with 48 extra courses.

## Usage

MKDD Extender needs to be provided with the following items:

- A retail ISO file of the original Mario Kart: Double Dash!! game. All regions are supported.
- The custom tracks that will be inserted in the game. Custom tracks can be downloaded from the
  community-powered [Custom Mario Kart: Double Dash Wiki!!](https://mkdd.miraheze.org).

Once the directory containing the custom tracks is specified, drag & drop the custom tracks from
the left-hand side pane onto each of the 48 slots in the main area.

Screenshot of the graphical user interface:

![MKDD Extender](https://user-images.githubusercontent.com/1853278/178599784-8b3c92c4-46bc-4794-9742-1ef4ae35455b.png)

Further details on how the tool is used can be found under the **Help > Instructions** menu.

> **NOTE:** The tool can be used also in command-line mode. Run with `--help` to print a list of the
available arguments. On Windows, use `mkdd-extender-cli.exe` to launch the application in
command-line mode.

## Downloads

### Official Releases

Stand-alone precompiled bundles for Linux and Windows can be found in the
[**Releases**](https://github.com/cristian64/mkdd-extender/releases) section.

### Compiling From Source

Clone the Git repository along with its submodules:

```shell
git clone https://github.com/cristian64/mkdd-extender.git
cd mkdd-extender
git submodule update --init
```

There are a number of Python dependencies (see [`requirements.txt`](requirements.txt)) that need to
be installed first:

```shell
python3 -m pip install --user -r requirements.txt
```

Then you can launch MKDD Extender by executing the `mkdd_extender.py` file:

```shell
python3 mkdd_extender.py
```
