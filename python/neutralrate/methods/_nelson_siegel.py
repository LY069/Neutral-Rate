"""
Nelson-Siegel decomposition of a (real) yield curve.

The four natural-yield-curve methods in the BoJ survey (Imakubo-Kojima-Nakajima
2015, Nakajima et al. 2023, Goy-Iwasaki 2024, Hatayama-Iwasaki 2024 a.k.a. the
"Del Negro" column for Japan) are all built on a Nelson-Siegel decomposition of
the *whole* JGB curve into three factors - level, slope and curvature:

    y(tau) = beta_L
           + beta_S * (1 - e^{-lam*tau}) / (lam*tau)
           + beta_C * [ (1 - e^{-lam*tau}) / (lam*tau) - e^{-lam*tau} ]

with a fixed decay `lam`.  The LEVEL factor (the tau -> infinity yield) is the
long-run anchor of the curve; the short end is beta_L + beta_S; the slope factor
governs the term spread and the curvature factor the medium-maturity hump.

This module provides the loadings, a per-date least-squares fit, and an evaluator.
It is the curve engine the term-structure methods consume *when a full curve is
available* (i.e. once the MoF JGB curve is wired in - see data.py / config.py);
with only two maturities the methods fall back to the legacy 3m/10y midpoint.

NB: this is the (linear) Nelson-Siegel curve, not the shadow-rate term-structure
model Imakubo et al. use to respect the ZLB.  Adding a shadow-rate front end is
the remaining fidelity step for the deep ZLB years; see docs/03_faithfulness_audit.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Default decay (per YEAR).  ~0.7 places the curvature-loading peak near the
# 2-3y area of the curve, the usual choice for an annual-tenor fit.
DEFAULT_LAMBDA = 0.7

FACTOR_NAMES = ["ns_level", "ns_slope", "ns_curvature"]


def loadings(maturities, lam: float = DEFAULT_LAMBDA) -> np.ndarray:
    """(k, 3) Nelson-Siegel factor loadings for maturities `tau` (in years)."""
    tau = np.asarray(maturities, dtype=float)
    x = lam * tau
    # guard tau -> 0 (slope loading -> 1, curvature -> 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(x > 0, (1.0 - np.exp(-x)) / x, 1.0)
    curv = slope - np.exp(-x)
    return np.column_stack([np.ones_like(tau), slope, curv])


def fit_factors(curve: pd.DataFrame, lam: float = DEFAULT_LAMBDA,
                min_points: int = 4) -> pd.DataFrame:
    """Fit {level, slope, curvature} per date by OLS across maturities.

    Parameters
    ----------
    curve : DataFrame indexed by date, columns = maturities in YEARS (float),
            values = yields (any unit; reals in, reals out).  NaNs allowed
            (missing maturities are skipped in that date's fit).
    min_points : a date with fewer than this many observed maturities cannot
            identify three factors and gets NaN factors.

    Returns a DataFrame indexed like `curve` with columns FACTOR_NAMES.
    """
    mats = np.asarray(curve.columns, dtype=float)
    rows = {}
    for dt, row in curve.iterrows():
        y = np.asarray(row.values, dtype=float)
        m = np.isfinite(y)
        if int(m.sum()) < min_points:
            rows[dt] = [np.nan, np.nan, np.nan]
            continue
        L = loadings(mats[m], lam)
        beta, *_ = np.linalg.lstsq(L, y[m], rcond=None)
        rows[dt] = list(beta)
    return pd.DataFrame.from_dict(rows, orient="index", columns=FACTOR_NAMES)


def evaluate(factors: pd.DataFrame, tau: float,
             lam: float = DEFAULT_LAMBDA) -> pd.Series:
    """Evaluate the fitted curve at a single maturity `tau` (years) per date."""
    L = loadings([tau], lam)[0]                       # (3,)
    vals = factors[FACTOR_NAMES].to_numpy() @ L
    return pd.Series(vals, index=factors.index, name=f"ns_y_{tau:g}y")


def short_rate(factors: pd.DataFrame) -> pd.Series:
    """Instantaneous short rate = level + slope (tau -> 0)."""
    s = factors["ns_level"] + factors["ns_slope"]
    s.name = "ns_short"
    return s
