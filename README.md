# PsyView

Read-only terminal explorer for the PNAS psychophysics archive.

## Running PsyView

Use **standard CPython 3.13 (recommended), minimum 3.12**. The existing Python
minimum and dependency ranges are unchanged. Windows 10/11, macOS Intel and
Apple Silicon, and Linux use the same Python application. First setup needs
internet access to install dependencies; later unchanged launches work offline.
Git is optional: a downloaded ZIP works after extraction. Keep empirical data
in a separate folder; PsyView reads it without modifying it.

### Windows

Install Python from [python.org](https://www.python.org/downloads/windows/),
including the Python launcher, then double-click `run_psyview.bat` or run:

```bat
run_psyview.bat
```

Windows Terminal is recommended. The existing Windows launcher is retained.

### macOS (Intel or Apple Silicon)

Install the standard Python 3.13 **macOS universal2 installer** from
[python.org](https://www.python.org/downloads/macos/). It runs natively on Intel
and Apple Silicon (M1/M2/M3/M4 and later ARM64 Macs); Homebrew is not required.
Open a new Terminal window after installing. Then:

```sh
git clone https://github.com/aminns123/Access_PNAS_psy_data.git
cd Access_PNAS_psy_data
chmod +x run_psyview.sh
./run_psyview.sh
```

For a ZIP download, `cd` into the extracted folder instead. The `chmod` step is
needed if the download/checkout did not preserve execute permission; alternatively
use `sh run_psyview.sh`. Paths containing spaces are supported. The launcher uses
`.venv/bin/python` directly and creates the environment when needed. To choose a
particular Python on first setup:

```sh
PSYVIEW_PYTHON="/path/to/python3.13" ./run_psyview.sh
```

Use a native ARM64 Python/Terminal on Apple Silicon. Do not copy `.venv` between
computers, architectures or operating systems. An incompatible local environment
is preserved as `.venv.incompatible-*` and replaced. On macOS, allow Terminal access
to Documents/Desktop or removable storage if prompted when browsing your data.

### Linux

Install Python 3.12+ with `venv`/pip support using your distribution's packages,
then run `sh run_psyview.sh`. Debian/Ubuntu may require `python3-venv`; Tk support
(`python3-tk`) is optional for Matplotlib windows. A desktop session is needed for
GUI windows, but terminal plots and PNG export also work without one.

### Choosing data and exporting

Startup opens a keyboard folder browser. Select the external empirical repository,
or supply paths directly (quote paths with spaces):

```sh
./run_psyview.sh --data-root "/Users/name/Research/PNAS data" --export-dir "/Users/name/psyview-exports"
```

On Windows pass the same options to `run_psyview.bat` with Windows paths.
The default export directory is `psyview-exports` in your home folder. PNG names
use portable timestamps, independently of display titles. Detection uses structure
and column headers, not folder names. Preserve the archive's exact filename case.
The browser starts at the last dataset's parent, then the project parent/current
directory, then home. Preferences remain in per-user storage outside the dataset
(`APPDATA`/`LOCALAPPDATA` on Windows; XDG directories or `~/.config/PsyView` and
`~/.cache/PsyView/cache` on macOS/Linux).

### Manual installation fallback

Windows (Command Prompt):

```bat
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m psyview
```

macOS/Linux (ensure `python3 --version` is 3.12+):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m psyview
```

Add `--data-root PATH` to the final command to bypass the browser.

### Matplotlib windows and terminal fonts

**M** opens a separate process using the same environment Python. Matplotlib
chooses its GUI backend; PsyView does not force one. MacOSX, TkAgg or QtAgg may be
used depending on your installation. **S** saves PNG without requiring a GUI.
If M fails, PsyView remains usable and reports the temporary `psyview.log` path.
Check the selected backend and, optionally, test Tk:

```sh
.venv/bin/python -c "import matplotlib; print(matplotlib.get_backend())"
.venv/bin/python -m tkinter
```

On Windows replace `.venv/bin/python` with `.venv\Scripts\python.exe`.
Python.org macOS installers [include their own Tcl/Tk](https://www.python.org/download/mac/tcltk/).
For Homebrew Python 3.13 only, missing Tk can optionally be installed with
[`brew install python-tk@3.13`](https://formulae.brew.sh/formula/python-tk@3.13)
(use a matching version). An explicitly set `MPLBACKEND=Agg` disables windows;
unset it for automatic selection. See the
[Matplotlib backend guide](https://matplotlib.org/stable/users/explain/figure/backends.html).

Keep the terminal's normal UTF-8 encoding and use a Unicode-capable monospace
font in Windows Terminal, macOS Terminal or iTerm2. Symbols such as ●, ◆ and →
are retained; a missing glyph is a font/display issue. Do not force a legacy
ASCII terminal encoding. Quit with Q: PsyView closes its Matplotlib child windows
and cancels queued analysis. A calculation already running in a worker thread
finishes before Python exits; large fits can therefore delay final shutdown.

Browser: Up/Down select; Enter/Right opens a dataset or enters an ordinary
directory; Left/Backspace goes to the parent; Home/End jumps; R refreshes;
Q exits. The highlighted folder is inspected and cached, with supported-dataset
details shown below the list. Use current folder opens a dataset already entered.

Both launchers install dependencies only during initial setup, after
`pyproject.toml` changes, or when an import check fails. It records the SHA-256
of the successfully installed configuration in `.venv/.psyview_pyproject_hash`.
Unchanged launches run no pip commands and work offline. Setup bootstraps the
declared build tools, then installs with `--no-build-isolation`; failures are
logged in `.venv/.psyview_setup.log` and do not advance the successful hash.
Interrupted updates must complete before launch. Incompatible environments
are preserved in a timestamped `.venv.incompatible-*` folder, never deleted.

Left/right change values; up/down change hierarchy level; Home/End select
the first/last value. M opens the current plot in a separate Matplotlib
window, S exports PNG outside the archive, R reloads tables and clears
caches, H/? opens help, and Q exits. Branch selections are remembered.

Analysis starts in **ARCHIVED PNAS** mode. Press A to focus analysis controls,
then Enter to switch modes. In interactive mode, Left/Right changes N and
Home/End selects the available range; A/Escape returns to hierarchy navigation.
The threshold is the median of the final N positive, finite detected reversals,
with deposited reversal rows checked against the preserved raw-trial detector.
N ranges from one to the dataset's largest reversal count. Staircases with
fewer than N valid reversals get no interactive estimate and a visible reason.
Archived exclusions and CSF fit-point exclusions remain in effect.

Interactive sensitivity is the reciprocal of the mean included staircase
threshold. CSFs use the supplied deterministic AoE fitting helper and its
original optimizer/grid; the grid peak supplies interactive preferred frequency.
This peak is **not** the archived mean of saved resampled PSFs. Interactive
uncertainty is not computed, and archived intervals are never reused for N.
Both TUI and Matplotlib label analysis mode and N. Archived references are
explicitly labelled.

Fitting runs in a background worker with a computing status; obsolete results
cannot replace a newer selection. Results are cached in memory and successful
condition fits persist under the per-user PsyView cache directory (Windows:
`%LOCALAPPDATA%/PsyView/cache`). Keys include root identity, source content hashes,
N, numerical implementation and NumPy/SciPy versions. R clears memory and reloads
data; unchanged disk results can be reused. Source changes require R and produce
a different content key. Cache writes are forbidden inside the selected dataset.

Subject, luminance, spatial-frequency and staircase views share prepared
scientific data between terminal and Matplotlib rendering. Scientific values
remain raw. Logarithmic axes show physical values, circles show measurements,
and diamonds identify selected final-N reversals (eight in archived mode).
Automatic and shared sibling-row limits use empirical observations and their
displayed uncertainty. Fits, model bands, references and diagnostic cursors are
overlays and cannot enlarge either axis. Exclusions are displayed, never edited.

Adapters can set `Series.role` to `data` (the backward-compatible default),
`uncertainty` (empirical intervals), `fit` (including model uncertainty),
`reference`, or `cursor`. Only `data` and `uncertainty` contribute to automatic
limits; horizontal/vertical reference-line kinds are also excluded for legacy
specs. Explicit limits remain authoritative. Series labels do not determine
axis extents. YAML `axis_policy` supplies scales, row/local sharing, rounding,
and soft `preferred_min`/`preferred_max` bounds. Lateral profiles prefer −1 to +1
but expand for empirical excursions. Log limits ignore nonpositive empirical
coordinates, falling back to linear when no positive empirical values remain.

M needs an interactive Matplotlib backend. Backend selection is automatic;
ordinary Python installations with working Tk support can use TkAgg.
An explicitly configured noninteractive backend such as Agg cannot open
windows. GUI subprocess errors are reported in the TUI and full tracebacks
are appended to `psyview.log` in the user temporary directory. Run
`python -m psyview --debug` for verbose diagnostics. PNG export works without
a GUI. SciPy is required for interactive fits; archived mode reads saved outputs.

Run `python -m pytest -q` for synthetic unit tests. Real-data integration tests
require `PSYVIEW_TEST_DATA` pointing to an external dataset; otherwise they skip.
Tests use
temporary output folders and do not modify the archive.

Run `python scripts/audit_gui.py` to repeat the 32 real-window integration
checks. This opens GUI windows and closes each automatically after rendering.

See `AUDIT.md` for verification results and platform limitations.
