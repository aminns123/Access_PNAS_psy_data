# PsyView fit-function UI — stage 1 implementation contract

This patch deliberately implements **only the visible interface and session state**.

## Non-negotiable behaviour

- Existing lateral thesis Eq. B.25 fitter remains unchanged.
- `F` continues to fit/hide Eq. B.25 exactly as before.
- Only the current displayed lateral profile is fitted; hidden siblings remain
  empirical-only for shared-axis calculations.
- At the lateral Subject -> Luminance/profile level the right panel visibly
  contains a `FIT FUNCTION` section.
- `G` opens a keyboard modal editor.
- Applying editor text stores a **session-only preview** and refreshes the panel.
- The preview is explicitly labelled `NOT FITTED`; it is never executed.
- `Ctrl+D` restores the default/no-preview state.
- `Esc` cancels without changing state.
- `V` still replaces the right panel with View controls and restores it on close.
- No empirical files are written.
- No fit mathematics, axis mathematics, plotting data, cache logic or Matplotlib
  rendering is changed.
- No `eval`/`exec`, parser or generic SciPy custom fitting is introduced in stage 1.
- The new `G` binding is hidden from the footer, matching F/E/C, but it is shown
  clearly in the right-side panel and help screen.

## Why this stage exists

It gives a clean pass/fail boundary: first verify the equation interface is
visible and usable on Windows/macOS without touching scientific fitting. Only
after that works should a later stage connect validated custom equations to a
generic fitter.
