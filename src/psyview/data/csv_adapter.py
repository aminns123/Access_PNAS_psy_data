from pathlib import Path
import pandas as pd
from .base import DatasetAdapter, DatasetError, safe_path
from ..models import Level, PlotSpec, Series
from .config import validate_config


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
                raise DatasetError(f'Source {level.source!r} lacks hierarchy column {level.column!r}.')

    def table(self, source):
        if source not in self.tables:
            path = safe_path(self.root, self.config['sources'][source])
            if not path.is_file():
                raise DatasetError(f"Missing required file: {path}. Check --data-root or restore the archive file.")
            try:
                frame = pd.read_csv(path, float_precision='round_trip')
                for column in frame.columns:
                    if column.startswith(('included_', 'in_last8')) or column == 'staircase_included':
                        values = frame[column].astype(str).str.lower()
                        if not values.isin(['true', 'false']).all():
                            raise DatasetError(f"Invalid or missing boolean flag: {path.name}: {column}")
                        frame[column] = values.eq('true')
                self.tables[source] = frame
            except (OSError, ValueError) as exc:
                raise DatasetError(f"Cannot read {path}: {exc}") from exc
        return self.tables[source]

    def select(self, source, filters):
        key = (source, tuple(sorted(filters.items())))
        if key not in self.filtered:
            frame = self.table(source)
            for column, value in filters.items():
                if column not in frame:
                    raise DatasetError(f"Source {source!r} lacks filter column {column!r}; configure an explicit join in an adapter.")
                frame = frame.loc[frame[column].eq(value)]
            self.filtered[key] = frame
        return self.filtered[key]

    def get_values(self, level, current_filters):
        item = self.levels()[level]
        return sorted(self.select(item.source, current_filters)[item.column].dropna().unique().tolist())

    def get_plot(self, level, current_filters):
        definition = self.config.get('plots', {}).get(self.levels()[level].column)
        if not definition:
            return PlotSpec('No plot configured', '', '', notes='Edit YAML to explicitly choose scientific x/y columns.', metadata=current_filters)
        frame = self.select(definition['source'], current_filters).sort_values(definition['x'])
        spec = PlotSpec(definition.get('title', self.name), definition.get('xlabel', definition['x']), definition.get('ylabel', definition['y']), metadata=current_filters)
        spec.series.append(Series(frame[definition['x']].tolist(), frame[definition['y']].tolist(), 'Recorded values', definition.get('kind', 'scatter')))
        return spec
