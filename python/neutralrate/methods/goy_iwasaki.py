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
growth.  r* = mu_t.

    real_short_t = mu_t                         + e1
    real_10y_t   = c_l + mu_t                    + e2
    trend_grow_t = c_g + mu_t                    + e3

Identification (loadings fixed to 1).  An earlier version estimated the loadings
a_l, a_g freely.  That model is only weakly identified: with a near-constant
common trend (small sigma_mu) and three free observation-noise variances, the
likelihood has a flat ridge along which one noise variance collapses to zero and
pins mu to a single series - so the estimate is unstable (it lands in different
basins run-to-run under BLAS non-determinism, giving r* anywhere from -0.8 to
+0.3) and its LEVEL drifts ~1.2pp above BoJ.  The fix is the model's own
economics: in a Nelson-Siegel curve the common LEVEL factor loads exactly 1 on
every maturity, and r* tracks trend growth one-for-one (the LW logic), so
a_l = a_g = 1 is the correct restriction, not a free parameter.  mu is then the
genuine common level (its mean ~ the real short rate, intercepts c_l, c_g
absorbing the average term premium and the growth-minus-rate wedge); this is
both well-identified/deterministic and ~0.7pp closer to BoJ.  A small floor on
the observation-noise std devs guarantees the ridge can never reappear.
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
    # Real short/long yields.  The short rate is the policy/short real rate; the
    # long rate is taken from the fitted Nelson-Siegel curve (whole-curve,
    # denoised) when the full JGB curve is available, else the raw real 10y.
    # (A full affine no-arbitrage curve - the original's structure - is the
    # remaining fidelity step; see docs/03_faithfulness_audit.md.)
    d["_rs"] = d["real_short_exp"] if "real_short_exp" in d else d["real_short_rate"]
    if "ns_real_10y" in d and d["ns_real_10y"].notna().any():
        d["_rl"] = d["ns_real_10y"]
    else:
        d["_rl"] = d["real_10y_exp"] if "real_10y_exp" in d else d["real_10y"]
    cols = ["_rs", "_rl", "trend_growth"]
    d = d.dropna(subset=cols)
    Y = d[cols].to_numpy()
    n = len(d)

    SIGMA_MU = 0.02                          # small common-trend innovation -> smooth
    SIGMA_FLOOR = 0.05                        # min obs-noise std (kills the flat ridge)
    A_LONG = 1.0     # Nelson-Siegel level factor loads 1 on every maturity
    A_GROWTH = 1.0   # r* tracks trend growth one-for-one (LW logic)
    a1 = np.array([float(np.nanmean(Y[:8, 0]))])
    P1 = np.array([[4.0]])

    def build(theta):
        c_l, c_g = theta[:2]
        s = np.sqrt(np.exp(theta[2:5]) ** 2 + SIGMA_FLOOR ** 2)
        T = np.array([[1.0]])
        Q = np.array([[SIGMA_MU ** 2]])
        Z = np.array([[1.0], [A_LONG], [A_GROWTH]])
        d_vec = np.array([0.0, c_l, c_g])
        H = np.diag(s ** 2)
        return SSM(T=T, Z=Z, Q=Q, H=H, d=d_vec, a1=a1.copy(), P1=P1.copy())

    def neg_ll(theta):
        ll = loglik(Y, build(theta))
        return -ll if np.isfinite(ll) else 1e6

    x0 = np.array([1.5, 0.0, np.log(0.5), np.log(0.8), np.log(0.8)])
    res = minimize(neg_ll, x0, method="Nelder-Mead",
                   options={"maxiter": 1500, "fatol": 1e-5, "xatol": 1e-5})
    sm = filter_smooth(Y, build(res.x))["smoothed"]
    mu = sm[:, 0]

    c_l, c_g = res.x[:2]
    s_final = np.sqrt(np.exp(res.x[2:5]) ** 2 + SIGMA_FLOOR ** 2)
    params = {"c_long": c_l, "a_long": A_LONG, "c_growth": c_g, "a_growth": A_GROWTH,
              "sigma_mu": SIGMA_MU,
              "sigma_short": float(s_final[0]), "sigma_long": float(s_final[1]),
              "sigma_growth": float(s_final[2])}
    return GoyIwasakiResult(
        r_star=pd.Series(mu, index=d.index, name="Goy-Iwasaki"),
        params=params,
    )
