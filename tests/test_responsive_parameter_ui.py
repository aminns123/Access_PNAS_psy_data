from pathlib import Path


APP = Path(__file__).parents[1] / "src" / "psyview" / "app.py"


def test_parameter_redraw_supports_background_mode():
    text = APP.read_text(encoding="utf-8")
    assert "async def redraw(self, force_background=False)" in text
    assert "force_background\n            or self.analysis.mode == 'interactive'" in text


def test_transient_input_focus_is_explicitly_recovered():
    text = APP.read_text(encoding="utf-8")
    assert "def _restore_keyboard_focus(self):" in text
    assert "self.screen.set_focus(None)" in text
    assert "self._queue_keyboard_focus_restore()" in text


def test_view_parameter_changes_request_background_redraw():
    text = APP.read_text(encoding="utf-8")
    view_start = text.index("async def _view_change")
    view_end = text.index("def _open_axis_limit_editor", view_start)
    region = text[view_start:view_end]
    assert "redraw(force_background=True)" in region


def test_axis_limit_modal_restores_keyboard_focus():
    text = APP.read_text(encoding="utf-8")
    start = text.index("def _open_axis_limit_editor")
    end = text.index("def _receive_axis_limit", start)
    region = text[start:end]
    assert "_queue_keyboard_focus_restore()" in region
