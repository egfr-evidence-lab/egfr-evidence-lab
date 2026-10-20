"""실험 간 병합 판단. 결측 일치나 상관계수 하나로 동질성을 승인하지 않는다."""

import math

import numpy as np


def wilson_interval(successes, total):
    if total == 0:
        return None, None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def compare_protocols(left, right, critical_fields):
    missing, different = [], []
    for field in critical_fields:
        a, b = left.get(field), right.get(field)
        if a is None or b is None or a == "" or b == "":
            missing.append(field)
        elif a != b:
            different.append(field)
    return {"protocols_complete_and_equal": not missing and not different,
            "missing_fields": ";".join(missing), "different_fields": ";".join(different)}


def agreement_metrics(left, right, policy):
    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if left.shape != right.shape or left.ndim != 1 or not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("같은 길이의 유한한 일대일 공통 구조 라벨이 필요합니다.")
    n = len(left)
    result = {"shared_structures": n, "median_signed_bias": None, "median_absolute_difference": None,
              "fraction_within_0_3": None, "fraction_within_0_5": None, "fraction_over_1": None,
              "agreement_wilson_95_lower": None, "agreement_wilson_95_upper": None,
              "bias_bootstrap_95_lower": None, "bias_bootstrap_95_upper": None,
              "statistical_gate_passed": False}
    if n == 0:
        return result
    differences = left - right
    absolute = np.abs(differences)
    cutoff = policy["agreement_absolute_delta_pIC50"]
    successes = int(np.count_nonzero(absolute <= cutoff))
    lower, upper = wilson_interval(successes, n)
    result.update(median_signed_bias=float(np.median(differences)), median_absolute_difference=float(np.median(absolute)),
                  fraction_within_0_3=float(np.mean(absolute <= 0.3)), fraction_within_0_5=successes / n,
                  fraction_over_1=float(np.mean(absolute > 1)), agreement_wilson_95_lower=lower,
                  agreement_wilson_95_upper=upper)
    if n < policy["minimum_shared_unique_structures"]:
        return result
    rng = np.random.default_rng(policy["seed"])
    draws = rng.choice(differences, size=(policy["bootstrap_resamples"], n), replace=True)
    lo, hi = np.quantile(np.median(draws, axis=1), [0.025, 0.975])
    result.update(bias_bootstrap_95_lower=float(lo), bias_bootstrap_95_upper=float(hi))
    result["statistical_gate_passed"] = bool(
        successes / n >= policy["agreement_fraction_minimum"]
        and lower >= policy["agreement_wilson_95_lower_minimum"]
        and max(abs(lo), abs(hi)) <= policy["median_bias_bootstrap_95_absolute_bound"]
        and result["fraction_over_1"] <= policy["fraction_absolute_delta_over_1_maximum"])
    return result
