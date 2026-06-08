"""
Central configuration for the Japan Neutral Rate (r*) toolkit.

Everything that a user might want to change when refreshing or re-pointing the
models lives here:  the FRED series catalog, the target estimation frequency,
the estimation sample, and the calibrated parameters that the (deliberately
tractable) reduced-form implementations rely on.

The six methods replicated here follow the survey in:
    Nakano, Sugioka & Yamamoto (2024), "Recent Developments in Measuring the
    Natural Rate of Interest", Bank of Japan Working Paper No. 24-E-12,
    summarized in BOJ Review 2026-E-4 (rev26e04).

See docs/01_research_report.md for the full description of each method.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# Repository root, resolved robustly (handles ".." left in sys.path entries).
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --------------------------------------------------------------------------- #
# 1. FRED series catalog
# --------------------------------------------------------------------------- #
# Logical name -> FRED series id.  Change the right-hand side to re-point a
# model at a different source series (e.g. a different inflation measure).
#
# All series are public on https://fred.stlouisfed.org.  Mixed native
# frequencies are harmonized to quarterly in data.py.
FRED_SERIES: dict[str, str] = {
    # --- Activity (quarterly, seasonally adjusted, real) --------------------
    "real_gdp": "JPNRGDPEXP",          # Real GDP for Japan, SA, bn chained yen
    "consumption": "JPNPFCEQDSMEI",    # Private final consumption expenditure
    # --- Prices (monthly -> quarterly) -------------------------------------
    "cpi": "JPNCPIALLMINMEI",          # CPI, all items, index (fallback)
    "core_cpi_yoy": "CPGRLE01JPQ657N",  # Core CPI (ex food & energy), YoY %, Q
                                        # OECD - the HLW-appropriate inflation input
    # --- Interest rates (monthly -> quarterly averages) --------------------
    "short_rate": "IRSTCI01JPM156N",   # Call money / interbank, < 24h  (policy)
    "rate_3m": "IR3TIB01JPM156N",      # 3-month interbank rate
    "rate_10y": "IRLTLT01JPM156N",     # 10-year government bond yield
    # --- Demographics (for trend-growth / DSGE drivers) --------------------
    "working_age_pop": "LFWA64TTJPM647S",  # Working-age population (15-64)
}

# Maturities (in years) available for the term-structure / natural-yield-curve
# methods, mapped to the logical names above.  Extend this dict if you add more
# JGB maturities (e.g. from MOF data) to the Data sheet.
YIELD_CURVE_MATURITIES: dict[float, str] = {
    0.25: "rate_3m",
    10.0: "rate_10y",
}

# --------------------------------------------------------------------------- #
# 2. Estimation settings
# --------------------------------------------------------------------------- #
TARGET_FREQ = "QS"          # quarter start; pandas offset alias
SAMPLE_START = "1985-01-01"  # estimation start (data trimmed to availability)
SAMPLE_END = None            # None -> latest available

# Inflation expectations.
# FRED carries no clean, long-history, percentage-valued Japan inflation-
# expectations series (Japan breakeven rates are distorted by deflation-option
# and liquidity premia - see BOJ WP 20-E-5; the Cleveland Fed EXPINF series is
# US-only).  We therefore follow Holston-Laubach-Williams and build expected
# inflation as a moving average of *core* CPI inflation (the adaptive-
# expectations proxy).  If you DO have access to a percentage expectations or
# breakeven series on FRED, set its id here and it will be used directly.
INFLATION_EXPECTATIONS_SERIES: str | None = None   # e.g. a JGB breakeven id
INFLATION_EXPECTATION_WINDOW = 4   # quarters in the core-inflation MA proxy


# --------------------------------------------------------------------------- #
# 3. Calibrated structural parameters (reduced-form implementations)
# --------------------------------------------------------------------------- #
@dataclass
class DSGEParams:
    """Consumption-Euler parameters for the DSGE-consistent method (Okazaki &
    Sudo 2018).  In the steady state of these models:

        r*  =  rho  +  gamma * g_c

    where g_c is trend per-capita consumption growth, gamma is the inverse of
    the intertemporal elasticity of substitution, and rho is the (annualized)
    rate of time preference.  Defaults are mid-range values used in the BOJ
    DSGE literature; override to match your preferred calibration.
    """
    rho: float = 0.0          # annual %, time-preference / steady-state premium
    gamma: float = 1.0        # inverse EIS (1.0 = log utility)
    per_capita: bool = True   # divide consumption by working-age population


@dataclass
class HLWPriors:
    """Loose starting values / bounds for the HLW signal-to-noise parameters
    (Holston-Laubach-Williams).  Estimation refines these by MLE; they also
    seed the in-Excel Kalman recursion."""
    lambda_g: float = 0.05    # trend-growth smoothing ratio
    lambda_z: float = 0.03    # other-factor (z) smoothing ratio
    c_param: float = 1.0      # r* = 4*g + z scaling on g (4 for annualizing q/q)


@dataclass
class Settings:
    fred_api_key: str | None = field(
        default_factory=lambda: os.environ.get("FRED_API_KEY")
    )
    cache_dir: str = field(
        default_factory=lambda: os.environ.get(
            "NEUTRALRATE_CACHE", os.path.join(_ROOT, "data", "cache")
        )
    )
    sample_data_path: str = field(
        default_factory=lambda: os.path.join(
            _ROOT, "data", "sample", "japan_quarterly_sample.csv"
        )
    )
    dsge: DSGEParams = field(default_factory=DSGEParams)
    hlw: HLWPriors = field(default_factory=HLWPriors)


SETTINGS = Settings()
