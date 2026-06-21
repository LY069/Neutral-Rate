"""Smoke tests: every method runs on the bundled sample and returns sane r*."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neutralrate import data  # noqa: E402
from neutralrate.methods import METHOD_REGISTRY  # noqa: E402

PANEL = data.load_panel(offline=True)


def test_panel_built():
    for col in ["log_gdp", "inflation", "real_short_rate", "real_10y", "gdp_growth"]:
        assert col in PANEL.columns
    assert len(PANEL) > 100


RESULTS = {}


def test_each_method_runs():
    for name, (module, _cite) in METHOD_REGISTRY.items():
        res = module.estimate(PANEL)
        rs = res.r_star.dropna()
        RESULTS[name] = rs
        assert len(rs) > 50, f"{name}: too few estimates"
        # r* should be finite and economically plausible for Japan (-6%..8%)
        assert np.isfinite(rs).all(), f"{name}: non-finite r*"
        assert rs.between(-6, 8).mean() > 0.9, f"{name}: implausible r* range"


def test_smoothness():
    """r* is a slow trend: qoq volatility must stay BoJ-like (no cyclical leak)."""
    for name, rs in RESULTS.items():
        qoq = rs.diff().dropna().std()
        assert qoq < 0.20, f"{name}: r* too volatile (qoq std {qoq:.3f} >= 0.20)"


def test_nyc_ordering():
    """Growth-anchored Nakajima sits above curve-anchored Imakubo (as in BoJ Chart 3)."""
    ima = RESULTS["Natural Yield Curve (Imakubo et al. 2015)"].iloc[-1]
    nak = RESULTS["Natural Yield Curve (Nakajima et al. 2023)"].iloc[-1]
    assert nak >= ima, f"ordering broken: Nakajima {nak:.2f} < Imakubo {ima:.2f}"


def test_nelson_siegel_recovers_factors():
    """The NS curve engine must recover known level/slope/curvature factors."""
    import pandas as pd
    from neutralrate.methods import _nelson_siegel as ns
    mats = [1, 2, 3, 5, 7, 10, 20, 30]
    beta = np.array([1.0, -1.2, 0.4])
    y = ns.loadings(mats, 0.7) @ beta
    curve = pd.DataFrame([y], columns=mats, index=pd.to_datetime(["2020-01-01"]))
    got = ns.fit_factors(curve, 0.7).iloc[0].to_numpy()
    assert np.allclose(got, beta, atol=1e-6), f"NS factors not recovered: {got}"


def test_full_curve_path_active():
    """The bundled sample carries a JGB curve, so build_features must decompose
    it into Nelson-Siegel factors that the term-structure methods consume."""
    for col in ["ns_level", "ns_slope", "ns_curvature", "ns_real_short",
                "ns_real_10y"]:
        assert col in PANEL.columns, f"{col} missing - curve path inactive"
        assert PANEL[col].notna().any(), f"{col} all-NaN"


def test_tax_adjustment():
    """Consumption-tax de-tax: level-based pure path and flag-gated YoY-window path."""
    import pandas as pd
    from neutralrate import config
    from neutralrate.data import _tax_adjust, tax_excluded_index

    # tax_excluded_index is a PURE de-tax (always applied regardless of flag).
    # The wedge is CUMULATIVE from the first hike (1989), so:
    #   - a date before ANY hike (pre Apr-1989) is unchanged;
    #   - crossing the Apr-2014 hike divides the index by exactly 1.02
    #     (isolated as a before/after ratio, independent of earlier hikes).
    idx = pd.date_range("1985-01-01", "2016-01-01", freq="MS")
    s = pd.Series(100.0, index=idx)
    adj_idx = tax_excluded_index(s)
    assert abs(adj_idx.loc["1988-01-01"] - 100.0) < 1e-9          # before all hikes
    ratio = adj_idx.loc["2014-05-01"] / adj_idx.loc["2014-03-01"]  # across Apr-2014
    assert abs(ratio - 1.0 / 1.02) < 1e-6

    # _tax_adjust (YoY-window path) is gated by ADJUST_CONSUMPTION_TAX.
    # Test the correct outcome for whichever value the config currently carries.
    yoy = pd.Series(1.0, index=pd.date_range("2013-01-01", "2015-12-01", freq="QS"))
    adj_yoy = _tax_adjust(yoy, yoy=True)
    if config.ADJUST_CONSUMPTION_TAX:
        assert abs(adj_yoy.loc["2014-07-01"] - (1.0 - 2.0)) < 1e-9  # stripped
        assert abs(adj_yoy.loc["2013-07-01"] - 1.0) < 1e-9           # outside untouched
    else:
        assert (adj_yoy == yoy).all()  # pass-through: CPI input already tax-excluded


if __name__ == "__main__":
    test_panel_built()
    test_each_method_runs()
    test_smoothness()
    test_nyc_ordering()
    test_nelson_siegel_recovers_factors()
    test_full_curve_path_active()
    test_tax_adjustment()
    print("All smoke tests passed.")
