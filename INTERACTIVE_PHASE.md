# External datasets and interactive final-N analysis

## Data-location audit

The project already contained a tracked empirical repository snapshot at
`PNAS_Psychopysics_data-main`: 605 tracked files, with 512 files under `data`
totalling 23,297,999 bytes. Automatic discovery could select this copy, and
real-data tests shared that discovery logic. Runtime used the preferred-frequency,
CSF threshold, staircase summary, trial, reversal, and optional archived-curve
tables. No empirical files were removed: this is scientific source material,
and deleting it was unnecessary to decouple software and data.

Automatic archive discovery is now removed. Starting without `--data-root`
opens a generic keyboard browser. Explicit `--data-root PATH` validates and
opens directly. The browser returns a validated adapter; the UI contains no
PNAS table names. Detection uses the dictionary, raw/processed structure and
required column headers, and samples at most 1000 small summary rows for the
participant count. Only highlighted candidates are inspected; results are
cached and R refreshes them. Renamed repositories work.

Last successful dataset selection is stored in per-user settings
(`%APPDATA%/PsyView/settings.json` on Windows). Startup tries its parent,
then the project parent/current directory, then home. Data stay in the selected
root; neither opening nor analysis copies empirical files into PsyView.

## Analysis definitions

Default mode is **ARCHIVED PNAS** and still uses deposited estimates and
intervals. A focuses analysis, Enter explicitly switches mode, Left/Right
changes N only while that control is focused, and A/Escape returns to the
hierarchy. Home/End reaches the minimum/maximum N. Mode and N appear in
plot titles, status and Matplotlib exports.

Interactive threshold is the median of the final N positive finite reversal
values, ordered by detected reversal number. The preserved supplied detector
runs on raw normalized trial contrasts up to `n_trials_used`, and its values
and trial indices must match deposited reversals. Mismatches stop interactive
analysis rather than silently changing the detector or data.

Available exploratory N is 1 through the dataset's maximum detected count
(12 here). N=1 is a one-reversal median, not a claim of publication suitability.
All actual archived staircases have at least nine detected reversals. The source
deterministic code slices the last eight; it supplies no general policy for an
arbitrary N larger than the observed count. PsyView therefore explicitly leaves
such an estimate unavailable and omits that staircase from interactive
aggregation, with a reason. This is a conservative interactive availability
policy, not a newly attributed historical exclusion rule. Archived primary
exclusions and CSF fit-point exclusions are retained separately.

Condition threshold is the arithmetic mean of available, primary-included
staircase medians; sensitivity is its reciprocal. The AoE model, unbounded
default fit parameters, `trf` optimizer, evaluation allowance and 1000-point
peak-search grid follow the supplied deterministic helper. Six numerical helper
bodies were preserved, with attribution/source lines in
`src/psyview/analysis/PROVENANCE.md`; no dataset entry-point code is executed.

Preferred frequency is the deterministic fitted-grid maximum. Archived mean
PSFs instead summarize retained saved resampling fits. Interactive plots never
reuse their percentile intervals. **Interactive uncertainty: not computed**
is explicit. Optional resampling was not added: the archive itself documents
unresolved historical sampling provenance and two distinct new sampling schemes.

## Numerical validation on the external repository

| Quantity, N=8 | Result |
| --- | --- |
| Raw detector versus deposited reversal rows | Matched for all 804 staircases |
| Staircase medians versus `threshold_last8_median` | All 804 exactly equal |
| CSF sensitivities versus archived inputs | All 255 exactly equal |
| Deterministic PSFs versus saved current-helper baseline peaks | All 31 agree; maximum absolute difference approximately 4.4e-16 cpd |
| Deterministic PSFs versus archived distribution means | Intentionally different estimands; maximum observed difference 1.0806861 cpd |

For example P01 at 10 cd/m² gives deterministic N=8 PSF 3.0008 cpd,
while its archived saved-fit mean is 3.23016005 cpd. Nothing was forced to match.
The per-condition comparison is retained in `.tools/interactive-n8-validation.csv`.

## Caching and responsiveness

Reversal detection and staircase thresholds are cached in memory. Conditions
are computed lazily; staircase views do not fit CSFs or analyze an entire
subject. Subject views request only the subject's luminance fits. Successful
condition fits persist as JSON under `%LOCALAPPDATA%/PsyView/cache` (or the
platform user cache fallback). No pickle or executable dataset cache is loaded.

Keys include canonical dataset root, SHA-256 source content fingerprints,
N, condition, fitting request, implementation files/version, and NumPy/SciPy
versions. Writes use a temporary file and atomic replacement. Cache writes
inside the selected dataset are refused. An unavailable user cache falls back
to memory. Tests use isolated temporary cache/settings folders.

A single background worker performs interactive preparation, with a visible
computing message. Queued obsolete requests are cancelled and generation checks
prevent stale results appearing after selection/mode changes. A running SciPy
fit cannot be forcibly interrupted; a newer request waits for it, while keyboard
navigation remains active. Source size/mtime checks require R after modifications;
reload refreshes tables and content fingerprints, preventing cross-source reuse.

## Tests and actual application checks

- 54 tests passed with `PSYVIEW_TEST_DATA` explicitly pointing to the external
  sibling repository. New standalone tests use very small synthetic datasets.
- Without real data configured, 32 tests pass and 22 real-data tests skip.
- Coverage includes browser navigation/parent/refresh, renamed and unsupported
  folders, explicit-root bypass, reversal membership and empty reversals,
  insufficient-N/excluded staircases, downstream propagation, source mismatch,
  data immutability, both renderers, state changes and cache separation/reuse.
- `scripts/audit_interactive_gui.py` selected the external dataset in the browser,
  exercised all four levels in both modes, and opened/drew/closed eight actual
  Matplotlib windows. N=6/8/12, resizing, reload, help and quit passed.
- Actual Windows PTY startup opened the browser; keyboard selection opened the
  external dataset in archived mode, then switched to interactive analysis.
- `pip check` and `git diff --check` passed. Before/after hashes of raw/processed
  files in both empirical copies showed zero changes. No tracked archive diff.

## Limitations and platform notes

Only Python 3.13.5 was available for execution. SciPy is now a declared runtime
dependency for the preserved fitter. The normal launcher's configuration hash
correctly triggers this one-time dependency update; unchanged startup remains
offline. One initial GUI run reported an Anaconda/Tk `init.tcl` lookup failure;
standalone Tk and the complete repeated eight-window run succeeded. It remains
a transient environment issue, not a demonstrated scientific/serialization bug.
Full tracebacks remain in the temporary `psyview.log`.

The browser currently registers the PNAS detector; generic CSV configuration
still works with explicit `--data-root` and `--config`. Future repositories need
their own detector/adapter. No optional uncertainty/resampling is implemented.
Very small terminals have limited space for long metadata and fit-failure details;
larger terminals or Matplotlib provide more room. Empirical files remain retained
in the old project snapshot but are no longer selected implicitly or required
by standalone tests.
