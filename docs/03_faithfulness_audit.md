# Faithfulness Audit — our replications vs. the BoJ-paper models

*Scope:* a model-by-model comparison of what each source paper actually estimates
versus what this toolkit computes, identifying the **structural** reason each
estimate diverges from BoJ's published Chart 3 — as opposed to the level/calibration
"gaps" tuned in earlier commits. Where full replication is feasible it is flagged
as such; where it is not, the blocking reason is stated explicitly.

Primary source for BoJ's own implementations: Nakano, Sugioka & Yamamoto (2024),
*Recent Developments in Measuring the Natural Rate of Interest*, BoJ WP 24-E-12
(summarised in BOJ Review 2026-E-4), plus each underlying paper (references at end).

---

## 0. The two root causes (read this first)

Every divergence below reduces to one of two structural facts. They are **not**
calibration errors and cannot be closed by re-tuning a parameter.

### Root cause A — the term-structure methods are not curve-based
**Four of the six methods** — Imakubo–Kojima–Nakajima (2015), Nakajima et al.
(2023), Goy–Iwasaki (2024), and the series BoJ labels "Del Negro" for Japan
(actually Hatayama–Iwasaki 2024, WP 24-E-17) — are built on a **Nelson–Siegel
decomposition of the *full* JGB yield curve** (level / slope / curvature
factors), several of them via a **shadow-rate** term-structure model to respect
the zero lower bound. r\* is the short end of an estimated *natural yield curve*,
and the term premium is a separate, separately-trending object.

Historically this toolkit fetched **only two maturities** — the 3-month
interbank rate and the 10-year JGB — and collapsed them to a single midpoint in a
scalar Laubach–Williams IS curve. With two points there is **no
level/slope/curvature identification, no natural *curve*, and no term-premium
trend**. Every term-structure method was therefore a *scalar proxy* of a *curve*
model. This is the dominant structural gap in the project.

> **Status update (curve scaffolding now in place).** The data layer and a
> Nelson–Siegel engine have since been added: `config.MOF_JGB_CURVE_SOURCE` +
> `data._fetch_mof_jgb` pull the **full MoF JGB constant-maturity curve**
> (1–40y), `data.build_features` deflates it (maturity-matched expectations) and
> decomposes it into level/slope/curvature via `methods/_nelson_siegel.py`, and
> the four term-structure methods consume the fitted curve when it is present
> (the 3m/10y midpoint remains the automatic fallback). What is **still
> outstanding**: (i) the *live* MoF endpoint is egress-blocked in this sandbox,
> so the curve currently runs on a synthetic full curve in the sample and has not
> been validated on real data; (ii) the shadow-rate front end (ZLB) and the
> affine no-arbitrage / common-trend-NS structures remain to be added for full
> fidelity. So root cause A is now *architecturally addressed but not yet
> validated on real data*.

### Root cause B — the structural models are collapsed to identities
The DSGE (Okazaki–Sudo) and the common-trends VAR (Del Negro / Hatayama–Iwasaki)
are full multi-equation estimators (Bayesian, many observables, structural
shocks). The toolkit replaces each with a 1–4 equation reduced form and **drops
the paper's central mechanism** (the DSGE's neutral-technology and
financial-intermediation channels; the VAR's convenience-yield / term-premium
identification). The level adjustments in earlier commits (e.g. DSGE `rho=-0.8`)
are *constant stand-ins* for those omitted channels — useful for monitoring, but
not replications of the structure that generates them.

**Consequence:** the gaps vs. Chart 3 are structural. Earlier commits made the
proxies *track BoJ's level* better and fixed two genuine identification bugs, but
did not — and by construction cannot — close the structural gap.

---

## 1. Environment constraints (why full replication cannot be completed *here*)

These are hard blockers in the current sandbox, independent of the modelling:

1. **No real data.** Network egress allows only GitHub/PyPI; `api.stlouisfed.org`,
   `fred.stlouisfed.org`, `api.e-stat.go.jp`, `api.db.nomics.world`, `boj.or.jp`,
   `newyorkfed.org` all return `403 Host not in allowlist`. Every method can only
   be run on the bundled **synthetic** sample, so no fuller model could be
   *validated* against BoJ even if coded.
2. **Two-maturity data only.** The synthetic sample and the FRED catalog carry
   only 3m and 10y rates, so the Nelson–Siegel curve at the heart of four methods
   cannot even be prototyped offline (NS needs ≥3–4 maturities).
3. **Missing input series.** Faithful replication needs series the toolkit never
   fetches: the full JGB curve (MoF: 1/2/5/20/30/40y), corporate–government
   spreads (US Del Negro convenience yield), business investment, hours, real
   wages (Okazaki–Sudo DSGE), and survey expectations of *growth* (Del Negro).
4. **Estimation machinery.** Several papers are Bayesian (MCMC) with
   paper-specific priors/calibrations that are not recoverable from abstracts; the
   toolkit uses fixed-variance MLE/Kalman by design.

Where a method is marked "blocked" below, it is blocked by some combination of
these four, made explicit each time.

---

## 2. Method-by-method audit

### Method 1 — HLW (Holston–Laubach–Williams) — **FAITHFUL**
* **Paper:** semi-structural state space — IS curve (output gap on the real-rate
  gap), Phillips curve, random-walk trend growth `g` and "other factor" `z`,
  `r* = 4·c·g + z`; MLE with Stock–Watson median-unbiased signal-to-noise.
* **Ours (`methods/_lw.py`):** the same 9-state IS+Phillips Kalman filter with the
  original two-lag real-rate-gap IS term; signal-to-noise *fixed* (not
  median-unbiased) to avoid the pile-up problem.
* **Divergence / gap:** minor (latest gap ≈ +0.04, corr ≈ 0.78). The only
  deliberate simplification is fixing the trend variances rather than estimating
  the ratio. **This is the one structurally faithful method.**
* **Replicable fully?** Essentially already is; adding Stock–Watson
  median-unbiased estimation is the only remaining refinement (feasible, but needs
  real data to matter).

### Method 2 — Okazaki–Sudo (2018) DSGE — **REDUCED-FORM IDENTITY (central mechanism dropped)**
* **Paper (WP 18-E-6):** a **medium-scale New-Keynesian DSGE**, Bayesian-estimated
  on Japanese data (1980–2017) with **five structural drivers**: (i) neutral
  technology — *the dominant driver of the r\* decline* — (ii) investment-specific
  technology, (iii) functioning of financial intermediation (a spread/wedge),
  (iv) demographics (working-age population), (v) demand/preference factors. r\*
  is the model's **flexible-price real rate**, which moves with *all* of these
  shocks and their trends — not with consumption growth alone.
* **Ours (`methods/dsge.py`):** a single steady-state Euler identity
  `r* = rho + gamma·g_c`, with `g_c` = a local-linear-trend of per-capita
  consumption. One driver (a smoothed consumption/productivity trend); `rho` a
  constant.
* **Root cause of the gap:** we keep the steady-state identity and **one** of five
  drivers. Neutral technology (the dominant channel) is not a model object here;
  the financial-intermediation wedge — the spread between the policy rate and the
  return on capital — is exactly what the earlier `rho = -0.8` constant
  *crudely stands in for* (a level, not a time-varying wedge). The residual
  mid-1990s shape gap is because BoJ's estimated neutral-technology trend fell
  *faster* than smoothed consumption growth does. So the gap is the four missing
  channels, not the value of `rho`.
* **Replicable fully?** **No, blocked.** Requires the full DSGE equation system, a
  solver, Bayesian estimation, and observables (investment, hours, wages) that are
  neither fetched nor reachable. (FRBNY publishes Julia DSGE machinery, but not
  Okazaki–Sudo's Japan model/priors.)

### Method 3 — Imakubo–Kojima–Nakajima (2015) natural yield curve — **SCALAR PROXY of a curve model**
* **Paper (WP 15-E-5):** estimate a **shadow-rate term-structure model** of the
  Japanese curve → decompose the *real* yield curve into **Nelson–Siegel
  level/slope/curvature** factors across the full maturity spectrum; an
  LW-type IS curve responds to the **yield-curve gap** (actual minus natural curve
  at every maturity). r\* = short end of the natural curve.
* **Ours (`methods/natural_yield_curve.py`):** the midpoint of the 3m and 10y real
  rates as the single real rate inside the standard scalar LW IS curve.
* **Root cause of the gap:** no full curve, no NS factors, no shadow-rate ZLB
  handling, no yield-curve *gap*. It fits BoJ reasonably (corr ≈ 0.85–0.93) only
  because the secular level/trend dominates the short end. The *curve* content —
  the whole point of the paper — is absent.
* **Replicable fully?** **Partially; blocked by data.** The NS + shadow-rate state
  space is codeable, but needs ≥4 JGB maturities (have 2) and real data to fit.

### Method 4 — Nakajima, Sudo, Hogen & Takizuka (2023) — **PROXY of the growth anchor + curve model**
* **Paper (Hitotsubashi DP 753; pub. *J. Int. Money & Finance* 2022, "Potential
  growth and natural yield curve in Japan"):** refines Imakubo by anchoring the
  natural curve's level to a **jointly-estimated potential growth** (a
  production-function / multi-input object — labour input, capital, TFP), with the
  full curve and explicit estimation-uncertainty treatment.
* **Ours (`methods/nakajima_nyc.py`):** r\* = a **univariate** local-linear-trend
  of log GDP, re-levelled halfway toward the realised real-rate curve.
* **Root cause of the gap:** "potential growth" is proxied by a *univariate GDP
  trend*, not the paper's multi-input potential-growth estimate. BoJ's series is
  **stationary-cyclical around ~0.5 and rises recently** (labour-input / TFP
  recovery, post-2013 and post-2022); a monotone univariate GDP trend cannot
  reproduce that recovery, which caps the correlation (~0.61) regardless of
  re-levelling. The earlier change correctly identified that the LW `4cg+z` form
  mis-correlated, but the trend-growth anchor is still a *proxy* of the paper's
  potential-growth construct.
* **Replicable fully?** **Partially; blocked by data and by the missing
  potential-growth block** (needs capital stock, labour input, TFP, full curve).

### Method 5 — Goy–Iwasaki (2024) macro-finance natural curve — **1-FACTOR PROXY of an affine model**
* **Paper:** a **trend–cycle macro-finance** model with a **no-arbitrage affine**
  term structure; a single slow real trend is *simultaneously* the curve's level
  factor and the natural rate that closes the output gap; estimated across the
  full curve, yielding a term-premium decomposition.
* **Ours (`methods/goy_iwasaki.py`):** a 1-factor common trend on {real short,
  real 10y, trend growth}, loadings fixed to 1, **no** no-arbitrage cross-equation
  restrictions, two maturities.
* **Root cause of the gap:** no affine/no-arbitrage structure, no full curve, no
  term-premium block. The earlier "fix loadings to 1" is a *defensible
  identification* (the NS level factor loads 1 on every maturity) and removed a
  real under-identification bug — but it is not the affine model.
* **Replicable fully?** **Partially; blocked by data** (full curve) and by the
  affine no-arbitrage estimation machinery.

### Method 6 — "Del Negro et al. (2017)" — **WRONG MODEL FAMILY for Japan + missing block**
* **What BoJ's Chart 3 "Del Negro" column actually is:** for Japan, BoJ uses
  **Hatayama–Iwasaki (2024), WP 24-E-17**, which *combines the **Nelson–Siegel**
  model of the full nominal **and** real JGB curves with a **VAR with common
  trends***; observables = the nominal & real curves + output gap + inflation; it
  finds r\* trending down **and the term premium trending down** (curve
  flattening). It is a *curve* model, in the same NS family as methods 3–5.
* **The original US paper (NY Fed SR 812 / Brookings 2017):** a **Bayesian VAR
  with common trends** on Treasury **and corporate** yields, inflation, and
  long-run **survey expectations**; the **convenience yield** (safety+liquidity
  premium) is identified by the **corporate-minus-Treasury spread** and is the
  *central* driver of r\*. (Replication code: `FRBNY-DSGE/rstarBrookings2017`,
  Julia, MCMC.)
* **Ours (`methods/delnegro_var.py`):** a 4-variable **MLE** state space {real
  short, real 10y, growth, inflation}; the "convenience/term-premium" trend
  `f_sp` is just the **10y-minus-short term spread**; fixed trend variances.
* **Root cause of the gap:** we replicate **neither** model. Against BoJ's actual
  Japan method we lack the Nelson–Siegel full-curve structure; against the US
  paper we lack the **corporate-spread convenience-yield identification** (its
  whole point), so `f_sp` conflates the term premium with the convenience yield.
  The earlier `sigma_fr`/cycle-cap changes only smoothed the trend and fixed a
  determinism bug; they do not add the missing identification.
* **Replicable fully?** **No, blocked.** The BoJ version needs the full JGB curve
  (have 2 maturities); the US version needs corporate-spread data + survey growth
  expectations + Bayesian MCMC. Both blocked by data/egress.

---

## 3. Honest status of the earlier (prior-commit) changes

| Change | Nature | Keep? |
|---|---|---|
| Goy–Iwasaki: loadings fixed to 1 + noise floor | **Genuine identification fix** — removed a flat-ridge under-identification that made r\* non-deterministic across runs | Keep (correctness) |
| Del Negro: σ_fr 0.07→0.04, cycle cap →0.97, φ≥0 | **Genuine identification/robustness fix** — stops trend/cycle leakage and a perverse-sign loading; now deterministic | Keep (correctness) |
| DSGE: `rho` 0 → −0.8 | **Reduced-form proxy** — a constant standing in for the DSGE's financial-wedge/preference channels | Keep *as a labelled monitoring calibration*, not a structural fix |
| Nakajima: trend-growth anchor + halfway re-level | **Reduced-form proxy** — stands in for the paper's potential-growth + curve block | Keep *as a labelled proxy* |

The two identification fixes are worth keeping regardless of the level debate
(they make previously unstable estimators reproducible). The two proxy
calibrations should be read as *transparent-tier* monitoring choices, **not** as
faithful structural replications — that distinction is the substance of this audit.

---

## 4. What faithful replication would actually require (roadmap)

In dependency order:

1. **Data layer (prerequisite for 4 of 6 methods).** — *JGB curve DONE
   (scaffolded).*
   - Full JGB curve from MoF: `config.MOF_JGB_CURVE_SOURCE`,
     `JGB_CURVE_MATURITIES` (1–40y), `data._fetch_mof_jgb`; synthetic full curve
     added to the sample via `scripts/add_curve_to_sample.py`. *Live fetch
     pending egress (`www.mof.go.jp`) — point the source at a local CSV meanwhile.*
   - Still missing: corporate–government spreads (US Del-Negro convenience
     yield); investment, hours, real wages (Okazaki–Sudo DSGE); survey
     expectations of *growth* (Del Negro).
2. **A Nelson–Siegel curve module** producing level/slope/curvature factors,
   feeding methods 3–6. — *DONE: `methods/_nelson_siegel.py`, wired through
   `build_features`; methods consume the fitted curve with a 3m/10y fallback.*
   Remaining: a **shadow-rate** front end (ZLB) for the deep-ZLB years.
3. **Method-specific full estimators:** Okazaki–Sudo DSGE (model + Bayesian
   estimation); Goy–Iwasaki affine no-arbitrage term structure; Hatayama–Iwasaki /
   Del Negro common-trends **Bayesian** VAR (MCMC + priors). — *Not started;
   the heaviest lift.*
4. **Real-data validation** vs. Chart 3 (`scripts/validate_vs_boj.py` already maps
   the columns; it just needs a real-data run once egress is opened).

Steps 1–2 (the curve) are now implemented; with them the term-structure methods
are genuinely curve-based when a full curve is supplied. What remains is real-data
validation (egress) and the full structural estimators for methods 2 & 6. That —
not parameter calibration — is why the residual gaps exist.

---

## References
- Nakano, Sugioka & Yamamoto (2024), *Recent Developments in Measuring the Natural
  Rate of Interest*, BoJ WP 24-E-12. https://www.boj.or.jp/en/research/wps_rev/wps_2024/wp24e12.htm
- Okazaki & Sudo (2018), *Natural Rate of Interest in Japan — … based on a DSGE
  Model*, BoJ WP 18-E-6. https://www.boj.or.jp/en/research/wps_rev/wps_2018/wp18e06.htm
- Imakubo, Kojima & Nakajima (2015), *The Natural Yield Curve: its concept and
  measurement*, BoJ WP 15-E-5. https://www.boj.or.jp/en/research/wps_rev/wps_2015/wp15e05.htm
- Nakajima, Sudo, Hogen & Takizuka (2023), *On the estimation of the natural yield
  curve*, Hitotsubashi DP 753 / *J. Int. Money & Finance* (2022).
  https://ideas.repec.org/p/hit/hituec/753.html
- Goy & Iwasaki (2024), *From the Natural Rate towards a Natural Curve.*
- Hatayama & Iwasaki (2024), *Estimating the Natural Yield Curve in Japan Using a
  VAR with Common Trends*, BoJ WP 24-E-17.
  https://www.boj.or.jp/en/research/wps_rev/wps_2024/wp24e17.htm
- Del Negro, Giannone, Giannoni & Tambalotti (2017), *Safety, Liquidity, and the
  Natural Rate of Interest*, NY Fed SR 812 / Brookings.
  https://www.newyorkfed.org/research/staff_reports/sr812.html ;
  code: https://github.com/FRBNY-DSGE/rstarBrookings2017
