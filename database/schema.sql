--database/schema.sql

CREATE TABLE variants (
    variant_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    clickability_test_id        CHAR(24) NOT NULL,
    headline                    TEXT NOT NULL,
    lede                        TEXT,
    excerpt                     TEXT,
    eyecatcher_id               char(24),
    impressions                 INTEGER NOT NULL CHECK (impressions >= 0),
    clicks                      INTEGER NOT NULL CHECK (clicks >= 0 AND clicks <= impressions),
    significance                REAL NOT NULL CHECK (significance BETWEEN 0 AND 100),
    winner                      BOOLEAN NOT NULL,
    first_place                 BOOLEAN NOT NULL,
    test_week                   INTEGER NOT NULL,
    ctr                         AS (CAST (clicks AS REAL) / NULLIF (impressions, 0)) VIRTUAL
);

CREATE TABLE audit_results (
    clickability_test_id  CHAR(24) PRIMARY KEY REFERENCES variants(clickability_test_id),
    winner_ctr             REAL NOT NULL,
    runner_up_ctr           REAL NOT NULL,
    observed_diff            REAL NOT NULL,
    ci_low                    REAL NOT NULL,
    ci_high                    REAL NOT NULL,
    significant                BOOLEAN NOT NULL,
    verdict                    TEXT NOT NULL,
    n_resamples                 INTEGER NOT NULL
);

CREATE INDEX idx_variants_test_id ON variants (clickability_test_id);
CREATE INDEX idx_variants_winner ON variants(winner);

CREATE VIEW experiment_summary AS 
SELECT
    clickability_test_id,
    COUNT(*)                AS variant_count,
    SUM(winner)             AS winner_sum,
    SUM(winner) != 1        AS winner_count_anomaly,
    MIN(test_week)          AS test_week
FROM variants
GROUP BY clickability_test_id;