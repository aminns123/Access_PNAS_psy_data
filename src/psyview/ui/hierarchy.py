from textual.containers import HorizontalScroll, Vertical
from textual.widgets import Static


class Hierarchy(Vertical):
    async def show_state(self, state):
        await self.remove_children()
        for index, level in enumerate(state.adapter.levels()):
            if index > state.active:
                break
            row = HorizontalScroll(classes='choice-row')
            row.border_title = level.name.upper() + (f' ({level.units})' if level.units else '')
            await self.mount(row)
            values = state.adapter.get_values(index, state.filters(index))
            for value in values:
                chosen = value == state.selected[index]
                label = f'{value:g}' if isinstance(value, (float, int)) else str(value)
                item = Static(label, classes='choice' + (' selected' if chosen else '') + (' active' if chosen and index == state.active else ''), markup=False)
                await row.mount(item)
                if chosen:
                    row.call_after_refresh(item.scroll_visible, animate=False)
