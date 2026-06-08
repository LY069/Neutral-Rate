"""Shared trend-extraction helpers for the term-structure / common-trend methods."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..kalman import SSM, filter_smooth, loglik

_LLT_CACHE: dict = {}


def llt_decompose(series: pd.Series):
    """Local-linear-trend decomposition of a (100*log) series.

    Returns (level, slope_quarterly) aligned to ``series.index``.
    Memoized so methods that share an input (output gap) don't re-estimate it.
    """
    s = series.dropna()
    key = (round(float(s.iloc[0]), 6), round(float(s.iloc[-1]), 6), len(s))
    if key in _LLT_CACHE:
        return _LLT_CACHE[key]
    y = s.to_numpy().reshape(-1, 1)
    n = len(y)
    a1 = np.array([y[0, 0], np.mean(np.diff(y[:20, 0])) if n > 20 else 0.5])
    P1 = np.diag([10.0, 1.0])

    def ssm(theta):
        T = np.array([[1.0, 1.0], [0.0, 1.0]])
        Z = np.array([[1.0, 0.0]])
        Q = np.diag([np.exp(theta[0]) ** 2, np.exp(theta[1]) ** 2])
        H = np.array([[np.exp(theta[2]) ** 2]])
        return SSM(T=T, Z=Z, Q=Q, H=H, a1=a1.copy(), P1=P1.copy())

    def neg_ll(theta):
        ll = loglik(y, ssm(theta))
        return -ll if np.isfinite(ll) else 1e6

    res = minimize(neg_ll, np.array([np.log(0.3), np.log(0.05), np.log(0.3)]),
                   method="Nelder-Mead", options={"maxiter": 800})
    sm = filter_smooth(y, ssm(res.x))["smoothed"]
    out = (pd.Series(sm[:, 0], index=s.index),
           pd.Series(sm[:, 1], index=s.index))
    _LLT_CACHE[key] = out
    return out


def output_gap(log_gdp: pd.Series):
    """Return (output_gap %, annualized trend growth %)."""
    level, slope = llt_decompose(log_gdp)
    gap = (log_gdp.reindex(level.index) - level)
    return gap, 4.0 * slope
