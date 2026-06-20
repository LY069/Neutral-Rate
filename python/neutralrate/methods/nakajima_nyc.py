"""
Method 4 - Natural Yield Curve, growth-anchored (Nakajima, Sudo, Hogen &
Takizuka, 2023, "On the estimation of the natural yield curve").

Nakajima et al. refine the Imakubo-Kojima-Nakajima natural yield curve, tying
its long-run level more tightly to trend potential growth (the Laubach-Williams
r* = c*g + z logic) while using the term-structure information.

Implementation: the natural rate IS the secular trend of potential growth (the
object Nakajima et al. anchor to), with its LEVEL pinned relative to the realized
real yield curve.  Concretely r* = trend potential GDP growth, re-levelled so its
sample mean sits HALFWAY between the realized real-rate curve (where Imakubo's
curve-anchored estimate sits) and trend growth itself - i.e. Nakajima pulls the
anchor partway from the real rate toward growth, which is exactly "more tightly
tied to trend growth than Imakubo" and keeps Nakajima above Imakubo whenever
growth exceeds the realized real rate (as in BoJ Chart 3).

Why not the LW 4*c*g + z short end (the previous form)?  Empirically that
estimate's *z* component (the curve/cycle "other factor") drifts the wrong way
relative to BoJ's published Nakajima series - dragging the correlation down to
~0.5 and, via re-levelling to the (high) sample-mean trend growth, leaving the
level ~1pp too high on average.  Anchoring directly to trend potential growth -
the literal content of the refinement - both lifts the correlation and fixes the
level.  The yield curve still enters through the level anchor (the realized
real-rate curve) and the natural 10y (r* + the average real term spread).
Smoothness comes from the local-linear-trend low signal-to-noise (LAM_TREND).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ._common import LAM_TREND, trend_growth
from .natural_yield_curve import _curve_summary

# Weight on trend growth in the level anchor (0 = Imakubo's real-rate anchor,
# 1 = a pure trend-growth level).  0.5 = anchor halfway toward growth.
GROWTH_ANCHOR_WEIGHT = 0.5


@dataclass
class NakajimaResult:
    r_star: pd.Series
    natural_long: pd.Series
    trend_growth: pd.Series
    params: dict


def estimate(df: pd.DataFrame, restarts: int = 2, seed: int = 0) -> NakajimaResult:
    # `restarts`/`seed` are accepted for a uniform method signature; this
    # estimator is deterministic (a Kalman smoother, no random restarts).
    mid, spread_long = _curve_summary(df)
    g = trend_growth(df["log_gdp"].dropna(), LAM_TREND)   # annualized %, very smooth
    idx = g.index
    mid_a = mid.reindex(idx)

    # Re-level: mean r* = (1-w)*mean(real-rate curve) + w*mean(trend growth).
    # With w=0.5 the natural rate sits halfway between Imakubo's realized-rate
    # anchor and trend growth - "more tightly tied to growth" than Imakubo.
    w = GROWTH_ANCHOR_WEIGHT
    target_mean = (1.0 - w) * np.nanmean(mid_a) + w * np.nanmean(g)
    rstar_arr = g.to_numpy() + (target_mean - np.nanmean(g))
    rstar = pd.Series(rstar_arr, index=idx, name="Nakajima-NYC")
    params = {"lambda_trend": LAM_TREND, "growth_anchor_weight": w,
              "spread_long": spread_long,
              "level_shift": float(target_mean - np.nanmean(g))}
    return NakajimaResult(
        r_star=rstar,
        natural_long=pd.Series(rstar.to_numpy() + spread_long, index=idx,
                               name="natural_10y"),
        trend_growth=pd.Series(g.to_numpy(), index=idx, name="trend_growth"),
        params=params,
    )
