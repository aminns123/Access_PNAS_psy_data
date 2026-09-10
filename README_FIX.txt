PsyView responsiveness / keyboard-focus fix

Built from the latest src.zip supplied in chat.

Install:
1. Close PsyView.
2. Extract this ZIP into the root of Access_PNAS_psy_data.
3. Choose Replace files in the destination.
4. Run run_psyview.bat normally.

What this fixes:
- After dismissing the View numeric Input, PsyView explicitly clears stale
  Textual widget focus on the next refresh.
- View scale/scope/min/max changes use the existing background executor rather
  than running an otherwise-synchronous row recomputation on the UI loop.
- Hidden X/Y scale changes, fit on/off, and archived/interactive mode changes
  also request a background redraw.
- Every completed plot display queues keyboard-focus recovery.
- No CSF/lateral calculations, fits, error bars, axis science, data files,
  repository discovery, or renderer mathematics were changed.

Expected behavior:
- Change Y min/max in V View, press Enter, and the TUI should remain responsive.
- You should not need to switch Windows desktops to get arrow/key input back.
- For a recalculation that takes time, the existing Computing/Fitting busy
  indicator can appear while the event loop remains available.

Rollback:
Replace src/psyview/app.py with your prior copy if needed.
