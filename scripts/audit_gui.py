import asyncio
from pathlib import Path
import os
from importlib.resources import files
import yaml
from psyview.app import PsyView
from psyview.data.detector import discover
from psyview.data.pnas_psychophysics import PNASAdapter
from psyview.plotting.matplotlib_plots import MatplotlibPlotRenderer

async def main():
    os.chdir(Path(__file__).resolve().parents[1])
    Path('.tools').mkdir(exist_ok=True)
    adapter=PNASAdapter(yaml.safe_load(files('psyview').joinpath('configs/pnas_psychophysics.yaml').read_text(encoding='utf-8')))
    root = discover(os.environ.get('PSYVIEW_TEST_DATA'))
    if root is None:
        raise ValueError('Set PSYVIEW_TEST_DATA to an external dataset root.')
    adapter.load(root)
    original=MatplotlibPlotRenderer.open
    processes=[]
    def opened(self,spec):
        process=original(self,spec,close_after=500)
        processes.append(process)
        return process
    MatplotlibPlotRenderer.open=opened
    app=PsyView(adapter)
    async with app.run_test(size=(140,52)) as pilot:
        for participant in range(4):
            for lum in range(2):
                for level in range(4):
                    while app.selection.active > level: await pilot.press('up')
                    while app.selection.active < level: await pilot.press('down')
                    await pilot.press('m')
                    process=processes[-1]
                    for _ in range(100):
                        if process.poll() is not None: break
                        await pilot.pause(.1)
                    assert process.poll()==0, (app.spec.title,process.poll())
                    print(app.spec.title, 'GUI opened/drawn/closed: PASS',flush=True)
                    if participant==0 and lum==0:
                        app.save_screenshot(f'audit-level-{level}.svg',path='.tools')
                        MatplotlibPlotRenderer().save(app.spec,Path('.tools')/f'audit-level-{level}.png')
                await pilot.press('up','up','right')
            await pilot.press('up','right')
        await pilot.press('r','h','escape','q')
    assert len(processes)==32
    print('32 real GUI subprocesses passed',flush=True)
asyncio.run(main())
