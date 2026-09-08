class SelectionState:
    """Remember each branch independently; only ancestors propagate as filters."""
    def __init__(self, adapter):
        self.adapter = adapter
        self.active = 0
        self.memory = {}
        self.selected = []
        self.refresh()

    def filters(self, before=None):
        end = self.active + 1 if before is None else before
        return {item.column: value for item, value in zip(self.adapter.levels()[:end], self.selected[:end]) if value is not None}

    def refresh(self):
        self.selected = []
        for index in range(len(self.adapter.levels())):
            key = (index, tuple(self.selected))
            values = self.adapter.get_values(index, self.filters(index)) if None not in self.selected else []
            value = self.memory.get(key)
            if value not in values:
                value = values[0] if values else None
            self.selected.append(value)
            self.memory[key] = value

    def move(self, delta=0, edge=None):
        values = self.adapter.get_values(self.active, self.filters(self.active))
        if not values:
            return
        index = values.index(self.selected[self.active])
        index = (0 if edge == 'first' else len(values)-1) if edge else (index+delta) % len(values)
        self.memory[(self.active, tuple(self.selected[:self.active]))] = values[index]
        self.refresh()

    def down(self):
        if self.active + 1 < len(self.selected) and self.selected[self.active+1] is not None:
            self.active += 1

    def up(self):
        self.active = max(0, self.active-1)
