# Update Manual — Refreshing the Japan r\* Models

This manual explains, step by step, how to **update the data and re-run all six
natural-rate models** in both the **Python** toolkit and the **Excel** workbook
when new economic data are released (typically once a quarter).

Everything is driven by **public FRED data**. You only ever change one thing —
the data — and the models recompute.

---

## 0. One-time setup

### 0.1 Get a (free) FRED API key — recommended
1. Create an account at <https://fredaccount.stlouisfed.org/login/secure/> and
   request an API key (instant).
2. Make it available to the toolkit as an environment variable. **Do not paste it
   into code or commit it to git.**

   macOS / Linux:
   ```bash
   export FRED_API_KEY="your_key_here"
   # add the line to ~/.bashrc or ~/.zshrc to persist it
   ```
   Windows (PowerShell):
   ```powershell
   setx FRED_API_KEY "your_key_here"
   ```
   Or create a local, git-ignored `.env` and `source` it.

> Without a key the toolkit still works: it falls back to FRED's no-key
> `fredgraph.csv` download. The key is just more robust and supports larger pulls.

### 0.2 Install the Python dependencies
```bash
cd python
python -m pip install -r requirements.txt
```

### 0.3 First build (no network needed)
The repo ships a **synthetic sample** so you can see everything work offline:
```bash
cd python
python scripts/make_sample_data.py          # (already committed; regenerates sample)
python -m neutralrate.run_all --offline      # runs all six on the sample
python ../excel/build_workbook.py            # builds the Excel workbook
```

---

## 1. The quarterly update — Python (the faithful estimates)

This is the recommended path; it produces the faithful state-space/MLE estimates.

```bash
cd python

# 1. Pull the latest data from FRED (writes data/cache/raw_panel.csv)
python scripts/refresh_data.py            # add --check first to preview values

# 2. Re-estimate all six methods on the fresh data
python -m neutralrate.run_all --refresh
```

Outputs land in `python/output/`:
- `r_star_estimates.csv` — quarterly r\* by method + cross-method mean/min/max
- `method_params.json` — the estimated parameters of every model
- `r_star_chart.png` — the comparison chart

**That's it.** Adding the new quarter is fully automatic — the data layer
re-downloads, re-aligns to quarterly, rebuilds all derived features (real rates,
inflation, gaps), and the six estimators re-run.

### Tips
- `python scripts/refresh_data.py --check` prints the latest fetched observations
  so you can sanity-check before re-estimating.
- To change a source series (e.g. a different inflation measure), edit
  `FRED_SERIES` in `python/neutralrate/config.py` — nothing else changes.
- To recalibrate the DSGE Euler equation, edit `DSGEParams` (`rho`, `gamma`) in
  the same file.

---

## 2. The quarterly update — Excel

The workbook recomputes the **Excel proxy** of each method live from its `Data`
sheet. Pick **one** refresh path.

### Option A — Automated (easiest, uses the Python data layer)
```bash
cd python
python scripts/refresh_data.py --excel
```
This pulls fresh FRED data and writes it straight into the workbook's `Data`
sheet. Open `excel/Japan_Neutral_Rate_Models.xlsx` and every r\* column and the
Dashboard chart will already reflect the new quarter (recalculate with **F9** if
needed).

To also refresh the faithful Python estimates that are overlaid on the Dashboard:
```bash
python -m neutralrate.run_all --refresh
python ../excel/build_workbook.py --from-cache
```

### Option B — Native Excel "Refresh All" via Power Query
Set this up once and thereafter just press **Data ▸ Refresh All**.

1. Open `Japan_Neutral_Rate_Models.xlsx`.
2. **Data ▸ Get Data ▸ From Other Sources ▸ From Web.**
3. Paste a FRED CSV URL, e.g. the 10-year JGB yield:
   ```
   https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01JPM156N
   ```
   (Swap `id=` for any series in the table below.)
4. In the Power Query editor: set the first row as headers, type the date and
   value columns, then **Close & Load To… ▸ a connection / a staging sheet.**
5. Repeat for each series, then combine them into the `Data` sheet layout
   (one date column + one column per series) — or load each to its own sheet and
   reference it. The derived-feature and r\* formulas already point at the `Data`
   columns by header, so once `Data` is refreshed everything recomputes.
6. From then on: **Data ▸ Refresh All** each quarter.

**FRED series ids for the Power Query URLs:**

| Column on `Data` | FRED id |
|---|---|
| `real_gdp` | `JPNRGDPEXP` |
| `consumption` | `JPNPFCEQDSMEI` |
| `cpi` | `JPNCPIALLMINMEI` |
| `short_rate` | `IRSTCI01JPM156N` |
| `rate_3m` | `IR3TIB01JPM156N` |
| `rate_10y` | `IRLTLT01JPM156N` |
| `working_age_pop` | `LFWA64TTJPM647S` |

> Monthly series (`cpi`, the three interest rates, `working_age_pop`) must be
> aggregated to **quarterly averages** to match the GDP frequency. The automated
> Option A does this for you; in Power Query use **Group By ▸ quarter ▸ Average**.

### Settings you can change in the workbook
On the **Settings** sheet:
- `B1` **window (quarters)** — trailing window for all trend/moving-average
  calculations (default 20 ≈ 5 years). All r\* columns recompute when you change it.
- `B2` **rho**, `B3` **gamma** — DSGE Euler calibration.
- `B4` **avg real term spread** — auto-computed from the data; used to level-adjust
  the long rate.

---

## 3. What "updating" actually recomputes

```
FRED  ──►  raw quarterly panel  ──►  derived features  ──►  six r* estimates
          (real_gdp, cpi, rates,    (log GDP, growth,      (Python: state-space MLE
           consumption, pop…)        inflation, real         Excel: live formulas)
                                      rates, exp. infl.)
```

- **Python**: `data.refresh()` re-pulls and re-derives; `run_all` re-estimates.
- **Excel**: the `Data` sheet is the single source; all helper columns and the six
  `rstar_*` columns are formulas over it, so a `Data` refresh propagates everywhere.

---

## 4. Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: FRED API fetch failed` | Check internet; verify `FRED_API_KEY`; the code retries 4× with backoff, then errors. Re-run, or omit the key to use the no-key `fredgraph` path. |
| `Host not in allowlist` / connection refused | You are on a network that blocks FRED (e.g. a locked-down CI sandbox). Run on a normal network, or use `--offline` for a demo run. |
| A method prints `[FAIL]` in `run_all` | The optimizer didn't converge on this vintage. Re-run (random restarts use a fixed seed but try `--refresh`), or widen the sample in `config.py`. Other methods still produce output. |
| Excel shows `#N/A` early in the sample | Expected: trailing windows need `window` quarters of history before they fill in. |
| Excel r\* columns don't update | Press **F9** (or **Formulas ▸ Calculate Now**); ensure calculation is set to Automatic. |
| Estimates look implausible | Check the `Data` sheet for a bad/late FRED revision; use `refresh_data.py --check` to inspect the latest observations. |

---

## 5. Quarterly checklist (TL;DR)

```bash
# Python (faithful)
cd python
python scripts/refresh_data.py --check     # eyeball the new data
python -m neutralrate.run_all --refresh     # re-estimate -> output/

# Excel (proxy + overlay)
python scripts/refresh_data.py --excel      # push data into the workbook
python ../excel/build_workbook.py --from-cache   # refresh overlaid Python series
```
Open `python/output/r_star_chart.png` and `excel/Japan_Neutral_Rate_Models.xlsx`,
read off the new r\* band, and remember BOJ's lesson: **watch the range, not a
single number.**
