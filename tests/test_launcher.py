import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('launcher_setup', Path(__file__).resolve().parents[1] / 'scripts/launcher_setup.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / '.venv').mkdir()
    (tmp_path / 'pyproject.toml').write_text('[build-system]\nrequires=["setuptools>=75"]\nbuild-backend="setuptools.build_meta"\n')
    monkeypatch.setattr(launcher, 'verify_install', lambda: None)
    return tmp_path


def test_first_setup_then_offline_start(project, monkeypatch):
    calls = []
    monkeypatch.setattr(launcher.subprocess, 'run', lambda command, **kw: calls.append(command) or SimpleNamespace(returncode=0))
    assert launcher.setup(project) == 0
    assert any('--no-build-isolation' in c for c in calls)
    assert any('setuptools>=75' in c for c in calls)
    marker = project / '.venv/.psyview_pyproject_hash'
    assert marker.read_text().strip() == hashlib.sha256((project/'pyproject.toml').read_bytes()).hexdigest()
    def forbidden(*args, **kwargs):
        raise AssertionError('Unchanged startup must not invoke pip or any subprocess')
    monkeypatch.setattr(launcher.subprocess, 'run', forbidden)
    assert launcher.setup(project) == 0


@pytest.mark.parametrize('failure', ['Build-tool installation', 'Project dependency installation'])
def test_changed_config_failed_install_preserves_hash(project, monkeypatch, failure):
    marker = project / '.venv/.psyview_pyproject_hash'
    marker.write_text('previous-success')
    monkeypatch.setattr(launcher.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher, 'install', lambda args, stage, root: stage != failure)
    assert launcher.setup(project) == 1
    assert marker.read_text() == 'previous-success'
    assert (project/'.venv/.psyview_setup_pending').exists()


def test_import_failure_does_not_record_success(project, monkeypatch):
    monkeypatch.setattr(launcher.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    def broken(): raise ImportError('missing textual')
    monkeypatch.setattr(launcher, 'verify_install', broken)
    assert launcher.setup(project) == 1
    assert not (project/'.venv/.psyview_pyproject_hash').exists()


def test_modified_configuration_updates_hash(project, monkeypatch):
    monkeypatch.setattr(launcher.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    assert launcher.setup(project) == 0
    config = project/'pyproject.toml'
    config.write_text(config.read_text()+'\n# changed\n')
    assert launcher.setup(project) == 0
    assert (project/'.venv/.psyview_pyproject_hash').read_text().strip() == hashlib.sha256(config.read_bytes()).hexdigest()


def test_incompatible_environment_preserved(project, monkeypatch):
    (project/'.venv/old-file').write_text('preserved')
    class Builder:
        def __init__(self, **kwargs): pass
        def create(self, target): target.mkdir()
    monkeypatch.setattr(launcher.venv, 'EnvBuilder', Builder)
    assert launcher.create_environment(project) == 0
    assert next(project.glob('.venv.incompatible-*/old-file')).read_text() == 'preserved'


def test_no_environment(tmp_path, monkeypatch):
    class Builder:
        def __init__(self, **kwargs): assert kwargs == {'with_pip': True}
        def create(self, target): target.mkdir()
    monkeypatch.setattr(launcher.venv, 'EnvBuilder', Builder)
    assert launcher.create_environment(tmp_path) == 0
    assert (tmp_path/'.venv').is_dir()


def test_network_failure_is_distinguished(project, monkeypatch, capsys):
    def fail(command, **kwargs):
        kwargs['stdout'].write('ConnectionResetError(10054): Could not fetch setuptools\n')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(launcher.subprocess, 'run', fail)
    assert not launcher.install(['setuptools>=75'], 'Build-tool installation', project)
    output = capsys.readouterr().out
    assert 'Build-tool installation failed' in output
    assert 'Network/PyPI access failed' in output
