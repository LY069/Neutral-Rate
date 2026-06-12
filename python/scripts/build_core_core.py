"""
Reconstruct BoJ's tax-excluded "core-core" CPI (less fresh food & energy,
excluding consumption-tax effects) from the LONGER Statistics-Bureau raw index,
and evaluate the reconstruction against BoJ's official series.

Why: BoJ's published tax-excluded core-core is short (starts ~2015); the
Statistics Bureau raw index goes back to the 1970s.  We remove the tax effect
ourselves (level-based wedge, config.CONSUMPTION_TAX_LEVEL_EFFECTS) to get a long,
consistent underlying-inflation series for the r* estimation.

Methodology
-----------
A consumption-tax hike is a one-time, permanent proportional jump in the price
LEVEL at its implementation month.  So divide the raw index by a cumulative
multiplicative wedge F(t)=prod(1+p_h/100) over hikes on/before t, then take YoY.

Usage
-----
    # from a Statistics-Bureau core-core INDEX (CSV, e-Stat spec, or FRED id):
    python scripts/build_core_core.py --raw data/cpi/jp_core_core_index_raw.csv
    python scripts/build_core_core.py --raw "estat:STATSDATAID:CDCAT01"

    # optionally evaluate against BoJ's official tax-excluded core-core YoY:
    python scripts/build_core_core.py --raw <raw_index> --boj data/cpi/boj_core_core_excl_tax.csv

Writes the tax-excluded YoY % to data/cpi/jp_core_core_yoy.csv (the path the
toolkit reads).  Because the OUTPUT is already tax-excluded, set
ADJUST_CONSUMPTION_TAX = False in config when using it.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neutralrate import data  # noqa: E402

OUT_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..",
                           "data", "cpi", "jp_core_core_yoy.csv")


def _is_index(s: pd.Series) -> bool:
    """Heuristic: a CPI index sits near 100; a YoY % series is small."""
    return s.dropna().abs().median() > 20


def _yoy(index: pd.Series) -> pd.Series:
    s = index.dropna()
    periods = 12 if (s.index.to_series().diff().median() <= pd.Timedelta(days=40)) else 4
    return 100.0 * np.log(s).diff(periods)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True,
                    help="raw core-core INDEX source (CSV path / estat:... / FRED id)")
    ap.add_argument("--boj", default=None,
                    help="BoJ official tax-excluded core-core (YoY % or index) to evaluate against")
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    raw = data.fetch_any(args.raw).dropna()
    if not _is_index(raw):
        print("WARNING: --raw does not look like an index (values are small). "
              "This tool expects the core-core INDEX (~100), not a YoY series.")
    adj_index = data.tax_excluded_index(raw)
    yoy = _yoy(adj_index).dropna()

    # quick self-check: the de-tax should shrink the YoY jump at each hike window
    raw_yoy = _yoy(raw).dropna()
    print("De-tax effect at hike windows (raw YoY -> tax-excluded YoY):")
    for date, pp in data.CONSUMPTION_TAX_LEVEL_EFFECTS:
        d = pd.Timestamp(date) + pd.offsets.MonthEnd(6)
        if d in raw_yoy.index and d in yoy.index:
            print(f"   {d.date()}:  {raw_yoy.loc[d]:+.2f}  ->  {yoy.loc[d]:+.2f}  "
                  f"(removed ~{raw_yoy.loc[d]-yoy.loc[d]:+.2f}pp, expect ~{pp:+.1f})")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    out = yoy.copy(); out.index.name = "date"
    out.to_frame("value").to_csv(args.out)
    print(f"\nWrote tax-excluded core-core YoY ({len(out)} obs, "
          f"{out.index.min().date()} -> {out.index.max().date()}) -> {args.out}")
    print("NOTE: output is already tax-excluded -> set ADJUST_CONSUMPTION_TAX=False.")

    if args.boj:
        boj = data.fetch_any(args.boj).dropna()
        boj_yoy = _yoy(boj) if _is_index(boj) else boj
        a, b = yoy.align(boj_yoy, join="inner")
        if len(a) < 8:
            print("\nEval: <8 overlapping points with BoJ series; cannot assess.")
        else:
            diff = (a - b)
            print(f"\nEvaluation vs BoJ official (overlap {a.index.min().date()} "
                  f"-> {a.index.max().date()}, n={len(a)}):")
            print(f"   correlation     = {a.corr(b):.3f}")
            print(f"   mean abs diff   = {diff.abs().mean():.3f} pp")
            print(f"   max  abs diff   = {diff.abs().max():.3f} pp")
            ok = diff.abs().mean() < 0.15
            print("   VERDICT:", "PASS - reconstruction matches BoJ; use the longer series."
                  if ok else "CHECK - gap > 0.15pp; revisit tax magnitudes/dates.")


if __name__ == "__main__":
    main()
