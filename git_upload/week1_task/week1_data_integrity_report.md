# Week 1 - Data Integrity Validation Report

Validation Status: FAIL_WITH_FLAGS
Rows: 3687
Date Range: 2010-03-05 to 2025-03-06
Ticker used for action reference: ASIANPAINT.NS

## Structural Checks
- Invalid Date rows: 0
- Invalid Adj Close rows: 0
- Duplicate Date rows: 0
- Date sorted ascending: True

## Consistency Checks
- Return mismatch rows above tolerance (1e-06): 0
- Best fit for Average: expanding_mean (MAE=0.000735, points=3685)
- Best fit for Volatility: expanding_std_ddof1 (MAE=0.001872, points=3685)

## Corporate Actions Coverage
- Split events from market reference: 1
- Dividend events from market reference: 31
- Split events missing +/-3 day coverage: 0
- Dividend events missing +/-3 day coverage: 0

## Anomaly Checks
- Extreme return days (|log return| > 0.20): 0

## Issues
- Volatility column differs from best candidate (expanding_std_ddof1) with MAE=0.001872.