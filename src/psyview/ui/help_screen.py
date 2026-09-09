from textual.screen import ModalScreen
from textual.widgets import Static


class HelpScreen(ModalScreen):
    BINDINGS = [
        ('escape', 'dismiss', 'Close'),
        ('h', 'dismiss', 'Close'),
        ('question_mark', 'dismiss', 'Close'),
    ]

    def compose(self):
        yield Static(
            'PSYVIEW • HELP\n\n'
            '← / →  Previous / next value\n'
            '↓ / ↑  Child / parent level\n'
            'Home / End  First / last value\n'
            'Enter  Enter child or expand final plot\n'
            'R  Reload from disk\n'
            'M  Open Matplotlib\n'
            'S  Save PNG\n'
            'F  Fit / hide diagnostic equation fit (where supported)\n'
            'H / ?  Help    Q  Quit\n\n'
            'Threshold is a result, not a navigation level.\n'
            'A focuses analysis; Enter switches archived/interactive where supported.\n'
            'With analysis focused: arrows change N; Home/End select range.\n\n'
            'LATERAL FITTING\n'
            'At Subject → Luminance:\n'
            '  F       fit/hide thesis Eq. B.25\n'
            '  E       enter/leave fit-point edit mode\n'
            '  ← / →   move the diamond fit-point cursor\n'
            '  Enter   exclude/re-include the selected point\n'
            '  C       clear all fit exclusions for this luminance\n'
            '  M       inspect the same fit in Matplotlib\n\n'
            'Excluded points remain visible and are marked with a red ×. Exclusions\n'
            'are session-only and never write to the empirical repository.\n\n'
            'The diagnostic fit is error-weighted with σ=max(full spread, 0.05).\n'
            'It uses weighted nonlinear least squares; for fixed Gaussian σ this is\n'
            'mathematically equivalent to Gaussian maximum-likelihood estimation.\n'
            'It is newly computed and is NOT labelled as a historical archived fit.\n\n'
            'BOX-PLOT VIEWS\n'
            'At Position level, threshold distributions are grouped side by side\n'
            'using the repository’s own experiment/category labels. At Experiment\n'
            'level, the selected category is shown as one box. These box plots use\n'
            'the underlying staircase trial-contrast y-axis range for context.\n\n'
            'The TUI key is displayed to the right of the boxed plot.\n\n'
            'Escape closes this help.',
            id='help',
            markup=False,
        )
