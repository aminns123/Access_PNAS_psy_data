import math
from copy import deepcopy

from textual_plotext import PlotextPlot

from ..models import FIT_COLOR
from .axes import axis_policy, anchor_ticks, finite, log_ticks, tick_label


class ScientificPlot(PlotextPlot):
    def render(self):
        # Plotext's build mutates log coordinates. Each Textual repaint must
        # build a disposable copy, including resizes and notification refreshes.
        original = self._plot
        self._plot = deepcopy(original)
        try:
            return super().render()
        finally:
            self._plot = original


def _is_vertical_interval(series):
    if series.kind != 'line' or len(series.x) != 2 or len(series.y) != 2:
        return False
    if not all(finite(v) for v in (*series.x, *series.y)):
        return False
    return math.isclose(
        float(series.x[0]),
        float(series.x[1]),
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def _interval_samples(y0, y1, scale, count=25):
    y0 = float(y0)
    y1 = float(y1)
    lo, hi = sorted((y0, y1))

    if math.isclose(lo, hi, rel_tol=0.0, abs_tol=1e-15):
        return [lo]

    count = max(5, int(count))

    if scale == 'log' and lo > 0:
        a = math.log10(lo)
        b = math.log10(hi)
        return [
            10 ** (a + (b - a) * i / (count - 1))
            for i in range(count)
        ]

    return [
        lo + (hi - lo) * i / (count - 1)
        for i in range(count)
    ]


class TerminalPlotRenderer:
    def render(self, widget, spec, *, show_labels=True):
        plt = widget.plt
        plt.clear_figure()
        plt.theme('textual-design-dark')
        plt.title(spec.title)

        display_scales = {}

        for axis in ('x', 'y'):
            scale, limits, fallback = axis_policy(spec, axis)
            display_scales[axis] = scale

            getattr(plt, axis + 'scale')(scale)
            getattr(plt, axis + 'label')(
                getattr(spec, axis + 'label')
                + (
                    ' (linear: nonpositive values)'
                    if fallback
                    else ''
                )
            )

            bounds = (
                [math.log10(v) for v in limits]
                if scale == 'log'
                else limits
            )
            getattr(plt, axis + 'lim')(*bounds)

            custom_ticks = getattr(
                spec,
                axis + 'ticks',
                [],
            )

            if custom_ticks:
                positions = [
                    float(position)
                    for position, _ in custom_ticks
                ]
                labels = [
                    str(label)
                    for _, label in custom_ticks
                ]
                getattr(
                    plt,
                    axis + 'ticks',
                )(
                    positions,
                    labels,
                )

            # Every numeric y-axis explicitly shows its displayed minimum,
            # visual midpoint and displayed maximum.  This is intentionally
            # global rather than box-plot-specific.
            elif axis == 'y':
                ticks = anchor_ticks(
                    limits,
                    scale,
                )
                if ticks:
                    getattr(
                        plt,
                        axis + 'ticks',
                    )(
                        ticks,
                        [
                            tick_label(value)
                            for value in ticks
                        ],
                    )

            elif scale == 'log':
                ticks = log_ticks(limits)
                getattr(plt, axis + 'ticks')(
                    ticks,
                    [tick_label(v) for v in ticks],
                )

            elif axis == 'x' and spec.xlabel.startswith('Trial'):
                step = max(
                    1,
                    math.ceil((limits[1] - limits[0]) / 6),
                )
                ticks = list(
                    range(
                        max(1, math.ceil(limits[0])),
                        math.floor(limits[1]) + 1,
                        step,
                    )
                )
                plt.xticks(ticks, [str(v) for v in ticks])

        def label_for(series):
            if show_labels and series.label:
                return series.label
            return None

        def display_color(series):
            # General visual convention: fitted/model curves are red.
            # Restrict this to line series so labels such as "Included in fit"
            # on measurement points are not recoloured.
            label = (series.label or '').casefold()
            if (
                series.kind == 'line'
                and (
                    ' fit' in (' ' + label)
                    or 'curve' in label
                )
            ):
                return FIT_COLOR
            return series.color

        # Measurements remain visible over uncertainty/trajectory lines.
        for series in sorted(
            spec.series,
            key=lambda s: s.kind == 'scatter',
        ):
            if series.kind == 'vline':
                if series.x and finite(series.x[0]):
                    plt.vertical_line(
                        series.x[0],
                        color=display_color(series),
                    )
                continue

            if series.kind == 'hline':
                if series.y and finite(series.y[0]):
                    plt.horizontal_line(
                        series.y[0],
                        color=display_color(series),
                    )
                continue

            # Heavy, exactly-centred terminal uncertainty intervals.
            if _is_vertical_interval(series):
                x_value = float(series.x[0])
                y_values = _interval_samples(
                    series.y[0],
                    series.y[1],
                    display_scales['y'],
                )
                x_values = [x_value] * len(y_values)

                plt.scatter(
                    x_values,
                    y_values,
                    label=label_for(series),
                    color=display_color(series),
                    marker='┃',
                )

                lo, hi = sorted(
                    (float(series.y[0]), float(series.y[1]))
                )
                plt.scatter(
                    [x_value, x_value],
                    [lo, hi],
                    color=display_color(series),
                    marker='━',
                )
                continue

            if series.x:
                points = [
                    (x, y)
                    for x, y in zip(series.x, series.y)
                    if finite(x) and finite(y)
                ]
                if points:
                    x, y = map(list, zip(*points))
                    function = (
                        plt.scatter
                        if series.kind == 'scatter'
                        else plt.plot
                    )
                    function(
                        x,
                        y,
                        label=label_for(series),
                        color=display_color(series),
                        marker=(
                            series.marker
                            if series.kind == 'scatter'
                            else 'braille'
                        ),
                    )

        widget.refresh()
