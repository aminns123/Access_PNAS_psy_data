from pathlib import Path
from .inspector import inspect_repository, generic_config


def discover(root=None):
    if root is not None:
        return Path(root).expanduser().resolve()
    return None


def infer_schema(root, sample_rows=200):
    """Return a conservative generic schema suggestion."""
    report = inspect_repository(Path(root).resolve())

    tables = {
        path: {
            'columns': item.columns,
            'numeric_candidates': item.numeric_candidates,
            'categorical_candidates': item.categorical_candidates,
            'sample_rows': item.sample_rows,
            **({'error': item.error} if item.error else {}),
        }
        for path, item in report.tables.items()
    }

    if report.best_table is None or not report.hierarchy:
        return {
            'dataset': {'name': Path(root).resolve().name, 'adapter': 'csv'},
            'sources': {},
            'hierarchy': [],
            'plots': {},
            'detection': {
                'confidence': 'tentative; human review required',
                'notes': 'No reliable one-table hierarchy was inferred.',
                'tables': tables,
                'shared_columns': _shared_columns(report),
                'dictionary_sample': report.dictionary_rows[:1000],
            },
        }

    config = generic_config(report)
    config['detection'] = {
        'confidence': (
            f'tentative; human review required '
            f'(structural score {report.confidence:.2f})'
        ),
        'notes': (
            'Hierarchy inferred from column names/data dictionary in one table. '
            'No scientific axes or cross-table joins inferred. Edit before scientific use.'
        ),
        'tables': tables,
        'shared_columns': _shared_columns(report),
        'dictionary_sample': report.dictionary_rows[:1000],
    }
    return config


def _shared_columns(report):
    owners = {}
    for path, table in report.tables.items():
        for column in table.columns:
            owners.setdefault(column, []).append(path)
    return {
        column: paths
        for column, paths in owners.items()
        if len(paths) > 1
    }
