"""Generic descriptive grouped box plots built from PlotSpec primitives."""
from __future__ import annotations

import numpy as np

from ..models import PlotSpec, Series
from .axes import finite, padded_limits


def _categories(frame, category_column, category_order=None):
    if category_order is not None:
        available = set(frame[category_column].dropna().tolist())
        return [
            value
            for value in category_order
            if value in available
        ]
    # Preserve the source/repository order instead of inventing semantics.
    return (
        frame[category_column]
        .dropna()
        .drop_duplicates()
        .tolist()
    )


def grouped_box_plot(
    frame,
    *,
    category_column,
    value_column,
    title,
    xlabel,
    ylabel,
    included_column=None,
    yscale='linear',
    reference_values=None,
    category_order=None,
    notes_prefix='',
    metadata=None,
    mean_label='Arithmetic mean',
):
    """Render distributions for arbitrary repository-defined categories.

    Box = Q1-Q3, centre line = median, whiskers = observed min-max.
    The individual observations and arithmetic mean are retained explicitly.

    If reference_values are supplied, their padded range becomes the y-axis
    range. This lets a summary plot use the same scale as its underlying raw
    trajectories without teaching the renderer what those trajectories mean.
    """
    if category_column not in frame:
        raise ValueError(f'Missing category column: {category_column}')
    if value_column not in frame:
        raise ValueError(f'Missing value column: {value_column}')
    if included_column is not None and included_column not in frame:
        raise ValueError(f'Missing inclusion column: {included_column}')

    categories = _categories(
        frame,
        category_column,
        category_order,
    )
    if not categories:
        raise ValueError('No categories are available for the box plot.')

    effective_scale = yscale
    ylim = None

    if reference_values is not None:
        reference = [
            float(value)
            for value in reference_values
            if finite(value)
        ]
        if reference:
            if (
                effective_scale == 'log'
                and any(value <= 0 for value in reference)
            ):
                effective_scale = 'linear'

            ylim = padded_limits(
                reference,
                effective_scale,
            )

    spec = PlotSpec(
        title,
        xlabel,
        ylabel,
        yscale=effective_scale,
        notes=(
            notes_prefix
            + 'Descriptive box plot: box = Q1-Q3; centre line = median; '
              'whiskers = observed minimum-maximum. Individual observations '
              'are shown as points and the arithmetic mean as a diamond. '
              'This is not a confidence interval.'
        ),
        metadata=dict(metadata or {}),
        xlim=(0.45, len(categories) + 0.55),
        ylim=ylim,
        xticks=[
            (float(index), str(category))
            for index, category in enumerate(categories, start=1)
        ],
    )

    first_whisker = True
    first_box = True
    first_median = True
    first_points = True
    first_mean = True
    first_excluded = True
    summary = {}

    for index, category in enumerate(categories, start=1):
        subset = frame.loc[
            frame[category_column].eq(category)
        ]

        all_values = subset[value_column].to_numpy(dtype=float)
        finite_mask = np.isfinite(all_values)

        if effective_scale == 'log':
            finite_mask &= all_values > 0

        if included_column is None:
            included_mask = np.ones(len(subset), dtype=bool)
        else:
            included_mask = (
                subset[included_column]
                .astype(bool)
                .to_numpy()
            )

        included = all_values[
            finite_mask & included_mask
        ]
        excluded = all_values[
            finite_mask & ~included_mask
        ]

        if len(included) == 0:
            continue

        q1, median, q3 = np.percentile(
            included,
            [25, 50, 75],
            method='linear',
        )
        minimum = float(np.min(included))
        maximum = float(np.max(included))
        mean = float(np.mean(included))

        x = float(index)
        box_half = 0.18
        cap_half = 0.08

        spec.series.append(
            Series(
                [x, x],
                [minimum, maximum],
                'Observed min-max' if first_whisker else '',
                color='blue',
            )
        )
        first_whisker = False

        for y_value in (minimum, maximum):
            spec.series.append(
                Series(
                    [x - cap_half, x + cap_half],
                    [y_value, y_value],
                    '',
                    color='blue',
                )
            )

        spec.series.extend([
            Series(
                [x - box_half, x - box_half],
                [float(q1), float(q3)],
                'Q1-Q3 box' if first_box else '',
                color='cyan',
            ),
            Series(
                [x + box_half, x + box_half],
                [float(q1), float(q3)],
                '',
                color='cyan',
            ),
            Series(
                [x - box_half, x + box_half],
                [float(q1), float(q1)],
                '',
                color='cyan',
            ),
            Series(
                [x - box_half, x + box_half],
                [float(q3), float(q3)],
                '',
                color='cyan',
            ),
        ])
        first_box = False

        spec.series.append(
            Series(
                [x - box_half, x + box_half],
                [float(median), float(median)],
                'Median' if first_median else '',
                color='white',
            )
        )
        first_median = False

        x_points = (
            [x]
            if len(included) == 1
            else np.linspace(
                x - 0.08,
                x + 0.08,
                len(included),
            ).tolist()
        )

        spec.series.append(
            Series(
                x_points,
                included.tolist(),
                'Included values' if first_points else '',
                'scatter',
                'cyan',
                marker='●',
            )
        )
        first_points = False

        spec.series.append(
            Series(
                [x],
                [mean],
                mean_label if first_mean else '',
                'scatter',
                'yellow',
                marker='◆',
            )
        )
        first_mean = False

        if len(excluded):
            x_excluded = (
                [x + 0.13]
                if len(excluded) == 1
                else np.linspace(
                    x + 0.10,
                    x + 0.18,
                    len(excluded),
                ).tolist()
            )

            spec.series.append(
                Series(
                    x_excluded,
                    excluded.tolist(),
                    'Excluded values' if first_excluded else '',
                    'scatter',
                    'red',
                    marker='×',
                )
            )
            first_excluded = False

        summary[str(category)] = {
            'n_included': int(len(included)),
            'n_excluded': int(len(excluded)),
            'minimum': minimum,
            'q1': float(q1),
            'median': float(median),
            'q3': float(q3),
            'maximum': maximum,
            'mean': mean,
        }

    if not summary:
        raise ValueError(
            'No finite included values are available for any category.'
        )

    spec.metadata['Box-plot groups'] = summary

    if ylim is not None:
        spec.metadata['Y-axis reference'] = (
            'limits inherited from the underlying raw trajectory values'
        )

    return spec
