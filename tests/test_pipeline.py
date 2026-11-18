import numpy as np
import pandas as pd
import pytest
from homepulse.config import FEATURES, CATEGORIES, NUMERIC, REPLICATES
from homepulse.data import clean_records, weighted_comparison, load_data
from homepulse.prediction import validate_profile
from homepulse.training import partition, conformal_radius, make_pipeline


def sample_profile():
    return {**{k: float(v[1]) for k, v in NUMERIC.items()},
            **{k: next(iter(v.values())) for k, v in CATEGORIES.items()}}


def test_predictor_allowlist_cannot_leak_target_or_costs():
    assert len(FEATURES) == len(set(FEATURES))
    assert not any(k.startswith(("KWH", "BTU", "DOL", "NWEIGHT", "Z")) or k == "DOEID" for k in FEATURES)


def test_special_equipment_code_is_not_treated_as_a_number():
    row = {"DOEID": 1, "KWH": 10000., "NWEIGHT": 1000., **{k: 1 for k in REPLICATES}}
    row.update({k: v[1] for k, v in NUMERIC.items()})
    row.update({k: next(iter(v)) for k, v in CATEGORIES.items()})
    row["ACEQUIPM_PUB"] = -2
    row["NUMFRIG"] = -1
    clean = clean_records(pd.DataFrame([row]))
    assert clean.ACEQUIPM_PUB.iloc[0] == "No air conditioning"
    assert pd.isna(clean.NUMFRIG.iloc[0])


def test_partitions_are_disjoint_reproducible_and_complete():
    df = load_data()
    a, b = partition(df), partition(df)
    ids = [set(v.DOEID) for v in a.values()]
    assert sum(map(len, ids)) == len(set.union(*ids)) == len(df)
    assert all(set(a[k].DOEID) == set(b[k].DOEID) for k in a)


def test_survey_weighted_mean_and_replicate_se():
    df = pd.DataFrame({"REGIONC": ["A", "A"], "KWH": [100., 300.], "NWEIGHT": [1., 3.]})
    for c in REPLICATES:
        df[c] = [1., 3.]
    result = weighted_comparison(df, "REGIONC").iloc[0]
    assert result.mean_kwh == 250.
    assert result.standard_error == 0.
    assert result.sample_households == 2


def test_training_imputer_does_not_learn_from_test_inputs():
    df = load_data().iloc[:20].copy()
    df.loc[df.index[0], "TOTSQFT_EN"] = np.nan
    pipeline = make_pipeline(dict(n_estimators=2, max_depth=2, learning_rate=.1))
    pipeline.fit(df[FEATURES], df.KWH)
    learned = pipeline.named_steps["preprocess"].named_transformers_["numeric"].statistics_[0]
    assert learned == df.TOTSQFT_EN.median()
    test = df[FEATURES].iloc[:1].copy()
    test["TOTSQFT_EN"] = 15000.
    pipeline.predict(test)
    assert pipeline.named_steps["preprocess"].named_transformers_["numeric"].statistics_[0] == learned


def test_input_validation_and_finite_sample_interval():
    profile = sample_profile()
    assert validate_profile(profile).shape == (1, len(FEATURES))
    profile["TOTSQFT_EN"] = float("nan")
    with pytest.raises(ValueError):
        validate_profile(profile)
    assert conformal_radius([1, 2, 3, 4], .8) == 4.
