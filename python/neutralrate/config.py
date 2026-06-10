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
    "consumption": "NAEXKP02JPQ659S",  # Private final consumption, CONSTANT
                                       # prices (real), SA.  NB: the superficially
                                       # similar JPNPFCEQDSMEI is CURRENT prices
                                       # (nominal) and discontinued - do not use.
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
# The original papers treat expected inflation in THREE different ways, and the
# toolkit mirrors that:
#   * HLW (semi-structural): adaptive, backward-looking - a 4q moving average of
#     core inflation.  -> exp_inflation below.
#   * Okazaki-Sudo (DSGE): model-consistent rational expectations - no external
#     series is used at all.
#   * Imakubo, Nakajima, Goy-Iwasaki, Del Negro (term-structure / common-trends):
#     SURVEY-BASED, maturity-specific expectations used to deflate the nominal
#     yield curve (Consensus Forecasts in Japan; long-run SPF in Del Negro).
#
# FRED carries no clean, long-history, percentage Japan inflation-expectations
# series.  The best REAL sources are from the Bank of Japan and aggregators:
#   * BoJ Tankan "Inflation Outlook of Enterprises" - firms' expected CPI at
#     1y/3y/5y (%, from 2014) - BoJ Time-Series Data Search (stat-search.boj.or.jp)
#   * BoJ "Opinion Survey on the General Public" - households' 1y/5y (%, from 2006)
#   * BoJ composite indicator (firms + households + experts: QUICK survey,
#     Consensus Forecasts, inflation swaps)
#   * DBnomics (api.db.nomics.world) mirrors BoJ Tankan + OECD with a free API
#   * Japan breakevens / inflation swaps (Bloomberg/Refinitiv; distorted, BOJ WP 20-E-5)
#
# Each hook below accepts ANY of:
#   - a FRED series id            e.g. "T10YIE"          (fetched from FRED)
#   - a DBnomics code "PROV/DATASET/SERIES"              (fetched from DBnomics)
#   - a local CSV path with date,value columns           e.g. "data/boj_tankan_1y.csv"
# Because BoJ surveys are short, a configured series is SPLICED onto the proxy:
# the survey value is used where available, the proxy fills the earlier history.
# If a source is missing/empty/unreachable, the toolkit warns and uses the proxy
# (a SHORT 4q MA of core, and a LONG-horizon multi-year "anchored" MA of core).
#
# PRE-WIRED to the BoJ Tankan "Inflation Outlook of Enterprises" CSVs shipped in
# data/expectations/ (see that folder's README for how to populate them from the
# BoJ Time-Series Data Search).  Until you paste in the BoJ data the templates
# are empty, so the proxy is used automatically.  To fetch live instead, replace
# a path with a DBnomics code, e.g.:
#     INFLATION_EXPECTATIONS_LONG_SERIES = "BOJ/TK/CO'..."   # 5y Tankan outlook
_EXP_DIR = os.path.join(_ROOT, "data", "expectations")
INFLATION_EXPECTATIONS_SERIES: str | None = os.path.join(   # short / ~1y
    _EXP_DIR, "japan_infl_exp_1y.csv")
INFLATION_EXPECTATIONS_LONG_SERIES: str | None = os.path.join(  # long / ~5y
    _EXP_DIR, "japan_infl_exp_5y.csv")
INFLATION_EXPECTATION_WINDOW = 4    # quarters in the short (HLW) MA proxy
INFLATION_EXPECTATION_LONG_WINDOW = 20   # quarters in the long-run anchor proxy

# --------------------------------------------------------------------------- #
# Consumption-tax adjustment (Japan-specific, important)
# --------------------------------------------------------------------------- #
# Japan's consumption-tax hikes mechanically lift YoY CPI inflation for the
# four quarters following each hike.  BoJ analysis works with TAX-ADJUSTED CPI;
# unadjusted, the spikes contaminate expected inflation and ex-ante real rates
# precisely at sample-sensitive moments.  Estimated YoY effects (percentage
# points, headline/core; BoJ put the April-2014 hike at ~+2.0pp for FY2014):
#   1989Q2-1990Q1  introduction at 3%          ~ +1.2
#   1997Q2-1998Q1  3% -> 5%                    ~ +1.5
#   2014Q2-2015Q1  5% -> 8%                    ~ +2.0
#   2019Q4-2020Q3  8% -> 10% (food kept at 8%,
#                   free-education offsets)    ~ +0.5
# Applied to the YoY inflation path when ADJUST_CONSUMPTION_TAX is True.
ADJUST_CONSUMPTION_TAX = True
CONSUMPTION_TAX_EFFECTS: list[tuple[str, str, float]] = [
    ("1989-04-01", "1990-03-31", 1.2),
    ("1997-04-01", "1998-03-31", 1.5),
    ("2014-04-01", "2015-03-31", 2.0),
    ("2019-10-01", "2020-09-30", 0.5),
]


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
    """HLW settings. The trend-shock std devs are fixed in the LW engine
    (methods/_lw.py, SIGMA_G/SIGMA_Z - the low signal-to-noise that smooths r*);
    here we expose only the growth-loading c (r* = 4*c*g + z)."""
    c_param: float = 1.0      # r* = 4*c*g + z scaling on g (4 for annualizing q/q)


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
