"""
Refresh the Japan macro panel from FRED.

    python scripts/refresh_data.py                # pull all series, update cache
    python scripts/refresh_data.py --excel        # also write into the Excel workbook
    python scripts/refresh_data.py --check        # print latest values, no write

Requires an internet connection.  Set a FRED API key for the robust JSON path:
    export FRED_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
Without a key it falls back to the no-key fredgraph CSV download.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neutralrate import data  # noqa: E402
from neutralrate.config import FRED_SERIES, SETTINGS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", action="store_true",
                    help="also push the refreshed raw panel into the workbook Data sheet")
    ap.add_argument("--check", action="store_true",
                    help="fetch and print latest values without writing the workbook")
    args = ap.parse_args()

    print("FRED series:")
    for k, v in FRED_SERIES.items():
        print(f"   {k:<18} {v}")
    print("API key:", "set" if SETTINGS.fred_api_key else "NOT set (using fredgraph)")

    raw = data.fetch_raw_panel()
    os.makedirs(SETTINGS.cache_dir, exist_ok=True)
    cache = os.path.join(SETTINGS.cache_dir, "raw_panel.csv")
    raw.to_csv(cache)
    print(f"\nFetched {len(raw)} quarters, {raw.index.min().date()} -> "
          f"{raw.index.max().date()}")

    # Per-series last valid (non-NaN) date - the quickest way to spot a
    # discontinued FRED series (which would freeze the dependent methods).
    print("Last valid observation by series (watch for any stuck in the past):")
    newest = raw.apply(lambda s: s.last_valid_index())
    overall = newest.max()
    for col in raw.columns:
        last = newest[col]
        flag = ""
        if last is not None and overall is not None:
            behind = (overall.to_period("Q") - last.to_period("Q")).n
            flag = f"   <-- STALE ({behind}q behind)" if behind > 2 else ""
        print(f"   {col:<18} {str(last.date()) if last is not None else 'EMPTY':<12}{flag}")

    print("\nLatest observations:")
    print(raw.tail(4).round(3).to_string())
    print(f"\nCache written: {cache}")

    if args.check:
        return
    if args.excel:
        here = os.path.dirname(__file__)
        wb = os.path.join(here, "..", "..", "excel", "Japan_Neutral_Rate_Models.xlsx")
        try:
            from build_workbook import write_data_sheet  # type: ignore
        except Exception:
            sys.path.insert(0, os.path.join(here, "..", "..", "excel"))
            from build_workbook import write_data_sheet  # type: ignore
        write_data_sheet(wb, data.build_features(raw))
        print(f"Updated workbook Data sheet: {wb}")


if __name__ == "__main__":
    main()
