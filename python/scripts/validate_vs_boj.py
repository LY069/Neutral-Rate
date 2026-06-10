"""
Validate this toolkit's r* estimates against the Bank of Japan's published
Chart 3 (BOJ Review 2026-E-4 supplementary data, bundled with attribution at
data/boj/boj_chart3_estimates.csv).

    python scripts/validate_vs_boj.py

Reads python/output/r_star_estimates.csv (run `python -m neutralrate.run_all`
first - with --refresh on real FRED data for a meaningful comparison) and
reports, per method: latest level vs BoJ, mean gap and correlation over the
overlapping sample, and quarter-on-quarter volatility vs BoJ.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
OURS_CSV = os.path.join(HERE, "..", "output", "r_star_estimates.csv")
BOJ_CSV = os.path.join(HERE, "..", "..", "data", "boj", "boj_chart3_estimates.csv")

# our column name -> BoJ column name
PAIRS = {
    "HLW (2023)": "HLW2023",
    "DSGE (Okazaki-Sudo 2018)": "OkazakiSudo2018",
    "Natural Yield Curve (Imakubo et al. 2015)": "Imakubo2015",
    "Natural Yield Curve (Nakajima et al. 2023)": "Nakajima2023",
    "Macro-finance (Goy-Iwasaki 2024)": "GoyIwasaki2024",
    "VAR common trends (Del Negro et al. 2017)": "DelNegro2017",
}


def main():
    if not os.path.exists(OURS_CSV):
        sys.exit("No output found - run `python -m neutralrate.run_all` first.")
    ours = pd.read_csv(OURS_CSV, index_col=0, parse_dates=True)
    boj = pd.read_csv(BOJ_CSV)
    boj.index = pd.PeriodIndex(boj["quarter"], freq="Q").to_timestamp()
    boj = boj.drop(columns=["quarter"]).apply(pd.to_numeric, errors="coerce")

    print(f"{'method':<42} {'ours':>7} {'BoJ':>7} {'gap':>6} "
          f"{'corr':>6} {'qoq_ours':>9} {'qoq_BoJ':>8}")
    gaps = []
    for our_col, boj_col in PAIRS.items():
        if our_col not in ours.columns:
            print(f"{our_col:<42} (missing from output)")
            continue
        o = ours[our_col].dropna()
        b = boj[boj_col].dropna()
        idx = o.index.intersection(b.index)
        o_l, b_l = o.iloc[-1], b.iloc[-1]
        gap = o_l - b_l
        gaps.append(gap)
        corr = o.loc[idx].corr(b.loc[idx]) if len(idx) > 8 else np.nan
        print(f"{our_col:<42} {o_l:>+7.2f} {b_l:>+7.2f} {gap:>+6.2f} "
              f"{corr:>6.2f} {o.diff().std():>9.3f} {b.diff().std():>8.3f}")

    print(f"\nmean |latest gap| = {np.mean(np.abs(gaps)):.2f} pp   "
          f"(BoJ latest quarter: {boj.dropna(how='all').index[-1].date()})")
    print("NB: gaps are only meaningful when our output was estimated on REAL "
          "FRED data (run_all --refresh), not the bundled synthetic sample.")


if __name__ == "__main__":
    main()
