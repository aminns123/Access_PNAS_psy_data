from dataclasses import dataclass, field


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
