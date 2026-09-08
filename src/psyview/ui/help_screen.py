from textual.screen import ModalScreen
from textual.widgets import Static


class HelpScreen(ModalScreen):
    BINDINGS = [('escape', 'dismiss', 'Close'), ('h', 'dismiss', 'Close'), ('question_mark', 'dismiss', 'Close')]

    def compose(self):
        yield Static('PSYVIEW • HELP\n\n← / →  Previous / next value\n↓ / ↑  Child / parent level\nHome / End  First / last value\nEnter  Enter child or expand final plot\nR  Reload from disk\nM  Open Matplotlib\nS  Save PNG\nH / ?  Help    Q  Quit\n\nThreshold is a result, not a navigation level.\nTerminal axes marked log10 use explicit transformed coordinates.\nParent selections are retained; branches remember child selections.\n\nEscape closes this help.', id='help', markup=False)
