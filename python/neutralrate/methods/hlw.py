"""
Method 1 - Holston-Laubach-Williams (HLW, 2017/2023).

The canonical semi-structural model behind the BoJ survey's "LW/HLW" estimates:
an IS curve, a Phillips curve, and random-walk trends for potential output,
trend growth g and an "other factor" z, with r* = 4*c*g + z.  Estimated by the
Kalman filter (MLE over the regression coefficients); the trend-shock variances
are small (the Laubach-Williams low signal-to-noise that delivers a smooth r*
and sidesteps the pile-up problem), and the level is pinned by long-run
neutrality.  HLW is the LW-family member whose IS curve uses the real *policy
(short) rate*.  See ``_lw.estimate_lw`` for the shared engine.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import SETTINGS
from ._lw import estimate_lw

# Trend-shock std devs (low signal-to-noise -> smooth, BoJ-like r*).
SIGMA_G = 0.02
SIGMA_Z = 0.03


@dataclass
class HLWResult:
    r_star: pd.Series
    output_gap: pd.Series
    trend_growth: pd.Series      # annualized %
    params: dict
    loglik: float


def estimate(df: pd.DataFrame, c: float | None = None,
             restarts: int = 2, seed: int = 0,
             anchor_level: bool = True) -> HLWResult:
    c = SETTINGS.hlw.c_param if c is None else c
    out = estimate_lw(df, df["real_short_rate"], c=c,
                      sigma_g=SIGMA_G, sigma_z=SIGMA_Z,
                      anchor_level=anchor_level, restarts=restarts, seed=seed)
    idx = out["index"]
    return HLWResult(
        r_star=pd.Series(out["r_star"], index=idx, name="HLW"),
        output_gap=pd.Series(out["output_gap"], index=idx, name="output_gap"),
        trend_growth=pd.Series(out["trend_growth"], index=idx, name="trend_growth"),
        params=out["params"],
        loglik=out["loglik"],
    )
