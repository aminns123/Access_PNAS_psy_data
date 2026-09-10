from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Container
from textual.widgets import Static, Footer
from textual_plotext import PlotextPlot

from .state import SelectionState, AnalysisState
import asyncio
from concurrent.futures import ThreadPoolExecutor
import math
import textwrap

from .ui.hierarchy import Hierarchy
from .ui.help_screen import HelpScreen
from .ui.busy import BusyOverlay
from .ui.axis_limit_screen import AxisLimitScreen
from .ui.view_state import SCALE_CHOICES, SCOPE_CHOICES, cycle_choice
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
    #plot-stage {
        width: 74;
        height: 29;
        min-height: 18;
        layers: plot busy;
    }
    #plot { width: 100%; height: 100%; layer: plot; }
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
    Screen.compact #plot-stage { width: 70%; height: 18; }
    Screen.compact #legend { width: 30%; height: 18; padding: 0 1; }
    Screen.compact #fitinfo { max-height: 3; }
    Screen.compact #info { max-height: 2; }
    '''

    BINDINGS = [
        ('left', 'previous', 'Previous'),
        ('right', 'next', 'Next'),
        ('down', 'child', 'Child'),
        ('up', 'parent', 'Parent'),
        Binding('home', 'first', 'First', show=False),
        Binding('end', 'last', 'Last', show=False),
        ('enter', 'enter', 'Open'),
        ('a', 'analysis', 'Analysis'),
        ('v', 'view', 'View'),
        Binding('x', 'x_scale', 'X scale', show=False),
        Binding('y', 'y_scale', 'Y scale', show=False),
        ('r', 'reload', 'Reload'),
        ('m', 'matplotlib', 'Matplotlib'),
        ('s', 'save', 'Save PNG'),
        Binding('f', 'fit', 'Fit', show=False),
        Binding('e', 'fit_edit', 'Fit points', show=False),
        Binding('c', 'clear_fit', 'Clear fit exclusions', show=False),
        ('h', 'help', 'Help'),
        Binding('question_mark', 'help', 'Help', show=False),
        ('q', 'quit', 'Quit'),
        Binding('escape', 'hierarchy_focus', 'Hierarchy', show=False),
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

        # Session-only View overrides, scoped by hierarchy level/view type.
        # Missing entries mean the dataset/default policy remains authoritative.
        self.axis_scale_overrides = {}
        self.axis_limit_overrides = {}
        self.axis_scope_overrides = {}
        self.view_focus = False
        self.view_index = 0

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
            with Container(id='plot-stage'):
                yield ScientificPlot(id='plot')
                yield BusyOverlay(id='fit-spinner')
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
            cleanup_plot_payload,
        )

        for process in self.figure_processes[:]:
            code = process.poll()
            if code is not None:
                try:
                    cleanup_plot_payload(process)
                except OSError:
                    logger.warning('Could not remove plot payload', exc_info=True)
                self.figure_processes.remove(
                    process
                )
                if code:
                    self.notify(
                        f'Matplotlib failed (exit {code}). '
                        f'Check the Matplotlib GUI backend (MacOSX, TkAgg or QtAgg). '
                        f'Terminal plots and PNG export remain available. '
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


    def _axis_config(self, level, axis):
        """Return optional YAML display policy for one hierarchy level."""
        policies = self.adapter.config.get(
            'axis_policy',
            {},
        )
        if not isinstance(policies, dict):
            return {}

        column = self.adapter.levels()[
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

    def _decorate_axis_policy(
        self,
        spec,
        level,
    ):
        """Resolve each sibling's display policy before sharing physical limits."""
        from .plotting.axes import axis_policy, apply_declared_limit_policy

        for axis in ('x', 'y'):
            policy = self._axis_config(
                level,
                axis,
            )

            configured = str(
                policy.get(
                    'scale',
                    'auto',
                )
            ).lower()

            original_scale = getattr(
                spec,
                axis + 'scale',
                'linear',
            )

            override = self.axis_scale_overrides.get(
                (
                    level,
                    axis,
                )
            )

            # A manual log request must not hide nonpositive empirical content
            # when navigating to a different row. Dataset log defaults retain
            # their existing scientific policy.
            if override == 'log' and not spec.metadata.get('_log_available', {}).get(axis, True):
                override = None

            if override in (
                'linear',
                'log',
            ):
                target_scale = override
                source = 'user override'
            elif configured in (
                'linear',
                'log',
            ):
                target_scale = configured
                source = 'dataset config'
            else:
                target_scale = original_scale
                source = 'plot default'

            # Categorical positions and labels remain local and linear.
            if axis == 'x' and spec.xticks:
                continue

            setattr(spec, axis + 'scale', target_scale)
            if target_scale != original_scale:
                setattr(spec, axis + 'lim', None)
            scale, limits, _ = axis_policy(spec, axis)
            setattr(spec, axis + 'lim', apply_declared_limit_policy(
                limits, scale, policy,
            ))

            spec.metadata[
                f'_{axis}_scale_source'
            ] = source

        return spec

    @classmethod
    def _prepare_plot_with_row_axes(
        cls,
        adapter,
        level,
        filters,
        analysis,
        use_fit,
        fit_cursor_x,
        fit_edit_mode,
        parent_filters,
        sibling_values,
        decorate_axis_policy=None,
        scope_override=None,
    ):
        """Prepare current plot and lock its scale to its hierarchy row.
    
        "Row" means the values selectable with left/right at the current
        hierarchy depth, under the currently selected parents.
    
        Examples:
          Subject row:
              all subjects share one x/y range.
    
          Luminance row:
              all luminances for the current subject share one x/y range.
    
          Spatial-frequency row:
              all frequencies for the current subject/luminance share one
              y range. If the plot is categorical (box plot), x remains local.
    
          Staircase row:
              all staircases under the current parents share one x/y range.
        """
        spec = cls._prepare_plot(
            adapter,
            level,
            filters,
            analysis,
            use_fit,
            fit_cursor_x,
            fit_edit_mode,
        )
    
        level_definition = adapter.levels()[level]
        sibling_specs = []
    
        for value in sibling_values:
            sibling_filters = dict(
                parent_filters
            )
            sibling_filters[
                level_definition.column
            ] = value
    
            try:
                # Reuse current plot when it has no transient edit cursor.
                if (
                    sibling_filters == filters
                    and not (
                        use_fit
                        and fit_edit_mode
                    )
                ):
                    sibling_spec = spec
                else:
                    sibling_spec = cls._prepare_plot(
                        adapter,
                        level,
                        sibling_filters,
                        analysis,
                        False,
                        None,
                        False,
                    )
    
                sibling_specs.append(
                    sibling_spec
                )
    
            # A single unavailable sibling must not make the current valid
            # selection disappear. Available siblings still define the scale.
            except Exception:
                logger.debug(
                    'Skipping sibling while resolving shared row axes',
                    exc_info=True,
                )
    
        if not sibling_specs:
            sibling_specs = [spec]
    
        from .plotting.axes import (
            shared_axis_limits,
            empirical_axis_values,
        )

        # Check the empirical row before applying any manual scale override.
        # Fits/references do not make a log axis valid or invalid.
        raw_policies = adapter.config.get('axis_policy', {}).get(
            level_definition.column,
            {},
        )
        policies = {
            axis: dict(raw_policies.get(axis, {}))
            if isinstance(raw_policies.get(axis, {}), dict)
            else {}
            for axis in ('x', 'y')
        }
        if scope_override in ('data', 'row'):
            for axis in ('x', 'y'):
                policies[axis]['limits'] = scope_override

        row_available = {}
        for axis in ('x', 'y'):
            values = [v for source in sibling_specs for v in empirical_axis_values(source, axis)]
            row_available[axis] = bool(values) and all(v > 0 for v in values)
        for item in [spec] + [s for s in sibling_specs if s is not spec]:
            available = dict(row_available)
            for axis in ('x', 'y'):
                if policies.get(axis, {}).get('limits') == 'data':
                    values = empirical_axis_values(item, axis)
                    available[axis] = bool(values) and all(v > 0 for v in values)
            item.metadata['_log_available'] = available
            if decorate_axis_policy is not None:
                decorate_axis_policy(item, level)
    
        shared_y = shared_axis_limits(
            sibling_specs,
            'y',
        )
        if shared_y is not None and policies.get('y', {}).get('limits') != 'data':
            spec.ylim = shared_y
    
        # Box/categorical plots intentionally keep their x positions local.
        # Their category label (e.g. selected spatial frequency, base/flanker)
        # remains the x-axis value, while only y is fixed across siblings.
        if not getattr(
            spec,
            'xticks',
            [],
        ):
            shared_x = shared_axis_limits(
                sibling_specs,
                'x',
            )
            if shared_x is not None and policies.get('x', {}).get('limits') != 'data':
                spec.xlim = shared_x
    
        shared_axes = []
        if policies.get('y', {}).get('limits') != 'data':
            shared_axes.append('Y')
        if (
            not getattr(spec, 'xticks', [])
            and policies.get('x', {}).get('limits') != 'data'
        ):
            shared_axes.append('X')

        if shared_axes:
            spec.metadata['_row_axis_scope'] = (
                f"{'/'.join(shared_axes)} fixed across {len(sibling_specs)} "
                f'{level_definition.name} value'
                + ('' if len(sibling_specs) == 1 else 's')
                + (' (user override)' if scope_override else '')
            )
        else:
            spec.metadata['_row_axis_scope'] = (
                'current selection data'
                + (' (user override)' if scope_override else '')
            )

        spec.metadata['_limit_scope_source'] = (
            'user override' if scope_override else 'dataset config'
        )
    
        return spec

    def _restore_keyboard_focus(self):
        """Return key handling to the app after transient controls/redraws.

        PsyView's hierarchy and View menu are keyboard-state driven rather than
        widget-focus driven. A dismissed Textual Input/modal can otherwise leave
        a stale focused control behind on some terminals (notably Windows).
        Clearing widget focus after the next refresh keeps the app-level
        bindings active without stealing focus from an open modal.
        """
        try:
            self.screen.set_focus(None)
        except Exception:
            logger.debug(
                'Could not clear transient Textual focus',
                exc_info=True,
            )

    def _queue_keyboard_focus_restore(self):
        try:
            self.call_after_refresh(
                self._restore_keyboard_focus
            )
        except Exception:
            logger.debug(
                'Could not queue keyboard focus restore',
                exc_info=True,
            )

    def set_busy(self, busy, label='Working…'):
        self.query_one(BusyOverlay).set_busy(busy, label)

    async def redraw(self, force_background=False):
        self.plot_generation += 1
        generation = self.plot_generation
        self.set_busy(False)

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
            force_background
            or self.analysis.mode == 'interactive'
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
            self.set_busy(True, 'Fitting…' if use_fit else 'Computing…')
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
                            self._decorate_axis_policy,
                            self.axis_scope_overrides.get(level),
                        )
                    )
                    if (
                        generation
                        == self.plot_generation
                    ):
                        self._apply_view_axis_limits(spec, level)
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
                finally:
                    if generation == self.plot_generation:
                        self.set_busy(False)

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

            spec = self._prepare_plot_with_row_axes(
                self.adapter,
                level,
                filters,
                None,
                use_fit,
                None,
                False,
                parent_filters,
                sibling_values,
                self._decorate_axis_policy,
                self.axis_scope_overrides.get(level),
            )
            self._apply_view_axis_limits(spec, level)
            self.display_spec(
                spec
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



    def _view_items(self):
        """Return the rows in the keyboard-first View panel."""
        categorical_x = bool(
            self.spec is not None
            and getattr(self.spec, 'xticks', [])
        )
        return [
            ('x_scale', 'X scale', categorical_x),
            ('x_min', 'X minimum', categorical_x),
            ('x_max', 'X maximum', categorical_x),
            ('y_scale', 'Y scale', False),
            ('y_min', 'Y minimum', False),
            ('y_max', 'Y maximum', False),
            ('scope', 'Limit scope', False),
            ('reset', 'Reset defaults', False),
        ]

    def _normalize_view_index(self):
        selectable = [
            index
            for index, (_, _, disabled) in enumerate(self._view_items())
            if not disabled
        ]
        if not selectable:
            self.view_index = 0
        elif self.view_index not in selectable:
            self.view_index = selectable[0]

    def _view_move(self, delta):
        selectable = [
            index
            for index, (_, _, disabled) in enumerate(self._view_items())
            if not disabled
        ]
        if not selectable:
            return

        self._normalize_view_index()
        position = selectable.index(self.view_index)
        step = 1 if delta >= 0 else -1
        self.view_index = selectable[(position + step) % len(selectable)]
        self._refresh_right_panel()

    def _configured_scope_label(self, level):
        policies = self.adapter.config.get('axis_policy', {}).get(
            self.adapter.levels()[level].column,
            {},
        )
        scopes = []
        for axis in ('x', 'y'):
            if (
                axis == 'x'
                and self.spec is not None
                and getattr(self.spec, 'xticks', [])
            ):
                continue
            policy = policies.get(axis, {})
            if isinstance(policy, dict):
                scope = str(policy.get('limits', 'row')).lower()
                if scope in ('data', 'row'):
                    scopes.append(scope)

        if not scopes:
            return 'Row'
        if len(set(scopes)) == 1:
            return scopes[0].title()
        return 'Mixed'

    def _auto_axis_limits(self, spec, axis):
        from .plotting.axes import axis_policy

        stored = spec.metadata.get(f'_auto_{axis}lim')
        if isinstance(stored, (tuple, list)) and len(stored) == 2:
            return tuple(float(value) for value in stored)

        _, limits, _ = axis_policy(spec, axis)
        return tuple(float(value) for value in limits)

    def _apply_view_axis_limits(self, spec, level):
        """Apply manual display bounds after PsyView resolves automatic axes."""
        from .plotting.axes import axis_policy

        for axis in ('x', 'y'):
            if axis == 'x' and getattr(spec, 'xticks', []):
                continue

            scale, automatic, _ = axis_policy(spec, axis)
            automatic = tuple(float(value) for value in automatic)
            spec.metadata[f'_auto_{axis}lim'] = automatic

            manual = self.axis_limit_overrides.get((level, axis), {})
            lower = manual.get('min')
            upper = manual.get('max')
            effective_lower = automatic[0] if lower is None else float(lower)
            effective_upper = automatic[1] if upper is None else float(upper)

            # Editing validates this before state is stored. Keep this guard so
            # stale session state can never corrupt the plot.
            if effective_lower >= effective_upper:
                continue
            if scale == 'log' and (
                effective_lower <= 0
                or effective_upper <= 0
            ):
                continue

            setattr(
                spec,
                axis + 'lim',
                (effective_lower, effective_upper),
            )
            spec.metadata[f'_{axis}_limit_source'] = (
                'user override'
                if lower is not None or upper is not None
                else 'automatic'
            )

        return spec

    def _view_value(self, key, spec):
        from .plotting.axes import axis_policy, tick_label

        level = self.selection.active

        if key in ('x_scale', 'y_scale'):
            axis = key[0]
            if axis == 'x' and getattr(spec, 'xticks', []):
                return 'Categorical'
            override = self.axis_scale_overrides.get((level, axis))
            effective, _, _ = axis_policy(spec, axis)
            if override is None:
                return f'Default ({effective.title()})'
            return override.title()

        if key in ('x_min', 'x_max', 'y_min', 'y_max'):
            axis = key[0]
            if axis == 'x' and getattr(spec, 'xticks', []):
                return 'Categorical'
            bound = 'min' if key.endswith('_min') else 'max'
            manual = self.axis_limit_overrides.get((level, axis), {})
            value = manual.get(bound)
            if value is not None:
                return tick_label(value)

            limits = self._auto_axis_limits(spec, axis)
            auto_value = limits[0 if bound == 'min' else 1]
            return f'Auto [{tick_label(auto_value)}]'

        if key == 'scope':
            override = self.axis_scope_overrides.get(level)
            if override is None:
                return f'Default ({self._configured_scope_label(level)})'
            return override.title()

        return ''

    def _view_panel_text(self, spec):
        if spec is None:
            return 'VIEW\n\nPlot is being prepared…'

        self._normalize_view_index()
        items = self._view_items()
        by_key = {
            key: (index, label, disabled)
            for index, (key, label, disabled) in enumerate(items)
        }

        lines = ['VIEW', '', 'X AXIS']
        for key in ('x_scale', 'x_min', 'x_max'):
            index, label, disabled = by_key[key]
            prefix = '›' if index == self.view_index and not disabled else ' '
            lines.append(f'{prefix} {label:<11} {self._view_value(key, spec)}')

        lines.extend(['', 'Y AXIS'])
        for key in ('y_scale', 'y_min', 'y_max'):
            index, label, disabled = by_key[key]
            prefix = '›' if index == self.view_index and not disabled else ' '
            lines.append(f'{prefix} {label:<11} {self._view_value(key, spec)}')

        lines.extend(['', 'GENERAL'])
        for key in ('scope', 'reset'):
            index, label, disabled = by_key[key]
            prefix = '›' if index == self.view_index and not disabled else ' '
            value = self._view_value(key, spec)
            lines.append(f'{prefix} {label}' + (f'  {value}' if value else ''))

        lines.extend([
            '',
            '↑↓ Select',
            '←→ Change choice',
            'Enter Edit / activate',
            'Esc or V Close',
            '',
            'Session-only overrides',
        ])
        return '\n'.join(lines)

    def _refresh_right_panel(self, spec=None):
        current = self.spec if spec is None else spec
        panel = self.query_one('#legend', Static)
        if self.view_focus:
            panel.update(self._view_panel_text(current))
        elif current is not None:
            panel.update(self._legend_text(current))
        else:
            panel.update('')

    def _can_use_log(self, axis):
        if self.spec is None:
            return False
        if axis == 'x' and getattr(self.spec, 'xticks', []):
            return False

        available = self.spec.metadata.get('_log_available', {}).get(axis)
        if available is None:
            from .plotting.axes import empirical_axis_values
            values = empirical_axis_values(self.spec, axis)
            available = bool(values) and all(value > 0 for value in values)

        if not available:
            return False

        manual = self.axis_limit_overrides.get(
            (self.selection.active, axis),
            {},
        )
        return all(
            value is None or value > 0
            for value in (manual.get('min'), manual.get('max'))
        )

    async def _view_change(self, delta):
        self._normalize_view_index()
        key = self._view_items()[self.view_index][0]
        level = self.selection.active

        if key in ('x_scale', 'y_scale'):
            axis = key[0]
            current = self.axis_scale_overrides.get((level, axis))
            target = cycle_choice(current, SCALE_CHOICES, delta)

            if target == 'log' and not self._can_use_log(axis):
                self.notify(
                    f'Cannot use logarithmic {axis.upper()} scale: '
                    'the displayed empirical data/uncertainty or a manual '
                    'bound is non-positive.'
                )
                return

            if target is None:
                self.axis_scale_overrides.pop((level, axis), None)
            else:
                self.axis_scale_overrides[(level, axis)] = target

            await self.redraw(force_background=True)
            return

        if key == 'scope':
            current = self.axis_scope_overrides.get(level)
            target = cycle_choice(current, SCOPE_CHOICES, delta)
            if target is None:
                self.axis_scope_overrides.pop(level, None)
            else:
                self.axis_scope_overrides[level] = target

            await self.redraw(force_background=True)
            return

        if key in ('x_min', 'x_max', 'y_min', 'y_max'):
            self.notify('Press Enter to edit this bound; type Auto to clear it.')

    async def _view_activate(self):
        self._normalize_view_index()
        key = self._view_items()[self.view_index][0]

        if key in ('x_scale', 'y_scale', 'scope'):
            await self._view_change(1)
            return

        if key == 'reset':
            level = self.selection.active
            for axis in ('x', 'y'):
                self.axis_scale_overrides.pop((level, axis), None)
                self.axis_limit_overrides.pop((level, axis), None)
            self.axis_scope_overrides.pop(level, None)
            self.notify('View overrides reset to dataset defaults.')
            await self.redraw(force_background=True)
            return

        if key in ('x_min', 'x_max', 'y_min', 'y_max'):
            axis = key[0]
            bound = 'min' if key.endswith('_min') else 'max'
            self._open_axis_limit_editor(axis, bound)

    def _open_axis_limit_editor(self, axis, bound):
        if self.spec is None:
            return
        if axis == 'x' and getattr(self.spec, 'xticks', []):
            self.notify('This X axis is categorical.')
            return

        current = self.axis_limit_overrides.get(
            (self.selection.active, axis),
            {},
        ).get(bound)
        title = f'{axis.upper()} {"minimum" if bound == "min" else "maximum"}'

        def receive(result):
            if result is not None:
                self._receive_axis_limit(axis, bound, result)
            # The Input lived on a modal screen. Once that screen is dismissed,
            # explicitly clear any stale Textual focus on the next refresh.
            self._queue_keyboard_focus_restore()

        self.push_screen(AxisLimitScreen(title, current), receive)

    def _receive_axis_limit(self, axis, bound, result):
        from .plotting.axes import axis_policy
        from .ui.view_state import validate_bound_pair

        if self.spec is None:
            return

        level = self.selection.active
        key = (level, axis)
        manual = dict(self.axis_limit_overrides.get(key, {}))

        if result.get('mode') == 'auto':
            manual.pop(bound, None)
            if manual:
                self.axis_limit_overrides[key] = manual
            else:
                self.axis_limit_overrides.pop(key, None)
            asyncio.create_task(self.redraw(force_background=True))
            return

        value = result.get('value')
        if value is None:
            return

        scale = axis_policy(self.spec, axis)[0]
        candidate = dict(manual)
        candidate[bound] = float(value)

        automatic = self._auto_axis_limits(self.spec, axis)
        lower = candidate.get('min')
        upper = candidate.get('max')
        effective_lower = automatic[0] if lower is None else lower
        effective_upper = automatic[1] if upper is None else upper

        try:
            validate_bound_pair(effective_lower, effective_upper, scale)
        except ValueError as exc:
            self.notify(str(exc), severity='warning')
            return

        self.axis_limit_overrides[key] = candidate
        asyncio.create_task(self.redraw(force_background=True))

    def action_view(self):
        if self.view_focus:
            self.view_focus = False
            self._refresh_right_panel()
            self._queue_keyboard_focus_restore()
            return

        if self.spec is None:
            self.notify('View options are available once the plot is prepared.')
            return

        self.analysis_focus = False
        self.fit_edit_mode = False
        self.view_focus = True
        self._normalize_view_index()
        self.show_analysis()
        self._refresh_right_panel()
        self._queue_keyboard_focus_restore()

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
            category_text = ' | '.join(
                str(label)
                for _, label in spec.xticks
            )
            lines.append(
                f'X values: {category_text}'
            )
        else:
            lines.append(
                'X range: '
                f'{tick_label(x_limits[0])} → '
                f'{tick_label(x_limits[1])}'
            )
            lines.append(
                f'X scale: {x_scale} '
                f'({spec.metadata.get("_x_scale_source", "plot default")})'
            )
    
        lines.extend([
            f'Y: {spec.ylabel or "not specified"}',
            (
                'Y range: '
                f'{tick_label(y_limits[0])} → '
                f'{tick_label(y_limits[1])}'
            ),
            f'Y scale: {y_scale} '
            f'({spec.metadata.get("_y_scale_source", "plot default")})',
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

        self._refresh_right_panel(spec)

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

        self._queue_keyboard_focus_restore()

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

    async def _toggle_axis_scale(self, axis):
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
                f'{axis.upper()} scale returned to dataset/default.'
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
            if current != 'log':
                from .plotting.axes import empirical_axis_values
                values = empirical_axis_values(self.spec, axis) if self.spec is not None else []
                valid = bool(values) and all(value > 0 for value in values)
                if self.spec is not None:
                    valid = self.spec.metadata.get('_log_available', {}).get(axis, valid)
                manual = self.axis_limit_overrides.get(key, {})
                if valid and any(
                    value is not None and value <= 0
                    for value in (manual.get('min'), manual.get('max'))
                ):
                    valid = False
                if not valid:
                    self.notify(
                        f'{axis.upper()} log scale requires positive empirical data, uncertainty, '
                        'and manual bounds throughout the displayed row. Scale unchanged.'
                    )
                    return
            self.axis_scale_overrides[
                key
            ] = (
                'linear'
                if current == 'log'
                else 'log'
            )
            self.notify(
                f'{axis.upper()} scale: '
                f'{self.axis_scale_overrides[key]} '
                f'(temporary override).'
            )

        await self.redraw(force_background=True)

    async def action_x_scale(self):
        await self._toggle_axis_scale(
            'x'
        )

    async def action_y_scale(self):
        await self._toggle_axis_scale(
            'y'
        )

    def action_analysis(self):
        if self.view_focus:
            self.view_focus = False
            self._refresh_right_panel()

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

        await self.redraw(force_background=True)

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
        if self.view_focus:
            self.view_focus = False
            self._refresh_right_panel()
            self._queue_keyboard_focus_restore()
            return

        self.analysis_focus = False
        self.fit_edit_mode = False
        self.show_analysis()
        self._queue_keyboard_focus_restore()

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
        from subprocess import TimeoutExpired
        from .plotting.matplotlib_plots import close_plot_process

        self.plot_generation += 1

        if self.analysis_task:
            self.analysis_task.cancel()

        self.analysis_executor.shutdown(
            wait=False,
            cancel_futures=True,
        )
        for process in self.figure_processes:
            try:
                close_plot_process(process)
            except (OSError, TimeoutExpired):
                logger.warning('Could not close plot process', exc_info=True)
        self.figure_processes.clear()

    async def action_previous(self):
        if self.view_focus:
            await self._view_change(-1)
            return

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
        if self.view_focus:
            await self._view_change(1)
            return

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
        if self.view_focus:
            self._view_move(1)
            return

        self.analysis_focus = False
        self.fit_edit_mode = False
        self.selection.down()
        await self.redraw()

    async def action_parent(self):
        if self.view_focus:
            self._view_move(-1)
            return

        self.analysis_focus = False
        self.fit_edit_mode = False
        self.selection.up()
        await self.redraw()

    async def action_first(self):
        if self.view_focus:
            return

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
        if self.view_focus:
            return

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
        if self.view_focus:
            await self._view_activate()
            return

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
            await self.redraw(force_background=True)
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
            self.axis_scale_overrides.clear()
            self.axis_limit_overrides.clear()
            self.axis_scope_overrides.clear()
            self.view_focus = False
            self.view_index = 0

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
