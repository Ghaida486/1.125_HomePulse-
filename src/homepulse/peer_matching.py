"""Survey-weighted profile matching with an inspectable geography fallback.

This is a benchmarking rule, not a household prediction model. It publishes
only group summaries; household records stay in the local database.
"""
import numpy as np


class ProfileSupportError(ValueError):
    """A valid request for which every geography has insufficient support."""

    def __init__(self, attempts):
        super().__init__("Too few comparable survey homes for this house type and size. "
                         "Try a better-supported profile; no estimate has been calculated.")
        self.attempts = attempts


def effective_sample_size(weights):
    """Kish effective n: penalize samples dominated by a few survey weights."""
    weights = np.asarray(weights, dtype=float)
    if not len(weights):
        return 0.0
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Survey weights must be finite and positive.")
    # Normalize first to avoid overflow without changing the statistic.
    scaled = weights / weights.max()
    return float(scaled.sum() ** 2 / np.square(scaled).sum())


class SurveyProfileMatcher:
    """Validate once and reuse aggregate summaries across many requests.

    Each scope's denominator includes all eligible homes in that geography.
    Its numerator includes only the requested joint home-type / size group.
    The first scope meeting BOTH support thresholds is selected.
    """

    def __init__(self, profiles, min_sample=50, min_effective_sample=30):
        required = {"state", "region", "home_type", "size_band", "weight", "kwh"}
        if not required.issubset(profiles.columns) or profiles.empty:
            raise ValueError("Survey profiles are empty or missing required columns.")
        if min_sample < 1 or not 1 <= min_effective_sample <= min_sample:
            raise ValueError("Invalid survey support thresholds.")
        if profiles[list(required)].isna().any().any():
            raise ValueError("Survey matching columns cannot contain missing values.")
        numbers = profiles[["weight", "kwh"]].to_numpy(dtype=float)
        if not np.isfinite(numbers).all() or (numbers <= 0).any():
            raise ValueError("Survey weights and annual kWh must be finite and positive.")
        if "survey_id" in profiles and profiles.survey_id.duplicated().any():
            raise ValueError("Duplicate survey households would distort matching support.")
        self.policy = {"min_sample": int(min_sample),
                       "min_effective_sample": float(min_effective_sample)}
        self._profiles = profiles.copy(deep=True)
        self._summaries = {}

    def _summarize(self, level, key):
        """Cache summaries, never mutable input frames or a request's audit trail."""
        cache_key = (level, key)
        if cache_key not in self._summaries:
            reference = self._profiles
            if level == "State":
                reference = reference.loc[reference.state == key]
            elif level == "Region":
                reference = reference.loc[reference.region == key]
            reference_mean = (float(np.average(reference.kwh, weights=reference.weight))
                              if len(reference) else None)
            groups = {}
            for group_key, peers in reference.groupby(["home_type", "size_band"], observed=True):
                groups[group_key] = {
                    "sample_n": len(peers),
                    "effective_n": effective_sample_size(peers.weight),
                    "profile_mean_annual_kwh": float(np.average(peers.kwh, weights=peers.weight)),
                }
            self._summaries[cache_key] = (reference_mean, groups)
        return self._summaries[cache_key]

    def match(self, *, state, state_name, region, home_type, size_band):
        attempts = []
        scopes = [("State", state, state_name), ("Region", region, region),
                  ("United States", "US", "United States")]
        for level, key, geography in scopes:
            reference_mean, groups = self._summarize(level, key)
            group = groups.get((home_type, size_band), {"sample_n": 0, "effective_n": 0.0})
            reasons = []
            if group["sample_n"] < self.policy["min_sample"]:
                reasons.append("insufficient_count")
            if group["effective_n"] < self.policy["min_effective_sample"]:
                reasons.append("insufficient_effective_sample")
            attempts.append({"level": level, "geography": geography,
                             "sample_n": group["sample_n"], "effective_n": group["effective_n"],
                             "decision": "rejected" if reasons else "selected", "reasons": reasons})
            if reasons:
                continue
            return {**group, "factor": group["profile_mean_annual_kwh"] / reference_mean,
                    "reference_mean_annual_kwh": reference_mean, "level": level,
                    "geography": geography, "size_band": size_band,
                    "support_policy": dict(self.policy), "matching_attempts": attempts}
        raise ProfileSupportError(attempts)
