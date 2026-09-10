from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from .view_state import parse_axis_limit


class AxisLimitScreen(ModalScreen):
    """Tiny numeric editor used by the keyboard-first View panel."""

    CSS = """
    AxisLimitScreen {
        align: center middle;
        background: #000000 55%;
    }

    #axis-limit-dialog {
        width: 46;
        height: 10;
        padding: 1 2;
        border: round #6de5f2;
        background: #142132;
    }

    #axis-limit-title {
        height: 1;
        color: #72d9e6;
        text-style: bold;
    }

    #axis-limit-help {
        height: 2;
        color: #a8bacd;
    }

    #axis-limit-input {
        width: 100%;
        margin-top: 1;
    }

    #axis-limit-error {
        height: 2;
        margin-top: 1;
        color: #ff7b72;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        title: str,
        current: float | None = None,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.current = current

    def compose(self) -> ComposeResult:
        value = "" if self.current is None else f"{self.current:g}"
        with Vertical(id="axis-limit-dialog"):
            yield Static(self.title_text, id="axis-limit-title", markup=False)
            yield Static(
                "Enter a finite number, or type Auto to restore the automatic bound.",
                id="axis-limit-help",
                markup=False,
            )
            yield Input(
                value=value,
                placeholder="Auto or numeric value",
                id="axis-limit-input",
            )
            yield Static("", id="axis-limit-error", markup=False)

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            value = parse_axis_limit(event.value)
        except ValueError as exc:
            self.query_one("#axis-limit-error", Static).update(str(exc))
            return

        if value is None:
            self.dismiss({"mode": "auto"})
        else:
            self.dismiss({"mode": "value", "value": value})

    def action_cancel(self) -> None:
        self.dismiss(None)
