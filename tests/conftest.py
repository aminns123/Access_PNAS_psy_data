from pathlib import Path
import os
import pytest
import yaml
from importlib.resources import files
from psyview.data.pnas_psychophysics import PNASAdapter


@pytest.fixture(autouse=True)
def isolated_user_storage(tmp_path, monkeypatch):
    monkeypatch.setattr('psyview.preferences.cache_directory', lambda: tmp_path/'user-cache')
    monkeypatch.setattr('psyview.preferences.settings_path', lambda: tmp_path/'user-settings.json')


@pytest.fixture
def adapter():
    from psyview.data.detector import discover
    root = discover(os.environ.get('PSYVIEW_TEST_DATA'))
    if root is None or not root.exists():
        pytest.skip('Set PSYVIEW_TEST_DATA to the public PNAS archive for integration tests')
    config = yaml.safe_load(files('psyview').joinpath('configs/pnas_psychophysics.yaml').read_text(encoding='utf-8'))
    item = PNASAdapter(config)
    item.load(root)
    return item
