import pandas as pd

from psyview.data.detector import infer_schema
from psyview.data.registry import detect_dataset, open_dataset


def test_unknown_structured_dataset_opens_generic(
    tmp_path,
):
    root = tmp_path / 'unknown experiment'
    root.mkdir()

    pd.DataFrame({
        'subject': ['A', 'A', 'B', 'B'],
        'condition': ['x', 'y', 'x', 'y'],
        'trial': [1, 1, 1, 1],
        'measurement': [0.2, 0.4, 0.3, 0.5],
    }).to_csv(
        root / 'measurements.csv',
        index=False,
    )

    info = detect_dataset(root)
    assert info is not None
    assert info.adapter == 'generic'

    config = infer_schema(root)
    assert [
        item['column']
        for item in config['hierarchy']
    ] == [
        'subject',
        'condition',
    ]
    assert config['plots'] == {}

    adapter = open_dataset(root)
    assert adapter.get_values(
        0,
        {},
    ) == [
        'A',
        'B',
    ]
    assert adapter.get_values(
        1,
        {'subject': 'A'},
    ) == [
        'x',
        'y',
    ]

    spec = adapter.get_plot(
        0,
        {'subject': 'A'},
    )
    assert spec.series == []
    assert (
        'No plot configured'
        in spec.title
    )


def test_parent_folder_is_not_misclassified(
    tmp_path,
):
    child = tmp_path / 'child'
    child.mkdir()

    pd.DataFrame({
        'subject': ['A'],
        'condition': ['x'],
    }).to_csv(
        child / 'measurements.csv',
        index=False,
    )

    assert detect_dataset(tmp_path) is None
