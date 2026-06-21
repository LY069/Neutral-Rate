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
    ADJUST_CONSUMPTION_TAX,
    CONSUMPTION_TAX_EFFECTS,
    CONSUMPTION_TAX_LEVEL_EFFECTS,
    CORE_CPI_CANDIDATES,
    CPI_INDEX_CANDIDATES,
    FRED_SERIES,
    INFLATION_EXPECTATION_LONG_WINDOW,
    INFLATION_EXPECTATION_WINDOW,
    INFLATION_EXPECTATIONS_LONG_SERIES,
    INFLATION_EXPECTATIONS_SERIES,
    JGB_CURVE_MATURITIES,
    MOF_JGB_CURVE_SOURCE,
    NELSON_SIEGEL_LAMBDA,
    SAMPLE_END,
    SAMPLE_START,
    SETTINGS,
    TARGET_FREQ,
    USE_FULL_CURVE,
    jgb_col,
)
from .methods import _nelson_siegel as _ns

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FREDGRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
DBNOMICS_URL = "https://api.db.nomics.world/v22/series"

# Native frequency hints -> how to aggregate to quarterly.
# "mean"  : average within the quarter (rates, indices read as levels)
# "last"  : end-of-quarter value
# Activity series are already quarterly and pass through.
AGG_RULE: dict[str, str] = {
    "short_rate": "mean",
    "rate_3m": "mean",
    "rate_10y": "mean",
    "cpi": "mean",
    "core_cpi_yoy": "mean",
    "inflation_expectations": "mean",
    "inflation_expectations_long": "mean",
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


def _fetch_dbnomics(code: str, retries: int = 4) -> pd.Series:
    """Fetch a DBnomics series 'PROVIDER/DATASET/SERIES' (e.g. BoJ Tankan, OECD).

    DBnomics (api.db.nomics.world) is a free aggregator that mirrors Bank of
    Japan Time-Series data and OECD surveys - the practical way to pull Japan
    inflation-expectations series programmatically.
    """
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(f"{DBNOMICS_URL}/{code}",
                             params={"observations": "1"}, timeout=30)
            r.raise_for_status()
            docs = r.json()["series"]["docs"][0]
            idx = pd.to_datetime(docs["period"])
            vals = pd.to_numeric(pd.Series(docs["value"]), errors="coerce")
            vals.index = idx
            vals.name = code
            return vals
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"DBnomics fetch failed for {code}: {last_err}")


def _estat_time_to_date(t: str):
    """Decode an e-Stat 10-digit @time code to a month-start Timestamp.
    Monthly codes carry the month in positions [6:8] (year in [0:4]); codes
    with no month are treated as annual (December).  Returns None if unparseable."""
    t = str(t)
    if len(t) < 4 or not t[:4].isdigit():
        return None
    year = int(t[:4])
    mm = t[6:8] if len(t) >= 8 else ""
    if mm.isdigit() and 1 <= int(mm) <= 12:
        return pd.Timestamp(year, int(mm), 1)
    return pd.Timestamp(year, 12, 1)


ESTAT_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"


ESTAT_ALL_JAPAN_AREA = "00000"   # CPI area code for 全国 (All Japan)


def _estat_pick_index_series(values: list[dict]) -> pd.Series:
    """An e-Stat CPI table is a CUBE: item x area x tabulation(index/YoY/MoM) x time.
    Filtering by cdCat01 alone still returns MULTIPLE series (e.g. the index AND its
    year-on-year change, possibly several areas), which - collapsed naively to one
    value per date - yields garbage (mixed index/percent, divide-by-zero in log).

    This groups the returned VALUE rows by their full dimension key (every @attr
    except @time/@unit/$) and selects ONE clean monthly INDEX series: the group
    whose values look like a CPI index (median in ~[40, 1000], i.e. ~100, not a
    small percent change), preferring the all-Japan area and the longest history."""
    groups: dict[tuple, list[tuple]] = {}
    for v in values:
        d = _estat_time_to_date(v.get("@time", ""))
        if d is None:
            continue
        try:
            val = float(v["$"])
        except (ValueError, TypeError, KeyError):
            continue
        key = tuple(sorted((k, str(val2)) for k, val2 in v.items()
                           if k.startswith("@") and k not in ("@time", "@unit")))
        groups.setdefault(key, []).append((d, val))

    if not groups:
        raise RuntimeError("e-Stat response carried no decodable VALUE rows")

    def _series(rows):
        s = pd.Series([x[1] for x in rows], index=pd.to_datetime([x[0] for x in rows]))
        return s.sort_index()[lambda z: ~z.index.duplicated(keep="last")]

    scored = []
    for key, rows in groups.items():
        s = _series(rows)
        med = s.abs().median()
        index_like = 40.0 <= med <= 5000.0          # CPI index ~100; YoY% ~1-3
        all_japan = any(k.endswith("area") and v == ESTAT_ALL_JAPAN_AREA for k, v in key)
        scored.append((index_like, all_japan, len(s), s))
    # prefer index-like, then all-Japan, then longest
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    best = scored[0]
    if not best[0]:
        raise RuntimeError("e-Stat returned no index-like series for this filter "
                           "(values look like a percent change, not an index); "
                           "specify the index tabulation via :area:tab in the spec")
    return best[3]


def _fetch_estat(spec: str, retries: int = 4) -> pd.Series:
    """Fetch a CPI INDEX series from the Statistics Bureau of Japan via e-Stat.

    spec form: 'estat:STATSDATAID[:CDCAT01[:CDAREA[:CDTAB]]]'
      CDCAT01 - item code (e.g. CPI 'All items less fresh food and energy')
      CDAREA  - area code (defaults to all-Japan 00000); pass '' to leave open
      CDTAB   - tabulation code (index vs YoY change); optional - if omitted the
                fetch auto-selects the INDEX series (median ~100, not a percent).
    Requires the free application id in env ESTAT_APP_ID.

    NOTE: opt-in (not in the default candidate lists).  The @time decoding can
    vary by table, so the result is validated and a mis-parse RAISES (so the
    candidate machinery skips it) rather than silently feeding wrong dates.
    Verify with `refresh_data.py --check`; the local-CSV route is the tested one.
    """
    app_id = os.environ.get("ESTAT_APP_ID")
    if not app_id:
        raise RuntimeError(f"ESTAT_APP_ID env var not set (needed for {spec})")
    parts = spec.split(":")[1:]   # drop the 'estat' scheme
    stats_id = parts[0]
    cat  = parts[1] if len(parts) > 1 and parts[1] else None
    area = parts[2] if len(parts) > 2 and parts[2] else ESTAT_ALL_JAPAN_AREA
    tab  = parts[3] if len(parts) > 3 and parts[3] else None
    base = {"appId": app_id, "statsDataId": stats_id, "limit": 100000}
    if cat:
        base["cdCat01"] = cat
    if tab:
        base["cdTab"] = tab

    # Try with the area filter first; if it yields nothing, retry without it
    # (area code can differ by table) and let _estat_pick_index_series sort it out.
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            for params in ([{**base, "cdArea": area}, base] if area else [base]):
                r = requests.get(ESTAT_URL, params=params, timeout=60)
                r.raise_for_status()
                values = (r.json()["GET_STATS_DATA"]["STATISTICAL_DATA"]
                          ["DATA_INF"].get("VALUE", []))
                if isinstance(values, dict):
                    values = [values]
                if not values:
                    continue
                s = _estat_pick_index_series(values)
                now = pd.Timestamp.now()
                if s.empty or s.index.min().year < 1950 \
                        or s.index.max() > now + pd.Timedelta(days=120):
                    raise RuntimeError(f"e-Stat response for {spec} parsed implausibly "
                                       f"(check statsDataId / cdCat01)")
                s.name = spec
                return s
            raise RuntimeError("e-Stat returned no VALUE rows for this filter")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"e-Stat fetch failed for {spec}: {last_err}")


def _fetch_mof_jgb(source: str, retries: int = 4) -> pd.DataFrame:
    """Fetch the Ministry of Finance JGB constant-maturity curve (jgbcm).

    `source` is either the MoF historical CSV URL (Shift-JIS / cp932 encoded) or
    a local CSV path (a manual export, any common encoding).  Returns a DataFrame
    indexed by date with one float column per maturity (in YEARS), values in %.

    The MoF file has a one/two-line header then daily rows "date,1y,2y,...,40y"
    with '-' for not-yet-issued maturities.  Parsing is deliberately tolerant
    (the live layout is only checkable on a real run): any row whose first field
    is a parseable date is taken as data and its yield fields are aligned BY
    POSITION to config.JGB_CURVE_MATURITIES.

    Raises on failure so the caller can warn and fall back to the 3m/10y pair.
    """
    def _read_text() -> str:
        if os.path.exists(source):
            for enc in ("cp932", "utf-8", "shift_jis"):
                try:
                    with open(source, encoding=enc) as fh:
                        return fh.read()
                except UnicodeDecodeError:
                    continue
            raise RuntimeError(f"could not decode local MoF file {source}")
        last: Exception | None = None
        for attempt in range(retries):
            try:
                r = requests.get(source, timeout=60,
                                 headers={"User-Agent": "Mozilla/5.0 (neutralrate)"})
                r.raise_for_status()
                r.encoding = "cp932"          # MoF jgbcm is Shift-JIS
                return r.text
            except Exception as exc:          # noqa: BLE001
                last = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"MoF JGB fetch failed for {source}: {last}")

    text = _read_text()
    mats = [float(t) for t in JGB_CURVE_MATURITIES]
    dates, recs = [], []
    for line in text.splitlines():
        fields = [c.strip() for c in line.split(",")]
        if len(fields) < 2:
            continue
        dt = pd.to_datetime(fields[0].replace(".", "/"), errors="coerce")
        if pd.isna(dt):
            continue                          # header / metadata line
        vals = []
        for tok in fields[1:1 + len(mats)]:
            tok = tok.replace("%", "")
            vals.append(np.nan if tok in ("", "-", "*", "***") else
                        pd.to_numeric(tok, errors="coerce"))
        # pad/trim to the configured maturity count
        vals = (vals + [np.nan] * len(mats))[:len(mats)]
        dates.append(dt)
        recs.append(vals)
    if not recs:
        raise RuntimeError(f"MoF JGB file {source} carried no parseable rows")
    df = pd.DataFrame(recs, index=pd.DatetimeIndex(dates), columns=mats)
    df = df.sort_index()[~df.index.duplicated(keep="last")]
    return df


def fetch_any(spec: str) -> pd.Series:
    """Load a series from any supported source, routed by the spec shape:
      * 'estat:STATSDATAID[:CDCAT01]'  -> Statistics Bureau of Japan (e-Stat API)
      * a local CSV path (date,value)  -> CSV reader (e.g. an e-Stat / BoJ export)
      * 'PROVIDER/DATASET/SERIES'      -> DBnomics
      * otherwise                      -> a FRED series id
    """
    if spec.startswith("estat:"):
        return _fetch_estat(spec)
    if spec.lower().endswith(".csv") or os.path.exists(spec):
        df = pd.read_csv(spec)
        date_col, val_col = df.columns[0], df.columns[1]
        s = pd.to_numeric(df[val_col], errors="coerce")
        s.index = pd.to_datetime(df[date_col])
        return s
    if "/" in spec:
        return _fetch_dbnomics(spec)
    return fetch_series(spec)


# Back-compat alias (inflation-expectations hooks use the same dispatch).
fetch_expectations = fetch_any


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


def _fetch_freshest(candidates, name):
    """Fetch each candidate FRED id; return (quarterly series, id, last_date) for
    the one whose data extends furthest. Skips dead/unreachable candidates so a
    discontinued series (e.g. the OECD-MEI CPI, frozen at 2021) is never used
    when a maintained one exists."""
    best = (None, None, None)
    for sid in candidates:
        try:
            s = fetch_any(sid).dropna()
        except Exception as exc:  # noqa: BLE001
            print(f"[neutralrate] {name}: candidate {sid} unavailable ({exc}).")
            continue
        if s.empty:
            continue
        end = s.index.max()
        if best[2] is None or end > best[2]:
            best = (_to_quarterly(s, name), sid, end)
    return best


def fetch_raw_panel() -> pd.DataFrame:
    """Fetch every configured series from FRED and align to quarterly."""
    cols = {}
    for logical, fred_id in FRED_SERIES.items():
        raw = fetch_series(fred_id)
        cols[logical] = _to_quarterly(raw, logical)

    # CPI: pick the freshest live candidate (the OECD-MEI family ends 2021).
    cpi_q, cpi_id, cpi_end = _fetch_freshest(CPI_INDEX_CANDIDATES, "cpi")
    if cpi_q is not None:
        cols["cpi"] = cpi_q
        print(f"[neutralrate] cpi <- {cpi_id} (ends {cpi_end.date()})")
    core_q, core_id, core_end = _fetch_freshest(CORE_CPI_CANDIDATES, "core_cpi_yoy")
    if core_q is not None:
        cols["core_cpi_yoy"] = core_q
        print(f"[neutralrate] core_cpi_yoy <- {core_id} (ends {core_end.date()})")

    # optional dedicated survey expectation series (FRED / DBnomics / CSV).
    # Missing/empty/unreachable -> warn once and fall back to the proxy.
    def _try_expectations(spec, name):
        if not spec:
            return
        try:
            s = fetch_expectations(spec)
            if s is None or not s.notna().any():
                print(f"[neutralrate] {name}: source '{spec}' is empty; using proxy.")
                return
            cols[name] = _to_quarterly(s, name)
        except Exception as exc:  # noqa: BLE001
            print(f"[neutralrate] {name}: source '{spec}' unavailable "
                  f"({exc}); using proxy.")

    _try_expectations(INFLATION_EXPECTATIONS_SERIES, "inflation_expectations")
    _try_expectations(INFLATION_EXPECTATIONS_LONG_SERIES, "inflation_expectations_long")

    # Full JGB constant-maturity curve (MoF) -> jgb_<m>y columns, quarterly.
    # Best-effort: if the source is unreachable (e.g. egress-blocked) the
    # term-structure methods fall back to the 3m/10y pair automatically.
    if MOF_JGB_CURVE_SOURCE:
        try:
            jgb = _fetch_mof_jgb(MOF_JGB_CURVE_SOURCE)
            for tau in JGB_CURVE_MATURITIES:
                if float(tau) in jgb.columns:
                    cols[jgb_col(tau)] = _to_quarterly(jgb[float(tau)], "rate_10y")
            print(f"[neutralrate] JGB curve <- MoF jgbcm "
                  f"({len([t for t in JGB_CURVE_MATURITIES if float(t) in jgb.columns])}"
                  f" maturities, ends {jgb.index.max().date()})")
        except Exception as exc:  # noqa: BLE001
            print(f"[neutralrate] MoF JGB curve unavailable ({exc}); "
                  f"term-structure methods use the 3m/10y fallback.")

    panel = pd.DataFrame(cols)
    if SAMPLE_END:
        panel = panel.loc[:SAMPLE_END]
    panel = panel.loc[SAMPLE_START:]
    return panel


# --------------------------------------------------------------------------- #
# Derived variables used by the models
# --------------------------------------------------------------------------- #
def _tax_adjust(infl: pd.Series, yoy: bool) -> pd.Series:
    """Strip the mechanical consumption-tax effect from Japanese CPI inflation.

    For a YoY series, each hike lifts inflation by ~`pp` for the four quarters
    in its window; for an annualized q/q series the entire level shift lands in
    the hike quarter (~4*pp).  Windows/magnitudes in config.CONSUMPTION_TAX_EFFECTS.
    """
    if not ADJUST_CONSUMPTION_TAX:
        return infl
    adj = infl.copy()
    for start, end, pp in CONSUMPTION_TAX_EFFECTS:
        if yoy:
            mask = (adj.index >= start) & (adj.index <= end)
            adj.loc[mask] = adj.loc[mask] - pp
        else:
            mask = (adj.index >= start) & (adj.index <= pd.Timestamp(start)
                                           + pd.offsets.QuarterEnd(1))
            adj.loc[mask] = adj.loc[mask] - 4.0 * pp
    return adj


def tax_excluded_index(index: pd.Series) -> pd.Series:
    """Remove the consumption-tax effect from a CPI *index* (the correct,
    level-based method).  Divide by a cumulative multiplicative wedge that steps
    up at each hike by its price-level impact (config.CONSUMPTION_TAX_LEVEL_EFFECTS).
    Returns the tax-excluded index; YoY of the result is free of the hike spikes.
    This reconstructs BoJ's "excluding consumption-tax effects" core-core from the
    longer Statistics-Bureau raw index (see scripts/build_core_core.py).

    NOTE: this is a PURE de-tax (it ALWAYS removes the wedge) - de-taxing is its
    sole purpose, and build_core_core.py relies on it regardless of the global
    ADJUST_CONSUMPTION_TAX flag.  Whether the toolkit de-taxes the all-items index
    at all is gated separately at the call site in build_features()."""
    s = index.dropna()
    factor = pd.Series(1.0, index=s.index)
    for date, pp in CONSUMPTION_TAX_LEVEL_EFFECTS:
        factor.loc[s.index >= pd.Timestamp(date)] *= (1.0 + pp / 100.0)
    return s / factor


def build_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Construct the model-ready variables (logs, gaps, real rates, inflation).

    Columns added (annualized %, unless noted):
      log_gdp           : 100 * ln(real GDP)
      log_cons          : 100 * ln(real consumption [per working-age head])
      gdp_growth        : annualized q/q real GDP growth
      cons_growth       : annualized q/q (per-capita) consumption growth
      inflation         : annualized q/q CPI inflation
      inflation_yoy     : 4-quarter CPI inflation
      exp_inflation     : short-horizon expected inflation (4q MA of core, or
                          a spliced survey series); exp_inflation_long = anchored
                          long-horizon expectation
      real_short_rate   : short_rate - exp_inflation     (ex-ante real policy)
      real_10y          : rate_10y  - exp_inflation;  real_10y_exp uses the long
                          (anchored) expectation, for the term-structure methods
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

    # Inflation (YoY %, consumption-tax adjusted).  Build both a core measure
    # (HLW-appropriate) and an all-items measure, then use whichever is FRESHER:
    # this prevents a discontinued core series (OECD MEI ends 2021) from silently
    # freezing every inflation-dependent method while a maintained all-items
    # series is available.  A loud warning fires if even the chosen series is
    # stale relative to the interest-rate data.
    allitems = None
    if "cpi" in df and df["cpi"].notna().any():
        # De-tax on the index (level-based, correct), then take YoY.  Gated by
        # the global flag: skip when the core series is already tax-excluded
        # (e.g. the build_core_core.py output) to avoid removing the tax twice.
        cpi_idx = tax_excluded_index(df["cpi"]) if ADJUST_CONSUMPTION_TAX else df["cpi"]
        allitems = 100.0 * np.log(cpi_idx).diff(4)
        allitems = allitems.reindex(df.index)
    core = None
    if "core_cpi_yoy" in df and df["core_cpi_yoy"].notna().any():
        core = _tax_adjust(df["core_cpi_yoy"], yoy=True)

    def _last(s):
        return None if s is None else s.last_valid_index()

    if core is not None and allitems is not None:
        core_fresh = _last(core) >= _last(allitems) - pd.Timedelta(days=185)
        inflation, src = (core, "core CPI") if core_fresh else \
            (allitems, "all-items CPI (core series stale)")
    elif core is not None:
        inflation, src = core, "core CPI"
    elif allitems is not None:
        inflation, src = allitems, "all-items CPI"
    else:
        raise ValueError("No CPI series available to build inflation.")
    df["inflation"] = inflation
    df["inflation_yoy"] = inflation
    print(f"[neutralrate] inflation source: {src} (ends {_last(inflation).date()})")

    rate_last = df["short_rate"].last_valid_index() if "short_rate" in df else None
    if rate_last is not None and _last(inflation) is not None:
        stale_q = (rate_last.to_period("Q") - _last(inflation).to_period("Q")).n
        if stale_q > 2:
            print(f"[neutralrate] WARNING: inflation ({src}) ends "
                  f"{_last(inflation).date()} but rates end {rate_last.date()} "
                  f"- {stale_q} quarters stale; recent r* will be missing for the "
                  f"CPI-based methods. Check / re-point the CPI candidates in config.")

    # --- Expected inflation, two horizons -------------------------------- #
    # Proxies (always computed): SHORT = 4q MA of core (the HLW expectation);
    # LONG = multi-year MA of core (an "anchored" stand-in for ~5-10y survey
    # expectations).  A configured survey series is SPLICED on top - used where
    # available, proxy fills the earlier history (BoJ surveys start 2006-2014).
    proxy_short = df["inflation"].rolling(
        INFLATION_EXPECTATION_WINDOW, min_periods=1).mean()
    proxy_long = df["inflation"].rolling(
        INFLATION_EXPECTATION_LONG_WINDOW, min_periods=4).mean().fillna(proxy_short)

    if "inflation_expectations" in df and df["inflation_expectations"].notna().any():
        df["exp_inflation"] = df["inflation_expectations"].combine_first(proxy_short)
    else:
        df["exp_inflation"] = proxy_short

    # The term-structure / common-trends methods deflate the *long* end of the
    # yield curve with this, mirroring the originals' survey-based expectations.
    if ("inflation_expectations_long" in df
            and df["inflation_expectations_long"].notna().any()):
        df["exp_inflation_long"] = (
            df["inflation_expectations_long"].combine_first(proxy_long))
    else:
        df["exp_inflation_long"] = proxy_long

    # --- ex-ante real rates ---------------------------------------------- #
    # Adaptive (HLW): deflate by the short-horizon (4q MA) expectation.
    df["real_short_rate"] = df["short_rate"] - df["exp_inflation"]
    df["real_10y"] = df["rate_10y"] - df["exp_inflation"]
    df["real_3m"] = df["rate_3m"] - df["exp_inflation"]
    # Survey-based (term-structure / common-trends methods): deflate the short
    # end by the short expectation and the long end by the long (anchored) one.
    df["real_short_exp"] = df["short_rate"] - df["exp_inflation"]
    df["real_3m_exp"] = df["rate_3m"] - df["exp_inflation"]
    df["real_10y_exp"] = df["rate_10y"] - df["exp_inflation_long"]

    # --- Full real JGB curve + Nelson-Siegel factors --------------------- #
    # When the MoF curve is present, deflate the WHOLE nominal curve by the
    # anchored (long-horizon) expectation and decompose the real curve into
    # level/slope/curvature.  These feed the natural-yield-curve methods; with
    # fewer than 4 maturities they are skipped and the methods use the 3m/10y
    # midpoint.  (Maturity-specific deflators are a later refinement; see
    # docs/03_faithfulness_audit.md.)
    jgb_cols = [(float(t), jgb_col(t)) for t in JGB_CURVE_MATURITIES
                if jgb_col(t) in df.columns]
    if USE_FULL_CURVE and len(jgb_cols) >= 4:
        # Maturity-matched deflation (as in the originals' survey expectations):
        # short maturities are deflated by the short-horizon expectation, long
        # maturities by the long (anchored) one, interpolating linearly in
        # maturity up to EXP_HORIZON years.  This keeps the fitted short end
        # consistent with real_short_exp and the long end with real_10y_exp.
        EXP_HORIZON = 5.0
        pi_s, pi_l = df["exp_inflation"], df["exp_inflation_long"]
        real_curve = pd.DataFrame(
            {t: df[c] - (pi_s + (pi_l - pi_s) * min(t / EXP_HORIZON, 1.0))
             for t, c in jgb_cols},
            index=df.index)
        for t, c in jgb_cols:
            df[f"real_{c}"] = real_curve[t]
        factors = _ns.fit_factors(real_curve, NELSON_SIEGEL_LAMBDA)
        for name in _ns.FACTOR_NAMES:
            df[name] = factors[name].reindex(df.index)
        df["ns_real_short"] = _ns.evaluate(
            factors, 0.25, NELSON_SIEGEL_LAMBDA).reindex(df.index)
        df["ns_real_10y"] = _ns.evaluate(
            factors, 10.0, NELSON_SIEGEL_LAMBDA).reindex(df.index)
        df["ns_real_curve_mean"] = real_curve.mean(axis=1)
        print(f"[neutralrate] Nelson-Siegel curve fitted on {len(jgb_cols)} "
              f"real maturities (lambda={NELSON_SIEGEL_LAMBDA}).")

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
