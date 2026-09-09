"""Opt-in real GUI lifecycle audit; requires PSYVIEW_TEST_DATA."""
import asyncio
import os
from pathlib import Path
from textual.widgets import OptionList
from psyview.ui.dataset_browser import DatasetBrowser
from psyview.app import PsyView
from psyview.plotting.matplotlib_plots import MatplotlibPlotRenderer


async def main():
    root = Path(os.environ['PSYVIEW_TEST_DATA']).resolve()
    output = Path(__file__).resolve().parents[1]/'.tools'
    output.mkdir(exist_ok=True)
    browser = DatasetBrowser(root.parent)
    async with browser.run_test(size=(140, 45)) as pilot:
        browser.query_one(OptionList).highlighted = browser.entries.index(root)
        await pilot.pause()
        browser.save_screenshot('dataset-browser.svg', path=str(output))
        await pilot.press('enter')
    assert browser.return_value.root == root
    original = MatplotlibPlotRenderer.open
    processes = []
    def opened(self, spec):
        process = original(self, spec, close_after=600)
        processes.append(process)
        return process
    MatplotlibPlotRenderer.open = opened
    app = PsyView(browser.return_value)
    try:
        async with app.run_test(size=(140, 52)) as pilot:
            for mode in ('archived', 'interactive'):
                if mode == 'interactive':
                    await pilot.press('a','enter','left','left','a')
                for level in range(4):
                    while app.selection.active > level:
                        await pilot.press('up')
                    while app.selection.active < level:
                        await pilot.press('down')
                    for _ in range(600):
                        if app.spec is not None:
                            break
                        await pilot.pause(.1)
                    assert app.spec is not None
                    app.save_screenshot(f'{mode}-level-{level}.svg',path=str(output))
                    MatplotlibPlotRenderer().save(app.spec,output/f'{mode}-level-{level}.png')
                    await pilot.press('m')
                    process=processes[-1]
                    for _ in range(200):
                        if process.poll() is not None:
                            break
                        await pilot.pause(.1)
                    assert process.poll()==0
                    print(mode,level,'GUI open/draw/close PASS',flush=True)
                    await pilot.resize_terminal(75,28)
                    await pilot.resize_terminal(140,52)
            await pilot.press('a','right','right')
            for _ in range(200):
                if app.spec is not None: break
                await pilot.pause(.1)
            assert app.analysis.n_reversals==8
            assert app.spec.metadata['Interactive threshold']==app.spec.metadata['Archived threshold']
            await pilot.press('end')
            for _ in range(200):
                if app.spec is not None: break
                await pilot.pause(.1)
            assert app.spec is not None and app.analysis.n_reversals==12
            assert 'Insufficient' in app.spec.notes
            await pilot.press('enter','escape','r','h','escape','q')
        print('External browser, both modes, N=6/8/12, resize, reload, help: PASS',flush=True)
    finally:
        MatplotlibPlotRenderer.open = original


if __name__ == '__main__':
    asyncio.run(main())
