from .base import DatasetError


def validate_config(config):
    if not isinstance(config, dict):
        raise DatasetError('YAML must contain a mapping with dataset, sources and hierarchy.')
    dataset = config.get('dataset')
    if not isinstance(dataset, dict) or not isinstance(dataset.get('name'), str):
        raise DatasetError('YAML dataset.name must be a string.')
    if dataset.get('adapter', 'csv') not in ('csv', 'pnas', 'lateral'):
        raise DatasetError('Unknown dataset adapter; supported adapters are csv, pnas and lateral.')
    if not isinstance(config.get('sources'), dict) or not config['sources']:
        raise DatasetError('YAML sources must map source names to relative CSV/CSV.GZ paths.')
    hierarchy = config.get('hierarchy')
    if not isinstance(hierarchy, list) or not hierarchy:
        raise DatasetError('No hierarchy configured. Review detected columns and add hierarchy entries.')
    seen = set()
    for level in hierarchy:
        if not isinstance(level, dict) or not all(
            isinstance(level.get(key), str) for key in ('name', 'column', 'source')
        ):
            raise DatasetError('Each hierarchy entry needs string name, column and source fields.')
        if set(level) - {'name', 'column', 'source', 'units'}:
            raise DatasetError(
                f'Unsupported hierarchy fields: '
                f'{set(level) - {"name", "column", "source", "units"}}'
            )
        if level['source'] not in config['sources'] or level['column'] in seen:
            raise DatasetError('Hierarchy has an unknown source or duplicate column.')
        seen.add(level['column'])
    for source, path in config['sources'].items():
        if not isinstance(path, str):
            raise DatasetError(f'Source {source} needs a relative path string.')
    return config
