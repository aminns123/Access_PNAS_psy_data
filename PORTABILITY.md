# Portability audit

The application retains one codebase and Python `>=3.12`. Standard CPython 3.13
is recommended. Scientific calculations, plotting semantics, hierarchy, axis
policies and numerical dependencies were not changed for portability.

## Integration findings

| Area | Finding / action |
| --- | --- |
| Launch | Windows BAT is retained unchanged. Added POSIX `run_psyview.sh`, quoting paths and forwarding arguments, using `.venv/bin/python` directly. Both call the same Python setup gate. |
| Installation | Existing editable install, configuration hash, import verification and offline startup retained. No architecture-specific wheels or Homebrew requirement. |
| Subprocesses | All calls use argument lists, `sys.executable` and no shell. `CREATE_NO_WINDOW` now supplied only on Windows. GUI children are terminated/reaped on quit, with a bounded kill fallback. |
| GUI | Backend selection remains Matplotlib's responsibility. MacOSX/TkAgg/QtAgg can be used; Agg still exports PNG. Backend failure is reported without stopping the TUI. |
| Temporary files | JSON is UTF-8, closed before child launch and deleted before optional GUI imports. Parent cleanup covers spawn failure, early child exit and quitting before the child reads it. Temporary paths come from `tempfile`. |
| Paths/browser | `Path`, `resolve`, `home`, `cwd`, and parent traversal are portable, including `/` where parent equals self. No application drive-letter, backslash, EXE, BAT or activation-path assumptions found. |
| Preferences | Existing APPDATA/LOCALAPPDATA and XDG/home fallbacks retained to avoid moving user settings. macOS uses the working `.config`/`.cache` fallback, not Library. |
| CSV/gzip | pandas reads `Path` objects with inferred compression and its default UTF-8 encoding. Round-trip numeric parsing retained. No platform-specific reader was introduced. |
| YAML/case | Packaged YAML uses resource loading and explicit UTF-8. Config source filenames match detector spellings exactly; slash-separated paths work on all platforms. Empirical filename case must be preserved. |
| Exports | Existing home-based default, archive-write protection and safe timestamp PNG filenames retained. Display titles are never used as filenames. |
| Unicode | Textual/Plotext symbols and render/deepcopy handling retained. Modern UTF-8 terminals and suitable fonts are required for intended appearance. No forced global encoding or symbol substitution. |
| Analysis startup | Uses `ThreadPoolExecutor`, not multiprocessing/fork. Entry points already have `__main__` guards. Queued work is cancelled at exit; an already-running calculation finishes before interpreter exit. |
| Line endings/mode | `.sh` forced to LF, `.bat` to CRLF. No bulk renormalization. A Windows working tree cannot reliably record a Unix executable bit without staging; use the documented `chmod +x run_psyview.sh` or `sh run_psyview.sh`. |
| Docs | README now covers both platforms, manual installation, data paths, Unicode and GUI troubleshooting. Obsolete INSTALL patch-copy instructions replaced. |

## Dependency evidence

These are example published versions **within the existing dependency ranges**,
not new pins. Their release file lists include CPython 3.12/3.13 macOS ARM64
artifacts; pure-Python wheels are architecture-independent. Ordinary pip selects
compatible releases for the interpreter and macOS version. Native dependencies
also provide Intel macOS and Windows wheels. macOS 12+ is a practical baseline
for the example ARM64 SciPy release; actual wheel OS requirements vary by version.

| Dependency | Example release / evidence |
| --- | --- |
| NumPy | [2.2.6 files](https://pypi.org/project/numpy/2.2.6/#files), macOS ARM64 wheels |
| SciPy | [1.15.3 files](https://pypi.org/project/scipy/1.15.3/#files), macOS ARM64 wheels |
| pandas | [2.2.3 files](https://pypi.org/project/pandas/2.2.3/#files), macOS ARM64 wheels |
| Matplotlib | [3.10.3 files](https://pypi.org/project/matplotlib/3.10.3/#files), macOS ARM64 wheels |
| PyYAML | [6.0.2 files](https://pypi.org/project/PyYAML/6.0.2/#files), macOS ARM64 wheels |
| Textual | [8.2.8 files](https://pypi.org/project/textual/8.2.8/#files), `py3-none-any` |
| textual-plotext | [1.0.1 release metadata](https://pypi.org/pypi/textual-plotext/1.0.1/json), `py3-none-any`, Windows/macOS/Linux classifiers |
| Plotext | [5.3.2 files](https://pypi.org/project/plotext/5.3.2/#files), `py3-none-any` |

Use the standard, native architecture Python build, not an experimental
free-threaded build. No lower minimum, upper bound or platform-specific dependency
change was needed. This is a dependency/platform compatibility assessment, not
a claim that every future Python/dependency release has been tested.

Python.org macOS installers [bundle Tcl/Tk](https://www.python.org/download/mac/tcltk/).
Matplotlib documents [automatic backend selection](https://matplotlib.org/stable/users/explain/figure/backends.html).
Homebrew users can optionally add [matching Tk support](https://formulae.brew.sh/formula/python-tk@3.13).

## Verification and remaining limits

`tests/test_portability.py` covers platform-specific Popen arguments, payload
cleanup, child termination, a real headless backend failure, PNG filenames and
Unicode paths, compressed adapter/config loading outside the repository CWD,
browser-root navigation and shell-launcher orchestration with spaces/arguments.
Existing launcher tests cover first installation and subsequent offline startup.

The small GitHub Actions matrix installs and smoke-tests on Windows, macOS and
Linux with Python 3.12/3.13, using synthetic datasets and Agg. It does not open
a GUI or require an interactive terminal. Existing unrelated broken tests are
not part of this explicitly selected smoke suite.

Local verification is on Windows with Python 3.13 and a POSIX shell. A physical
Mac GUI/Terminal session, native Apple Silicon numerical execution, and hosted CI
have not been exercised here. Small floating-point differences across numerical
libraries/architectures remain possible without any change to the algorithms.
Running analysis threads may delay exit; forcibly interrupting scientific work
would require a separate change to the execution model.
