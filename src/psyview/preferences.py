"""Per-user preferences; never stored in an empirical repository."""
import json
import logging
import os
from pathlib import Path


def settings_path():
    base = Path(os.environ.get('APPDATA') or os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
    return base / 'PsyView' / 'settings.json'


def cache_directory():
    base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')
    return base / 'PsyView' / 'cache'


def starting_directory():
    try:
        last = Path(json.loads(settings_path().read_text(encoding='utf-8'))['last_dataset']).parent
        if last.is_dir():
            return last
    except (OSError, ValueError, KeyError, TypeError):
        pass
    project = Path(__file__).resolve().parents[2]
    for candidate in (project.parent if (project/'pyproject.toml').exists() else Path.cwd(), Path.home()):
        if candidate.is_dir():
            return candidate
    return Path.home()


def remember_dataset(root):
    try:
        path = settings_path()
        if path.resolve().is_relative_to(root.resolve()):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'last_dataset': str(root.resolve())}), encoding='utf-8')
    except OSError:
        logging.getLogger(__name__).exception('Could not save dataset preference')
