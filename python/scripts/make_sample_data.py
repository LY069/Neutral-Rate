"""
Generate a SYNTHETIC quarterly sample panel for offline testing.

This is NOT real data.  It is a deterministic, plausible-looking stand-in that
matches the raw-panel schema expected by neutralrate.data.build_features, so the
six methods can be run and tested without network access to FRED.  On a machine
with FRED access, use scripts/refresh_data.py to pull the real series.

Schema (columns) == logical names in config.FRED_SERIES:
    real_gdp, consumption, cpi, short_rate, rate_3m, rate_10y, working_age_pop
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample",
                   "japan_quarterly_sample.csv")


def build() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    idx = pd.date_range("1985-01-01", "2025-10-01", freq="QS")
    n = len(idx)
    t = np.arange(n)
    yrs = t / 4.0

    # Trend growth: ~4% (1985) declining toward ~0.5% (2020s).
    g_annual = 4.0 * np.exp(-yrs / 22.0) + 0.5
    g_q = g_annual / 4.0 / 100.0
    cycle = 1.5 * np.sin(2 * np.pi * yrs / 8.0) / 100.0   # ~8y business cycle
    log_gdp = np.cumsum(g_q + cycle / 4.0 + rng.normal(0, 0.003, n))
    real_gdp = 350000.0 * np.exp(log_gdp)
    consumption = 0.55 * real_gdp * np.exp(rng.normal(0, 0.004, n))

    # CPI: deflation 1998-2012, reflation from 2014, jump from 2022.
    infl = np.where(yrs < 5, 1.5,
            np.where(yrs < 13, 0.3,
            np.where(yrs < 27, -0.3,
            np.where(yrs < 37, 0.6, 2.6))))
    infl = infl + rng.normal(0, 0.3, n)
    cpi = 60.0 * np.exp(np.cumsum(infl / 4.0 / 100.0))
    # Synthetic "core CPI YoY %" (smoother, ex food&energy): 4q-smoothed infl.
    core_cpi_yoy = pd.Series(infl).rolling(4, min_periods=1).mean().to_numpy()

    # Policy / call rate: high late-80s, ZIRP from ~1999, NIRP 2016-2024.
    call = np.where(yrs < 6, 6.0 - 0.4 * yrs,
            np.where(yrs < 14, np.maximum(0.1, 4.0 - 0.5 * (yrs - 6)),
            np.where(yrs < 31, 0.1,
            np.where(yrs < 39, -0.1, 0.25 + 0.15 * (yrs - 39)))))
    call = call + rng.normal(0, 0.05, n)
    rate_3m = call + 0.2 + rng.normal(0, 0.03, n)

    # 10y JGB: term spread over call, compressed in QQE/YCC era.
    spread = np.where(yrs < 31, 1.8, np.where(yrs < 39, 0.6, 1.0))
    rate_10y = np.maximum(0.0, call + spread + rng.normal(0, 0.1, n))

    # Working-age population (mn): peak ~1995 then decline.
    wap = 86.0 - 0.10 * np.maximum(0, yrs - 10) + rng.normal(0, 0.05, n)

    df = pd.DataFrame({
        "real_gdp": real_gdp,
        "consumption": consumption,
        "cpi": cpi,
        "core_cpi_yoy": core_cpi_yoy,
        "short_rate": call,
        "rate_3m": rate_3m,
        "rate_10y": rate_10y,
        "working_age_pop": wap,
    }, index=idx)
    df.index.name = "date"
    return df


def main():
    df = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT)
    print(f"Wrote synthetic sample: {os.path.abspath(OUT)}  ({len(df)} quarters)")


if __name__ == "__main__":
    main()
