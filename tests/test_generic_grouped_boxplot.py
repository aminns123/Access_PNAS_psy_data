import numpy as np
import pandas as pd
import pytest

from psyview.plotting.axes import padded_limits
from psyview.plotting.boxplots import grouped_box_plot


def test_grouped_box_plot_uses_repository_labels_and_reference_limits():
    frame = pd.DataFrame({
        'kind': [
            'control', 'control', 'control', 'control',
            'stimulus', 'stimulus', 'stimulus', 'stimulus',
        ],
        'threshold': [
            0.02, 0.03, 0.04, 0.05,
            0.03, 0.04, 0.05, 0.06,
        ],
        'included': [True] * 8,
    })
    reference = [0.005, 0.01, 0.02, 0.04, 0.08, 0.16]

    spec = grouped_box_plot(
        frame,
        category_column='kind',
        value_column='threshold',
        included_column='included',
        title='test',
        xlabel='Condition',
        ylabel='Threshold',
        yscale='log',
        reference_values=reference,
    )

    assert spec.xticks == [
        (1.0, 'control'),
        (2.0, 'stimulus'),
    ]
    assert spec.ylim == pytest.approx(
        padded_limits(reference, 'log')
    )
    assert spec.metadata['Box-plot groups']['control']['mean'] == pytest.approx(
        np.mean([0.02, 0.03, 0.04, 0.05])
    )
    assert spec.metadata['Box-plot groups']['stimulus']['median'] == pytest.approx(
        0.045
    )


def test_same_helper_handles_single_repository_category():
    frame = pd.DataFrame({
        'kind': ['flanker'] * 4,
        'threshold': [0.02, 0.03, 0.04, 0.05],
        'included': [True] * 4,
    })

    spec = grouped_box_plot(
        frame,
        category_column='kind',
        value_column='threshold',
        included_column='included',
        title='test',
        xlabel='Experiment',
        ylabel='Threshold',
        yscale='log',
        reference_values=[0.01, 0.02, 0.05, 0.1],
    )

    assert spec.xticks == [(1.0, 'flanker')]
    assert spec.xlim == (0.45, 1.55)
