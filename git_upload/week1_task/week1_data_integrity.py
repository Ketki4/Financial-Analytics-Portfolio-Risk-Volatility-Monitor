from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class SeriesFitResult:
    name: str
    mae: float
    compared_points: int


def load_dataset(file_path: Path) -> pd.DataFrame:
    df = pd.read_excel(file_path)
    if "Date" not in df.columns:
        raise ValueError("Expected a 'Date' column in the dataset.")
    if "Adj Close" not in df.columns:
        raise ValueError("Expected an 'Adj Close' column in the dataset.")

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Adj Close"] = (
        df["Adj Close"].astype(str).str.replace(",", "", regex=False).str.strip()
    )
    df["Adj Close"] = pd.to_numeric(df["Adj Close"], errors="coerce")
    return df


def fit_series(
    target: pd.Series, candidates: dict[str, Callable[[], pd.Series]]
) -> SeriesFitResult:
    best = SeriesFitResult(name="unavailable", mae=np.inf, compared_points=0)
    for name, fn in candidates.items():
        pred = fn()
        aligned = pd.concat([target, pred], axis=1, keys=["target", "pred"]).dropna()
        if aligned.empty:
            continue
        mae = float((aligned["target"] - aligned["pred"]).abs().mean())
        if mae < best.mae:
            best = SeriesFitResult(name=name, mae=mae, compared_points=len(aligned))
    return best


def fetch_actions(ticker: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    tk = yf.Ticker(ticker)
    hist = tk.history(
        start=(start_date - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        end=(end_date + pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        auto_adjust=False,
        actions=True,
    )
    if hist.empty or "Dividends" not in hist.columns or "Stock Splits" not in hist.columns:
        return pd.DataFrame(columns=["Dividends", "Stock Splits"])

    out = hist[["Dividends", "Stock Splits"]].copy()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out


def nearest_date_distance_days(dates: pd.Series, point: pd.Timestamp) -> int:
    deltas = (dates - point).abs().dt.days
    return int(deltas.min()) if len(deltas) else 10**9


def build_report(
    df: pd.DataFrame,
    ticker: str,
    tol_return: float,
    tol_rolling: float,
) -> tuple[str, pd.DataFrame]:
    issues: list[str] = []

    invalid_dates = int(df["Date"].isna().sum())
    invalid_prices = int(df["Adj Close"].isna().sum())
    duplicate_dates = int(df["Date"].duplicated().sum())
    is_sorted = bool(df["Date"].is_monotonic_increasing)

    if invalid_dates:
        issues.append(f"Found {invalid_dates} invalid date rows.")
    if invalid_prices:
        issues.append(f"Found {invalid_prices} invalid Adj Close rows after numeric coercion.")
    if duplicate_dates:
        issues.append(f"Found {duplicate_dates} duplicate Date values.")
    if not is_sorted:
        issues.append("Date column is not sorted in ascending order.")

    work = df.sort_values("Date").reset_index(drop=True)
    work["recomputed_log_return"] = np.log(work["Adj Close"] / work["Adj Close"].shift(1))

    if "Log Return" in work.columns:
        ret_diff = (work["Log Return"] - work["recomputed_log_return"]).abs()
        bad_return = int((ret_diff > tol_return).sum())
    else:
        ret_diff = pd.Series(np.nan, index=work.index)
        bad_return = 0
        issues.append("Log Return column missing; skipped direct return consistency check.")

    avg_fit = SeriesFitResult("missing", np.nan, 0)
    vol_fit = SeriesFitResult("missing", np.nan, 0)

    if "Average" in work.columns:
        avg_candidates = {
            "expanding_mean": lambda: work["recomputed_log_return"].expanding(min_periods=2).mean(),
            **{
                f"rolling_mean_{w}": (
                    lambda w=w: work["recomputed_log_return"].rolling(window=w, min_periods=2).mean()
                )
                for w in (5, 10, 20, 30)
            },
        }
        avg_fit = fit_series(work["Average"], avg_candidates)
        if avg_fit.compared_points and avg_fit.mae > tol_rolling:
            issues.append(
                f"Average column differs from best candidate ({avg_fit.name}) with MAE={avg_fit.mae:.6f}."
            )

    if "Volatility" in work.columns:
        vol_candidates: dict[str, Callable[[], pd.Series]] = {
            "expanding_std_ddof0": lambda: work["recomputed_log_return"].expanding(min_periods=2).std(ddof=0),
            "expanding_std_ddof1": lambda: work["recomputed_log_return"].expanding(min_periods=2).std(ddof=1),
        }
        for w in (5, 10, 20, 30):
            vol_candidates[f"rolling_std_{w}_ddof0"] = (
                lambda w=w: work["recomputed_log_return"].rolling(window=w, min_periods=2).std(ddof=0)
            )
            vol_candidates[f"rolling_std_{w}_ddof1"] = (
                lambda w=w: work["recomputed_log_return"].rolling(window=w, min_periods=2).std(ddof=1)
            )

        vol_fit = fit_series(work["Volatility"], vol_candidates)
        if vol_fit.compared_points and vol_fit.mae > tol_rolling:
            issues.append(
                f"Volatility column differs from best candidate ({vol_fit.name}) with MAE={vol_fit.mae:.6f}."
            )

    start_date = work["Date"].min()
    end_date = work["Date"].max()
    actions = fetch_actions(ticker, start_date, end_date)

    split_dates = actions.index[actions["Stock Splits"] > 0]
    div_dates = actions.index[actions["Dividends"] > 0]

    missing_split_coverage = 0
    for d in split_dates:
        if nearest_date_distance_days(work["Date"], d) > 3:
            missing_split_coverage += 1

    missing_div_coverage = 0
    for d in div_dates:
        if nearest_date_distance_days(work["Date"], d) > 3:
            missing_div_coverage += 1

    if missing_split_coverage:
        issues.append(
            f"{missing_split_coverage} split action date(s) not represented within +/-3 days in dataset."
        )
    if missing_div_coverage:
        issues.append(
            f"{missing_div_coverage} dividend action date(s) not represented within +/-3 days in dataset."
        )

    work["abs_recomputed_log_return"] = work["recomputed_log_return"].abs()
    extreme_return_threshold = 0.20
    work["is_extreme_return"] = work["abs_recomputed_log_return"] > extreme_return_threshold
    extreme_count = int(work["is_extreme_return"].sum())
    if extreme_count:
        issues.append(
            f"Detected {extreme_count} extreme return days above |log return| > {extreme_return_threshold:.2f}."
        )

    work["return_diff_abs"] = ret_diff
    work["flag_return_mismatch"] = work["return_diff_abs"] > tol_return

    flagged = work.loc[
        work["flag_return_mismatch"] | work["is_extreme_return"],
        [
            "Date",
            "Adj Close",
            "Log Return",
            "recomputed_log_return",
            "return_diff_abs",
            "is_extreme_return",
            "Average",
            "Volatility",
        ],
    ].copy()

    status = "PASS" if not issues else "FAIL_WITH_FLAGS"
    summary_lines = [
        "# Week 1 - Data Integrity Validation Report",
        "",
        f"Validation Status: {status}",
        f"Rows: {len(work)}",
        f"Date Range: {start_date.date()} to {end_date.date()}",
        f"Ticker used for action reference: {ticker}",
        "",
        "## Structural Checks",
        f"- Invalid Date rows: {invalid_dates}",
        f"- Invalid Adj Close rows: {invalid_prices}",
        f"- Duplicate Date rows: {duplicate_dates}",
        f"- Date sorted ascending: {is_sorted}",
        "",
        "## Consistency Checks",
        f"- Return mismatch rows above tolerance ({tol_return}): {bad_return}",
        f"- Best fit for Average: {avg_fit.name} (MAE={avg_fit.mae:.6f}, points={avg_fit.compared_points})",
        f"- Best fit for Volatility: {vol_fit.name} (MAE={vol_fit.mae:.6f}, points={vol_fit.compared_points})",
        "",
        "## Corporate Actions Coverage",
        f"- Split events from market reference: {len(split_dates)}",
        f"- Dividend events from market reference: {len(div_dates)}",
        f"- Split events missing +/-3 day coverage: {missing_split_coverage}",
        f"- Dividend events missing +/-3 day coverage: {missing_div_coverage}",
        "",
        "## Anomaly Checks",
        f"- Extreme return days (|log return| > {extreme_return_threshold:.2f}): {extreme_count}",
        "",
        "## Issues",
    ]

    if issues:
        summary_lines.extend([f"- {x}" for x in issues])
    else:
        summary_lines.append("- No critical integrity issues detected.")

    return "\n".join(summary_lines), flagged


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 1 data integrity validation")
    parser.add_argument("--input", required=True, help="Path to input Excel file")
    parser.add_argument("--ticker", default="ASIANPAINT.NS", help="Ticker for split/dividend reference")
    parser.add_argument(
        "--output-dir", default="reports", help="Directory where report artifacts are saved"
    )
    parser.add_argument("--return-tol", type=float, default=1e-6, help="Tolerance for return mismatch")
    parser.add_argument(
        "--rolling-tol", type=float, default=1e-3, help="Tolerance for average/volatility fit MAE"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(input_path)
    report_text, flagged = build_report(
        df=df, ticker=args.ticker, tol_return=args.return_tol, tol_rolling=args.rolling_tol
    )

    report_path = output_dir / "week1_data_integrity_report.md"
    flags_path = output_dir / "week1_flagged_rows.csv"

    report_path.write_text(report_text, encoding="utf-8")
    flagged.to_csv(flags_path, index=False)

    print(f"Week 1 report saved: {report_path}")
    print(f"Week 1 flagged rows saved: {flags_path}")


if __name__ == "__main__":
    main()
