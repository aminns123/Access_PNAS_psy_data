"""Safe on-demand fitting of user-defined lateral-profile functions.

Custom expressions are parsed with ``ast`` and evaluated by an explicit
mathematical interpreter. Python ``eval`` / ``exec`` are never used.
"""
from __future__ import annotations

from dataclasses import dataclass
import ast
import math
import re

import numpy as np
from scipy.optimize import least_squares

from .lateral_fit import _clean_profile


_ALLOWED_FUNCTIONS = {
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "sinh": np.sinh,
    "cosh": np.cosh,
    "tanh": np.tanh,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "sign": np.sign,
}

_CONSTANTS = {
    "pi": float(np.pi),
    "e": float(np.e),
}

_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
}

_UNARYOPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}

_RESERVED = {
    "x",
    *_ALLOWED_FUNCTIONS,
    *_CONSTANTS,
}

_PARAMETER_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?)\s*"
    r"\[\s*(.*?)\s*,\s*(.*?)\s*\]\s*$"
)


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    initial: float
    lower: float
    upper: float


@dataclass(frozen=True)
class CustomFitDefinition:
    source_expression: str
    normalized_expression: str
    parameters: tuple[ParameterSpec, ...]

    def cache_key(self):
        return (
            self.normalized_expression,
            tuple(
                (
                    parameter.name,
                    round(parameter.initial, 14),
                    round(parameter.lower, 14),
                    round(parameter.upper, 14),
                )
                for parameter in self.parameters
            ),
        )

    def parameter_text(self):
        return "; ".join(
            f"{parameter.name}={parameter.initial:g}"
            f"[{parameter.lower:g},{parameter.upper:g}]"
            for parameter in self.parameters
        )


@dataclass(frozen=True)
class CustomFitResult:
    x_curve: list[float]
    y_curve: list[float]
    parameters: tuple[tuple[str, float], ...]
    rmse: float
    weighted_rms: float
    r_squared: float
    n_points: int
    excluded_points: int
    sigma_floor: float


def normalize_expression(expression):
    text = str(expression).strip()

    if not text:
        raise ValueError("Equation cannot be empty.")
    if len(text) > 600:
        raise ValueError("Equation is too long (maximum 600 characters).")

    replacements = {
        "−": "-",
        "×": "*",
        "·": "*",
        "π": "pi",
        "λ": "lam",
        "φ": "phi",
        r"\left": "",
        r"\right": "",
        r"\lambda": "lam",
        r"\phi": "phi",
        r"\pi": "pi",
        r"\sin": "sin",
        r"\cos": "cos",
        r"\tan": "tan",
        r"\sinh": "sinh",
        r"\cosh": "cosh",
        r"\tanh": "tanh",
        r"\exp": "exp",
        r"\log": "log",
        r"\ln": "log",
        r"\sqrt": "sqrt",
        r"\mathrm{sgn}": "sign",
        r"\operatorname{sgn}": "sign",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\bsgn\b", "sign", text)
    text = re.sub(r"\bln\b", "log", text)
    text = text.replace("^", "**")
    text = text.replace("{", "(").replace("}", ")")

    previous = None
    while previous != text and "|" in text:
        previous = text
        text = re.sub(
            r"\|([^|]+)\|",
            r"abs(\1)",
            text,
        )

    if "|" in text:
        raise ValueError(
            "Unmatched absolute-value bar. Use abs(...) for nested expressions."
        )

    return text


def _validate_expression_tree(tree):
    parameters = []
    seen = set()

    def visit(node):
        if isinstance(node, ast.Expression):
            visit(node.body)
            return

        if isinstance(node, ast.BinOp):
            if type(node.op) not in _BINOPS:
                raise ValueError("That arithmetic operator is not allowed.")
            visit(node.left)
            visit(node.right)
            return

        if isinstance(node, ast.UnaryOp):
            if type(node.op) not in _UNARYOPS:
                raise ValueError("That unary operator is not allowed.")
            visit(node.operand)
            return

        if isinstance(node, ast.Call):
            if (
                not isinstance(node.func, ast.Name)
                or node.func.id not in _ALLOWED_FUNCTIONS
                or node.keywords
            ):
                raise ValueError(
                    "Only the documented mathematical functions may be called."
                )
            if len(node.args) != 1:
                raise ValueError(
                    f"{node.func.id}() requires exactly one argument."
                )
            visit(node.args[0])
            return

        if isinstance(node, ast.Name):
            name = node.id
            if name.startswith("_"):
                raise ValueError("Names beginning with '_' are not allowed.")
            if name not in _RESERVED and name not in seen:
                seen.add(name)
                parameters.append(name)
            return

        if isinstance(node, ast.Constant):
            if (
                isinstance(node.value, bool)
                or not isinstance(node.value, (int, float))
            ):
                raise ValueError("Only real numeric constants are allowed.")
            return

        raise ValueError(
            f"Unsupported equation syntax: {type(node).__name__}."
        )

    visit(tree)

    if not parameters:
        raise ValueError(
            "A fitted custom equation must contain at least one free parameter."
        )

    if len(parameters) > 12:
        raise ValueError("At most 12 fitted parameters are supported.")

    return tuple(parameters)


def _numeric_value(node):
    if isinstance(node, ast.Expression):
        return _numeric_value(node.body)

    if (
        isinstance(node, ast.Constant)
        and not isinstance(node.value, bool)
        and isinstance(node.value, (int, float))
    ):
        return float(node.value)

    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]

    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return float(
            _BINOPS[type(node.op)](
                _numeric_value(node.left),
                _numeric_value(node.right),
            )
        )

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return float(
            _UNARYOPS[type(node.op)](
                _numeric_value(node.operand)
            )
        )

    raise ValueError(
        "Parameter values and bounds may use numbers, pi/e, and simple arithmetic."
    )


def _parse_number(text):
    try:
        tree = ast.parse(
            normalize_expression(text),
            mode="eval",
        )
    except SyntaxError as exc:
        raise ValueError(
            f"Invalid numeric value {text!r}."
        ) from exc

    value = _numeric_value(tree)

    if not math.isfinite(value):
        raise ValueError(
            "Parameter values and bounds must be finite."
        )

    return value


def parse_parameter_text(parameter_text, expected_names):
    parameter_text = str(parameter_text).strip()
    if not parameter_text:
        raise ValueError("Parameter definitions cannot be empty.")
    if len(parameter_text) > 600:
        raise ValueError(
            "Parameter definitions are too long (maximum 600 characters)."
        )

    chunks = [
        chunk.strip()
        for chunk in parameter_text.split(";")
        if chunk.strip()
    ]

    parsed = {}

    for chunk in chunks:
        match = _PARAMETER_RE.match(chunk)

        if match is None:
            raise ValueError(
                "Parameters must use name=initial[lower,upper], separated by ';'."
            )

        (
            name,
            initial_text,
            lower_text,
            upper_text,
        ) = match.groups()

        if name in _RESERVED:
            raise ValueError(f"{name!r} is reserved.")

        if name in parsed:
            raise ValueError(
                f"Parameter {name!r} was supplied more than once."
            )

        parameter = ParameterSpec(
            name=name,
            initial=_parse_number(initial_text),
            lower=_parse_number(lower_text),
            upper=_parse_number(upper_text),
        )

        if not parameter.lower < parameter.upper:
            raise ValueError(
                f"{name}: lower bound must be smaller than upper bound."
            )

        if not (
            parameter.lower
            <= parameter.initial
            <= parameter.upper
        ):
            raise ValueError(
                f"{name}: initial value must lie inside its bounds."
            )

        parsed[name] = parameter

    missing = [
        name
        for name in expected_names
        if name not in parsed
    ]
    extra = [
        name
        for name in parsed
        if name not in expected_names
    ]

    if missing:
        raise ValueError(
            "Missing parameter definition(s): "
            + ", ".join(missing)
        )

    if extra:
        raise ValueError(
            "Parameter definition(s) not used by the equation: "
            + ", ".join(extra)
        )

    return tuple(
        parsed[name]
        for name in expected_names
    )


def build_custom_fit_definition(expression, parameter_text):
    normalized = normalize_expression(expression)

    try:
        tree = ast.parse(
            normalized,
            mode="eval",
        )
    except SyntaxError as exc:
        raise ValueError(
            f"Invalid equation syntax: {exc.msg}."
        ) from exc

    names = _validate_expression_tree(tree)
    parameters = parse_parameter_text(
        parameter_text,
        names,
    )

    return CustomFitDefinition(
        source_expression=str(expression).strip(),
        normalized_expression=normalized,
        parameters=parameters,
    )


def _evaluate_node(node, environment):
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, environment)

    if isinstance(node, ast.Constant):
        return float(node.value)

    if isinstance(node, ast.Name):
        if node.id in environment:
            return environment[node.id]
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"Unknown name {node.id!r}.")

    if isinstance(node, ast.BinOp):
        return _BINOPS[type(node.op)](
            _evaluate_node(node.left, environment),
            _evaluate_node(node.right, environment),
        )

    if isinstance(node, ast.UnaryOp):
        return _UNARYOPS[type(node.op)](
            _evaluate_node(node.operand, environment)
        )

    if isinstance(node, ast.Call):
        return _ALLOWED_FUNCTIONS[
            node.func.id
        ](
            _evaluate_node(node.args[0], environment)
        )

    raise ValueError("Unsupported equation node.")


def evaluate_custom_function(
    definition,
    x,
    parameter_values,
):
    x = np.asarray(x, dtype=float)

    if len(parameter_values) != len(definition.parameters):
        raise ValueError(
            "Incorrect number of parameter values."
        )

    environment = {"x": x}
    environment.update(
        {
            parameter.name: float(value)
            for parameter, value in zip(
                definition.parameters,
                parameter_values,
                strict=True,
            )
        }
    )

    tree = ast.parse(
        definition.normalized_expression,
        mode="eval",
    )

    with np.errstate(all="ignore"):
        value = _evaluate_node(
            tree,
            environment,
        )

    output = np.asarray(
        value,
        dtype=float,
    )

    if output.ndim == 0:
        output = np.full_like(
            x,
            float(output),
        )

    try:
        return np.broadcast_to(
            output,
            x.shape,
        ).astype(
            float,
            copy=False,
        )
    except ValueError as exc:
        raise ValueError(
            "Equation output cannot be matched to the x-data shape."
        ) from exc


def fit_custom_profile(
    frame,
    definition,
    *,
    excluded_x=(),
    sigma_floor=0.05,
):
    x, y, sigma, excluded_count = _clean_profile(
        frame,
        sigma_floor,
        excluded_x,
    )

    parameter_count = len(
        definition.parameters
    )
    minimum_points = max(
        5,
        parameter_count + 1,
    )

    if len(x) < minimum_points:
        raise ValueError(
            f"At least {minimum_points} included profile points are required "
            f"for {parameter_count} fitted parameters; found {len(x)}."
        )

    lower = np.array(
        [
            parameter.lower
            for parameter in definition.parameters
        ],
        dtype=float,
    )
    upper = np.array(
        [
            parameter.upper
            for parameter in definition.parameters
        ],
        dtype=float,
    )
    initial = np.array(
        [
            parameter.initial
            for parameter in definition.parameters
        ],
        dtype=float,
    )

    def prediction(params, x_values=x):
        return evaluate_custom_function(
            definition,
            x_values,
            params,
        )

    def residuals(params):
        try:
            predicted = prediction(params)
        except (
            ValueError,
            FloatingPointError,
            OverflowError,
        ):
            return np.full_like(
                y,
                1e12,
                dtype=float,
            )

        if not np.all(np.isfinite(predicted)):
            return np.full_like(
                y,
                1e12,
                dtype=float,
            )

        return (
            predicted - y
        ) / sigma

    starts = [initial]
    rng = np.random.default_rng(0)

    for _ in range(8):
        starts.append(
            lower
            + (upper - lower)
            * rng.uniform(
                0.05,
                0.95,
                size=parameter_count,
            )
        )

    best = None
    best_cost = float("inf")

    for start in starts:
        try:
            result = least_squares(
                residuals,
                start,
                bounds=(
                    lower,
                    upper,
                ),
                method="trf",
                max_nfev=3000,
                xtol=1e-10,
                ftol=1e-10,
                gtol=1e-10,
            )
            cost = float(
                np.sum(
                    residuals(
                        result.x
                    ) ** 2
                )
            )
        except (
            ValueError,
            FloatingPointError,
            OverflowError,
        ):
            continue

        if (
            result.success
            and np.all(np.isfinite(result.x))
            and np.isfinite(cost)
            and cost < best_cost
        ):
            best = result
            best_cost = cost

    if best is None:
        raise RuntimeError(
            "No stable custom fit was found. "
            "Try different starting values or parameter bounds."
        )

    fitted_at_data = prediction(
        best.x
    )

    if not np.all(np.isfinite(fitted_at_data)):
        raise RuntimeError(
            "The fitted equation returned non-finite values."
        )

    residual = y - fitted_at_data

    rmse = float(
        np.sqrt(
            np.mean(
                residual ** 2
            )
        )
    )
    weighted_rms = float(
        np.sqrt(
            np.mean(
                (residual / sigma) ** 2
            )
        )
    )

    total = float(
        np.sum(
            (y - np.mean(y)) ** 2
        )
    )
    r_squared = (
        float(
            1.0
            - np.sum(residual ** 2)
            / total
        )
        if total > 0
        else float("nan")
    )

    x_curve = np.linspace(
        float(np.min(x)),
        float(np.max(x)),
        500,
    )
    y_curve = evaluate_custom_function(
        definition,
        x_curve,
        best.x,
    )

    if not np.all(np.isfinite(y_curve)):
        raise RuntimeError(
            "The fitted equation is not finite over the displayed x range."
        )

    return CustomFitResult(
        x_curve=x_curve.tolist(),
        y_curve=y_curve.tolist(),
        parameters=tuple(
            (
                parameter.name,
                float(value),
            )
            for parameter, value in zip(
                definition.parameters,
                best.x,
                strict=True,
            )
        ),
        rmse=rmse,
        weighted_rms=weighted_rms,
        r_squared=r_squared,
        n_points=int(len(x)),
        excluded_points=excluded_count,
        sigma_floor=float(sigma_floor),
    )


def custom_fit_display_text(
    definition,
    result,
):
    r_squared = (
        f"{result.r_squared:.3f}"
        if math.isfinite(result.r_squared)
        else "n/a"
    )

    parameters = "  |  ".join(
        f"{name}={value:.5g}"
        for name, value in result.parameters
    )

    return (
        "INTERACTIVE / DIAGNOSTIC CUSTOM FIT\n"
        f"R(x)={definition.source_expression}\n"
        f"{parameters}\n"
        f"R²={r_squared}  |  "
        f"RMSE={result.rmse:.4g}  |  "
        f"weighted RMS={result.weighted_rms:.4g}\n"
        f"Fit points={result.n_points}  |  "
        f"Excluded={result.excluded_points}  |  "
        f"σ=max(full spread, {result.sigma_floor:g})"
    )
