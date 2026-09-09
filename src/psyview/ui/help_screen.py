from textual.screen import ModalScreen
from textual.widgets import Static


class HelpScreen(ModalScreen):
    BINDINGS = [('escape', 'dismiss', 'Close'), ('h', 'dismiss', 'Close'), ('question_mark', 'dismiss', 'Close')]

    def compose(self):
        yield Static('PSYVIEW • HELP\n\n← / →  Previous / next value\n↓ / ↑  Child / parent level\nHome / End  First / last value\nEnter  Enter child or expand final plot\nR  Reload from disk\nM  Open Matplotlib\nS  Save PNG\nH / ?  Help    Q  Quit\n\nThreshold is a result, not a navigation level.\nLog axes show raw scientific values; diamonds mark final eight reversals.\nA focuses analysis; Enter switches archived/interactive.\nWith analysis focused: arrows change N; Home/End select range.\nA/Escape returns to hierarchy. Interactive uncertainty is not computed.\nParent selections are retained; branches remember child selections.\n\nEscape closes this help.', id='help', markup=False)
