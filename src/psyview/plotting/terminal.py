import numpy as np


class TerminalPlotRenderer:
    def render(self, widget, spec):
        plt = widget.plt
        plt.clear_figure()
        plt.theme('textual-design-dark')
        # Explicit transformed coordinates avoid backend-dependent log tick behaviour.
        tx = lambda x: np.log10(x).tolist() if spec.xscale == 'log' else list(x)
        ty = lambda y: np.log10(y).tolist() if spec.yscale == 'log' else list(y)
        plt.title(spec.title)
        plt.xlabel(('log10 ' if spec.xscale == 'log' else '') + spec.xlabel)
        plt.ylabel(('log10 ' if spec.yscale == 'log' else '') + spec.ylabel)
        for series in spec.series:
            if series.kind == 'vline':
                plt.vertical_line(tx(series.x)[0], color=series.color)
            elif series.kind == 'hline':
                plt.horizontal_line(ty(series.y)[0], color=series.color)
            elif series.x:
                function = plt.scatter if series.kind == 'scatter' else plt.plot
                function(tx(series.x), ty(series.y), label=series.label or None, color=series.color, marker='dot' if series.kind == 'scatter' else 'braille')
        widget.refresh()
