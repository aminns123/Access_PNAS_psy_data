from pathlib import Path
from collections import defaultdict
import pandas as pd


def discover(root=None):
    if root is not None:
        return Path(root).expanduser().resolve()
    # Dataset choice is explicit or made in the browser, never inferred from
    # a convenient archive copy in the software checkout.
    return None


def infer_schema(root, sample_rows=200):
    """Suggest structure from bounded samples; never choose scientific x/y axes."""
    root = Path(root).resolve()
    sources, reports, shared = {}, {}, defaultdict(list)
    priority = [('Subject', ('participant_id', 'participant', 'subject_id', 'subject')),
                ('Luminance', ('luminance_cd_m2', 'luminance')),
                ('Condition', ('condition_id', 'condition')),
                ('Spatial frequency', ('spatial_frequency_cpd', 'frequency')),
                ('Staircase', ('staircase_id', 'staircase'))]
    candidates = []
    for index, path in enumerate(sorted(root.rglob('*'))):
        if not path.is_file() or not (path.name.endswith('.csv') or path.name.endswith('.csv.gz')):
            continue
        if not path.resolve().is_relative_to(root):
            continue
        relative = path.relative_to(root).as_posix()
        if any(part.startswith('.') for part in path.relative_to(root).parts):
            continue
        try:
            frame = pd.read_csv(path, nrows=sample_rows)
        except (ValueError, OSError) as exc:
            reports[relative] = {'error': str(exc)}
            continue
        source = f'table_{len(sources)+1}'
        sources[source] = relative
        numeric = frame.select_dtypes(include='number').columns.tolist()
        likely = []
        for name, aliases in priority:
            match = next((col for col in aliases if col in frame), None)
            if match:
                likely.append({'name': name, 'column': match, 'source': source})
        # A single source avoids silently inventing joins between tables.
        if likely:
            candidates.append(likely)
        reports[relative] = {'columns': frame.columns.tolist(), 'numeric_candidates': numeric,
                             'categorical_candidates': [col for col in frame if frame[col].nunique() <= 30],
                             'sample_rows': len(frame)}
        for column in frame.columns:
            shared[column].append(relative)
    hierarchy = max(candidates, key=len, default=[])
    dictionary = []
    dictionary_path = root / 'data_dictionary.csv'
    if dictionary_path.is_file():
        dictionary = pd.read_csv(dictionary_path, nrows=1000).fillna('').to_dict('records')
    return {'dataset': {'name': root.name, 'adapter': 'csv'}, 'sources': sources,
            'hierarchy': hierarchy, 'plots': {},
            'detection': {'confidence': 'tentative; human review required',
                          'notes': 'Hierarchy inferred by column names from one table; no scientific axes or cross-table joins inferred. Samples may miss categories. Edit before use.',
                          'tables': reports, 'shared_columns': {key: val for key, val in shared.items() if len(val) > 1},
                          'dictionary_sample': dictionary}}
