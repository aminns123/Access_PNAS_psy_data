from textual.containers import HorizontalScroll, Vertical
from textual.widgets import Static


class Hierarchy(Vertical):
    """Compact hierarchy: one breadcrumb plus the active selector row."""

    def _breadcrumb(self, state):
        # Show the selected path compactly, using source values rather than
        # hard-coded dataset semantics. This works for arbitrary hierarchies:
        #
        #   P01 | 40 | 0.768 | base | S1
        #
        # The active row below still shows the full set of choices for the
        # current level, so the user always knows both where they are and what
        # can be changed.
        values = []

        for index in range(state.active + 1):
            if index >= len(state.selected):
                break

            value = state.selected[index]
            if value is None:
                break

            if isinstance(value, (float, int)):
                label = f'{value:g}'
            else:
                label = str(value)

            values.append(label)

        return (
            'PATH: ' + ' | '.join(values)
            if values
            else 'PATH: —'
        )

    async def show_state(self, state):
        await self.remove_children()

        # Stable-height breadcrumb: previous hierarchy levels collapse here
        # instead of remaining as full boxed rows.
        await self.mount(
            Static(
                self._breadcrumb(state),
                id='hierarchy-path',
                markup=False,
            )
        )

        level = state.adapter.levels()[
            state.active
        ]

        row = HorizontalScroll(
            classes='choice-row'
        )
        row.border_title = (
            level.name.upper()
            + (
                f' ({level.units})'
                if level.units
                else ''
            )
        )
        await self.mount(row)

        values = state.adapter.get_values(
            state.active,
            state.filters(
                state.active
            ),
        )

        for value in values:
            chosen = (
                value
                == state.selected[
                    state.active
                ]
            )

            label = (
                f'{value:g}'
                if isinstance(
                    value,
                    (float, int),
                )
                else str(value)
            )

            item = Static(
                label,
                classes=(
                    'choice'
                    + (
                        ' selected'
                        if chosen
                        else ''
                    )
                    + (
                        ' active'
                        if chosen
                        else ''
                    )
                ),
                markup=False,
            )

            await row.mount(item)

            if chosen:
                row.call_after_refresh(
                    item.scroll_visible,
                    animate=False,
                )
