from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Footer
from textual_plotext import PlotextPlot

from .state import SelectionState, AnalysisState
import asyncio
from concurrent.futures import ThreadPoolExecutor
import math
import textwrap

from .ui.hierarchy import Hierarchy
from .ui.help_screen import HelpScreen
from .plotting.terminal import (
    TerminalPlotRenderer,
    ScientificPlot,
)

import logging

logger = logging.getLogger(__name__)


class PsyView(App):
    CSS = '''
    Screen { background: #0b111b; color: #dae5f2; }
    #heading { height: 4; padding: 0 1; color: #72d9e6; }
    Hierarchy {
        height: 7;
        max-height: 7;
        overflow-y: hidden;
    }
    #hierarchy-path {
        height: 2;
        padding: 0 1;
        color: #8092a9;
    }
    .choice-row { height: 5; border-top: solid #33465c; padding: 0 1; }
    .choice { width: auto; min-width: 7; height: 3; padding: 0 1; margin-right: 1; border: blank; color: #8092a9; }
    .selected { background: #203348; color: #dae5f2; }
    .active { border: dashed #6de5f2; color: #ffffff; }

    #plotbox {
        width: 110;
        height: 30;
        align-horizontal: center;
    }
    #plot {
        width: 74;
        height: 29;
        min-height: 18;
    }
    #legend {
        width: 34;
        height: 29;
        padding: 1 1;
        border-left: solid #33465c;
        color: #b8c7d8;
        overflow-y: auto;
    }

    #fitinfo {
        height: auto;
        max-height: 5;
        padding: 0 1;
        color: #e4c25a;
        overflow-y: auto;
    }
    #info {
        height: auto;
        max-height: 7;
        padding: 0 1;
        color: #a8bacd;
        overflow-y: auto;
    }
    #analysis { height: 2; padding: 0 1; color: #72d9e6; }

    HelpScreen {
        align: center middle;
        background: #000000 70%;
    }
    #help {
        width: 76;
        height: auto;
        padding: 2;
        border: round #6de5f2;
        background: #142132;
    }

    Screen.compact #heading { height: 2; }
    Screen.compact Hierarchy {
        height: 4;
        max-height: 4;
    }
    Screen.compact #hierarchy-path {
        height: 1;
        padding: 0 1;
    }
    Screen.compact .choice-row { height: 2; }
    Screen.compact .choice { height: 1; border: none; }
    Screen.compact #plotbox { width: 100%; height: 19; }
    Screen.compact #plot { width: 70%; height: 18; }
    Screen.compact #legend { width: 30%; height: 18; padding: 0 1; }
    Screen.compact #fitinfo { max-height: 3; }
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
        ('f', 'fit', 'Fit'),
        ('e', 'fit_edit', 'Fit points'),
        ('c', 'clear_fit', 'Clear fit exclusions'),
        ('h', 'help', 'Help'),
        ('question_mark', 'help', 'Help'),
        ('q', 'quit', 'Quit'),
        ('a', 'analysis', 'Analysis'),
        ('x', 'x_scale', 'X scale'),
        ('y', 'y_scale', 'Y scale'),
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
            getattr(
                adapter,
                'default_n_reversals',
                8,
            )
        )
        self.analysis = AnalysisState(
            'archived',
            default_n,
        )
        self.analysis_focus = False

        self.fit_enabled = False
        self.fit_edit_mode = False
        self.fit_cursor_index = 0

        # Temporary user overrides keyed by (hierarchy_level, axis).
        # Absence means use YAML/PlotSpec scientific defaults.
        self.axis_scale_overrides = {}

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
        yield Static(
            id='analysis',
            markup=False,
        )

        with Horizontal(id='plotbox'):
            yield ScientificPlot(id='plot')
            yield Static(
                id='legend',
                markup=False,
            )

        yield Static(
            id='fitinfo',
            markup=False,
        )
        yield Static(
            id='info',
            markup=False,
        )
        yield Footer()

    async def on_mount(self):
        self.screen.set_class(
            self.size.height < 40,
            'compact',
        )
        self.set_interval(
            .5,
            self.check_figures,
        )
        await self.redraw()

    def on_resize(self, event):
        self.screen.set_class(
            event.size.height < 40,
            'compact',
        )

    def check_figures(self):
        from .plotting.matplotlib_plots import (
            LOG_PATH,
        )

        for process in self.figure_processes[:]:
            code = process.poll()
            if code is not None:
                self.figure_processes.remove(
                    process
                )
                if code:
                    self.notify(
                        f'Matplotlib failed (exit {code}). '
                        f'Check GUI backend/Tk installation. '
                        f'Full traceback: {LOG_PATH}',
                        severity='error',
                        timeout=15,
                    )

    def _fit_supported_here(self):
        supports = getattr(
            self.adapter,
            'supports_fit',
            None,
        )
        return bool(
            supports
            and supports(
                self.selection.active
            )
        )

    def _analysis_for_adapter(self):
        if self.analysis.mode == 'interactive':
            return self.analysis
        return None

    def _fit_points(self):
        getter = getattr(
            self.adapter,
            'fit_points',
            None,
        )
        if (
            getter is None
            or not self._fit_supported_here()
        ):
            return []

        return getter(
            self.selection.filters(),
            self._analysis_for_adapter(),
        )

    def _fit_cursor_x(self):
        points = self._fit_points()
        if not points:
            return None

        self.fit_cursor_index = min(
            max(
                0,
                self.fit_cursor_index,
            ),
            len(points) - 1,
        )
        return points[
            self.fit_cursor_index
        ]

    @staticmethod
    def _prepare_plot(
        adapter,
        level,
        filters,
        analysis,
        use_fit,
        fit_cursor_x,
        fit_edit_mode,
    ):
        if (
            use_fit
            and hasattr(
                adapter,
                'get_plot_with_fit',
            )
        ):
            return adapter.get_plot_with_fit(
                level,
                filters,
                analysis,
                fit_cursor_x,
                fit_edit_mode,
            )

        if (
            analysis is not None
            and analysis.mode == 'interactive'
        ):
            return adapter.get_plot(
                level,
                filters,
                analysis,
            )

        return adapter.get_plot(
            level,
            filters,
        )



    def _declared_axis_policy(
        self,
        adapter,
        level,
        axis,
    ):
        policies = adapter.config.get(
            'axis_policy',
            {},
        )
    
        if not isinstance(
            policies,
            dict,
        ):
            return {}
    
        column = adapter.levels()[
            level
        ].column
    
        level_policy = policies.get(
            column,
            {},
        )
    
        if not isinstance(
            level_policy,
            dict,
        ):
            return {}
    
        policy = level_policy.get(
            axis,
            {},
        )
    
        return (
            dict(policy)
            if isinstance(policy, dict)
            else {}
        )
    
    def _effective_axis_scale(
        self,
        adapter,
        level,
        spec,
        axis,
    ):
        """YAML default -> temporary user override -> PlotSpec fallback."""
        policy = self._declared_axis_policy(
            adapter,
            level,
            axis,
        )
    
        declared = str(
            policy.get(
                'scale',
                'auto',
            )
        ).lower()
    
        if declared in (
            'linear',
            'log',
        ):
            scale = declared
            source = 'dataset config'
        else:
            scale = getattr(
                spec,
                axis + 'scale',
                'linear',
            )
            source = 'plot default'
    
        override = self.axis_scale_overrides.get(
            (level, axis)
        )
    
        if override in (
            'linear',
            'log',
        ):
            scale = override
            source = 'user override'
    
        return scale, source
    
    def _prepare_plot_with_row_axes(
        self,
        adapter,
        level,
        filters,
        analysis,
        use_fit,
        fit_cursor_x,
        fit_edit_mode,
        parent_filters,
        sibling_values,
    ):
        """Prepare current plot using one stable scale for all row siblings.
    
        Important: limits are resolved ONCE from the union of raw sibling plot
        values. We do not union already-rounded/padded limits. This keeps data
        comfortably in frame and prevents cumulative scale expansion.
        """
        spec = self._prepare_plot(
            adapter,
            level,
            filters,
            analysis,
            use_fit,
            fit_cursor_x,
            fit_edit_mode,
        )
    
        level_definition = adapter.levels()[
            level
        ]
        sibling_specs = []
    
        for value in sibling_values:
            sibling_filters = dict(
                parent_filters
            )
            sibling_filters[
                level_definition.column
            ] = value
    
            try:
                if (
                    sibling_filters == filters
                    and not (
                        use_fit
                        and fit_edit_mode
                    )
                ):
                    sibling_spec = spec
                else:
                    sibling_spec = self._prepare_plot(
                        adapter,
                        level,
                        sibling_filters,
                        analysis,
                        use_fit,
                        None,
                        False,
                    )
    
                sibling_specs.append(
                    sibling_spec
                )
    
            except Exception:
                logger.debug(
                    'Skipping unavailable sibling while resolving row axes',
                    exc_info=True,
                )
    
        if not sibling_specs:
            sibling_specs = [spec]
    
        from .plotting.axes import (
            shared_axis_limits_for_scale,
        )
    
        for axis in ('x', 'y'):
            scale, source = self._effective_axis_scale(
                adapter,
                level,
                spec,
                axis,
            )
    
            setattr(
                spec,
                axis + 'scale',
                scale,
            )
    
            # All sibling specs must be interpreted on the same scientific
            # scale while resolving this row.
            for sibling_spec in sibling_specs:
                setattr(
                    sibling_spec,
                    axis + 'scale',
                    scale,
                )
    
            spec.metadata[
                f'_{axis}_scale_source'
            ] = source
    
            # Categorical box-plot X positions are deliberately local.
            if (
                axis == 'x'
                and getattr(
                    spec,
                    'xticks',
                    [],
                )
            ):
                continue
    
            policy = self._declared_axis_policy(
                adapter,
                level,
                axis,
            )
    
            scope = str(
                policy.get(
                    'limits',
                    'row',
                )
            ).lower()
    
            # User scale override changes SCALE, not the scientific preferred
            # window. A configured log-only preferred window (e.g. CSF
            # 10..1000) is therefore disabled while viewing that axis linear.
            limit_policy = dict(
                policy
            )
    
            if (
                source == 'user override'
                and str(
                    policy.get(
                        'scale',
                        'auto',
                    )
                ).lower()
                != scale
            ):
                limit_policy.pop(
                    'preferred_min',
                    None,
                )
                limit_policy.pop(
                    'preferred_max',
                    None,
                )
                limit_policy[
                    'rounding'
                ] = 'nice'
    
            if scope == 'row':
                limits = shared_axis_limits_for_scale(
                    sibling_specs,
                    axis,
                    scale,
                    limit_policy,
                )
    
                if limits is not None:
                    setattr(
                        spec,
                        axis + 'lim',
                        limits,
                    )
    
            # `data` means leave the adapter/PlotSpec's normal local limits
            # alone; this is particularly useful for categorical axes.
    
        spec.metadata[
            '_row_axis_scope'
        ] = (
            f'fixed across {len(sibling_specs)} '
            f'{level_definition.name} value'
            + (
                ''
                if len(sibling_specs) == 1
                else 's'
            )
        )
    
        return spec
    
    async def redraw(self):
        self.plot_generation += 1
        generation = self.plot_generation

        if self.analysis_task:
            self.analysis_task.cancel()

        self.spec = None
        self.query_one(
            '#fitinfo',
            Static,
        ).update('')
        self.query_one(
            '#legend',
            Static,
        ).update('')

        use_fit = (
            self.fit_enabled
            and self._fit_supported_here()
        )

        if not self._fit_supported_here():
            self.fit_edit_mode = False

        background_work = (
            self.analysis.mode == 'interactive'
            or use_fit
        )

        if background_work:
            self.query_one(
                PlotextPlot
            ).plt.clear_figure()
            self.query_one(
                PlotextPlot
            ).refresh()

        self.show_analysis()

        await self.query_one(
            Hierarchy
        ).show_state(
            self.selection
        )

        if background_work:
            adapter = self.adapter
            level = self.selection.active
            filters = self.selection.filters()
            parent_filters = self.selection.filters(
                level
            )
            sibling_values = adapter.get_values(
                level,
                parent_filters,
            )
            analysis = (
                self.analysis
                if self.analysis.mode == 'interactive'
                else None
            )
            cursor_x = (
                self._fit_cursor_x()
                if (
                    use_fit
                    and self.fit_edit_mode
                )
                else None
            )

            self.query_one(
                PlotextPlot
            ).plt.clear_figure()
            self.query_one(
                PlotextPlot
            ).refresh()

            if (
                use_fit
                and self.fit_edit_mode
                and cursor_x is not None
            ):
                message = (
                    f'Fit-point edit: cursor at X={cursor_x:g}°. '
                    '←/→ move, Enter include/exclude.'
                )
            elif use_fit:
                message = (
                    'Fitting thesis Eq. B.25 to the '
                    'current lateral-sensitivity profile…'
                )
            else:
                message = (
                    f'Computing interactive final '
                    f'{self.analysis.n_reversals} reversals…'
                )

            self.query_one(
                '#info',
                Static,
            ).update(
                message
                + ' Navigation remains available.'
            )

            async def compute():
                try:
                    spec = await (
                        asyncio.get_running_loop()
                        .run_in_executor(
                            self.analysis_executor,
                            self._prepare_plot_with_row_axes,
                            adapter,
                            level,
                            filters,
                            analysis,
                            use_fit,
                            cursor_x,
                            self.fit_edit_mode,
                            parent_filters,
                            sibling_values,
                        )
                    )
                    if (
                        generation
                        == self.plot_generation
                    ):
                        self.display_spec(
                            spec
                        )
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.exception(
                        'Background analysis failed'
                    )
                    if (
                        generation
                        == self.plot_generation
                    ):
                        self.query_one(
                            '#info',
                            Static,
                        ).update(
                            f'Analysis unavailable: {exc}'
                        )

            self.analysis_task = (
                asyncio.create_task(
                    compute()
                )
            )
            return

        try:
            level = self.selection.active
            filters = self.selection.filters()
            parent_filters = self.selection.filters(
                level
            )
            sibling_values = self.adapter.get_values(
                level,
                parent_filters,
            )

            self.display_spec(
                self._prepare_plot_with_row_axes(
                    self.adapter,
                    level,
                    filters,
                    None,
                    use_fit,
                    None,
                    False,
                    parent_filters,
                    sibling_values,
                )
            )
        except Exception as exc:
            logger.exception(
                'Cannot render selection'
            )
            self.spec = None
            self.query_one(
                PlotextPlot
            ).plt.clear_figure()
            self.query_one(
                PlotextPlot
            ).refresh()
            self.query_one(
                '#info',
                Static,
            ).update(
                f'Cannot display selection: {exc}'
            )

    @staticmethod
    def _legend_symbol(series):
        if series.kind == 'scatter':
            return (
                series.marker
                if series.marker
                else '●'
            )

        if series.kind == 'vline':
            return '┃'

        if series.kind == 'hline':
            return '━━'

        if (
            series.kind == 'line'
            and len(series.x) == 2
            and len(series.y) == 2
            and all(
                value is not None
                and math.isfinite(float(value))
                for value in series.x
            )
            and math.isclose(
                float(series.x[0]),
                float(series.x[1]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            return '┃'

        return '━━'



    def _legend_text(self, spec):
        from .plotting.axes import (
            axis_policy,
            tick_label,
        )
    
        entries = []
        seen = set()
    
        for series in spec.series:
            label = (
                str(series.label).strip()
                if series.label
                else ''
            )
    
            if (
                not label
                or label in seen
            ):
                continue
    
            seen.add(label)
            entries.append(
                (
                    self._legend_symbol(
                        series
                    ),
                    label,
                )
            )
    
        x_scale, x_limits, _ = axis_policy(
            spec,
            'x',
        )
        y_scale, y_limits, _ = axis_policy(
            spec,
            'y',
        )
    
        lines = [
            'AXES',
            '',
            f'X: {spec.xlabel or "not specified"}',
        ]
    
        if getattr(
            spec,
            'xticks',
            [],
        ):
            lines.append(
                'X values: '
                + ' | '.join(
                    str(label)
                    for _, label
                    in spec.xticks
                )
            )
        else:
            lines.extend([
                (
                    'X range: '
                    f'{tick_label(x_limits[0])} → '
                    f'{tick_label(x_limits[1])}'
                ),
                (
                    f'X scale: {x_scale} '
                    f'({spec.metadata.get("_x_scale_source", "plot default")})'
                ),
            ])
    
        lines.extend([
            f'Y: {spec.ylabel or "not specified"}',
            (
                'Y range: '
                f'{tick_label(y_limits[0])} → '
                f'{tick_label(y_limits[1])}'
            ),
            (
                f'Y scale: {y_scale} '
                f'({spec.metadata.get("_y_scale_source", "plot default")})'
            ),
        ])
    
        scope = spec.metadata.get(
            '_row_axis_scope',
            '',
        )
        if scope:
            lines.extend([
                '',
                f'Scale: {scope}',
            ])
    
        lines.extend([
            '',
            'KEY',
            '',
        ])
    
        wrap_width = 27
    
        if not entries:
            lines.append(
                '(no labelled series)'
            )
        else:
            for symbol, label in entries:
                wrapped = textwrap.wrap(
                    label,
                    width=wrap_width,
                ) or ['']
    
                lines.append(
                    f'{symbol:<3}{wrapped[0]}'
                )
    
                for continuation in wrapped[1:]:
                    lines.append(
                        f'   {continuation}'
                    )
    
                lines.append('')
    
        return '\n'.join(lines).rstrip()
    
    def display_spec(self, spec):
        self.spec = spec

        TerminalPlotRenderer().render(
            self.query_one(
                PlotextPlot
            ),
            spec,
            show_labels=False,
        )

        self.query_one(
            '#legend',
            Static,
        ).update(
            self._legend_text(
                spec
            )
        )

        fit_text = spec.metadata.get(
            '_fit_display',
            '',
        )
        self.query_one(
            '#fitinfo',
            Static,
        ).update(
            fit_text
        )

        info = ' | '.join(
            f'{k}: {v}'
            for k, v in spec.metadata.items()
            if not str(k).startswith('_')
        )

        self.query_one(
            '#info',
            Static,
        ).update(
            f'Current level: '
            f'{self.adapter.levels()[self.selection.active].name}\n'
            f'{info}\n'
            f'{spec.notes}'
        )

    def show_analysis(self):
        if not hasattr(
            self.adapter,
            'interactive',
        ):
            mode = (
                'Analysis: STRUCTURAL / READ-ONLY — '
                'no scientific interactive adapter identified'
            )
        else:
            focus = (
                ' [FOCUSED: ENTER switches mode; '
                '←/→ change N; A/ESC returns]'
                if self.analysis_focus
                else ' [A: focus controls]'
            )

            if self.analysis.mode == 'archived':
                analysis_label = getattr(
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
                analysis_label = (
                    formatter(
                        self.analysis.n_reversals
                    )
                    if formatter
                    else (
                        f'INTERACTIVE — final '
                        f'{self.analysis.n_reversals} reversals'
                    )
                )

            mode = (
                'Analysis: '
                + analysis_label
                + focus
            )

        if self._fit_supported_here():
            mode += (
                ' | F: '
                + (
                    'HIDE FIT'
                    if self.fit_enabled
                    else 'FIT Eq. B.25'
                )
            )

            if self.fit_enabled:
                mode += (
                    ' | E: '
                    + (
                        'EXIT POINT EDIT'
                        if self.fit_edit_mode
                        else 'EDIT FIT POINTS'
                    )
                    + ' | C: CLEAR EXCLUSIONS'
                )

        self.query_one(
            '#analysis',
            Static,
        ).update(
            mode
        )


    async def _toggle_axis_scale(
        self,
        axis,
    ):
        if axis not in ('x', 'y'):
            return
    
        if (
            axis == 'x'
            and self.spec is not None
            and getattr(
                self.spec,
                'xticks',
                [],
            )
        ):
            self.notify(
                'This X axis is categorical; log/linear scaling does not apply.'
            )
            return
    
        level = self.selection.active
        key = (
            level,
            axis,
        )
    
        if key in self.axis_scale_overrides:
            del self.axis_scale_overrides[
                key
            ]
    
            self.notify(
                f'{axis.upper()} scale returned to dataset/default policy.'
            )
    
        else:
            current = (
                getattr(
                    self.spec,
                    axis + 'scale',
                    'linear',
                )
                if self.spec is not None
                else 'linear'
            )
    
            self.axis_scale_overrides[
                key
            ] = (
                'linear'
                if current == 'log'
                else 'log'
            )
    
            self.notify(
                f'{axis.upper()} scale override: '
                f'{self.axis_scale_overrides[key]}. '
                f'Press {axis.upper()} again to restore dataset/default.'
            )
    
        await self.redraw()
    
    async def action_x_scale(self):
        await self._toggle_axis_scale(
            'x'
        )
    
    async def action_y_scale(self):
        await self._toggle_axis_scale(
            'y'
        )
    
    def action_analysis(self):
        if not hasattr(
            self.adapter,
            'interactive',
        ):
            self.notify(
                'Interactive analysis is not available '
                'for this adapter.'
            )
            return

        self.fit_edit_mode = False
        self.analysis_focus = (
            not self.analysis_focus
        )
        self.show_analysis()

    async def action_fit(self):
        if not self._fit_supported_here():
            self.notify(
                'Diagnostic equation fitting is available '
                'on the lateral Luminance/profile level.'
            )
            return

        self.fit_enabled = (
            not self.fit_enabled
        )

        if not self.fit_enabled:
            self.fit_edit_mode = False

        await self.redraw()

    async def action_fit_edit(self):
        if (
            not self.fit_enabled
            or not self._fit_supported_here()
        ):
            self.notify(
                'Enable the lateral diagnostic fit with F first.'
            )
            return

        self.analysis_focus = False
        self.fit_edit_mode = (
            not self.fit_edit_mode
        )

        if self.fit_edit_mode:
            self.fit_cursor_index = 0

        await self.redraw()

    async def action_clear_fit(self):
        if (
            not self.fit_enabled
            or not self._fit_supported_here()
        ):
            self.notify(
                'No active lateral diagnostic fit to clear.'
            )
            return

        clearer = getattr(
            self.adapter,
            'clear_fit_exclusions',
            None,
        )

        if clearer is not None:
            clearer(
                self.selection.filters()
            )
            self.fit_cursor_index = 0
            await self.redraw()

    def action_hierarchy_focus(self):
        self.analysis_focus = False
        self.fit_edit_mode = False
        self.show_analysis()

    async def change_n(
        self,
        delta=0,
        edge=None,
    ):
        if (
            self.analysis.mode
            != 'interactive'
        ):
            self.notify(
                'Press Enter to explicitly switch '
                'to interactive analysis.'
            )
            return

        maximum = (
            self.adapter
            .interactive()
            .max_n()
        )

        n = (
            1
            if edge == 'first'
            else maximum
            if edge == 'last'
            else min(
                maximum,
                max(
                    1,
                    self.analysis.n_reversals
                    + delta,
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
        if self.fit_edit_mode:
            points = self._fit_points()
            if points:
                self.fit_cursor_index = (
                    self.fit_cursor_index - 1
                ) % len(points)
                await self.redraw()
            return

        if self.analysis_focus:
            await self.change_n(-1)
            return

        self.selection.move(-1)
        self.fit_cursor_index = 0
        await self.redraw()

    async def action_next(self):
        if self.fit_edit_mode:
            points = self._fit_points()
            if points:
                self.fit_cursor_index = (
                    self.fit_cursor_index + 1
                ) % len(points)
                await self.redraw()
            return

        if self.analysis_focus:
            await self.change_n(1)
            return

        self.selection.move(1)
        self.fit_cursor_index = 0
        await self.redraw()

    async def action_child(self):
        self.analysis_focus = False
        self.fit_edit_mode = False
        self.selection.down()
        await self.redraw()

    async def action_parent(self):
        self.analysis_focus = False
        self.fit_edit_mode = False
        self.selection.up()
        await self.redraw()

    async def action_first(self):
        if self.fit_edit_mode:
            self.fit_cursor_index = 0
            await self.redraw()
            return

        if self.analysis_focus:
            await self.change_n(
                edge='first'
            )
            return

        self.selection.move(
            edge='first'
        )
        self.fit_cursor_index = 0
        await self.redraw()

    async def action_last(self):
        if self.fit_edit_mode:
            points = self._fit_points()
            if points:
                self.fit_cursor_index = (
                    len(points) - 1
                )
                await self.redraw()
            return

        if self.analysis_focus:
            await self.change_n(
                edge='last'
            )
            return

        self.selection.move(
            edge='last'
        )
        self.fit_cursor_index = 0
        await self.redraw()

    async def action_enter(self):
        if self.fit_edit_mode:
            x_value = self._fit_cursor_x()
            toggler = getattr(
                self.adapter,
                'toggle_fit_exclusion',
                None,
            )

            if (
                x_value is not None
                and toggler is not None
            ):
                excluded = toggler(
                    self.selection.filters(),
                    x_value,
                )

                self.notify(
                    (
                        'Excluded'
                        if excluded
                        else 'Re-included'
                    )
                    + f' X={x_value:g}° '
                    + 'for this diagnostic fit.'
                )

                await self.redraw()
            return

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
            == len(
                self.adapter.levels()
            ) - 1
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
                    or (
                        Path.home()
                        / 'psyview-exports'
                    )
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
                logger.exception(
                    'Cannot save plot'
                )
                self.notify(
                    str(exc),
                    severity='error',
                )

    async def action_reload(self):
        try:
            candidate = type(
                self.adapter
            )(
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

            if (
                self.analysis.mode
                == 'archived'
            ):
                self.analysis = AnalysisState(
                    'archived',
                    default_n,
                )

            self.fit_enabled = False
            self.fit_edit_mode = False
            self.fit_cursor_index = 0

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
