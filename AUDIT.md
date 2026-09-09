# PsyView audit — 2026-09-09

## Diagnosis

The existing architecture was already appropriate: `SelectionState` maintains
branch selections; `app.py` binds navigation and M; `PNASAdapter` prepares
`PlotSpec` objects through `pnas_plots.py`; both renderers consume the same
specification. No hierarchy dispatch was missing. Raw trials and reversals
are cached lazily. Reload creates a fresh adapter and validates remembered
selections against the newly loaded branches. Numeric conditions come directly
from the archive, using round-trip float parsing and exact values selected
from those same tables. No participant-specific condition arrays are used.

The individual staircase M failure reproduced for P01, P02, P03 and P04.
The traceback led through `MatplotlibPlotRenderer.open`,
`json.dump(asdict(spec), file)`, and Python's JSON encoder to:

```
TypeError: Object of type int64 is not JSON serializable
```

Individual metadata obtained from pandas rows contains NumPy integer and boolean
scalars. JSON serialization failed before a GUI process launched. Subject,
CSF and multi-staircase serialization succeeded for those selections. Existing
tests saved PNGs but did not exercise this JSON boundary. This was not a
laptop/backend failure.

Other findings and fixes:

- Plotext 5.3.2 supports log axes, but mutates coordinates during `build()`.
  Repainting a native log plot caused `ValueError: math domain error` when
  previously transformed values were logged again. `ScientificPlot` now builds
  a disposable copy per repaint. Its backend-specific limit conversion is
  isolated; scientific arrays and tick positions remain raw.
- Terminal plots previously exposed log10 coordinates and tiny markers.
  Shared axis policy now adds padding and readable ticks; measurements are
  drawn above lines; final-eight reversals use diamonds in both renderers.
- Missing optional thresholds are omitted, and empty reversal tables are valid.
- M now supports NumPy scalars, writes subprocess tracebacks to a temporary log,
  detects noninteractive backends, and reports child-process failure in the TUI.
  It no longer forces TkAgg. Separate processes retain independent GUI loops.
- Discovery missed the actual `-main` archive folder. Integration tests could
  silently skip it. Both now discover this checkout.
- String IDs now sort naturally. No source identifiers are rewritten.
- Small terminals use compact hierarchy rows; trial ticks are integers.
- Existing screenshot tests assumed a pre-existing `.tools` folder; they now
  use pytest temporary directories.
- The existing untracked launcher was preserved with one targeted correction:
  delayed expansion of `ERRORLEVEL` after application exit. Its prior block
  expansion could report a stale status. Launcher discovery/recreation branches
  were inspected, not destructively exercised against the user's environment.

## Verification

- Clean `.audit-venv` created without system site packages from Python 3.13.5.
  Editable project and test extras installed successfully; `pip check` passed.
- 31 automated tests passed, including 64 M actions across all four hierarchy
  levels, P01–P04, and two luminances each; repeated repaint/resize, navigation,
  reload, help, optional thresholds/reversals and inclusion/exclusion variants.
- All hierarchy branches and archived aggregate threshold identities are checked
  by the existing data tests. Raw compressed trials and cache reuse are tested.
- Prepared specs and cached dataframes are compared before/after both renderers.
- A separate integration run pressed M through Textual's Pilot and launched
  32 real TkAgg subprocesses (four levels, four participants, two luminances).
  Every process opened, rendered and closed using a GUI timer with exit code 0.
  Navigation continued between openings. Results/screenshots are in `.tools`.
  The repeatable harness is `scripts/audit_gui.py`.
- The actual CLI was also launched in a Windows PTY and navigated to staircase
  and help views. The GUI exercise used automated closure, not manual mouse clicks.
- Before/after SHA-256 checks cover every file in archive `data/raw` and
  `data/processed`. No scientific files were changed.

Installed versions: Textual 8.2.8, textual-plotext 1.0.1, Plotext 5.3.2,
Matplotlib 3.11.1, pandas 3.0.5, NumPy 2.5.3, PyYAML 6.0.3, pytest 9.1.1.
Plotext now has an explicit compatible range because its native log/build
behavior is directly used. Other compatible ranges remain unchanged.

## Limitations

Python 3.12 was not installed locally, so runtime verification covers 3.13.5.
The clean environment still uses this machine's Anaconda-provided Python/Tk;
it is not a second-machine or python.org-installer test. The Windows `py`
launcher lists only Python 3.8, while the existing venv uses 3.13.5; the batch
launcher's compatible-venv reuse path accommodates that configuration.

Native desktop mouse automation was unavailable. All 32 actual GUI lifecycle
checks were automated; not every window was visually inspected. Representative
PNG output and terminal output were inspected. Very narrow terminals still
have less space for long titles, legends and metadata; resizing larger exposes
more detail. Optional curve files remain lazy, with a visible unavailable note
if missing. Scientific source files, fits and flags were never regenerated.
