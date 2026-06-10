"""
Shared Laubach-Williams-type semi-structural state-space estimator.

This is the common engine behind the three LW-family methods in the BoJ survey:
HLW (2017/2023), Imakubo-Kojima-Nakajima (2015) and Nakajima et al. (2023).  All
three are explicitly *extensions of Laubach-Williams (2003)*; they differ only in
which real interest rate enters the IS curve (the policy/short rate for HLW; a
real *yield-curve* summary for the natural-yield-curve methods) and in how
tightly r* is anchored to trend growth.

Model (linear-Gaussian state space, Kalman filter + MLE):

    IS:       gap_t = a1 gap_{t-1} + a2 gap_{t-2} - a_r (R_{t-1} - R*_{t-1}) + e
    Phillips: pi_t  = b_pi pi_{t-1} + (1-b_pi) pi_{t-2..4} + b_y gap_{t-1} + u
    Trends:   y*_t = y*_{t-1} + g_{t-1} (+shock);  g, z ~ random walks
              R*_t = 4 c g_t + z_t            (the natural rate)

where R is the real-rate summary supplied by the caller and gap = y - y*.

Smoothness is controlled THE WAY THE ORIGINAL PAPERS DO IT: the trend-shock
std devs (sigma_g, sigma_z) are small relative to the cyclical shocks (a low
signal-to-noise ratio).  Laubach-Williams pin this ratio by Stock-Watson
median-unbiased estimation; we fix it to a small calibrated value, which both
reproduces the smooth r* the papers report and avoids the well-known pile-up
problem (MLE drives the trend variances to a corner).

State vector (9):
    [y*_t, y*_{t-1}, y*_{t-2}, g_t, g_{t-1}, g_{t-2}, z_t, z_{t-1}, z_{t-2}]
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..kalman import SSM, filter_smooth, loglik


def _build_ssm(theta, c, sigma_g, sigma_z):
    a1, a2, a_r, b_pi, b_y = theta[:5]
    s_yp, s_e1, s_e2 = np.exp(theta[5:8])

    m = 9
    T = np.zeros((m, m))
    T[0, 0] = 1.0; T[0, 3] = 1.0          # y*_t = y*_{t-1} + g_{t-1}
    T[1, 0] = 1.0; T[2, 1] = 1.0          # y* lags
    T[3, 3] = 1.0; T[4, 3] = 1.0; T[5, 4] = 1.0   # g random walk + lags
    T[6, 6] = 1.0; T[7, 6] = 1.0; T[8, 7] = 1.0   # z random walk + lags

    Q = np.zeros((m, m))
    Q[0, 0] = s_yp ** 2
    Q[3, 3] = sigma_g ** 2
    Q[6, 6] = sigma_z ** 2

    # Measurement (observed-data intercepts subtracted by the caller).  The IS
    # curve carries the ORIGINAL HLW two-lag average real-rate-gap term,
    # -(a_r/2)(r̃_{t-1}+r̃_{t-2}), so r*'s lags load (a_r/2) each via g and z.
    Z = np.zeros((2, m))
    Z[0, 0] = 1.0
    Z[0, 1] = -a1
    Z[0, 2] = -a2
    Z[0, 4] = 2.0 * a_r * c    # (a_r/2)*4c on g_{t-1}
    Z[0, 5] = 2.0 * a_r * c    # (a_r/2)*4c on g_{t-2}
    Z[0, 7] = a_r / 2.0        # on z_{t-1}
    Z[0, 8] = a_r / 2.0        # on z_{t-2}
    Z[1, 1] = -b_y
    H = np.diag([s_e1 ** 2, s_e2 ** 2])
    return T, Z, Q, H


def estimate_lw(df: pd.DataFrame, rate: pd.Series, *, c: float = 1.0,
                sigma_g: float = 0.02, sigma_z: float = 0.03,
                anchor_level: bool = True, restarts: int = 2, seed: int = 0):
    """Estimate an LW-type r* given a real-rate summary `rate`.

    Returns a dict with r_star, output_gap, trend_growth (annualized %), params,
    loglik - all as numpy arrays plus the aligned index.
    """
    data = pd.DataFrame({
        "y": df["log_gdp"], "pi": df["inflation"], "r": rate.reindex(df.index),
    }).dropna()
    y = data["y"].to_numpy(); pi = data["pi"].to_numpy(); r = data["r"].to_numpy()
    n = len(data)
    pi_bar = np.full(n, np.nan)
    for t in range(4, n):
        pi_bar[t] = np.mean(pi[t - 4:t - 1])

    def make_yadj(a1, a2, a_r, b_pi, b_y):
        yadj = np.full((n, 2), np.nan)
        yadj[2:, 0] = y[2:] - (a1 * y[1:-1] + a2 * y[:-2]
                               - (a_r / 2.0) * (r[1:-1] + r[:-2]))
        yadj[4:, 1] = pi[4:] - (b_pi * pi[3:-1] + (1 - b_pi) * pi_bar[4:]
                                + b_y * y[3:-1])
        return yadj

    g0 = float(np.mean(np.diff(y)))
    a1v = np.full(9, y[0]); a1v[3:6] = g0; a1v[6:] = 0.0
    P1 = np.diag([10., 10., 10., 0.25, 0.25, 0.25, 4., 4., 4.])

    def neg_ll(theta):
        a1, a2, a_r, b_pi, b_y = theta[:5]
        pen = 0.0
        if not (-2 < a1 < 2 and -2 < a2 < 2):
            pen += 1e3
        if a1 + a2 > 0.98:
            pen += 1e4 * (a1 + a2 - 0.98)
        if a_r <= 0:
            pen += 1e3 * (1 - a_r)
        if not (0 < b_pi < 1):
            pen += 1e3
        if b_y <= 0:
            pen += 1e3 * (1 - b_y)
        T, Z, Q, H = _build_ssm(theta, c, sigma_g, sigma_z)
        ssm = SSM(T=T, Z=Z, Q=Q, H=H, a1=a1v.copy(), P1=P1.copy())
        try:
            ll = loglik(make_yadj(a1, a2, a_r, b_pi, b_y), ssm)
        except Exception:  # noqa: BLE001
            return 1e6
        return (-ll + pen) if np.isfinite(ll) else 1e6

    rng = np.random.default_rng(seed)
    base = np.array([1.2, -0.3, 0.05, 0.5, 0.1,
                     np.log(0.6), np.log(0.6), np.log(0.6)])
    best = None
    for k in range(restarts):
        x0 = base + (0 if k == 0 else rng.normal(0, 0.12, size=base.shape))
        try:
            res = minimize(neg_ll, x0, method="Nelder-Mead",
                           options={"maxiter": 800, "xatol": 1e-3, "fatol": 1e-3})
            if best is None or res.fun < best.fun:
                best = res
        except Exception:  # noqa: BLE001
            continue
    if best is None:
        raise RuntimeError("LW estimation failed to converge.")

    theta = best.x
    a1, a2, a_r, b_pi, b_y = theta[:5]
    T, Z, Q, H = _build_ssm(theta, c, sigma_g, sigma_z)
    ssm = SSM(T=T, Z=Z, Q=Q, H=H, a1=a1v.copy(), P1=P1.copy())
    out = filter_smooth(make_yadj(a1, a2, a_r, b_pi, b_y), ssm)
    sm = out["smoothed"]

    g_t = sm[:, 3]; z_t = sm[:, 6]; yp = sm[:, 0]
    r_star = 4.0 * c * g_t + z_t
    gap = y - yp

    level_shift = 0.0
    if anchor_level:               # long-run neutrality: mean r* = mean real rate
        level_shift = float(np.nanmean(r) - np.nanmean(r_star))
        r_star = r_star + level_shift

    return {
        "index": data.index,
        "r_star": r_star,
        "output_gap": gap,
        "trend_growth": 4.0 * g_t,
        "loglik": out["loglik"],
        "params": {"a_y1": a1, "a_y2": a2, "a_r": a_r, "b_pi": b_pi, "b_y": b_y,
                   "c": c, "sigma_g": sigma_g, "sigma_z": sigma_z,
                   "sigma_ystar": np.exp(theta[5]), "sigma_ygap": np.exp(theta[6]),
                   "sigma_pi": np.exp(theta[7]), "level_shift": level_shift},
    }
