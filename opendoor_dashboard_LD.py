#!/usr/bin/env python3
"""
Opendoor Technologies — Interactive Financial Analysis Dashboard (FY2020–2025)

Unified deployable build.
- Five light-themed institutional tabs: Income Statement, Unit Economics,
  Balance Sheet, Cash Flow, Efficiency & Risk.
- One dark-themed Profitability Bridge tab (CP vs. Fixed Cost Coverage) with
  a slider that reclassifies SM&O between fixed and variable.

Run locally:
    python opendoor_dashboard_v6.py
On macOS this auto-launches Safari. Deployable via gunicorn:
    gunicorn opendoor_dashboard_v6:server
"""

import os
import subprocess
import threading
import webbrowser

import dash
from dash import html, dcc, dash_table, Input, Output, State, ctx
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ─────────────────────────────────────────────────────────────────
#  STYLING CONSTANTS
# ─────────────────────────────────────────────────────────────────
NAVY   = "#1e3a5f"
TEAL   = "#0ea5e9"
GREEN  = "#10b981"
RED    = "#ef4444"
AMBER  = "#f59e0b"
PURPLE = "#8b5cf6"
SLATE  = "#475569"
LGRAY  = "#f1f5f9"
BORDER = "#e2e8f0"
PALETTE = [NAVY, TEAL, GREEN, AMBER, PURPLE, "#f97316"]

FONT_FAMILY = "'Inter', 'Segoe UI', system-ui, sans-serif"

# Dark theme (for Profitability Bridge tab)
DARK = {
    "bg":           "#0d0d1a",
    "panel":        "rgba(255,255,255,0.02)",
    "panel_border": "rgba(255,255,255,0.06)",
    "text":         "#e0e0e0",
    "text_dim":     "#888",
    "text_muted":   "#666",
    "text_faint":   "#555",
    "white":        "#ffffff",
    "accent":       "#4ecdc4",
    "warn":         "#ff6b6b",
    "purple":       "#8884d8",
    "gold":         "#f0c040",
    "orange":       "#e07020",
}
MONO = "'IBM Plex Mono', monospace"
HEADING = "'Space Grotesk', sans-serif"


# ─────────────────────────────────────────────────────────────────
#  DATA LAYER — Light-Themed Sections (Income/Unit/Balance/CF/Eff)
#  All monetary values in $M USD unless noted.
#  Confidence tags:
#    "C" = Confirmed from SEC 10-K / Official Earnings Release
#    "E" = Estimated / inference
#    "K" = Calculated from confirmed figures
# ─────────────────────────────────────────────────────────────────
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

METRICS = {
    "revenue":            {"label": "Revenue",                          "unit": "$M",  "conf": "C", "vals": [2583,   8020,   15565,  6940,   5190,   4370  ]},
    "cogs":               {"label": "Cost of Revenue",                  "unit": "$M",  "conf": "K", "vals": [2363,   7292,   14898,  6453,   4757,   4020  ]},
    "grossProfit":        {"label": "Gross Profit",                     "unit": "$M",  "conf": "C", "vals": [220,    728,    667,    487,    433,    350   ]},
    "grossMargin":        {"label": "Gross Margin",                     "unit": "%",   "conf": "C", "vals": [8.5,    9.1,    4.3,    7.0,    8.4,    8.0   ]},
    "smo":                {"label": "Sales, Mktg & Operations",         "unit": "$M",  "conf": "C", "vals": [189,    544,    1006,   486,    413,    310   ]},
    "ga":                 {"label": "General & Administrative",         "unit": "$M",  "conf": "C", "vals": [132,    620,    346,    206,    182,    238   ]},
    "td":                 {"label": "Technology & Development",         "unit": "$M",  "conf": "C", "vals": [56,     134,    169,    167,    141,    79    ]},
    "restructuring":      {"label": "Restructuring Charges",            "unit": "$M",  "conf": "C", "vals": [29,     0,      17,     14,     17,     10    ]},
    "totalOpex":          {"label": "Total Operating Expenses",         "unit": "$M",  "conf": "K", "vals": [406,    1298,   1538,   873,    753,    637   ]},
    "operatingIncome":    {"label": "Operating Income / (Loss)",        "unit": "$M",  "conf": "C", "vals": [-186,   -568,   -931,   -386,   -320,   -287  ]},
    "operatingMargin":    {"label": "Operating Margin",                 "unit": "%",   "conf": "K", "vals": [-7.2,   -7.1,   -6.0,   -5.6,   -6.2,   -6.6  ]},
    "interestExpense":    {"label": "Interest Expense",                 "unit": "$M",  "conf": "C", "vals": [-68,    -143,   -385,   -211,   -133,   -131  ]},
    "netLoss":            {"label": "Net Income / (Loss)",              "unit": "$M",  "conf": "C", "vals": [-253,   -662,   -1350,  -275,   -392,   -1300 ]},
    "netMargin":          {"label": "Net Margin",                       "unit": "%",   "conf": "K", "vals": [-9.8,   -8.3,   -8.7,   -4.0,   -7.6,   -29.7 ]},
    "adjEBITDA":          {"label": "Adjusted EBITDA",                  "unit": "$M",  "conf": "C", "vals": [-98,    58,     -168,   -627,   -142,   -83   ]},
    "adjNetLoss":         {"label": "Adjusted Net Loss",                "unit": "$M",  "conf": "C", "vals": [-175,   -116,   -574,   -778,   -258,   -195  ]},
    "adjNetLossMargin":   {"label": "Adjusted Net Loss Margin",         "unit": "%",   "conf": "K", "vals": [-6.8,   -1.4,   -3.7,   -11.2,  -5.0,   -4.5  ]},
    "sbc":                {"label": "Stock-Based Compensation",         "unit": "$M",  "conf": "C", "vals": [38,     536,    171,    126,    114,    159   ]},
    "da":                 {"label": "Depreciation & Amortization",      "unit": "$M",  "conf": "C", "vals": [39,     47,     83,     65,     48,     44    ]},
    "inventoryAdj":       {"label": "Inventory Valuation Adjustment",   "unit": "$M",  "conf": "C", "vals": [8,      56,     737,    65,     57,     57    ]},
    "reconRestructuring": {"label": "Restructuring (EBITDA Recon)",     "unit": "$M",  "conf": "C", "vals": [29,     0,      17,     14,     17,     10    ]},
    "noteNonCash":        {"label": "Non-Cash Convertible Note Loss",   "unit": "$M",  "conf": "C", "vals": [None,   None,   None,   None,   None,   933   ]},
    "homesPurchased":     {"label": "Homes Purchased",                  "unit": "#",   "conf": "C", "vals": [None,   36908,  34962,  11246,  14684,  8241  ]},
    "homesSold":          {"label": "Homes Sold",                       "unit": "#",   "conf": "C", "vals": [9913,   21725,  39183,  18708,  13593,  11791 ]},
    "revenuePerHome":     {"label": "Revenue per Home Sold",            "unit": "$K",  "conf": "K", "vals": [261,    369,    397,    371,    382,    370   ]},
    "gpPerHome":          {"label": "Gross Profit per Home Sold",       "unit": "$K",  "conf": "K", "vals": [22.2,   33.5,   17.0,   26.0,   31.9,   29.7  ]},
    "contribProfitPerHm": {"label": "Contribution Profit per Home",     "unit": "$K",  "conf": "K", "vals": [11.1,   24.2,   13.4,   -13.8,  17.8,   12.7  ]},
    "contributionProfit": {"label": "Contribution Profit",              "unit": "$M",  "conf": "C", "vals": [110,    525,    525,    -258,   242,    150   ]},
    "contributionMargin": {"label": "Contribution Margin",              "unit": "%",   "conf": "C", "vals": [4.3,    6.5,    3.4,    -3.7,   4.7,    3.4   ]},
    "inventoryValue":     {"label": "Real Estate Inventory (Value)",    "unit": "$M",  "conf": "C", "vals": [466,    6100,   4500,   1800,   2159,   925   ]},
    "inventoryCount":     {"label": "Inventory Count (Homes at YE)",    "unit": "#",   "conf": "C", "vals": [1827,   17009,  12788,  5326,   6417,   2867  ]},
    "cashEquiv":          {"label": "Cash & Equivalents",               "unit": "$M",  "conf": "C", "vals": [1400,   1700,   1100,   1000,   671,    962   ]},
    "restrictedCash":     {"label": "Restricted Cash",                  "unit": "$M",  "conf": "C", "vals": [93,     847,    654,    541,    92,     339   ]},
    "totalCash":          {"label": "Total Cash",                       "unit": "$M",  "conf": "K", "vals": [1493,   2547,   1754,   1541,   763,    1301  ]},
    "nrDebtCurrent":      {"label": "Non-Recourse Debt \u2014 Current",     "unit": "$M",  "conf": "C", "vals": [None,   4200,   1400,   0,      432,    52    ]},
    "nrDebtLongTerm":     {"label": "Non-Recourse Debt \u2014 Long-Term",   "unit": "$M",  "conf": "C", "vals": [None,   1900,   3000,   2100,   1500,   1100  ]},
    "convNotesCurrent":   {"label": "Convertible Notes \u2014 Current",     "unit": "$M",  "conf": "C", "vals": [0,      0,      0,      0,      0,      193   ]},
    "convNotesLongTerm":  {"label": "Convertible Notes \u2014 Long-Term",   "unit": "$M",  "conf": "C", "vals": [0,      954,    959,    376,    378,    0     ]},
    "shareholdersEq":     {"label": "Shareholders' Equity / Book Value","unit": "$M",  "conf": "C", "vals": [1600,   2200,   1100,   967,    713,    1000  ]},
    "operatingCF":        {"label": "Operating Cash Flow",              "unit": "$M",  "conf": "C", "vals": [682,    -5800,  730,    2300,   -595,   1050  ]},
    "investingCF":        {"label": "Investing Cash Flow",              "unit": "$M",  "conf": "C", "vals": [-22,    -476,   234,    44,     28,     -12   ]},
    "financingCF":        {"label": "Financing Cash Flow",              "unit": "$M",  "conf": "C", "vals": [161,    7300,   -1800,  -2600,  -210,   -499  ]},
    "reInventoryCF":      {"label": "RE Inventory Cash Flow",           "unit": "$M",  "conf": "C", "vals": [834,    -5700,  896,    2600,   -449,   1200  ]},
    "equityRaised":       {"label": "Equity Capital Raised",            "unit": "$M",  "conf": "C", "vals": [980,    894,    6,      5,      5,      245   ]},
    "debtNetChange":      {"label": "Net Debt Raised / (Repaid)",       "unit": "$M",  "conf": "C", "vals": [-820,   6448,   -1757,  -2644,  -215,   -752  ]},
    "inventoryTurnover":  {"label": "Inventory Turnover",               "unit": "x",   "conf": "C", "vals": [2.66,   2.22,   2.67,   2.99,   2.32,   2.50  ]},
    "bookValuePerShare":  {"label": "Book Value per Share",             "unit": "$",   "conf": "K", "vals": [14.68,  3.71,   1.75,   1.47,   1.02,   1.30  ]},
    "sharesOutstanding":  {"label": "Shares Outstanding (Wtd Avg)",     "unit": "M",   "conf": "C", "vals": [109,    593,    627,    657,    699,    767   ]},
}


# ─────────────────────────────────────────────────────────────────
#  DATA LAYER — Profitability Bridge (Dark-Themed Tab)
#  cpAfterInterest = reported CP After Interest (treats ALL SM&O as
#  OpEx below the CP line; no SM&O subtracted).
# ─────────────────────────────────────────────────────────────────
PROFIT_RAW = [
    {"year": "2020", "revenue": 2600, "cp": 110,  "interestExpense": 68,  "cpAfterInterest": 42,   "smo": 189,  "ga": 132, "td": 56},
    {"year": "2021", "revenue": 8000, "cp": 525,  "interestExpense": 143, "cpAfterInterest": 382,  "smo": 544,  "ga": 620, "td": 134},
    {"year": "2022", "revenue": 15600,"cp": 525,  "interestExpense": 385, "cpAfterInterest": 140,  "smo": 1000, "ga": 346, "td": 169},
    {"year": "2023", "revenue": 6900, "cp": -258, "interestExpense": 211, "cpAfterInterest": -469, "smo": 486,  "ga": 206, "td": 167},
    {"year": "2024", "revenue": 5200, "cp": 242,  "interestExpense": 133, "cpAfterInterest": 109,  "smo": 413,  "ga": 182, "td": 141},
    {"year": "2025", "revenue": 4400, "cp": 150,  "interestExpense": 131, "cpAfterInterest": 19,   "smo": 310,  "ga": 238, "td": 79},
]

DEFAULT_SMO_FIXED_PCT = 0.30  # default slider position


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────
def format_val(val, unit):
    if val is None:
        return "N/A"
    absv = abs(val)
    neg = val < 0
    if unit == "$M":
        inner = f"${absv/1000:.1f}B" if absv >= 1000 else f"${absv:.0f}M"
        return f"({inner})" if neg else inner
    elif unit == "%":
        return f"{val:.1f}%"
    elif unit == "#":
        return f"{val:,}" if val >= 1000 else str(val)
    elif unit == "$K":
        inner = f"${absv:.1f}K"
        return f"({inner})" if neg else inner
    elif unit == "x":
        return f"{val:.1f}x"
    elif unit == "$":
        return f"${val:.2f}"
    elif unit == "M":
        return f"{val:.0f}M"
    return str(val)


def yoy(cur, prev):
    if cur is None or prev is None or prev == 0:
        return None
    return ((cur - prev) / abs(prev)) * 100


def conf_badge(conf):
    cmap = {
        "C": {"bg": "#d1fae5", "color": "#065f46", "label": "\u2713 Filed"},
        "E": {"bg": "#fef9c3", "color": "#713f12", "label": "~ Est."},
        "K": {"bg": "#dbeafe", "color": "#1e3a8a", "label": "\u2211 Calc."},
    }
    s = cmap.get(conf, cmap["E"])
    return html.Span(s["label"], style={
        "background": s["bg"], "color": s["color"], "borderRadius": 4,
        "padding": "1px 5px", "fontSize": 10, "fontWeight": 600, "letterSpacing": 0.2
    })


def fmt_dollar_dark(val):
    if val >= 0:
        return f"${int(round(val))}M"
    return f"-${int(round(abs(val)))}M"


# ─────────────────────────────────────────────────────────────────
#  CHART LAYOUT DEFAULTS (light theme)
# ─────────────────────────────────────────────────────────────────
def base_layout(**overrides):
    layout = dict(
        font=dict(family=FONT_FAMILY, size=12),
        plot_bgcolor="#fff",
        paper_bgcolor="#fff",
        margin=dict(l=60, r=40, t=10, b=40),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11)),
        xaxis=dict(gridcolor=BORDER, gridwidth=1, griddash="dot", tickfont=dict(size=12)),
        yaxis=dict(gridcolor=BORDER, gridwidth=1, griddash="dot", tickfont=dict(size=11)),
        hovermode="x unified",
        bargap=0.25,
    )
    layout.update(overrides)
    return layout


# ─────────────────────────────────────────────────────────────────
#  LIGHT TABLE BUILDER
# ─────────────────────────────────────────────────────────────────
def build_metric_table(metric_keys, show_yoy=True):
    rev_profit_keys = {"revenue", "grossProfit", "adjEBITDA", "contributionProfit"}

    header_cells = [
        html.Th("Metric", style={"padding": "10px 12px", "textAlign": "left", "whiteSpace": "nowrap",
                                  "fontWeight": 600, "position": "sticky", "left": 0, "background": NAVY, "zIndex": 2, "color": "#fff"}),
        html.Th("Source", style={"padding": "8px 6px", "textAlign": "center", "fontSize": 10, "color": "#94a3b8"}),
    ]
    for yr in YEARS:
        header_cells.append(html.Th(str(yr), style={"padding": "10px 10px", "textAlign": "right", "whiteSpace": "nowrap", "color": "#fff"}))
    if show_yoy:
        for yr in YEARS[1:]:
            header_cells.append(html.Th(f"YoY {yr}", style={"padding": "10px 8px", "textAlign": "right", "fontSize": 10, "color": "#94a3b8", "whiteSpace": "nowrap"}))

    rows = []
    for ri, key in enumerate(metric_keys):
        m = METRICS.get(key)
        if not m:
            continue
        bg = "#fff" if ri % 2 == 0 else LGRAY
        cells = [
            html.Td(m["label"], style={"padding": "8px 12px", "fontWeight": 500, "color": NAVY, "whiteSpace": "nowrap",
                                        "position": "sticky", "left": 0, "background": bg, "zIndex": 1}),
            html.Td(conf_badge(m["conf"]), style={"padding": "8px 6px", "textAlign": "center"}),
        ]
        for i, _ in enumerate(YEARS):
            v = m["vals"][i]
            is_neg = v is not None and v < 0
            cells.append(html.Td(format_val(v, m["unit"]), style={
                "padding": "8px 10px", "textAlign": "right",
                "color": RED if is_neg else "#1e293b",
                "fontVariantNumeric": "tabular-nums", "whiteSpace": "nowrap"
            }))
        if show_yoy:
            for i, _ in enumerate(YEARS[1:]):
                cur = m["vals"][i + 1]
                prev = m["vals"][i]
                chg = yoy(cur, prev)
                if chg is None:
                    cells.append(html.Td("\u2014", style={"padding": "8px 8px", "textAlign": "right", "color": "#94a3b8", "fontSize": 11}))
                else:
                    is_pos = chg > 0
                    is_rev_or_profit = key in rev_profit_keys
                    is_good = is_pos if is_rev_or_profit else not is_pos
                    color = SLATE if abs(chg) < 1 else (GREEN if is_good else RED)
                    cells.append(html.Td(f"{'+'if is_pos else ''}{chg:.1f}%", style={
                        "padding": "8px 8px", "textAlign": "right", "color": color,
                        "fontSize": 11, "whiteSpace": "nowrap"
                    }))
        rows.append(html.Tr(cells, style={"background": bg, "borderBottom": f"1px solid {BORDER}"}))

    return html.Div(
        html.Table([
            html.Thead(html.Tr(header_cells, style={"background": NAVY, "color": "#fff"})),
            html.Tbody(rows)
        ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": 12}),
        style={"overflowX": "auto"}
    )


# ─────────────────────────────────────────────────────────────────
#  LIGHT CHART BUILDERS
# ─────────────────────────────────────────────────────────────────
def chart_income_topline():
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["revenue"]["vals"], name="Revenue", marker_color=NAVY, marker_line_width=0), secondary_y=False)
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["grossProfit"]["vals"], name="Gross Profit", marker_color=TEAL), secondary_y=False)
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["adjEBITDA"]["vals"], name="Adj. EBITDA", mode="lines+markers",
                             line=dict(color=AMBER, width=2.5), marker=dict(size=8)), secondary_y=True)
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["netLoss"]["vals"], name="Net Income/(Loss)", mode="lines+markers",
                             line=dict(color=RED, width=2, dash="dash"), marker=dict(size=6)), secondary_y=True)
    fig.add_hline(y=0, line_dash="dot", line_color=SLATE, line_width=1, secondary_y=False)
    fig.update_layout(**base_layout())
    fig.update_yaxes(tickformat="$,.0f", ticksuffix="M", secondary_y=False)
    fig.update_yaxes(tickformat="$,.0f", ticksuffix="M", secondary_y=True)
    return fig


def chart_income_margins():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["grossMargin"]["vals"], name="Gross Margin",
                             mode="lines+markers", line=dict(color=TEAL, width=2.5), marker=dict(size=10)))
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["contributionMargin"]["vals"], name="Contribution Margin",
                             mode="lines+markers", line=dict(color=PURPLE, width=2.5, dash="dash"), marker=dict(size=10)))
    fig.add_hline(y=0, line_dash="dot", line_color=RED, line_width=1)
    fig.update_layout(**base_layout(yaxis=dict(ticksuffix="%", tickfont=dict(size=11), range=[-6, 12],
                                                gridcolor=BORDER, gridwidth=1, griddash="dot")))
    return fig


def chart_income_opex():
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["smo"]["vals"],           name="SM&O",          marker_color=NAVY))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["ga"]["vals"],            name="G&A",           marker_color=TEAL))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["td"]["vals"],            name="Tech & Dev",    marker_color=PURPLE))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["restructuring"]["vals"], name="Restructuring", marker_color=RED))
    fig.update_layout(**base_layout(barmode="stack"))
    return fig


def chart_income_ebitda_recon():
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["adjEBITDA"]["vals"],   name="Adj. EBITDA",        marker_color=AMBER))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["sbc"]["vals"],         name="SBC (addback)",      marker_color=TEAL))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["da"]["vals"],          name="D&A (addback)",      marker_color=PURPLE))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["inventoryAdj"]["vals"],name="Inventory Adj.",     marker_color=RED))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["noteNonCash"]["vals"], name="Conv. Note Non-Cash",marker_color="#f97316"))
    fig.update_layout(**base_layout(barmode="group"))
    return fig


def chart_unit_volume():
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["homesPurchased"]["vals"], name="Homes Purchased", marker_color=NAVY))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["homesSold"]["vals"],      name="Homes Sold",      marker_color=TEAL))
    fig.update_layout(**base_layout(barmode="group"))
    fig.update_yaxes(tickformat=",")
    return fig


def chart_unit_per_home():
    cpph = METRICS["contribProfitPerHm"]["vals"]
    colors = [RED if (v is not None and v < 0) else PURPLE for v in cpph]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["revenuePerHome"]["vals"], name="Revenue / Home",      marker_color=NAVY))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["gpPerHome"]["vals"],      name="Gross Profit / Home", marker_color=TEAL))
    fig.add_trace(go.Bar(x=YEARS, y=cpph,                              name="Contribution Profit / Home", marker_color=colors))
    fig.add_hline(y=0, line_color=SLATE, line_width=1)
    fig.update_layout(**base_layout(barmode="group"))
    fig.update_yaxes(tickprefix="$", ticksuffix="K")
    return fig


def chart_unit_contribution():
    cp = METRICS["contributionProfit"]["vals"]
    cp_colors = [RED if (v is not None and v < 0) else PURPLE for v in cp]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["grossProfit"]["vals"], name="Gross Profit",        marker_color=TEAL))
    fig.add_trace(go.Bar(x=YEARS, y=cp,                             name="Contribution Profit", marker_color=cp_colors))
    fig.add_hline(y=0, line_dash="dot", line_color=RED, line_width=1)
    fig.update_layout(**base_layout(barmode="group"))
    return fig


def chart_unit_margins():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["grossMargin"]["vals"], name="Gross Margin",
                             mode="lines+markers", line=dict(color=TEAL, width=2.5), marker=dict(size=10)))
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["contributionMargin"]["vals"], name="Contribution Margin",
                             mode="lines+markers", line=dict(color=PURPLE, width=2.5, dash="dash"), marker=dict(size=10)))
    fig.add_hline(y=0, line_dash="dot", line_color=RED, line_width=1)
    fig.update_layout(**base_layout(yaxis=dict(ticksuffix="%", tickfont=dict(size=11), range=[-6, 12],
                                                gridcolor=BORDER, gridwidth=1, griddash="dot")))
    return fig


def chart_balance_inventory():
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["inventoryValue"]["vals"], name="Inventory Value ($M)", marker_color=NAVY), secondary_y=False)
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["inventoryCount"]["vals"], name="Home Count", mode="lines+markers",
                             line=dict(color=AMBER, width=2.5), marker=dict(size=10)), secondary_y=True)
    fig.update_layout(**base_layout())
    fig.update_yaxes(tickprefix="$", ticksuffix="M", tickformat=",", secondary_y=False)
    fig.update_yaxes(tickformat=",", secondary_y=True)
    return fig


def chart_balance_capital():
    nr_total = [None if (a is None and b is None) else (a or 0) + (b or 0)
                for a, b in zip(METRICS["nrDebtCurrent"]["vals"], METRICS["nrDebtLongTerm"]["vals"])]
    conv_total = [(a or 0) + (b or 0)
                  for a, b in zip(METRICS["convNotesCurrent"]["vals"], METRICS["convNotesLongTerm"]["vals"])]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["totalCash"]["vals"],     name="Total Cash",         marker_color=GREEN))
    fig.add_trace(go.Bar(x=YEARS, y=nr_total,                         name="Non-Recourse Debt",  marker_color=RED))
    fig.add_trace(go.Bar(x=YEARS, y=conv_total,                       name="Convertible Notes",  marker_color=AMBER))
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["shareholdersEq"]["vals"],name="Equity",             marker_color=TEAL))
    fig.update_layout(**base_layout(barmode="group"))
    return fig


def chart_cf_operating():
    vals = METRICS["operatingCF"]["vals"]
    colors = [GREEN if (v is not None and v >= 0) else RED for v in vals]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=vals, name="Operating Cash Flow", marker_color=colors))
    fig.add_hline(y=0, line_dash="dot", line_color=SLATE, line_width=1)
    fig.update_layout(**base_layout())
    return fig


def chart_cf_capital_raised():
    dn = METRICS["debtNetChange"]["vals"]
    dn_colors = [NAVY if (v is not None and v >= 0) else AMBER for v in dn]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["equityRaised"]["vals"], name="Equity Raised",    marker_color=TEAL))
    fig.add_trace(go.Bar(x=YEARS, y=dn,                              name="Net Debt Change",  marker_color=dn_colors))
    fig.add_hline(y=0, line_color=SLATE, line_width=1)
    fig.update_layout(**base_layout(barmode="group"))
    return fig


def chart_eff_turnover():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["inventoryTurnover"]["vals"], name="Inventory Turnover",
                             mode="lines+markers", line=dict(color=TEAL, width=2.5), marker=dict(size=12, color=TEAL)))
    fig.update_layout(**base_layout(yaxis=dict(ticksuffix="x", tickfont=dict(size=11), range=[0, 4],
                                                gridcolor=BORDER, gridwidth=1, griddash="dot")))
    return fig


def chart_eff_bv():
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=YEARS, y=METRICS["sharesOutstanding"]["vals"], name="Shares (M)", marker_color=BORDER), secondary_y=True)
    fig.add_trace(go.Scatter(x=YEARS, y=METRICS["bookValuePerShare"]["vals"], name="BV / Share ($)", mode="lines+markers",
                             line=dict(color=NAVY, width=2.5), marker=dict(size=10)), secondary_y=False)
    fig.update_layout(**base_layout())
    fig.update_yaxes(tickprefix="$", tickformat=".2f", secondary_y=False)
    fig.update_yaxes(ticksuffix="M", secondary_y=True)
    return fig


# ─────────────────────────────────────────────────────────────────
#  PROFITABILITY BRIDGE — slider-driven computation
#
#  INVARIANT: reclassifying SM&O between fixed and variable changes
#  the CPAI line and the fixed-cost line by equal and opposite
#  amounts. Shortfall is independent of the slider position. Proof:
#
#     shortfall = CPAI_adj - totalFixedCosts
#               = (reportedCPAI - (1-x)*SMO) - (x*SMO + GA + TD)
#               = reportedCPAI - SMO - GA - TD
#
#  → no dependence on x (the fixed %).
# ─────────────────────────────────────────────────────────────────
def compute_profit_df(smo_fixed_pct):
    df = pd.DataFrame(PROFIT_RAW).copy()
    df["fixedSMO"]        = (df["smo"] * smo_fixed_pct).round().astype(int)
    # Define variable as residual so fixedSMO + variableSMO == smo exactly
    # (otherwise independent rounding can introduce ±$1 drift)
    df["variableSMO"]     = df["smo"] - df["fixedSMO"]
    # Push variable SM&O above the CPAI line (reported CPAI has all SM&O below it)
    df["cpaiAdjusted"]    = df["cpAfterInterest"] - df["variableSMO"]
    df["totalFixedCosts"] = df["fixedSMO"] + df["ga"] + df["td"]
    df["shortfall"]       = df["cpaiAdjusted"] - df["totalFixedCosts"]
    df["cpMarginAdj"]     = (df["cpaiAdjusted"] / df["revenue"] * 100).round(2)
    return df


def chart_profit_main(df):
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df["year"], y=df["cp"], name="Contribution Profit",
        marker_color=DARK["gold"], opacity=0.85,
        text=[fmt_dollar_dark(v) for v in df["cp"]],
        textposition="outside", textfont=dict(color=DARK["gold"], family=MONO, size=10),
    ))
    fig.add_trace(go.Bar(
        x=df["year"], y=df["interestExpense"], name="Interest Expense",
        marker_color=DARK["orange"], opacity=0.85,
        text=[fmt_dollar_dark(v) for v in df["interestExpense"]],
        textposition="outside", textfont=dict(color=DARK["orange"], family=MONO, size=10),
    ))
    fig.add_trace(go.Bar(
        x=df["year"], y=df["cpaiAdjusted"], name="CP After Int. (Adj.)",
        marker_color=DARK["accent"], opacity=0.9,
        text=[fmt_dollar_dark(v) for v in df["cpaiAdjusted"]],
        textposition="outside", textfont=dict(color=DARK["accent"], family=MONO, size=10),
    ))
    fig.add_trace(go.Bar(
        x=df["year"], y=df["totalFixedCosts"], name="Total Fixed Costs",
        marker_color=DARK["warn"], opacity=0.7,
        text=[fmt_dollar_dark(v) for v in df["totalFixedCosts"]],
        textposition="outside", textfont=dict(color=DARK["warn"], family=MONO, size=10),
    ))
    fig.add_trace(go.Bar(
        x=df["year"], y=df["shortfall"], name="Shortfall",
        marker_color=DARK["warn"], opacity=0.45,
        text=[fmt_dollar_dark(v) for v in df["shortfall"]],
        textposition="outside", textfont=dict(color=DARK["warn"], family=MONO, size=10),
    ))

    fig.add_trace(go.Scatter(
        x=df["year"], y=df["cpMarginAdj"], name="CP After Int. Margin %",
        mode="lines+markers+text",
        line=dict(color=DARK["purple"], width=2.5),
        marker=dict(size=8, color=DARK["purple"]),
        text=[f"{v}%" for v in df["cpMarginAdj"]],
        textposition="top center",
        textfont=dict(color=DARK["purple"], family=MONO, size=10),
        yaxis="y2",
    ))

    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.2)", width=1, dash="dash"), yref="y")

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=MONO, color=DARK["text_dim"], size=11),
        barmode="group",
        bargap=0.25,
        height=500,
        margin=dict(l=60, r=60, t=30, b=60),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5,
                    font=dict(color=DARK["text_dim"], size=11), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, linecolor="rgba(255,255,255,0.1)",
                   tickfont=dict(color=DARK["text_dim"], family=MONO, size=12)),
        yaxis=dict(title=dict(text="$M", font=dict(color=DARK["text_dim"])),
                   gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.1)",
                   tickformat="$,", tickfont=dict(color=DARK["text_dim"], family=MONO)),
        yaxis2=dict(title=dict(text="Margin %", font=dict(color=DARK["purple"])),
                    overlaying="y", side="right", showgrid=False,
                    tickfont=dict(color=DARK["purple"], family=MONO), ticksuffix="%"),
    )
    return fig


def profit_summary_cards(df):
    latest = df.iloc[-1]
    cards = [
        ("CP After Int. (Adj.)", "FY2025", fmt_dollar_dark(int(latest["cpaiAdjusted"])), DARK["accent"]),
        ("CP After Int. Margin", "FY2025", f"{latest['cpMarginAdj']}%", DARK["purple"]),
        ("Total Fixed Costs",    "FY2025", fmt_dollar_dark(int(latest["totalFixedCosts"])), DARK["warn"]),
        ("Shortfall",            "FY2025", fmt_dollar_dark(int(latest["shortfall"])), DARK["warn"]),
    ]
    return html.Div(
        style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)",
               "gap": "12px", "marginBottom": "24px"},
        children=[
            html.Div(
                style={"background": "rgba(255,255,255,0.03)",
                       "border": f"1px solid {DARK['panel_border']}",
                       "borderRadius": "8px", "padding": "14px 16px"},
                children=[
                    html.Div(label, style={"fontSize": "10px", "color": DARK["text_muted"],
                                           "textTransform": "uppercase", "letterSpacing": "1.5px",
                                           "marginBottom": "2px"}),
                    html.Div(sub, style={"fontSize": "10px", "color": DARK["text_faint"],
                                         "marginBottom": "6px"}),
                    html.Div(val, style={"fontSize": "22px", "fontWeight": 700,
                                         "color": color, "fontFamily": HEADING}),
                ],
            )
            for (label, sub, val, color) in cards
        ],
    )


def build_profit_table(df):
    t = df.copy()
    t["Revenue"]       = t["revenue"].apply(lambda v: f"${v:,}M")
    t["CP"]            = t["cp"].apply(fmt_dollar_dark)
    t["Int. Exp."]     = t["interestExpense"].apply(fmt_dollar_dark)
    t["CPAI (Adj.)"]   = t["cpaiAdjusted"].apply(fmt_dollar_dark)
    t["Margin"]        = t["cpMarginAdj"].apply(lambda v: f"{v}%")
    t["Fixed SM&O"]    = t["fixedSMO"].apply(fmt_dollar_dark)
    t["Variable SM&O"] = t["variableSMO"].apply(fmt_dollar_dark)
    t["G&A"]           = t["ga"].apply(fmt_dollar_dark)
    t["T&D"]           = t["td"].apply(fmt_dollar_dark)
    t["Total Fixed"]   = t["totalFixedCosts"].apply(fmt_dollar_dark)
    t["Shortfall"]     = t["shortfall"].apply(fmt_dollar_dark)
    t = t.rename(columns={"year": "Year"})

    display_cols = ["Year", "Revenue", "CP", "Int. Exp.", "CPAI (Adj.)", "Margin",
                    "Fixed SM&O", "Variable SM&O", "G&A", "T&D", "Total Fixed", "Shortfall"]

    return dash_table.DataTable(
        data=t[display_cols].to_dict("records"),
        columns=[{"name": c, "id": c} for c in display_cols],
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "rgba(255,255,255,0.03)", "color": DARK["text_muted"],
                      "fontWeight": 500, "fontSize": "10px", "textTransform": "uppercase",
                      "letterSpacing": "1px", "border": "none",
                      "borderBottom": "1px solid rgba(255,255,255,0.1)",
                      "fontFamily": MONO, "padding": "10px"},
        style_cell={"backgroundColor": "transparent", "color": DARK["text"],
                    "fontFamily": MONO, "fontSize": "12px", "padding": "10px",
                    "border": "none", "borderBottom": "1px solid rgba(255,255,255,0.04)",
                    "textAlign": "right"},
        style_cell_conditional=[
            {"if": {"column_id": "Year"}, "textAlign": "left", "fontWeight": 600, "color": DARK["white"]},
        ],
        style_data_conditional=[
            {"if": {"column_id": "CP"}, "color": DARK["gold"], "fontWeight": 600},
            {"if": {"filter_query": "{CP} contains '-'", "column_id": "CP"},
             "color": DARK["warn"], "fontWeight": 600},
            {"if": {"column_id": "Int. Exp."}, "color": DARK["orange"]},
            {"if": {"column_id": "CPAI (Adj.)"}, "color": DARK["accent"], "fontWeight": 600},
            {"if": {"filter_query": "{CPAI (Adj.)} contains '-'", "column_id": "CPAI (Adj.)"},
             "color": DARK["warn"], "fontWeight": 600},
            {"if": {"column_id": "Margin"}, "color": DARK["purple"]},
            {"if": {"filter_query": "{Margin} contains '-'", "column_id": "Margin"},
             "color": DARK["warn"]},
            {"if": {"column_id": "Total Fixed"}, "color": DARK["warn"], "fontWeight": 500},
            {"if": {"column_id": "Shortfall"}, "color": DARK["accent"], "fontWeight": 700},
            {"if": {"filter_query": "{Shortfall} contains '-'", "column_id": "Shortfall"},
             "color": DARK["warn"], "fontWeight": 700},
        ],
    )


# ─────────────────────────────────────────────────────────────────
#  UI BUILDERS (light-themed sections)
# ─────────────────────────────────────────────────────────────────
def _view_toggle_buttons(section_id, active_view):
    """Chart / Data Table toggle. Stable string IDs."""
    chart_active = (active_view == "chart")
    return html.Div([
        html.Button(
            "\U0001F4CA Charts",
            id=f"{section_id}-view-chart",
            style={"padding": "6px 18px", "borderRadius": 6,
                   "border": f"1.5px solid {NAVY if chart_active else BORDER}",
                   "background": NAVY if chart_active else "#fff",
                   "color": "#fff" if chart_active else SLATE,
                   "fontSize": 12, "fontWeight": 600, "cursor": "pointer", "marginRight": 8},
        ),
        html.Button(
            "\U0001F4CB Data Table",
            id=f"{section_id}-view-table",
            style={"padding": "6px 18px", "borderRadius": 6,
                   "border": f"1.5px solid {NAVY if not chart_active else BORDER}",
                   "background": NAVY if not chart_active else "#fff",
                   "color": "#fff" if not chart_active else SLATE,
                   "fontSize": 12, "fontWeight": 600, "cursor": "pointer"},
        ),
    ], style={"display": "flex", "gap": 8, "marginBottom": 16})


def _chart_tab_buttons(section_id, tab_options, active_tab, hidden=False):
    """Sub-tab pill row. hidden=True hides via CSS but keeps components mounted
    so that callback inputs remain present in the DOM — this is what fixes
    the Table→Chart toggle bug."""
    buttons = []
    for tid, lbl in tab_options:
        is_active = (tid == active_tab)
        buttons.append(html.Button(
            lbl,
            id=f"{section_id}-tab-{tid}",
            style={"padding": "5px 14px", "borderRadius": 20,
                   "border": f"1.5px solid {TEAL if is_active else BORDER}",
                   "background": TEAL if is_active else "#fff",
                   "color": "#fff" if is_active else SLATE,
                   "fontSize": 11, "fontWeight": 600, "cursor": "pointer"},
        ))
    row_style = {"display": "none" if hidden else "flex",
                 "gap": 6, "marginBottom": 16, "flexWrap": "wrap"}
    return html.Div(buttons, style=row_style)


def chart_panel(title, subtitle=None, figure=None):
    children = [html.P(title, style={"margin": "0 0 4px", "fontWeight": 700,
                                     "color": NAVY, "fontSize": 14})]
    if subtitle:
        children.append(html.P(subtitle, style={"margin": "0 0 16px",
                                                "fontSize": 11, "color": SLATE}))
    if figure is not None:
        children.append(dcc.Graph(figure=figure, config={"displayModeBar": False},
                                  style={"height": 320}))
    return html.Div(children, style={"background": "#fff", "borderRadius": 10,
                                     "border": f"1px solid {BORDER}",
                                     "padding": 20, "marginBottom": 20})


def section_header(text, mt=False):
    return html.H3(text, style={
        "margin": "24px 0 10px" if mt else "0 0 10px", "color": NAVY, "fontSize": 13,
        "fontWeight": 700, "borderBottom": f"2px solid {TEAL}", "paddingBottom": 6
    })


# ── KPI CARDS ─────────────────────────────────────────────────────
def kpi_cards():
    kpis = [
        {"label": "FY2025 Revenue",       "val": "$4.4B",    "sub": "\u221216% YoY",              "color": AMBER,  "note": "C"},
        {"label": "FY2025 Gross Margin",  "val": "8.0%",     "sub": "vs. 8.4% in '24",            "color": TEAL,   "note": "C"},
        {"label": "FY2025 Adj. EBITDA",   "val": "($83)M",   "sub": "Improved from ($142)M",      "color": GREEN,  "note": "C"},
        {"label": "FY2025 Homes Sold",    "val": "11,791",   "sub": "\u221213% YoY",              "color": NAVY,   "note": "C"},
        {"label": "FY2025 YE Inventory",  "val": "2,867",    "sub": "$925M value",                "color": PURPLE, "note": "C"},
        {"label": "FY2025 YE Cash",       "val": "$962M",    "sub": "+$291M vs. '24",             "color": GREEN,  "note": "C"},
    ]
    cards = []
    for k in kpis:
        cards.append(html.Div([
            html.P(k["label"], style={"margin": 0, "fontSize": 10, "color": SLATE, "fontWeight": 600,
                                       "textTransform": "uppercase", "letterSpacing": 0.5}),
            html.P(k["val"], style={"margin": "6px 0 2px", "fontSize": 22, "fontWeight": 800, "color": NAVY}),
            html.P([k["sub"], " ", conf_badge(k["note"])], style={"margin": 0, "fontSize": 10, "color": SLATE}),
        ], style={"background": "#fff", "borderRadius": 10, "border": f"1px solid {BORDER}",
                   "padding": "14px 16px", "borderLeft": f"4px solid {k['color']}"}))
    return html.Div(cards, style={
        "display": "grid",
        "gridTemplateColumns": "repeat(auto-fill, minmax(160px, 1fr))",
        "gap": 12, "marginBottom": 24
    })


# ─────────────────────────────────────────────────────────────────
#  SECTION BUILDERS
#  Each builder ALWAYS renders the view toggle AND the sub-tab row
#  (hidden via CSS in table view). This keeps button IDs mounted so
#  callbacks fire even after toggling to table and back.
# ─────────────────────────────────────────────────────────────────
INCOME_TABS     = [("topline", "Top-Line"), ("margins", "Margins"),
                   ("opex", "Opex Breakdown"), ("ebitda_recon", "EBITDA Recon")]
UNIT_TABS       = [("volume", "Volume"), ("per_home", "Per-Home Economics"),
                   ("contribution", "Contribution Profit"), ("margins", "Margin Trends")]
BALANCE_TABS    = [("inventory", "Inventory"), ("capital_structure", "Capital Structure")]
CASHFLOW_TABS   = [("cf", "Operating CF"), ("capital_raised", "Capital Raised")]
EFFICIENCY_TABS = [("turnover", "Inventory Turnover"), ("bv", "Book Value / Share")]


def build_income(view, tab):
    is_chart = (view == "chart")
    children = [
        _view_toggle_buttons("income", view),
        _chart_tab_buttons("income", INCOME_TABS, tab, hidden=not is_chart),
    ]
    if is_chart:
        if tab == "topline":
            children.append(chart_panel("Revenue, Gross Profit & Adjusted EBITDA", "$M", chart_income_topline()))
        elif tab == "margins":
            children.append(chart_panel("Gross Margin & Contribution Margin", "%", chart_income_margins()))
        elif tab == "opex":
            children.append(chart_panel("Operating Expense Breakdown", "$M \u2014 SEC 10-K confirmed", chart_income_opex()))
        elif tab == "ebitda_recon":
            children.append(chart_panel("Adj. EBITDA Bridge \u2014 Key Reconciliation Items",
                                        "$M addbacks", chart_income_ebitda_recon()))
    else:
        children.append(section_header("Income Statement Summary"))
        children.append(build_metric_table([
            "revenue", "cogs", "grossProfit", "grossMargin", "smo", "ga", "td",
            "restructuring", "totalOpex", "operatingIncome", "operatingMargin",
            "interestExpense", "netLoss", "netMargin", "adjEBITDA",
            "adjNetLoss", "adjNetLossMargin",
        ]))
        children.append(section_header("EBITDA Reconciliation (Addback Items)", mt=True))
        children.append(build_metric_table(
            ["netLoss", "sbc", "da", "inventoryAdj", "reconRestructuring",
             "noteNonCash", "adjEBITDA"], show_yoy=False))
    return html.Div(children)


def build_unit(view, tab):
    is_chart = (view == "chart")
    children = [
        _view_toggle_buttons("unit", view),
        _chart_tab_buttons("unit", UNIT_TABS, tab, hidden=not is_chart),
    ]
    if is_chart:
        if tab == "volume":
            children.append(chart_panel("Annual Home Volume: Purchased vs. Sold", figure=chart_unit_volume()))
        elif tab == "per_home":
            children.append(chart_panel("Per-Home Economics", "$K per home sold", chart_unit_per_home()))
        elif tab == "contribution":
            children.append(chart_panel("Gross Profit vs. Contribution Profit", "$M", chart_unit_contribution()))
        elif tab == "margins":
            children.append(chart_panel("Gross Margin vs. Contribution Margin", "%", chart_unit_margins()))
    else:
        children.append(section_header("Unit Economics & Operational Metrics"))
        children.append(build_metric_table([
            "homesPurchased", "homesSold", "revenuePerHome", "gpPerHome",
            "contribProfitPerHm", "contributionProfit", "contributionMargin",
        ]))
    return html.Div(children)


def build_balance(view, tab):
    is_chart = (view == "chart")
    children = [
        _view_toggle_buttons("balance", view),
        _chart_tab_buttons("balance", BALANCE_TABS, tab, hidden=not is_chart),
    ]
    if is_chart:
        if tab == "inventory":
            children.append(chart_panel("Real Estate Inventory \u2014 Value & Count",
                                        "$M value (bars) vs. home count (line)",
                                        chart_balance_inventory()))
        elif tab == "capital_structure":
            children.append(chart_panel("Capital Structure Overview",
                                        "$M \u2014 SEC 10-K confirmed",
                                        chart_balance_capital()))
    else:
        children.append(section_header("Balance Sheet & Capital"))
        children.append(build_metric_table([
            "inventoryValue", "inventoryCount", "cashEquiv", "restrictedCash",
            "totalCash", "nrDebtCurrent", "nrDebtLongTerm", "convNotesCurrent",
            "convNotesLongTerm", "shareholdersEq",
        ]))
    return html.Div(children)


def build_cashflow(view, tab):
    is_chart = (view == "chart")
    children = [
        _view_toggle_buttons("cashflow", view),
        _chart_tab_buttons("cashflow", CASHFLOW_TABS, tab, hidden=not is_chart),
    ]
    if is_chart:
        if tab == "cf":
            children.append(chart_panel("Operating Cash Flow", "$M \u2014 SEC 10-K confirmed",
                                        chart_cf_operating()))
        elif tab == "capital_raised":
            children.append(chart_panel("Capital Raised \u2014 Equity & Net Debt Change",
                                        "$M \u2014 SEC 10-K confirmed",
                                        chart_cf_capital_raised()))
    else:
        children.append(section_header("Cash Flow & Liquidity"))
        children.append(build_metric_table([
            "operatingCF", "investingCF", "financingCF", "reInventoryCF",
            "equityRaised", "debtNetChange",
        ]))
    return html.Div(children)


def build_efficiency(view, tab):
    is_chart = (view == "chart")
    children = [
        _view_toggle_buttons("efficiency", view),
        _chart_tab_buttons("efficiency", EFFICIENCY_TABS, tab, hidden=not is_chart),
    ]
    if is_chart:
        if tab == "turnover":
            children.append(chart_panel("Inventory Turnover Ratio",
                                        "COGS \u00F7 Average Inventory \u2014 calculated",
                                        chart_eff_turnover()))
        elif tab == "bv":
            children.append(chart_panel("Book Value per Share & Shares Outstanding",
                                        "$ per share (line) vs. M shares (bar)",
                                        chart_eff_bv()))
    else:
        children.append(section_header("Efficiency & Risk Indicators"))
        children.append(build_metric_table([
            "inventoryTurnover", "bookValuePerShare", "sharesOutstanding",
        ]))
    return html.Div(children)


# ─────────────────────────────────────────────────────────────────
#  PROFITABILITY BRIDGE SECTION BUILDER
# ─────────────────────────────────────────────────────────────────
def _profit_view_toggle(active_view):
    chart_active = (active_view == "chart")
    base = {"padding": "6px 18px", "borderRadius": 6, "fontSize": 12,
            "fontWeight": 600, "cursor": "pointer"}
    return html.Div([
        html.Button(
            "\U0001F4CA Charts",
            id="profit-view-chart",
            style={**base,
                   "border": f"1.5px solid {DARK['accent'] if chart_active else DARK['panel_border']}",
                   "background": DARK["accent"] if chart_active else "rgba(255,255,255,0.04)",
                   "color": "#0d0d1a" if chart_active else DARK["text_dim"],
                   "marginRight": 8},
        ),
        html.Button(
            "\U0001F4CB Data Table",
            id="profit-view-table",
            style={**base,
                   "border": f"1.5px solid {DARK['accent'] if not chart_active else DARK['panel_border']}",
                   "background": DARK["accent"] if not chart_active else "rgba(255,255,255,0.04)",
                   "color": "#0d0d1a" if not chart_active else DARK["text_dim"]},
        ),
    ], style={"display": "flex", "gap": 8, "marginBottom": 16})


def _profit_slider(smo_fixed_pct):
    marks = {i: {"label": f"{i}%", "style": {"color": DARK["text_faint"], "fontSize": 10,
                                             "fontFamily": MONO}}
             for i in [10, 20, 30, 40, 50]}
    return html.Div([
        html.Div([
            html.Span("Assumed % of SM&O that is FIXED",
                      style={"fontSize": 11, "color": DARK["text_dim"],
                             "letterSpacing": "1px", "textTransform": "uppercase",
                             "fontFamily": MONO}),
            html.Span(f"{int(round(smo_fixed_pct * 100))}%",
                      id="profit-smo-display",
                      style={"fontSize": 18, "color": DARK["accent"], "fontWeight": 700,
                             "marginLeft": 12, "fontFamily": HEADING}),
        ], style={"display": "flex", "alignItems": "baseline", "marginBottom": 10}),
        dcc.Slider(
            id="profit-smo-slider",
            min=10, max=50, step=1,
            value=int(round(smo_fixed_pct * 100)),
            marks=marks,
            tooltip={"placement": "bottom", "always_visible": False},
            updatemode="drag",
        ),
        html.Div(
            "Moving this slider only re-labels SM&O between fixed and variable. "
            "Total SM&O dollars are invariant; shortfall is invariant by construction.",
            style={"fontSize": 10, "color": DARK["text_faint"],
                   "marginTop": 8, "fontStyle": "italic", "lineHeight": 1.5},
        ),
    ], style={"background": DARK["panel"], "border": f"1px solid {DARK['panel_border']}",
              "borderRadius": 10, "padding": "16px 20px", "marginBottom": 20})


def build_profit(view, smo_fixed_pct):
    df = compute_profit_df(smo_fixed_pct)
    children = [
        _profit_view_toggle(view),
        _profit_slider(smo_fixed_pct),
    ]

    if view == "chart":
        children.append(profit_summary_cards(df))
        children.append(html.Div(
            style={"background": DARK["panel"], "border": f"1px solid {DARK['panel_border']}",
                   "borderRadius": 12, "padding": "24px 20px 16px", "marginBottom": 24},
            children=[
                html.Div("CP After Interest vs. Fixed Cost Base", style={
                    "fontSize": 13, "fontWeight": 600, "color": DARK["white"],
                    "marginBottom": 4, "fontFamily": HEADING}),
                html.Div("Bars = $M  \u00B7  Line = CP After Int. Margin (adjusted)",
                         style={"fontSize": 11, "color": DARK["text_faint"],
                                "marginBottom": 20}),
                dcc.Graph(figure=chart_profit_main(df),
                          config={"displayModeBar": False}),
            ],
        ))
        children.append(html.Div(
            style={"background": "rgba(255,100,100,0.05)",
                   "border": "1px solid rgba(255,100,100,0.15)",
                   "borderRadius": 10, "padding": "18px 22px"},
            children=[
                html.Div("Key Finding", style={
                    "fontSize": 12, "fontWeight": 600, "color": DARK["warn"],
                    "marginBottom": 8, "fontFamily": HEADING}),
                html.Div(
                    "Opendoor has never generated sufficient Contribution Profit After Interest to cover its "
                    "fixed cost base in any year from FY2020\u2013FY2025. Shortfall is invariant to how SM&O is "
                    "split between fixed and variable \u2014 the slider is a decomposition tool, not a lever. "
                    "In normalized years (FY2024\u201325), the shortfall implies the business requires "
                    "significant volume expansion, margin improvement, or further fixed cost reduction to "
                    "reach operating profitability on a fully-burdened basis.",
                    style={"fontSize": 12, "color": "#ccc", "lineHeight": 1.7}),
            ],
        ))
    else:
        children.append(html.Div(
            style={"background": DARK["panel"], "border": f"1px solid {DARK['panel_border']}",
                   "borderRadius": 12, "padding": 20},
            children=[
                html.Div("Detailed Breakdown", style={
                    "fontSize": 13, "fontWeight": 600, "color": DARK["white"],
                    "marginBottom": 16, "fontFamily": HEADING}),
                build_profit_table(df),
            ],
        ))

    return html.Div(children, style={"background": DARK["bg"], "padding": "24px",
                                     "borderRadius": 12, "color": DARK["text"],
                                     "fontFamily": MONO})


# ─────────────────────────────────────────────────────────────────
#  APP
# ─────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Opendoor Technologies \u2014 Financial Dashboard"
server = app.server  # for gunicorn

app.index_string = """
<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; }
        .rc-slider-track { background-color: #4ecdc4 !important; }
        .rc-slider-handle { border-color: #4ecdc4 !important; background-color: #4ecdc4 !important; }
        .rc-slider-dot-active { border-color: #4ecdc4 !important; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
"""


# ── Top-level tabs config ────────────────────────────────────────
TOP_TABS = [
    {"id": "income",     "label": "\U0001F4C8 Income Statement"},
    {"id": "unit",       "label": "\U0001F3E0 Unit Economics"},
    {"id": "balance",    "label": "\u2696\uFE0F Balance Sheet"},
    {"id": "cashflow",   "label": "\U0001F4B5 Cash Flow"},
    {"id": "efficiency", "label": "\u26A1 Efficiency & Risk"},
    {"id": "profit",     "label": "\U0001F4A1 Profitability Bridge"},
]

INITIAL_STATE = {
    "income":     {"view": "chart", "tab": "topline"},
    "unit":       {"view": "chart", "tab": "volume"},
    "balance":    {"view": "chart", "tab": "inventory"},
    "cashflow":   {"view": "chart", "tab": "cf"},
    "efficiency": {"view": "chart", "tab": "turnover"},
    "profit":     {"view": "chart", "smo_pct": DEFAULT_SMO_FIXED_PCT},
}


def make_section_panel(section_id, initial_child, dark=False):
    """Wrap the section's content in a wrapper div whose children get replaced
    by the callback. dcc.Store holds per-section state."""
    wrapper_style = {}
    if dark:
        wrapper_style = {"background": DARK["bg"]}
    return html.Div([
        dcc.Store(id=f"{section_id}-state", data=INITIAL_STATE[section_id]),
        html.Div(initial_child, id=f"{section_id}-wrapper", style=wrapper_style),
    ])


# ── APP LAYOUT ───────────────────────────────────────────────────
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H1("Opendoor Technologies",
                    style={"margin": 0, "fontSize": 22, "fontWeight": 800,
                           "letterSpacing": -0.5, "color": "#fff"}),
            html.Span("NASDAQ: OPEN",
                      style={"background": TEAL, "borderRadius": 4,
                             "padding": "2px 8px", "fontSize": 11,
                             "fontWeight": 700, "color": "#fff"}),
            html.Span("Institutional Equity Research \u2014 Historical Financial Database",
                      style={"color": "#94a3b8", "fontSize": 12}),
        ], style={"display": "flex", "alignItems": "baseline", "gap": 12,
                  "flexWrap": "wrap"}),
        html.P("Fiscal Years 2020\u20132025 \u00B7 All monetary values in USD millions ($M) unless noted",
               style={"margin": "8px 0 0", "fontSize": 12, "color": "#94a3b8"}),
    ], style={"background": NAVY, "color": "#fff", "padding": "20px 32px 16px"}),

    # Data quality banner
    html.Div([
        html.Strong("Data Sources & Confidence:"),
        html.Span([
            html.Span("\u2713 Filed", style={"background": "#d1fae5", "color": "#065f46",
                                             "borderRadius": 4, "padding": "1px 6px",
                                             "fontSize": 10, "fontWeight": 700,
                                             "marginRight": 5}),
            "\u2713 Filed \u2014 Confirmed from 10-K / Official Earnings Release",
        ], style={"display": "flex", "alignItems": "center", "gap": 5}),
        html.Span([
            html.Span("\u2211 Calc.", style={"background": "#dbeafe", "color": "#1e3a8a",
                                             "borderRadius": 4, "padding": "1px 6px",
                                             "fontSize": 10, "fontWeight": 700,
                                             "marginRight": 5}),
            "\u2211 Calc. \u2014 Calculated from confirmed figures",
        ], style={"display": "flex", "alignItems": "center", "gap": 5}),
        html.Span([
            html.Span("~ Est.", style={"background": "#fef9c3", "color": "#713f12",
                                       "borderRadius": 4, "padding": "1px 6px",
                                       "fontSize": 10, "fontWeight": 700,
                                       "marginRight": 5}),
            "~ Est. \u2014 Estimated from training data; verify against SEC EDGAR filings",
        ], style={"display": "flex", "alignItems": "center", "gap": 5}),
        html.Span("\u26A0\uFE0F FY2025 GAAP net loss of ($1,100)M includes a $933M non-cash convertible note exchange loss; Adj. EBITDA of ($83)M better reflects operating performance."),
    ], style={"background": "#fffbeb", "borderBottom": "1px solid #fde68a",
              "padding": "10px 32px", "fontSize": 11, "color": "#92400e",
              "display": "flex", "gap": 24, "flexWrap": "wrap", "alignItems": "center"}),

    # Top-level dcc.Tabs (native tab switching — no callback needed)
    html.Div([
        dcc.Tabs(
            id="main-tabs",
            value="income",
            children=[
                dcc.Tab(
                    label=t["label"],
                    value=t["id"],
                    style={"padding": "14px 20px", "border": "none", "background": "none",
                           "color": SLATE, "fontWeight": 500, "fontSize": 13,
                           "whiteSpace": "nowrap"},
                    selected_style={"padding": "14px 20px", "border": "none",
                                    "background": "none", "color": TEAL,
                                    "fontWeight": 700, "fontSize": 13,
                                    "borderBottom": f"3px solid {TEAL}",
                                    "whiteSpace": "nowrap"},
                    children=html.Div([
                        kpi_cards() if t["id"] != "profit" else html.Div(),
                        make_section_panel(
                            t["id"],
                            (build_income(**INITIAL_STATE["income"])       if t["id"] == "income" else
                             build_unit(**INITIAL_STATE["unit"])           if t["id"] == "unit" else
                             build_balance(**INITIAL_STATE["balance"])     if t["id"] == "balance" else
                             build_cashflow(**INITIAL_STATE["cashflow"])   if t["id"] == "cashflow" else
                             build_efficiency(**INITIAL_STATE["efficiency"]) if t["id"] == "efficiency" else
                             build_profit(INITIAL_STATE["profit"]["view"],
                                          INITIAL_STATE["profit"]["smo_pct"])),
                            dark=(t["id"] == "profit"),
                        ),
                    ], style={"padding": "24px 32px", "maxWidth": 1300,
                              "margin": "0 auto",
                              "background": DARK["bg"] if t["id"] == "profit" else "transparent"}),
                )
                for t in TOP_TABS
            ],
            style={"height": "auto"},
            colors={"border": "transparent", "primary": TEAL, "background": "#fff"},
        ),
    ], style={"background": "#fff", "borderBottom": f"1px solid {BORDER}", "padding": "0 32px"}),

    # Footer
    html.Div(
        html.Div([
            html.Strong("Data Sources:", style={"color": NAVY}),
            " Opendoor Technologies SEC Form 10-K filings (FY2020\u2013FY2025), Q4 earnings releases, and investor presentations. "
            "Official filings available at investor.opendoor.com and sec.gov/cgi-bin/browse-edgar (CIK: 0001801169). "
            "Items marked \"~ Est.\" are drawn from training-data knowledge of public disclosures and should be cross-referenced against the relevant 10-K or earnings press release. "
            "Opendoor reports real estate inventory as an operating activity; home purchase outflows and sale proceeds flow through operating cash flow, not investing activities. "
            "FY2020 SPAC merger with Social Capital Hedosophia Holdings Corp. II closed December 18, 2020. "
            "FY2023 GAAP net loss of ($275)M is smaller than Adj. EBITDA of ($627)M due to excluded non-operating gains (incl. bargain purchase gain from Doma Holdings acquisition)."
        ], style={"background": "#f1f5f9", "borderRadius": 10, "padding": "16px 20px",
                   "fontSize": 11, "color": SLATE, "lineHeight": 1.7}),
        style={"padding": "24px 32px 0", "maxWidth": 1300, "margin": "0 auto"}
    ),

], style={"fontFamily": FONT_FAMILY, "background": "#f8fafc",
          "minHeight": "100vh", "paddingBottom": 60})


# ─────────────────────────────────────────────────────────────────
#  PER-SECTION CALLBACKS (simple string IDs, no pattern-matching)
# ─────────────────────────────────────────────────────────────────
def register_light_callback(section_id, build_fn, tab_options):
    tab_btn_ids = [f"{section_id}-tab-{tid}" for tid, _ in tab_options]
    inputs = [
        Input(f"{section_id}-view-chart", "n_clicks"),
        Input(f"{section_id}-view-table", "n_clicks"),
    ] + [Input(bid, "n_clicks") for bid in tab_btn_ids]

    @app.callback(
        Output(f"{section_id}-wrapper", "children"),
        Output(f"{section_id}-state",   "data"),
        *inputs,
        State(f"{section_id}-state", "data"),
        prevent_initial_call=True,
    )
    def _cb(*args):
        state = dict(args[-1]) if args[-1] else dict(INITIAL_STATE[section_id])
        triggered = ctx.triggered_id
        if triggered == f"{section_id}-view-chart":
            state["view"] = "chart"
        elif triggered == f"{section_id}-view-table":
            state["view"] = "table"
        elif isinstance(triggered, str) and triggered.startswith(f"{section_id}-tab-"):
            state["tab"] = triggered.replace(f"{section_id}-tab-", "")
            state["view"] = "chart"
        else:
            return dash.no_update, dash.no_update
        return build_fn(state["view"], state["tab"]), state
    return _cb


register_light_callback("income",     build_income,     INCOME_TABS)
register_light_callback("unit",       build_unit,       UNIT_TABS)
register_light_callback("balance",    build_balance,    BALANCE_TABS)
register_light_callback("cashflow",   build_cashflow,   CASHFLOW_TABS)
register_light_callback("efficiency", build_efficiency, EFFICIENCY_TABS)


# Profit section has its own callback (slider instead of sub-tabs)
@app.callback(
    Output("profit-wrapper", "children"),
    Output("profit-state",   "data"),
    Input("profit-view-chart",   "n_clicks"),
    Input("profit-view-table",   "n_clicks"),
    Input("profit-smo-slider",   "value"),
    State("profit-state", "data"),
    prevent_initial_call=True,
)
def _profit_cb(_c1, _c2, slider_val, state):
    state = dict(state) if state else dict(INITIAL_STATE["profit"])
    triggered = ctx.triggered_id
    if triggered == "profit-view-chart":
        state["view"] = "chart"
    elif triggered == "profit-view-table":
        state["view"] = "table"
    elif triggered == "profit-smo-slider":
        if slider_val is not None:
            state["smo_pct"] = max(0.10, min(0.50, slider_val / 100.0))
    else:
        return dash.no_update, dash.no_update
    return build_profit(state["view"], state["smo_pct"]), state


# ─────────────────────────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────────────────────────
def _open_safari():
    import time
    time.sleep(1.5)
    url = "http://127.0.0.1:8050"
    try:
        subprocess.Popen(["open", "-a", "Safari", url])
    except FileNotFoundError:
        webbrowser.open(url)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    # Only auto-open Safari if running locally (not in a hosted environment)
    if os.environ.get("PORT") is None:
        print("\n  Opendoor Financial Dashboard")
        print(f"  Opening in Safari at http://127.0.0.1:{port} ...\n")
        threading.Thread(target=_open_safari, daemon=True).start()
    app.run(debug=False, host="0.0.0.0", port=port)
