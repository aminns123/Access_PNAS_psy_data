"""Modal editor for selecting a session-only custom fit function."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from .fit_function_state import (
    DEFAULT_EQUATION,
    DEFAULT_PARAMETERS,
    validate_fit_function,
)


class FitFunctionScreen(ModalScreen):
    """Edit and validate a custom lateral fit function."""

    CSS = """
    FitFunctionScreen {
        align: center middle;
        background: #000000 55%;
    }

    #fit-function-dialog {
        width: 96;
        height: 21;
        padding: 1 2;
        border: round #6de5f2;
        background: #142132;
    }

    #fit-function-title {
        height: 1;
        color: #72d9e6;
        text-style: bold;
    }

    #fit-function-help {
        height: 6;
        color: #a8bacd;
        margin-bottom: 1;
    }

    #fit-equation, #fit-parameters {
        width: 100%;
        margin-bottom: 1;
    }

    #fit-function-error {
        height: 2;
        color: #ff7b72;
    }

    #fit-function-footer {
        height: 2;
        color: #8092a9;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+r", "restore_default", "Default", show=False),
    ]

    def __init__(
        self,
        current=None,
    ) -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        equation = (
            self.current.source_expression
            if self.current is not None
            else DEFAULT_EQUATION
        )
        parameters = (
            self.current.parameter_text()
            if self.current is not None
            else DEFAULT_PARAMETERS
        )

        with Vertical(id="fit-function-dialog"):
            yield Static(
                "FIT FUNCTION",
                id="fit-function-title",
                markup=False,
            )
            yield Static(
                "Enter a custom function of x and fitted parameter "
                "starts/bounds. Applying it selects that function for F. "
                "Use explicit multiplication (*). Supported functions include "
                "sin, cos, tan, exp, log/ln, sqrt, abs and sign/sgn. "
                "Example: A*cos(2*pi*f*x+phi)",
                id="fit-function-help",
                markup=False,
            )
            yield Input(
                value=equation,
                placeholder=(
                    "Equation, e.g. A*cos(2*pi*f*x+phi)"
                ),
                id="fit-equation",
            )
            yield Input(
                value=parameters,
                placeholder=(
                    "A=0.2[-2,2]; f=3[0.1,20]; "
                    "phi=0[-pi,pi]"
                ),
                id="fit-parameters",
            )
            yield Static(
                "",
                id="fit-function-error",
                markup=False,
            )
            yield Static(
                "Enter: next/apply   Ctrl+R: thesis Eq. B.25   Esc: cancel",
                id="fit-function-footer",
                markup=False,
            )

    def on_mount(self) -> None:
        self.query_one(
            "#fit-equation",
            Input,
        ).focus()

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:
        if event.input.id == "fit-equation":
            self.query_one(
                "#fit-parameters",
                Input,
            ).focus()
            return

        if event.input.id != "fit-parameters":
            return

        equation = self.query_one(
            "#fit-equation",
            Input,
        ).value
        parameters = self.query_one(
            "#fit-parameters",
            Input,
        ).value

        try:
            definition = validate_fit_function(
                equation,
                parameters,
            )
        except ValueError as exc:
            self.query_one(
                "#fit-function-error",
                Static,
            ).update(str(exc))
            return

        self.dismiss(
            {
                "mode": "custom",
                "definition": definition,
            }
        )

    def action_restore_default(self) -> None:
        self.dismiss(
            {
                "mode": "default",
            }
        )

    def action_cancel(self) -> None:
        self.dismiss(None)
