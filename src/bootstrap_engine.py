import sqlite3
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy import stats

DB_PATH = Path("database/upworthy.db")

@dataclass 
class BootstrapResult:
    ctr_a: float
    ctr_b: float
    observed_diff: float #ctr_a - ctr_b
    ci_low: float
    ci_high: float 
    significant: bool # True if CI excludes 0
    n_resamples: int

def bootstrap_ctr_diff(
    clicks_a: int,
    impressions_a: int,
    clicks_b: int,
    impressions_b: int,
    n_resamples: int = 10_000,
    confidence_level: float = 0.95,
    random_state: int | None = None,
) -> BootstrapResult:

    arr_a = np.zeros(impressions_a, dtype = np.int8)
    arr_a[:clicks_a] = 1

    arr_b = np.zeros(impressions_b, dtype = np.int8)
    arr_b[:clicks_b] = 1

    def diff_stat(a, b, axis = -1):
        return np.mean(a, axis=axis) - np.mean(b, axis = axis)

 
    res = stats.bootstrap(
        (arr_a, arr_b),
        statistic = diff_stat,
        n_resamples = n_resamples,
        confidence_level= confidence_level,
        method = "BCa",
        random_state = random_state,
        vectorized=True,
    )

    ci_low, ci_high = res.confidence_interval

    return BootstrapResult(
        ctr_a = clicks_a / impressions_a,
        ctr_b = clicks_b / impressions_b,
        observed_diff= diff_stat(arr_a, arr_b),
        ci_low = ci_low,
        ci_high = ci_high,
        significant=(ci_low > 0 or ci_high < 0),
        n_resamples= n_resamples
    )

def audit_experiment(
    test_id: str,
    db_path: Path = DB_PATH,
    n_resamples: int = 10_000,
    random_state: int | None = None
) -> BootstrapResult | None:

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT winner_count_anomaly FROM experiment_summary "
        "WHERE clickability_test_id = ?",
        (test_id,),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"unknown clickability_test_id: {test_id}")
    if row[0]:
        conn.close()
        return None

    cur.execute(
        "SELECT clicks, impressions, winner FROM variants "
        "WHERE clickability_test_id = ?",
        (test_id,),
    )
    rows = cur.fetchall()
    conn.close()

    winner_row = next(r for r in rows if r[2] == 1)
    non_winner_rows = [r for r in rows if r[2] == 0]

    runner_up_row = max(
        non_winner_rows, key = lambda r: r[0] / r[1] #highest CTR
    )

    clicks_w, impressions_w, _ = winner_row
    clicks_r, impressions_r, _ = runner_up_row

    return bootstrap_ctr_diff(
        clicks_a = clicks_w,
        impressions_a = impressions_w,
        clicks_b = clicks_r,
        impressions_b = impressions_r,
        n_resamples = n_resamples,
        random_state = random_state,
    )

def verdict(result : BootstrapResult) -> str:

    if not result.significant:
        return "Does not hold up (not statistically significant)"
    elif result.observed_diff > 0:
        return "Holds up (winner significantly beats runner-up)"
    else:
        return "Red flag (winner significantly worse than runner-up)"


if __name__ == "__main__":
    import sys

    if (len(sys.argv) < 2):
        print("usage: python src/bootstrap_engine.py <clickability_test_id>")
        sys.exit(1)

    test_id = sys.argv[1]
    result = audit_experiment(test_id)

    if result is None:
        print(f"{test_id}: skipped - no single declared winner"
              f"(winner_count_anomaly)")
    else:
        print(f"=== Bootstrap audit: {test_id} ===")
        print(f"winner CTR:     {result.ctr_a:.4f}")
        print(f"runner-up CTR:  {result.ctr_b:.4f}")
        print(f"observed diff:  {result.observed_diff:+.4f}")
        print(f"95% CI:         [{result.ci_low:+.4f}, {result.ci_high:+.4f}]")
        print(f"verdict:        {verdict(result)}")
