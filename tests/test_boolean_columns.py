import pandas as pd

from psyview.data.csv_adapter import _coerce_boolean_columns


def test_boolean_coercion_does_not_treat_included_counts_as_flags(tmp_path):
    path = tmp_path / 'condition_summary.csv'
    frame = pd.DataFrame({
        'included_in_thesis_main_isf': ['True', 'False'],
        'included_staircases': [125, 93],
        'excluded_staircases': [3, 3],
    })

    result = _coerce_boolean_columns(frame.copy(), path)

    assert result.included_in_thesis_main_isf.tolist() == [True, False]
    assert result.included_staircases.tolist() == [125, 93]
    assert result.excluded_staircases.tolist() == [3, 3]
