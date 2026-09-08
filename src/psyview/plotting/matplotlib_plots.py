"""Render the same plot specification using physical values and native log axes."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from ..models import PlotSpec, Series

COLORS = {'cyan': '#087e8b', 'blue': '#315caa', 'green': '#27804b', 'magenta': '#9b4d96', 'yellow': '#b77912', 'white': '#526477', 'red': '#c83232'}


class MatplotlibPlotRenderer:
    def figure(self, spec, figure=None):
        from matplotlib.figure import Figure
        fig = figure if figure is not None else Figure(figsize=(11, 6.5), layout='constrained')
        ax = fig.subplots()
        for series in spec.series:
            kwargs = dict(color=COLORS.get(series.color, series.color), label=series.label or '_nolegend_')
            if series.kind == 'vline':
                ax.axvline(series.x[0], linestyle='--', linewidth=1, **kwargs)
            elif series.kind == 'hline':
                ax.axhline(series.y[0], linestyle='--', linewidth=1, **kwargs)
            elif series.kind == 'scatter':
                ax.scatter(series.x, series.y, s=24, marker='x' if series.color == 'red' else 'o', zorder=3, **kwargs)
            else:
                ax.plot(series.x, series.y, linestyle='--' if series.dashed else '-', linewidth=1.2, **kwargs)
        ax.set(title=spec.title, xlabel=spec.xlabel, ylabel=spec.ylabel, xscale=spec.xscale, yscale=spec.yscale)
        ax.grid(alpha=.2)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(fontsize=8, loc='best')
        import textwrap
        fig.supxlabel('\n'.join(textwrap.wrap(spec.notes, 125)), fontsize=8)
        return fig

    def save(self, spec, path):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        figure = self.figure(spec)
        FigureCanvasAgg(figure)
        figure.savefig(path, dpi=200)
        figure.clear()

    def open(self, spec):
        # A separate process owns the Windows GUI event loop so navigation continues.
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8', delete=False) as file:
            json.dump(asdict(spec), file)
            path = file.name
        try:
            process = subprocess.Popen([sys.executable, '-m', 'psyview.plotting.matplotlib_plots', path], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError:
            Path(path).unlink(missing_ok=True)
            raise
        return process


def show_payload(path, close_after=None):
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib import pyplot as plt
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    finally:
        path.unlink(missing_ok=True)
    payload['series'] = [Series(**s) for s in payload['series']]
    fig = plt.figure(figsize=(11, 6.5), layout='constrained')
    MatplotlibPlotRenderer().figure(PlotSpec(**payload), fig)
    if close_after is not None:
        fig.canvas.manager.window.after(close_after, lambda: plt.close(fig))
    plt.show()


if __name__ == '__main__':
    show_payload(sys.argv[1])
