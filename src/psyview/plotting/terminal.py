import math
from copy import deepcopy

from textual_plotext import PlotextPlot

from .axes import axis_policy, finite, log_ticks, tick_label


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
    """Identify a finite two-point vertical interval/error-bar series."""
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
    """Sample an interval uniformly in terminal display coordinates.

    On log axes, geometric sampling gives an approximately uniform visual
    vertical stroke. On linear axes, ordinary linear interpolation is used.
    """
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
    def render(self, widget, spec):
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

            # Plotext 5.3 transforms data and ticks, but expects limits in
            # display coordinates. This backend-only conversion leaves raw
            # scientific data unchanged.
            bounds = (
                [math.log10(v) for v in limits]
                if scale == 'log'
                else limits
            )
            getattr(plt, axis + 'lim')(*bounds)

            if scale == 'log':
                ticks = log_ticks(limits)
                getattr(plt, axis + 'ticks')(
                    ticks,
                    [tick_label(v) for v in ticks],
                )
            elif (
                axis == 'x'
                and spec.xlabel.startswith('Trial')
            ):
                step = max(
                    1,
                    math.ceil(
                        (limits[1] - limits[0]) / 6
                    ),
                )
                ticks = list(
                    range(
                        max(1, math.ceil(limits[0])),
                        math.floor(limits[1]) + 1,
                        step,
                    )
                )
                plt.xticks(
                    ticks,
                    [str(v) for v in ticks],
                )

        # Draw lines/intervals first and measurements last so points remain
        # visible on top of uncertainty bars and trajectories.
        for series in sorted(
            spec.series,
            key=lambda s: s.kind == 'scatter',
        ):
            if series.kind == 'vline':
                if series.x and finite(series.x[0]):
                    plt.vertical_line(
                        series.x[0],
                        color=series.color,
                    )
                continue

            if series.kind == 'hline':
                if series.y and finite(series.y[0]):
                    plt.horizontal_line(
                        series.y[0],
                        color=series.color,
                    )
                continue

            # Plotext's braille line rasterisation can put a two-point vertical
            # segment one sub-cell away from a scatter marker. For uncertainty
            # intervals, render a stack of heavy vertical glyphs at the exact
            # same x coordinate instead. The measurement scatter is drawn later,
            # so it remains centred on top of the bar.
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
                    label=series.label or None,
                    color=series.color,
                    marker='┃',
                )

                # Heavy endpoint caps make the interval easier to distinguish
                # from trajectories without altering the scientific values.
                lo, hi = sorted(
                    (
                        float(series.y[0]),
                        float(series.y[1]),
                    )
                )
                plt.scatter(
                    [x_value, x_value],
                    [lo, hi],
                    color=series.color,
                    marker='━',
                )
                continue

            if series.x:
                points = [
                    (x, y)
                    for x, y in zip(
                        series.x,
                        series.y,
                    )
                    if finite(x) and finite(y)
                ]
                if points:
                    x, y = map(
                        list,
                        zip(*points),
                    )
                    function = (
                        plt.scatter
                        if series.kind == 'scatter'
                        else plt.plot
                    )
                    function(
                        x,
                        y,
                        label=series.label or None,
                        color=series.color,
                        marker=(
                            series.marker
                            if series.kind == 'scatter'
                            else 'braille'
                        ),
                    )

        widget.refresh()
