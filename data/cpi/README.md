# CPI input — official Statistics Bureau of Japan data (recommended)

The toolkit's inflation input is pre-wired to look here **first**, then fall back
to FRED. The OECD CPI series on FRED (`JPNCPIALLMINMEI`, `CPGRLE01JP*657N`) were
**discontinued at June 2021**, so for live estimates use the **Statistics Bureau
of Japan (e-Stat)** — the authoritative source. Two ways:

## Option A — local CSV (tested, reliable, recommended)

### Which inflation concept? (consistency with the papers)

The natural-rate methods deflate with an **underlying / core** measure, not
headline:
- **HLW** (and Del Negro for the US) use core inflation, *ex food & energy*.
  Japan's analog is **"core-core" = CPI excluding fresh food and energy**
  (生鮮食品及びエネルギーを除く総合). BoJ's traditional **"core" = ex fresh food**
  is an acceptable alternative; **headline is not** the right concept.
- The **DSGE** here (`r* = ρ + γ·g_c`) is driven by consumption only, so the CPI
  choice does not affect it.
- **Tax / institutional effects are removed.** BoJ's "Indicators for Core CPI"
  publishes the core measures **excluding the consumption-tax hikes, free
  education, mobile-phone charges and subsidies** — the cleanest input.

> **Avoid double-counting the tax.** If you use a series that is **already
> tax-excluded** (BoJ's "Indicators for Core CPI"), set
> `ADJUST_CONSUMPTION_TAX = False` in `config.py`. If you use a **raw**
> Statistics-Bureau series (tax still in it), leave it `True` so the toolkit
> strips the 1989/1997/2014/2019 hikes.

### Fill these two files (they ship empty; used automatically, picked by recency)

| File | What | Source |
|---|---|---|
| `jp_cpi_allitems_index.csv` | All-items CPI **index** (2020=100) — used only as a fallback/cross-check | Statistics Bureau "All items" (総合) |
| `jp_core_core_yoy.csv` | **Core-core YoY %** — the primary input | **BoJ "Indicators for Core CPI"**: *less fresh food & energy, excl. tax effects* (preferred), **or** Statistics Bureau *less fresh food & energy*, YoY |

Format — two columns, monthly or quarterly (monthly is auto-aggregated):
```
date,value
2020-01-01,99.1
...
2026-04-01,111.8
```
- `jp_cpi_allitems_index.csv` → the **index level** (the toolkit computes YoY itself).
- `jp_core_core_yoy.csv` → the **YoY % change** (already a growth rate).

How to get it:
1. **Preferred (tax-excluded core-core):** BoJ ▸ Research & Statistics ▸
   *"Indicators for Core CPI"* <https://www.boj.or.jp/en/research/research_data/cpi/index.htm>
   — download the *less fresh food & energy, excluding the effects of the
   consumption tax hikes* series; then set `ADJUST_CONSUMPTION_TAX = False`.
2. **Or raw (tax-included):** e-Stat ▸ "2020-Base Consumer Price Index", All-Japan
   monthly <https://www.e-stat.go.jp/en/stat-search/files?query=Consumer%20Price%20Index>
   — export the "All items less fresh food and energy" YoY; keep
   `ADJUST_CONSUMPTION_TAX = True`.
3. Reduce to two columns `date,value`, save over the files here, then
   `python scripts/refresh_data.py --check` and confirm they reach the latest month.

## Option B — e-Stat API (automated, opt-in)

1. Register for a free **application ID** at e-Stat and export it:
   ```bash
   export ESTAT_APP_ID="your_app_id"
   ```
2. In `python/neutralrate/config.py`, set a candidate to
   `"estat:STATSDATAID:CDCAT01"` (the `statsDataId` of the 2020-base CPI table and
   the `cdCat01` item code for "All items" / "core-core"). Find these via the
   e-Stat `getStatsList` / `getMetaInfo` endpoints or the table's API tab.

> The API path is **opt-in and validated** — if the `@time` decoding doesn't match
> the table, the fetch raises and the toolkit falls back rather than using wrong
> dates. Always confirm with `refresh_data.py --check` (it prints each series' last
> valid date). The CSV route (Option A) is the tested one.

Until populated, the toolkit falls back to the FRED candidates in
`CPI_INDEX_CANDIDATES` / `CORE_CPI_CANDIDATES` and warns if those are stale.
