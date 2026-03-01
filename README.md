# Retention Cohort Analyzer

Analyze user retention from raw event data. Generates cohort tables, churn curves, and LTV projections — the metrics that matter for growth.

## Why this exists

Retention is the only metric that matters. If you can't retain users, nothing else works — not acquisition, not monetization, not virality. But most teams either (a) don't measure it properly or (b) rely on a BI tool they don't control.

This tool takes raw event data and produces the cohort analysis that every growth PM needs.

## Quick start

```python
from cohort_analyzer import CohortAnalyzer

analyzer = CohortAnalyzer()

# Load events: user_id, event_name, timestamp
analyzer.load_csv("events.csv")

# Generate cohort retention table
table = analyzer.retention_table(
    cohort_by="signup_month",   # Group users by signup month
    activity="any_event",       # What counts as "active"
    periods=12,                 # Track for 12 periods
)

analyzer.print_table(table)
```

**Output:**

```
Cohort Retention Table (Monthly)

Cohort     Users   M0     M1     M2     M3     M4     M5     M6
─────────────────────────────────────────────────────────────────
2025-07    1,842   100%   68%    52%    44%    41%    39%    38%
2025-08    2,103   100%   71%    55%    47%    43%    40%
2025-09    1,956   100%   65%    49%    42%    39%
2025-10    2,311   100%   72%    58%    48%
2025-11    2,089   100%   69%    53%
2025-12    2,445   100%   74%
2026-01    2,678   100%

Average              100%   70%    53%    45%    41%    40%    38%
```

## Features

- **Cohort retention tables** — Classic M0-M12 retention grids
- **Churn curves** — Visualize where you lose users
- **LTV projection** — Estimate lifetime value from retention curves
- **Segment comparison** — Compare retention by plan, channel, or any attribute
- **Week-over-week trends** — Are recent cohorts retaining better?
- **Export** — Markdown, CSV, JSON

## LTV projection

```python
ltv = analyzer.project_ltv(
    retention_table=table,
    avg_revenue_per_user_per_month=29.99,
    discount_rate=0.10,  # Annual discount rate
    projection_months=36,
)
```

**Output:**

```
LTV Projection
══════════════════════════════════
  ARPU/month:         $29.99
  Avg retention M12:  38%
  Projected LTV:      $287.40
  Payback period:     4.2 months
══════════════════════════════════
```

## Segment comparison

```python
# Compare retention by acquisition channel
segments = analyzer.compare_segments(
    segment_column="acquisition_channel",
    segments=["organic", "paid_search", "referral"],
)
```

```
Retention by Acquisition Channel (M6)

Channel        Users    M1     M3     M6     LTV
───────────────────────────────────────────────────
organic        4,201    72%    48%    41%    $312
referral       1,803    78%    55%    49%    $367
paid_search    3,442    61%    35%    28%    $198
```

## Project structure

```
retention-cohort-analyzer/
├── cohort_analyzer.py     # Core library
├── examples/
│   ├── sample_events.csv  # Sample dataset
│   └── analyze.py         # Example usage
├── tests/
│   └── test_cohort.py
├── requirements.txt
└── README.md
```

## The retention curve every PM should know

```
100% ┐
     │\
     │ \
     │  \
     │   \___
     │       \___________
     │                   \_______________ ← Flattening = product-market fit
     │
  0% └──────────────────────────────────
     M0  M1  M2  M3  M4  M5  M6  ...
```

**If the curve flattens:** You have PMF. Optimize the early drop-off.
**If the curve hits zero:** You don't have PMF. Fix the product, not the funnel.

## License

MIT
