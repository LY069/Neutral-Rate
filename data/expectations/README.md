# Inflation-expectations input (pre-wired)

The toolkit's config hooks point here:

```python
INFLATION_EXPECTATIONS_SERIES      = "data/expectations/japan_infl_exp_1y.csv"  # short ~1y
INFLATION_EXPECTATIONS_LONG_SERIES = "data/expectations/japan_infl_exp_5y.csv"  # long ~5y
```

These files ship **empty** (header only), so until you populate them the toolkit
warns once and falls back to the core-inflation moving-average proxy. Drop in
real survey data and the four term-structure / common-trends methods (Imakubo,
Nakajima, Goy–Iwasaki, Del Negro) will use it automatically — **spliced** onto
the proxy, so a short survey history (2014→) is fine for a 1990s→ sample.

## Format
Two columns, quarterly or monthly (monthly is auto-aggregated to quarterly):

```
date,value
2014-03-01,0.9
2014-06-01,0.9
...
2025-09-01,2.4
```
`value` = expected CPI inflation in **percent**.

## Where to get the data (recommended: BoJ Tankan)

**BoJ Tankan – "Inflation Outlook of Enterprises"** (firms' expected general
prices; all enterprises, all industries, average):
- 1-year-ahead → `japan_infl_exp_1y.csv`
- 5-years-ahead → `japan_infl_exp_5y.csv`

1. Open the **BoJ Time-Series Data Search**: <https://www.stat-search.boj.or.jp>
2. Search "Tankan inflation outlook" (series codes begin with `CO'`; see
   <https://www.stat-search.boj.or.jp/info/tankan_code_en.html>). Pick the
   *all enterprises / all industries, general prices* 1y and 5y averages.
3. Download as CSV, keep just `date,value`, save over the files here.

Alternatives:
- **BoJ Opinion Survey on the General Public** (households' 1y/5y expectations).
- **DBnomics** (free API) — set the hook to a code instead of a path, e.g.
  `INFLATION_EXPECTATIONS_LONG_SERIES = "BOJ/<dataset>/<series>"`.
- **FRED** id (no clean Japan series; US `T10YIE` only as a placeholder).
- A **breakeven / inflation-swap** series if you have market access (note the
  deflation-option/liquidity distortions, BOJ WP 20-E-5).

> History note: BoJ Tankan expectations start in 2014, the Opinion Survey in
> 2006. That's why the toolkit splices — the proxy covers the earlier sample.
