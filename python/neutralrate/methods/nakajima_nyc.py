"""
Method 4 - Natural Yield Curve, growth-anchored (Nakajima, Sudo, Hogen &
Takizuka, 2023, "On the estimation of the natural yield curve").

Nakajima et al. refine the Imakubo-Kojima-Nakajima natural yield curve by tying
its long-run level to trend potential growth (the Laubach-Williams r* = g + z
logic) while still using the term-structure / yield-curve-gap information.  That
growth anchor is the key difference from Method 3, whose natural rate is purely
curve-based.

Construction (same robust IS inversion as Method 3, then anchored):
    r_curve_t = LLT-smoothed curve-implied neutral rate   (as in Method 3)
    g_t       = trend potential growth (annualized)
    r*_t      = 0.5 * g_t + 0.5 * r_curve_t

so the natural rate is pinned half by potential growth (theory) and half by the
real yield curve (data).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ._common import llt_decompose, output_gap
from .natural_yield_curve import _fit_is, _implied_rate


@dataclass
class NakajimaResult:
    r_star: pd.Series
    natural_long: pd.Series
    trend_growth: pd.Series
    params: dict


def estimate(df: pd.DataFrame) -> NakajimaResult:
    gap, tg = output_gap(df["log_gdp"])      # tg = annualized trend growth %
    d = df.reindex(gap.index)
    # Survey-based real yields (long end deflated by anchored expectations).
    rs = d["real_short_exp"] if "real_short_exp" in d else d["real_short_rate"]
    rl = d["real_10y_exp"] if "real_10y_exp" in d else d["real_10y"]
    spread_long = float((rl - rs).mean())
    mid = 0.5 * (rs + (rl - spread_long))

    valid = gap.notna() & mid.notna() & tg.notna()
    gap = gap[valid]; mid = mid[valid]; tg = tg[valid]
    g = gap.to_numpy(); mc = mid.to_numpy(); tgv = tg.to_numpy()

    c0, phi1, phi2, delta = _fit_is(g, mc)
    impl = _implied_rate(g, mc, phi1, phi2, delta)
    r_curve, _ = llt_decompose(pd.Series(impl, index=gap.index))
    r_curve = r_curve.to_numpy()

    r_star = 0.5 * tgv + 0.5 * r_curve       # growth-anchored natural rate

    params = {"c0": c0, "phi1": phi1, "phi2": phi2, "delta": delta,
              "spread_long": spread_long, "growth_weight": 0.5}
    return NakajimaResult(
        r_star=pd.Series(r_star, index=gap.index, name="Nakajima-NYC"),
        natural_long=pd.Series(r_star + spread_long, index=gap.index,
                               name="natural_10y"),
        trend_growth=pd.Series(tgv, index=gap.index, name="trend_growth"),
        params=params,
    )
