"""
Method 1 - Holston-Laubach-Williams (HLW, 2017/2023).

A faithful (if compact) implementation of the HLW semi-structural model, the
workhorse behind the BOJ survey's "LW/HLW" estimates.  Three building blocks:

    IS curve      : output gap depends on its own lags and the *real-rate gap*
                    (real rate minus r*).
    Phillips curve: inflation depends on lagged inflation and the output gap.
    Trends        : potential output y*, trend growth g and an "other factor"
                    z all follow random walks, with   r* = 4*c*g + z.

The system is cast in linear-Gaussian state-space form and estimated by maximum
likelihood (Kalman filter) over the regression coefficients, with the trend
innovation variances fixed (the Laubach-Williams remedy for the pile-up
problem).  The level of r* is then pinned by a long-run-neutrality anchor (see
``estimate``).  Estimated parameters are returned for reference / the workbook.

State vector (9):
    [y*_t, y*_{t-1}, y*_{t-2}, g_t, g_{t-1}, g_{t-2}, z_t, z_{t-1}, z_{t-2}]
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..config import SETTINGS
from ..kalman import SSM, filter_smooth, loglik


@dataclass
class HLWResult:
    r_star: pd.Series
    output_gap: pd.Series
    trend_growth: pd.Series      # annualized %
    params: dict
    loglik: float


# Trend-innovation std devs are FIXED rather than estimated, following the
# Laubach-Williams remedy for the "pile-up" problem (MLE drives these to 0 or
# explodes).  Small values impose smooth, well-identified r* trends.
SIGMA_G = 0.08      # trend-growth innovation (quarterly, 100*log units)
SIGMA_Z = 0.08      # other-factor innovation (annualized %) - smoother z


def _build_ssm(theta: np.ndarray, c: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    a1, a2, a_r, b_pi, b_y = theta[:5]
    s_yp, s_e1, s_e2 = np.exp(theta[5:8])  # estimated std devs (positive)
    s_g, s_z = SIGMA_G, SIGMA_Z

    # State (after transition to t):
    #   [y*_t, y*_{t-1}, y*_{t-2}, g_t, g_{t-1}, g_{t-2}, z_t, z_{t-1}, z_{t-2}]
    # old state holds the t-1 values, so e.g. old_s0 = y*_{t-1}, old_s3 = g_{t-1}.
    m = 9
    T = np.zeros((m, m))
    # y*_t = y*_{t-1} + g_{t-1}
    T[0, 0] = 1.0
    T[0, 3] = 1.0
    # lags of y*
    T[1, 0] = 1.0
    T[2, 1] = 1.0
    # g_t = g_{t-1} (random walk) + lag shifts
    T[3, 3] = 1.0
    T[4, 3] = 1.0
    T[5, 4] = 1.0
    # z_t = z_{t-1} (random walk) + lag shifts
    T[6, 6] = 1.0
    T[7, 6] = 1.0
    T[8, 7] = 1.0

    Q = np.zeros((m, m))
    Q[0, 0] = s_yp ** 2      # potential output innovation
    Q[3, 3] = s_g ** 2       # trend-growth innovation
    Q[6, 6] = s_z ** 2       # other-factor innovation

    # Measurement loadings (see module docstring for the algebra).  The IS curve
    # uses a single real-rate lag (r_{t-1}-r*_{t-1}); a symmetric two-lag average
    # induces a spurious 2-quarter oscillation in the smoothed z.
    Z = np.zeros((2, m))
    Z[0, 0] = 1.0
    Z[0, 1] = -a1
    Z[0, 2] = -a2
    Z[0, 4] = 4.0 * a_r * c   # a_r*4c on g_{t-1}
    Z[0, 7] = a_r             # a_r on z_{t-1}
    Z[1, 1] = -b_y
    H = np.diag([s_e1 ** 2, s_e2 ** 2])
    return T, Z, Q, H


def _prep(df: pd.DataFrame):
    d = df.dropna(subset=["log_gdp", "inflation", "real_short_rate"]).copy()
    y = d["log_gdp"].to_numpy()
    pi = d["inflation"].to_numpy()
    r = d["real_short_rate"].to_numpy()
    n = len(d)
    pi_bar = np.full(n, np.nan)
    for t in range(n):
        if t >= 4:
            pi_bar[t] = np.mean(pi[t - 4:t - 1])  # avg of t-2..t-4
    return d, y, pi, r, pi_bar, n


def estimate(df: pd.DataFrame, c: float | None = None,
             restarts: int = 2, seed: int = 0,
             anchor_level: bool = True) -> HLWResult:
    """Estimate HLW r*.

    anchor_level : if True (default), apply the standard long-run-neutrality
        calibration - shift the level of the other-factor z so that the
        sample-average r* equals the sample-average ex-ante real policy rate
        (i.e. policy is neutral on average over the full sample).  This pins the
        otherwise weakly-identified *level* of r* without altering its dynamics.
    """
    c = SETTINGS.hlw.c_param if c is None else c
    d, y, pi, r, pi_bar, n = _prep(df)

    # Observed-data intercepts d_t are subtracted so the SSM has constant terms.
    # Vectorized for speed (called once per likelihood evaluation).
    def make_yadj(a1, a2, a_r, b_pi, b_y):
        yadj = np.full((n, 2), np.nan)
        yadj[2:, 0] = y[2:] - (a1 * y[1:-1] + a2 * y[:-2] - a_r * r[1:-1])
        yadj[4:, 1] = pi[4:] - (b_pi * pi[3:-1] + (1 - b_pi) * pi_bar[4:]
                                + b_y * y[3:-1])
        return yadj

    g0 = float(np.mean(np.diff(y)))      # full-sample avg growth (neutral start)
    a1 = np.full(9, y[0]); a1[3:6] = g0; a1[6:] = 0.0
    # tight prior on the (fixed-variance) trend states; loose on potential level
    P1 = np.diag([10., 10., 10., 0.25, 0.25, 0.25, 4., 4., 4.])

    def neg_ll(theta):
        a1c, a2c, a_r, b_pi, b_y = theta[:5]
        # gentle penalties to keep the model well-behaved / identified
        pen = 0.0
        if not (-2 < a1c < 2 and -2 < a2c < 2):
            pen += 1e3
        if a1c + a2c > 0.98:                 # IS-curve (near-)stationarity
            pen += 1e4 * (a1c + a2c - 0.98)
        if a_r <= 0:
            pen += 1e3 * (1 - a_r)
        if not (0 < b_pi < 1):
            pen += 1e3
        if b_y <= 0:
            pen += 1e3 * (1 - b_y)
        T, Z, Q, H = _build_ssm(theta, c)
        ssm = SSM(T=T, Z=Z, Q=Q, H=H, a1=a1.copy(), P1=P1.copy())
        yadj = make_yadj(a1c, a2c, a_r, b_pi, b_y)
        try:
            ll = loglik(yadj, ssm)
        except Exception:  # noqa: BLE001
            return 1e6
        if not np.isfinite(ll):
            return 1e6
        return -ll + pen

    rng = np.random.default_rng(seed)
    # theta: a1,a2,a_r,b_pi,b_y, log s_yp, log s_e1, log s_e2
    # (trend-growth and z innovation std devs are fixed: see SIGMA_G / SIGMA_Z)
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
        raise RuntimeError("HLW estimation failed to converge.")

    theta = best.x
    a1c, a2c, a_r, b_pi, b_y = theta[:5]
    T, Z, Q, H = _build_ssm(theta, c)
    ssm = SSM(T=T, Z=Z, Q=Q, H=H, a1=a1.copy(), P1=P1.copy())
    out = filter_smooth(make_yadj(a1c, a2c, a_r, b_pi, b_y), ssm)
    sm = out["smoothed"]

    g_t = sm[:, 3]            # quarterly trend growth (100*log units)
    z_t = sm[:, 6]
    yp = sm[:, 0]
    r_star = 4.0 * c * g_t + z_t
    gap = y - yp

    # Long-run-neutrality level calibration: on average over the full sample the
    # economy is at potential, so the average real policy rate should equal r*.
    level_shift = 0.0
    if anchor_level:
        level_shift = float(np.nanmean(r) - np.nanmean(r_star))
        r_star = r_star + level_shift
        z_t = z_t + level_shift

    idx = d.index
    s_yp, s_e1, s_e2 = np.exp(theta[5:8])
    s_g, s_z = SIGMA_G, SIGMA_Z
    params = {
        "a_y1": a1c, "a_y2": a2c, "a_r": a_r, "b_pi": b_pi, "b_y": b_y, "c": c,
        "sigma_ystar": s_yp, "sigma_g": s_g, "sigma_z": s_z,
        "sigma_ygap": s_e1, "sigma_pi": s_e2,
        "level_shift": level_shift,
    }
    return HLWResult(
        r_star=pd.Series(r_star, index=idx, name="HLW"),
        output_gap=pd.Series(gap, index=idx, name="output_gap"),
        trend_growth=pd.Series(4.0 * g_t, index=idx, name="trend_growth"),
        params=params,
        loglik=out["loglik"],
    )
