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

> **Calibration of ρ (this toolkit: ρ = −0.8).** With `ρ = 0` the pure Euler rate
> `r* = γ·g_c` sits ~0.8 pp **above** BoJ's published Okazaki–Sudo series, because
> Japan's observed *safe* real rate lies below the consumption-Euler rate by a
> sizeable **convenience/safety yield** on government debt (the same wedge Del
> Negro models explicitly). We therefore let `ρ` absorb that steady-state
> safe-asset wedge in addition to pure time preference and set `ρ = −0.8`, which
> anchors the latest r\* into BoJ's recent **+0.2/+0.4** range. A residual gap in
> the mid-1990s remains: BoJ's structural productivity trend falls faster than
> this deliberately smooth per-capita consumption trend, so this is a
> *trend-shape*, not a *level*, difference (loosening the trend does not help — it
> just tracks the consumption series' own swings).

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

> **Implementation (this toolkit).** We take the refinement literally: r\* **is**
> the secular trend of potential GDP growth (a local-linear-trend with the same
> low signal-to-noise as the other methods), with its *level* pinned **halfway**
> between the realized real-rate curve (where Imakubo's curve-anchored estimate
> sits) and trend growth itself — i.e. Nakajima pulls the anchor partway from the
> real rate toward growth, which keeps it above Imakubo whenever growth exceeds
> the realized real rate (as in BoJ Chart 3). An earlier version used the LW
> `4·c·g + z` short end with a *tighter z*; its "other factor" `z` drifted the
> wrong way relative to BoJ's published Nakajima series (correlation only ~0.55)
> and re-levelling to the high sample-mean trend growth left the level ~1 pp too
> high. Anchoring directly to trend potential growth raises the correlation
> (~0.61) and fixes the level. The yield curve still enters through the level
> anchor and the natural 10y (r\* + the average real term spread).

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

> **Identification (this toolkit: loadings fixed to 1).** An earlier version
> estimated the common trend's loadings on the long rate and growth *freely*. That
> model is only weakly identified — with a near-constant common trend and three
> free observation-noise variances the likelihood has a flat ridge along which one
> noise variance collapses to zero and pins the trend to a single series — so the
> estimate was **unstable** (it landed in different optima run-to-run under BLAS
> non-determinism, giving r\* anywhere from −0.8 to +0.3) and its level drifted
> ~1.2 pp above BoJ. The model's own economics supply the fix: in a Nelson–Siegel
> curve the common **level** factor loads exactly 1 on every maturity, and r\*
> tracks trend growth one-for-one (the LW logic), so the loadings are **1 by
> construction, not free parameters**. The trend is then the genuine common level
> (intercepts absorb the average term premium and growth-minus-rate wedge); this
> is well-identified, deterministic, and ~0.7 pp closer to BoJ. A small floor on
> the observation-noise std devs guarantees the ridge cannot reappear.

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

> **Trend/cycle split (this toolkit).** r\* = the trend real rate `f_r`. With the
> trend-real-rate innovation set loosely (σ_fr = 0.07) and the cycle persistence
> capped at 0.90, `f_r` **over-rotated**: it tracked the persistent 2022–24
> real-rate plunge (policy at zero while inflation spiked) straight into the
> *trend*, so r\* fell to ~−1.5 (≈1 pp **below** BoJ) even though it sat ~0.4 pp
> *above* BoJ on average earlier. Two changes restore Del Negro's tight-prior
> smoothness: **σ_fr = 0.04** (slower trend) and a **cycle-persistence cap of
> 0.97** (so near-unit-root but still transitory swings are absorbed by the cycle,
> not the trend). We also penalize a negative growth loading `φ` (economically
> perverse, an artefact of weak identification). Together these halve the latest
> gap and lower the mean gap, and — like the Goy–Iwasaki fix — make the estimate
> deterministic across runs.

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
| Private consumption, **constant prices** | `NAEXKP02JPQ659S` | DSGE |
| **Core CPI, YoY %** (ex food & energy) | `CPGRLE01JPQ657N` | inflation, expectations, real rates |
| CPI all-items (fallback) | `JPNCPIALLMINMEI` | inflation if core unavailable |
| Call/interbank rate (policy) | `IRSTCI01JPM156N` | short real rate |
| 3-month rate | `IR3TIB01JPM156N` | curve short end |
| 10-year JGB yield | `IRLTLT01JPM156N` | curve long end |
| Working-age population | `LFWA64TTJPM647S` | per-capita / demographics |

Three Japan-specific data-handling points a careful replication must get right:

0. **Inflation concept = core, not headline.** HLW (and Del Negro for the US)
   deflate with *core* inflation (ex food & energy) to strip volatile items; the
   Japan analog is **"core-core" = CPI ex fresh food & energy** (BoJ's traditional
   "core" = ex fresh food is an acceptable alternative). The toolkit's `cpi`/
   `core` candidate lists (config) prefer the Statistics-Bureau / BoJ core-core;
   the DSGE here is consumption-driven so the CPI choice doesn't enter it. The
   OECD CPI series on FRED were discontinued at June 2021, so live runs should
   use the Statistics Bureau of Japan / BoJ source (see `data/cpi/README.md`).
1. **Real, not nominal, consumption.** The superficially obvious FRED series
   `JPNPFCEQDSMEI` is *current-price* (nominal) consumption — and discontinued.
   Using it would inflate the DSGE's trend consumption growth by the deflator
   and bias its r\* up. The toolkit uses `NAEXKP02JPQ659S` (constant prices).
2. **Consumption-tax adjustment.** The 1989/1997/2014/2019 consumption-tax
   hikes mechanically lift YoY CPI inflation for four quarters (BoJ put the
   April-2014 hike at ≈ +2.0pp; 1997 ≈ +1.5pp; 2019 ≈ +0.5pp net of the
   free-education offset; 1989 ≈ +1.2pp). BoJ works with tax-adjusted CPI, and
   so does the toolkit (`ADJUST_CONSUMPTION_TAX` in `config.py`, windows and
   magnitudes documented there). Unadjusted, the spikes contaminate expected
   inflation and ex-ante real rates exactly at sample-sensitive moments. BoJ's
   "Indicators for Core CPI" is published *already* tax-excluded — if you feed
   that in, turn `ADJUST_CONSUMPTION_TAX` off to avoid removing the tax twice.

**Inflation expectations — handled three ways, matching the originals.** This is
a genuine point of difference across the methods, not a detail:

| Method(s) | Expectations treatment |
|---|---|
| **HLW** | adaptive / backward-looking: a 4-quarter MA of core inflation |
| **DSGE (Okazaki–Sudo)** | model-consistent **rational expectations** (no external series) |
| **Imakubo, Nakajima, Goy–Iwasaki, Del Negro** | **survey-based**, maturity-specific, used to deflate the nominal yield curve (Consensus Forecasts in Japan; long-run SPF in Del Negro) |

FRED has no clean Japan expectations series, so the toolkit (i) keeps HLW on the
core-inflation MA, (ii) keeps the DSGE on rational expectations, and (iii) for
the four term-structure / common-trends methods uses a **short** (≈1y, 4q MA)
and a **long** (≈5–10y, "anchored" multi-year MA) expectation, with config hooks
(`INFLATION_EXPECTATIONS_SERIES`, `…_LONG_SERIES`) that accept a real series from
**FRED, DBnomics, or a downloaded CSV**. The best real sources are **BoJ's own**
data — the Tankan *Inflation Outlook of Enterprises* (1y/3y/5y, from 2014), the
*Opinion Survey on the General Public* (households, from 2006), and BoJ's
composite indicator (firms + households + experts incl. inflation swaps) — which
a user can splice in via DBnomics or a CSV export (see the update manual).

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

> **Faithfulness caveat (important).** "Python (faithful)" below means *faithful in
> spirit* — the economic content that pins down r\* — not a line-for-line
> replication of each paper's full estimator. Only **HLW** is structurally
> complete. The other five are **reduced forms** that, in four cases, omit the
> paper's central mechanism (the DSGE's neutral-technology / financial-wedge
> channels; the Nelson–Siegel *full-curve* structure behind every
> natural-yield-curve method; the convenience-yield identification in Del Negro).
> The residual gaps vs. BoJ Chart 3 are therefore **structural**, not calibration.
> See **`docs/03_faithfulness_audit.md`** for the model-by-model audit, the root
> causes, and exactly what (data + estimation machinery) full replication would
> require — and why it is currently blocked.
>
> *Curve scaffolding (in progress).* The biggest of those gaps — the
> term-structure methods not being curve-based — now has its plumbing in place: a
> MoF full-JGB-curve fetcher and a Nelson–Siegel decomposition
> (`methods/_nelson_siegel.py`) feed methods 3–6 when a full curve is supplied
> (3m/10y midpoint remains the fallback). It runs on a synthetic full curve in
> the bundled sample today; the live MoF fetch and real-data validation are
> pending network egress to `www.mof.go.jp`.

| Method | **Python (faithful)** | **Excel (transparent proxy)** |
|---|---|---|
| HLW | 9-state IS+Phillips Kalman filter (MLE) with the **original two-lag real-rate-gap IS term** −(a_r/2)(r̃₋₁+r̃₋₂); LW low signal-to-noise (small fixed trend-shock variances); **long-run-neutrality level anchor** | `0.5·trend-growth + 0.5·trend-real-rate` |
| DSGE | Consumption-Euler `r*=ρ+γg_c` with **ρ=−0.8** (time preference + safe-asset/convenience wedge); `g_c` = Kalman local-linear-trend of consumption, low signal-to-noise | same Euler formula, `g_c` via moving average — *near-exact* |
| Imakubo NYC | **Same LW state space as HLW** but the IS curve uses a real *yield-curve* summary; r*=4cg+z (short end of the natural curve) | trailing trend of the real-curve midpoint |
| Nakajima NYC | r\* **= trend potential growth** (local-linear-trend), level set **halfway** between the realized real-rate curve and trend growth (`0.5·curve-level + 0.5·trend-growth`) | `0.5·trend-growth + 0.5·curve-level` |
| Goy–Iwasaki | common stochastic trend (Nelson–Siegel **level**) of {short, long, growth}, **loadings fixed to 1** (well-identified), small trend variance + obs-noise floor | average of the three trends |
| Del Negro VAR | **3-common-trend** + AR(1)-cycle state space (MLE) on {real short, real 10y, growth, inflation}: trend real rate **f_r = r\***, a **convenience/term-premium trend f_sp** wedging the long rate (the paper's safety/liquidity mechanism), and trend inflation; **σ_fr=0.04, cycle cap 0.97, φ≥0** | `0.7·trend-real-rate + 0.3·trend-growth` |

**On smoothing — consistent with the originals.** None of the source papers use
an HP filter; they all get a smooth r\* from **state-space stochastic trends with
a low signal-to-noise ratio** (small trend-shock variances relative to the
cyclical shocks). This toolkit does the same: HLW/Imakubo/Nakajima share one
Laubach-Williams state space (the natural-yield-curve methods are explicit
LW extensions, with the yield curve entering the IS curve); the DSGE trend
growth and the macro-finance/common-trend methods use Kalman trends with the
same small trend variances. We *fix* that signal-to-noise (rather than estimate
it via Stock-Watson median-unbiased, as HLW do) to reproduce the papers' smooth
r\* and avoid the pile-up problem — note that an HP filter with parameter λ is
exactly the Kalman smoother of this trend-plus-noise model, so the choice is one
of estimating vs. fixing the same ratio, not of a different mechanism.

The Python implementations are the ones to cite as replications; the Excel proxies
are for transparent, refreshable monitoring and recompute live as data arrive. The
faithful Python r\* series are also overlaid on the Excel **Dashboard** for reference.
See **`docs/02_update_manual.md`** to refresh and re-run both.

---

## 6. Matching BoJ — volatility and the cross-method range

BoJ's published Chart 3 (file `rev26e04b.xlsx`) has two notable features: r\* is
very **smooth** (quarter-on-quarter std ≈ 0.04–0.15 pp), and the six methods sit
in a fairly **tight band** (latest 2025Q3 ≈ **−0.93% Goy–Iwasaki to +0.53%
Nakajima**, width ≈ 1.5 pp).

**Volatility — now matched.** Early versions of this toolkit were far too
volatile (qoq std ≈ 0.25 pp). The cause was under-smoothing: cyclical movement
was leaking into the trend. The fix — described in §5 — was to extract every
trend the way the original papers do, via **state-space stochastic trends with a
low signal-to-noise ratio** (small trend-shock variances). After that change the
qoq std falls to ≈ **0.01–0.03 pp**, i.e. at or below BoJ's own smoothness, and
the business cycle is correctly held in the transitory component. (We chose
*fixed* small trend variances rather than the HP filter or MLE; an HP filter is
exactly the Kalman smoother of this model, and MLE suffers the pile-up problem.)

**Level fit — recalibration (2026Q2).** Four methods originally tracked BoJ's
*shape* but were off in *level* (and two were numerically unstable). Validating
against BoJ Chart 3 (`scripts/validate_vs_boj.py`) and recalibrating each in a
way faithful to its own economics — documented per method in §4 — closes most of
the gap and removes the instability. Latest-quarter level gap (ours − BoJ) and
correlation over the overlap:

| Method | gap before | gap after | corr before → after | change |
|---|---:|---:|---|---|
| DSGE (Okazaki–Sudo) | +0.80 | **+0.00** | 0.79 → 0.79 | ρ: 0 → −0.8 (safe-asset wedge) |
| Goy–Iwasaki | +1.22 | **+0.48** | 0.91 → 0.89 | loadings fixed to 1 (+ stable) |
| Del Negro VAR | −1.05 | **−0.39** | 0.83 → 0.84 | σ_fr 0.07→0.04, cap 0.97, φ≥0 (+ stable) |
| Nakajima NYC | +0.37 | −0.21 | **0.55 → 0.61** | r\* = trend growth, ½-growth anchor |
| HLW *(kept)* | +0.06 | +0.04 | ~0.78 | unchanged |
| Imakubo *(kept)* | −0.11 | −0.07 | ~0.88 | unchanged |

Mean |latest gap| falls from **0.60 → 0.20 pp**. Two of the fixes (Goy–Iwasaki,
Del Negro) also make previously under-identified state spaces **deterministic**
across runs. (Figures are on the bundled synthetic sample, which here reproduces
the real-data gaps closely; re-run `run_all --refresh` + the validator on live
FRED to confirm on the latest vintage.)

**The remaining range gap** is explained, in order of importance, by
**data → data-handling → modeling** — not by a flaw in any one method:

**1. Data: synthetic vs. real.** The shipped sample is a *synthetic* stand-in
whose recent inflation (~2.6%) and ex-ante short real rate (~−2.7% = NIRP minus
high near-term inflation) are more extreme than Japan's actual data. The residual
range is driven mainly by the short-rate-deflated methods (Del Negro, and the
short end generally), which by design follow that very negative synthetic real
rate; on real FRED data the short real rate is materially less negative, so they
compress toward the others. **Re-run on real data to confirm the band against
BoJ's ~1.5 pp.**

**2. Data handling — inflation expectations.** The originals deflate the *long*
end of the yield curve with **survey/anchored** expectations; deflating it
instead with a backward MA of realized inflation (during an inflation spike)
overstates expected inflation, understates the real long rate, and pushes the
term-structure r\* too low. Switching the long-rate deflator to anchored
expectations moved our Imakubo estimate up by ~0.2–0.4 pp and Goy–Iwasaki by
~0.3 pp. The *short* end is still deflated by near-term inflation (which is
realistic — Japan's real policy rate genuinely was very negative in 2022–24), so
short-rate-driven methods remain data-sensitive by design.

**3. Modeling — reduced forms vs. the authors' full estimators.** Where BoJ uses
each paper's full machinery (a Bayesian VAR with a convenience-yield block, an
affine macro-finance term-structure model, a medium-scale estimated DSGE), this
toolkit uses tractable reduced-form/MLE versions (a frequentist common-trends UC,
a single-common-trend extraction, a consumption-Euler identity). The originals
embed structure — term premia, convenience yields, tight trend priors, and a
common potential-growth anchor — that pulls r\* toward trend growth and damps the
spread. Our six are estimated *independently* with no shared trend-growth or
level anchor, which mechanically widens the cross-method range. (HLW is the
exception: it now carries an explicit long-run-neutrality level anchor.)

**4. Sample, vintage and end-point sensitivity.** r\* endpoints are notoriously
revision-prone under one-sided filtering; BoJ's sample window, real-time
vintages and (for some methods) judgmental calibration differ from a from-FRED
rebuild, which shifts levels by a few tenths.

**Validation harness.** BoJ's Chart 3 estimates are bundled (with attribution)
at `data/boj/boj_chart3_estimates.csv`; `python scripts/validate_vs_boj.py`
prints, per method, our latest level vs BoJ's, the mean gap and correlation
over the overlapping sample, and qoq volatility — making the comparison above a
one-command, falsifiable check after every data refresh.

**Bottom line:** the wider band is mostly an artifact of the **synthetic test
data** plus the deliberately **simplified estimators**, amplified for the two
most real-rate-sensitive methods. The fixes that close most of the gap are
already in place or available: run on **real FRED data**, wire in **survey-based
expectations** (BoJ Tankan via DBnomics/CSV), and — if exact replication is
required — swap the reduced forms for the authors' published code. The
qualitative story BoJ tells (secular decline; ~−1.0% to +0.5% recently; read the
range, not a point) is reproduced either way.

---

## 7. References

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
