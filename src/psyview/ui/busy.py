"""Lightweight busy overlay; animation never calls the scientific renderer."""
from textual.widgets import Static


class BusyOverlay(Static):
    DEFAULT_CSS = '''
    BusyOverlay {
        display: none; position: absolute; width: 100%; height: 100%;
        layer: busy; content-align: center middle;
        background: #0b111b 85%; color: #e4c25a;
    }
    '''
    FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

    def __init__(self, **kwargs):
        super().__init__(markup=False, **kwargs)
        self.busy = False
        self.label = ''
        self.frame = 0

    def on_mount(self):
        self.animation = self.set_interval(.1, self.advance, pause=True)

    def set_busy(self, busy, label='Working…'):
        self.busy = busy
        self.label = label
        self.display = busy
        if busy:
            self.frame = 0
            self.advance()
            self.animation.resume()
        else:
            self.animation.pause()

    def advance(self):
        self.update(f'{self.FRAMES[self.frame % len(self.FRAMES)]}\n{self.label}')
        self.frame += 1
