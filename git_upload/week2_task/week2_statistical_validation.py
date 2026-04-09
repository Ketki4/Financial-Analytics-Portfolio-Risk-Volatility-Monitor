from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.tsa.stattools import adfuller


def load_returns(file_path: Path) -> pd.DataFrame:
    df = pd.read_excel(file_path).copy()
    if "Date" not in df.columns or "Adj Close" not in df.columns:
        raise ValueError("Dataset must contain 'Date' and 'Adj Close' columns.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Adj Close"] = (
        df["Adj Close"].astype(str).str.replace(",", "", regex=False).str.strip()
    )
    df["Adj Close"] = pd.to_numeric(df["Adj Close"], errors="coerce")
    df = df.dropna(subset=["Date", "Adj Close"]).sort_values("Date").reset_index(drop=True)

    df["recomputed_log_return"] = np.log(df["Adj Close"] / df["Adj Close"].shift(1))
    returns = df["recomputed_log_return"].dropna().copy()

    if len(returns) < 50:
        raise ValueError("Need at least 50 return observations for statistical validation.")

    return df


def classify_vol_regime(rolling_vol: pd.Series) -> pd.Series:
    q1 = rolling_vol.quantile(0.33)
    q2 = rolling_vol.quantile(0.66)

    def _label(v: float) -> str:
        if pd.isna(v):
            return "unknown"
        if v <= q1:
            return "low"
        if v <= q2:
            return "medium"
        return "high"

    return rolling_vol.apply(_label)


def build_week2_report(df: pd.DataFrame, alpha: float) -> tuple[str, pd.DataFrame]:
    ret = df["recomputed_log_return"].dropna()

    mean_ret = float(ret.mean())
    std_ret = float(ret.std(ddof=1))
    skew_ret = float(stats.skew(ret, bias=False))
    kurt_ret = float(stats.kurtosis(ret, fisher=True, bias=False))

    jb_stat, jb_p = stats.jarque_bera(ret)
    nt_stat, nt_p = stats.normaltest(ret)

    adf_stat, adf_p, adf_lags, adf_nobs, _, _ = adfuller(ret, autolag="AIC")

    lb = acorr_ljungbox(ret, lags=[10], return_df=True)
    lb_stat = float(lb["lb_stat"].iloc[0])
    lb_p = float(lb["lb_pvalue"].iloc[0])

    arch_stat, arch_p, _, _ = het_arch(ret, nlags=10)

    z = np.abs(stats.zscore(ret, nan_policy="omit"))
    outlier_mask = z > 3
    outlier_count = int(np.nansum(outlier_mask))

    rolling_window = 21
    df = df.copy()
    df["rolling_vol_21"] = df["recomputed_log_return"].rolling(rolling_window).std(ddof=1)
    df["rolling_vol_21_annualized"] = df["rolling_vol_21"] * np.sqrt(252)
    df["vol_regime"] = classify_vol_regime(df["rolling_vol_21_annualized"])

    regime_counts = (
        df["vol_regime"].value_counts().reindex(["low", "medium", "high", "unknown"]).fillna(0)
    )

    var_95 = float(stats.norm.ppf(0.05, loc=mean_ret, scale=std_ret))
    realized_breach_rate = float((ret < var_95).mean())

    consistency_corr = np.nan
    consistency_mae = np.nan
    if "Volatility" in df.columns:
        aligned = df[["Volatility", "rolling_vol_21"]].dropna()
        if not aligned.empty:
            consistency_corr = float(aligned.corr().iloc[0, 1])
            consistency_mae = float((aligned["Volatility"] - aligned["rolling_vol_21"]).abs().mean())

    findings = []
    if jb_p < alpha or nt_p < alpha:
        findings.append("Return distribution departs from normality at chosen significance level.")
    if adf_p < alpha:
        findings.append("Returns appear stationary by ADF test.")
    else:
        findings.append("ADF does not reject unit-root null; inspect data generation process.")
    if lb_p < alpha:
        findings.append("Ljung-Box indicates autocorrelation up to lag 10.")
    else:
        findings.append("No strong autocorrelation signal up to lag 10.")
    if arch_p < alpha:
        findings.append("ARCH effect detected, suggesting volatility clustering.")
    else:
        findings.append("No strong ARCH effect at selected lag depth.")

    report_lines = [
        "# Week 2 - Statistical Validation Report",
        "",
        f"Observations (returns): {len(ret)}",
        f"Significance level (alpha): {alpha}",
        "",
        "## Descriptive Statistics",
        f"- Mean return: {mean_ret:.8f}",
        f"- Std deviation: {std_ret:.8f}",
        f"- Skewness: {skew_ret:.4f}",
        f"- Excess kurtosis: {kurt_ret:.4f}",
        "",
        "## Hypothesis Tests",
        f"- Jarque-Bera: stat={jb_stat:.4f}, p-value={jb_p:.6g}",
        f"- D'Agostino K^2: stat={nt_stat:.4f}, p-value={nt_p:.6g}",
        f"- ADF: stat={adf_stat:.4f}, p-value={adf_p:.6g}, lags={adf_lags}, nobs={adf_nobs}",
        f"- Ljung-Box (lag 10): stat={lb_stat:.4f}, p-value={lb_p:.6g}",
        f"- ARCH LM (lag 10): stat={arch_stat:.4f}, p-value={arch_p:.6g}",
        "",
        "## Risk Sanity Checks",
        f"- Parametric VaR(95%) daily threshold: {var_95:.6f}",
        f"- Realized breach rate (< VaR95): {realized_breach_rate:.4%}",
        f"- Outliers (|z| > 3): {outlier_count}",
        "",
        "## Volatility Regime Summary",
        f"- Low regime days: {int(regime_counts['low'])}",
        f"- Medium regime days: {int(regime_counts['medium'])}",
        f"- High regime days: {int(regime_counts['high'])}",
        "",
        "## Volatility Column Consistency",
        f"- Correlation with recomputed 21-day vol: {consistency_corr:.4f}",
        f"- MAE vs recomputed 21-day vol: {consistency_mae:.6f}",
        "",
        "## Findings",
    ]
    report_lines.extend([f"- {item}" for item in findings])

    flagged = df.loc[
        (df["rolling_vol_21_annualized"].notna()) & (df["vol_regime"] == "high"),
        ["Date", "Adj Close", "recomputed_log_return", "rolling_vol_21", "rolling_vol_21_annualized", "vol_regime"],
    ].copy()

    return "\n".join(report_lines), flagged


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 2 statistical validation")
    parser.add_argument("--input", required=True, help="Path to input Excel file")
    parser.add_argument("--output-dir", default="reports", help="Directory for output files")
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance level for tests")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_returns(input_path)
    report_text, flagged = build_week2_report(df=df, alpha=args.alpha)

    report_path = output_dir / "week2_statistical_validation_report.md"
    flags_path = output_dir / "week2_high_volatility_periods.csv"

    report_path.write_text(report_text, encoding="utf-8")
    flagged.to_csv(flags_path, index=False)

    print(f"Week 2 report saved: {report_path}")
    print(f"Week 2 flagged periods saved: {flags_path}")


if __name__ == "__main__":
    main()
