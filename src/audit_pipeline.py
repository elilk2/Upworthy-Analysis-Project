""" 
Runs the bootstrap engine on every eligible experiment (every experiment with 1 declared winner)
Posts the results to database/upworthy_db's audit_results table 

Run with python src/audit_pipeline.py
"""

import sqlite3
import time
from collections import Counter
from pathlib import Path

from bootstrap_engine import DB_PATH, audit_experiment, verdict

N_RESAMPLES = 2_000

REPORT_PATH = Path("reports/audit_summary.txt")

def get_eligible_test_ids(db_path : Path = DB_PATH) -> list[str]:
    """
    Every experiment with exactly one declared winner: NOT flagged by winner_count_anomaly
    """

    conn = sqlite3.connect(db_path)
    ids = [
        row[0] for row in conn.execute(
            "SELECT clickability_test_id FROM experiment_summary "
            "WHERE winner_count_anomaly = 0"
        )
    ]
    conn.close()
    return ids

def get_already_audited_ids(db_path : Path = DB_PATH) -> set[str]:
    """
    Checks for ids in previous runs that are already present in audit_results
    """

    conn = sqlite3.connect(db_path)
    ids = {
        row[0] for row in conn.execute(
            "SELECT clickability_test_id FROM  audit_results"
        )
    }
    conn.close()
    return ids

def persist_one(test_id : str, result, db_path : Path = DB_PATH) -> None:
    """
    Prevents lost work if interrupted
    Writes a single result immediately
    """

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO audit_results (
            clickability_test_id, winner_ctr, runner_up_ctr,
            observed_diff, ci_low, ci_high, significant,
            verdict, n_resamples
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            test_id, result.ctr_a, result.ctr_b, result.observed_diff,
            result.ci_low, result.ci_high, result.significant,
            verdict(result), result.n_resamples,
        ),
    )
    conn.commit()
    conn.close()

def run_audit(
    db_path : Path = DB_PATH,
    n_resamples : int = N_RESAMPLES,
    max_experiments : int | None = None,
    ) -> tuple[int, list[tuple[str,str]] ]:
    """
    Run audit_experiment() across every eligible test_id not already in audit_results, persisting each result immediately

    Includes per-experiment error handling

    Returns (count_processed_this_run, errors)
    """

    all_ids = get_eligible_test_ids(db_path)
    done_ids = get_already_audited_ids(db_path)
    remaining = [t for t in all_ids if t not in done_ids]

    if max_experiments is not None:
        remaining = remaining[:max_experiments]

    print(f"{len(done_ids)} already audited, {len(remaining) } remaining"
            f"this run (n_resamples = {n_resamples})..."
        )

    errors = []
    start = time.time()

    for i, test_id in enumerate(remaining, 1):
        try:
            result = audit_experiment(
                test_id, db_path=db_path, n_resamples=n_resamples
            )
            if result is not None:
                persist_one(test_id, result, db_path=db_path)

        except Exception as e:
            errors.append((test_id, str(e)))

        if i % 50 == 0 or i == len(remaining):
            elapsed = time.time() - start
            print(f" {i} / {len(remaining)} processed this run "
                    f"({elapsed: .0f}s elapsed)", flush = True
                  )

    print(f"\nthis run: {len(remaining) -len(errors)} succeeded, "
        f"{len(errors)} errors")
        
    if errors:
        print("first few errors:") 
        for test_id, msg in errors[:5]:
            print(f" {test_id}: {msg}")

    return len(remaining) - len(errors), errors

def summarize(db_path : Path = DB_PATH) -> dict:
    """
    Computes the three-way headline breakdown
    Reads directly from audit_results
    """

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT verdict FROM audit_results").fetchall()
    conn.close()

    total = len(rows)
    counts = Counter(r[0] for r in rows)

    summary = {}
    for label, count in counts.items():
        summary[label] = {
            "count" : count,
            "pct" : count / total * 100 if total else 0.0,
        }
    summary["_total"] = total
    return summary

def sanity_check(db_path : Path = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    red_flag_count = conn.execute(
        "SELECT COUNT(*) FROM audit_results WHERE verdict LIKE 'RED FLAG%' " 
    ).fetchone()[0]
    conn.close()

    print(f"\n--- sanity checks ---")
    print(f"red flag count: {red_flag_count} "
          f"(must be <= 290, the known raw-CTR-reversal ceiling from Phase 5)")
    if red_flag_count > 290:
        print("  ⚠ WARNING: exceeds known ceiling -- investigate before trusting results")
    else:
        print("  ✓ within expected bound")


def write_report(summary : dict, path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents = True, exist_ok= True)
    total = summary.pop("_total") 
    lines = [
        f"Bootstrap audit summary -- {total} eligible experiments",
        f"(experiments with exactly one declared winner; "
        f"anomaly tests excluded)"
    ]
    for label, stats in summary.items():
        lines.append(f"{label}: {stats['count']} ({stats['pct']:.1f}% ) ")
    path.write_text("\n".join(lines) + "\n")
    print(f"\nsummary written to {path}")


def main(max_experiments: int | None = None):
    processed, errors = run_audit(max_experiments=max_experiments)
    print(f"\n{processed} experiments processed in this run "
          f"({len(errors)} errors)")
 
    summary = summarize()
 
    print("\n=== Headline results (cumulative, all runs) ===")
    for label, stats in summary.items():
        if label == "_total":
            continue
        print(f"{label}: {stats['count']} ({stats['pct']:.1f}%)")
 
    sanity_check()
    write_report(summary)
 
 
if __name__ == "__main__":
    import sys
 
    max_experiments = None
    if len(sys.argv) > 1 and sys.argv[1] == "--max":
        max_experiments = int(sys.argv[2])
 
    main(max_experiments=max_experiments)