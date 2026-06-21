"""
Augment the bundled synthetic sample with a full JGB constant-maturity curve.

The real MoF curve is firewalled in the sandbox, so to exercise (and offline-test)
the Nelson-Siegel term-structure path we synthesise a curve that is CONSISTENT
with the columns already in the sample: for each quarter we fit a Nelson-Siegel
curve that passes through the existing 3-month (rate_3m) and 10-year (rate_10y)
points, with a small fixed curvature, and evaluate it at every MoF maturity.

This adds jgb_<m>y columns WITHOUT touching any existing column, so every method
that does not use the curve is unchanged, and the curve-based methods get a
genuine (if synthetic) full curve to decompose.  On real data, swap this for the
live MoF fetch (config.MOF_JGB_CURVE_SOURCE).

    python scripts/add_curve_to_sample.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neutralrate.config import (  # noqa: E402
    JGB_CURVE_MATURITIES, NELSON_SIEGEL_LAMBDA, SETTINGS, jgb_col,
)
from neutralrate.methods import _nelson_siegel as ns  # noqa: E402

CURV = 0.20  # small fixed curvature factor (a mild medium-maturity hump)


def main():
    path = SETTINGS.sample_data_path
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if "rate_3m" not in df or "rate_10y" not in df:
        sys.exit("sample lacks rate_3m / rate_10y anchors")

    mats = [float(t) for t in JGB_CURVE_MATURITIES]
    lam = NELSON_SIEGEL_LAMBDA
    # NS loadings at the two anchor maturities (0.25y ~ 3m, 10y).
    (l0, s0, c0), (l1, s1, c1) = ns.loadings([0.25, 10.0], lam)
    full = ns.loadings(mats, lam)            # (k, 3)

    cols = {jgb_col(t): [] for t in JGB_CURVE_MATURITIES}
    for _, row in df.iterrows():
        y_short, y_long = row["rate_3m"], row["rate_10y"]
        if not np.isfinite(y_short) or not np.isfinite(y_long):
            for t in JGB_CURVE_MATURITIES:
                cols[jgb_col(t)].append(np.nan)
            continue
        # Solve level (b0) and slope (b1) so the curve hits both anchors, given a
        # fixed curvature b2 = CURV:  [s0 ; s1] are slope loadings at the anchors.
        b2 = CURV
        # y_short = b0 + b1*s0 + b2*c0 ;  y_long = b0 + b1*s1 + b2*c1
        A = np.array([[1.0, s0], [1.0, s1]])
        rhs = np.array([y_short - b2 * c0, y_long - b2 * c1])
        b0, b1 = np.linalg.solve(A, rhs)
        beta = np.array([b0, b1, b2])
        yvals = full @ beta
        for t, v in zip(JGB_CURVE_MATURITIES, yvals):
            cols[jgb_col(t)].append(v)

    for name, vals in cols.items():
        df[name] = vals
    df.to_csv(path)
    added = ", ".join(cols)
    print(f"Added {len(cols)} curve columns to {path}:\n  {added}")
    print(df[[jgb_col(t) for t in (1, 5, 10, 30)]].tail(3).round(3).to_string())


if __name__ == "__main__":
    main()
