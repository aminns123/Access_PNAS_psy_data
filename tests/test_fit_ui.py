from threading import Event

import pytest

from psyview.app import PsyView
from psyview.data.registry import open_dataset
from psyview.ui.busy import BusyOverlay
from test_lateral import tiny_lateral


@pytest.mark.parametrize('outcome', ['success', 'exception', 'navigate'])
async def test_fit_busy_lifecycle(tiny_lateral, tmp_path, monkeypatch, outcome):
    adapter = open_dataset(tiny_lateral)
    started, release = Event(), Event()

    def delayed(level, filters, *args, **kwargs):
        started.set()
        release.wait(5)
        if outcome == 'exception':
            raise RuntimeError('test fit failed')
        return adapter.get_plot(level, filters)

    monkeypatch.setattr(adapter, 'get_plot_with_fit', delayed)
    app = PsyView(adapter, tmp_path)
    try:
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press('down', 'f')
            spinner = app.query_one(BusyOverlay)
            assert spinner.busy and started.is_set()
            frame = spinner.frame
            await pilot.pause(.15)
            assert spinner.frame > frame
            if outcome == 'navigate':
                await pilot.press('up')
                assert not spinner.busy
            release.set()
            await pilot.pause(.3)
            assert not spinner.busy
            if outcome == 'navigate':
                assert app.selection.active == 0
                assert 'ISF' in app.spec.title
            elif outcome == 'success':
                assert app.spec is not None
    finally:
        release.set()
