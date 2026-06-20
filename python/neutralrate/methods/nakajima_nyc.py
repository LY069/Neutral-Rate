"""
Method 4 - Natural Yield Curve, growth-anchored (Nakajima, Sudo, Hogen &
Takizuka, 2023, "On the estimation of the natural yield curve").

Nakajima et al. refine the Imakubo-Kojima-Nakajima natural yield curve, tying
its long-run level more tightly to trend potential growth (the Laubach-Williams
r* = c*g + z logic) while using the term-structure information.

Implementation: the same LW state space and real yield-curve IS term as Method 3,
but with a *tighter* "other factor" z (a smaller z trend-shock variance), so the
natural rate is anchored more firmly to trend growth g - the refinement Nakajima
et al. emphasize.  Smoothness, as in the original, comes from the LW low
signal-to-noise.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ._lw import estimate_lw
from .natural_yield_curve import _curve_summary

SIGMA_G = 0.02
SIGMA_Z = 0.015      # tighter than Imakubo -> r* more firmly growth-anchored


@dataclass
class NakajimaResult:
    r_star: pd.Series
    natural_long: pd.Series
    trend_growth: pd.Series
    params: dict


def estimate(df: pd.DataFrame, restarts: int = 2, seed: int = 0) -> NakajimaResult:
    mid, spread_long = _curve_summary(df)
    # Nakajima's refinement anchors the natural rate to trend potential growth
    # (not the average real rate, as Imakubo effectively does): estimate without
    # the real-rate level anchor, then re-level so the sample-mean r* equals the
    # sample-mean trend growth.  This makes Nakajima's r* sit above Imakubo's
    # when growth exceeds the realized real rate, as in the BoJ estimates.
    out = estimate_lw(df, mid, c=1.0, sigma_g=SIGMA_G, sigma_z=SIGMA_Z,
                      anchor_level=False, restarts=restarts, seed=seed)
    rstar_arr = out["r_star"] + (np.nanmean(out["trend_growth"])
                                 - np.nanmean(out["r_star"]))
    idx = out["index"]
    rstar = pd.Series(rstar_arr, index=idx, name="Nakajima-NYC")
    params = dict(out["params"]); params["spread_long"] = spread_long
    return NakajimaResult(
        r_star=rstar,
        natural_long=pd.Series(rstar.to_numpy() + spread_long, index=idx,
                               name="natural_10y"),
        trend_growth=pd.Series(out["trend_growth"], index=idx, name="trend_growth"),
        params=params,
    )
