from textual.containers import HorizontalScroll, VerticalScroll
from textual.widgets import Static


class Hierarchy(VerticalScroll):
    """Scrollable hierarchy so the deepest selector row is never clipped."""

    async def show_state(self, state):
        await self.remove_children()

        active_row = None

        for index, level in enumerate(state.adapter.levels()):
            if index > state.active:
                break

            row = HorizontalScroll(classes='choice-row')
            row.border_title = (
                level.name.upper()
                + (f' ({level.units})' if level.units else '')
            )
            await self.mount(row)

            values = state.adapter.get_values(
                index,
                state.filters(index),
            )

            for value in values:
                chosen = (
                    value
                    == state.selected[index]
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
                            if (
                                chosen
                                and index
                                == state.active
                            )
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

            if index == state.active:
                active_row = row

        # With five lateral levels the final STAIRCASE row can otherwise be
        # clipped by the finite hierarchy viewport. Keep the active row visible
        # vertically as well as horizontally.
        if active_row is not None:
            active_row.call_after_refresh(
                active_row.scroll_visible,
                animate=False,
            )
