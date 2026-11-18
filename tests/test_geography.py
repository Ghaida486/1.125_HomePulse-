import numpy as np
import pandas as pd
import pytest
from homepulse.config import REPLICATES
from homepulse.geography import geographic_summary, electricity_map


def records():
    # Unequal state weights distinguish pooled region estimates from mean-of-means.
    df = pd.DataFrame({"state_postal": ["MA", "NY", "TX"], "REGIONC": ["Northeast", "Northeast", "South"],
                       "TYPEHUQ": ["Detached house", "Detached house", "Apartment"],
                       "KWH": [1000., 5000., 10000.], "NWEIGHT": [1., 9., 10.]})
    return pd.concat([df, pd.DataFrame({k: df.NWEIGHT for k in REPLICATES})], axis=1)


def test_region_pooling_and_national_reference():
    summary, tiles, national = geographic_summary(records(), "Region")
    assert summary.set_index("group").loc["Northeast", "mean_kwh"] == pytest.approx(4600)
    assert national == pytest.approx(7300)
    assert tiles.set_index("state_postal").loc["MA", "mean_kwh"] == 4600
    assert tiles.set_index("state_postal").loc["NY", "mean_kwh"] == 4600
    assert tiles.set_index("state_postal").loc["CA", "mean_kwh"] is not None
    assert np.isnan(tiles.set_index("state_postal").loc["CA", "mean_kwh"])


def test_state_filter_keeps_missing_states_uncoloured_and_recomputes_benchmark():
    summary, tiles, national = geographic_summary(records(), "State", "Detached house")
    assert set(summary.group) == {"MA", "NY"}
    assert national == 4600
    fig = electricity_map(tiles, "Difference from U.S. average (%)")
    assert set(fig.data[0].locations) == {"MA", "NY"}
    assert fig.layout.coloraxis.cmin == -fig.layout.coloraxis.cmax
    vals = dict(zip(fig.data[0].locations, fig.data[0].z))
    assert vals["MA"] == pytest.approx(100 * (1000 / 4600 - 1))
    assert summary.low_support.all()
    assert geographic_summary(records(), "State", "Missing type")[2] is None
