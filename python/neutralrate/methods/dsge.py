"""
Method 2 - DSGE-consistent natural rate (Okazaki & Sudo, 2018, BOJ WP 18-E-6).

A full medium-scale DSGE cannot be estimated inside a spreadsheet, so we
replicate the *economic content* that pins down r* in that class of models.  In
the (de-trended) consumption Euler equation, the steady-state real rate is

        r*_t = rho + gamma * g_c,t

where
    g_c,t   = trend growth of per-capita real consumption (annualized %),
    gamma   = inverse intertemporal elasticity of substitution,
    rho     = rate of time preference / steady-state risk-premium adjustment.

Okazaki-Sudo show Japan's r* decline is driven mainly by the slowdown in trend
(per-capita) consumption/productivity growth - exactly the g_c,t term here.

Trend consumption growth is extracted with a local-linear-trend (LLT)
unobserved-components model estimated by maximum likelihood, the standard
state-space way to obtain a smooth stochastic trend.  The Python module is
the faithful implementation; the Excel sheet uses the same LLT parameters.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import SETTINGS
from ._common import LAM_TREND, trend_growth


@dataclass
class DSGEResult:
    r_star: pd.Series
    trend_growth: pd.Series      # annualized %
    params: dict


def estimate(df: pd.DataFrame, rho: float | None = None,
             gamma: float | None = None) -> DSGEResult:
    p = SETTINGS.dsge
    rho = p.rho if rho is None else rho
    gamma = p.gamma if gamma is None else gamma

    series = df["log_cons"].dropna()
    # Trend per-capita consumption growth from a Kalman local-linear-trend with a
    # low signal-to-noise (the stochastic-trend mechanism Okazaki-Sudo estimate
    # in their DSGE).  In the steady state r* = rho + gamma * g_c, with g_c slow.
    g_c = trend_growth(series, LAM_TREND)        # annualized %, very smooth
    r_star = rho + gamma * g_c

    idx = series.index
    params = {
        "rho": rho, "gamma": gamma, "per_capita": p.per_capita,
        "lambda_trend": LAM_TREND,
    }
    return DSGEResult(
        r_star=pd.Series(r_star, index=idx, name="DSGE"),
        trend_growth=pd.Series(g_c, index=idx, name="trend_growth"),
        params=params,
    )
