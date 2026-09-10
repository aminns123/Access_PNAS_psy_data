"""Platform integration smoke tests; no GUI or real terminal is required."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from psyview.app import PsyView
from psyview.models import PlotSpec, Series
from psyview.plotting import matplotlib_plots as plots
from psyview.data.registry import _packaged_config, open_dataset
from psyview.data.config import validate_config
from psyview.ui.dataset_browser import DatasetBrowser
from test_browser import tiny_dataset
from test_lateral import tiny_lateral

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('platform', ['win32', 'darwin', 'linux'])
def test_gui_subprocess_arguments_and_payload(platform, tmp_path, monkeypatch):
    monkeypatch.setattr(plots.sys, 'platform', platform)
    monkeypatch.setattr(plots.subprocess, 'CREATE_NO_WINDOW', 0x08000000, raising=False)
    monkeypatch.setattr(plots, 'LOG_PATH', tmp_path / 'log with spaces.txt')
    calls = []
    child = SimpleNamespace()
    monkeypatch.setattr(plots.subprocess, 'Popen', lambda args, **kw: calls.append((args, kw)) or child)
    spec = PlotSpec('Unicode ● → ²', 'x', 'y', [Series([1, 2], [3, 4], '')])
    assert plots.MatplotlibPlotRenderer().open(spec) is child
    try:
        args, kwargs = calls[0]
        assert args[:3] == [sys.executable, '-m', 'psyview.plotting.matplotlib_plots']
        assert not kwargs.get('shell', False)
        if platform == 'win32':
            assert kwargs['creationflags'] == 0x08000000
        else:
            assert 'creationflags' not in kwargs
        path = Path(args[3])
        assert json.loads(path.read_text(encoding='utf-8'))['title'] == spec.title
        # The parent has closed the file, so the child can open it on Windows.
        with path.open('a', encoding='utf-8'):
            pass
    finally:
        plots.cleanup_plot_payload(child)
    assert not path.exists()


def test_spawn_failure_removes_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(plots, 'LOG_PATH', tmp_path / 'log')
    paths = []
    def fail(args, **kwargs):
        paths.append(Path(args[3]))
        raise OSError('cannot start child')
    monkeypatch.setattr(plots.subprocess, 'Popen', fail)
    with pytest.raises(OSError):
        plots.MatplotlibPlotRenderer().open(PlotSpec('', '', ''))
    assert not paths[0].exists()


def test_headless_child_explains_backend_and_removes_payload(tmp_path):
    path = tmp_path / 'plot with spaces.json'
    path.write_text('{"title": "test", "xlabel": "x", "ylabel": "y", "series": []}', encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'psyview.plotting.matplotlib_plots', str(path)],
                            env={**os.environ, 'MPLBACKEND': 'Agg'}, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=30)
    assert result.returncode != 0
    assert 'cannot open windows' in result.stderr
    assert not path.exists()


@pytest.mark.parametrize('stubborn', [False, True])
def test_quit_reaps_child_and_removes_unread_payload(stubborn, tmp_path):
    path = tmp_path / 'unread.json'
    path.write_text('{}', encoding='utf-8')
    calls = []
    def wait(timeout):
        calls.append('wait')
        if stubborn and calls.count('wait') == 1:
            raise subprocess.TimeoutExpired('plot', timeout)
    process = SimpleNamespace(poll=lambda: None, terminate=lambda: calls.append('terminate'),
                              wait=wait, kill=lambda: calls.append('kill'), _psyview_payload=path)
    app = SimpleNamespace(plot_generation=0, analysis_task=None,
        analysis_executor=SimpleNamespace(shutdown=lambda **kw: None), figure_processes=[process])
    PsyView.on_unmount(app)
    assert calls == (['terminate', 'wait', 'kill', 'wait'] if stubborn else ['terminate', 'wait'])
    assert not app.figure_processes and not path.exists()


def test_real_child_is_stopped_on_cleanup(tmp_path):
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        plots.close_plot_process(child)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_safe_png_export_with_spaces_and_unicode(tiny_dataset, tmp_path):
    adapter = open_dataset(tiny_dataset)
    destination = tmp_path / 'Exports with spaces é'
    app = SimpleNamespace(spec=adapter.get_plot(0, {'participant_id': 'S'}),
                          adapter=adapter, export_dir=destination, notify=lambda *a, **kw: None)
    app.spec.title = 'P01:38 / CSF * ? " < > | ●'
    PsyView.action_save(app)
    path, = destination.glob('*.png')
    assert not any(c in path.name for c in ':*?"<>|/\\')
    assert path.read_bytes().startswith(b'\x89PNG')


@pytest.mark.parametrize('dataset', ['tiny_dataset', 'tiny_lateral'])
def test_config_and_gzip_adapter_load_in_unrelated_cwd(dataset, request, tmp_path, monkeypatch):
    root = request.getfixturevalue(dataset)
    elsewhere = tmp_path / 'other folder'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    adapter = open_dataset(root)
    assert not adapter.table('trials').empty
    for name in ['pnas_psychophysics.yaml', 'lateral_sensitivity.yaml']:
        config = _packaged_config(name)
        validate_config(config)
        assert all('\\' not in relative for relative in config['sources'].values())
    assert all(path.read_bytes() == data for path, data in before.items())


def test_browser_parent_at_filesystem_root():
    root = Path.cwd().anchor
    app = SimpleNamespace(folder=Path(root), action_reload=lambda: None)
    DatasetBrowser.action_parent(app)
    assert app.folder == Path(root)


def test_launcher_layout_and_line_endings():
    unix = (ROOT / 'run_psyview.sh').read_bytes()
    assert unix.startswith(b'#!/bin/sh\n') and b'\r' not in unix
    assert b'.venv/bin/python' in unix
    assert 'Scripts\\python.exe' in (ROOT / 'run_psyview.bat').read_text(encoding='utf-8')


@pytest.mark.parametrize('existing', [False, True])
def test_unix_launcher_quotes_paths_reuses_setup_and_propagates_exit(tmp_path, existing):
    shell = shutil.which('bash') or shutil.which('sh')
    if shell is None:
        pytest.skip('POSIX shell unavailable; exercised on macOS/Linux CI')
    project = tmp_path / 'project with spaces'
    project.mkdir()
    shutil.copyfile(ROOT / 'run_psyview.sh', project / 'run_psyview.sh')
    # A shell stub isolates launcher orchestration from pip and real installs.
    fake = project / 'fake python'
    fake.write_text("""#!/bin/sh
set -eu
case "$1" in
  -c) exit 0 ;;
  scripts/launcher_setup.py)
    if [ "${2:-}" = --create ]; then
      echo create >> calls
      mkdir -p .venv/bin
      cp "$0" .venv/bin/python
      chmod +x .venv/bin/python
    else
      echo setup >> calls
    fi ;;
  -m) printf '%s\\n' "$@" > launch-arguments; exit 7 ;;
  *) exit 99 ;;
esac
""", encoding='utf-8', newline='\n')
    fake.chmod(0o755)
    if existing:
        (project / '.venv/bin').mkdir(parents=True)
        shutil.copyfile(fake, project / '.venv/bin/python')
        (project / '.venv/bin/python').chmod(0o755)
    # Native Windows-to-MSYS argv conversion is not the Unix launcher interface.
    # Exercise Unicode argv natively on macOS/Linux; Windows Unicode paths are
    # covered separately by the export/payload tests.
    data_argument = 'data with spaces' if os.name == 'nt' else 'data with spaces é'
    result = subprocess.run([shell, (project / 'run_psyview.sh').as_posix(),
                             '--data-root', data_argument, '--export-dir', 'exports'],
                            cwd=tmp_path, env={**os.environ, 'PSYVIEW_PYTHON': './fake python'},
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 7, result.stdout + result.stderr
    assert (project / 'calls').read_text().splitlines() == (['setup'] if existing else ['create', 'setup'])
    assert (project / 'launch-arguments').read_text(encoding='utf-8').splitlines() == [
        '-m', 'psyview', '--data-root', data_argument, '--export-dir', 'exports']
