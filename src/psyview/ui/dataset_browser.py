from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Static, OptionList, Footer
from textual.widgets.option_list import Option
from ..data.registry import detect_dataset, open_dataset
from ..preferences import starting_directory


class DatasetBrowser(App):
    """Return an already validated adapter; no dataset filenames in this UI."""
    CSS = '''
    #location { height: 4; padding: 1; }
    #details { height: auto; min-height: 4; max-height: 7; padding: 0 1; }
    OptionList { height: 1fr; }
    '''
    BINDINGS = [('backspace', 'parent', 'Parent'), ('left', 'parent', 'Parent'),
                ('right', 'open', 'Open'), ('r', 'reload', 'Refresh'), ('q', 'quit', 'Quit')]

    def __init__(self, start=None):
        super().__init__()
        self.folder = Path(start or starting_directory()).resolve()
        self.entries = []

    def compose(self) -> ComposeResult:
        yield Static(id='location', markup=False)
        yield OptionList(id='directories')
        yield Static(id='details', markup=False)
        yield Footer()

    def on_mount(self):
        self.action_reload()

    def action_reload(self):
        detect_dataset.cache_clear()
        listing = self.query_one(OptionList)
        listing.clear_options()
        self.query_one('#location', Static).update(f'PsyView — Select empirical dataset\nCurrent folder: {self.folder}')
        try:
            self.entries = [self.folder] + sorted((p for p in self.folder.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
        except OSError as exc:
            self.entries = [self.folder]
            self.query_one('#details', Static).update(f'Cannot list folder: {exc}')
        listing.add_options([Option('Use current folder' if p == self.folder else p.name, id=str(i)) for i, p in enumerate(self.entries)])
        listing.highlighted = 0
        listing.focus()
        self.show_details()

    def show_details(self):
        index = self.query_one(OptionList).highlighted
        if index is None or index >= len(self.entries):
            return
        info = detect_dataset(self.entries[index])
        self.query_one('#details', Static).update(
            f'[SUPPORTED DATASET] {info.title}\n{info.details}\nENTER to open' if info else
            'Not a supported PsyView dataset\nENTER to browse folder | BACKSPACE / LEFT for parent')

    def on_option_list_option_highlighted(self, event):
        self.show_details()

    def on_option_list_option_selected(self, event):
        self.action_open()

    def action_open(self):
        index = self.query_one(OptionList).highlighted
        if index is None:
            return
        path = self.entries[index]
        if detect_dataset(path):
            try:
                self.exit(open_dataset(path))
            except (OSError, ValueError, KeyError) as exc:
                self.query_one('#details', Static).update(f'Cannot open dataset: {exc}')
        elif path != self.folder:
            self.folder = path
            self.action_reload()

    def action_parent(self):
        self.folder = self.folder.parent
        self.action_reload()
