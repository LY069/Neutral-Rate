"""
Run all six natural-rate methods and assemble a combined output.

Usage
-----
    python -m neutralrate.run_all                 # live FRED data (needs key)
    python -m neutralrate.run_all --offline       # bundled synthetic sample
    python -m neutralrate.run_all --refresh       # force fresh FRED pull
    python -m neutralrate.run_all --out ../output # output directory

Outputs (in --out, default python/output):
    r_star_estimates.csv   : quarterly r* by method + cross-method mean/range
    method_params.json     : estimated parameters per method (also feeds Excel)
    r_star_chart.png       : comparison chart (if matplotlib available)
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

from . import data
from .methods import METHOD_REGISTRY


def run(panel: pd.DataFrame):
    results, params = {}, {}
    for name, (module, _cite) in METHOD_REGISTRY.items():
        try:
            res = module.estimate(panel)
            results[name] = res.r_star
            params[name] = getattr(res, "params", {})
            print(f"  [ok]   {name}: latest r* = {res.r_star.dropna().iloc[-1]:+.2f}%")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] {name}: {exc}")
    table = pd.DataFrame(results)
    table["cross_method_mean"] = table.mean(axis=1)
    table["cross_method_min"] = table.iloc[:, :len(results)].min(axis=1)
    table["cross_method_max"] = table.iloc[:, :len(results)].max(axis=1)
    return table, params


def _maybe_plot(table: pd.DataFrame, path: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        print("  (matplotlib not available - skipping chart)")
        return
    method_cols = [c for c in table.columns if not c.startswith("cross_method")]
    fig, ax = plt.subplots(figsize=(11, 6))
    for c in method_cols:
        ax.plot(table.index, table[c], label=c, lw=1.3)
    ax.fill_between(table.index, table["cross_method_min"], table["cross_method_max"],
                    color="grey", alpha=0.15, label="cross-method range")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_title("Japan natural rate of interest (r*) - six estimation methods")
    ax.set_ylabel("annualized %")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print(f"  chart -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use bundled sample")
    ap.add_argument("--refresh", action="store_true", help="force fresh FRED pull")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "..", "output"))
    args = ap.parse_args()

    print("Loading data...")
    if args.refresh:
        panel = data.refresh(offline=args.offline)
    else:
        panel = data.load_panel(offline=args.offline)
    print(f"  panel: {panel.index.min().date()} -> {panel.index.max().date()}, "
          f"{len(panel)} quarters")

    print("Estimating six methods...")
    table, params = run(panel)

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "r_star_estimates.csv")
    table.to_csv(csv_path)
    with open(os.path.join(args.out, "method_params.json"), "w") as fh:
        json.dump(params, fh, indent=2, default=float)
    _maybe_plot(table, os.path.join(args.out, "r_star_chart.png"))
    print(f"\nDone. Estimates -> {csv_path}")
    print(table.dropna(how="all").tail(8).round(2).to_string())


if __name__ == "__main__":
    main()
