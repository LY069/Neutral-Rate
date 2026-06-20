# Japan's Natural Rate of Interest — Six Methods, Replicated

Deep-research comparison **and** a refreshable Excel + Python replication of the
**six methods** the Bank of Japan uses to estimate Japan's natural rate of
interest (r\*), as surveyed in **BOJ Review 2026-E-4** and the underlying working
paper **BOJ WP 24-E-12** (Nakano, Sugioka & Yamamoto, 2024).

> Source page: <https://www.boj.or.jp/en/research/wps_rev/rev_2026/rev26e04.htm>

## The six methods

| # | Method | Family |
|---|--------|--------|
| 1 | Holston–Laubach–Williams (2023) | Semi-structural (IS + Phillips, Kalman) |
| 2 | Okazaki & Sudo (2018) | DSGE (consumption Euler) |
| 3 | Imakubo, Kojima & Nakajima (2015) | Natural yield curve |
| 4 | Nakajima et al. (2023) | Natural yield curve (growth-anchored) |
| 5 | Goy & Iwasaki (2024) | Macro-finance natural curve |
| 6 | Del Negro et al. (2017) | VAR with common trends |

## What's here

```
docs/
  01_research_report.md   ← deep comparison + summary table of key variables
  02_update_manual.md     ← step-by-step: refresh data & re-run everything
python/
  neutralrate/            ← package: data layer + one module per method
  scripts/refresh_data.py ← pull latest FRED data (FRED_API_KEY env var)
  scripts/validate_vs_boj.py ← one-command check vs BoJ's published Chart 3
  scripts/make_sample_data.py
  run_all (module)        ← estimate all six, write CSV/JSON/chart
  tests/test_smoke.py     ← incl. smoothness / ordering / tax-adj regression tests
  output/                 ← r_star_estimates.csv, method_params.json, chart
excel/
  build_workbook.py       ← generates the refreshable workbook
  Japan_Neutral_Rate_Models.xlsx
data/
  sample/                 ← bundled SYNTHETIC sample (offline demo/testing)
  boj/                    ← BoJ Chart 3 reference estimates (validation target)
  expectations/           ← pre-wired BoJ Tankan CSV hooks (see its README)
```

## Quick start

```bash
cd python
python -m pip install -r requirements.txt

# Offline demo on the bundled synthetic sample (no network needed):
python -m neutralrate.run_all --offline
python ../excel/build_workbook.py

# Real data (set a free FRED key first — see docs/02_update_manual.md):
export FRED_API_KEY=your_key_here
python scripts/refresh_data.py            # pull latest Japan series from FRED
python -m neutralrate.run_all --refresh    # re-estimate all six methods
python scripts/validate_vs_boj.py          # compare against BoJ's Chart 3
```

## Fidelity, honestly

- **Python** holds the *faithful* state-space / MLE replications of each method.
- **Excel** holds transparent *reduced-form proxies* that recompute live as data
  arrive (full DSGE/affine/MCMC estimation can't live in a spreadsheet). The
  faithful Python series are overlaid on the workbook's `Python_faithful` sheet.
- The exact "exact vs. approximated" map is in `docs/01_research_report.md` §5.

Estimates vary widely by method (BOJ's central point) — Japan's r\* lands roughly
in the **−1.0% to +0.5%** band in recent years, all methods agreeing only on the
long-run *decline*. Read the **range**, not a single number.

## Data

All inputs are public FRED series (Japan): real GDP, private consumption, **core
CPI** (`CPGRLE01JPQ657N`, the HLW-appropriate inflation input), call/3-month/
10-year rates, working-age population. Expected inflation follows HLW (a moving
average of core inflation); a config hook (`INFLATION_EXPECTATIONS_SERIES`) lets
you drop in a real breakeven/Consensus series if you have one. See
`python/neutralrate/config.py` for the catalog and how to re-point any series.

> The bundled `data/sample/` panel is **synthetic** (deterministic stand-in) so
> the toolkit runs offline. Use `refresh_data.py` for real FRED data.
