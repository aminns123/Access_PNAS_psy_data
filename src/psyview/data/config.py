from .base import DatasetError


def validate_config(config):
    if not isinstance(config, dict):
        raise DatasetError(
            'YAML must contain a mapping with dataset, sources and hierarchy.'
        )

    dataset = config.get('dataset')
    if (
        not isinstance(dataset, dict)
        or not isinstance(
            dataset.get('name'),
            str,
        )
    ):
        raise DatasetError(
            'YAML dataset.name must be a string.'
        )

    if dataset.get(
        'adapter',
        'csv',
    ) not in (
        'csv',
        'pnas',
        'lateral',
    ):
        raise DatasetError(
            'Unknown dataset adapter; supported adapters are csv, pnas and lateral.'
        )

    if (
        not isinstance(
            config.get('sources'),
            dict,
        )
        or not config['sources']
    ):
        raise DatasetError(
            'YAML sources must map source names to relative CSV/CSV.GZ paths.'
        )

    hierarchy = config.get('hierarchy')
    if (
        not isinstance(hierarchy, list)
        or not hierarchy
    ):
        raise DatasetError(
            'No hierarchy configured. Review detected columns and add hierarchy entries.'
        )

    seen = set()

    for level in hierarchy:
        if (
            not isinstance(level, dict)
            or not all(
                isinstance(
                    level.get(key),
                    str,
                )
                for key in (
                    'name',
                    'column',
                    'source',
                )
            )
        ):
            raise DatasetError(
                'Each hierarchy entry needs string name, column and source fields.'
            )

        allowed = {
            'name',
            'column',
            'source',
            'units',
        }
        unsupported = set(level) - allowed

        if unsupported:
            raise DatasetError(
                f'Unsupported hierarchy fields: {unsupported}'
            )

        if (
            level['source']
            not in config['sources']
            or level['column'] in seen
        ):
            raise DatasetError(
                'Hierarchy has an unknown source or duplicate column.'
            )

        seen.add(
            level['column']
        )

    for source, path in config[
        'sources'
    ].items():
        if not isinstance(path, str):
            raise DatasetError(
                f'Source {source} needs a relative path string.'
            )

    axis_policy = config.get(
        'axis_policy',
        {},
    )

    if not isinstance(
        axis_policy,
        dict,
    ):
        raise DatasetError(
            'axis_policy must be a mapping when provided.'
        )

    allowed_axis_fields = {
        'scale',
        'limits',
        'rounding',
        'preferred_min',
        'preferred_max',
    }

    for level_column, level_policy in axis_policy.items():
        if level_column not in seen:
            raise DatasetError(
                f'axis_policy references unknown hierarchy column: {level_column}'
            )

        if not isinstance(
            level_policy,
            dict,
        ):
            raise DatasetError(
                f'axis_policy.{level_column} must be a mapping.'
            )

        for axis, policy in level_policy.items():
            if axis not in ('x', 'y'):
                raise DatasetError(
                    f'axis_policy.{level_column} supports only x and y.'
                )

            if not isinstance(
                policy,
                dict,
            ):
                raise DatasetError(
                    f'axis_policy.{level_column}.{axis} must be a mapping.'
                )

            unsupported = (
                set(policy)
                - allowed_axis_fields
            )
            if unsupported:
                raise DatasetError(
                    f'Unsupported axis-policy fields at '
                    f'{level_column}.{axis}: {unsupported}'
                )

            scale = policy.get(
                'scale',
                'auto',
            )
            if scale not in (
                'auto',
                'linear',
                'log',
            ):
                raise DatasetError(
                    f'Invalid scale at {level_column}.{axis}: {scale}'
                )

            limits = policy.get(
                'limits',
                'row',
            )
            if limits not in (
                'row',
                'data',
            ):
                raise DatasetError(
                    f'Invalid limits policy at {level_column}.{axis}: {limits}'
                )

            rounding = policy.get(
                'rounding',
                'auto',
            )
            if rounding not in (
                'auto',
                'nice',
                'decades',
            ):
                raise DatasetError(
                    f'Invalid rounding policy at {level_column}.{axis}: {rounding}'
                )

            for name in (
                'preferred_min',
                'preferred_max',
            ):
                value = policy.get(name)
                if (
                    value is not None
                    and not isinstance(
                        value,
                        (int, float),
                    )
                ):
                    raise DatasetError(
                        f'{level_column}.{axis}.{name} must be numeric.'
                    )

            if (
                scale == 'log'
                and policy.get(
                    'preferred_min'
                ) is not None
                and float(
                    policy['preferred_min']
                ) <= 0
            ):
                raise DatasetError(
                    f'{level_column}.{axis}.preferred_min must be > 0 for log axes.'
                )

    return config
