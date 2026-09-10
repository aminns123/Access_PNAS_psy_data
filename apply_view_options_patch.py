"""Apply the PsyView right-side View-options UI patch.

Run from the repository root:
    .\.venv\Scripts\python.exe apply_view_options_patch.py
or on macOS/Linux:
    ./.venv/bin/python apply_view_options_patch.py

Only src/psyview/app.py is edited. The ZIP supplies the two new UI modules,
updated help, and tests.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


APP = Path("src/psyview/app.py")
BACKUP = Path("src/psyview/app.py.pre_view_options.bak")
VIEW_METHODS = '\n    def _view_items(self):\n        """Logical rows in the keyboard-first right-side View table."""\n        categorical_x = bool(\n            self.spec is not None\n            and getattr(self.spec, \'xticks\', [])\n        )\n        return [\n            (\'x_scale\', \'X scale\', categorical_x),\n            (\'x_min\', \'X minimum\', categorical_x),\n            (\'x_max\', \'X maximum\', categorical_x),\n            (\'y_scale\', \'Y scale\', False),\n            (\'y_min\', \'Y minimum\', False),\n            (\'y_max\', \'Y maximum\', False),\n            (\'scope\', \'Limit scope\', False),\n            (\'reset\', \'Reset to defaults\', False),\n        ]\n\n    def _normalize_view_index(self):\n        items = self._view_items()\n        selectable = [\n            index\n            for index, (_, _, disabled) in enumerate(items)\n            if not disabled\n        ]\n        if not selectable:\n            self.view_index = 0\n            return\n        if self.view_index not in selectable:\n            self.view_index = selectable[0]\n\n    def _view_move(self, delta):\n        items = self._view_items()\n        selectable = [\n            index\n            for index, (_, _, disabled) in enumerate(items)\n            if not disabled\n        ]\n        if not selectable:\n            return\n        self._normalize_view_index()\n        position = selectable.index(self.view_index)\n        self.view_index = selectable[\n            (position + (1 if delta >= 0 else -1)) % len(selectable)\n        ]\n        self._refresh_right_panel()\n\n    def _configured_scope_label(self, level):\n        policies = self.adapter.config.get(\'axis_policy\', {}).get(\n            self.adapter.levels()[level].column,\n            {},\n        )\n        scopes = []\n        for axis in (\'x\', \'y\'):\n            if (\n                axis == \'x\'\n                and self.spec is not None\n                and getattr(self.spec, \'xticks\', [])\n            ):\n                continue\n            policy = policies.get(axis, {})\n            if isinstance(policy, dict):\n                scopes.append(str(policy.get(\'limits\', \'row\')).lower())\n        scopes = [scope for scope in scopes if scope in (\'data\', \'row\')]\n        if not scopes:\n            return \'Row\'\n        if len(set(scopes)) == 1:\n            return scopes[0].title()\n        return \'Mixed\'\n\n    def _auto_axis_limits(self, spec, axis):\n        from .plotting.axes import axis_policy\n\n        stored = spec.metadata.get(f\'_auto_{axis}lim\')\n        if (\n            isinstance(stored, (tuple, list))\n            and len(stored) == 2\n        ):\n            return tuple(float(value) for value in stored)\n\n        _, limits, _ = axis_policy(spec, axis)\n        return tuple(float(value) for value in limits)\n\n    def _apply_view_axis_limits(self, spec, level):\n        """Apply session manual bounds after normal data/row resolution.\n\n        Layer order:\n            dataset config -> automatic data/row limits -> user manual bounds.\n        """\n        from .plotting.axes import axis_policy\n\n        for axis in (\'x\', \'y\'):\n            if axis == \'x\' and getattr(spec, \'xticks\', []):\n                continue\n\n            scale, automatic, _ = axis_policy(spec, axis)\n            automatic = tuple(float(value) for value in automatic)\n            spec.metadata[f\'_auto_{axis}lim\'] = automatic\n\n            manual = self.axis_limit_overrides.get((level, axis), {})\n            lower = manual.get(\'min\')\n            upper = manual.get(\'max\')\n\n            effective_lower = automatic[0] if lower is None else float(lower)\n            effective_upper = automatic[1] if upper is None else float(upper)\n\n            # Defensive only: interactive editing validates before state changes.\n            if (\n                effective_lower >= effective_upper\n                or (\n                    scale == \'log\'\n                    and (\n                        effective_lower <= 0\n                        or effective_upper <= 0\n                    )\n                )\n            ):\n                continue\n\n            setattr(\n                spec,\n                axis + \'lim\',\n                (effective_lower, effective_upper),\n            )\n            spec.metadata[f\'_{axis}_limit_source\'] = (\n                \'user override\'\n                if lower is not None or upper is not None\n                else \'automatic\'\n            )\n\n        return spec\n\n    def _view_value(self, key, spec):\n        from .plotting.axes import axis_policy, tick_label\n\n        level = self.selection.active\n\n        if key in (\'x_scale\', \'y_scale\'):\n            axis = key[0]\n            if axis == \'x\' and getattr(spec, \'xticks\', []):\n                return \'Categorical\'\n            override = self.axis_scale_overrides.get((level, axis))\n            effective, _, _ = axis_policy(spec, axis)\n            if override is None:\n                return f\'Default ({effective.title()})\'\n            return override.title()\n\n        if key in (\'x_min\', \'x_max\', \'y_min\', \'y_max\'):\n            axis = key[0]\n            if axis == \'x\' and getattr(spec, \'xticks\', []):\n                return \'Categorical\'\n            bound = \'min\' if key.endswith(\'_min\') else \'max\'\n            manual = self.axis_limit_overrides.get((level, axis), {})\n            value = manual.get(bound)\n            if value is not None:\n                return tick_label(value)\n\n            limits = self._auto_axis_limits(spec, axis)\n            auto_value = limits[0 if bound == \'min\' else 1]\n            return f\'Auto [{tick_label(auto_value)}]\'\n\n        if key == \'scope\':\n            override = self.axis_scope_overrides.get(level)\n            if override is None:\n                return f\'Default ({self._configured_scope_label(level)})\'\n            return override.title()\n\n        return \'\'\n\n    def _view_panel_text(self, spec):\n        if spec is None:\n            return \'VIEW\\n\\nPlot is being prepared…\'\n\n        self._normalize_view_index()\n        items = self._view_items()\n        by_key = {\n            key: (index, label, disabled)\n            for index, (key, label, disabled) in enumerate(items)\n        }\n\n        lines = [\n            \'VIEW\',\n            \'\',\n            \'X AXIS\',\n        ]\n\n        for key in (\'x_scale\', \'x_min\', \'x_max\'):\n            index, label, disabled = by_key[key]\n            prefix = \'›\' if index == self.view_index and not disabled else \' \'\n            value = self._view_value(key, spec)\n            lines.append(f\'{prefix} {label:<11} {value}\')\n\n        lines.extend([\'\', \'Y AXIS\'])\n\n        for key in (\'y_scale\', \'y_min\', \'y_max\'):\n            index, label, disabled = by_key[key]\n            prefix = \'›\' if index == self.view_index and not disabled else \' \'\n            value = self._view_value(key, spec)\n            lines.append(f\'{prefix} {label:<11} {value}\')\n\n        lines.extend([\'\', \'GENERAL\'])\n\n        for key in (\'scope\', \'reset\'):\n            index, label, disabled = by_key[key]\n            prefix = \'›\' if index == self.view_index and not disabled else \' \'\n            value = self._view_value(key, spec)\n            lines.append(\n                f\'{prefix} {label}\'\n                + (f\'  {value}\' if value else \'\')\n            )\n\n        lines.extend([\n            \'\',\n            \'↑↓ Select\',\n            \'←→ Change choice\',\n            \'Enter Edit / activate\',\n            \'Esc or V Close\',\n            \'\',\n            \'Overrides are session-only.\',\n        ])\n        return \'\\n\'.join(lines)\n\n    def _refresh_right_panel(self, spec=None):\n        current = self.spec if spec is None else spec\n        panel = self.query_one(\'#legend\', Static)\n\n        if self.view_focus:\n            panel.update(self._view_panel_text(current))\n        elif current is not None:\n            panel.update(self._legend_text(current))\n        else:\n            panel.update(\'\')\n\n    def _can_use_log(self, axis):\n        if self.spec is None:\n            return False\n        if axis == \'x\' and getattr(self.spec, \'xticks\', []):\n            return False\n\n        available = self.spec.metadata.get(\n            \'_log_available\',\n            {},\n        ).get(axis)\n\n        if available is None:\n            from .plotting.axes import empirical_axis_values\n            values = empirical_axis_values(self.spec, axis)\n            available = bool(values) and all(value > 0 for value in values)\n\n        if not available:\n            return False\n\n        manual = self.axis_limit_overrides.get(\n            (self.selection.active, axis),\n            {},\n        )\n        return all(\n            value is None or value > 0\n            for value in (\n                manual.get(\'min\'),\n                manual.get(\'max\'),\n            )\n        )\n\n    async def _view_change(self, delta):\n        self._normalize_view_index()\n        key = self._view_items()[self.view_index][0]\n        level = self.selection.active\n\n        if key in (\'x_scale\', \'y_scale\'):\n            axis = key[0]\n            current = self.axis_scale_overrides.get((level, axis))\n            target = cycle_choice(current, SCALE_CHOICES, delta)\n\n            if target == \'log\' and not self._can_use_log(axis):\n                self.notify(\n                    f\'Cannot use logarithmic {axis.upper()} scale: \'\n                    \'the displayed empirical data/uncertainty or a manual \'\n                    \'bound is non-positive.\'\n                )\n                return\n\n            if target is None:\n                self.axis_scale_overrides.pop((level, axis), None)\n            else:\n                self.axis_scale_overrides[(level, axis)] = target\n\n            await self.redraw()\n            return\n\n        if key == \'scope\':\n            current = self.axis_scope_overrides.get(level)\n            target = cycle_choice(current, SCOPE_CHOICES, delta)\n            if target is None:\n                self.axis_scope_overrides.pop(level, None)\n            else:\n                self.axis_scope_overrides[level] = target\n\n            await self.redraw()\n            return\n\n        if key in (\'x_min\', \'x_max\', \'y_min\', \'y_max\'):\n            self.notify(\n                \'Press Enter to edit this numeric bound; type Auto to clear it.\'\n            )\n\n    async def _view_activate(self):\n        self._normalize_view_index()\n        key = self._view_items()[self.view_index][0]\n\n        if key in (\'x_scale\', \'y_scale\', \'scope\'):\n            await self._view_change(1)\n            return\n\n        if key == \'reset\':\n            level = self.selection.active\n            for axis in (\'x\', \'y\'):\n                self.axis_scale_overrides.pop((level, axis), None)\n                self.axis_limit_overrides.pop((level, axis), None)\n            self.axis_scope_overrides.pop(level, None)\n\n            self.notify(\'View overrides reset to dataset defaults.\')\n            await self.redraw()\n            return\n\n        if key in (\'x_min\', \'x_max\', \'y_min\', \'y_max\'):\n            axis = key[0]\n            bound = \'min\' if key.endswith(\'_min\') else \'max\'\n            self._open_axis_limit_editor(axis, bound)\n\n    def _open_axis_limit_editor(self, axis, bound):\n        if self.spec is None:\n            return\n\n        if axis == \'x\' and getattr(self.spec, \'xticks\', []):\n            self.notify(\'This X axis is categorical.\')\n            return\n\n        current = self.axis_limit_overrides.get(\n            (self.selection.active, axis),\n            {},\n        ).get(bound)\n\n        title = f\'{axis.upper()} {"minimum" if bound == "min" else "maximum"}\'\n\n        def receive(result):\n            if result is not None:\n                self._receive_axis_limit(axis, bound, result)\n\n        self.push_screen(\n            AxisLimitScreen(title, current),\n            receive,\n        )\n\n    def _receive_axis_limit(self, axis, bound, result):\n        from .plotting.axes import axis_policy\n        from .ui.view_state import validate_bound_pair\n\n        if self.spec is None:\n            return\n\n        level = self.selection.active\n        key = (level, axis)\n        manual = dict(self.axis_limit_overrides.get(key, {}))\n\n        if result.get(\'mode\') == \'auto\':\n            manual.pop(bound, None)\n            if manual:\n                self.axis_limit_overrides[key] = manual\n            else:\n                self.axis_limit_overrides.pop(key, None)\n            asyncio.create_task(self.redraw())\n            return\n\n        value = result.get(\'value\')\n        if value is None:\n            return\n\n        scale = axis_policy(self.spec, axis)[0]\n        candidate = dict(manual)\n        candidate[bound] = float(value)\n\n        automatic = self._auto_axis_limits(self.spec, axis)\n        lower = candidate.get(\'min\')\n        upper = candidate.get(\'max\')\n        effective_lower = automatic[0] if lower is None else lower\n        effective_upper = automatic[1] if upper is None else upper\n\n        try:\n            validate_bound_pair(\n                effective_lower,\n                effective_upper,\n                scale,\n            )\n        except ValueError as exc:\n            self.notify(str(exc), severity=\'warning\')\n            return\n\n        self.axis_limit_overrides[key] = candidate\n        asyncio.create_task(self.redraw())\n\n    def action_view(self):\n        if self.view_focus:\n            self.view_focus = False\n            self._refresh_right_panel()\n            return\n\n        if self.spec is None:\n            self.notify(\n                \'View options are available once the current plot is prepared.\'\n            )\n            return\n\n        self.analysis_focus = False\n        self.fit_edit_mode = False\n        self.view_focus = True\n        self._normalize_view_index()\n        self.show_analysis()\n        self._refresh_right_panel()\n\n'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one current-code match, found {count}. "
            "No files were changed. Apply this only to the current "
            "Access_PNAS_psy_data code."
        )
    return text.replace(old, new, 1)


def main() -> int:
    if not APP.exists():
        print(f"Cannot find {APP}. Run from the repository root.")
        return 2

    original = APP.read_text(encoding="utf-8")

    if "self.view_focus = False" in original and "def action_view(self)" in original:
        print("View-options patch already appears applied; nothing changed.")
        return 0

    text = original

    text = replace_once(
        text,
        "from .ui.busy import BusyOverlay\n",
        "from .ui.busy import BusyOverlay\n"
        "from .ui.axis_limit_screen import AxisLimitScreen\n"
        "from .ui.view_state import SCALE_CHOICES, SCOPE_CHOICES, cycle_choice\n",
        "imports",
    )

    text = replace_once(
        text,
        "        ('a', 'analysis', 'Analysis'),\n"
        "        ('x', 'x_scale', 'X scale'),\n"
        "        ('y', 'y_scale', 'Y scale'),\n",
        "        ('a', 'analysis', 'Analysis'),\n"
        "        ('v', 'view', 'View'),\n"
        "        Binding('x', 'x_scale', 'X scale', show=False),\n"
        "        Binding('y', 'y_scale', 'Y scale', show=False),\n",
        "footer bindings",
    )

    text = replace_once(
        text,
        "        # Temporary per-level axis scale overrides. Empty = YAML / plot default.\n"
        "        self.axis_scale_overrides = {}\n",
        "        # Session-only View overrides, scoped by hierarchy level/view type.\n"
        "        # No entry means the dataset/default policy remains authoritative.\n"
        "        self.axis_scale_overrides = {}\n"
        "        self.axis_limit_overrides = {}\n"
        "        self.axis_scope_overrides = {}\n"
        "        self.view_focus = False\n"
        "        self.view_index = 0\n",
        "View state",
    )

    text = replace_once(
        text,
        "        sibling_values,\n"
        "        decorate_axis_policy=None,\n"
        "    ):\n",
        "        sibling_values,\n"
        "        decorate_axis_policy=None,\n"
        "        scope_override=None,\n"
        "    ):\n",
        "row-axis signature",
    )

    text = replace_once(
        text,
        "        policies = adapter.config.get('axis_policy', {}).get(level_definition.column, {})\n"
        "        row_available = {}\n",
        "        raw_policies = adapter.config.get('axis_policy', {}).get(\n"
        "            level_definition.column,\n"
        "            {},\n"
        "        )\n"
        "        policies = {\n"
        "            axis: dict(raw_policies.get(axis, {}))\n"
        "            if isinstance(raw_policies.get(axis, {}), dict)\n"
        "            else {}\n"
        "            for axis in ('x', 'y')\n"
        "        }\n"
        "        if scope_override in ('data', 'row'):\n"
        "            for axis in ('x', 'y'):\n"
        "                policies[axis]['limits'] = scope_override\n"
        "\n"
        "        row_available = {}\n",
        "effective scope policy",
    )

    old_scope_metadata = """        spec.metadata[
            '_row_axis_scope'
        ] = (
            f'fixed across {len(sibling_specs)} '
            f'{level_definition.name} value'
            + (
                ''
                if len(sibling_specs) == 1
                else 's'
            )
        )

        return spec
"""
    new_scope_metadata = """        shared_axes = []
        if policies.get('y', {}).get('limits') != 'data':
            shared_axes.append('Y')
        if (
            not getattr(spec, 'xticks', [])
            and policies.get('x', {}).get('limits') != 'data'
        ):
            shared_axes.append('X')

        if shared_axes:
            spec.metadata['_row_axis_scope'] = (
                f"{'/'.join(shared_axes)} fixed across {len(sibling_specs)} "
                f'{level_definition.name} value'
                + ('' if len(sibling_specs) == 1 else 's')
                + (' (user override)' if scope_override else '')
            )
        else:
            spec.metadata['_row_axis_scope'] = (
                'current selection data'
                + (' (user override)' if scope_override else '')
            )

        spec.metadata['_limit_scope_source'] = (
            'user override' if scope_override else 'dataset config'
        )

        return spec
"""
    text = replace_once(
        text,
        old_scope_metadata,
        new_scope_metadata,
        "row-axis scope metadata",
    )

    text = replace_once(
        text,
        "                            sibling_values,\n"
        "                            self._decorate_axis_policy,\n"
        "                        )\n",
        "                            sibling_values,\n"
        "                            self._decorate_axis_policy,\n"
        "                            self.axis_scope_overrides.get(level),\n"
        "                        )\n",
        "background scope argument",
    )

    text = replace_once(
        text,
        "                sibling_values,\n"
        "                self._decorate_axis_policy,\n"
        "            )\n"
        "            self.display_spec(\n"
        "                spec\n"
        "            )\n",
        "                sibling_values,\n"
        "                self._decorate_axis_policy,\n"
        "                self.axis_scope_overrides.get(level),\n"
        "            )\n"
        "            self._apply_view_axis_limits(spec, level)\n"
        "            self.display_spec(\n"
        "                spec\n"
        "            )\n",
        "foreground scope/manual limits",
    )

    text = replace_once(
        text,
        "                    if (\n"
        "                        generation\n"
        "                        == self.plot_generation\n"
        "                    ):\n"
        "                        self.display_spec(\n"
        "                            spec\n"
        "                        )\n",
        "                    if (\n"
        "                        generation\n"
        "                        == self.plot_generation\n"
        "                    ):\n"
        "                        self._apply_view_axis_limits(spec, level)\n"
        "                        self.display_spec(\n"
        "                            spec\n"
        "                        )\n",
        "background manual limits",
    )

    text = replace_once(
        text,
        "    def _legend_text(self, spec):\n",
        VIEW_METHODS + "    def _legend_text(self, spec):\n",
        "View methods",
    )

    text = replace_once(
        text,
        "        self.query_one(\n"
        "            '#legend',\n"
        "            Static,\n"
        "        ).update(\n"
        "            self._legend_text(\n"
        "                spec\n"
        "            )\n"
        "        )\n",
        "        self._refresh_right_panel(spec)\n",
        "right-panel display",
    )

    text = replace_once(
        text,
        "                if not valid:\n"
        "                    self.notify(\n"
        "                        f'{axis.upper()} log scale requires positive empirical data and uncertainty '\n"
        "                        'throughout the displayed row. Scale unchanged.'\n"
        "                    )\n"
        "                    return\n"
        "            self.axis_scale_overrides[\n",
        "                manual = getattr(self, 'axis_limit_overrides', {}).get(key, {})\n"
        "                if valid and any(\n"
        "                    value is not None and value <= 0\n"
        "                    for value in (manual.get('min'), manual.get('max'))\n"
        "                ):\n"
        "                    valid = False\n"
        "                if not valid:\n"
        "                    self.notify(\n"
        "                        f'{axis.upper()} log scale requires positive empirical data, uncertainty, '\n"
        "                        'and manual bounds throughout the displayed row. Scale unchanged.'\n"
        "                    )\n"
        "                    return\n"
        "            self.axis_scale_overrides[\n",
        "hidden X/Y compatibility validation",
    )

    text = replace_once(
        text,
        "    def action_analysis(self):\n"
        "        if not hasattr(\n",
        "    def action_analysis(self):\n"
        "        if self.view_focus:\n"
        "            self.view_focus = False\n"
        "            self._refresh_right_panel()\n"
        "\n"
        "        if not hasattr(\n",
        "Analysis/View focus",
    )

    text = replace_once(
        text,
        "    def action_hierarchy_focus(self):\n"
        "        self.analysis_focus = False\n"
        "        self.fit_edit_mode = False\n"
        "        self.show_analysis()\n",
        "    def action_hierarchy_focus(self):\n"
        "        if self.view_focus:\n"
        "            self.view_focus = False\n"
        "            self._refresh_right_panel()\n"
        "            return\n"
        "        self.analysis_focus = False\n"
        "        self.fit_edit_mode = False\n"
        "        self.show_analysis()\n",
        "Escape View handling",
    )

    for old, new, label in [
        (
            "    async def action_previous(self):\n        if self.fit_edit_mode:\n",
            "    async def action_previous(self):\n"
            "        if self.view_focus:\n"
            "            await self._view_change(-1)\n"
            "            return\n\n"
            "        if self.fit_edit_mode:\n",
            "View left",
        ),
        (
            "    async def action_next(self):\n        if self.fit_edit_mode:\n",
            "    async def action_next(self):\n"
            "        if self.view_focus:\n"
            "            await self._view_change(1)\n"
            "            return\n\n"
            "        if self.fit_edit_mode:\n",
            "View right",
        ),
        (
            "    async def action_child(self):\n        self.analysis_focus = False\n",
            "    async def action_child(self):\n"
            "        if self.view_focus:\n"
            "            self._view_move(1)\n"
            "            return\n\n"
            "        self.analysis_focus = False\n",
            "View down",
        ),
        (
            "    async def action_parent(self):\n        self.analysis_focus = False\n",
            "    async def action_parent(self):\n"
            "        if self.view_focus:\n"
            "            self._view_move(-1)\n"
            "            return\n\n"
            "        self.analysis_focus = False\n",
            "View up",
        ),
        (
            "    async def action_first(self):\n        if self.fit_edit_mode:\n",
            "    async def action_first(self):\n"
            "        if self.view_focus:\n"
            "            return\n\n"
            "        if self.fit_edit_mode:\n",
            "View Home guard",
        ),
        (
            "    async def action_last(self):\n        if self.fit_edit_mode:\n",
            "    async def action_last(self):\n"
            "        if self.view_focus:\n"
            "            return\n\n"
            "        if self.fit_edit_mode:\n",
            "View End guard",
        ),
        (
            "    async def action_enter(self):\n        if self.fit_edit_mode:\n",
            "    async def action_enter(self):\n"
            "        if self.view_focus:\n"
            "            await self._view_activate()\n"
            "            return\n\n"
            "        if self.fit_edit_mode:\n",
            "View Enter",
        ),
    ]:
        text = replace_once(text, old, new, label)

    text = replace_once(
        text,
        "            self.fit_enabled = False\n"
        "            self.fit_edit_mode = False\n"
        "            self.fit_cursor_index = 0\n"
        "\n"
        "            self.selection.refresh()\n",
        "            self.fit_enabled = False\n"
        "            self.fit_edit_mode = False\n"
        "            self.fit_cursor_index = 0\n"
        "            self.axis_scale_overrides.clear()\n"
        "            self.axis_limit_overrides.clear()\n"
        "            self.axis_scope_overrides.clear()\n"
        "            self.view_focus = False\n"
        "            self.view_index = 0\n"
        "\n"
        "            self.selection.refresh()\n",
        "reload View reset",
    )

    required = [
        "('v', 'view', 'View')",
        "Binding('x', 'x_scale', 'X scale', show=False)",
        "self.axis_limit_overrides = {}",
        "self.axis_scope_overrides = {}",
        "def action_view(self):",
        "def _apply_view_axis_limits(self, spec, level):",
        "scope_override=None",
        "self._apply_view_axis_limits(spec, level)",
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"Internal patch validation failed: {missing}")

    for dependency in (
        Path("src/psyview/ui/axis_limit_screen.py"),
        Path("src/psyview/ui/view_state.py"),
    ):
        if not dependency.exists():
            raise RuntimeError(
                f"Missing {dependency}. Extract the whole ZIP over the repo "
                "before running this patcher."
            )

    if not BACKUP.exists():
        shutil.copy2(APP, BACKUP)

    APP.write_text(text, encoding="utf-8")
    print(f"Patched {APP}")
    print(f"Backup: {BACKUP}")
    print("No scientific data, thresholds, fits, or repositories were changed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PATCH ABORTED: {exc}", file=sys.stderr)
        raise SystemExit(1)
