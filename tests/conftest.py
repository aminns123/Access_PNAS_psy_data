from pathlib import Path
import os
import pytest
import yaml
from importlib.resources import files
from psyview.data.pnas_psychophysics import PNASAdapter


@pytest.fixture
def adapter():
    root = Path(os.environ.get('PSYVIEW_TEST_DATA', 'PNAS_Psychopysics_data'))
    if not root.exists():
        pytest.skip('Set PSYVIEW_TEST_DATA to the public PNAS archive for integration tests')
    config = yaml.safe_load(files('psyview').joinpath('configs/pnas_psychophysics.yaml').read_text(encoding='utf-8'))
    item = PNASAdapter(config)
    item.load(root)
    return item
