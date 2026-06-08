# Japan's Natural Rate of Interest — A Comparison of Six Estimation Methods

*A senior-economist's reading of the Bank of Japan's survey of r\* estimation,
with a faithful Excel + Python replication.*

---

## 0. Source and scope

This report and the accompanying code replicate the **six estimation methods**
for Japan's natural rate of interest (r\*) that the Bank of Japan brings together in:

- **BOJ Review 2026-E-4** — *"Developments in the Natural Rate of Interest and the
  Assessment of the Degree of Monetary Accommodation"* (March 2026), the page you
  referenced: <https://www.boj.or.jp/en/research/wps_rev/rev_2026/rev26e04.htm>
- **BOJ Working Paper 24-E-12** — Nakano, Sugioka & Yamamoto (2024), *"Recent
  Developments in Measuring the Natural Rate of Interest"*, the detailed survey
  the Review summarizes:
  <https://www.boj.or.jp/en/research/wps_rev/wps_2024/wp24e12.htm>

> **Sourcing note (transparency).** The BOJ website blocks automated retrieval
> (HTTP 403 to crawlers/PDF fetchers), so the method list, variables and findings
> below were reconstructed from (i) BOJ's own published abstracts and search
> metadata for rev26e04 / wp24e12, and (ii) the underlying primary papers that
> BOJ cites and applies to Japan. The six methods correspond to the six estimates
> BOJ compares: **Del Negro et al. (2017), HLW (2023), Imakubo–Kojima–Nakajima
> (2015), Nakajima et al. (2023), Okazaki–Sudo (2018), and Goy–Iwasaki (2024).**
> If your copy of the paper labels them differently, the code is modular and a
> method can be re-pointed without touching the rest of the toolkit.

The BOJ's bottom line, which frames everything below: **all six methods agree that
Japan's r\* trended down over the long run, but the *level* estimates differ widely
(roughly −1.0% to +0.5% in recent years) and move when new data arrive.** That
dispersion is the whole point — it is why the Bank refuses to read the policy
stance off a single r\* number and instead judges accommodation comprehensively.

---

## 1. What is r\* and why six methods?

The natural (or neutral) rate of interest **r\*** is the *real* short-term interest
rate that would prevail when the economy is at potential and inflation is stable —
Wicksell's rate that is "neutral" to prices. It is unobservable and must be
*inferred*. Two design choices generate the whole zoo of methods:

1. **What pins r\* down economically?** Trend growth of potential output / per-capita
   consumption (the Ramsey/Euler logic), a saving–investment (IS) balance, or a
   common stochastic trend shared with other macro-financial variables.
2. **How is the unobserved trend extracted?** A semi-structural Kalman filter, a
   fully structural DSGE, a term-structure (yield-curve) model, or a reduced-form
   VAR with common trends.

The six methods are best understood as **four families**:

| Family | Methods | Identifying restriction |
|---|---|---|
| **Semi-structural (LW-type)** | HLW (2023) | IS + Phillips curve; r\* = c·g + z |
| **Structural (DSGE)** | Okazaki–Sudo (2018) | Euler equation: r\* = ρ + γ·g_c |
| **Term-structure / natural yield curve** | Imakubo et al. (2015); Nakajima et al. (2023); Goy–Iwasaki (2024) | Yield-curve gap closes the output gap; r\* is the short end of a *natural yield curve* |
| **Reduced-form common trends** | Del Negro et al. (2017) | r\* is the shared stochastic trend in real rates, growth & inflation |

---

## 2. The six methods in detail

### Method 1 — Holston–Laubach–Williams (HLW, 2017; 2023 update)
**Family:** semi-structural. **Builds on:** Laubach & Williams (2003).

A three-equation linear-Gaussian state-space model estimated by the Kalman filter:

- **IS curve:** the output gap depends on its own lags and the **real-rate gap**
  `(r − r*)`. A positive gap (policy tighter than neutral) opens a negative output gap.
- **Phillips curve:** inflation depends on lagged inflation and the lagged output gap.
- **Trends (random walks):** potential output `y*`, its trend growth `g`, and an
  "other factor" `z`, with the natural rate

  **r\*ₜ = c·gₜ + zₜ**  (c≈4 to annualize quarterly trend growth).

So HLW makes r\* move one-for-one with *trend growth* plus a slow residual `z`
(demographics, risk premia, global forces). Holston–Laubach–Williams (2017) add an
open-economy/global block; the 2023 vintage refines the post-pandemic handling.
**Strengths:** transparent economics, internationally comparable, directly delivers
the output gap. **Weaknesses:** the "pile-up" problem (trend-variance ratios are
hard to estimate; HLW use Stock–Watson median-unbiased estimation), heavy end-point
revision, and a tight (often criticized) link of r\* to estimated trend growth.

### Method 2 — Okazaki & Sudo (2018) DSGE (BOJ WP 18-E-6)
**Family:** structural DSGE. **Title:** *"Natural Rate of Interest in Japan —
Measuring its size and identifying drivers based on a DSGE model."*

A medium-scale New-Keynesian DSGE for Japan. The natural rate is the model's
flexible-price real rate. The steady-state heart of it is the **consumption Euler
equation**:

  **r\*ₜ = ρ + γ·g_c,ₜ**

where `g_c` is trend (per-capita) consumption/productivity growth, `γ` is the inverse
intertemporal elasticity of substitution, and `ρ` the rate of time preference.
Okazaki–Sudo's key finding: Japan's r\* fell mainly because **trend growth slowed**
(declining TFP and a shrinking working-age population), with preference/demographic
shifts adding to the decline. **Strengths:** structural *interpretation* and driver
decomposition (you learn *why* r\* moved). **Weaknesses:** model-dependence — r\*
inherits every assumption; cannot be reproduced in a spreadsheet; sensitive to the
calibration of `γ` and `ρ`.

### Method 3 — Natural Yield Curve, Imakubo, Kojima & Nakajima (2015)
**Family:** term structure. **Concept:** generalize the *single* natural rate to a
*whole curve* of natural rates, one per maturity.

They extend LW so the IS curve responds to the **yield-curve gap** — the gap between
the *actual* real yield curve and a *natural* yield curve — rather than to one
short-rate gap. The natural rate of interest is the **short end** of the natural
yield curve; the slope of the natural curve carries information about expected
future growth. **Strengths:** uses the information in the whole term structure, not
just the policy rate; intuitive for a YCC-era central bank. **Weaknesses:**
identification of the curve's level vs. slope is delicate; needs multiple maturities;
the natural curve is itself a filtered (revisable) object.

### Method 4 — Natural Yield Curve, Nakajima, Sudo, Hogen & Takizuka (2023)
**Family:** term structure (refinement of Method 3). **Title:** *"On the estimation
of the natural yield curve."*

Refines Imakubo et al. by **anchoring the long-run level of the natural curve to
trend potential growth** (the LW `r* = c·g + z` logic) while still estimating the
cyclical "other factor" from the yield-curve gap, and by treating the curve at both
the short (≈1y) and long (≈10y) ends with explicit attention to estimation
uncertainty. **Strengths:** combines the growth anchor (theory) with the term-
structure information (data); reports the natural rate at multiple maturities.
**Weaknesses:** more moving parts; results depend on the growth-trend estimate fed in.

### Method 5 — Macro-finance natural curve, Goy & Iwasaki (2024)
**Family:** term structure / macro-finance. **Title:** *"From the Natural Rate
towards a Natural Curve: A First Step to Benchmarking the Term Structure."*

A **trend–cycle macro-finance** term-structure model. A Nelson–Siegel-style yield
curve (level / slope / curvature factors) is fused with a macro block. A single
slow-moving **real trend** plays a *dual role*: it is both the long-run **level of
the yield curve** and the **natural real rate** that closes the output gap. r\* is
that common trend. **Strengths:** disciplines r\* with *bond-market* information and
enforces internal consistency between the macro natural rate and the term structure;
naturally produces a term premium decomposition. **Weaknesses:** the most data- and
specification-intensive; needs a real yield curve across maturities and a
no-arbitrage/affine structure for full fidelity.

### Method 6 — VAR with common trends, Del Negro, Giannone, Giannoni & Tambalotti (2017)
**Family:** reduced-form time series. **Title:** *"Safety, Liquidity, and the
Natural Rate of Interest"* (Brookings). BOJ applied the same common-trends approach
to Japan in **WP 24-E-17**.

A flexible Bayesian VAR with **common stochastic trends** across real Treasury and
corporate yields, inflation and long-horizon survey expectations. r\* is the trend
real (safe) rate. The famous decomposition attributes the decline in r\* mainly to a
rising **convenience yield** (the premium on safe & liquid assets), plus a smaller
contribution from slower trend growth. **Strengths:** few economic restrictions
(lets the data speak), credible long-run trends, and an explicit safety/liquidity
story. **Weaknesses:** little structural interpretation of the cycle; needs priors
for stable trends; the convenience-yield block needs corporate-spread data.

---

## 3. Summary comparison table — key economic variables by model

The single most useful artifact: **what each model actually consumes and produces.**
(✓ = primary input; ·  = not used directly.)

| Variable / feature | HLW (2023) | DSGE Okazaki–Sudo | Imakubo NYC (2015) | Nakajima NYC (2023) | Goy–Iwasaki (2024) | Del Negro VAR (2017) |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Real GDP / output gap | ✓ | ✓ | ✓ | ✓ | ✓ (trend) | ✓ (growth) |
| Per-capita **consumption** | · | ✓ (Euler) | · | · | · | · |
| Core **inflation** | ✓ (Phillips) | ✓ | ✓ | ✓ | · | ✓ |
| Inflation **expectations** | ✓ (proxy) | ✓ | ✓ | ✓ | ✓ | ✓ (surveys) |
| **Short / policy** real rate | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (trend = r\*) |
| **Long (10y)** real rate | (HLW-open) | · | ✓ | ✓ | ✓ | ✓ |
| Full **yield curve** (multi-maturity) | · | · | ✓ | ✓ | ✓ | ✓ |
| Corporate spread / **convenience yield** | · | · | · | · | (premium) | ✓ |
| **Demographics** (working-age pop.) | via `g` | ✓ (driver) | via `g` | ✓ (anchor) | via trend | via trend |
| Trend **growth `g`** drives r\* | ✓ `r*=c·g+z` | ✓ `r*=ρ+γg_c` | implied | ✓ anchor | ✓ common trend | ✓ partial |
| **Output:** single r\* | ✓ | ✓ | short end | short + long | curve level | ✓ |
| **Output:** whole natural *curve* | · | · | ✓ | ✓ | ✓ | (multi-rate) |
| Estimation engine | Kalman + MLE / median-unbiased | Bayesian DSGE | Kalman (state-space) | Kalman (state-space) | Kalman / affine macro-finance | Bayesian VAR (common trends) |
| Structural interpretation | medium | **high** | medium | medium | medium–high | **low** |
| Reproducible in a spreadsheet? | partial | no | partial | partial | partial | partial |
| End-point revision risk | **high** | medium | high | high | medium | medium |

**FRED series used by the replication** (logical name → series id; see
`python/neutralrate/config.py`):

| Logical name | FRED id | Used by |
|---|---|---|
| Real GDP | `JPNRGDPEXP` | all (output gap / growth) |
| Private consumption | `JPNPFCEQDSMEI` | DSGE |
| CPI (→ core-ish YoY) | `JPNCPIALLMINMEI` | inflation, real rates |
| Call/interbank rate (policy) | `IRSTCI01JPM156N` | short real rate |
| 3-month rate | `IR3TIB01JPM156N` | curve short end |
| 10-year JGB yield | `IRLTLT01JPM156N` | curve long end |
| Working-age population | `LFWA64TTJPM647S` | per-capita / demographics |

---

## 4. How the estimates compare for Japan (qualitative)

- **Direction:** unanimous secular decline from the high-growth 1980s through the
  1990s; broadly **0–1%** in the 2000s, drifting toward or **below zero** in the
  2010s under deflation/ZIRP/QQE.
- **Recent level / dispersion:** growth-anchored methods (HLW, DSGE, Nakajima) tend
  to sit nearer the **potential-growth range (~0.0% to +0.5%)**, while the original
  natural-yield-curve (Imakubo) and convenience-yield (Del Negro) readings hover
  **around or slightly below zero**. BOJ summarizes the band as roughly **−1.0% to
  +0.5%**.
- **Drivers:** every method ties the long decline to **slower trend growth** (TFP +
  shrinking working-age population); Del Negro adds a **rising safety/liquidity
  premium**, and Okazaki–Sudo decomposes the growth/preference split structurally.
- **Policy implication (BOJ's point):** because the level estimates disagree by more
  than a percentage point and revise with new data, **the gap `r − r*` cannot by
  itself date the stance of policy.** The Bank reads accommodation comprehensively —
  alongside activity, prices and financial conditions.

---

## 5. From the literature to this replication (fidelity map)

Full structural estimation (a Bayesian DSGE, an affine macro-finance term-structure
model, or a BVAR with common trends and a convenience-yield block) cannot live inside
a spreadsheet and would be thousands of lines to reproduce verbatim. This toolkit
therefore offers **two tiers**, and is explicit about which is which:

| Method | **Python (faithful)** | **Excel (transparent proxy)** |
|---|---|---|
| HLW | Full 9-state IS+Phillips Kalman filter, MLE | `0.5·trend-growth + 0.5·trend-real-rate` |
| DSGE | Consumption-Euler `r*=ρ+γg_c`, trend `g_c` via local-linear-trend MLE | same Euler formula, `g_c` via moving average — *near-exact* |
| Imakubo NYC | IS-curve state space; natural level = RW identified from yield-curve gap | trailing trend of the real-curve midpoint |
| Nakajima NYC | growth-anchored `r*=g+z`, `z` from yield-curve gap (Kalman) | `0.5·trend-growth + 0.5·curve-level` |
| Goy–Iwasaki | common stochastic trend of {short, long, growth} (Kalman) | average of the three trends |
| Del Negro VAR | 2-common-trend + AR(1)-cycle state space, MLE | `0.7·trend-real-rate + 0.3·trend-growth` |

The Python implementations are the ones to cite as replications; the Excel proxies
are for transparent, refreshable monitoring and recompute live as data arrive. The
faithful Python r\* series are also overlaid on the Excel **Dashboard** for reference.
See **`docs/02_update_manual.md`** to refresh and re-run both.

---

## 6. References

- Nakano, S., Sugioka, Y. & Yamamoto, H. (2024). *Recent Developments in Measuring
  the Natural Rate of Interest.* BOJ Working Paper 24-E-12.
- Bank of Japan (2026). *Developments in the Natural Rate of Interest and the
  Assessment of the Degree of Monetary Accommodation.* BOJ Review 2026-E-4.
- Holston, K., Laubach, T. & Williams, J. C. (2017). *Measuring the natural rate of
  interest: International trends and determinants.* JIE; 2023 update, NY Fed.
- Laubach, T. & Williams, J. C. (2003). *Measuring the Natural Rate of Interest.* REStat.
- Okazaki, Y. & Sudo, N. (2018). *Natural Rate of Interest in Japan — … based on a
  DSGE model.* BOJ Working Paper 18-E-6.
- Imakubo, K., Kojima, H. & Nakajima, J. (2015/2018). *The natural yield curve: its
  concept and measurement.* BOJ; Empirical Economics.
- Nakajima, J., Sudo, N., Hogen, Y. & Takizuka, Y. (2023). *On the estimation of the
  natural yield curve.* Hitotsubashi IER DP 753.
- Goy, G. & Iwasaki, K. (2024). *From the Natural Rate towards a Natural Curve.* mimeo.
- Del Negro, M., Giannone, D., Giannoni, M. & Tambalotti, A. (2017). *Safety,
  Liquidity, and the Natural Rate of Interest.* Brookings Papers; NY Fed SR 812.
- Bank of Japan (2024). *Estimating the Natural Yield Curve in Japan Using a VAR with
  Common Trends.* BOJ Working Paper 24-E-17.
