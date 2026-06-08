"""
Method 3 - Natural Yield Curve (Imakubo, Kojima & Nakajima, 2015).

Imakubo et al. extend Laubach-Williams from a single natural rate to a whole
"natural yield curve": the term structure of real rates consistent with a
closed output gap.  The natural rate of interest is the short end of that curve,
and the IS curve responds to the *yield-curve gap* (actual minus natural curve)
rather than to a single short-rate gap.

Tractable faithful form (robust two-step)
-----------------------------------------
1. Estimate the IS curve by OLS:
       gap_t = c0 + phi1 gap_{t-1} + phi2 gap_{t-2} + b * curve_mid_{t-1} + e
   where curve_mid is the level of the real yield curve (avg of the short and
   level-adjusted long real rate) and delta = -b is its sensitivity.
2. Invert the IS curve for the *neutral* real rate that keeps the systematic
   output gap from opening further:
       r_implied_t = curve_mid_t + ((phi1 - 1) gap_t + phi2 gap_{t-1}) / delta
   then smooth it with a local-linear-trend (Kalman) to obtain r*.

This is far better identified than estimating a free random-walk natural rate
from a single noisy IS equation, and it tracks the Wicksellian idea directly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ._common import llt_decompose, output_gap


@dataclass
class NYCResult:
    r_star: pd.Series           # short end of the natural yield curve
    natural_long: pd.Series     # natural 10y
    output_gap: pd.Series
    params: dict


def _fit_is(gap: np.ndarray, mid: np.ndarray):
    """OLS of gap on its 2 lags and lagged curve level. Returns c0,phi1,phi2,delta."""
    n = len(gap)
    rows = range(2, n)
    X = np.column_stack([np.ones(len(rows)),
                         gap[1:n - 1], gap[0:n - 2], mid[1:n - 1]])
    yv = gap[2:n]
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    c0, phi1, phi2, b = beta
    delta = max(-b, 0.10)        # ensure a sensible positive rate sensitivity
    return c0, phi1, phi2, delta


def _implied_rate(gap, mid, phi1, phi2, delta):
    impl = mid.copy()
    cyc = ((phi1 - 1.0) * gap + phi2 * np.r_[0.0, gap[:-1]]) / delta
    impl = mid + np.clip(cyc, -2.0, 2.0)     # bounded cyclical adjustment
    return impl


def estimate(df: pd.DataFrame) -> NYCResult:
    gap, _tg = output_gap(df["log_gdp"])
    d = df.reindex(gap.index)
    # Survey-based real yields (long end deflated by anchored expectations),
    # mirroring Imakubo et al.'s Consensus-Forecasts deflation of nominal yields.
    rs = d["real_short_exp"] if "real_short_exp" in d else d["real_short_rate"]
    rl = d["real_10y_exp"] if "real_10y_exp" in d else d["real_10y"]
    spread_long = float((rl - rs).mean())
    mid = 0.5 * (rs + (rl - spread_long))

    valid = gap.notna() & mid.notna()
    gap = gap[valid]; mid = mid[valid]
    g = gap.to_numpy(); mc = mid.to_numpy()

    c0, phi1, phi2, delta = _fit_is(g, mc)
    impl = _implied_rate(g, mc, phi1, phi2, delta)
    level, _ = llt_decompose(pd.Series(impl, index=gap.index))

    params = {"c0": c0, "phi1": phi1, "phi2": phi2, "delta": delta,
              "spread_long": spread_long}
    return NYCResult(
        r_star=pd.Series(level.to_numpy(), index=gap.index, name="Imakubo-NYC"),
        natural_long=pd.Series(level.to_numpy() + spread_long, index=gap.index,
                               name="natural_10y"),
        output_gap=pd.Series(g, index=gap.index, name="output_gap"),
        params=params,
    )
