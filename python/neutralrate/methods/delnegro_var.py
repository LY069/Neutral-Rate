"""
Method 6 - VAR with common trends (Del Negro, Giannone, Giannoni & Tambalotti,
2017, "Safety, Liquidity, and the Natural Rate of Interest").  BOJ applied this
common-trends approach to Japan in WP 24-E-17.

Del Negro et al. estimate r* as the slow-moving *trend* of the real interest
rate inside a multivariate model in which macro-financial series share common
stochastic trends.  Two mechanisms matter: a falling growth trend, and a RISING
SAFETY/LIQUIDITY (convenience-yield / term) premium that wedges the safe short
rate away from long yields - which is why the long rate belongs in the
observation vector.

Tractable faithful form
------------------------
Common-trends unobserved-components model on FOUR observables with THREE
random-walk trends and AR(1) cycles:

    real_short_t = f_r,t                +  cyc_r,t      (r* = f_r)
    real_10y_t   = f_r,t + f_sp,t       +  cyc_10,t     (f_sp = term/convenience
                                                          premium trend)
    gdp_growth_t = c_g + phi * f_r,t    +  cyc_g,t      (growth shares the real
                                                          trend, as in DGGT)
    inflation_t  = f_pi,t               +  cyc_pi,t

Trend innovations are fixed small (low signal-to-noise, the smoothness
mechanism of the original's priors); cycle persistence/variances are MLE.
The original is Bayesian with an explicit convenience-yield block on corporate
spreads; that simplification is documented in the research report.
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
    convenience_trend: pd.Series   # trend term/safety premium (10y - r*)
    trend_growth: pd.Series
    params: dict


def estimate(df: pd.DataFrame) -> DelNegroResult:
    d = df.copy()
    d["_rs"] = d["real_short_exp"] if "real_short_exp" in d else d["real_short_rate"]
    d["_r10"] = d["real_10y_exp"] if "real_10y_exp" in d else d["real_10y"]
    cols = ["_rs", "_r10", "gdp_growth", "inflation"]
    d = d.dropna(subset=cols)
    Y = d[cols].to_numpy()
    n = len(d)

    # state = [f_r, f_sp, f_pi, cyc_r, cyc_10, cyc_g, cyc_pi]
    # Trends start at early-sample means with TIGHT priors: the f_r / f_sp split
    # in the 10y equation is only identified through the short-rate equation, so
    # loose trend priors + near-unit-root cycles let f_r drift.
    a1 = np.array([float(np.nanmean(Y[:8, 0])),
                   float(np.nanmean(Y[:8, 1] - Y[:8, 0])),
                   float(np.nanmean(Y[:8, 3])),
                   0.0, 0.0, 0.0, 0.0])
    P1 = np.diag([4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0])

    SIGMA_FR = 0.07    # trend real rate innovation (smooth but not flat)
    SIGMA_FSP = 0.05   # convenience/term-premium trend innovation
    SIGMA_FPI = 0.10   # trend inflation innovation

    def build(theta):
        phi, c_g = theta[:2]
        rho = theta[2:6]
        s_cyc = np.exp(theta[6:10])
        T = np.diag([1.0, 1.0, 1.0, *rho])
        Q = np.diag([SIGMA_FR ** 2, SIGMA_FSP ** 2, SIGMA_FPI ** 2,
                     *(s_cyc ** 2)])
        Z = np.array([
            [1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [phi, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
        ])
        d_vec = np.array([0.0, 0.0, c_g, 0.0])
        H = np.eye(4) * 1e-4
        return SSM(T=T, Z=Z, Q=Q, H=H, d=d_vec, a1=a1.copy(), P1=P1.copy())

    def neg_ll(theta):
        # cycles must be CYCLES: |rho| <= 0.9 keeps transitory components from
        # impersonating the trend (which would let f_r drift off the data).
        pen = sum(1e4 * (abs(r) - 0.9) for r in theta[2:6] if abs(r) > 0.9)
        ll = loglik(Y, build(theta))
        return (-ll + pen) if np.isfinite(ll) else 1e6

    x0 = np.array([1.0, 0.0, 0.6, 0.6, 0.6, 0.6,
                   np.log(0.5), np.log(0.5), np.log(0.5), np.log(0.5)])
    res = minimize(neg_ll, x0, method="Nelder-Mead",
                   options={"maxiter": 2500, "fatol": 1e-4, "xatol": 1e-4})
    sm = filter_smooth(Y, build(res.x))["smoothed"]
    f_r, f_sp = sm[:, 0], sm[:, 1]
    phi = res.x[0]

    params = {"phi_growth": phi, "c_growth": res.x[1],
              "rho_r": res.x[2], "rho_10": res.x[3],
              "rho_g": res.x[4], "rho_pi": res.x[5],
              "sigma_fr": SIGMA_FR, "sigma_fsp": SIGMA_FSP,
              "sigma_fpi": SIGMA_FPI}
    return DelNegroResult(
        r_star=pd.Series(f_r, index=d.index, name="DelNegro-VAR"),
        convenience_trend=pd.Series(f_sp, index=d.index, name="convenience_trend"),
        trend_growth=pd.Series(phi * f_r, index=d.index, name="trend_growth"),
        params=params,
    )
