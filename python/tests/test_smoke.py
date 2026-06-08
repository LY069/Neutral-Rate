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


def test_each_method_runs():
    for name, (module, _cite) in METHOD_REGISTRY.items():
        res = module.estimate(PANEL)
        rs = res.r_star.dropna()
        assert len(rs) > 50, f"{name}: too few estimates"
        # r* should be finite and economically plausible for Japan (-6%..8%)
        assert np.isfinite(rs).all(), f"{name}: non-finite r*"
        assert rs.between(-6, 8).mean() > 0.9, f"{name}: implausible r* range"


if __name__ == "__main__":
    test_panel_built()
    test_each_method_runs()
    print("All smoke tests passed.")
