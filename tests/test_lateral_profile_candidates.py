def test_all_lateral_conditions_retain_profiles(lateral_adapter):
    conditions = lateral_adapter.table('conditions')
    profiles = lateral_adapter.table('profiles')

    expected = set(
        conditions.condition_id.astype(str)
    )
    observed = set(
        profiles.condition_id.astype(str)
    )

    assert observed == expected

    counts = (
        profiles
        .groupby('condition_id')
        .size()
        .to_dict()
    )

    for row in conditions.itertuples():
        assert (
            counts[row.condition_id]
            == row.profile_positions
        )


def test_p01_200_profile_is_present(lateral_adapter):
    frame = lateral_adapter.select(
        'profiles',
        {
            'participant_id': 'P01',
            'luminance_label_cd_m2': 200,
        },
    )

    assert not frame.empty
    assert (
        frame.exclusion_candidate.nunique()
        == 1
    )
    assert (
        frame.exclusion_candidate.iloc[0]
        == 'recorded_exclusion_list'
    )
