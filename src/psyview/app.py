from textual.app import App, ComposeResult
from textual.widgets import Static, Footer
from textual_plotext import PlotextPlot
from .state import SelectionState, AnalysisState
import asyncio
from concurrent.futures import ThreadPoolExecutor
from .ui.hierarchy import Hierarchy
from .ui.help_screen import HelpScreen
from .plotting.terminal import TerminalPlotRenderer, ScientificPlot
import logging

logger = logging.getLogger(__name__)


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
    #analysis { height: 2; padding: 0 1; color: #72d9e6; }
    HelpScreen { align: center middle; background: #000000 70%; }
    #help { width: 72; height: auto; padding: 2; border: round #6de5f2; background: #142132; }
    Screen.compact #heading { height: 2; }
    Screen.compact .choice-row { height: 2; }
    Screen.compact .choice { height: 1; border: none; }
    Screen.compact #info { max-height: 2; }
    '''
    BINDINGS = [
        ('left', 'previous', 'Previous'),
        ('right', 'next', 'Next'),
        ('down', 'child', 'Child'),
        ('up', 'parent', 'Parent'),
        ('home', 'first', 'First'),
        ('end', 'last', 'Last'),
        ('enter', 'enter', 'Open'),
        ('r', 'reload', 'Reload'),
        ('m', 'matplotlib', 'Matplotlib'),
        ('s', 'save', 'Save PNG'),
        ('h', 'help', 'Help'),
        ('question_mark', 'help', 'Help'),
        ('q', 'quit', 'Quit'),
    ]
    BINDINGS += [
        ('a', 'analysis', 'Analysis'),
        ('escape', 'hierarchy_focus', 'Hierarchy'),
    ]

    def __init__(self, adapter, export_dir=None):
        super().__init__()
        self.adapter = adapter
        self.selection = SelectionState(adapter)
        self.spec = None
        self.export_dir = export_dir
        self.figure_processes = []
        default_n = int(
            getattr(adapter, 'default_n_reversals', 8)
        )
        self.analysis = AnalysisState('archived', default_n)
        self.analysis_focus = False
        self.analysis_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix='psyview-analysis',
        )
        self.analysis_task = None
        self.plot_generation = 0

    def compose(self) -> ComposeResult:
        dataset = self.adapter.config['dataset']
        yield Static(
            f"{dataset.get('title', self.adapter.name)}\n"
            f"Data Explorer • Dataset: {self.adapter.name}\n"
            f"{dataset.get('citation', '')}",
            id='heading',
            markup=False,
        )
        yield Hierarchy()
        yield Static(id='analysis', markup=False)
        yield ScientificPlot()
        yield Static(id='info', markup=False)
        yield Footer()

    async def on_mount(self):
        self.screen.set_class(
            self.size.height < 40,
            'compact',
        )
        self.set_interval(.5, self.check_figures)
        await self.redraw()

    def on_resize(self, event):
        self.screen.set_class(
            event.size.height < 40,
            'compact',
        )

    def check_figures(self):
        from .plotting.matplotlib_plots import LOG_PATH
        for process in self.figure_processes[:]:
            code = process.poll()
            if code is not None:
                self.figure_processes.remove(process)
                if code:
                    self.notify(
                        f'Matplotlib failed (exit {code}). '
                        f'Check GUI backend/Tk installation. '
                        f'Full traceback: {LOG_PATH}',
                        severity='error',
                        timeout=15,
                    )

    async def redraw(self):
        self.plot_generation += 1
        generation = self.plot_generation

        if self.analysis_task:
            self.analysis_task.cancel()

        self.spec = None

        if self.analysis.mode == 'interactive':
            self.query_one(PlotextPlot).plt.clear_figure()
            self.query_one(PlotextPlot).refresh()

        self.show_analysis()
        await self.query_one(Hierarchy).show_state(
            self.selection
        )

        if self.analysis.mode == 'interactive':
            adapter = self.adapter
            level = self.selection.active
            filters = self.selection.filters()
            analysis = self.analysis

            self.query_one(PlotextPlot).plt.clear_figure()
            self.query_one(PlotextPlot).refresh()
            self.query_one('#info', Static).update(
                f'Computing interactive final '
                f'{analysis.n_reversals} reversals… '
                f'Navigation remains available.'
            )

            async def compute():
                try:
                    spec = await asyncio.get_running_loop().run_in_executor(
                        self.analysis_executor,
                        adapter.get_plot,
                        level,
                        filters,
                        analysis,
                    )
                    if generation == self.plot_generation:
                        self.display_spec(spec)
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.exception(
                        'Interactive analysis failed'
                    )
                    if generation == self.plot_generation:
                        self.query_one(
                            '#info', Static
                        ).update(
                            f'Interactive analysis unavailable: {exc}'
                        )

            self.analysis_task = asyncio.create_task(
                compute()
            )
            return

        try:
            self.display_spec(
                self.adapter.get_plot(
                    self.selection.active,
                    self.selection.filters(),
                )
            )
        except Exception as exc:
            logger.exception('Cannot render selection')
            self.spec = None
            self.query_one(
                PlotextPlot
            ).plt.clear_figure()
            self.query_one(
                PlotextPlot
            ).refresh()
            self.query_one(
                '#info', Static
            ).update(
                f'Cannot display selection: {exc}'
            )

    def display_spec(self, spec):
        self.spec = spec
        TerminalPlotRenderer().render(
            self.query_one(PlotextPlot),
            spec,
        )
        info = ' | '.join(
            f'{k}: {v}'
            for k, v in spec.metadata.items()
        )
        self.query_one(
            '#info', Static
        ).update(
            f'Current level: '
            f'{self.adapter.levels()[self.selection.active].name}\n'
            f'{info}\n'
            f'{spec.notes}'
        )

    def show_analysis(self):
        if not hasattr(self.adapter, 'interactive'):
            self.query_one(
                '#analysis', Static
            ).update(
                'Analysis: STRUCTURAL / READ-ONLY — '
                'no scientific interactive adapter identified'
            )
            return

        focus = (
            ' [FOCUSED: ENTER switches mode; '
            '←/→ change N; A/ESC returns]'
            if self.analysis_focus
            else ' [A: focus controls]'
        )

        if self.analysis.mode == 'archived':
            mode = getattr(
                self.adapter,
                'archived_analysis_label',
                'ARCHIVED DATA',
            )
        else:
            formatter = getattr(
                self.adapter,
                'interactive_analysis_label',
                None,
            )
            mode = (
                formatter(self.analysis.n_reversals)
                if formatter
                else (
                    f'INTERACTIVE — final '
                    f'{self.analysis.n_reversals} reversals'
                )
            )

        self.query_one(
            '#analysis', Static
        ).update(
            'Analysis: ' + mode + focus
        )

    def action_analysis(self):
        if not hasattr(self.adapter, 'interactive'):
            self.notify(
                'Interactive analysis is not available '
                'for this adapter.'
            )
            return
        self.analysis_focus = not self.analysis_focus
        self.show_analysis()

    def action_hierarchy_focus(self):
        self.analysis_focus = False
        self.show_analysis()

    async def change_n(
        self,
        delta=0,
        edge=None,
    ):
        if self.analysis.mode != 'interactive':
            self.notify(
                'Press Enter to explicitly switch '
                'to interactive analysis.'
            )
            return

        maximum = self.adapter.interactive().max_n()
        n = (
            1
            if edge == 'first'
            else maximum
            if edge == 'last'
            else min(
                maximum,
                max(
                    1,
                    self.analysis.n_reversals + delta,
                ),
            )
        )
        self.analysis = AnalysisState(
            'interactive',
            n,
        )
        await self.redraw()

    def on_unmount(self):
        self.plot_generation += 1
        if self.analysis_task:
            self.analysis_task.cancel()
        self.analysis_executor.shutdown(
            wait=False,
            cancel_futures=True,
        )

    async def action_previous(self):
        if self.analysis_focus:
            await self.change_n(-1)
            return
        self.selection.move(-1)
        await self.redraw()

    async def action_next(self):
        if self.analysis_focus:
            await self.change_n(1)
            return
        self.selection.move(1)
        await self.redraw()

    async def action_child(self):
        self.analysis_focus = False
        self.selection.down()
        await self.redraw()

    async def action_parent(self):
        self.analysis_focus = False
        self.selection.up()
        await self.redraw()

    async def action_first(self):
        if self.analysis_focus:
            await self.change_n(
                edge='first'
            )
            return
        self.selection.move(edge='first')
        await self.redraw()

    async def action_last(self):
        if self.analysis_focus:
            await self.change_n(
                edge='last'
            )
            return
        self.selection.move(edge='last')
        await self.redraw()

    async def action_enter(self):
        if self.analysis_focus:
            mode = (
                'interactive'
                if self.analysis.mode == 'archived'
                else 'archived'
            )
            self.analysis = AnalysisState(
                mode,
                self.analysis.n_reversals,
            )
            await self.redraw()
            return

        if (
            self.selection.active
            == len(self.adapter.levels()) - 1
        ):
            self.action_matplotlib()
        else:
            await self.action_child()

    def action_matplotlib(self):
        if self.spec:
            from .plotting.matplotlib_plots import (
                MatplotlibPlotRenderer,
            )
            try:
                self.figure_processes.append(
                    MatplotlibPlotRenderer().open(
                        self.spec
                    )
                )
                self.notify(
                    'Starting Matplotlib window'
                )
            except Exception as exc:
                logger.exception(
                    'Cannot open Matplotlib'
                )
                self.notify(
                    str(exc),
                    severity='error',
                )
        else:
            self.notify(
                'No prepared plot is available '
                'for this selection.',
                severity='warning',
            )

    def action_save(self):
        if self.spec:
            from datetime import datetime
            from pathlib import Path
            from .plotting.matplotlib_plots import (
                MatplotlibPlotRenderer,
            )

            try:
                destination = Path(
                    self.export_dir
                    or Path.home() / 'psyview-exports'
                ).resolve()
                if destination.is_relative_to(
                    self.adapter.root
                ):
                    raise ValueError(
                        'Export folder must be outside '
                        'the read-only dataset root. '
                        'Use --export-dir.'
                    )

                destination.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                path = destination / (
                    f"psyview-"
                    f"{datetime.now():%Y%m%d-%H%M%S-%f}.png"
                )
                MatplotlibPlotRenderer().save(
                    self.spec,
                    path,
                )
                self.notify(
                    f'Saved {path}',
                    timeout=10,
                )
            except Exception as exc:
                logger.exception('Cannot save plot')
                self.notify(
                    str(exc),
                    severity='error',
                )

    async def action_reload(self):
        try:
            candidate = type(self.adapter)(
                self.adapter.config
            )
            candidate.load(
                self.adapter.root
            )
            self.adapter = candidate
            self.selection.adapter = candidate

            default_n = int(
                getattr(
                    candidate,
                    'default_n_reversals',
                    self.analysis.n_reversals,
                )
            )
            if self.analysis.mode == 'archived':
                self.analysis = AnalysisState(
                    'archived',
                    default_n,
                )

            self.selection.refresh()
            await self.redraw()
        except (
            ValueError,
            OSError,
            KeyError,
        ) as exc:
            logger.exception(
                'Cannot reload dataset'
            )
            self.notify(
                str(exc),
                severity='error',
                timeout=10,
            )

    def action_help(self):
        self.push_screen(
            HelpScreen()
        )
