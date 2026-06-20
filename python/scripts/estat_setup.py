"""
e-Stat API discovery helper — find the correct statsDataId and cdCat01 codes
for the Statistics Bureau of Japan 2020-base CPI tables.

This script does NOT pull any data — it searches the e-Stat catalogue and
prints the exact config.py lines to copy/paste.

Usage
-----
    export ESTAT_APP_ID="your_app_id"

    # List CPI tables from the Statistics Bureau:
    python scripts/estat_setup.py --search "consumer price index"

    # Show all cdCat01 item codes for a specific table (once you have its id):
    python scripts/estat_setup.py --meta 0003427113

    # Quick-check that a spec round-trips and returns recent data:
    python scripts/estat_setup.py --check "estat:0003427113:0020001"

The three-step workflow is:
    1. --search to find the right table id
    2. --meta  to find the item codes for "All items" and "less fresh food & energy"
    3. --check to verify the spec reaches today's data
    4. Copy the suggested lines into config.py and run refresh_data.py --check

The authoritative CPI table at the Statistics Bureau of Japan (SBJ) is:
    "Consumer Price Index, Japan, Monthly (2020-base)"
    https://www.e-stat.go.jp/en/stat-search/files?query=Consumer+Price+Index

Two series matter here:
    All-items CPI index (総合)                → config.CPI_INDEX_CANDIDATES
    All items less fresh food and energy      → config.CORE_CPI_CANDIDATES
      (生鮮食品及びエネルギーを除く総合)

Remember: set ADJUST_CONSUMPTION_TAX = False in config.py if you obtain the
BoJ "Indicators for Core CPI" tax-excluded series; keep it True if you pull
a raw SBJ index (tax still baked in).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import requests

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
ESTAT_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json"


def _app_id() -> str:
    aid = os.environ.get("ESTAT_APP_ID", "")
    if not aid:
        sys.exit(
            "ERROR: ESTAT_APP_ID environment variable is not set.\n"
            "Register for a free application ID at:\n"
            "  https://www.e-stat.go.jp/api/en/\n"
            "then: export ESTAT_APP_ID='your_app_id'"
        )
    return aid


def _get(endpoint: str, params: dict, retries: int = 3) -> dict:
    url = f"{ESTAT_BASE}/{endpoint}"
    params["appId"] = _app_id()
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"e-Stat request failed: {last_err}") from last_err


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

# The Statistics Bureau "Consumer Price Index" government-statistics code.
# Filtering getStatsList by statsCode is far more reliable than a free-text
# keyword: e-Stat's catalogue is indexed primarily in Japanese, so an English
# searchWord often returns nothing.
CPI_STATS_CODE = "00200573"           # 消費者物価指数 (Statistics Bureau)
CPI_KEYWORD_JA = "消費者物価指数"      # Japanese fallback keyword


def _run_search(params: dict) -> list[dict]:
    """Run one getStatsList query and normalise the TABLE_INF list."""
    data = _get("getStatsList", params)
    tables = (data.get("GET_STATS_LIST", {})
                  .get("DATALIST_INF", {})
                  .get("TABLE_INF", []))
    if isinstance(tables, dict):
        tables = [tables]
    return tables


def cmd_search(keyword: str) -> None:
    """Find CPI tables in the e-Stat catalogue.

    Strategy (most reliable first):
      1. by the Statistics Bureau CPI statsCode (00200573) — no keyword needed;
      2. fall back to the Japanese keyword 消費者物価指数 if (1) is empty;
      3. finally the user's free-text keyword.
    No statsField/surveyYears restriction (those filtered out current data)."""
    tables: list[dict] = []
    used = ""
    # 1. statsCode — the robust path
    try:
        tables = _run_search({"statsCode": CPI_STATS_CODE, "limit": 50})
        used = f"statsCode={CPI_STATS_CODE}"
    except Exception:  # noqa: BLE001
        tables = []
    # 2. Japanese keyword fallback
    if not tables:
        tables = _run_search({"searchWord": CPI_KEYWORD_JA, "limit": 50})
        used = f"searchWord='{CPI_KEYWORD_JA}'"
    # 3. the user's keyword, last resort
    if not tables:
        tables = _run_search({"searchWord": keyword, "limit": 50})
        used = f"searchWord='{keyword}'"

    print(f"Searched e-Stat ({used}).\n")
    if not tables:
        print("No tables found even by statsCode. Check ESTAT_APP_ID is valid and")
        print("that your network can reach api.e-stat.go.jp. You can also browse the")
        print("table manually at https://www.e-stat.go.jp/en/stat-search/files and read")
        print("its statsDataId from the URL, then go straight to --meta <id>.")
        return

    # Prefer monthly, all-Japan, 2020-base tables — surface those first.
    def _score(t: dict) -> int:
        title = t.get("TITLE", {})
        title = title.get("$", "") if isinstance(title, dict) else str(title)
        blob = (title + str(t.get("CYCLE", "")) + str(t.get("STATISTICS_NAME", ""))).lower()
        s = 0
        if "monthly" in blob or "月" in blob:
            s += 2
        if "2020" in blob:
            s += 2
        if "all japan" in blob or "全国" in blob:
            s += 1
        return -s  # sort ascending -> best first

    tables.sort(key=_score)

    print(f"{'ID':<16} Title  (cycle, latest survey)")
    print("-" * 90)
    for t in tables[:30]:
        tid = t.get("@id", "?")
        title = t.get("TITLE", {})
        if isinstance(title, dict):
            title = title.get("$", title.get("#text", "?"))
        stat_name = t.get("STATISTICS_NAME", "")
        cycle = t.get("CYCLE", "")
        survey_date = t.get("SURVEY_DATE", "")
        print(f"  {tid:<14} {stat_name} {title} ({cycle}, {survey_date})")

    print(f"\nFound {len(tables)} table(s). Pick the MONTHLY, 2020-base, all-Japan one")
    print("(its title mentions '2020-base', 'Monthly', 'All Japan' / '全国'), then run:")
    print("    python3 scripts/estat_setup.py --meta <that ID>")


def cmd_meta(stats_id: str) -> None:
    """Fetch all cdCat01 item codes for a table and print config suggestions."""
    print(f"Fetching metadata for statsDataId={stats_id} ...\n")
    data = _get("getMetaInfo", {"statsDataId": stats_id, "lang": "E"})
    meta = (data.get("GET_META_INFO", {})
                .get("METADATA_INF", {})
                .get("CLASS_INF", {})
                .get("CLASS_OBJ", []))
    if isinstance(meta, dict):
        meta = [meta]

    # Find the category dimension (usually id='cat01' or similar)
    cat_obj = next((m for m in meta if "cat01" in str(m.get("@id", "")).lower()), None)
    if cat_obj is None:
        print("Could not find a cat01 dimension. Full CLASS_OBJ keys:")
        for m in meta:
            print(f"  @id={m.get('@id')} @name={m.get('@name')}")
        return

    items = cat_obj.get("CLASS", [])
    if isinstance(items, dict):
        items = [items]

    print(f"{'Code':<14} Name")
    print("-" * 70)
    for item in items:
        code = item.get("@code", "?")
        name = item.get("@name", "?")
        print(f"  {code:<12} {name}")

    # Heuristic: guess which codes are "All items" and "less fresh food & energy"
    all_items_code = next(
        (i.get("@code") for i in items if "all item" in str(i.get("@name", "")).lower()),
        None
    )
    core_core_code = next(
        (i.get("@code") for i in items
         if "fresh food" in str(i.get("@name", "")).lower()
         and "energy" in str(i.get("@name", "")).lower()),
        None
    )

    print("\n" + "=" * 70)
    print("Suggested config.py entries (paste into python/neutralrate/config.py)")
    print("=" * 70)
    if all_items_code:
        print(f'\n# All-items CPI index (add to CPI_INDEX_CANDIDATES, first position):')
        print(f'    "estat:{stats_id}:{all_items_code}",  # SBJ 2020-base CPI all items')
    else:
        print('\n# Could not auto-detect "All items" code; check the list above.')
        print(f'    "estat:{stats_id}:<CODE>",')

    if core_core_code:
        print(f'\n# Core-core (less fresh food & energy) — for CORE_CPI_CANDIDATES:')
        print(f'    "estat:{stats_id}:{core_core_code}",  # SBJ 2020-base core-core index')
        print(f'\n# NOTE: this is the raw INDEX (tax not excluded).')
        print(f'# Set ADJUST_CONSUMPTION_TAX = True in config.py (default).')
        print(f'# OR run scripts/build_core_core.py --raw "estat:{stats_id}:{core_core_code}"')
        print(f'# to produce the tax-excluded YoY file; then set ADJUST_CONSUMPTION_TAX = False.')
    else:
        print('\n# Could not auto-detect "less fresh food & energy" code; check list above.')
        print(f'    "estat:{stats_id}:<CODE>",')

    print(f"\nVerify with: python scripts/estat_setup.py --check \"estat:{stats_id}:{all_items_code or '<CODE>'}\"")


def cmd_check(spec: str) -> None:
    """Verify that a spec string fetches data and print summary stats."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from neutralrate import data  # noqa: E402

    print(f"Checking: {spec}")
    print("Fetching (this may take a moment for large tables) ...")
    try:
        s = data.fetch_any(spec).dropna()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)

    if s.empty:
        print("FAIL: returned empty series.")
        sys.exit(1)

    print(f"OK:")
    print(f"  Length:      {len(s)} observations")
    print(f"  First date:  {s.index.min().date()}")
    print(f"  Last date:   {s.index.max().date()}")
    print(f"  Value range: {s.min():.2f} .. {s.max():.2f}")

    import pandas as pd
    lag_months = (pd.Timestamp.now() - s.index.max()).days // 30
    if lag_months <= 3:
        print(f"  Recency:     CURRENT (last obs {lag_months}m ago) ✓")
    elif lag_months <= 12:
        print(f"  Recency:     WARNING — last obs {lag_months}m ago; SBJ usually publishes within ~6 weeks")
    else:
        print(f"  Recency:     STALE — last obs {lag_months}m ago; check statsDataId/cdCat01")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="e-Stat API discovery: find statsDataId and cdCat01 codes for Japan CPI."
    )
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--search", metavar="KEYWORD",
                     help="search the e-Stat catalogue (e.g. 'consumer price index')")
    grp.add_argument("--meta", metavar="STATSDATAID",
                     help="show item codes for a specific table id")
    grp.add_argument("--check", metavar="SPEC",
                     help="verify a spec (e.g. 'estat:0003427113:0020001') fetches recent data")
    args = ap.parse_args()

    if args.search:
        cmd_search(args.search)
    elif args.meta:
        cmd_meta(args.meta)
    elif args.check:
        cmd_check(args.check)


if __name__ == "__main__":
    main()
