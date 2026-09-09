"""Fast, read-only structural inspection for empirical repositories.

The inspector deliberately separates structural inference from scientific
interpretation. It only reads lightweight metadata, CSV headers and bounded
samples; known scientific meaning remains the responsibility of dataset
adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd


_SKIP_PARTS = {
    ".git", ".venv", "__pycache__", "bootstrap", "validation",
    "figures", "exports", "cache",
}

_ROLE_ALIASES = {
    "participant": {
        "participant_id", "participant", "subject_id", "subject",
        "observer_id", "observer",
    },
    "luminance": {
        "luminance_cd_m2", "luminance_label_cd_m2", "luminance",
        "background_luminance", "mean_luminance",
    },
    "condition": {"condition_id", "condition"},
    "position": {
        "probe_position_deg", "distance_from_flanker_edge_deg",
        "probe_position", "position", "separation_deg", "distance_deg",
    },
    "spatial_frequency": {
        "spatial_frequency_cpd", "spatial_frequency", "frequency_cpd",
        "frequency", "sf_cpd", "sf",
    },
    "experiment": {
        "experiment", "experiment_type", "stimulus_type", "session_type",
    },
    "staircase": {"staircase_id", "staircase"},
    "trial": {
        "trial_within_staircase", "trial_index", "trial_number", "trial",
    },
}

_ROLE_LABELS = {
    "participant": "Subject",
    "luminance": "Luminance",
    "condition": "Condition",
    "position": "Position",
    "spatial_frequency": "Spatial frequency",
    "experiment": "Experiment",
    "staircase": "Staircase",
    "trial": "Trial",
}

_ROLE_ORDER = (
    "participant", "luminance", "condition", "position",
    "spatial_frequency", "experiment", "staircase", "trial",
)


@dataclass(frozen=True)
class ColumnRole:
    column: str
    role: str
    confidence: float
    evidence: str


@dataclass
class TableReport:
    relative_path: str
    columns: list[str]
    numeric_candidates: list[str] = field(default_factory=list)
    categorical_candidates: list[str] = field(default_factory=list)
    sample_rows: int = 0
    roles: list[ColumnRole] = field(default_factory=list)
    error: str = ""


@dataclass
class RepositoryReport:
    root: Path
    tables: dict[str, TableReport]
    dictionary_rows: list[dict]
    best_table: str | None
    hierarchy: list[ColumnRole]
    confidence: float
    evidence: list[str]


def _candidate_paths(root: Path, max_files: int = 160) -> list[Path]:
    """Inspect only plausible material belonging to the selected dataset root."""
    paths: list[Path] = []

    for path in root.glob("*.csv*"):
        if path.is_file():
            paths.append(path)

    data_root = root / "data"
    if data_root.is_dir():
        for path in data_root.rglob("*.csv*"):
            if not path.is_file():
                continue
            relative_parts = set(path.relative_to(root).parts[:-1])
            if relative_parts & _SKIP_PARTS:
                continue
            if "_saved_fits" in path.name or "mode_assignments" in path.name:
                continue
            paths.append(path)

    unique = sorted({p.resolve() for p in paths}, key=lambda p: str(p).casefold())
    return unique[:max_files]


def _dictionary(root: Path) -> list[dict]:
    path = root / "data_dictionary.csv"
    if not path.is_file():
        return []
    try:
        return pd.read_csv(path, nrows=6000).fillna("").to_dict("records")
    except (OSError, ValueError, UnicodeError):
        return []


def _dictionary_index(rows: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for row in rows:
        field_name = str(row.get("field", "")).strip()
        if field_name:
            index.setdefault(field_name, []).append(row)
    return index


def _role_for_column(column: str, dictionary_index: dict[str, list[dict]]) -> list[ColumnRole]:
    lower = column.casefold()
    results: list[ColumnRole] = []
    dictionary_text = " ".join(
        str(row.get("description", "")) + " " + str(row.get("units", ""))
        for row in dictionary_index.get(column, [])
    ).casefold()

    for role, aliases in _ROLE_ALIASES.items():
        score = 0.0
        evidence = []
        if lower in aliases:
            score = 0.99
            evidence.append("exact column-name match")
        elif any(alias in lower or lower in alias for alias in aliases if len(alias) >= 4):
            score = max(score, 0.78)
            evidence.append("column-name pattern")

        keywords = {
            "participant": ("participant", "subject", "observer"),
            "luminance": ("luminance", "cd m", "cd/m"),
            "condition": ("condition id", "condition"),
            "position": ("position", "distance", "separation", "degree of visual angle"),
            "spatial_frequency": ("spatial frequency", "cycles degree", "cpd"),
            "experiment": ("experiment", "base or", "flanker"),
            "staircase": ("staircase",),
            "trial": ("trial",),
        }[role]

        if dictionary_text and any(word in dictionary_text for word in keywords):
            score = min(1.0, score + (0.12 if score else 0.62))
            evidence.append("data-dictionary description/units")

        if score >= 0.55:
            results.append(
                ColumnRole(column, role, round(score, 3), ", ".join(evidence))
            )
    return sorted(results, key=lambda item: item.confidence, reverse=True)


def _read_table(
    path: Path,
    root: Path,
    dictionary_index: dict[str, list[dict]],
    sample_rows: int,
) -> TableReport:
    relative = path.relative_to(root).as_posix()
    try:
        header = pd.read_csv(path, nrows=0)
        columns = header.columns.tolist()
        sample = pd.DataFrame(columns=columns)

        if path.stat().st_size <= 2_000_000:
            sample = pd.read_csv(path, nrows=sample_rows)

        numeric = sample.select_dtypes(include="number").columns.tolist()
        categorical = [
            column
            for column in sample.columns
            if len(sample) and sample[column].nunique(dropna=True) <= 40
        ]

        roles: list[ColumnRole] = []
        for column in columns:
            candidate_roles = _role_for_column(column, dictionary_index)
            if candidate_roles:
                roles.append(candidate_roles[0])

        return TableReport(
            relative_path=relative,
            columns=columns,
            numeric_candidates=numeric,
            categorical_candidates=categorical,
            sample_rows=len(sample),
            roles=roles,
        )
    except (OSError, ValueError, EOFError, UnicodeError) as exc:
        return TableReport(relative, [], error=str(exc))


def _best_hierarchy(
    tables: dict[str, TableReport],
) -> tuple[str | None, list[ColumnRole], float]:
    best_path = None
    best_roles: list[ColumnRole] = []
    best_score = -1.0

    for path, report in tables.items():
        by_role: dict[str, ColumnRole] = {}
        for item in report.roles:
            current = by_role.get(item.role)
            if current is None or item.confidence > current.confidence:
                by_role[item.role] = item

        roles = []
        for role in _ROLE_ORDER:
            if role == "condition" and "luminance" in by_role:
                continue
            if role == "trial":
                continue
            if role in by_role:
                roles.append(by_role[role])

        score = sum(item.confidence for item in roles)
        if any(item.role == "participant" for item in roles):
            score += 1.0
        if any(item.role == "staircase" for item in roles):
            score += 0.5
        if score > best_score:
            best_path, best_roles, best_score = path, roles, score

    if not best_roles:
        return None, [], 0.0

    mean_conf = sum(item.confidence for item in best_roles) / len(best_roles)
    structure_bonus = min(0.12, 0.03 * max(0, len(best_roles) - 1))
    return best_path, best_roles, min(0.99, mean_conf + structure_bonus)


@lru_cache(maxsize=128)
def inspect_repository(root) -> RepositoryReport:
    root = Path(root).expanduser().resolve()
    dictionary_rows = _dictionary(root)
    dictionary_index = _dictionary_index(dictionary_rows)

    tables: dict[str, TableReport] = {}
    for path in _candidate_paths(root):
        report = _read_table(path, root, dictionary_index, sample_rows=250)
        tables[report.relative_path] = report

    best_table, hierarchy, confidence = _best_hierarchy(tables)
    evidence = []
    if (root / "data_dictionary.csv").is_file():
        evidence.append("root data_dictionary.csv")
    if (root / "data").is_dir():
        evidence.append("root data/ directory")
    if best_table:
        evidence.append(f"hierarchy evidence in {best_table}")

    return RepositoryReport(
        root, tables, dictionary_rows, best_table, hierarchy, confidence, evidence
    )


def generic_config(report: RepositoryReport) -> dict:
    """Build a conservative one-table generic explorer configuration."""
    if report.best_table is None or not report.hierarchy:
        raise ValueError("No reliable one-table hierarchy could be inferred.")

    hierarchy = []
    for item in report.hierarchy:
        units = ""
        for row in report.dictionary_rows:
            if str(row.get("field", "")).strip() == item.column:
                units = str(row.get("units", "")).strip()
                break
        hierarchy.append(
            {
                "name": _ROLE_LABELS.get(item.role, item.column),
                "column": item.column,
                "source": "records",
                **(
                    {"units": units}
                    if units and units != "not applicable"
                    else {}
                ),
            }
        )

    return {
        "dataset": {
            "name": report.root.name,
            "adapter": "csv",
            "title": f"Generic empirical explorer — {report.root.name}",
            "citation": (
                "Scientific analysis type not identified; structural navigation only."
            ),
        },
        "sources": {"records": report.best_table},
        "hierarchy": hierarchy,
        "plots": {},
        "detection": {
            "confidence": report.confidence,
            "notes": (
                "Automatically inferred one-table hierarchy. Scientific x/y "
                "semantics were not guessed; no derived analysis is performed."
            ),
            "evidence": report.evidence,
        },
    }
