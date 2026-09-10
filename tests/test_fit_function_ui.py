from textual.widgets import Input

from psyview.app import PsyView
from psyview.data.registry import open_dataset
from psyview.ui.fit_function_screen import FitFunctionScreen
from test_lateral import tiny_lateral


async def test_lateral_luminance_shows_fit_function_panel(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(tiny_lateral)
    app = PsyView(adapter, tmp_path)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("down")
        assert app.selection.active == 1

        panel = app._fit_function_panel_text()
        assert "FIT FUNCTION" in panel
        assert "ACTIVE FIT" in panel
        assert "Thesis Eq. B.25" in panel
        assert "CUSTOM PREVIEW" in panel
        assert "F  Fit active Eq. B.25" in panel


async def test_g_opens_editor_and_apply_is_preview_only(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(tiny_lateral)
    app = PsyView(adapter, tmp_path)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("down", "g")
        assert isinstance(app.screen, FitFunctionScreen)

        equation = app.screen.query_one(
            "#fit-equation",
            Input,
        )
        parameters = app.screen.query_one(
            "#fit-parameters",
            Input,
        )

        equation.value = "A*cos(k*x+phi)"
        await pilot.press("enter")
        assert parameters.has_focus

        parameters.value = "A; k; phi"
        await pilot.press("enter")
        await pilot.pause(.05)

        assert app.fit_function_preview is not None
        assert (
            app.fit_function_preview.equation
            == "A*cos(k*x+phi)"
        )
        assert not app.fit_enabled

        panel = app._fit_function_panel_text()
        assert "CUSTOM PREVIEW — NOT FITTED" in panel
        assert "A*cos(k*x+phi)" in panel


async def test_g_escape_preserves_previous_preview(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(tiny_lateral)
    app = PsyView(adapter, tmp_path)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("down", "g")
        app.screen.query_one(
            "#fit-equation",
            Input,
        ).value = "A*x"
        await pilot.press("escape")
        await pilot.pause(.05)

        assert app.fit_function_preview is None


async def test_g_ctrl_d_restores_default_preview(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(tiny_lateral)
    app = PsyView(adapter, tmp_path)

    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("down", "g")
        equation = app.screen.query_one(
            "#fit-equation",
            Input,
        )
        parameters = app.screen.query_one(
            "#fit-parameters",
            Input,
        )
        equation.value = "A*x"
        await pilot.press("enter")
        parameters.value = "A"
        await pilot.press("enter")
        await pilot.pause(.05)
        assert app.fit_function_preview is not None

        await pilot.press("g")
        assert isinstance(app.screen, FitFunctionScreen)
        await pilot.press("ctrl+d")
        await pilot.pause(.05)

        assert app.fit_function_preview is None
        assert "None — using thesis fit only" in (
            app._fit_function_panel_text()
        )
