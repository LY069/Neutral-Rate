"""
Shared trend-extraction for the methods that need a univariate stochastic trend
(the DSGE's trend consumption growth and the macro-finance trend growth input).

The natural rate is a slow-moving object, so - exactly as in the original
state-space papers - the trend is a local-linear-trend (I(2)) estimated by the
Kalman smoother with a *low signal-to-noise ratio* (small slope-shock variance
relative to the measurement variance).  That low signal-to-noise is what makes
r* smooth in HLW/Imakubo/Nakajima/Del Negro, and we reproduce it here rather
than bolting on a separate (HP) smoother.  The smoothness knob ``lam`` is the
ratio sigma_irregular^2 / sigma_slope^2 (numerically the Hodrick-Prescott
parameter, since HP is precisely the Kalman smoother of this model).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..kalman import SSM, filter_smooth

# Signal-to-noise (quarterly).  1600 = business-cycle trend; the large value
# gives the very smooth *secular* growth trend that anchors r*.
LAM_GAP = 1600.0
LAM_TREND = 1.0e5


def llt_decompose(series: pd.Series, lam: float = LAM_TREND):
    """Kalman local-linear-trend smoother of a series.

    state = [level, slope];  level is I(2) (no own shock), slope ~ random walk
    with variance 1, measurement variance = lam (so the trend-to-noise ratio is
    1/lam).  Returns (level, slope_quarterly) aligned to ``series.index``.
    """
    s = series.dropna()
    y = s.to_numpy(dtype=float).reshape(-1, 1)
    n = len(y)
    if n < 5:
        return s.copy(), s.diff().bfill()
    T = np.array([[1.0, 1.0], [0.0, 1.0]])
    Z = np.array([[1.0, 0.0]])
    Q = np.diag([0.0, 1.0])                 # sigma_level=0, sigma_slope=1
    H = np.array([[float(lam)]])            # sigma_irregular^2 = lam
    a1 = np.array([y[0, 0], float(np.mean(np.diff(y[:8, 0]))) if n > 8 else 0.0])
    P1 = np.diag([1e6, 1e6])
    sm = filter_smooth(y, SSM(T=T, Z=Z, Q=Q, H=H, a1=a1, P1=P1))["smoothed"]
    return (pd.Series(sm[:, 0], index=s.index),
            pd.Series(sm[:, 1], index=s.index))


def trend_growth(log_series: pd.Series, lam: float = LAM_TREND) -> pd.Series:
    """Annualized %, very smooth secular trend growth (4 * quarterly slope)."""
    _, slope = llt_decompose(log_series, lam)
    return 4.0 * slope


def output_gap(log_gdp: pd.Series):
    """Return (output_gap %, annualized secular trend growth %).

    Gap uses a business-cycle trend (LAM_GAP); trend growth uses the much
    smoother secular trend (LAM_TREND) - the object that anchors r*.
    """
    s = log_gdp.dropna()
    level_bc, _ = llt_decompose(s, LAM_GAP)
    gap = s.reindex(level_bc.index) - level_bc
    return gap, trend_growth(s, LAM_TREND)
