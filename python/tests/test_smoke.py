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


def test_tax_adjustment():
    """Consumption-tax effect is stripped from YoY inflation in the hike windows."""
    import pandas as pd
    from neutralrate.data import _tax_adjust
    idx = pd.date_range("2013-01-01", "2015-12-01", freq="QS")
    s = pd.Series(1.0, index=idx)
    adj = _tax_adjust(s, yoy=True)
    assert abs(adj.loc["2014-07-01"] - (1.0 - 2.0)) < 1e-9   # inside FY2014 window
    assert abs(adj.loc["2013-07-01"] - 1.0) < 1e-9           # outside untouched


if __name__ == "__main__":
    test_panel_built()
    test_each_method_runs()
    test_smoothness()
    test_nyc_ordering()
    test_tax_adjustment()
    print("All smoke tests passed.")
