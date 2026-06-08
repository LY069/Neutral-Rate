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

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..config import SETTINGS
from ..kalman import SSM, filter_smooth, loglik


@dataclass
class DSGEResult:
    r_star: pd.Series
    trend_growth: pd.Series      # annualized %
    params: dict


def _llt_ssm(log_sigma_level: float, log_sigma_slope: float, log_sigma_irr: float):
    """Local linear trend: state = [level, slope]."""
    T = np.array([[1.0, 1.0], [0.0, 1.0]])
    Z = np.array([[1.0, 0.0]])
    Q = np.diag([np.exp(log_sigma_level) ** 2, np.exp(log_sigma_slope) ** 2])
    H = np.array([[np.exp(log_sigma_irr) ** 2]])
    return T, Z, Q, H


def estimate(df: pd.DataFrame, rho: float | None = None,
             gamma: float | None = None) -> DSGEResult:
    p = SETTINGS.dsge
    rho = p.rho if rho is None else rho
    gamma = p.gamma if gamma is None else gamma

    series = df["log_cons"].dropna()
    y = series.to_numpy().reshape(-1, 1)
    n = len(y)
    a1 = np.array([y[0, 0], np.mean(np.diff(y[:20, 0])) if n > 20 else 0.5])
    P1 = np.diag([10.0, 1.0])

    def neg_ll(theta):
        T, Z, Q, H = _llt_ssm(*theta)
        ssm = SSM(T=T, Z=Z, Q=Q, H=H, a1=a1.copy(), P1=P1.copy())
        ll = loglik(y, ssm)
        return -ll if np.isfinite(ll) else 1e6

    x0 = np.array([np.log(0.3), np.log(0.05), np.log(0.3)])
    res = minimize(neg_ll, x0, method="Nelder-Mead",
                   options={"maxiter": 1500, "xatol": 1e-4, "fatol": 1e-4})
    T, Z, Q, H = _llt_ssm(*res.x)
    ssm = SSM(T=T, Z=Z, Q=Q, H=H, a1=a1.copy(), P1=P1.copy())
    sm = filter_smooth(y, ssm)["smoothed"]

    slope_q = sm[:, 1]                 # quarterly trend growth (100*log units)
    g_c = 4.0 * slope_q                # annualized %
    r_star = rho + gamma * g_c

    idx = series.index
    params = {
        "rho": rho, "gamma": gamma, "per_capita": p.per_capita,
        "sigma_level": np.exp(res.x[0]), "sigma_slope": np.exp(res.x[1]),
        "sigma_irregular": np.exp(res.x[2]),
    }
    return DSGEResult(
        r_star=pd.Series(r_star, index=idx, name="DSGE"),
        trend_growth=pd.Series(g_c, index=idx, name="trend_growth"),
        params=params,
    )
