"""
Method 3 - Natural Yield Curve (Imakubo, Kojima & Nakajima, 2015).

Imakubo et al. extend Laubach-Williams from a single natural rate to a whole
"natural yield curve": the output gap responds to the *yield-curve gap* (the gap
between the actual real yield curve and the natural one) rather than to a single
short-rate gap.  The natural rate of interest is the short end of that curve.

Implementation: the same LW semi-structural state space as HLW (Kalman filter,
random-walk trends, r* = 4*c*g + z), but the IS curve's real-rate term is a
**real yield-curve summary** - the curve midpoint, deflated by survey/anchored
expectations - instead of the policy rate.  This is faithful to "an extension of
LW for the conventional natural rate" and produces the natural rate of interest
(short end) plus the natural 10y rate.  Smoothness comes from the LW low
signal-to-noise (small trend-shock variances), as in the original.

FAITHFULNESS (see docs/03_faithfulness_audit.md).  The original decomposes the
*whole* real JGB curve into Nelson-Siegel level/slope/curvature factors via a
shadow-rate term-structure model (to respect the ZLB), and the IS curve responds
to the *yield-curve gap* across maturities.  This toolkit fetches only two
maturities (3m, 10y) and collapses them to a midpoint, so there is no curve
decomposition, no shadow-rate handling, and no natural *curve* - only a scalar
proxy of the short end.  The same two-maturity limitation caps every method in
the natural-yield-curve family (Nakajima, Goy-Iwasaki, Hatayama-Iwasaki/"Del
Negro").  Closing it needs the full JGB curve (>=4 maturities), a data gap, not a
calibration one.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ._lw import estimate_lw

SIGMA_G = 0.02
SIGMA_Z = 0.03


@dataclass
class NYCResult:
    r_star: pd.Series           # short end of the natural yield curve
    natural_long: pd.Series     # natural 10y
    output_gap: pd.Series
    params: dict


def _curve_summary(df: pd.DataFrame):
    """Real yield-curve midpoint, long end deflated by anchored expectations and
    reduced to a short-equivalent by removing the average real term spread."""
    rs = df["real_short_exp"] if "real_short_exp" in df else df["real_short_rate"]
    rl = df["real_10y_exp"] if "real_10y_exp" in df else df["real_10y"]
    spread_long = float((rl - rs).mean())
    mid = 0.5 * (rs + (rl - spread_long))
    return mid, spread_long


def estimate(df: pd.DataFrame, restarts: int = 2, seed: int = 0) -> NYCResult:
    mid, spread_long = _curve_summary(df)
    out = estimate_lw(df, mid, c=1.0, sigma_g=SIGMA_G, sigma_z=SIGMA_Z,
                      anchor_level=True, restarts=restarts, seed=seed)
    idx = out["index"]
    rstar = pd.Series(out["r_star"], index=idx, name="Imakubo-NYC")
    params = dict(out["params"]); params["spread_long"] = spread_long
    return NYCResult(
        r_star=rstar,
        natural_long=pd.Series(rstar.to_numpy() + spread_long, index=idx,
                               name="natural_10y"),
        output_gap=pd.Series(out["output_gap"], index=idx, name="output_gap"),
        params=params,
    )
