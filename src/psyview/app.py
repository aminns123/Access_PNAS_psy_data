from textual.app import App, ComposeResult
from textual.widgets import Static, Footer
from textual_plotext import PlotextPlot
from .state import SelectionState
from .ui.hierarchy import Hierarchy
from .ui.help_screen import HelpScreen
from .plotting.terminal import TerminalPlotRenderer


class PsyView(App):
    CSS = '''
    Screen { background: #0b111b; color: #dae5f2; }
    #heading { height: 4; padding: 0 1; color: #72d9e6; }
    Hierarchy { height: auto; max-height: 45%; }
    .choice-row { height: 5; border-top: solid #33465c; padding: 0 1; }
    .choice { width: auto; min-width: 7; height: 3; padding: 0 1; margin-right: 1; border: blank; color: #8092a9; }
    .selected { background: #203348; color: #dae5f2; }
    .active { border: dashed #6de5f2; color: #ffffff; }
    PlotextPlot { height: 1fr; min-height: 8; }
    #info { height: auto; max-height: 7; padding: 0 1; color: #a8bacd; overflow-y: auto; }
    HelpScreen { align: center middle; background: #000000 70%; }
    #help { width: 72; height: auto; padding: 2; border: round #6de5f2; background: #142132; }
    '''
    BINDINGS = [('left', 'previous', 'Previous'), ('right', 'next', 'Next'), ('down', 'child', 'Child'), ('up', 'parent', 'Parent'), ('home', 'first', 'First'), ('end', 'last', 'Last'), ('enter', 'enter', 'Open'), ('r', 'reload', 'Reload'), ('m', 'matplotlib', 'Matplotlib'), ('s', 'save', 'Save PNG'), ('h', 'help', 'Help'), ('question_mark', 'help', 'Help'), ('q', 'quit', 'Quit')]

    def __init__(self, adapter, export_dir=None):
        super().__init__()
        self.adapter = adapter
        self.selection = SelectionState(adapter)
        self.spec = None
        self.export_dir = export_dir

    def compose(self) -> ComposeResult:
        dataset = self.adapter.config['dataset']
        yield Static(f"{dataset.get('title', self.adapter.name)}\nData Explorer • Dataset: {self.adapter.name}\n{dataset.get('citation', '')}", id='heading', markup=False)
        yield Hierarchy()
        yield PlotextPlot()
        yield Static(id='info', markup=False)
        yield Footer()

    async def on_mount(self):
        await self.redraw()

    async def redraw(self):
        await self.query_one(Hierarchy).show_state(self.selection)
        try:
            self.spec = self.adapter.get_plot(self.selection.active, self.selection.filters())
            TerminalPlotRenderer().render(self.query_one(PlotextPlot), self.spec)
            info = ' | '.join(f'{k}: {v}' for k, v in self.spec.metadata.items())
            self.query_one('#info', Static).update(f'Current level: {self.adapter.levels()[self.selection.active].name}\n{info}\n{self.spec.notes}')
        except (ValueError, OSError, KeyError) as exc:
            self.spec = None
            self.query_one(PlotextPlot).plt.clear_figure()
            self.query_one(PlotextPlot).refresh()
            self.query_one('#info', Static).update(f'Cannot display selection: {exc}')

    async def action_previous(self):
        self.selection.move(-1)
        await self.redraw()

    async def action_next(self):
        self.selection.move(1)
        await self.redraw()

    async def action_child(self):
        self.selection.down()
        await self.redraw()

    async def action_parent(self):
        self.selection.up()
        await self.redraw()

    async def action_first(self):
        self.selection.move(edge='first')
        await self.redraw()

    async def action_last(self):
        self.selection.move(edge='last')
        await self.redraw()

    async def action_enter(self):
        if self.selection.active == len(self.adapter.levels()) - 1:
            self.action_matplotlib()
        else:
            await self.action_child()

    def action_matplotlib(self):
        if self.spec:
            from .plotting.matplotlib_plots import MatplotlibPlotRenderer
            try:
                MatplotlibPlotRenderer().open(self.spec)
                self.notify('Opening Matplotlib window')
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')

    def action_save(self):
        if self.spec:
            from datetime import datetime
            from pathlib import Path
            from .plotting.matplotlib_plots import MatplotlibPlotRenderer
            try:
                destination = Path(self.export_dir or Path.home() / 'psyview-exports').resolve()
                if destination.is_relative_to(self.adapter.root):
                    raise ValueError('Export folder must be outside the read-only dataset root. Use --export-dir.')
                destination.mkdir(parents=True, exist_ok=True)
                path = destination / f"psyview-{datetime.now():%Y%m%d-%H%M%S-%f}.png"
                MatplotlibPlotRenderer().save(self.spec, path)
                self.notify(f'Saved {path}', timeout=10)
            except (OSError, ValueError) as exc:
                self.notify(str(exc), severity='error')

    async def action_reload(self):
        try:
            candidate = type(self.adapter)(self.adapter.config)
            candidate.load(self.adapter.root)
            self.adapter = candidate
            self.selection.adapter = candidate
            self.selection.refresh()
            await self.redraw()
        except (ValueError, OSError, KeyError) as exc:
            self.notify(str(exc), severity='error', timeout=10)

    def action_help(self):
        self.push_screen(HelpScreen())
