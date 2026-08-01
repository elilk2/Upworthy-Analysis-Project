# 🧪 Upworthy A/B Test Re-Evaluator: Non-Parametric Bootstrapping Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit App](https://static.streamlit.io/badge_svg/build.svg)](https://your-app-url.streamlit.app)

## Executive Summary
Digital publishers frequently make high-stakes editorial decisions based on A/B testing frameworks that rely on standard parametric assumptions (e.g., asymptotic Z-tests). This project builds a non-parametric bootstrapping experimentation engine in Python and SQL, re-evaluating 22,666 headline/teaser package variations across 4,873 A/B tests from the Upworthy Research Archive.

## Key Findings
* **False Positive Identification:** Non-parametric bootstrapping revealed that X% of headline variations flagged as "winners" under standard Z-tests had 95% confidence intervals that spanned across zero, indicating insufficient statistical evidence.
* **Skewness Mitigation:** BCa (Bias-Corrected and Accelerated) resampling properly adjusted interval bounds for low-CTR headline variations where standard asymptotic errors under-represented variance.

## Tech Stack
* **Language:** Python 3.10+
* **Database & Data Pipeline:** SQLite, Pandas, NumPy
* **Statistical Methods:** Non-Parametric Binomial Bootstrapping, BCa Confidence Intervals, Parametric Z-Testing
* **Visualization & Frontend:** Streamlit, Plotly, Seaborn
* **Testing & Quality:** Pytest, Flake8

## Architecture & Workflow
1. **ETL & SQL Storage:** Raw experiment logs are normalized into an indexed SQLite database.
2. **Resampling Engine:** Vectorized NumPy implementation resamples B=10,000 iterations to generate empirical difference distributions.
3. **Interactive Dashboard:** Deployed Streamlit web application enabling real-time scenario modeling and custom experiment analysis.

## How to Run Locally
```bash
git clone [https://github.com/yourusername/upworthy-bootstrap-engine.git](https://github.com/yourusername/upworthy-bootstrap-engine.git)
cd upworthy-bootstrap-engine
pip install -r requirements.txt
python src/etl.py
streamlit run app.py