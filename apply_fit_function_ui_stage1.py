"""Install the stage-1 PsyView fit-function UI.

The installer edits only app.py, help_screen.py and portability.yml.  It validates
all anchors before writing, syntax-checks the result, runs focused tests, and
automatically restores the original files if validation/tests fail.
"""
from __future__ import annotations

from pathlib import Path
import py_compile
import subprocess
import sys


ROOT = Path(__file__).resolve().parent

APP = ROOT / "src/psyview/app.py"
HELP = ROOT / "src/psyview/ui/help_screen.py"
WORKFLOW = ROOT / ".github/workflows/portability.yml"
NEW_STATE = ROOT / "src/psyview/ui/fit_function_state.py"
NEW_SCREEN = ROOT / "src/psyview/ui/fit_function_screen.py"
NEW_TEST_STATE = ROOT / "tests/test_fit_function_state.py"
NEW_TEST_UI = ROOT / "tests/test_fit_function_ui.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one current-source anchor; found {count}."
        )
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    if "def action_fit_function(self):" in text:
        raise RuntimeError("Stage-1 fit-function UI already appears to be installed.")

    text = replace_once(
        text,
        "from .ui.axis_limit_screen import AxisLimitScreen\n"
        "from .ui.view_state import SCALE_CHOICES, SCOPE_CHOICES, cycle_choice\n",
        "from .ui.axis_limit_screen import AxisLimitScreen\n"
        "from .ui.fit_function_screen import FitFunctionScreen\n"
        "from .ui.fit_function_state import fit_function_panel_text\n"
        "from .ui.view_state import SCALE_CHOICES, SCOPE_CHOICES, cycle_choice\n",
        "app imports",
    )

    text = replace_once(
        text,
        "        Binding('f', 'fit', 'Fit', show=False),\n"
        "        Binding('e', 'fit_edit', 'Fit points', show=False),\n",
        "        Binding('f', 'fit', 'Fit', show=False),\n"
        "        Binding('g', 'fit_function', 'Fit function', show=False),\n"
        "        Binding('e', 'fit_edit', 'Fit points', show=False),\n",
        "app G binding",
    )

    text = replace_once(
        text,
        "        self.fit_enabled = False\n"
        "        self.fit_edit_mode = False\n"
        "        self.fit_cursor_index = 0\n\n"
        "        # Session-only View overrides, scoped by hierarchy level/view type.\n",
        "        self.fit_enabled = False\n"
        "        self.fit_edit_mode = False\n"
        "        self.fit_cursor_index = 0\n"
        "        # Stage-1 UI only: this text is never executed by the fitter.\n"
        "        self.fit_function_preview = None\n\n"
        "        # Session-only View overrides, scoped by hierarchy level/view type.\n",
        "app preview state",
    )

    old_panel = """    def _refresh_right_panel(self, spec=None):
        current = self.spec if spec is None else spec
        panel = self.query_one('#legend', Static)
        if self.view_focus:
            panel.update(self._view_panel_text(current))
        elif current is not None:
            panel.update(self._legend_text(current))
        else:
            panel.update('')
"""

    new_panel = """    def _fit_function_panel_text(self):
        if not self._fit_supported_here():
            return ''
        return fit_function_panel_text(
            self.fit_function_preview
        )

    def _refresh_right_panel(self, spec=None):
        current = self.spec if spec is None else spec
        panel = self.query_one('#legend', Static)
        if self.view_focus:
            panel.update(self._view_panel_text(current))
        elif current is not None:
            legend = self._legend_text(current)
            fit_function = self._fit_function_panel_text()
            panel.update(
                (
                    fit_function + '\\n\\n' + legend
                    if fit_function
                    else legend
                )
            )
        else:
            panel.update('')
"""

    text = replace_once(
        text,
        old_panel,
        new_panel,
        "right panel",
    )

    text = replace_once(
        text,
        "        if self._fit_supported_here():\n"
        "            mode += (\n"
        "                ' | F: '\n",
        "        if self._fit_supported_here():\n"
        "            mode += ' | G: FUNCTION'\n"
        "            mode += (\n"
        "                ' | F: '\n",
        "analysis G label",
    )

    action_anchor = """    async def action_fit(self):
        if not self._fit_supported_here():
"""
    action_code = """    def action_fit_function(self):
        if not self._fit_supported_here():
            self.notify(
                'Fit-function preview is available on the lateral '
                'Luminance/profile level.'
            )
            return

        self.analysis_focus = False
        self.fit_edit_mode = False
        self.view_focus = False

        def receive(result):
            if result is None:
                self._refresh_right_panel()
                self._queue_keyboard_focus_restore()
                return

            mode = result.get('mode')
            if mode == 'default':
                self.fit_function_preview = None
                self.notify(
                    'Fit-function preview reset. '
                    'F continues to fit thesis Eq. B.25.'
                )
            elif mode == 'preview':
                preview = result.get('preview')
                if preview is None:
                    return
                self.fit_function_preview = preview
                self.notify(
                    'Custom equation saved as a session-only preview. '
                    'It is NOT fitted yet; F still fits thesis Eq. B.25.'
                )
            else:
                return

            self._refresh_right_panel()
            self.show_analysis()
            self._queue_keyboard_focus_restore()

        self.push_screen(
            FitFunctionScreen(
                self.fit_function_preview
            ),
            receive,
        )

    async def action_fit(self):
        if not self._fit_supported_here():
"""
    text = replace_once(
        text,
        action_anchor,
        action_code,
        "fit-function action",
    )

    text = replace_once(
        text,
        "            self.fit_enabled = False\n"
        "            self.fit_edit_mode = False\n"
        "            self.fit_cursor_index = 0\n"
        "            self.axis_scale_overrides.clear()\n",
        "            self.fit_enabled = False\n"
        "            self.fit_edit_mode = False\n"
        "            self.fit_cursor_index = 0\n"
        "            self.fit_function_preview = None\n"
        "            self.axis_scale_overrides.clear()\n",
        "reload reset",
    )

    return text


def patch_help(text: str) -> str:
    text = replace_once(
        text,
        "            'F  Fit / hide diagnostic equation fit (where supported)\\n'\n",
        "            'F  Fit / hide diagnostic equation fit (where supported)\\n'\n"
        "            'G  Open fit-function interface preview (where supported)\\n'\n",
        "help top G",
    )

    text = replace_once(
        text,
        "            '  F       fit/hide thesis Eq. B.25\\n'\n"
        "            '  E       enter/leave fit-point edit mode\\n'\n",
        "            '  F       fit/hide thesis Eq. B.25\\n'\n"
        "            '  G       open the fit-function preview editor\\n'\n"
        "            '  E       enter/leave fit-point edit mode\\n'\n",
        "help lateral G",
    )

    text = replace_once(
        text,
        "            'Excluded points remain visible and are marked with a red ×. Exclusions\\n'\n",
        "            'The G editor is stage-1 interface/state only: custom text is shown as\\n'\n"
        "            'CUSTOM PREVIEW — NOT FITTED. F still runs the unchanged thesis Eq. B.25\\n'\n"
        "            'fitter. Ctrl+R restores the default preview; Esc cancels.\\n\\n'\n"
        "            'Excluded points remain visible and are marked with a red ×. Exclusions\\n'\n",
        "help stage-one explanation",
    )

    return text


def patch_workflow(text: str) -> str:
    return replace_once(
        text,
        "          tests/test_display_refinements.py\n"
        "          tests/test_fit_ui.py\n",
        "          tests/test_display_refinements.py\n"
        "          tests/test_fit_ui.py\n"
        "          tests/test_fit_function_state.py\n"
        "          tests/test_fit_function_ui.py\n",
        "workflow tests",
    )


def restore(originals):
    for path, content in originals.items():
        path.write_text(
            content,
            encoding="utf-8",
            newline="\n",
        )


def main() -> int:
    required = [
        APP,
        HELP,
        WORKFLOW,
        NEW_STATE,
        NEW_SCREEN,
        NEW_TEST_STATE,
        NEW_TEST_UI,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print(
            "ERROR: Extract the ZIP into the repository root first. "
            "Missing: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    originals = {
        APP: APP.read_text(encoding="utf-8"),
        HELP: HELP.read_text(encoding="utf-8"),
        WORKFLOW: WORKFLOW.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            APP: patch_app(originals[APP]),
            HELP: patch_help(originals[HELP]),
            WORKFLOW: patch_workflow(originals[WORKFLOW]),
        }
    except Exception as exc:
        print(f"ERROR before writing anything: {exc}", file=sys.stderr)
        return 1

    try:
        for path, content in updated.items():
            path.write_text(
                content,
                encoding="utf-8",
                newline="\n",
            )

        # Local development verification only.  This deliberately does not use
        # pytest or pytest's temp/cache directories.
        for path in (
            APP,
            HELP,
            NEW_STATE,
            NEW_SCREEN,
            NEW_TEST_STATE,
            NEW_TEST_UI,
        ):
            py_compile.compile(
                str(path),
                doraise=True,
            )

        # Verify the expected wiring is physically present in the edited source.
        app_text = APP.read_text(encoding="utf-8")
        required_app_markers = (
            "from .ui.fit_function_screen import FitFunctionScreen",
            "from .ui.fit_function_state import fit_function_panel_text",
            "Binding('g', 'fit_function', 'Fit function', show=False)",
            "self.fit_function_preview = None",
            "def _fit_function_panel_text(self):",
            "def action_fit_function(self):",
            "mode += ' | G: FUNCTION'",
        )
        missing_markers = [
            marker
            for marker in required_app_markers
            if marker not in app_text
        ]
        if missing_markers:
            raise RuntimeError(
                "post-install source verification failed; missing: "
                + ", ".join(missing_markers)
            )

        # Fresh interpreter import catches broken imports without touching pytest.
        check_code = (
            "from psyview.app import PsyView; "
            "from psyview.ui.fit_function_screen import FitFunctionScreen; "
            "from psyview.ui.fit_function_state import fit_function_panel_text; "
            "assert hasattr(PsyView, 'action_fit_function'); "
            "assert 'FIT FUNCTION' in fit_function_panel_text(None)"
        )
        result = subprocess.run(
            [sys.executable, "-c", check_code],
            cwd=ROOT,
        )
        if result.returncode:
            raise RuntimeError(
                f"fresh-interpreter import/wiring check failed "
                f"(exit {result.returncode})"
            )

    except Exception as exc:
        restore(originals)
        print(
            "\nINSTALL FAILED — existing source files were automatically restored.",
            file=sys.stderr,
        )
        print(f"Reason: {exc}", file=sys.stderr)
        print(
            "The extracted new stage-1 files may remain, but app.py/help/workflow "
            "are back to their pre-install contents.",
            file=sys.stderr,
        )
        return 1

    print()
    print("INSTALL SUCCESSFUL")
    print("The stage-1 fit-function interface is now connected.")
    print()
    print("No pytest was required or run.")
    print()
    print("Now:")
    print("  1. Start PsyView normally with run_psyview.bat")
    print("  2. Open the lateral dataset")
    print("  3. Move to Subject -> Luminance/profile")
    print("  4. Confirm the right panel begins with FIT FUNCTION")
    print("  5. Press G and confirm the editor opens")
    print()
    print("F still runs the unchanged thesis Eq. B.25 fitter.")
    print("Custom equation text is preview-only in this stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
