"""
Method 6 - VAR with common trends (Del Negro, Giannone, Giannoni & Tambalotti,
2017, "Safety, Liquidity, and the Natural Rate of Interest").  BOJ applied this
common-trends approach to Japan in WP 24-E-17.

Del Negro et al. estimate r* as the slow-moving *trend* component of the real
interest rate inside a multivariate time-series model in which several
macro-financial series share a small number of common stochastic trends.  The
trend real rate is the natural rate; its decline reflects a falling growth
trend and a rising safety/liquidity (convenience-yield) premium.

Tractable faithful form
------------------------
A common-trends unobserved-components model on three series - the real short
rate, real GDP growth and inflation - with TWO common random-walk trends and
stationary AR(1) cycles:

    real_short_t = f1_t            + cyc_r_t
    gdp_growth_t = c_g + phi*f1_t  + cyc_g_t      (real rate & growth share f1)
    inflation_t  = c_pi + f2_t     + cyc_pi_t

r* = f1_t (the common real trend).  The original paper uses a Bayesian VAR with
priors and an explicit convenience-yield block; here we keep a frequentist,
spreadsheet-reproducible state space and note that simplification.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..kalman import SSM, filter_smooth, loglik


@dataclass
class DelNegroResult:
    r_star: pd.Series
    trend_growth: pd.Series
    params: dict


def estimate(df: pd.DataFrame) -> DelNegroResult:
    cols = ["real_short_rate", "gdp_growth", "inflation"]
    d = df.dropna(subset=cols)
    Y = d[cols].to_numpy()
    n = len(d)

    # state = [f1, f2, cyc_r, cyc_g, cyc_pi]
    a1 = np.array([float(np.nanmean(Y[:8, 0])), float(np.nanmean(Y[:8, 2])),
                   0.0, 0.0, 0.0])
    P1 = np.diag([25.0, 25.0, 10.0, 10.0, 10.0])

    SIGMA_F = 0.10          # fixed common-trend innovation std (pile-up remedy)

    def build(theta):
        phi, c_g, c_pi = theta[:3]
        rho_r, rho_g, rho_pi = theta[3:6]
        s_cr, s_cg, s_cpi = np.exp(theta[6:9])
        s_f1 = s_f2 = SIGMA_F
        T = np.diag([1.0, 1.0, rho_r, rho_g, rho_pi])
        Q = np.diag([s_f1 ** 2, s_f2 ** 2, s_cr ** 2, s_cg ** 2, s_cpi ** 2])
        Z = np.array([
            [1.0, 0.0, 1.0, 0.0, 0.0],
            [phi, 0.0, 0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 1.0],
        ])
        d_vec = np.array([0.0, c_g, c_pi])
        H = np.eye(3) * 1e-4
        return SSM(T=T, Z=Z, Q=Q, H=H, d=d_vec, a1=a1.copy(), P1=P1.copy())

    def neg_ll(theta):
        rho_r, rho_g, rho_pi = theta[3:6]
        pen = 0.0
        for r in (rho_r, rho_g, rho_pi):
            if not (-0.99 < r < 0.99):
                pen += 1e3
        ll = loglik(Y, build(theta))
        return (-ll + pen) if np.isfinite(ll) else 1e6

    x0 = np.array([1.0, 0.0, 0.0, 0.6, 0.6, 0.6,
                   np.log(0.5), np.log(0.5), np.log(0.5)])
    res = minimize(neg_ll, x0, method="Nelder-Mead",
                   options={"maxiter": 2000, "fatol": 1e-4, "xatol": 1e-4})
    sm = filter_smooth(Y, build(res.x))["smoothed"]
    f1 = sm[:, 0]
    phi = res.x[0]

    params = {"phi_growth": phi, "c_growth": res.x[1], "c_inflation": res.x[2],
              "rho_r": res.x[3], "rho_g": res.x[4], "rho_pi": res.x[5],
              "sigma_f1": SIGMA_F, "sigma_f2": SIGMA_F}
    return DelNegroResult(
        r_star=pd.Series(f1, index=d.index, name="DelNegro-VAR"),
        trend_growth=pd.Series(phi * f1, index=d.index, name="trend_growth"),
        params=params,
    )
