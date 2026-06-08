"""
Method 5 - Macro-finance natural curve (Goy & Iwasaki, 2024,
"From the Natural Rate towards a Natural Curve").

A trend-cycle macro-finance term-structure model: the real yield curve (a
Nelson-Siegel level/slope structure) and the macroeconomy share a common,
slowly-moving real trend that plays the dual role of (i) the long-run level of
the yield curve and (ii) the natural real rate that closes the output gap.

Tractable faithful form
------------------------
A single common stochastic trend mu_t (random walk) underlies the short real
rate, the long real rate (the Nelson-Siegel *level* factor) and trend output
growth.  Loadings are estimated by ML; idiosyncratic deviations are measurement
noise.  r* = mu_t.

    real_short_t = mu_t                         + e1   (loading fixed to 1)
    real_10y_t   = c_l + a_l * mu_t              + e2
    trend_grow_t = c_g + a_g * mu_t              + e3
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..kalman import SSM, filter_smooth, loglik
from ._common import output_gap


@dataclass
class GoyIwasakiResult:
    r_star: pd.Series
    params: dict


def estimate(df: pd.DataFrame) -> GoyIwasakiResult:
    _, tg = output_gap(df["log_gdp"])
    d = df.copy()
    d["trend_growth"] = tg.reindex(d.index)
    cols = ["real_short_rate", "real_10y", "trend_growth"]
    d = d.dropna(subset=cols)
    Y = d[cols].to_numpy()
    n = len(d)

    SIGMA_MU = 0.10                          # fixed common-trend innovation std
    a1 = np.array([float(np.nanmean(Y[:8, 0]))])
    P1 = np.array([[4.0]])

    def build(theta):
        c_l, a_l, c_g, a_g = theta[:4]
        s1, s2, s3 = np.exp(theta[4:7])
        T = np.array([[1.0]])
        Q = np.array([[SIGMA_MU ** 2]])
        Z = np.array([[1.0], [a_l], [a_g]])
        d_vec = np.array([0.0, c_l, c_g])
        H = np.diag([s1 ** 2, s2 ** 2, s3 ** 2])
        return SSM(T=T, Z=Z, Q=Q, H=H, d=d_vec, a1=a1.copy(), P1=P1.copy())

    def neg_ll(theta):
        ll = loglik(Y, build(theta))
        return -ll if np.isfinite(ll) else 1e6

    x0 = np.array([2.0, 1.0, 0.0, 1.0,
                   np.log(0.5), np.log(0.8), np.log(0.8)])
    res = minimize(neg_ll, x0, method="Nelder-Mead",
                   options={"maxiter": 1500, "fatol": 1e-4, "xatol": 1e-4})
    sm = filter_smooth(Y, build(res.x))["smoothed"]
    mu = sm[:, 0]

    c_l, a_l, c_g, a_g = res.x[:4]
    params = {"c_long": c_l, "a_long": a_l, "c_growth": c_g, "a_growth": a_g,
              "sigma_mu": SIGMA_MU,
              "sigma_short": np.exp(res.x[4]), "sigma_long": np.exp(res.x[5]),
              "sigma_growth": np.exp(res.x[6])}
    return GoyIwasakiResult(
        r_star=pd.Series(mu, index=d.index, name="Goy-Iwasaki"),
        params=params,
    )
