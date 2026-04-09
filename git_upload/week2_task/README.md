# Week 2 - Statistical Validation of Results

## Included Files
- week2_statistical_validation.py
- week2_statistical_validation_report.md
- week2_high_volatility_periods.csv

## Purpose
This package validates statistical behavior of returns:
- Distribution tests (Jarque-Bera, D'Agostino)
- Stationarity check (ADF)
- Autocorrelation check (Ljung-Box)
- Volatility clustering check (ARCH)
- Risk sanity checks (VaR breach rate, outliers, volatility regimes)

## Run
```bash
python week2_statistical_validation.py --input ../asian_paints_sorted.xlsx --output-dir . --alpha 0.05
```

## Notes
- Generated report in this folder is based on the current dataset snapshot.
- If you run again, files in this folder will be refreshed.
