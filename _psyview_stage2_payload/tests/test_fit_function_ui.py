from textual.widgets import Input

from psyview.app import PsyView
from psyview.data.registry import open_dataset
from psyview.ui.fit_function_screen import FitFunctionScreen
from test_lateral import tiny_lateral


async def test_lateral_luminance_shows_default_fit_function_panel(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(
        tiny_lateral
    )
    app = PsyView(
        adapter,
        tmp_path,
    )

    async with app.run_test(
        size=(140, 45)
    ) as pilot:
        await pilot.press("down")
        assert app.selection.active == 1

        panel = app._fit_function_panel_text()
        assert "FIT FUNCTION" in panel
        assert "ACTIVE FIT" in panel
        assert "Thesis Eq. B.25" in panel
        assert "F  Fit active Eq. B.25" in panel


async def test_g_selects_validated_custom_function(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(
        tiny_lateral
    )
    app = PsyView(
        adapter,
        tmp_path,
    )

    async with app.run_test(
        size=(140, 45)
    ) as pilot:
        await pilot.press(
            "down",
            "g",
        )
        assert isinstance(
            app.screen,
            FitFunctionScreen,
        )

        equation = app.screen.query_one(
            "#fit-equation",
            Input,
        )
        parameters = app.screen.query_one(
            "#fit-parameters",
            Input,
        )

        equation.value = (
            "A*cos(2*pi*f*x+phi)+C"
        )
        await pilot.press("enter")
        assert parameters.has_focus

        parameters.value = (
            "A=0.2[-2,2]; "
            "f=3[0.1,20]; "
            "phi=0[-pi,pi]; "
            "C=0[-2,2]"
        )
        await pilot.press("enter")
        await pilot.pause(.05)

        assert (
            app.fit_function_preview
            is not None
        )
        assert (
            adapter.custom_fit_definition()
            is not None
        )
        assert not app.fit_enabled

        panel = app._fit_function_panel_text()
        assert "Custom • session-only" in panel
        assert (
            "F  Fit active custom function"
            in panel
        )


async def test_invalid_equation_stays_in_editor(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(
        tiny_lateral
    )
    app = PsyView(
        adapter,
        tmp_path,
    )

    async with app.run_test(
        size=(140, 45)
    ) as pilot:
        await pilot.press(
            "down",
            "g",
        )

        equation = app.screen.query_one(
            "#fit-equation",
            Input,
        )
        parameters = app.screen.query_one(
            "#fit-parameters",
            Input,
        )

        equation.value = (
            "__import__('os').system('bad')"
        )
        await pilot.press("enter")
        parameters.value = "A=1[0,2]"
        await pilot.press("enter")
        await pilot.pause(.05)

        assert isinstance(
            app.screen,
            FitFunctionScreen,
        )
        assert (
            adapter.custom_fit_definition()
            is None
        )


async def test_g_ctrl_r_restores_thesis_fit(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(
        tiny_lateral
    )
    app = PsyView(
        adapter,
        tmp_path,
    )

    async with app.run_test(
        size=(140, 45)
    ) as pilot:
        await pilot.press(
            "down",
            "g",
        )

        equation = app.screen.query_one(
            "#fit-equation",
            Input,
        )
        parameters = app.screen.query_one(
            "#fit-parameters",
            Input,
        )

        equation.value = "A*x+C"
        await pilot.press("enter")
        parameters.value = (
            "A=1[-5,5]; C=0[-1,1]"
        )
        await pilot.press("enter")
        await pilot.pause(.05)

        assert (
            app.fit_function_preview
            is not None
        )
        assert (
            adapter.custom_fit_definition()
            is not None
        )

        await pilot.press("g")
        assert isinstance(
            app.screen,
            FitFunctionScreen,
        )

        await pilot.press("ctrl+r")
        await pilot.pause(.05)

        assert (
            app.fit_function_preview
            is None
        )
        assert (
            adapter.custom_fit_definition()
            is None
        )
        assert "Thesis Eq. B.25" in (
            app._fit_function_panel_text()
        )


async def test_g_escape_preserves_current_selection(
    tiny_lateral,
    tmp_path,
):
    adapter = open_dataset(
        tiny_lateral
    )
    app = PsyView(
        adapter,
        tmp_path,
    )

    async with app.run_test(
        size=(140, 45)
    ) as pilot:
        await pilot.press(
            "down",
            "g",
        )
        await pilot.press("escape")
        await pilot.pause(.05)

        assert (
            app.fit_function_preview
            is None
        )
        assert (
            adapter.custom_fit_definition()
            is None
        )
