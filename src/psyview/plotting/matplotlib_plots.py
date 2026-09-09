"""Render the same plot specification using physical values and native log axes."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from ..models import PlotSpec, Series
from .axes import axis_policy, finite, log_ticks, tick_label
import numpy as np

LOG_PATH = Path(tempfile.gettempdir()) / 'psyview.log'


def json_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f'Unsupported plot payload value: {type(value).__name__}')

COLORS = {'cyan': '#087e8b', 'blue': '#315caa', 'green': '#27804b', 'magenta': '#9b4d96', 'yellow': '#b77912', 'white': '#526477', 'red': '#c83232'}


class MatplotlibPlotRenderer:
    def figure(self, spec, figure=None):
        from matplotlib.figure import Figure
        fig = figure if figure is not None else Figure(figsize=(11, 6.5), layout='constrained')
        ax = fig.subplots()
        for series in spec.series:
            kwargs = dict(color=COLORS.get(series.color, series.color), label=series.label or '_nolegend_')
            if series.kind == 'vline':
                if series.x and finite(series.x[0]):
                    ax.axvline(series.x[0], linestyle='--', linewidth=1, **kwargs)
            elif series.kind == 'hline':
                if series.y and finite(series.y[0]):
                    ax.axhline(series.y[0], linestyle='--', linewidth=1, **kwargs)
            elif series.kind == 'scatter':
                ax.scatter(series.x, series.y, s=54 if series.marker == '◆' else 38, marker='D' if series.marker == '◆' else 'x' if series.color == 'red' else 'o', zorder=3, **kwargs)
            else:
                ax.plot(series.x, series.y, linestyle='--' if series.dashed else '-', linewidth=1.2, **kwargs)
        ax.set(title=spec.title, xlabel=spec.xlabel, ylabel=spec.ylabel, xscale=spec.xscale, yscale=spec.yscale)
        from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter, MaxNLocator
        for axis in ('x', 'y'):
            scale, limits, fallback = axis_policy(spec, axis)
            getattr(ax, 'set_'+axis+'scale')(scale)
            getattr(ax, 'set_'+axis+'lim')(limits)
            target = getattr(ax, axis+'axis')
            if scale == 'log':
                target.set_major_locator(FixedLocator(log_ticks(limits)))
                target.set_major_formatter(FuncFormatter(lambda v, pos: tick_label(v)))
                target.set_minor_formatter(NullFormatter())
            if fallback:
                getattr(ax, 'set_'+axis+'label')(getattr(spec, axis+'label')+' (linear: nonpositive values)')
        if spec.xlabel.startswith('Trial'):
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(alpha=.2)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(fontsize=8, loc='best')
        import textwrap
        details = ' | '.join(f'{k}: {v}' for k, v in spec.metadata.items() if k in ('included_in_primary_csf', 'threshold_last8_median', 'Exclusion reason'))
        fig.supxlabel('\n'.join(textwrap.wrap(spec.notes + ' ' + details, 125)), fontsize=8)
        return fig

    def save(self, spec, path):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        figure = self.figure(spec)
        FigureCanvasAgg(figure)
        figure.savefig(path, dpi=200)
        figure.clear()

    def open(self, spec, *, close_after=None):
        # A separate process owns the Windows GUI event loop so navigation continues.
        payload = json.dumps(asdict(spec), default=json_scalar)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8', delete=False) as file:
            file.write(payload)
            path = file.name
        try:
            command = [sys.executable, '-m', 'psyview.plotting.matplotlib_plots', path]
            if close_after is not None:
                command.append(str(close_after))
            with LOG_PATH.open('a', encoding='utf-8') as log:
                process = subprocess.Popen(command, stderr=log, stdout=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError:
            Path(path).unlink(missing_ok=True)
            raise
        return process


def show_payload(path, close_after=None):
    import matplotlib
    from matplotlib import pyplot as plt
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    finally:
        path.unlink(missing_ok=True)
    payload['series'] = [Series(**s) for s in payload['series']]
    from matplotlib.backends.registry import backend_registry
    _, gui = backend_registry.resolve_backend(matplotlib.get_backend())
    if gui is None:
        raise RuntimeError(f'Matplotlib backend {matplotlib.get_backend()} cannot open windows. Install Python with Tk support or configure a usable GUI backend via MPLBACKEND.')
    fig = plt.figure(figsize=(11, 6.5), layout='constrained')
    MatplotlibPlotRenderer().figure(PlotSpec(**payload), fig)
    if close_after is not None:
        timer = fig.canvas.new_timer(interval=close_after)
        timer.single_shot = True
        timer.add_callback(lambda: plt.close(fig))
        timer.start()
    plt.show()


if __name__ == '__main__':
    show_payload(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
