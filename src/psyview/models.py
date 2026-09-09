from dataclasses import dataclass, field


FIT_COLOR = "red"


@dataclass(frozen=True)
class Level:
    name: str
    column: str
    source: str
    units: str = ""


@dataclass
class Series:
    x: list[float]
    y: list[float]
    label: str
    kind: str = "line"
    color: str = "cyan"
    dashed: bool = False
    marker: str = '●'


@dataclass
class PlotSpec:
    title: str
    xlabel: str
    ylabel: str
    series: list[Series] = field(default_factory=list)
    xscale: str = "linear"
    yscale: str = "linear"
    notes: str = ""
    metadata: dict = field(default_factory=dict)

    # Generic display overrides for adapters that need shared scales or
    # categorical labels.
    xlim: tuple[float, float] | None = None
    ylim: tuple[float, float] | None = None
    xticks: list[tuple[float, str]] = field(default_factory=list)
    yticks: list[tuple[float, str]] = field(default_factory=list)
