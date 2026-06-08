"""
Build the refreshable Excel workbook for the six natural-rate methods.

    python excel/build_workbook.py                 # build from synthetic sample
    python excel/build_workbook.py --from-cache    # build from refreshed FRED cache

Design
------
* "Data" sheet  : the quarterly panel (raw FRED series + derived features).
                  Refresh it by (a) running scripts/refresh_data.py --excel, or
                  (b) a native Excel Power Query (see docs/02_update_manual.md).
* Helper columns (live formulas) : trailing trends, curve midpoint, etc.  They
                  recompute automatically whenever the Data sheet is refreshed.
* Six r* columns (live formulas) : an economically-faithful *reduced-form proxy*
                  of each method, computed entirely from the Data columns so the
                  workbook updates with new data without re-estimation.
* "Dashboard"   : overlays the six proxies (+ the Python faithful estimates when
                  python/output/r_star_estimates.csv is present) with a chart.
* "Settings"    : window length, DSGE rho/gamma, average real term spread.

The Excel models are deliberately transparent proxies; the faithful
state-space/MLE estimates live in the Python package (see the research report
and manual for exactly where each is exact vs. approximated).
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(__file__)
WB_PATH = os.path.join(HERE, "Japan_Neutral_Rate_Models.xlsx")
sys.path.insert(0, os.path.join(HERE, "..", "python"))

# Trailing-window length (quarters) used for all trend / moving-average columns.
# Baked into explicit ranges at build time (robust + non-volatile); shown on the
# Settings sheet and re-applied whenever the workbook is rebuilt / refreshed.
DEFAULT_WINDOW = 20

# Order of columns written to the Data sheet (logical feature names).
DATA_COLS = [
    "real_gdp", "consumption", "cpi", "core_cpi_yoy", "short_rate", "rate_3m",
    "rate_10y", "working_age_pop", "log_gdp", "log_cons", "gdp_growth",
    "cons_growth", "inflation", "inflation_yoy", "exp_inflation",
    "real_short_rate", "real_10y", "real_3m",
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
TITLE_FONT = Font(bold=True, size=14, color="1F4E78")
NOTE_FONT = Font(italic=True, size=9, color="555555")
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


# --------------------------------------------------------------------------- #
def _load_features(from_cache: bool) -> pd.DataFrame:
    from neutralrate import data
    if from_cache:
        return data.load_panel(offline=False)   # uses cached raw_panel.csv
    return data.load_panel(offline=True)


def _col_letters(start_index: int):
    """Yield successive column letters starting at 1-based index."""
    i = start_index
    while True:
        yield get_column_letter(i)
        i += 1


# --------------------------------------------------------------------------- #
def write_data_sheet(wb_path: str, features: pd.DataFrame):
    """Update only the Data sheet of an existing workbook (used by refresh)."""
    wb = load_workbook(wb_path)
    if "Data" in wb.sheetnames:
        del wb["Data"]
    ws = wb.create_sheet("Data", index=1)
    _populate_data_sheet(ws, features)
    wb.save(wb_path)


def _populate_data_sheet(ws, features: pd.DataFrame):
    df = features.copy()
    df = df[[c for c in DATA_COLS if c in df.columns]]
    df = df.dropna(how="all")
    n = len(df)

    # Header
    ws.cell(1, 1, "date")
    for j, col in enumerate(df.columns, start=2):
        ws.cell(1, j, col)
    # Data values
    for i, (idx, row) in enumerate(df.iterrows(), start=2):
        ws.cell(i, 1, pd.Timestamp(idx).strftime("%Y-%m-%d"))
        for j, col in enumerate(df.columns, start=2):
            v = row[col]
            ws.cell(i, j, None if pd.isna(v) else float(v))

    # --- column-letter map for feature columns ---
    L = {"date": "A"}
    for j, col in enumerate(df.columns, start=2):
        L[col] = get_column_letter(j)

    # --- computed (live-formula) columns appended after the features ---
    nextcol = 2 + len(df.columns)
    letters = _col_letters(nextcol)
    comp = {}   # name -> (letter, header)

    def add(name, header):
        ltr = next(letters)
        comp[name] = ltr
        ws.cell(1, ltr_to_idx(ltr), header)
        return ltr

    def ltr_to_idx(ltr):
        from openpyxl.utils import column_index_from_string
        return column_index_from_string(ltr)

    c_tp = add("tp", "term_premium")            # real_10y - real_short
    c_r10adj = add("r10adj", "real_10y_adj")     # real_10y - avg spread
    c_mid = add("mid", "curve_mid")              # 0.5*(rs + r10adj)
    c_tg = add("tg_gdp", "trend_growth_gdp")     # trailing MA of gdp_growth
    c_tc = add("tg_cons", "trend_growth_cons")   # trailing MA of cons_growth
    c_mar = add("ma_rsr", "MA_real_short")
    c_ma10 = add("ma_r10", "MA_real_10y_adj")
    c_mamid = add("ma_mid", "MA_curve_mid")
    # r* proxies
    c_hlw = add("HLW", "rstar_HLW")
    c_dsge = add("DSGE", "rstar_DSGE")
    c_ima = add("Imakubo", "rstar_Imakubo_NYC")
    c_nak = add("Nakajima", "rstar_Nakajima_NYC")
    c_goy = add("Goy", "rstar_GoyIwasaki")
    c_dn = add("DelNegro", "rstar_DelNegro_VAR")

    P = L["real_short_rate"]; Q = L["real_10y"]; K = L["gdp_growth"]; Lc = L["cons_growth"]

    for r in range(2, n + 2):
        ws[f"{c_tp}{r}"] = f"={Q}{r}-{P}{r}"
        ws[f"{c_r10adj}{r}"] = f"={Q}{r}-Settings!$B$5"   # B5 = avg term spread
        ws[f"{c_mid}{r}"] = f"=0.5*({P}{r}+{c_r10adj}{r})"
        # trailing moving averages over an explicit window (relative range so it
        # shifts correctly when new rows are filled down)
        ws[f"{c_tg}{r}"] = _ma(K, r)
        ws[f"{c_tc}{r}"] = _ma(Lc, r)
        ws[f"{c_mar}{r}"] = _ma(P, r)
        ws[f"{c_ma10}{r}"] = _ma(c_r10adj, r)
        ws[f"{c_mamid}{r}"] = _ma(c_mid, r)
        # six method proxies
        ws[f"{c_hlw}{r}"] = f"=0.5*{c_tg}{r}+0.5*{c_mar}{r}"
        ws[f"{c_dsge}{r}"] = f"=Settings!$B$3+Settings!$B$4*{c_tc}{r}"  # rho+gamma*g_c
        ws[f"{c_ima}{r}"] = f"={c_mamid}{r}"
        ws[f"{c_nak}{r}"] = f"=0.5*{c_tg}{r}+0.5*{c_mamid}{r}"
        ws[f"{c_goy}{r}"] = f"=({c_mar}{r}+{c_ma10}{r}+{c_tg}{r})/3"
        ws[f"{c_dn}{r}"] = f"=0.7*{c_mar}{r}+0.3*{c_tg}{r}"

    # styling
    for j in range(1, ltr_to_idx(c_dn) + 1):
        cell = ws.cell(1, j)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 12

    # Point the Settings "avg term spread" cell at the (dynamically located)
    # term_premium column, so it stays correct if the Data layout changes.
    if "Settings" in ws.parent.sheetnames:
        ws.parent["Settings"]["B5"] = f"=AVERAGE(Data!${c_tp}$2:${c_tp}${n + 1})"
    return comp, n


def _ma(src_letter: str, r: int, window: int = DEFAULT_WINDOW) -> str:
    """Trailing moving average of `src_letter` ending at row r over `window`
    quarters, as an explicit (relative) range so it survives fill-down and is
    portable across Excel / LibreOffice."""
    start = max(2, r - window + 1)
    return f"=AVERAGE({src_letter}{start}:{src_letter}{r})"


# --------------------------------------------------------------------------- #
def _build_settings(ws, features: pd.DataFrame):
    ws["A1"] = "Settings"; ws["A1"].font = TITLE_FONT
    rows = [
        ("window (quarters)", DEFAULT_WINDOW,
         "Trailing window baked into the trend columns (rebuild to change)"),
        ("rho (DSGE, %)", 0.0, "Rate of time preference / steady-state premium"),
        ("gamma (DSGE)", 1.0, "Inverse EIS (1 = log utility)"),
        ("avg real term spread", 0.0,   # set by _populate_data_sheet (dynamic col)
         "Average real 10y-short spread; used to level-adjust the long rate"),
    ]
    for i, (label, val, note) in enumerate(rows, start=1):
        ws.cell(i + 1, 1, label).font = Font(bold=True)
        ws.cell(i + 1, 2, val)
        ws.cell(i + 1, 3, note).font = NOTE_FONT
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 60
    ws["A7"] = ("B3/B4 recalibrate the DSGE Euler equation and recompute live. "
                "B2 (window) is baked into the trend ranges at build time - to "
                "change it, rerun build_workbook.py. New data rows recompute "
                "automatically once formulas are filled down.")
    ws["A7"].font = NOTE_FONT


def _build_readme(ws):
    ws["A1"] = "Japan Natural Rate of Interest (r*) - Six Methods"
    ws["A1"].font = TITLE_FONT
    lines = [
        "",
        "Replicates the six methods surveyed by the Bank of Japan",
        "(Nakano, Sugioka & Yamamoto 2024, BOJ WP 24-E-12; BOJ Review 2026-E-4).",
        "",
        "SHEETS",
        "  Settings  - window length and DSGE calibration (editable).",
        "  Data      - quarterly panel from FRED + derived features + the six",
        "              r* proxy columns (all live formulas).",
        "  Dashboard - chart comparing the six r* estimates.",
        "",
        "THE SIX METHODS (Excel proxy column on the Data sheet):",
        "  rstar_HLW            Holston-Laubach-Williams (2017/2023)",
        "  rstar_DSGE           Okazaki & Sudo (2018) - consumption Euler",
        "  rstar_Imakubo_NYC    Imakubo, Kojima & Nakajima (2015) natural yield curve",
        "  rstar_Nakajima_NYC   Nakajima et al. (2023) growth-anchored NYC",
        "  rstar_GoyIwasaki     Goy & Iwasaki (2024) macro-finance natural curve",
        "  rstar_DelNegro_VAR   Del Negro et al. (2017) VAR common trends",
        "",
        "IMPORTANT - fidelity:",
        "  The Excel columns are transparent REDUCED-FORM PROXIES that update",
        "  live with the data. The faithful state-space / MLE estimates are in",
        "  the Python package (run: python -m neutralrate.run_all). See",
        "  docs/01_research_report.md and docs/02_update_manual.md.",
        "",
        "TO UPDATE THE DATA:",
        "  Option A (automated): python python/scripts/refresh_data.py --excel",
        "  Option B (native):    Data > Refresh All after setting up Power Query",
        "                        (steps in docs/02_update_manual.md).",
    ]
    for i, t in enumerate(lines, start=2):
        ws.cell(i, 1, t)
    ws.column_dimensions["A"].width = 90


def _build_dashboard(ws, data_ws_name, comp, n, py_estimates: pd.DataFrame | None):
    ws["A1"] = "Dashboard - Japan r* by method"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Excel proxies (live). Python faithful estimates shown where "
                "available - re-run python -m neutralrate.run_all to refresh them.")
    ws["A2"].font = NOTE_FONT

    chart = LineChart()
    chart.title = "Japan natural rate of interest (r*)"
    chart.y_axis.title = "annualized %"
    chart.x_axis.title = "quarter"
    chart.height = 11; chart.width = 24

    from openpyxl.utils import column_index_from_string
    proxy_cols = ["HLW", "DSGE", "Imakubo", "Nakajima", "Goy", "DelNegro"]
    cats = Reference(ws.parent[data_ws_name], min_col=1, min_row=2, max_row=n + 1)
    for name in proxy_cols:
        ci = column_index_from_string(comp[name])
        ref = Reference(ws.parent[data_ws_name], min_col=ci, min_row=1, max_row=n + 1)
        chart.add_data(ref, titles_from_data=True)
    chart.set_categories(cats)
    ws.add_chart(chart, "A5")
    return ws


# --------------------------------------------------------------------------- #
def _build_python_sheet(wb, py: pd.DataFrame):
    """Drop in the faithful Python r* estimates (from run_all) + a chart."""
    ws = wb.create_sheet("Python_faithful")
    ws["A1"] = ("Faithful Python (state-space / MLE) estimates - from "
                "`python -m neutralrate.run_all`. Re-run to refresh.")
    ws["A1"].font = NOTE_FONT
    method_cols = [c for c in py.columns if not c.startswith("cross_method")]
    start = 3
    ws.cell(start, 1, "date")
    for j, c in enumerate(method_cols, start=2):
        ws.cell(start, j, c)
    for i, (idx, row) in enumerate(py.iterrows(), start=start + 1):
        ws.cell(i, 1, str(idx)[:10])
        for j, c in enumerate(method_cols, start=2):
            v = row[c]
            ws.cell(i, j, None if pd.isna(v) else float(v))
    nrows = len(py)
    chart = LineChart()
    chart.title = "Japan r* - faithful Python estimates"
    chart.y_axis.title = "annualized %"; chart.height = 10; chart.width = 22
    cats = Reference(ws, min_col=1, min_row=start + 1, max_row=start + nrows)
    for j in range(2, 2 + len(method_cols)):
        ref = Reference(ws, min_col=j, min_row=start, max_row=start + nrows)
        chart.add_data(ref, titles_from_data=True)
    chart.set_categories(cats)
    ws.add_chart(chart, f"A{start + nrows + 3}")
    for col in range(1, 2 + len(method_cols)):
        ws.cell(start, col).fill = HEADER_FILL
        ws.cell(start, col).font = HEADER_FONT


def build(from_cache: bool = False):
    features = _load_features(from_cache)
    wb = Workbook()
    _build_readme(wb.active)
    wb.active.title = "ReadMe"
    data_ws = wb.create_sheet("Data")
    settings_ws = wb.create_sheet("Settings")
    _build_settings(settings_ws, features)
    comp, n = _populate_data_sheet(data_ws, features)

    py_csv = os.path.join(HERE, "..", "python", "output", "r_star_estimates.csv")
    py = pd.read_csv(py_csv, index_col=0) if os.path.exists(py_csv) else None
    dash = wb.create_sheet("Dashboard")
    _build_dashboard(dash, "Data", comp, n, py)
    if py is not None:
        _build_python_sheet(wb, py)

    wb.save(WB_PATH)
    print(f"Workbook written: {os.path.abspath(WB_PATH)}  ({n} quarters)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-cache", action="store_true",
                    help="build from refreshed FRED cache instead of sample")
    args = ap.parse_args()
    build(from_cache=args.from_cache)


if __name__ == "__main__":
    main()
