"""
Refreshable data layer for the Japan r* toolkit.

Pulls the Japan series defined in ``config.FRED_SERIES`` from FRED and
harmonizes them to a single quarterly panel that every method consumes.

Two fetch paths, tried in order:
    1. FRED API   (if FRED_API_KEY is set) -> JSON, robust, dated vintages.
    2. fredgraph  (no key needed)          -> CSV download.

If neither network path is reachable (e.g. an offline / locked-down
environment), ``load_panel(offline=True)`` falls back to the bundled synthetic
sample so the rest of the toolkit still runs and can be tested.

The cleaned panel is cached to ``data/cache`` and (when used by the Excel
builder) written into the workbook's Data sheet.
"""
from __future__ import annotations

import io
import os
import time

import numpy as np
import pandas as pd
import requests

from .config import (
    FRED_SERIES,
    INFLATION_EXPECTATION_WINDOW,
    SAMPLE_END,
    SAMPLE_START,
    SETTINGS,
    TARGET_FREQ,
)

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FREDGRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Native frequency hints -> how to aggregate to quarterly.
# "mean"  : average within the quarter (rates, indices read as levels)
# "last"  : end-of-quarter value
# Activity series are already quarterly and pass through.
AGG_RULE: dict[str, str] = {
    "short_rate": "mean",
    "rate_3m": "mean",
    "rate_10y": "mean",
    "cpi": "mean",
    "working_age_pop": "mean",
}


# --------------------------------------------------------------------------- #
# Low-level single-series fetch
# --------------------------------------------------------------------------- #
def _fetch_fred_api(series_id: str, api_key: str, retries: int = 4) -> pd.Series:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": SAMPLE_START,
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(FRED_API_URL, params=params, timeout=30)
            r.raise_for_status()
            obs = r.json()["observations"]
            idx = pd.to_datetime([o["date"] for o in obs])
            vals = pd.to_numeric(
                [o["value"] if o["value"] != "." else np.nan for o in obs],
                errors="coerce",
            )
            return pd.Series(vals, index=idx, name=series_id)
        except Exception as exc:  # noqa: BLE001 - retry w/ backoff
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"FRED API fetch failed for {series_id}: {last_err}")


def _fetch_fredgraph(series_id: str, retries: int = 4) -> pd.Series:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(
                FREDGRAPH_URL,
                params={"id": series_id},
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (neutralrate)"},
            )
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = ["date", "value"]
            df["date"] = pd.to_datetime(df["date"])
            s = pd.to_numeric(df["value"], errors="coerce")
            s.index = df["date"]
            s.name = series_id
            return s
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"fredgraph fetch failed for {series_id}: {last_err}")


def fetch_series(series_id: str) -> pd.Series:
    """Fetch one FRED series, preferring the API key path."""
    if SETTINGS.fred_api_key:
        return _fetch_fred_api(series_id, SETTINGS.fred_api_key)
    return _fetch_fredgraph(series_id)


# --------------------------------------------------------------------------- #
# Build the quarterly panel
# --------------------------------------------------------------------------- #
def _to_quarterly(s: pd.Series, logical_name: str) -> pd.Series:
    rule = AGG_RULE.get(logical_name)
    if rule is None:  # already quarterly activity series
        q = s.resample(TARGET_FREQ).mean()
    elif rule == "last":
        q = s.resample(TARGET_FREQ).last()
    else:
        q = s.resample(TARGET_FREQ).mean()
    return q


def fetch_raw_panel() -> pd.DataFrame:
    """Fetch every configured series from FRED and align to quarterly."""
    cols = {}
    for logical, fred_id in FRED_SERIES.items():
        raw = fetch_series(fred_id)
        cols[logical] = _to_quarterly(raw, logical)
    panel = pd.DataFrame(cols)
    if SAMPLE_END:
        panel = panel.loc[:SAMPLE_END]
    panel = panel.loc[SAMPLE_START:]
    return panel


# --------------------------------------------------------------------------- #
# Derived variables used by the models
# --------------------------------------------------------------------------- #
def build_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Construct the model-ready variables (logs, gaps, real rates, inflation).

    Columns added (annualized %, unless noted):
      log_gdp           : 100 * ln(real GDP)
      log_cons          : 100 * ln(real consumption [per working-age head])
      gdp_growth        : annualized q/q real GDP growth
      cons_growth       : annualized q/q (per-capita) consumption growth
      inflation         : annualized q/q CPI inflation
      inflation_yoy     : 4-quarter CPI inflation
      exp_inflation     : trailing 4q average of inflation (expectations proxy)
      real_short_rate   : short_rate - exp_inflation     (ex-ante real policy)
      real_10y          : rate_10y  - exp_inflation
      output_gap        : 100*(log_gdp - HP/one-sided trend)   [filled in by methods]
    """
    df = panel.copy()

    df["log_gdp"] = 100.0 * np.log(df["real_gdp"])
    cons = df["consumption"]
    if SETTINGS.dsge.per_capita and "working_age_pop" in df:
        cons = cons / df["working_age_pop"]
    df["log_cons"] = 100.0 * np.log(cons)

    # annualized q/q growth = 4 * 100 * dln
    df["gdp_growth"] = 4.0 * df["log_gdp"].diff()
    df["cons_growth"] = 4.0 * df["log_cons"].diff()

    # CPI inflation
    log_cpi = 100.0 * np.log(df["cpi"])
    df["inflation"] = 4.0 * log_cpi.diff()
    df["inflation_yoy"] = log_cpi.diff(4)
    df["exp_inflation"] = (
        df["inflation"].rolling(INFLATION_EXPECTATION_WINDOW, min_periods=1).mean()
    )

    # ex-ante real rates
    df["real_short_rate"] = df["short_rate"] - df["exp_inflation"]
    df["real_10y"] = df["rate_10y"] - df["exp_inflation"]
    df["real_3m"] = df["rate_3m"] - df["exp_inflation"]

    return df


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #
def load_panel(offline: bool = False, use_cache: bool = True) -> pd.DataFrame:
    """Return the model-ready quarterly feature panel.

    Parameters
    ----------
    offline   : if True, load the bundled synthetic sample (no network).
    use_cache : if True, reuse a previously refreshed cache when present.
    """
    if offline:
        raw = pd.read_csv(SETTINGS.sample_data_path, index_col=0, parse_dates=True)
        return build_features(raw)

    cache_file = os.path.join(SETTINGS.cache_dir, "raw_panel.csv")
    if use_cache and os.path.exists(cache_file):
        raw = pd.read_csv(cache_file, index_col=0, parse_dates=True)
    else:
        raw = fetch_raw_panel()
        os.makedirs(SETTINGS.cache_dir, exist_ok=True)
        raw.to_csv(cache_file)
    return build_features(raw)


def refresh(offline: bool = False) -> pd.DataFrame:
    """Force a fresh pull from FRED, overwrite the cache, return features."""
    if offline:
        return load_panel(offline=True)
    raw = fetch_raw_panel()
    os.makedirs(SETTINGS.cache_dir, exist_ok=True)
    raw.to_csv(os.path.join(SETTINGS.cache_dir, "raw_panel.csv"))
    return build_features(raw)
