# PNAS numerical helpers

`source_helpers.py` preserves six function bodies from the supplied PNAS
`code/analysis/source_helpers.py` without numerical changes. Original library
source references: reversal detector LIB001 4935–4975; AoE 7403–7406;
peak lookup 715–722; makeList 6564–6568; fit_to_CSF 21483–21495;
fitFunctionLimit 21499–21522. Attribution: supplied analysis accompanying
*Intrinsic Organization of Contrast Sensitivity in Human Vision*, archive
DOI 10.5281/zenodo.22644071. No empirical tables are packaged in PsyView.

The archive's LICENSE_CODE.txt says the Zenodo record lists CC BY 4.0 but
separate software-specific terms have not been confirmed; this file does not
assert a new license or resolve that notice.

The deterministic call follows `reproduce.py:baseline_fits`: AoE, unbounded
default initial parameters, SciPy `curve_fit(method='trf', maxfev=5000000)`,
1000-point grid beginning at 0.1 and ending before max(frequency)+10, choosing
the last grid maximum. It does not reproduce saved resampling draws.

Raw staircase trials are restricted to `n_trials_used` (the archive caps at
200), detected with the preserved helper, and cross-checked against deposited
reversal rows before interactive use. Positive finite reversal values are
eligible; the final N are ordered by detected reversal number. N ranges from
1 to the largest detected count; N=1 is explicitly a one-reversal exploratory
median, not a publication estimate. Fewer-than-N staircases receive no estimate,
and are omitted from aggregation with an explicit reason. Existing primary
exclusions and CSF point exclusions remain in force for every N.
