"""
Streamlit app: browse the bootstrap audit results.

Run with:  streamlit run app.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path("database/upworthy.db")


@st.cache_data
def load_summary(db_path: str = str(DB_PATH)) -> pd.DataFrame:
    """One row per verdict category, with count and percentage."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        "SELECT verdict, COUNT(*) as count FROM audit_results GROUP BY verdict",
        conn,
    )
    conn.close()
    df["pct"] = df["count"] / df["count"].sum() * 100
    return df


@st.cache_data
def load_experiment_list(db_path: str = str(DB_PATH)) -> pd.DataFrame:
    """
    One row per audited experiment, with the winner's headline
    joined in 
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        """
        SELECT a.clickability_test_id, v.headline, a.verdict
        FROM audit_results a
        JOIN variants v
            ON v.clickability_test_id = a.clickability_test_id
            AND v.winner = 1
        ORDER BY a.clickability_test_id
        """,
        conn,
    )
    conn.close()
    return df


@st.cache_data
def load_experiment_detail(test_id: str, db_path: str = str(DB_PATH)) -> dict:
    """Everything needed for the detail view of one experiment:
    winner + runner-up headlines, CTRs, CI, verdict, and what kind
    of variation this test actually was (headline / image / excerpt) --
    """
    conn = sqlite3.connect(db_path)

    audit_row = conn.execute(
        """
        SELECT winner_ctr, runner_up_ctr, observed_diff,
               ci_low, ci_high, significant, verdict, n_resamples
        FROM audit_results WHERE clickability_test_id = ?
        """,
        (test_id,),
    ).fetchone()

    winner = conn.execute(
        "SELECT headline, eyecatcher_id, excerpt FROM variants "
        "WHERE clickability_test_id = ? AND winner = 1",
        (test_id,),
    ).fetchone()
    winner_headline, winner_eyecatcher, winner_excerpt = winner

    non_winners = conn.execute(
        "SELECT headline, eyecatcher_id, excerpt, clicks, impressions "
        "FROM variants WHERE clickability_test_id = ? AND winner = 0",
        (test_id,),
    ).fetchall()
    conn.close()

    ru_headline, ru_eyecatcher, ru_excerpt, _, _ = max(
        non_winners, key=lambda r: r[3] / r[4]
    )

    if winner_headline != ru_headline:
        variation_type = "Headline test"
    elif winner_eyecatcher != ru_eyecatcher:
        variation_type = "Image/thumbnail test (headline unchanged)"
    elif winner_excerpt != ru_excerpt:
        variation_type = "Excerpt test (headline & image unchanged)"
    else:
        variation_type = "No observable variation between winner and runner-up"

    return {
        "winner_headline": winner_headline,
        "runner_up_headline": ru_headline,
        "variation_type": variation_type,
        "winner_ctr": audit_row[0],
        "runner_up_ctr": audit_row[1],
        "observed_diff": audit_row[2],
        "ci_low": audit_row[3],
        "ci_high": audit_row[4],
        "significant": bool(audit_row[5]),
        "verdict": audit_row[6],
        "n_resamples": audit_row[7],
    }


# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------

st.set_page_config(page_title="Upworthy A/B Test Audit", layout="wide")

st.title("Did Upworthy's A/B test winners actually win?")
st.caption(
    "Independently re-testing 1,150 historical Upworthy headline "
    "experiments with bootstrap resampling, to see whether the "
    "declared 'winner' actually beats its strongest competing "
    "variant -- or whether the difference could just be noise."
)

summary = load_summary()
total = int(summary["count"].sum())

VERDICT_COLORS = {
    "HOLDS UP": "#2ecc71",
    "DOES NOT HOLD UP": "#95a5a6",
    "RED FLAG": "#e74c3c",
}


def short_label(verdict: str) -> str:
    """First couple words of the verdict string, for compact display."""
    return verdict.split("(")[0].strip()


def color_for(verdict: str) -> str:
    for key, color in VERDICT_COLORS.items():
        if verdict.startswith(key):
            return color
    return "#95a5a6"


st.subheader("Summary")
cols = st.columns(len(summary))
for col, (_, row) in zip(cols, summary.iterrows()):
    with col:
        st.metric(
            label=short_label(row["verdict"]),
            value=f"{row['count']} ({row['pct']:.1f}%)",
        )

st.caption(
    f"Based on {total} experiments with exactly one declared winner "
    f"-- 3,723 additional experiments (0 or 2+ declared winners) were "
    f"excluded from the audit as ambiguous."
)

fig_summary = go.Figure(
    go.Bar(
        x=summary["count"],
        y=[short_label(v) for v in summary["verdict"]],
        orientation="h",
        marker_color=[color_for(v) for v in summary["verdict"]],
        text=[f"{p:.1f}%" for p in summary["pct"]],
        textposition="auto",
    )
)
fig_summary.update_layout(
    height=250, margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="Number of experiments",
)
st.plotly_chart(fig_summary, width='stretch')

st.divider()

# --- Selector ---
st.subheader("Browse individual experiments")

exp_list = load_experiment_list()

filter_choice = st.selectbox(
    "Filter by verdict",
    options=["All"] + sorted(exp_list["verdict"].apply(short_label).unique()),
)

filtered = exp_list if filter_choice == "All" else exp_list[
    exp_list["verdict"].apply(short_label) == filter_choice
]

filtered = filtered.copy()
filtered["label"] = (
    filtered["verdict"].apply(short_label) + " | " + filtered["headline"]
)

chosen_label = st.selectbox("Experiment", options=filtered["label"])
chosen_test_id = filtered.loc[
    filtered["label"] == chosen_label, "clickability_test_id"
].iloc[0]

# --- Detail view ---
detail = load_experiment_detail(chosen_test_id)

badge_color = color_for(detail["verdict"])
st.markdown(
    f"### <span style='color:{badge_color}'>{detail['verdict']}</span>",
    unsafe_allow_html=True,
)
st.caption(detail["variation_type"])

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Winner**")
    st.write(detail["winner_headline"])
    st.metric("CTR", f"{detail['winner_ctr']:.4f}")
with col_b:
    st.markdown("**Runner-up (strongest competing variant)**")
    st.write(detail["runner_up_headline"])
    st.metric("CTR", f"{detail['runner_up_ctr']:.4f}")

fig_ci = go.Figure()
fig_ci.add_trace(go.Scatter(
    x=[detail["ci_low"], detail["ci_high"]],
    y=["CTR difference", "CTR difference"],
    mode="lines",
    line=dict(color=badge_color, width=4),
    showlegend=False,
))
fig_ci.add_trace(go.Scatter(
    x=[detail["observed_diff"]],
    y=["CTR difference"],
    mode="markers",
    marker=dict(color=badge_color, size=14),
    showlegend=False,
))
fig_ci.add_vline(x=0, line_dash="dash", line_color="grey")
fig_ci.update_layout(
    height=200,
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis_title="Winner CTR − Runner-up CTR (95% bootstrap CI)",
    yaxis=dict(showticklabels=False),
)
st.plotly_chart(fig_ci, width='stretch')

st.caption(
    f"Observed difference: {detail['observed_diff']:+.4f}   "
    f"95% CI: [{detail['ci_low']:+.4f}, {detail['ci_high']:+.4f}]   "
    f"({detail['n_resamples']} bootstrap resamples)"
)