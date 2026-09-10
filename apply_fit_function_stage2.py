"""Apply PsyView custom-equation fitting Stage 2.

Target baseline:
  aminns123/Access_PNAS_psy_data
  main commit bf9386ecfb5ffc1700b149f98131831e18f5a3f0

The installer is conservative:
- payload files are staged outside the live src/tests tree until this runs;
- all source anchors are checked before any live file is changed;
- existing target files are kept in memory and restored on failure;
- no pytest is required locally;
- a safe-parser and synthetic numerical-fit smoke check is run;
- GitHub and empirical repositories are never written by this installer.
"""
from __future__ import annotations

from pathlib import Path
import py_compile
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "_psyview_stage2_payload"

APP = ROOT / "src/psyview/app.py"
LATERAL = ROOT / "src/psyview/data/lateral_sensitivity.py"
HELP = ROOT / "src/psyview/ui/help_screen.py"
WORKFLOW = ROOT / ".github/workflows/portability.yml"

COPY_TARGETS = {
    ROOT / "src/psyview/analysis/custom_fit.py":
        PAYLOAD / "src/psyview/analysis/custom_fit.py",
    ROOT / "src/psyview/ui/fit_function_state.py":
        PAYLOAD / "src/psyview/ui/fit_function_state.py",
    ROOT / "src/psyview/ui/fit_function_screen.py":
        PAYLOAD / "src/psyview/ui/fit_function_screen.py",
    ROOT / "tests/test_custom_fit.py":
        PAYLOAD / "tests/test_custom_fit.py",
    ROOT / "tests/test_fit_function_state.py":
        PAYLOAD / "tests/test_fit_function_state.py",
    ROOT / "tests/test_fit_function_ui.py":
        PAYLOAD / "tests/test_fit_function_ui.py",
}


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one current-source anchor; found {count}."
        )
    return text.replace(old, new, 1)


def patch_app(text):
    text = replace_once(
        text,
        "        # Stage-1 UI only: this text is never executed by the fitter.\n"
        "        self.fit_function_preview = None\n",
        "        # Session-only validated custom fit definition; None means thesis Eq. B.25.\n"
        "        self.fit_function_preview = None\n",
        "app custom-fit state comment",
    )

    old_show = """        if self._fit_supported_here():
            mode += ' | G: FUNCTION'
            mode += (
                ' | F: '
                + (
                    'HIDE FIT'
                    if self.fit_enabled
                    else 'FIT Eq. B.25'
                )
            )
"""
    new_show = """        if self._fit_supported_here():
            mode += ' | G: FUNCTION'
            mode += (
                ' | F: '
                + (
                    'HIDE FIT'
                    if self.fit_enabled
                    else (
                        'FIT CUSTOM'
                        if self.fit_function_preview is not None
                        else 'FIT Eq. B.25'
                    )
                )
            )
"""
    text = replace_once(
        text,
        old_show,
        new_show,
        "app analysis fit label",
    )

    start = text.index("    def action_fit_function(self):\n")
    end = text.index("\n    async def action_fit(self):\n", start)

    new_action = """    def action_fit_function(self):
        if not self._fit_supported_here():
            self.notify(
                'Fit-function editing is available on the lateral '
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
                resetter = getattr(
                    self.adapter,
                    'reset_custom_fit_definition',
                    None,
                )
                if resetter is not None:
                    resetter()
                self.notify(
                    'Fit function restored to thesis Eq. B.25.'
                )

            elif mode == 'custom':
                definition = result.get('definition')
                if definition is None:
                    return

                setter = getattr(
                    self.adapter,
                    'set_custom_fit_definition',
                    None,
                )
                if setter is None:
                    self.notify(
                        'This adapter does not support custom fit functions.',
                        severity='warning',
                    )
                    return

                setter(definition)
                self.fit_function_preview = definition
                self.notify(
                    'Custom fit function selected for this session.'
                )

            else:
                return

            self.show_analysis()
            self._queue_keyboard_focus_restore()

            if self.fit_enabled:
                asyncio.create_task(
                    self.redraw(force_background=True)
                )
            else:
                self._refresh_right_panel()

        self.push_screen(
            FitFunctionScreen(
                self.fit_function_preview
            ),
            receive,
        )
"""
    text = text[:start] + new_action + text[end:]

    old_message = """            elif use_fit:
                message = (
                    'Fitting thesis Eq. B.25 to the '
                    'current lateral-sensitivity profile…'
                )
"""
    new_message = """            elif use_fit:
                message = (
                    (
                        'Fitting custom equation to the '
                        'current lateral-sensitivity profile…'
                    )
                    if self.fit_function_preview is not None
                    else (
                        'Fitting thesis Eq. B.25 to the '
                        'current lateral-sensitivity profile…'
                    )
                )
"""
    text = replace_once(
        text,
        old_message,
        new_message,
        "app fitting status message",
    )

    return text


def patch_lateral(text):
    text = replace_once(
        text,
        "        self._fit_cache = {}\n"
        "        self._fit_exclusions = {}\n",
        "        self._fit_cache = {}\n"
        "        self._fit_exclusions = {}\n"
        "        self._custom_fit_definition = None\n",
        "lateral custom-fit state",
    )

    anchor = """    def supports_fit(self, level):
        return level == 1

"""
    methods = """    def supports_fit(self, level):
        return level == 1

    def custom_fit_definition(self):
        return self._custom_fit_definition

    def set_custom_fit_definition(self, definition):
        self._custom_fit_definition = definition
        self._fit_cache.clear()

    def reset_custom_fit_definition(self):
        self._custom_fit_definition = None
        self._fit_cache.clear()

"""
    text = replace_once(
        text,
        anchor,
        methods,
        "lateral custom-fit accessors",
    )

    cache_anchor = """        cache_key = (
            'fit',
            condition_id,
"""
    custom_branch = """        fit_function = self._custom_fit_definition

        if fit_function is not None:
            custom_cache_key = (
                'custom_fit',
                condition_id,
                (
                    analysis.mode
                    if analysis is not None
                    else 'archived'
                ),
                (
                    analysis.n_reversals
                    if (
                        analysis is not None
                        and analysis.mode == 'interactive'
                    )
                    else None
                ),
                fit_function.cache_key(),
                tuple(
                    sorted(
                        round(
                            float(value),
                            10,
                        )
                        for value in exclusions
                    )
                ),
            )

            if custom_cache_key not in self._fit_cache:
                from ..analysis.custom_fit import (
                    fit_custom_profile,
                )

                try:
                    result = fit_custom_profile(
                        profile,
                        fit_function,
                        excluded_x=exclusions,
                    )
                    self._fit_cache[
                        custom_cache_key
                    ] = (
                        'ok',
                        result,
                    )
                except Exception as exc:
                    self._fit_cache[
                        custom_cache_key
                    ] = (
                        'error',
                        str(exc),
                    )

            status, payload = self._fit_cache[
                custom_cache_key
            ]

            if status == 'error':
                spec.metadata[
                    '_fit_display'
                ] = (
                    'INTERACTIVE / DIAGNOSTIC CUSTOM FIT\\n'
                    f'R(x)={fit_function.source_expression}\\n'
                    f'Fit unavailable: {payload}\\n'
                    f'Excluded points: {len(exclusions)}.'
                )
                spec.metadata[
                    'Diagnostic fit function'
                ] = 'custom'
                spec.metadata[
                    'Diagnostic fit exclusions'
                ] = len(exclusions)
                return spec

            result = payload

            from ..analysis.custom_fit import (
                custom_fit_display_text,
            )

            spec.series.append(
                Series(
                    result.x_curve,
                    result.y_curve,
                    'Custom diagnostic fit',
                    color='red',
                    role='fit',
                )
            )

            spec.metadata[
                '_fit_display'
            ] = custom_fit_display_text(
                fit_function,
                result,
            )
            spec.metadata[
                'Diagnostic fit function'
            ] = 'custom'
            spec.metadata[
                'Diagnostic fit points'
            ] = result.n_points
            spec.metadata[
                'Diagnostic fit exclusions'
            ] = result.excluded_points
            spec.metadata[
                'Diagnostic fit weighting'
            ] = (
                'full spread with sigma floor 0.05'
            )

            spec.notes += (
                ' The red curve is a NEW on-demand custom diagnostic fit '
                'to the currently displayed profile. It uses the same '
                'empirical spread weighting and session-only fit-point '
                'exclusions as the Eq. B.25 diagnostic fitter. It is not '
                'an archived historical fit and does not replace the '
                'archived ISF.'
            )

            return spec

        cache_key = (
            'fit',
            condition_id,
"""
    text = replace_once(
        text,
        cache_anchor,
        custom_branch,
        "lateral custom-fit branch",
    )

    return text


def patch_help(text):
    text = text.replace(
        "'G  Open fit-function interface preview (where supported)\\n'",
        "'G  Select/edit custom fit function (where supported)\\n'",
    )
    text = text.replace(
        "'  G       open the fit-function preview editor\\n'",
        "'  G       select/edit a custom fit function\\n'",
    )

    old = (
        "            'The G editor is stage-1 interface/state only: custom text is shown as\\n'\n"
        "            'CUSTOM PREVIEW — NOT FITTED. F still runs the unchanged thesis Eq. B.25\\n'\n"
        "            'fitter. Ctrl+D restores the default preview; Esc cancels.\\n\\n'\n"
    )
    new = (
        "            'G accepts a restricted mathematical expression plus parameter starts/bounds.\\n'\n"
        "            'When a custom function is selected, F fits that function to the CURRENT\\n'\n"
        "            'displayed lateral profile. Ctrl+R restores the specialist thesis Eq. B.25\\n'\n"
        "            'fitter; Esc cancels. Custom functions are session-only.\\n\\n'\n"
    )
    text = replace_once(
        text,
        old,
        new,
        "help Stage-2 description",
    )

    return text


def patch_workflow(text):
    text = replace_once(
        text,
        "          tests/test_empirical_axis_limits.py tests/test_lateral_fit.py\n"
        "          tests/test_shared_row_axes.py tests/test_declarative_axis_policy.py\n",
        "          tests/test_empirical_axis_limits.py tests/test_lateral_fit.py\n"
        "          tests/test_custom_fit.py\n"
        "          tests/test_shared_row_axes.py tests/test_declarative_axis_policy.py\n",
        "workflow custom-fit test",
    )
    return text


def restore(originals):
    for path, content in originals.items():
        if content is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        else:
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            path.write_bytes(content)


def main():
    required = [
        APP,
        LATERAL,
        HELP,
        WORKFLOW,
        *COPY_TARGETS.values(),
    ]
    missing = [
        str(path)
        for path in required
        if not path.exists()
    ]
    if missing:
        print(
            "ERROR: Extract the Stage-2 ZIP into the PsyView repository root first.",
            file=sys.stderr,
        )
        print(
            "Missing: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    originals = {
        path: (
            path.read_bytes()
            if path.exists()
            else None
        )
        for path in [
            APP,
            LATERAL,
            HELP,
            WORKFLOW,
            *COPY_TARGETS.keys(),
        ]
    }

    try:
        app_new = patch_app(
            APP.read_text(encoding="utf-8")
        )
        lateral_new = patch_lateral(
            LATERAL.read_text(encoding="utf-8")
        )
        help_new = patch_help(
            HELP.read_text(encoding="utf-8")
        )
        workflow_new = patch_workflow(
            WORKFLOW.read_text(encoding="utf-8")
        )
    except Exception as exc:
        print(
            f"ERROR before changing live files: {exc}",
            file=sys.stderr,
        )
        return 1

    try:
        APP.write_text(
            app_new,
            encoding="utf-8",
            newline="\n",
        )
        LATERAL.write_text(
            lateral_new,
            encoding="utf-8",
            newline="\n",
        )
        HELP.write_text(
            help_new,
            encoding="utf-8",
            newline="\n",
        )
        WORKFLOW.write_text(
            workflow_new,
            encoding="utf-8",
            newline="\n",
        )

        for target, source in COPY_TARGETS.items():
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            shutil.copyfile(
                source,
                target,
            )

        compile_paths = [
            APP,
            LATERAL,
            HELP,
            *[
                path
                for path in COPY_TARGETS.keys()
                if path.suffix == ".py"
            ],
        ]

        for path in compile_paths:
            py_compile.compile(
                str(path),
                doraise=True,
            )

        # Fresh interpreter smoke check. No pytest, temp directory or cache needed.
        smoke = r"""
import numpy as np
import pandas as pd

from psyview.app import PsyView
from psyview.analysis.custom_fit import (
    build_custom_fit_definition,
    fit_custom_profile,
)
from psyview.data.lateral_sensitivity import LateralAdapter
from psyview.ui.fit_function_screen import FitFunctionScreen
from psyview.ui.fit_function_state import fit_function_panel_text

assert hasattr(PsyView, "action_fit_function")
assert hasattr(LateralAdapter, "set_custom_fit_definition")
assert "Thesis Eq. B.25" in fit_function_panel_text(None)

try:
    build_custom_fit_definition(
        "__import__('os').system('bad')",
        "A=1[0,2]",
    )
except ValueError:
    pass
else:
    raise AssertionError("unsafe expression was accepted")

x = np.linspace(-0.8, 0.8, 31)
y = 0.42 * np.exp(-1.35 * np.abs(x))
frame = pd.DataFrame({
    "distance_from_flanker_edge_deg": x,
    "log_sensitivity_ratio": y,
    "spread": np.full_like(x, 0.12),
})
definition = build_custom_fit_definition(
    "A*exp(-b*abs(x))",
    "A=0.2[-1,1]; b=0.8[0.001,5]",
)
result = fit_custom_profile(frame, definition)
params = dict(result.parameters)
assert abs(params["A"] - 0.42) < 1e-3
assert abs(params["b"] - 1.35) < 1e-3
assert result.rmse < 1e-5
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                smoke,
            ],
            cwd=ROOT,
        )

        if result.returncode:
            raise RuntimeError(
                "fresh-interpreter Stage-2 smoke check failed "
                f"(exit {result.returncode})"
            )

    except Exception as exc:
        restore(originals)
        print(
            "\nINSTALL FAILED — all live target files were restored.",
            file=sys.stderr,
        )
        print(
            f"Reason: {exc}",
            file=sys.stderr,
        )
        return 1

    print()
    print("INSTALL SUCCESSFUL — PsyView custom equation fitting Stage 2 is connected.")
    print()
    print("What to test now:")
    print("  1. Start PsyView normally with run_psyview.bat")
    print("  2. Open the lateral dataset and go to Subject -> Luminance")
    print("  3. Press G")
    print("  4. Try:")
    print("       A*cos(2*pi*f*x+phi)+C")
    print("     with:")
    print("       A=0.2[-2,2]; f=3[0.1,20]; phi=0[-pi,pi]; C=0[-2,2]")
    print("  5. Press Enter in equation, then Enter in parameters")
    print("  6. The panel should say ACTIVE FIT / Custom")
    print("  7. Press F: the red curve should now be the custom fit")
    print("  8. Press G then Ctrl+R to restore the specialist thesis Eq. B.25 fitter")
    print()
    print("Only the CURRENT displayed profile is fitted. Hidden siblings remain empirical-only.")
    print("No empirical files or GitHub content were written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
