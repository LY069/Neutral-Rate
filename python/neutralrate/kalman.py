"""
Minimal, transparent linear-Gaussian Kalman filter + smoother.

Kept deliberately simple and dependency-light (numpy only) so that the *same*
recursion can be mirrored cell-by-cell in the Excel workbook.  Used by the HLW,
natural-yield-curve and common-trends methods.

State-space form
----------------
    x_t = T x_{t-1} + c + R eta_t,      eta_t ~ N(0, Q)
    y_t = Z x_t     + d + eps_t,        eps_t ~ N(0, H)

Handles missing observations (NaN rows in y) by skipping the update step.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SSM:
    T: np.ndarray   # (m, m)
    Z: np.ndarray   # (k, m)
    Q: np.ndarray   # (m, m)  state covariance (R Q R')
    H: np.ndarray   # (k, k)  obs covariance
    c: np.ndarray | None = None   # (m,) state intercept
    d: np.ndarray | None = None   # (k,) obs intercept
    a1: np.ndarray | None = None  # (m,) initial state mean
    P1: np.ndarray | None = None  # (m, m) initial state cov


def _diffuse_init(m: int, scale: float = 1e6) -> tuple[np.ndarray, np.ndarray]:
    return np.zeros(m), np.eye(m) * scale


def filter_smooth(y: np.ndarray, ssm: SSM, smooth: bool = True):
    """Run the Kalman filter and (optionally) the RTS smoother.

    Parameters
    ----------
    y      : (n, k) observations (NaN allowed).
    smooth : if False, skip the backward smoother (used during MLE, where only
             the log-likelihood is needed -> roughly halves the cost per eval).

    Returns
    -------
    dict with 'loglik', 'filtered' (n,m), 'smoothed' (n,m),
    'filtered_cov' (n,m,m), 'smoothed_cov' (n,m,m).  When smooth=False the
    'smoothed*' entries alias the filtered ones.
    """
    y = np.atleast_2d(y)
    n, k = y.shape
    m = ssm.T.shape[0]
    T, Z, Q, H = ssm.T, ssm.Z, ssm.Q, ssm.H
    c = np.zeros(m) if ssm.c is None else ssm.c
    d = np.zeros(k) if ssm.d is None else ssm.d

    a, P = (ssm.a1, ssm.P1) if ssm.a1 is not None else _diffuse_init(m)
    if ssm.P1 is not None:
        P = ssm.P1

    a_pred = np.zeros((n, m))
    P_pred = np.zeros((n, m, m))
    a_filt = np.zeros((n, m))
    P_filt = np.zeros((n, m, m))
    loglik = 0.0

    for t in range(n):
        # --- predict ---
        a = T @ a + c
        P = T @ P @ T.T + Q
        a_pred[t], P_pred[t] = a, P

        # --- update (handle missing) ---
        yt = y[t]
        mask = ~np.isnan(yt)
        if mask.any():
            Zt = Z[mask]
            Ht = H[np.ix_(mask, mask)]
            dt = d[mask]
            v = yt[mask] - (Zt @ a + dt)
            F = Zt @ P @ Zt.T + Ht
            Finv = np.linalg.pinv(F)
            K = P @ Zt.T @ Finv
            a = a + K @ v
            P = P - K @ Zt @ P
            sign, logdet = np.linalg.slogdet(F)
            loglik += -0.5 * (mask.sum() * np.log(2 * np.pi) + logdet + v @ Finv @ v)
        a_filt[t], P_filt[t] = a, P

    if not smooth:
        return {
            "loglik": loglik,
            "filtered": a_filt,
            "smoothed": a_filt,
            "filtered_cov": P_filt,
            "smoothed_cov": P_filt,
        }

    # --- RTS smoother ---
    a_smooth = a_filt.copy()
    P_smooth = P_filt.copy()
    jitter = np.eye(m) * 1e-8
    for t in range(n - 2, -1, -1):
        Pp = P_pred[t + 1]
        A = P_filt[t] @ T.T                       # J = A @ Pp^{-1}
        J = np.linalg.solve(Pp + jitter, A.T).T   # faster/stabler than pinv
        a_smooth[t] = a_filt[t] + J @ (a_smooth[t + 1] - a_pred[t + 1])
        P_smooth[t] = P_filt[t] + J @ (P_smooth[t + 1] - Pp) @ J.T

    return {
        "loglik": loglik,
        "filtered": a_filt,
        "smoothed": a_smooth,
        "filtered_cov": P_filt,
        "smoothed_cov": P_smooth,
    }


def loglik(y: np.ndarray, ssm: SSM) -> float:
    """Filter-only log-likelihood (no smoother) - for use inside optimizers."""
    return filter_smooth(y, ssm, smooth=False)["loglik"]
