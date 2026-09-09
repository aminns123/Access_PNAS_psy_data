from pathlib import Path
import pandas as pd
from .base import DatasetAdapter, DatasetError, safe_path
from ..models import Level, PlotSpec, Series
from .config import validate_config


def _looks_boolean_name(column):
    """Return True for columns whose names commonly encode logical flags.

    A name alone is not enough to force conversion: e.g. ``included_staircases``
    is a numeric count, not a boolean.  Conversion is therefore also gated by
    the observed values in ``_coerce_boolean_columns``.
    """
    return (
        column.startswith(('included_', 'in_', 'is_', 'used_', 'dominant_'))
        or column.endswith(('_included', '_excluded'))
        or column in {
            'staircase_included',
            'counts_match',
            'retained_for_display',
            'accepted_fms_ra',
        }
    )


def _coerce_boolean_columns(frame, path):
    """Convert genuine True/False columns without misreading count columns.

    Previous PsyView code converted every column beginning with ``included_``.
    That incorrectly treated lateral archive fields such as
    ``included_staircases`` (an integer count) as boolean flags.

    Rules:
    - Only boolean-looking column names are considered.
    - If all non-missing values are True/False tokens, convert to bool.
    - Numeric/count columns are left untouched.
    - If a column contains some True/False tokens plus invalid text, fail
      loudly instead of silently accepting a corrupted logical flag.
    """
    for column in frame.columns:
        if not _looks_boolean_name(column):
            continue

        series = frame[column]
        nonmissing = series.loc[series.notna()]
        if nonmissing.empty:
            continue

        # pandas may already have inferred a proper bool dtype.
        if pd.api.types.is_bool_dtype(nonmissing):
            continue

        # Numeric columns such as included_staircases are counts, not flags.
        if pd.api.types.is_numeric_dtype(nonmissing):
            continue

        values = nonmissing.astype(str).str.strip().str.lower()
        unique = set(values.unique())
        boolean_tokens = {'true', 'false'}

        if unique and unique.issubset(boolean_tokens):
            # Preserve rows exactly; current scientific archives do not use
            # missing values for these logical flags.
            if series.isna().any():
                raise DatasetError(
                    f"Invalid or missing boolean flag: {path.name}: {column}"
                )
            frame[column] = values.eq('true')
            continue

        # If the column partly resembles a logical flag, treat the remaining
        # token(s) as a data error.  Pure text/numeric-like count columns are
        # left alone.
        if unique & boolean_tokens:
            raise DatasetError(
                f"Invalid boolean value in {path.name}: {column}: "
                f"{sorted(unique - boolean_tokens)}"
            )

    return frame


class CSVAdapter(DatasetAdapter):
    def __init__(self, config):
        self.config = validate_config(config)
        self.name = config['dataset']['name']
        self._levels = [Level(**x) for x in config['hierarchy']]
        self.tables = {}
        self.filtered = {}

    def levels(self):
        return self._levels

    def load(self, root):
        self.root = Path(root).resolve()
        self.tables = {}
        self.filtered = {}
        for level in self.levels():
            if level.column not in self.table(level.source):
                raise DatasetError(
                    f'Source {level.source!r} lacks hierarchy column '
                    f'{level.column!r}.'
                )

    def table(self, source):
        if source not in self.tables:
            path = safe_path(self.root, self.config['sources'][source])
            if not path.is_file():
                raise DatasetError(
                    f"Missing required file: {path}. "
                    f"Check --data-root or restore the archive file."
                )
            try:
                frame = pd.read_csv(path, float_precision='round_trip')
                frame = _coerce_boolean_columns(frame, path)
                self.tables[source] = frame
            except DatasetError:
                raise
            except (OSError, ValueError) as exc:
                raise DatasetError(f"Cannot read {path}: {exc}") from exc
        return self.tables[source]

    def select(self, source, filters):
        key = (source, tuple(sorted(filters.items())))
        if key not in self.filtered:
            frame = self.table(source)
            for column, value in filters.items():
                if column not in frame:
                    raise DatasetError(
                        f"Source {source!r} lacks filter column {column!r}; "
                        f"configure an explicit join in an adapter."
                    )
                frame = frame.loc[frame[column].eq(value)]
            self.filtered[key] = frame
        return self.filtered[key]

    def get_values(self, level, current_filters):
        item = self.levels()[level]
        values = (
            self.select(item.source, current_filters)[item.column]
            .dropna()
            .unique()
            .tolist()
        )

        import re

        def natural(value):
            return tuple(
                (0, int(part)) if part.isdigit() else (1, part.casefold())
                for part in re.split(r'(\d+)', str(value))
            )

        return (
            sorted(values)
            if pd.api.types.is_numeric_dtype(
                self.table(item.source)[item.column]
            )
            else sorted(values, key=natural)
        )

    def get_plot(self, level, current_filters):
        definition = self.config.get('plots', {}).get(
            self.levels()[level].column
        )
        if not definition:
            return PlotSpec(
                'No plot configured',
                '',
                '',
                notes=(
                    'Edit YAML to explicitly choose scientific x/y columns.'
                ),
                metadata=current_filters,
            )

        frame = self.select(
            definition['source'],
            current_filters,
        ).sort_values(definition['x'])

        spec = PlotSpec(
            definition.get('title', self.name),
            definition.get('xlabel', definition['x']),
            definition.get('ylabel', definition['y']),
            metadata=current_filters,
        )
        spec.series.append(
            Series(
                frame[definition['x']].tolist(),
                frame[definition['y']].tolist(),
                'Recorded values',
                definition.get('kind', 'scatter'),
            )
        )
        return spec
