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
            'Log axes show raw scientific values; diamonds mark final-N reversals.\n'
            'A focuses analysis; Enter switches archived/interactive where supported.\n'
            'With analysis focused: arrows change N; Home/End select range.\n'
            'A/Escape returns to hierarchy. Interactive uncertainty is not computed.\n'
            'The threshold reducer is experiment-specific (median for CSF; geometric\n'
            'mean for lateral sensitivity).\n\n'
            'LATERAL FITTING\n'
            'At Subject → Luminance, press F to fit thesis Eq. B.25 to the currently\n'
            'displayed lateral-sensitivity profile. The fit uses full spread with a\n'
            '0.05 floor for weighting and is newly computed/diagnostic, not an\n'
            'archived historical fit. Press M to inspect the same fit in Matplotlib.\n\n'
            'Escape closes this help.',
            id='help',
            markup=False,
        )
