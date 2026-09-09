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


class TerminalPlotRenderer:
    def render(self, widget, spec):
        plt = widget.plt
        plt.clear_figure()
        plt.theme('textual-design-dark')
        plt.title(spec.title)
        for axis in ('x', 'y'):
            scale, limits, fallback = axis_policy(spec, axis)
            getattr(plt, axis+'scale')(scale)
            getattr(plt, axis+'label')(getattr(spec, axis+'label') + (' (linear: nonpositive values)' if fallback else ''))
            # Plotext 5.3 transforms data and ticks, but expects limits in
            # display coordinates. This backend-only conversion leaves raw data intact.
            bounds = [math.log10(v) for v in limits] if scale == 'log' else limits
            getattr(plt, axis+'lim')(*bounds)
            if scale == 'log':
                ticks = log_ticks(limits)
                getattr(plt, axis+'ticks')(ticks, [tick_label(v) for v in ticks])
            elif axis == 'x' and spec.xlabel.startswith('Trial'):
                step = max(1, math.ceil((limits[1]-limits[0])/6))
                ticks = list(range(max(1, math.ceil(limits[0])), math.floor(limits[1])+1, step))
                plt.xticks(ticks, [str(v) for v in ticks])
        # Measurements must remain visible over uncertainty/trajectory lines.
        for series in sorted(spec.series, key=lambda s: s.kind == 'scatter'):
            if series.kind == 'vline':
                if series.x and finite(series.x[0]):
                    plt.vertical_line(series.x[0], color=series.color)
            elif series.kind == 'hline':
                if series.y and finite(series.y[0]):
                    plt.horizontal_line(series.y[0], color=series.color)
            elif series.x:
                points = [(x, y) for x, y in zip(series.x, series.y) if finite(x) and finite(y)]
                if points:
                    x, y = map(list, zip(*points))
                    function = plt.scatter if series.kind == 'scatter' else plt.plot
                    function(x, y, label=series.label or None, color=series.color,
                             marker=series.marker if series.kind == 'scatter' else 'braille')
        widget.refresh()
