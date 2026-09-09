import pytest
from psyview.app import PsyView
from psyview.data.detector import discover
from psyview.state import SelectionState


def test_discovery(adapter):
    assert discover(adapter.root) == adapter.root
    assert discover() is None
    assert adapter.get_values(0, {}) == ['P01', 'P02', 'P03', 'P04']
    for participant, count in zip(['P01', 'P02', 'P03', 'P04'], [12, 6, 7, 6]):
        assert len(adapter.get_values(1, {'participant_id': participant})) == count
    assert 'trials' not in adapter.tables
    assert 'curves' not in adapter.tables


def test_branch_memory(adapter):
    state = SelectionState(adapter)
    state.down()
    state.move(1)
    assert state.filters()['luminance_cd_m2'] == 20
    state.up()
    state.move(1)
    state.down()
    assert state.filters()['luminance_cd_m2'] == 10
    state.up()
    state.move(-1)
    state.down()
    assert state.filters()['luminance_cd_m2'] == 20


async def test_vertical_slice(adapter, tmp_path):
    app = PsyView(adapter)
    async with app.run_test(size=(130, 45)) as pilot:
        assert 'P01' in app.spec.title
        await pilot.press('right')
        assert 'P02' in app.spec.title
        await pilot.press('down', 'right')
        assert app.selection.filters()['luminance_cd_m2'] == 26
        assert 'CSF' in app.spec.title
        await pilot.press('up')
        assert app.selection.active == 0
        assert 'Preferred spatial frequency' in app.spec.title
        app.save_screenshot('milestone1.svg', path=str(tmp_path))
