# PsyView

Read-only terminal explorer for the PNAS psychophysics archive.

Use Python 3.12 or newer. On Windows, run `run_psyview.bat`, or create
a virtual environment and run `python -m pip install -e ".[test]"` followed
by `python -m psyview`. Startup opens a keyboard dataset browser. Choose your
external empirical repository, or use `--data-root PATH` to validate and open
it directly. No scientific data are copied. Detection uses structure and
column headers, not folder names. The browser starts at the last dataset's
parent, then the project parent/current directory, then home. Preferences
live in the per-user PsyView settings folder, never in the project or dataset.

Browser: Up/Down select; Enter/Right opens a dataset or enters an ordinary
directory; Left/Backspace goes to the parent; Home/End jumps; R refreshes;
Q exits. The highlighted folder is inspected and cached, with supported-dataset
details shown below the list. Use current folder opens a dataset already entered.

The Windows launcher installs dependencies only during initial setup, after
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
and diamonds identify selected final-N reversals (eight in archived mode). Bounds include 7% padding in
linear or logarithmic space. Nonpositive observations explicitly switch an
otherwise logarithmic axis to linear. Exclusions are displayed, never edited.

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
