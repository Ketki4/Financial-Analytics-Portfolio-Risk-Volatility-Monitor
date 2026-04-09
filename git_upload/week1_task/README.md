# Week 1 - Data Integrity Validation

## Included Files
- week1_data_integrity.py
- week1_data_integrity_report.md
- week1_flagged_rows.csv

## Purpose
This package validates:
- Date and price field integrity
- Duplicate and sort consistency
- Split and dividend coverage checks (against market reference)
- Return and derived metric consistency

## Run
```bash
python week1_data_integrity.py --input ../asian_paints_sorted.xlsx --ticker ASIANPAINT.NS --output-dir .
```

## Notes
- Generated report in this folder is based on the current dataset snapshot.
- If you run again, files in this folder will be refreshed.
