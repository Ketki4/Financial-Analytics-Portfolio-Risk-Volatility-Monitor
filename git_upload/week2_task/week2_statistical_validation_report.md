# Week 2 - Statistical Validation Report

Observations (returns): 3686
Significance level (alpha): 0.05

## Descriptive Statistics
- Mean return: 0.00069357
- Std deviation: 0.01581885
- Skewness: -0.1791
- Excess kurtosis: 4.8068

## Hypothesis Tests
- Jarque-Bera: stat=3556.3298, p-value=0
- D'Agostino K^2: stat=417.8488, p-value=1.84197e-91
- ADF: stat=-60.1749, p-value=0, lags=0, nobs=3685
- Ljung-Box (lag 10): stat=10.0529, p-value=0.435868
- ARCH LM (lag 10): stat=238.9793, p-value=1.1222e-45

## Risk Sanity Checks
- Parametric VaR(95%) daily threshold: -0.025326
- Realized breach rate (< VaR95): 4.2051%
- Outliers (|z| > 3): 50

## Volatility Regime Summary
- Low regime days: 1210
- Medium regime days: 1209
- High regime days: 1247

## Volatility Column Consistency
- Correlation with recomputed 21-day vol: -0.0303
- MAE vs recomputed 21-day vol: 0.004167

## Findings
- Return distribution departs from normality at chosen significance level.
- Returns appear stationary by ADF test.
- No strong autocorrelation signal up to lag 10.
- ARCH effect detected, suggesting volatility clustering.