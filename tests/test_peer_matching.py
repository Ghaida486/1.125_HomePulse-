"""Challenge fallback, survey-weight concentration, and data-integrity rules."""
import numpy as np
import pandas as pd
import pytest
from homepulse.peer_matching import SurveyProfileMatcher, ProfileSupportError, effective_sample_size


def homes(n, state='MA', region='Northeast', kind=5, kwh=6000, weight=1):
    return pd.DataFrame({'state': state, 'region': region, 'home_type': kind,
                         'size_band': 'small', 'kwh': kwh, 'weight': weight}, index=range(n))


def match(frame, **kwargs):
    return SurveyProfileMatcher(frame).match(state='MA', state_name='Massachusetts',
                                             region='Northeast', home_type=5, size_band='small', **kwargs)


def test_first_sufficient_geography_and_joint_weighted_factor():
    frame = pd.concat([homes(50), homes(50, kind=2, kwh=12000, weight=2)])
    result = match(frame)
    assert result['level'] == 'State'
    assert result['reference_mean_annual_kwh'] == 10000
    assert result['factor'] == .6
    assert result['sample_n'] == result['effective_n'] == 50
    assert [x['decision'] for x in result['matching_attempts']] == ['selected']


def test_small_state_falls_back_to_region():
    result = match(pd.concat([homes(49), homes(1, state='NY')]))
    assert result['level'] == 'Region'
    assert result['sample_n'] == 50
    assert result['matching_attempts'][0]['reasons'] == ['insufficient_count']


def test_many_records_with_concentrated_weights_fail_effective_n_gate():
    frame = homes(60)
    frame.loc[0, 'weight'] = 1000
    result = match(pd.concat([frame, homes(100, state='NY', weight=100)]))
    first = result['matching_attempts'][0]
    assert first['sample_n'] == 60 and first['effective_n'] < 2
    assert first['reasons'] == ['insufficient_effective_sample']
    assert result['level'] == 'Region'


def test_empty_state_and_region_reach_national_group():
    result = match(homes(50, state='CA', region='West'))
    assert result['level'] == 'United States'
    assert [x['sample_n'] for x in result['matching_attempts']] == [0, 0, 50]


def test_unsupported_profile_returns_all_rejections_not_a_number():
    with pytest.raises(ProfileSupportError) as error:
        match(homes(49))
    assert len(error.value.attempts) == 3
    assert all(x['decision'] == 'rejected' for x in error.value.attempts)


@pytest.mark.parametrize('column,value', [('weight', 0), ('weight', -1), ('weight', np.inf),
                                          ('kwh', np.nan), ('kwh', -1)])
def test_invalid_source_data_is_not_disguised_as_low_support(column, value):
    frame = homes(50).astype({'weight': float, 'kwh': float})
    frame.loc[0, column] = value
    with pytest.raises(ValueError) as error:
        match(frame)
    assert not isinstance(error.value, ProfileSupportError)


def test_duplicate_households_rejected():
    frame = homes(50).assign(survey_id=1)
    with pytest.raises(ValueError, match='Duplicate'):
        match(frame)


def test_effective_n_is_invariant_to_weight_units_and_numerically_stable():
    weights = np.array([1., 2., 3.])
    expected = 36 / 14
    assert effective_sample_size(weights) == pytest.approx(expected)
    assert effective_sample_size(weights * 1e300) == pytest.approx(expected)


def test_snapshot_and_cached_results_are_isolated_from_callers():
    frame = homes(50)
    matcher = SurveyProfileMatcher(frame)
    frame.loc[:, 'weight'] = 0
    request = dict(state='MA', state_name='Massachusetts', region='Northeast', home_type=5, size_band='small')
    first = matcher.match(**request)
    first['matching_attempts'][0]['decision'] = 'tampered'
    first['support_policy']['min_sample'] = 1
    second = matcher.match(**request)
    assert second['matching_attempts'][0]['decision'] == 'selected'
    assert second['support_policy']['min_sample'] == 50
