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
            'Enter  Enter child or expand final plot\n'
            'A  Focus analysis controls\n'
            'V  Open / close View options\n'
            'R  Reload from disk\n'
            'M  Open Matplotlib\n'
            'S  Save PNG\n'
            'F  Fit / hide diagnostic equation fit (where supported)\n'
            'G  Select/edit custom fit function (where supported)\n'
            'H / ?  Help    Q  Quit\n\n'
            'VIEW OPTIONS\n'
            'Press V to temporarily replace the right-side AXES/KEY panel.\n'
            '  ↑ / ↓   select a View setting\n'
            '  ← / →   cycle Scale or Limit scope\n'
            '  Enter   edit a numeric minimum/maximum or activate/reset\n'
            '  Escape  close View and return arrows to hierarchy navigation\n'
            '  Auto    in the numeric editor restores the automatic bound\n\n'
            'View overrides are session-only and scoped to the current hierarchy\n'
            'level/view type. Manual bounds may intentionally crop the display.\n'
            'Log scale is refused when empirical data/uncertainty are non-positive.\n'
            'Categorical X axes disable numeric X controls.\n\n'
            'X/Y still work as hidden compatibility shortcuts. Home/End also remain\n'
            'available but are not advertised in the normal footer.\n\n'
            'Threshold is a result, not a navigation level.\n'
            'A focuses analysis; Enter switches archived/interactive where supported.\n'
            'With analysis focused: arrows change N; Home/End select range.\n\n'
            'LATERAL FITTING\n'
            'At Subject → Luminance:\n'
            '  F       fit/hide thesis Eq. B.25\n'
            '  G       select/edit a custom fit function\n'
            '  E       enter/leave fit-point edit mode\n'
            '  ← / →   move the diamond fit-point cursor\n'
            '  Enter   exclude/re-include the selected point\n'
            '  C       clear all fit exclusions for this luminance\n'
            '  M       inspect the same fit in Matplotlib\n\n'
            'G accepts a restricted mathematical expression plus parameter starts/bounds.\n'
            'When a custom function is selected, F fits that function to the CURRENT\n'
            'displayed lateral profile. Ctrl+R restores the specialist thesis Eq. B.25\n'
            'fitter; Esc cancels. Custom functions are session-only.\n\n'
            'Excluded points remain visible and are marked with a red ×. Exclusions\n'
            'are session-only and never write to the empirical repository.\n\n'
            'The diagnostic fit is error-weighted with σ=max(full spread, 0.05).\n'
            'It uses weighted nonlinear least squares; for fixed Gaussian σ this is\n'
            'mathematically equivalent to Gaussian maximum-likelihood estimation.\n'
            'It is newly computed and is NOT labelled as a historical archived fit.\n\n'
            'COMPACT HIERARCHY\n'
            'Previous levels collapse into a single breadcrumb, e.g.\n'
            'P01 | 40 | 0.768 | base | S1. Only the current level remains\n'
            'as a full boxed selector row, so the plot stays fixed in place.\n\n'
            'BOX-PLOT VIEWS\n'
            'At Position level, threshold distributions are grouped side by side\n'
            'using the repository’s own experiment/category labels. At Experiment\n'
            'level, the selected category is shown as one box.\n\n'
            'Escape closes this help.',
            id='help',
            markup=False,
        )
