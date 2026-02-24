import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import re
import yfinance as yf

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Institutional Retest Scanner",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme ─────────────────────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"
_t = st.session_state["theme"]

# ── CSS Variables by theme ────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "--bg":          "#0b0d11",
        "--bg-card":     "#13161d",
        "--bg-raised":   "#1a1d27",
        "--bg-sidebar":  "#0e1017",
        "--border":      "#222637",
        "--border-soft": "#1c1f2e",
        "--text-primary":"#f0f2f8",
        "--text-secondary":"#8b92a8",
        "--text-muted":  "#4a5068",
        "--accent":      "#f0b429",
        "--accent-soft": "rgba(240,180,41,0.12)",
        "--green":       "#10b981",
        "--green-soft":  "rgba(16,185,129,0.12)",
        "--red":         "#f43f5e",
        "--red-soft":    "rgba(244,63,94,0.12)",
        "--blue":        "#3b82f6",
        "--blue-soft":   "rgba(59,130,246,0.12)",
        "--amber":       "#f59e0b",
        "--indigo":      "#818cf8",
        "--progress-from":"#f0b429",
        "--progress-to": "#f43f5e",
        "--shadow":      "0 4px 24px rgba(0,0,0,0.4)",
    },
    "light": {
        "--bg":          "#f4f5f7",
        "--bg-card":     "#ffffff",
        "--bg-raised":   "#eef0f5",
        "--bg-sidebar":  "#ffffff",
        "--border":      "#e2e5ed",
        "--border-soft": "#eaecf2",
        "--text-primary":"#111827",
        "--text-secondary":"#4b5563",
        "--text-muted":  "#9ca3af",
        "--accent":      "#d97706",
        "--accent-soft": "rgba(217,119,6,0.1)",
        "--green":       "#059669",
        "--green-soft":  "rgba(5,150,105,0.1)",
        "--red":         "#dc2626",
        "--red-soft":    "rgba(220,38,38,0.1)",
        "--blue":        "#2563eb",
        "--blue-soft":   "rgba(37,99,235,0.1)",
        "--amber":       "#d97706",
        "--indigo":      "#4f46e5",
        "--progress-from":"#d97706",
        "--progress-to": "#dc2626",
        "--shadow":      "0 2px 12px rgba(0,0,0,0.08)",
    }
}

_vars = THEMES[_t]
_css_vars = "\n".join([f"  {k}: {v};" for k, v in _vars.items()])

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Bricolage+Grotesque:opsz,wght@12..96,300;12..96,500;12..96,700;12..96,800&display=swap');

:root {{
{_css_vars}
}}

/* ── Reset & Base ── */
html, body, [class*="css"] {{
    font-family: 'Bricolage Grotesque', sans-serif;
    background-color: var(--bg) !important;
    color: var(--text-primary) !important;
    -webkit-font-smoothing: antialiased;
}}
.stApp {{ background-color: var(--bg) !important; }}
.main .block-container {{ padding-top: 1.5rem; max-width: 1200px; }}

/* ── Sidebar ── */
div[data-testid="stSidebar"] {{
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border) !important;
}}
div[data-testid="stSidebar"] * {{ color: var(--text-primary) !important; }}
div[data-testid="stSidebar"] .stSlider > div > div > div {{
    background: var(--accent) !important;
}}

/* ── Header ── */
.app-header {{
    display: flex; align-items: flex-start; justify-content: space-between;
    margin-bottom: 1.5rem; padding-bottom: 1.2rem;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap; gap: 0.75rem;
}}
.app-title {{
    font-size: clamp(1.6rem, 4vw, 2.2rem);
    font-weight: 800; letter-spacing: -0.04em;
    color: var(--text-primary);
    line-height: 1;
}}
.app-title span {{
    color: var(--accent);
}}
.app-subtitle {{
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem; color: var(--text-muted);
    letter-spacing: 0.08em; text-transform: uppercase;
    margin-top: 0.35rem;
}}
.theme-toggle {{
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--bg-raised); border: 1px solid var(--border);
    border-radius: 20px; padding: 5px 12px; cursor: pointer;
    font-family: 'DM Mono', monospace; font-size: 0.72rem;
    color: var(--text-secondary); user-select: none;
    transition: all 0.2s;
}}
.theme-toggle:hover {{ border-color: var(--accent); color: var(--accent); }}

/* ── Mode pill ── */
.mode-pill {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 20px;
    font-family: 'DM Mono', monospace; font-size: 0.68rem; font-weight: 500;
    letter-spacing: 0.04em;
}}
.mode-retest  {{ background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent); }}
.mode-base    {{ background: var(--blue-soft);   color: var(--blue);   border: 1px solid var(--blue); }}

/* ── Section header ── */
.section-header {{
    font-family: 'DM Mono', monospace; font-size: 0.65rem;
    color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.14em;
    border-bottom: 1px solid var(--border-soft);
    padding-bottom: 0.45rem; margin-bottom: 0.9rem; margin-top: 1.4rem;
}}

/* ── Cards ── */
.card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 16px; padding: 1.1rem 1.3rem; margin-bottom: 0.75rem;
    box-shadow: var(--shadow); transition: border-color 0.2s;
}}
.card:hover {{ border-color: var(--accent); }}
.card-accent {{ border-left: 3px solid var(--accent); }}
.card-green  {{ border-left: 3px solid var(--green); }}
.card-blue   {{ border-left: 3px solid var(--blue); }}
.card-muted  {{ border-left: 3px solid var(--border); opacity: 0.85; }}

/* ── Hit card ── */
.hit-card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 16px; padding: 1.1rem 1.3rem; margin-bottom: 0.75rem;
    box-shadow: var(--shadow);
}}
.hit-card-full   {{ border-left: 4px solid var(--green); }}
.hit-card-strong {{ border-left: 4px solid var(--accent); }}
.hit-card-watch  {{ border-left: 4px solid var(--indigo); }}

/* ── Ticker ── */
.ticker-label {{
    font-size: 1.3rem; font-weight: 800; letter-spacing: -0.02em;
    color: var(--text-primary);
}}
.score-chip {{
    display: inline-flex; align-items: center;
    background: var(--accent-soft); color: var(--accent);
    border: 1px solid var(--accent); border-radius: 20px;
    font-family: 'DM Mono', monospace; font-size: 0.72rem; font-weight: 500;
    padding: 2px 10px;
}}
.price-label {{
    font-family: 'DM Mono', monospace; font-size: 0.95rem;
    color: var(--text-secondary); font-weight: 500;
}}

/* ── Badges ── */
.badge {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 9px; border-radius: 6px;
    font-size: 0.63rem; font-family: 'DM Mono', monospace; font-weight: 500;
    margin-right: 4px; margin-top: 4px; letter-spacing: 0.02em;
}}
.badge-green {{ background: var(--green-soft); color: var(--green); border: 1px solid var(--green); }}
.badge-red   {{ background: var(--red-soft);   color: var(--red);   border: 1px solid var(--red); }}

/* ── Category headers ── */
.category-header {{
    display: flex; align-items: center; gap: 8px;
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em;
    padding: 0.55rem 1rem; border-radius: 10px;
    margin: 1.5rem 0 0.6rem; text-transform: uppercase;
    font-family: 'DM Mono', monospace;
}}
.cat-full   {{ background: var(--green-soft); color: var(--green); border: 1px solid var(--green); }}
.cat-strong {{ background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent); }}
.cat-watch  {{ background: var(--blue-soft); color: var(--blue); border: 1px solid var(--blue); }}

/* ── Metric strip ── */
.metric-strip {{
    display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem;
}}
.metric-item {{
    background: var(--bg-raised); border-radius: 8px;
    padding: 0.3rem 0.7rem; font-family: 'DM Mono', monospace;
    font-size: 0.63rem; color: var(--text-muted);
}}
.metric-item b {{ color: var(--text-secondary); }}

/* ── TV button ── */
.tv-btn {{
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--blue-soft); color: var(--blue);
    font-family: 'DM Mono', monospace; font-size: 0.63rem; font-weight: 500;
    padding: 4px 10px; border-radius: 6px; text-decoration: none;
    border: 1px solid var(--blue); margin-left: 8px;
    transition: all 0.15s;
}}
.tv-btn:hover {{ background: var(--blue); color: #fff; }}

/* ── Info / step boxes ── */
.info-box {{
    background: var(--bg-raised); border: 1px solid var(--border-soft);
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 1rem;
    font-family: 'DM Mono', monospace; font-size: 0.73rem;
    color: var(--text-secondary); line-height: 1.7;
}}
.step-box {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.8rem 1.2rem; margin-bottom: 0.6rem;
    display: flex; align-items: flex-start; gap: 0.75rem;
}}
.step-num {{
    background: var(--accent-soft); color: var(--accent);
    border-radius: 50%; width: 24px; height: 24px; min-width: 24px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'DM Mono', monospace; font-size: 0.72rem; font-weight: 700;
}}
.step-text {{ font-family: 'DM Mono', monospace; font-size: 0.72rem; color: var(--text-secondary); line-height: 1.5; }}

/* ── Ticker pills ── */
.ticker-pill {{
    display: inline-flex; align-items: center;
    background: var(--bg-raised); color: var(--accent);
    border: 1px solid var(--border); border-radius: 6px;
    font-family: 'DM Mono', monospace; font-size: 0.68rem;
    padding: 2px 8px; margin: 2px;
}}

/* ── Known setup cards ── */
.known-setup-card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 0.5rem;
    transition: border-color 0.2s;
}}
.known-setup-card:hover {{ border-color: var(--accent); }}
.known-setup-card .ks-ticker {{
    font-size: 1.05rem; font-weight: 800; color: var(--text-primary);
    letter-spacing: -0.01em;
}}
.known-setup-card .ks-date {{
    font-family: 'DM Mono', monospace; font-size: 0.62rem;
    color: var(--text-muted); margin-left: 8px;
}}
.known-setup-card .ks-desc {{
    font-family: 'DM Mono', monospace; font-size: 0.67rem;
    color: var(--text-muted); margin-top: 0.3rem; line-height: 1.5;
}}

/* ── Backtest result cards ── */
.bt-result-pass {{
    background: var(--green-soft); border: 1px solid var(--green);
    border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 0.6rem;
}}
.bt-result-fail {{
    background: var(--red-soft); border: 1px solid var(--red);
    border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 0.6rem;
}}
.bt-result-warn {{
    background: var(--accent-soft); border: 1px solid var(--accent);
    border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 0.6rem;
}}
.bt-ticker {{ font-size: 1.1rem; font-weight: 800; letter-spacing: -0.01em; }}
.bt-score  {{ font-family: 'DM Mono', monospace; font-size: 0.7rem; color: var(--text-muted); margin-left: 10px; }}
.bt-meta   {{ font-family: 'DM Mono', monospace; font-size: 0.63rem; color: var(--text-muted); margin-top: 0.4rem; line-height: 1.7; }}

/* ── Log box ── */
.log-box {{
    background: var(--bg-raised); border: 1px solid var(--border);
    border-radius: 10px; padding: 0.9rem 1rem;
    font-family: 'DM Mono', monospace; font-size: 0.68rem;
    color: var(--text-muted); max-height: 260px; overflow-y: auto;
    line-height: 1.6;
}}

/* ── Progress bar ── */
.stProgress > div > div > div > div {{
    background: linear-gradient(90deg, var(--progress-from), var(--progress-to)) !important;
    border-radius: 4px;
}}

/* ── Buttons ── */
.stButton > button {{
    background: var(--accent) !important; color: #0b0d11 !important;
    font-family: 'Bricolage Grotesque', sans-serif !important;
    font-weight: 700 !important; border: none !important;
    border-radius: 10px !important; padding: 0.55rem 1.8rem !important;
    font-size: 0.88rem !important; width: 100% !important;
    transition: opacity 0.15s, transform 0.1s !important;
    letter-spacing: 0.01em !important;
}}
.stButton > button:hover {{ opacity: 0.88 !important; transform: translateY(-1px) !important; }}
.stButton > button:active {{ transform: translateY(0) !important; }}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    background: var(--bg-raised) !important;
    border-radius: 12px !important; padding: 3px !important;
    border: 1px solid var(--border) !important; gap: 2px !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important; border-radius: 9px !important;
    font-family: 'Bricolage Grotesque', sans-serif !important;
    font-size: 0.82rem !important; font-weight: 600 !important;
    color: var(--text-muted) !important; padding: 0.45rem 1rem !important;
    border: none !important;
}}
.stTabs [aria-selected="true"] {{
    background: var(--bg-card) !important; color: var(--text-primary) !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.15) !important;
}}

/* ── Inputs ── */
.stTextArea textarea, .stTextInput input {{
    background: var(--bg-raised) !important; color: var(--text-primary) !important;
    border: 1px solid var(--border) !important; border-radius: 10px !important;
    font-family: 'DM Mono', monospace !important; font-size: 0.8rem !important;
}}
.stTextArea textarea:focus, .stTextInput input:focus {{
    border-color: var(--accent) !important; box-shadow: 0 0 0 2px var(--accent-soft) !important;
}}
.stSelectbox > div > div, .stMultiSelect > div > div {{
    background: var(--bg-raised) !important; border: 1px solid var(--border) !important;
    border-radius: 10px !important; color: var(--text-primary) !important;
}}

/* ── Metric card ── */
.metric-card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 0.75rem;
    box-shadow: var(--shadow);
}}
.metric-card .label {{
    font-family: 'DM Mono', monospace; font-size: 0.62rem;
    color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em;
}}
.metric-card .value {{
    font-size: 1.9rem; font-weight: 800; color: var(--accent);
    letter-spacing: -0.03em; line-height: 1.1;
}}

/* ── Summary table ── */
.summary-table {{ width: 100%; border-collapse: collapse; font-family: 'DM Mono', monospace; font-size: 0.72rem; }}
.summary-table th {{
    color: var(--text-muted); font-size: 0.62rem; text-transform: uppercase;
    letter-spacing: 0.1em; padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--border);
}}
.summary-table td {{ padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border-soft); color: var(--text-secondary); }}
.summary-table tr:last-child td {{ border-bottom: none; }}

/* ── Idle state ── */
.idle-card {{
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 20px; padding: 3rem 2rem; text-align: center;
    margin-top: 1rem; box-shadow: var(--shadow);
}}
.idle-icon {{ font-size: 2.5rem; margin-bottom: 0.75rem; }}
.idle-title {{ font-size: 1.1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.4rem; }}
.idle-sub   {{ font-family: 'DM Mono', monospace; font-size: 0.72rem; color: var(--text-muted); line-height: 1.6; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
_mode_display = "🔄 Retest" if st.session_state.get("theme") == "dark" else "🔄 Retest"
col_hdr, col_theme = st.columns([6, 1])
with col_hdr:
    st.markdown('''
    <div class="app-header">
      <div>
        <div class="app-title">📡 <span>Institutional</span> Scanner</div>
        <div class="app-subtitle">TradingView Pre-Filter · 200W SMA Retest · Volume Surge · Base Breakout</div>
      </div>
    </div>
    ''', unsafe_allow_html=True)
with col_theme:
    _icon = "☀️ Light" if _t == "dark" else "🌙 Dark"
    if st.button(_icon, key="theme_btn"):
        st.session_state["theme"] = "light" if _t == "dark" else "dark"
        st.rerun()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-header">Configuration</div>', unsafe_allow_html=True)
    st.caption("✅ No API key needed — powered by yfinance")

    # ── Mode Toggle ───────────────────────────────────────────────────────────
    scan_mode = st.radio(
        "Scanner Mode",
        ["🔴  Retest Mode", "🟡  Base Breakout Mode"],
        help="Retest: deep correction → 200W SMA retest (TPL, LITE, NVDA). "
             "Base Breakout: multi-year sideways base → volume breakout (KGC, gold/commodities)."
    )
    is_retest = scan_mode == "🔴  Retest Mode"

    if is_retest:
        st.markdown('<div class="section-header">Retest Criteria — Weekly</div>', unsafe_allow_html=True)
        st.caption("Big prior run → deep correction → 200W SMA retest")
        w_dist_200sma_lo = st.slider("Max % BELOW 200W SMA", 0, 80, 60,
            help="Bear market lows: META=-51%, TSLA=-26%, ENPH=-49%, PYPL=-49%")
        w_dist_200sma_hi = st.slider("Max % ABOVE 200W SMA", 0, 150, 80,
            help="TPL=+41%, KGC=+78%, LITE=+39% — setups can consolidate well above the 200W SMA")
        w_prior_run  = st.slider("Min prior run from base (%)", 50, 2000, 300)
        w_correction = st.slider("Min correction from ATH (%)", 20, 85, 35)
        w_vol_mult   = st.slider("Weekly volume surge multiplier", 1.0, 5.0, 1.2)
        # Base breakout params not used in retest mode — set neutral defaults
        bb_base_years  = 2
        bb_range_pct   = 60
        bb_atr_max     = 4.0
        bb_vol_mult    = 1.5
        bb_sma_lo      = 10
        bb_sma_hi      = 40
        bb_sectors     = []

        st.markdown('<div class="section-header">Retest Criteria — Daily</div>', unsafe_allow_html=True)
        d_atr_pct_min = st.slider("Min ATR% (daily)", 2.0, 8.0, 3.0)
        d_atr_pct_max = st.slider("Max ATR% (daily)", 4.0, 15.0, 12.0)
        d_above_50sma = st.slider("Max % above 50-day SMA", 0, 20, 10)
    else:
        st.markdown('<div class="section-header">Base Breakout Criteria — Weekly</div>', unsafe_allow_html=True)
        st.caption("Multi-year sideways base → volume breakout (KGC style)")
        bb_base_years = st.slider("Min base duration (years)", 1, 5, 2,
            help="How many years price has been consolidating sideways")
        bb_range_pct  = st.slider("Max base range % (high-low / low)", 10, 100, 60,
            help="Lower = tighter base. KGC-style bases are often 40-60% range over years")
        bb_atr_max    = st.slider("Max weekly ATR% during base", 2.0, 8.0, 4.0,
            help="Tight bases have low ATR — filters out choppy/volatile stocks")
        bb_vol_mult   = st.slider("Volume surge multiplier (breakout week)", 1.0, 5.0, 2.0,
            help="Breakout volume should be significantly above average")
        bb_sma_lo     = st.slider("Max % BELOW 200W SMA", 0, 30, 10,
            help="Base breakouts happen near or above the 200W SMA, not deep below")
        bb_sma_hi     = st.slider("Max % ABOVE 200W SMA", 0, 100, 40,
            help="KGC was ~60-70% above 200W SMA at breakout — allow more room than retest mode")

        st.markdown('<div class="section-header">Sector Filter (optional)</div>', unsafe_allow_html=True)
        st.caption("Base breakouts cluster in sectors with macro tailwinds")
        bb_sectors = st.multiselect("Require sector match", [
            "Gold & Precious Metals", "Energy", "Basic Materials",
            "Industrials", "Uranium & Nuclear", "Copper & Mining",
        ], default=[], help="Leave empty to scan all sectors")

        st.markdown('<div class="section-header">Daily Criteria</div>', unsafe_allow_html=True)
        d_atr_pct_min = st.slider("Min ATR% (daily)", 1.0, 5.0, 2.0)
        d_atr_pct_max = st.slider("Max ATR% (daily)", 3.0, 12.0, 8.0)
        d_above_50sma = st.slider("Max % above 50-day SMA", 0, 40, 20)

        # Retest params not used — set neutral defaults
        w_dist_200sma_lo = 60
        w_dist_200sma_hi = 80
        w_prior_run      = 300
        w_correction     = 35
        w_vol_mult       = 1.2

    st.markdown('<div class="section-header">Universe</div>', unsafe_allow_html=True)
    universe_choice = st.selectbox("Stock Universe", [
        "TradingView Pre-Filter (recommended)",
        "S&P 500 (505 stocks)",
        "Custom Tickers",
    ])
    custom_tickers_input = ""
    if universe_choice == "Custom Tickers":
        custom_tickers_input = st.text_area("Tickers (comma separated)", "TPL, NVDA, TSLA")

    max_stocks  = st.number_input("Max stocks to scan", 50, 2000, 500, step=50)
    min_display = st.slider("Min score to display", 0, 90, 60,
        help="Show everything above this score — lower = wider net. Hard pass/fail gates removed.")
    run_scan = st.button("🚀 Run Scanner")

# ── S&P 500 Universe ──────────────────────────────────────────────────────────
SP500_TICKERS = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB","AKAM","ALB","ARE",
    "ALGN","ALLE","LNT","ALL","GOOGL","MO","AMZN","AEP","AXP","AMT","AWK","AMP","AME","AMGN",
    "APH","ADI","ANSS","AON","APA","AAPL","AMAT","APTV","ACGL","ADM","ANET","AJG","T","ADSK",
    "ADP","AZO","AVB","AVY","AXON","BKR","BALL","BAC","BK","BBY","BIIB","BLK","BX","BA","BSX",
    "BMY","AVGO","BR","BRO","BG","CDNS","CPB","COF","CAH","KMX","CCL","CARR","CAT","CBOE","CBRE",
    "CDW","COR","CNC","SCHW","CHTR","CVX","CMG","CB","CHD","CI","CINF","CTAS","CSCO","C","CLX",
    "CME","CMS","KO","CTSH","CL","CMCSA","CAG","COP","ED","STZ","CEG","CPRT","GLW","CTVA","COST",
    "CTRA","CCI","CSX","CMI","CVS","DHI","DHR","DRI","DE","DELL","DAL","DVN","DXCM","FANG","DLR",
    "DFS","DG","DLTR","D","DPZ","DOV","DOW","DTE","DUK","DD","EMN","ETN","EBAY","ECL","EIX","EW",
    "EA","ELV","LLY","EMR","ENPH","ETR","EOG","EQT","EFX","EQIX","EQR","ESS","EL","ETSY","EG",
    "ES","EXC","EXPE","EXPD","EXR","XOM","FDS","FICO","FAST","FRT","FDX","FIS","FITB","FSLR",
    "FE","FI","FMC","F","FTNT","FTV","BEN","FCX","GRMN","IT","GE","GEHC","GD","GIS","GM","GPC",
    "GILD","GPN","GL","GS","HAL","HIG","HAS","HCA","HSY","HES","HPE","HLT","HOLX","HD","HON",
    "HRL","HST","HWM","HPQ","HUBB","HUM","HBAN","HII","IBM","IEX","IDXX","ITW","ILMN","IR",
    "INTC","ICE","IFF","IP","IPG","INTU","ISRG","IVZ","IQV","IRM","JBHT","J","JNJ","JCI","JPM",
    "K","KDP","KEY","KEYS","KMB","KIM","KMI","KLAC","KHC","KR","LHX","LH","LRCX","LW","LVS",
    "LDOS","LEN","LIN","LYV","LMT","L","LOW","LULU","LYB","MTB","MRO","MPC","MAR","MMC","MLM",
    "MAS","MA","MKC","MCD","MCK","MDT","MRK","META","MET","MTD","MGM","MCHP","MU","MSFT","MAA",
    "MRNA","MOH","TAP","MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI","NDAQ","NTAP","NFLX",
    "NEM","NEE","NKE","NI","NSC","NTRS","NOC","NCLH","NRG","NUE","NVDA","NVR","NXPI","O","OXY",
    "ODFL","OMC","ON","OKE","ORCL","OTIS","PCAR","PKG","PANW","PH","PAYX","PYPL","PEP","PFE",
    "PCG","PM","PSX","PNC","POOL","PPG","PPL","PFG","PG","PGR","PLD","PRU","PEG","PTC","PSA",
    "PHM","PWR","QCOM","DGX","RL","RJF","RTX","REG","REGN","RF","RSG","RMD","ROK","ROL","ROP",
    "ROST","RCL","SPGI","CRM","SBAC","SLB","STX","SRE","NOW","SHW","SPG","SJM","SNA","SO","LUV",
    "SWK","SBUX","STT","STLD","STE","SYK","SYF","SNPS","SYY","TMUS","TROW","TTWO","TRGP","TGT",
    "TEL","TDY","TSLA","TXN","TXT","TMO","TJX","TSCO","TT","TDG","TRV","TRMB","TFC","TYL","TSN",
    "USB","UBER","UNP","UAL","UPS","URI","UNH","UHS","VLO","VTR","VRSN","VRSK","VZ","VRTX","VICI",
    "V","VMC","WAB","WBA","WMT","WBD","WM","WAT","WEC","WFC","WELL","WST","WDC","WHR","WMB",
    "WTW","GWW","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZION","ZTS","TPL"
]

# ── TradingView Screener API ──────────────────────────────────────────────────
SECTOR_MAP = {
    "Energy":             "Energy",
    "Technology":         "Technology",
    "Industrials":        "Industrials",
    "Basic Materials":    "Basic Materials",
    "Healthcare":         "Health Technology",
    "Consumer Cyclical":  "Consumer Cyclical",
    "Financial":          "Finance",
    "Real Estate":        "Real Estate",
    "Communication":      "Communication Services",
    "Utilities":          "Utilities",
    "Consumer Defensive": "Consumer Defensive",
}

def fetch_tradingview_tickers(
    min_market_cap_b=1.0,
    max_market_cap_b=None,
    min_avg_vol=300_000,
    perf_1y_min=-60.0,
    perf_1y_max=-15.0,
    sectors=None,
    exchanges=("NASDAQ", "NYSE", "AMEX"),
    max_results=500,
):
    url = "https://scanner.tradingview.com/america/scan"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }
    filters = [
        {"left": "market_cap_basic", "operation": "greater", "right": int(min_market_cap_b * 1e9)},
        {"left": "average_volume_10d_calc", "operation": "greater", "right": min_avg_vol},
        {"left": "Perf.Y", "operation": "in_range", "right": [perf_1y_min, perf_1y_max]},
        {"left": "exchange", "operation": "in_range", "right": list(exchanges)},
    ]
    if max_market_cap_b:
        filters.append({"left": "market_cap_basic", "operation": "less", "right": int(max_market_cap_b * 1e9)})
    if sectors:
        tv_sectors = [SECTOR_MAP.get(s, s) for s in sectors]
        filters.append({"left": "sector", "operation": "in_range", "right": tv_sectors})

    payload = {
        "filter": filters,
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "close", "market_cap_basic", "average_volume_10d_calc", "Perf.Y", "sector"],
        "sort": {"sortBy": "average_volume_10d_calc", "sortOrder": "desc"},
        "range": [0, max_results],
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        if r.status_code != 200:
            return [], f"TradingView returned HTTP {r.status_code}"
        rows = r.json().get("data", [])
        tickers = [row["d"][0] for row in rows if re.match(r"^[A-Z]{1,5}$", str(row.get("d", [None])[0] or ""))]
        return tickers, None
    except Exception as e:
        return [], str(e)

# ── yfinance Data Helpers ─────────────────────────────────────────────────────
_yf_cache = {}

# ── Sector ETF map ────────────────────────────────────────────────────────────
SECTOR_ETF_MAP = {
    "XLK":  "Technology",
    "XLV":  "Healthcare",
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLB":  "Basic Materials",
    "XLI":  "Industrials",
    "XLC":  "Communication",
    "XLY":  "Consumer Cyclical",
    "XLP":  "Consumer Defensive",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
    "GDX":  "Gold Miners",
}

def fetch_sector_returns(period_weeks=26):
    """
    Fetch 26W return for each sector ETF vs SPY.
    Returns dict: {ticker_sector_etf: relative_return_pct}
    Pre-fetched once per scan, cached in session state.
    """
    key = f"sector_returns_{period_weeks}"
    if key in st.session_state:
        return st.session_state[key]
    results = {}
    try:
        spy = yf.Ticker("SPY").history(period="1y", interval="1wk", auto_adjust=True)
        spy_ret = (spy["Close"].iloc[-1] / spy["Close"].iloc[-period_weeks] - 1) * 100 if len(spy) >= period_weeks else 0
        for etf in list(SECTOR_ETF_MAP.keys()):
            try:
                df = yf.Ticker(etf).history(period="1y", interval="1wk", auto_adjust=True)
                if len(df) >= period_weeks:
                    etf_ret = (df["Close"].iloc[-1] / df["Close"].iloc[-period_weeks] - 1) * 100
                    results[etf] = round(etf_ret - spy_ret, 1)
                else:
                    results[etf] = 0
            except Exception:
                results[etf] = 0
    except Exception:
        pass
    st.session_state[key] = results
    return results

def get_stock_sector_etf(ticker):
    """Map a stock to its sector ETF using yfinance info."""
    cache_key = f"sector_{ticker}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "")
        # Map yfinance sector string to ETF
        mapping = {
            "Technology":             "XLK",
            "Healthcare":             "XLV",
            "Financial Services":     "XLF",
            "Energy":                 "XLE",
            "Basic Materials":        "XLB",
            "Industrials":            "XLI",
            "Communication Services": "XLC",
            "Consumer Cyclical":      "XLY",
            "Consumer Defensive":     "XLP",
            "Utilities":              "XLU",
            "Real Estate":            "XLRE",
        }
        etf = mapping.get(sector, None)
        st.session_state[cache_key] = (etf, sector)
        return (etf, sector)
    except Exception:
        return (None, "")

def score_sector(ticker, sector_returns):
    """
    Return (bonus_pts, sector_name, relative_return).
    +10 pts if sector >+15% vs SPY over 26W
    +5  pts if sector +5% to +15%
     0  pts if sector -5% to +5%
    -5  pts if sector underperforming
    """
    etf, sector_name = get_stock_sector_etf(ticker)
    if etf is None or etf not in sector_returns:
        return 0, sector_name or "Unknown", None
    rel = sector_returns[etf]
    if rel >= 15:
        pts = 10
    elif rel >= 5:
        pts = 5
    elif rel >= -5:
        pts = 0
    else:
        pts = -5
    return pts, sector_name, rel

def get_yf_data(ticker, period="5y", freq="1wk"):
    """
    Fetch OHLCV from yfinance with in-memory caching.
    freq: "1wk" for weekly, "1d" for daily
    Returns a DataFrame with columns: open, high, low, close, volume (lowercase)
    """
    cache_key = f"{ticker}_{freq}"
    if cache_key in _yf_cache:
        return _yf_cache[cache_key]
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=freq, auto_adjust=True)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        # Normalise column names to lowercase
        df.columns = [c.lower() for c in df.columns]
        # Rename Date/Datetime → date
        if "datetime" in df.columns:
            df = df.rename(columns={"datetime": "date"})
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df.sort_values("date").reset_index(drop=True)
        _yf_cache[cache_key] = df
        return df
    except Exception:
        return None

def calc_sma(series, period):
    return series.rolling(window=period, min_periods=period).mean()

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_atr_pct(df, period=14):
    high  = df["high"]
    low   = df["low"]
    close = df["close"]
    prev  = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return (tr.rolling(period).mean() / close * 100).iloc[-1]

def check_weekly(df_w, w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult):
    res = {}
    if len(df_w) < 52:
        return False, {"error": "short"}
    closes = df_w["close"]; vols = df_w["volume"]

    sma200_series = calc_sma(closes, min(200, len(closes) - 1))
    sma200 = sma200_series.iloc[-1]
    cur    = closes.iloc[-1]

    # ── ATH: full history ending 8 weeks ago ─────────────────────────────────
    # Uses ALL available history (not just 4yr) so long-cycle stocks like LITE
    # (IPO 2013, ATH $391 in 2021) get their real ATH captured.
    # Ends 8 weeks ago to avoid counting the current rally as the ATH.
    win_end   = max(0, len(closes) - 8)
    ath_w     = closes.iloc[:win_end]
    ath       = ath_w.max() if len(ath_w) > 0 else closes.iloc[0]
    atl       = ath_w.min() if len(ath_w) > 0 else closes.iloc[0]

    dist = (cur - sma200) / sma200 * 100
    run  = (ath - atl) / atl * 100  if atl > 0 else 0
    corr = (ath - cur) / ath * 100  if ath > cur else 0  # 0 if price > ATH (breakout)

    # ── Volume: best of 4W rolling OR peak single week in last 12W ────────────
    # Catches both sustained accumulation AND a single explosive volume week.
    avg_vol_20w = vols.rolling(20).mean().iloc[-1]
    avg_vol_4w  = vols.rolling(4).mean().iloc[-1]
    peak_12w    = vols.iloc[-12:].max() if len(vols) >= 12 else vols.max()
    vr_rolling  = avg_vol_4w  / avg_vol_20w if avg_vol_20w > 0 else 0
    vr_peak     = peak_12w    / avg_vol_20w if avg_vol_20w > 0 else 0
    vr          = max(vr_rolling, vr_peak)

    slope = sma200_series.iloc[-1] - sma200_series.iloc[-5] if len(sma200_series) >= 5 else 0
    pass_dist = (-w_dist_200sma_lo <= dist <= w_dist_200sma_hi)

    res.update({
        "dist_200sma_pct":        round(dist, 2),
        "sma200":                 round(sma200, 2),
        "current_close":          round(cur, 2),
        "prior_run_pct":          round(run, 1),
        "correction_from_ath_pct":round(corr, 1),
        "vol_ratio":              round(vr, 2),
        "sma200_slope":           round(slope, 2),
        "pass_200sma_proximity":  pass_dist,
        "pass_prior_run":         run >= w_prior_run,
        "pass_correction":        corr >= w_correction,
        "pass_volume_surge":      vr >= w_vol_mult,
        "pass_sma200_slope":      slope >= 0,
    })
    passed = all([res["pass_200sma_proximity"], res["pass_prior_run"],
                  res["pass_correction"], res["pass_volume_surge"]])
    return passed, res

def check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma):
    res = {}
    if len(df_d) < 55:
        return False, {"error": "short"}
    closes = df_d["close"]; cur = closes.iloc[-1]
    sma50  = calc_sma(closes, 50).iloc[-1]
    ema10  = calc_ema(closes, 10).iloc[-1]
    ema20  = calc_ema(closes, 20).iloc[-1]
    atr    = calc_atr_pct(df_d)
    p50    = (cur - sma50) / sma50 * 100
    ema_sp = (ema10 - ema20) / ema20 * 100
    hi = df_d["high"].iloc[-1]
    lo = df_d["low"].iloc[-1]
    rng_pos = (cur - lo) / (hi - lo) if hi != lo else 0.5
    res.update({"atr_pct": round(atr,2), "pct_above_50sma": round(p50,2),
                "ema10_vs_ema20_pct": round(ema_sp,2), "candle_range_position": round(rng_pos,2),
                "pass_atr": d_atr_pct_min <= atr <= d_atr_pct_max,
                "pass_50sma": -40 <= p50 <= d_above_50sma,  # allow up to 40% below 50D (deep corrections)
                "pass_ema_cross": ema_sp > -5,
                "pass_candle_position": rng_pos >= 0.4})
    return res["pass_atr"] and res["pass_50sma"], res

def check_recovery_structure(df_w):
    """
    Detects which recovery structure (if any) is present after the bottom.
    Returns a dict with:
      - structure:    "ma_stack" | "bounce_ema" | "first_pullback" | "none"
      - structure_pts: 0–15 (bonus points)
      - structure_label: human-readable label for the badge
      - sub-fields for the card metric strip
    
    Three patterns detected:
    
    1. MA STACK — EMAs aligned in bull order above 200W SMA
       10W EMA > 20W EMA > 50W SMA, all above 200W SMA
       Full stack = 15pts, partial (2 of 3 in order) = 8pts
    
    2. BOUNCE OFF RISING EMA — price pulling back to rising 10W/20W EMA
       Price within 5% below the EMA, EMA slope positive over 8W,
       price higher than 12 weeks ago (uptrend intact)
       = 10pts
    
    3. FIRST PULLBACK — ran to local high, now consolidating or pulling back
       Local high 4–16W ago was 10%+ above current price,
       price near 20W or 50W EMA (within 8%),
       weekly ATR contracting (last 4W avg ATR < prior 8W avg ATR)
       = 10pts
    """
    res = {
        "structure": "none",
        "structure_pts": 0,
        "structure_label": "No structure",
        "ma_stack_full": False,
        "ma_stack_partial": False,
        "bounce_ema": False,
        "first_pullback": False,
        "ema10w": None,
        "ema20w": None,
        "sma50w": None,
        "local_high_pct": None,
        "atr_contracting": False,
    }

    if len(df_w) < 52:
        return res

    closes = df_w["close"]
    highs  = df_w["high"]
    lows   = df_w["low"]
    cur    = closes.iloc[-1]

    # ── Compute MAs ───────────────────────────────────────────────────────────
    ema10w_s = calc_ema(closes, 10)
    ema20w_s = calc_ema(closes, 20)
    sma50w_s = calc_sma(closes, min(50, len(closes)-1))
    sma200_s = calc_sma(closes, min(200, len(closes)-1))

    ema10w  = ema10w_s.iloc[-1]
    ema20w  = ema20w_s.iloc[-1]
    sma50w  = sma50w_s.iloc[-1]
    sma200  = sma200_s.iloc[-1]

    res["ema10w"] = round(ema10w, 2)
    res["ema20w"] = round(ema20w, 2)
    res["sma50w"] = round(sma50w, 2)

    # ── Structure 1: MA Stack ─────────────────────────────────────────────────
    above_200  = sma50w > sma200   # 50W above 200W — base requirement
    ema_stack  = ema10w > ema20w   # 10W EMA above 20W EMA
    sma_stack  = ema20w > sma50w   # 20W EMA above 50W SMA
    price_top  = cur > ema10w      # price leading the stack

    stack_score = sum([above_200, ema_stack, sma_stack, price_top])
    full_stack    = stack_score >= 4
    partial_stack = stack_score == 3

    res["ma_stack_full"]    = full_stack
    res["ma_stack_partial"] = partial_stack

    if full_stack:
        res["structure"]     = "ma_stack"
        res["structure_pts"] = 15
        res["structure_label"] = "MA Stack"
        return res
    if partial_stack:
        res["structure"]     = "ma_stack"
        res["structure_pts"] = 8
        res["structure_label"] = "Partial Stack"
        # Don't return — still check other structures to label correctly

    # ── Structure 2: Bounce off rising EMA ───────────────────────────────────
    # Price pulling back to 10W or 20W EMA with positive slope
    dist_ema10 = (cur - ema10w) / ema10w * 100  # negative = below EMA
    dist_ema20 = (cur - ema20w) / ema20w * 100

    # EMA slopes: positive over last 8 weeks
    ema10_slope = ema10w_s.iloc[-1] - ema10w_s.iloc[-8] if len(ema10w_s) >= 8 else 0
    ema20_slope = ema20w_s.iloc[-1] - ema20w_s.iloc[-8] if len(ema20w_s) >= 8 else 0

    # Price trend: higher than 12 weeks ago
    price_12w_ago   = closes.iloc[-12] if len(closes) >= 12 else closes.iloc[0]
    uptrend_intact  = cur > price_12w_ago

    touching_ema10 = -5.0 <= dist_ema10 <= 2.0 and ema10_slope > 0
    touching_ema20 = -5.0 <= dist_ema20 <= 2.0 and ema20_slope > 0

    if (touching_ema10 or touching_ema20) and uptrend_intact and res["structure_pts"] == 0:
        res["structure"]      = "bounce_ema"
        res["structure_pts"]  = 10
        res["structure_label"]= "EMA Bounce"
        res["bounce_ema"]     = True

    # ── Structure 3: First Pullback ───────────────────────────────────────────
    # Local high 4–16W ago was 10%+ above current; price near 20W/50W EMA;
    # ATR contracting (last 4W < prior 8W)
    lookback = min(16, len(closes) - 1)
    local_high = closes.iloc[-lookback:-1].max() if lookback > 1 else cur
    local_high_pct = (local_high - cur) / cur * 100 if cur > 0 else 0

    dist_to_ema20 = abs((cur - ema20w) / ema20w * 100)
    dist_to_sma50 = abs((cur - sma50w) / sma50w * 100)
    near_ma = dist_to_ema20 <= 8 or dist_to_sma50 <= 8

    # ATR contraction: compare last 4W vs prior 8W
    if len(highs) >= 12:
        tr_series = pd.concat([
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows  - closes.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr_4w  = tr_series.iloc[-4:].mean()
        atr_8w  = tr_series.iloc[-12:-4].mean()
        atr_contracting = atr_4w < atr_8w * 0.85  # 15% contraction
    else:
        atr_contracting = False

    res["local_high_pct"]  = round(local_high_pct, 1)
    res["atr_contracting"] = atr_contracting

    if local_high_pct >= 10 and near_ma and res["structure_pts"] == 0:
        res["structure"]      = "first_pullback"
        res["structure_pts"]  = 10 if atr_contracting else 7
        res["structure_label"]= "First Pullback" + (" + Compression" if atr_contracting else "")
        res["first_pullback"] = True

    return res

def check_base_breakout(df_w, bb_base_years, bb_range_pct, bb_atr_max,
                         bb_vol_mult, bb_sma_lo, bb_sma_hi):
    """
    Base Breakout Mode criteria:
    - Multi-year tight sideways consolidation (low ATR, narrow range)
    - Price near / breaking above 200W SMA
    - Volume surge on breakout week
    - Long base duration
    """
    res = {}
    if len(df_w) < 52:
        return False, {"error": "short"}

    closes = df_w["close"]
    vols   = df_w["volume"]
    cur    = closes.iloc[-1]

    # 200W SMA (use available history)
    sma200_series = calc_sma(closes, min(200, len(closes) - 1))
    sma200 = sma200_series.iloc[-1]
    dist   = (cur - sma200) / sma200 * 100

    # Base window = last bb_base_years * 52 weeks
    base_weeks = int(bb_base_years * 52)
    base_window = closes.iloc[-(base_weeks + 1):-1] if len(closes) > base_weeks else closes.iloc[:-1]

    if len(base_window) < 26:
        return False, {"error": "insufficient base history"}

    base_high = base_window.max()
    base_low  = base_window.min()
    base_range_pct = (base_high - base_low) / base_low * 100 if base_low > 0 else 999

    # Weekly ATR% during base (avg ATR over base window)
    if len(df_w) >= base_weeks + 1:
        base_df = df_w.iloc[-(base_weeks + 1):-1].copy()
    else:
        base_df = df_w.iloc[:-1].copy()
    base_atr = calc_atr_pct(base_df) if len(base_df) >= 14 else 999

    # Volume surge — current 4W avg vs 20W avg
    avg_vol_4w  = vols.rolling(4).mean().iloc[-1]
    avg_vol_20w = vols.rolling(20).mean().iloc[-1]
    vr = avg_vol_4w / avg_vol_20w if avg_vol_20w > 0 else 0

    # Base duration — how many consecutive weeks price stayed within base range
    # Count weeks from end going backwards where close stayed within base_low*0.9 to base_high*1.1
    duration_weeks = 0
    for i in range(len(closes) - 2, max(0, len(closes) - base_weeks * 2) - 1, -1):
        if base_low * 0.85 <= closes.iloc[i] <= base_high * 1.15:
            duration_weeks += 1
        else:
            break
    duration_years = round(duration_weeks / 52, 1)

    slope = sma200_series.iloc[-1] - sma200_series.iloc[-5] if len(sma200_series) >= 5 else 0

    pass_sma      = (-bb_sma_lo <= dist <= bb_sma_hi)
    pass_range    = base_range_pct <= bb_range_pct
    pass_atr_base = base_atr <= bb_atr_max
    pass_vol      = vr >= bb_vol_mult
    pass_duration = duration_weeks >= (bb_base_years * 52 * 0.5)  # at least half the target duration

    res.update({
        "dist_200sma_pct":    round(dist, 2),
        "sma200":             round(sma200, 2),
        "current_close":      round(cur, 2),
        "base_range_pct":     round(base_range_pct, 1),
        "base_atr_pct":       round(base_atr, 2),
        "base_duration_yrs":  duration_years,
        "vol_ratio":          round(vr, 2),
        "sma200_slope":       round(slope, 2),
        "pass_200sma_proximity": pass_sma,
        "pass_base_range":    pass_range,
        "pass_base_atr":      pass_atr_base,
        "pass_volume_surge":  pass_vol,
        "pass_base_duration": pass_duration,
        "pass_sma200_slope":  slope >= -0.05,
        # Compat fields for shared badge renderer
        "pass_prior_run":     True,
        "correction_from_ath_pct": 0,
        "prior_run_pct":      0,
    })
    passed = all([pass_sma, pass_range, pass_atr_base, pass_vol, pass_duration])
    return passed, res

def score_base_breakout(br, dr):
    pts = 0
    if br.get("pass_200sma_proximity"): pts += 25
    if br.get("pass_base_range"):       pts += 20
    if br.get("pass_base_atr"):         pts += 20
    if br.get("pass_volume_surge"):     pts += 20
    if br.get("pass_base_duration"):    pts += 10
    if br.get("pass_sma200_slope"):     pts += 5
    if dr.get("pass_atr"):              pts += 5
    if dr.get("pass_50sma"):            pts += 5
    if dr.get("pass_ema_cross"):        pts += 3
    if dr.get("pass_candle_position"):  pts += 2
    return pts

def score_setup(wr, dr):
    """
    Proportional scoring — rewards extremity, not just binary pass/fail.
    Total: 100 points possible.

    Prior run  (25pts): scales from 0 at 100% run to 25 at 1000%+
    Correction (20pts): scales from 0 at 30% to 20 at 80%+
    Volume     (20pts): scales from 0 at 1x to 20 at 3x+
    200W SMA   (15pts): 15 if within window, partial credit for close misses
    SMA slope  ( 5pts): binary — rising 200W SMA
    Daily ATR  ( 5pts): binary — in range
    50D SMA    ( 5pts): binary — not too extended
    EMA cross  ( 3pts): binary — EMA10 > EMA20
    Candle pos ( 2pts): binary — closing in upper half of range
    """
    pts = 0

    # Prior run — proportional 0–25pts (scales up to 1000%)
    run = wr.get("prior_run_pct", 0)
    pts += min(25, max(0, (run - 100) / 900 * 25))

    # Correction — proportional 0–20pts (20% = 0pts, 80% = 20pts)
    corr = wr.get("correction_from_ath_pct", 0)
    pts += min(20, max(0, (corr - 20) / 60 * 20))

    # Volume surge — proportional 0–20pts (1x = 0pts, 3x+ = 20pts)
    vr = wr.get("vol_ratio", 0)
    pts += min(20, max(0, (vr - 1.0) / 2.0 * 20))

    # 200W SMA proximity — 15pts if inside window, 5pts if within 10% outside
    dist = wr.get("dist_200sma_pct", 999)
    if wr.get("pass_200sma_proximity"):
        pts += 15
    elif abs(dist) <= 10:
        pts += 5  # partial credit for near misses

    # Binary criteria
    if wr.get("pass_sma200_slope"):     pts += 5
    if dr.get("pass_atr"):              pts += 5
    if dr.get("pass_50sma"):            pts += 5
    if dr.get("pass_ema_cross"):        pts += 3
    if dr.get("pass_candle_position"):  pts += 2

    return round(pts)

# ── Backtest Helpers ─────────────────────────────────────────────────────────

# Known historic setups for validation
KNOWN_SETUPS = [
    {
        "ticker": "TPL",
        "date": "2026-02-03",
        "label": "Texas Pacific Land — Feb 2026",
        "desc": "Retested rising 200W SMA at ~$335 after 70% correction from $1,200 ATH. "
                "Volume surge 3.9× average. Ran from $270 to $589 in 6 weeks.",
        "expected_score": 90,
    },
    {
        "ticker": "NVDA",
        "date": "2023-01-09",
        "label": "NVIDIA — Jan 2023",
        "desc": "Retested 200W SMA after ~65% correction from $346 ATH during 2022 bear. "
                "Setup preceded massive AI-driven run to $974.",
        "expected_score": 75,
    },
    {
        "ticker": "META",
        "date": "2022-11-07",
        "label": "Meta Platforms — Nov 2022",
        "desc": "Down 77% from ATH, retesting long-term support. Massive prior run 2012–2021. "
                "Recovered from $88 low to over $500.",
        "expected_score": 75,
    },
    {
        "ticker": "TSLA",
        "date": "2023-01-09",
        "label": "Tesla — Jan 2023",
        "desc": "80% correction from $414 ATH to ~$101 low, testing major long-term support. "
                "Prior run of 1,500%+ from 2019 base.",
        "expected_score": 70,
    },
    {
        "ticker": "FCX",
        "date": "2023-10-02",
        "label": "Freeport-McMoRan — Oct 2023",
        "desc": "Copper producer retesting 200W SMA after 45% pullback from cycle highs. "
                "Classic commodity big-run-then-correct setup.",
        "expected_score": 70,
    },
    {
        "ticker": "ENPH",
        "date": "2023-10-30",
        "label": "Enphase Energy — Oct 2023",
        "desc": "Solar sector selloff — 80% correction from ATH, 200W SMA retest. "
                "Prior run of 4,000%+ from 2019 base.",
        "expected_score": 80,
    },
    {
        "ticker": "PYPL",
        "date": "2023-01-09",
        "label": "PayPal — Jan 2023",
        "desc": "Down 80% from ATH of $310. Long-term 200W SMA support test. "
                "Massive prior run from 2017 base.",
        "expected_score": 65,
    },
    {
        "ticker": "LITE",
        "date": "2025-07-07",
        "label": "Lumentum Holdings — Jul 2025",
        "desc": "91% correction from $391 ATH down to $35 low. Price sitting ~20-25% "
                "below rising 200W SMA (~$67). Prior run 1,460%+. Volume surge visible "
                "on weekly as institutions accumulated. Ran from $51 to $391 in months.",
        "expected_score": 70,
    },
    {
        "ticker": "LITE",
        "date": "2025-08-04",
        "label": "Lumentum Holdings — Aug 2025 (breakout week)",
        "desc": "Week price crossed back above 200W SMA with massive volume surge. "
                "Classic retest-then-breakout confirmation. ATR% elevated showing "
                "volatility expansion at the start of the move.",
        "expected_score": 75,
        "mode": "retest",
    },
    {
        "ticker": "KGC",
        "date": "2024-10-07",
        "label": "Kinross Gold — Oct 2024 (base breakout)",
        "desc": "Multi-year sideways base from 2022–2024 between $3.50–$8.00. "
                "Gold sector tailwind from macro. Volume surge as price broke above "
                "200W SMA (~$5.50). Ran from ~$8 to $35+ by Feb 2026.",
        "expected_score": 70,
        "mode": "base_breakout",
    },
    {
        "ticker": "KGC",
        "date": "2024-12-30",
        "label": "Kinross Gold — Dec 2024 (mid breakout)",
        "desc": "Price already above 200W SMA, base breakout confirmed. "
                "Still early in the move — $9.78 with 200W SMA at $5.93.",
        "expected_score": 65,
        "mode": "base_breakout",
    },
]

def get_yf_data_asof(ticker, as_of_date, lookback_years=6, freq="1wk"):
    """
    Fetch historical data and truncate to simulate scanning on a past date.
    Returns only data available up to as_of_date.
    """
    try:
        start = (as_of_date - timedelta(days=365 * lookback_years)).strftime("%Y-%m-%d")
        end   = (as_of_date + timedelta(days=7)).strftime("%Y-%m-%d")
        tk = yf.Ticker(ticker)
        df = tk.history(start=start, end=end, interval=freq, auto_adjust=True)
        if df is None or df.empty:
            return None
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        if "datetime" in df.columns:
            df = df.rename(columns={"datetime": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        # Truncate to as_of_date
        df = df[df["date"] <= pd.Timestamp(as_of_date)].sort_values("date").reset_index(drop=True)
        return df if len(df) > 0 else None
    except Exception:
        return None

def run_single_backtest(ticker, as_of_date, w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction,
                         w_vol_mult, d_atr_pct_min, d_atr_pct_max, d_above_50sma,
                         mode="retest",
                         bb_base_years=2, bb_range_pct=60, bb_atr_max=4.0,
                         bb_vol_mult=2.0, bb_sma_lo=10, bb_sma_hi=40):
    """Run scanner criteria on a single ticker as of a specific past date."""
    df_w = get_yf_data_asof(ticker, as_of_date, lookback_years=6, freq="1wk")
    df_d = get_yf_data_asof(ticker, as_of_date, lookback_years=2, freq="1d")

    if df_w is None or len(df_w) < 52:
        return None, None, None, "Insufficient weekly history"
    if df_d is None or len(df_d) < 55:
        return None, None, None, "Insufficient daily history"

    d_pass, dr = check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma)

    if mode == "retest":
        w_pass, wr = check_weekly(df_w, w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult)
        sc = score_setup(wr, dr)
    else:
        w_pass, wr = check_base_breakout(df_w, bb_base_years, bb_range_pct,
                                          bb_atr_max, bb_vol_mult, bb_sma_lo, bb_sma_hi)
        sc = score_base_breakout(wr, dr)
    return w_pass, d_pass, sc, wr, dr

# ── Forward Return Helper ────────────────────────────────────────────────────
def get_forward_return(ticker, as_of_date, weeks):
    """
    Fetch the closing price N weeks after as_of_date and compute % return.
    Returns (fwd_price, fwd_return_pct) or (None, None) if data unavailable.
    """
    try:
        start = as_of_date.strftime("%Y-%m-%d")
        end   = (as_of_date + timedelta(days=weeks * 7 + 14)).strftime("%Y-%m-%d")
        tk    = yf.Ticker(ticker)
        df    = tk.history(start=start, end=end, interval="1wk", auto_adjust=True)
        if df is None or len(df) < 2:
            return None, None
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        if "datetime" in df.columns:
            df = df.rename(columns={"datetime": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        # Entry = first available close on or after as_of_date
        entry_row = df.iloc[0]
        entry_price = entry_row["close"]
        # Target = closest row to N weeks forward
        target_date = as_of_date + timedelta(weeks=weeks)
        df["dist"] = (df["date"] - target_date).abs()
        fwd_row   = df.loc[df["dist"].idxmin()]
        fwd_price = fwd_row["close"]
        fwd_ret   = (fwd_price - entry_price) / entry_price * 100
        return round(fwd_price, 2), round(fwd_ret, 2)
    except Exception:
        return None, None

# ── Global UI Helper ─────────────────────────────────────────────────────────
def badge(ok, label):
    cls = "badge-green" if ok else "badge-red"
    return f'<span class="badge {cls}">{"✓" if ok else "✗"} {label}</span>'

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🔍  Step 1 — TradingView Pre-Filter", "🚀  Step 2 — Run Scanner", "🕰  Backtest & Validate"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TRADINGVIEW PRE-FILTER
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── Why bother? ───────────────────────────────────────────────────────────
    loaded_count = len(st.session_state.get("finviz_tickers", []))
    status_color = "var(--green)" if loaded_count > 0 else "var(--text-muted)"
    status_text  = f"{loaded_count} tickers ready" if loaded_count > 0 else "No universe loaded — scanner will use S&P 500"

    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.2rem">' +
        f'<div>' +
        f'<div style="font-size:1.05rem;font-weight:700;color:var(--text-primary)">Universe Builder</div>' +
        f'<div style="font-family:DM Mono,monospace;font-size:0.68rem;color:var(--text-muted);margin-top:0.2rem">' +
        f'Optional — but highly recommended for speed and signal quality' +
        f'</div></div>' +
        f'<div style="font-family:DM Mono,monospace;font-size:0.72rem;color:{status_color};background:var(--bg-raised);' +
        f'border:1px solid var(--border);border-radius:8px;padding:0.4rem 0.9rem">{status_text}</div>' +
        f'</div>',
        unsafe_allow_html=True)

    # Why it matters callout
    st.markdown('''
    <div class="info-box">
    <b style="color:var(--accent)">Why not just scan the S&P 500?</b><br>
    The S&P 500 is 505 large-caps — slow to scan (~20 min) and the wrong pool.
    The best retest setups live in mid-caps that ran 500%+, corrected 60%+, and are now ignored.
    Most of those aren't in the S&P 500.<br><br>
    This pre-filter hits TradingView's screener in seconds and returns 200–400 stocks
    already showing meaningful corrections — so the scanner spends its time on stocks
    that actually have a chance of passing. <b style="color:var(--accent)">Sector momentum
    scoring happens automatically inside the scanner</b>, so no need to filter by sector here.
    </div>
    ''', unsafe_allow_html=True)

    # ── Two columns: filters + fetch ──────────────────────────────────────────
    col_l, col_r = st.columns([1, 1], gap="large")

    with col_l:
        st.markdown('<div class="section-header">Filters</div>', unsafe_allow_html=True)

        min_mcap = st.select_slider("Market cap min ($B)",
            options=[0.5, 1, 2, 5, 10, 20], value=1,
            help="$1–5B mid-caps are the sweet spot for big-run setups")

        max_mcap_options = {"No limit": None, "$5B": 5, "$10B": 10, "$50B": 50}
        max_mcap_label   = st.selectbox("Market cap max", list(max_mcap_options.keys()), index=0)
        max_mcap         = max_mcap_options[max_mcap_label]

        min_vol_k = st.select_slider("Min avg daily volume",
            options=[100_000, 200_000, 300_000, 500_000, 1_000_000],
            format_func=lambda x: f"{x:,.0f}",
            value=200_000)

        exchanges = st.multiselect("Exchanges", ["NYSE", "NASDAQ", "AMEX"],
            default=["NYSE", "NASDAQ"])

    with col_r:
        st.markdown('<div class="section-header">Correction Depth</div>', unsafe_allow_html=True)
        st.caption("1-year performance acts as a correction proxy")

        perf_presets = {
            "Mild       −15% to −30%":    (-30,  -15),
            "Moderate   −30% to −60%  ✦": (-60,  -30),
            "Deep       −60% to −80%":    (-80,  -60),
            "Extreme    −80%+":           (-99,  -80),
            "Custom":                      None,
        }
        perf_choice = st.radio("Preset", list(perf_presets.keys()), index=1,
            help="Moderate catches most retest setups — deep/extreme for bear market bottoms")
        if perf_presets[perf_choice] is None:
            c1, c2 = st.columns(2)
            perf_min = c1.number_input("Min 1Y perf %", value=-80, min_value=-100, max_value=0)
            perf_max = c2.number_input("Max 1Y perf %", value=-15, min_value=-100, max_value=0)
        else:
            perf_min, perf_max = perf_presets[perf_choice]

        max_tv_results = st.slider("Max tickers to fetch", 100, 1000, 500, step=50)

    # ── Fetch ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header"></div>', unsafe_allow_html=True)
    fetch_col, paste_col = st.columns([1, 1], gap="large")

    with fetch_col:
        st.markdown('<div style="font-weight:600;font-size:0.85rem;margin-bottom:0.5rem">Auto-fetch from TradingView</div>', unsafe_allow_html=True)
        fetch_btn = st.button("⬇  Fetch Universe", use_container_width=True)

        if fetch_btn:
            with st.spinner("Querying TradingView screener..."):
                found, err = fetch_tradingview_tickers(
                    min_market_cap_b=float(min_mcap),
                    max_market_cap_b=float(max_mcap) if max_mcap else None,
                    min_avg_vol=min_vol_k,
                    perf_1y_min=float(perf_min),
                    perf_1y_max=float(perf_max),
                    sectors=None,
                    exchanges=tuple(exchanges),
                    max_results=max_tv_results,
                )
            if err:
                st.error(f"TradingView error: {err}")
            elif found:
                st.session_state["finviz_tickers"] = found
                st.success(f"✅ {len(found)} tickers loaded — go to Scanner tab")
                pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in found[:80]])
                st.markdown(f'<div style="margin-top:0.6rem;line-height:2">{pills}{"&nbsp;…" if len(found) > 80 else ""}</div>',
                    unsafe_allow_html=True)
            else:
                st.warning("No tickers matched. Try broadening your filters.")

    with paste_col:
        st.markdown('<div style="font-weight:600;font-size:0.85rem;margin-bottom:0.5rem">Or paste manually</div>', unsafe_allow_html=True)
        st.caption("From TradingView screener export, Finviz, or any watchlist")
        manual_paste = st.text_area("Tickers (comma, space, or newline separated)",
            height=120, placeholder="AAPL, NVDA, TPL, TSLA\nor one per line...",
            label_visibility="collapsed")
        if st.button("✓ Load Pasted Tickers", use_container_width=True):
            raw   = re.split(r"[\s,;]+", manual_paste.strip())
            clean = [t.upper() for t in raw if re.match(r"^[A-Z]{1,5}$", t.upper())]
            if clean:
                st.session_state["finviz_tickers"] = clean
                st.success(f"✅ {len(clean)} tickers loaded — go to Scanner tab")
            else:
                st.error("No valid tickers found.")

    # ── Loaded state ──────────────────────────────────────────────────────────
    if "finviz_tickers" in st.session_state:
        loaded = st.session_state["finviz_tickers"]
        st.markdown('<div class="section-header"></div>', unsafe_allow_html=True)
        lcol1, lcol2, lcol3 = st.columns([2, 1, 1])
        lcol1.markdown(
            f'<div style="font-family:DM Mono,monospace;font-size:0.72rem;color:var(--text-muted);padding-top:0.5rem">' +
            f'<b style="color:var(--green)">{len(loaded)}</b> tickers ready to scan</div>',
            unsafe_allow_html=True)
        lcol2.download_button("⬇ Download CSV", ",".join(loaded), "universe.csv", "text/csv",
            use_container_width=True)
        if lcol3.button("🗑 Clear", use_container_width=True):
            del st.session_state["finviz_tickers"]
            st.rerun()
        pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in loaded[:150]])
        st.markdown(f'<div style="margin-top:0.6rem;line-height:2">{pills}{"&nbsp;…" if len(loaded) > 150 else ""}</div>',
            unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:

    # Resolve universe
    if universe_choice == "TradingView Pre-Filter (recommended)":
        scan_universe = st.session_state.get("finviz_tickers", [])
        if scan_universe:
            st.info(f"📋 {len(scan_universe)} tickers loaded from TradingView pre-filter. Adjust filters in the Pre-Filter tab if needed.")
        else:
            st.warning("No tickers loaded yet. Go to **Step 1 — TradingView Pre-Filter** first, or switch Universe in the sidebar.")
    elif universe_choice == "Custom Tickers":
        scan_universe = [t.strip().upper() for t in custom_tickers_input.split(",") if t.strip()]
    else:
        scan_universe = SP500_TICKERS

    scan_universe = scan_universe[:int(max_stocks)]

    if run_scan:
        # No API key needed for yfinance
        if not scan_universe:
            st.error("No tickers to scan.")
            st.stop()

        _yf_cache.clear()  # fresh cache each scan run

        st.markdown('<div class="section-header">Scan in Progress</div>', unsafe_allow_html=True)
        with st.spinner("Fetching sector momentum data..."):
            sector_returns = fetch_sector_returns(26)
            # Show sector heatmap
            if sector_returns:
                cols = st.columns(6)
                for i, (etf, rel) in enumerate(sector_returns.items()):
                    color = "var(--green)" if rel >= 5 else ("var(--red)" if rel <= -5 else "var(--text-muted)")
                    sign  = "+" if rel >= 0 else ""
                    cols[i % 6].markdown(
                        f'<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:0.4rem 0.6rem;text-align:center;margin-bottom:0.4rem">' +
                        f'<div style="font-family:DM Mono,monospace;font-size:0.62rem;color:var(--text-muted)">{etf}</div>' +
                        f'<div style="font-family:DM Mono,monospace;font-size:0.78rem;font-weight:700;color:{color}">{sign}{rel}%</div>' +
                        f'</div>',
                        unsafe_allow_html=True)
        pbar        = st.progress(0)
        status_txt  = st.empty()
        log_ph      = st.empty()

        c1, c2, c3     = st.columns(3)
        met_scanned    = c1.empty()
        met_hits       = c2.empty()
        met_skipped    = c3.empty()

        hits    = []
        logs    = []
        skipped = 0
        total   = len(scan_universe)

        for i, ticker in enumerate(scan_universe):
            pbar.progress((i + 1) / total)
            status_txt.markdown(
                f'<span style="font-family:Space Mono;font-size:0.75rem;color:#64748b;">Scanning {ticker} ({i+1}/{total})</span>',
                unsafe_allow_html=True)

            df_w = get_yf_data(ticker, period="5y", freq="1wk")
            if df_w is None or len(df_w) < 100:
                skipped += 1
                logs.append(f"⚠ {ticker} — no data")
                log_ph.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
                continue

            if is_retest:
                w_pass, wr = check_weekly(df_w, w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult)
            else:
                w_pass, wr = check_base_breakout(df_w, bb_base_years, bb_range_pct, bb_atr_max, bb_vol_mult, bb_sma_lo, bb_sma_hi)

            df_d = get_yf_data(ticker, period="1y", freq="1d")
            d_pass, dr = (False, {}) if (df_d is None or len(df_d) < 55) else check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma)

            sc = score_setup(wr, dr) if is_retest else score_base_breakout(wr, dr)

            # ── Recovery structure detection (Retest Mode only) ───────────────
            rr = check_recovery_structure(df_w) if is_retest else {
                "structure": "none", "structure_pts": 0, "structure_label": "N/A",
                "ema10w": None, "ema20w": None, "sma50w": None,
                "local_high_pct": None, "atr_contracting": False
            }
            sc = max(0, sc + rr["structure_pts"])

            # ── Sector momentum bonus ─────────────────────────────────────────
            sector_pts, sector_name, sector_rel = score_sector(ticker, sector_returns)
            sc = max(0, sc + sector_pts)

            # ── No hard gate — score everything, display above min_display ──
            if sc >= min_display:
                hits.append({"ticker": ticker, "score": sc, "wr": wr, "dr": dr,
                             "w_pass": w_pass, "d_pass": d_pass,
                             "sector": sector_name, "sector_rel": sector_rel,
                             "sector_pts": sector_pts, "rr": rr})
                flag = "✅" if (w_pass and d_pass) else ("◑" if w_pass else "○")
                logs.append(f"{flag} {ticker} — {sc}/100")
            else:
                logs.append(f"✗ {ticker} — {sc}/100")

            log_ph.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
            met_scanned.markdown(f'<div class="metric-card"><div class="label">Scanned</div><div class="value">{i+1}</div></div>', unsafe_allow_html=True)
            met_hits.markdown(f'<div class="metric-card"><div class="label">Hits</div><div class="value" style="color:#22c55e">{len(hits)}</div></div>', unsafe_allow_html=True)
            met_skipped.markdown(f'<div class="metric-card"><div class="label">Skipped</div><div class="value" style="color:#ef4444">{skipped}</div></div>', unsafe_allow_html=True)

        pbar.progress(1.0)
        status_txt.markdown('<span style="font-family:Space Mono;font-size:0.75rem;color:#22c55e;">✓ Scan complete</span>', unsafe_allow_html=True)

        mode_label = '🔄 Retest Mode' if is_retest else '📦 Base Breakout Mode'
        st.markdown(f'<div class="section-header">Results — {mode_label}</div>', unsafe_allow_html=True)

        if not hits:
            st.warning("No stocks passed. Try relaxing the criteria sliders in the sidebar.")
        else:
            hits_sorted = sorted(hits, key=lambda x: x["score"], reverse=True)

            # ── Categorise ────────────────────────────────────────────────────
            full_hits    = [h for h in hits_sorted if h["score"] >= 80]
            strong_hits  = [h for h in hits_sorted if 60 <= h["score"] < 80]
            watchlist    = [h for h in hits_sorted if h["score"] < 60]

            def tv_url(ticker):
                """TradingView weekly chart deep-link with key MAs pre-loaded."""
                return (f"https://www.tradingview.com/chart/?symbol={ticker}"
                        f"&interval=W"
                        f"&studies=MASimple%40tv-basicstudies,MAExp%40tv-basicstudies,MASimple%40tv-basicstudies"
                        f"&studyOverrides=%7B%22MA%20Simple.length%22%3A200%2C%22MA%20Exp.length%22%3A20%2C%22MA%20Simple.length%22%3A50%7D")

            def render_category(label, emoji, cat_class, group):
                if not group:
                    return
                st.markdown(
                    f'<div class="category-header {cat_class}">{emoji} {label} — {len(group)} stock{"s" if len(group)!=1 else ""}</div>',
                    unsafe_allow_html=True)
                for h in group:
                    wr = h["wr"]; dr = h["dr"]
                    partial_tag = " <span style='color:#64748b;font-size:0.62rem'>(weekly only)</span>" if h.get("partial") else ""
                    tv_link = tv_url(h["ticker"])
                    if is_retest:
                        badges = (
                            badge(wr.get("pass_200sma_proximity"), f"200W {wr.get('dist_200sma_pct',0):+.1f}%") +
                            badge(wr.get("pass_prior_run"),        f"Run {wr.get('prior_run_pct',0):.0f}%") +
                            badge(wr.get("pass_correction"),       f"Corr {wr.get('correction_from_ath_pct',0):.0f}%") +
                            badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                            badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                            badge(dr.get("pass_50sma"),            f"50D +{dr.get('pct_above_50sma',0):.1f}%")
                        )
                        def mi(label, val):
                            return f'<span class="metric-item"><b>{label}</b> {val}</span>'
                        detail = (
                            mi("200W SMA", f"${wr.get('sma200','—')}") +
                            mi("Dist", f"{wr.get('dist_200sma_pct','—')}%") +
                            mi("Run", f"{wr.get('prior_run_pct','—')}%") +
                            mi("Corr", f"{wr.get('correction_from_ath_pct','—')}%") +
                            mi("Vol", f"×{wr.get('vol_ratio','—')}") +
                            mi("ATR", f"{dr.get('atr_pct','—')}%") +
                            mi("50D", f"{dr.get('pct_above_50sma','—')}%")
                        )
                    else:
                        badges = (
                            badge(wr.get("pass_200sma_proximity"), f"200W {wr.get('dist_200sma_pct',0):+.1f}%") +
                            badge(wr.get("pass_base_range"),       f"Base range {wr.get('base_range_pct',0):.0f}%") +
                            badge(wr.get("pass_base_atr"),         f"Base ATR {wr.get('base_atr_pct',0):.1f}%") +
                            badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                            badge(wr.get("pass_base_duration"),    f"Base {wr.get('base_duration_yrs',0):.1f}yr") +
                            badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%")
                        )
                        detail = (
                            mi("200W SMA", f"${wr.get('sma200','—')}") +
                            mi("Dist", f"{wr.get('dist_200sma_pct','—')}%") +
                            mi("Base range", f"{wr.get('base_range_pct','—')}%") +
                            mi("Base ATR", f"{wr.get('base_atr_pct','—')}%") +
                            mi("Duration", f"{wr.get('base_duration_yrs','—')}yr") +
                            mi("Vol", f"×{wr.get('vol_ratio','—')}") +
                            mi("ATR", f"{dr.get('atr_pct','—')}%")
                        )

                    mode_tag   = "[RETEST]" if is_retest else "[BASE]"
                    mode_color = "var(--text-muted)" if is_retest else "var(--amber)"
                    card_class = "hit-card-full" if h["score"] >= 80 else ("hit-card-strong" if h["score"] >= 60 else "hit-card-watch")
                    price      = wr.get("current_close", "—")
                    score      = h["score"]
                    ticker     = h["ticker"]
                    sec_name   = h.get("sector", "")
                    sec_rel    = h.get("sector_rel")
                    sec_pts    = h.get("sector_pts", 0)
                    rr         = h.get("rr", {})

                    # ── Sector badge ──────────────────────────────────────────
                    if sec_rel is not None:
                        sec_color = "var(--green)" if sec_rel >= 5 else ("var(--red)" if sec_rel <= -5 else "var(--text-muted)")
                        sec_sign  = "+" if sec_rel >= 0 else ""
                        sec_bonus = f" ({sec_sign}{sec_pts:+d}pts)" if sec_pts != 0 else ""
                        sec_badge = f'<span style="font-family:DM Mono,monospace;font-size:0.6rem;color:{sec_color};background:var(--bg-raised);border:1px solid var(--border);border-radius:4px;padding:2px 7px">{sec_name} {sec_sign}{sec_rel}%{sec_bonus}</span>'
                    else:
                        sec_badge = ""

                    # ── Recovery structure badge ──────────────────────────────
                    struct      = rr.get("structure", "none")
                    struct_pts  = rr.get("structure_pts", 0)
                    struct_lbl  = rr.get("structure_label", "")
                    if struct == "none" or not is_retest:
                        struct_badge = ""
                    else:
                        s_color_map = {
                            "ma_stack":      ("var(--green)",  "🟢"),
                            "bounce_ema":    ("var(--blue)",   "🔵"),
                            "first_pullback":("var(--amber)",  "🟡"),
                        }
                        s_color, s_icon = s_color_map.get(struct, ("var(--text-muted)", "⚪"))
                        pts_tag = f" +{struct_pts}pts" if struct_pts else ""
                        struct_badge = (
                            f'<span style="font-family:DM Mono,monospace;font-size:0.6rem;' +
                            f'color:{s_color};background:var(--bg-raised);border:1px solid {s_color};' +
                            f'border-radius:4px;padding:2px 7px;margin-left:6px">' +
                            f'{s_icon} {struct_lbl}{pts_tag}</span>'
                        )

                    # ── EMA metrics for detail strip (retest only) ────────────
                    ema_detail = ""
                    if is_retest and rr.get("ema10w") is not None:
                        ema_detail = (
                            mi("10W EMA", f"${rr['ema10w']}") +
                            mi("20W EMA", f"${rr['ema20w']}") +
                            mi("50W SMA", f"${rr['sma50w']}") +
                            (mi("Pullback from hi", f"{rr['local_high_pct']}%") if rr.get("local_high_pct") is not None else "") +
                            (mi("ATR contracting", "yes") if rr.get("atr_contracting") else "")
                        )

                    html = (
                        f'<div class="hit-card {card_class}">' +
                        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.4rem">' +
                        f'<div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap">' +
                        f'<span class="ticker-label">{ticker}</span>' +
                        f'<span style="font-family:DM Mono,monospace;font-size:0.6rem;color:{mode_color}">{mode_tag}</span>' +
                        f'<a class="tv-btn" href="{tv_link}" target="_blank">📈 Chart</a>' +
                        f'</div>' +
                        f'<div style="display:flex;align-items:center;gap:0.75rem">' +
                        f'<span class="price-label">${price}</span>' +
                        f'<span class="score-chip">{score}/125</span>' +
                        f'</div></div>' +
                        f'<div style="margin-top:0.35rem;display:flex;flex-wrap:wrap;gap:0.4rem">{sec_badge}{struct_badge}</div>' +
                        f'<div style="margin-top:0.5rem">{badges}</div>' +
                        f'<div class="metric-strip" style="margin-top:0.4rem">{detail}{ema_detail}</div>' +
                        f'</div>'
                    )
                    st.markdown(html, unsafe_allow_html=True)

            render_category("Full Hit  ≥80",  "🟢", "cat-full",   full_hits)
            render_category("Strong  60–79",  "🟡", "cat-strong",  strong_hits)
            render_category("Watchlist  <60", "🔵", "cat-watch",   watchlist)

            # ── Export ────────────────────────────────────────────────────────
            st.markdown('<div class="section-header">Export Results</div>', unsafe_allow_html=True)
            rows = []
            for h in hits_sorted:
                score = h["score"]
                category = "Full Hit" if score >= 85 and not h.get("partial") else                            "Strong"   if score >= 65 and not h.get("partial") else "Watchlist"
                rows.append({
                    "Category":        category,
                    "Ticker":          h["ticker"],
                    "Score":           score,
                    "Close":           h["wr"].get("current_close"),
                    "200W SMA":        h["wr"].get("sma200"),
                    "Dist 200W SMA %": h["wr"].get("dist_200sma_pct"),
                    "Prior Run %":     h["wr"].get("prior_run_pct"),
                    "Correction %":    h["wr"].get("correction_from_ath_pct"),
                    "Vol Ratio":       h["wr"].get("vol_ratio"),
                    "ATR %":              h["dr"].get("atr_pct"),
                    "% Above 50D SMA":    h["dr"].get("pct_above_50sma"),
                    "Sector":             h.get("sector", ""),
                    "Sector vs SPY 26W":  h.get("sector_rel", ""),
                    "Sector Pts":         h.get("sector_pts", 0),
                    "Recovery Structure": h.get("rr", {}).get("structure_label", ""),
                    "Structure Pts":      h.get("rr", {}).get("structure_pts", 0),
                    "TradingView":        tv_url(h["ticker"]),
                })
            df_out = pd.DataFrame(rows)
            st.dataframe(df_out, use_container_width=True)
            st.download_button("⬇ Download Results CSV", df_out.to_csv(index=False), "scanner_results.csv", "text/csv")

    else:
        # Idle state
        if scan_universe:
            st.markdown(f"""
            <div style="background:#0f1a2e;border:1px solid #1e3a5f;border-radius:12px;padding:2.5rem;text-align:center;margin-top:1rem;">
                <div style="font-family:Space Mono,monospace;font-size:0.7rem;color:#64748b;margin-bottom:0.3rem;">READY TO SCAN</div>
                <div style="font-family:Syne,sans-serif;font-weight:800;font-size:2.5rem;color:#f59e0b">{len(scan_universe)}</div>
                <div style="font-family:Space Mono,monospace;font-size:0.75rem;color:#94a3b8;">tickers queued · mode: <b style="color:#f59e0b">{"🔴 Retest" if is_retest else "🟡 Base Breakout"}</b> · click <b>🚀 Run Scanner</b> in the sidebar</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="idle-card">
                <div class="idle-icon">⬅</div>
                <div class="idle-title">No tickers loaded</div>
                <div class="idle-sub">Go to <b>Step 1 — TradingView Pre-Filter</b> to build your<br>candidate list, then hit 🚀 Run Scanner.</div>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — BACKTEST & VALIDATE
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('''
    <div class="info-box">
    Validate the scanner against known historic setups, or scan any past date to see what the
    scanner would have flagged. Uses the same criteria and thresholds as the live scanner.
    <br><br>
    <b style="color:#f59e0b">Note:</b> Uses sidebar criteria sliders — adjust them to see how
    threshold changes affect which setups are caught.
    </div>
    ''', unsafe_allow_html=True)

    bt_tab_a, bt_tab_b, bt_tab_c = st.tabs(["📋  Known Setup Validator", "📅  Date Picker Scan", "📈  Forward Return Validator"])

    # ── SUB-TAB A: Known Setups ───────────────────────────────────────────────
    with bt_tab_a:
        st.markdown('<div class="section-header">Known Historic Setups — Would The Scanner Have Caught These?</div>',
                    unsafe_allow_html=True)

        st.markdown("""
        <div style="font-family:Space Mono,monospace;font-size:0.72rem;color:#64748b;margin-bottom:1rem">
        Each setup below is a confirmed big-run-then-correct that preceded a major move.
        The scanner checks if it would have flagged the stock at the ideal entry date.
        </div>
        """, unsafe_allow_html=True)

        # Show known setups list
        col_l, col_r = st.columns([2, 1])
        with col_l:
            selected_setups = st.multiselect(
                "Select setups to validate",
                options=[s["label"] for s in KNOWN_SETUPS],
                default=[s["label"] for s in KNOWN_SETUPS],
            )
        with col_r:
            run_validation = st.button("▶ Run Validation", key="run_val")

        # Show setup cards
        for s in KNOWN_SETUPS:
            tv_link = f"https://www.tradingview.com/chart/?symbol={s['ticker']}&interval=W"
            st.markdown(f"""
            <div class="known-setup-card">
                <span class="ks-ticker">{s['ticker']}</span>
                <span class="ks-date">@ {s['date']}</span>
                <a class="tv-btn" href="{tv_link}" target="_blank" style="margin-left:12px">📈 Chart ↗</a>
                <div class="ks-desc">{s['desc']}</div>
                <div style="margin-top:0.3rem;font-size:0.63rem;color:#475569">Expected score: ~{s['expected_score']}/100</div>
            </div>
            """, unsafe_allow_html=True)

        if run_validation:
            to_run = [s for s in KNOWN_SETUPS if s["label"] in selected_setups]
            st.markdown('<div class="section-header">Validation Results</div>', unsafe_allow_html=True)

            passed_count = 0
            for s in to_run:
                ticker    = s["ticker"]
                as_of     = datetime.strptime(s["date"], "%Y-%m-%d")
                with st.spinner(f"Testing {ticker} as of {s['date']}..."):
                    setup_mode = s.get("mode", "retest")
                    result = run_single_backtest(
                        ticker, as_of,
                        w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult,
                        d_atr_pct_min, d_atr_pct_max, d_above_50sma,
                        mode=setup_mode,
                        bb_base_years=bb_base_years, bb_range_pct=bb_range_pct,
                        bb_atr_max=bb_atr_max, bb_vol_mult=bb_vol_mult,
                        bb_sma_lo=bb_sma_lo, bb_sma_hi=bb_sma_hi,
                    )

                if result[0] is None:
                    err = result[-1]
                    st.markdown(f'''
                    <div class="bt-result-warn">
                        <span class="bt-ticker" style="color:#fcd34d">{ticker}</span>
                        <span class="bt-meta">⚠ Could not fetch data: {err}</span>
                    </div>''', unsafe_allow_html=True)
                    continue

                w_pass, d_pass, sc, wr, dr = result
                full_pass = sc >= 60   # caught = scored above display threshold
                if full_pass: passed_count += 1

                result_class = "bt-result-pass" if sc >= 70 else ("bt-result-warn" if sc >= 55 else "bt-result-fail")
                status_icon  = "✅ CAUGHT" if full_pass else ("◑ CLOSE" if sc >= 55 else "❌ MISSED")
                status_color = "#6ee7b7" if full_pass else ("#fcd34d" if w_pass else "#fca5a5")
                tv_link      = f"https://www.tradingview.com/chart/?symbol={ticker}&interval=W"

                badges = (
                    badge(wr.get("pass_200sma_proximity"), f"200W-SMA {wr.get('dist_200sma_pct',0):+.1f}%") +
                    badge(wr.get("pass_prior_run"),        f"Run {wr.get('prior_run_pct',0):.0f}%") +
                    badge(wr.get("pass_correction"),       f"Corr {wr.get('correction_from_ath_pct',0):.0f}%") +
                    badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                    badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                    badge(dr.get("pass_50sma"),            f"50D +{dr.get('pct_above_50sma',0):.1f}%")
                )

                delta = sc - s["expected_score"]
                delta_str = f"+{delta}" if delta >= 0 else str(delta)

                st.markdown(f"""
                <div class="{result_class}">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
                        <div>
                            <span class="bt-ticker" style="color:{status_color}">{ticker}</span>
                            <span class="bt-score">{s['label']} @ {s['date']}</span>
                        </div>
                        <div style="display:flex;gap:1rem;align-items:center">
                            <span style="font-family:Space Mono,monospace;font-size:0.75rem;color:{status_color};font-weight:700">{status_icon}</span>
                            <span style="font-family:Space Mono,monospace;font-size:0.72rem;color:#f59e0b">{sc}/100
                                <span style="color:#64748b;font-size:0.62rem">(expected ~{s['expected_score']} · delta {delta_str})</span>
                            </span>
                            <a class="tv-btn" href="{tv_link}" target="_blank">📈 Chart ↗</a>
                        </div>
                    </div>
                    <div style="margin-top:0.6rem">{badges}</div>
                    <div class="bt-meta">
                        200W SMA: ${wr.get('sma200','—')} &nbsp;|&nbsp;
                        Dist: {wr.get('dist_200sma_pct','—')}% &nbsp;|&nbsp;
                        Prior Run: {wr.get('prior_run_pct','—')}% &nbsp;|&nbsp;
                        Correction: {wr.get('correction_from_ath_pct','—')}% &nbsp;|&nbsp;
                        Vol ×{wr.get('vol_ratio','—')} &nbsp;|&nbsp;
                        ATR: {dr.get('atr_pct','—')}% &nbsp;|&nbsp;
                        50D dist: {dr.get('pct_above_50sma','—')}%
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Summary
            total = len(to_run)
            st.markdown(f"""
            <div style="background:#111827;border:1px solid #1e293b;border-radius:10px;padding:1rem 1.5rem;margin-top:1rem;
                        font-family:Space Mono,monospace;font-size:0.8rem;text-align:center">
                Scanner caught <b style="color:#f59e0b;font-size:1.2rem">{passed_count}/{total}</b> known setups
                with current thresholds.
                {"&nbsp; 🎯 Strong validation!" if passed_count/total >= 0.7 else
                 "&nbsp; ⚠ Consider relaxing criteria." if passed_count/total < 0.5 else
                 "&nbsp; ✓ Reasonable coverage."}
            </div>
            """, unsafe_allow_html=True)

    # ── SUB-TAB B: Date Picker ────────────────────────────────────────────────
    with bt_tab_b:
        st.markdown('<div class="section-header">Scan Any Past Date</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-family:Space Mono,monospace;font-size:0.72rem;color:#64748b;margin-bottom:1rem">
        Enter a date and a list of tickers. The scanner will evaluate each stock exactly as it
        would have looked on that date — using only data available at that time.
        </div>
        """, unsafe_allow_html=True)

        col_date, col_quick = st.columns([1, 2])
        with col_date:
            bt_date = st.date_input(
                "Scan as-of date",
                value=datetime(2026, 2, 3).date(),
                min_value=datetime(2015, 1, 1).date(),
                max_value=datetime.now().date(),
            )
        with col_quick:
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption("Quick dates from known setups:")
            quick_cols = st.columns(len(KNOWN_SETUPS))
            for i, s in enumerate(KNOWN_SETUPS):
                quick_cols[i].markdown(
                    f'<div style="font-family:Space Mono,monospace;font-size:0.6rem;color:#64748b">'
                    f'{s["ticker"]}<br><b style="color:#f59e0b">{s["date"]}</b></div>',
                    unsafe_allow_html=True)

        bt_tickers_input = st.text_area(
            "Tickers to test (comma or newline separated)",
            value="TPL, NVDA, META, TSLA, FCX, ENPH, PYPL",
            height=80,
        )

        bt_run = st.button("▶ Run Historical Scan", key="bt_run")

        if bt_run:
            raw_tickers = re.split(r"[\s,;]+", bt_tickers_input.strip())
            bt_tickers  = [t.upper() for t in raw_tickers if re.match(r"^[A-Z]{1,5}$", t.upper())]
            as_of       = datetime.combine(bt_date, datetime.min.time())

            st.markdown(f'<div class="section-header">Results — As of {bt_date.strftime("%B %d, %Y")}</div>',
                        unsafe_allow_html=True)

            bt_hits = []
            bt_pbar = st.progress(0)
            bt_status = st.empty()

            for i, ticker in enumerate(bt_tickers):
                bt_pbar.progress((i + 1) / len(bt_tickers))
                bt_status.markdown(
                    f'<span style="font-family:Space Mono;font-size:0.72rem;color:#64748b">Testing {ticker}...</span>',
                    unsafe_allow_html=True)

                bt_mode = "retest" if is_retest else "base"
                result = run_single_backtest(
                    ticker, as_of,
                    w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult,
                    d_atr_pct_min, d_atr_pct_max, d_above_50sma,
                    mode=bt_mode,
                    bb_base_years=bb_base_years, bb_range_pct=bb_range_pct,
                    bb_atr_max=bb_atr_max, bb_vol_mult=bb_vol_mult,
                    bb_sma_lo=bb_sma_lo, bb_sma_hi=bb_sma_hi,
                )
                if result[0] is None:
                    continue

                w_pass, d_pass, sc, wr, dr = result
                if sc >= 60:
                    bt_hits.append({"ticker": ticker, "score": sc, "w_pass": w_pass,
                                    "d_pass": d_pass, "wr": wr, "dr": dr})

            bt_pbar.progress(1.0)
            bt_status.empty()

            if not bt_hits:
                st.warning(f"No stocks scored 60+ on {bt_date}. Try different tickers or relax criteria.")
            else:
                for h in sorted(bt_hits, key=lambda x: x["score"], reverse=True):
                    wr = h["wr"]; dr = h["dr"]
                    full = h["w_pass"] and h["d_pass"]
                    rc   = "bt-result-pass" if full else ("bt-result-warn" if h["w_pass"] else "bt-result-fail")
                    sc_color = "#6ee7b7" if full else ("#fcd34d" if h["w_pass"] else "#fca5a5")
                    tv_link  = f"https://www.tradingview.com/chart/?symbol={h['ticker']}&interval=W"

                    if is_retest:
                        badges = (
                            badge(wr.get("pass_200sma_proximity"), f"200W-SMA {wr.get('dist_200sma_pct',0):+.1f}%") +
                            badge(wr.get("pass_prior_run"),        f"Run {wr.get('prior_run_pct',0):.0f}%") +
                            badge(wr.get("pass_correction"),       f"Corr {wr.get('correction_from_ath_pct',0):.0f}%") +
                            badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                            badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                            badge(dr.get("pass_50sma"),            f"50D +{dr.get('pct_above_50sma',0):.1f}%")
                        )
                    else:
                        badges = (
                            badge(wr.get("pass_200sma_proximity"), f"200W-SMA {wr.get('dist_200sma_pct',0):+.1f}%") +
                            badge(wr.get("pass_base_tightness"),   f"Base ATR {wr.get('base_atr_pct',0):.1f}%") +
                            badge(wr.get("pass_range_tightness"),  f"Range {wr.get('base_range_pct',0):.0f}%") +
                            badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                            badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                            badge(dr.get("pass_50sma"),            f"50D +{dr.get('pct_above_50sma',0):.1f}%")
                        )

                    st.markdown(f"""
                    <div class="{rc}">
                        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
                            <div>
                                <span class="bt-ticker" style="color:{sc_color}">{h['ticker']}</span>
                                <span class="bt-score">as of {bt_date}</span>
                            </div>
                            <div style="display:flex;gap:1rem;align-items:center">
                                <span style="font-family:Space Mono,monospace;font-size:0.72rem;color:#f59e0b;font-weight:700">{h['score']}/100</span>
                                <a class="tv-btn" href="{tv_link}" target="_blank">📈 Chart ↗</a>
                            </div>
                        </div>
                        <div style="margin-top:0.6rem">{badges}</div>
                        <div class="bt-meta">
                            200W SMA: ${wr.get('sma200','—')} &nbsp;|&nbsp;
                            Dist: {wr.get('dist_200sma_pct','—')}% &nbsp;|&nbsp;
                            Prior Run: {wr.get('prior_run_pct','—')}% &nbsp;|&nbsp;
                            Correction: {wr.get('correction_from_ath_pct','—')}% &nbsp;|&nbsp;
                            Vol ×{wr.get('vol_ratio','—')} &nbsp;|&nbsp;
                            ATR: {dr.get('atr_pct','—')}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # Replay hint
                st.markdown(f"""
                <div style="background:#111827;border:1px solid #1e293b;border-radius:8px;padding:0.8rem 1rem;
                            margin-top:1rem;font-family:Space Mono,monospace;font-size:0.7rem;color:#64748b">
                    💡 <b style="color:#94a3b8">Replay tip:</b> Step through weekly dates manually to watch
                    setups form — try the same tickers 4, 8, and 12 weeks earlier to see the signal building.
                </div>
                """, unsafe_allow_html=True)


    # ── SUB-TAB C: Forward Return Validator ──────────────────────────────────
    with bt_tab_c:
        st.markdown('<div class="section-header">Forward Return Validator — Did Signals Lead to Gains?</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div class="info-box">
        Pick a scan date and tickers. The app will:<br>
        1. Run the scanner criteria on each ticker <b>as of that date</b><br>
        2. For every stock that <b>passed</b>, fetch the actual return 4, 8, and 12 weeks later<br>
        3. Show precision (% of signals that were profitable) and avg return<br><br>
        <b style="color:#f59e0b">This is ground-truth validation</b> — no guessing, real price data only.
        </div>
        """, unsafe_allow_html=True)

        col_fv1, col_fv2 = st.columns([1, 2])
        with col_fv1:
            fv_date = st.date_input(
                "Scan date",
                value=datetime(2023, 1, 9).date(),
                min_value=datetime(2015, 1, 1).date(),
                max_value=(datetime.now() - timedelta(weeks=13)).date(),
                key="fv_date",
                help="Must be at least 12 weeks in the past so forward returns exist"
            )
        with col_fv2:
            fv_tickers_raw = st.text_area(
                "Tickers to test",
                value="NVDA, META, TSLA, ENPH, PYPL, FCX, TPL, AMD, AMZN, NFLX, GOOGL, MSFT, AAPL, CRM, COIN, ROKU, SNAP, UBER, LYFT, SHOP",
                height=80,
                key="fv_tickers"
            )

        fv_min_score = st.slider("Minimum score to count as a signal", 40, 90, 60,
            help="Only stocks scoring above this are counted as signals")

        fv_run = st.button("▶ Run Forward Return Validation", key="fv_run")

        if fv_run:
            fv_tickers = [t.upper() for t in re.split(r"[\s,;]+", fv_tickers_raw.strip())
                          if re.match(r"^[A-Z]{1,5}$", t.upper())]
            as_of = datetime.combine(fv_date, datetime.min.time())

            # Check 12 weeks of future data exist
            if (datetime.now() - as_of).days < 85:
                st.error("Please choose a date at least 12 weeks in the past.")
                st.stop()

            st.markdown(f'<div class="section-header">Scanning {len(fv_tickers)} tickers as of {fv_date} → fetching 4/8/12-week returns</div>',
                        unsafe_allow_html=True)

            fv_pbar   = st.progress(0)
            fv_status = st.empty()

            signals     = []  # passed the scanner
            non_signals = []  # did not pass

            for i, ticker in enumerate(fv_tickers):
                fv_pbar.progress((i + 1) / len(fv_tickers))
                fv_status.markdown(
                    f'<span style="font-family:Space Mono;font-size:0.72rem;color:#64748b">Scanning {ticker} ({i+1}/{len(fv_tickers)})...</span>',
                    unsafe_allow_html=True)

                bt_mode = "retest" if is_retest else "base"
                result = run_single_backtest(
                    ticker, as_of,
                    w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult,
                    d_atr_pct_min, d_atr_pct_max, d_above_50sma,
                    mode=bt_mode,
                    bb_base_years=bb_base_years, bb_range_pct=bb_range_pct,
                    bb_atr_max=bb_atr_max, bb_vol_mult=bb_vol_mult,
                    bb_sma_lo=bb_sma_lo, bb_sma_hi=bb_sma_hi,
                )
                if result[0] is None:
                    continue

                w_pass, d_pass, sc, wr, dr = result
                if sc < fv_min_score:
                    continue

                # Fetch forward returns for signals and a sample of non-signals
                r4w_p,  r4w  = get_forward_return(ticker, as_of, 4)
                r8w_p,  r8w  = get_forward_return(ticker, as_of, 8)
                r12w_p, r12w = get_forward_return(ticker, as_of, 12)

                row = {
                    "ticker":    ticker,
                    "score":     sc,
                    "passed":    w_pass and d_pass,
                    "w_pass":    w_pass,
                    "wr":        wr,
                    "dr":        dr,
                    "entry":     wr.get("current_close"),
                    "ret_4w":    r4w,
                    "ret_8w":    r8w,
                    "ret_12w":   r12w,
                    "price_4w":  r4w_p,
                    "price_8w":  r8w_p,
                    "price_12w": r12w_p,
                }
                if w_pass and d_pass:
                    signals.append(row)
                else:
                    non_signals.append(row)

            fv_pbar.progress(1.0)
            fv_status.empty()

            all_rows = signals + non_signals
            if not all_rows:
                st.warning("No stocks met the minimum score threshold. Try lowering the minimum score or relaxing criteria.")
            else:
                # ── Summary metrics ───────────────────────────────────────────
                def avg_ret(rows, key):
                    vals = [r[key] for r in rows if r[key] is not None]
                    return round(sum(vals)/len(vals), 1) if vals else None

                def pct_positive(rows, key):
                    vals = [r[key] for r in rows if r[key] is not None]
                    return round(sum(1 for v in vals if v > 0) / len(vals) * 100, 0) if vals else None

                sig_4w  = avg_ret(signals, "ret_4w")
                sig_8w  = avg_ret(signals, "ret_8w")
                sig_12w = avg_ret(signals, "ret_12w")
                ns_4w   = avg_ret(non_signals, "ret_4w")
                ns_8w   = avg_ret(non_signals, "ret_8w")
                ns_12w  = avg_ret(non_signals, "ret_12w")

                prec_4w  = pct_positive(signals, "ret_4w")
                prec_8w  = pct_positive(signals, "ret_8w")
                prec_12w = pct_positive(signals, "ret_12w")

                def fmt_ret(v):
                    if v is None: return "—"
                    color = "#22c55e" if v > 0 else "#ef4444"
                    return f'<span style="color:{color};font-weight:700">{v:+.1f}%</span>'

                st.markdown(f"""
                <div style="background:#111827;border:1px solid #1e293b;border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1.2rem">
                    <div style="font-family:Space Mono,monospace;font-size:0.65rem;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.8rem">
                        Summary — {len(signals)} Signals vs {len(non_signals)} Near-Misses (score ≥{fv_min_score}, as of {fv_date})
                    </div>
                    <table style="width:100%;border-collapse:collapse;font-family:Space Mono,monospace;font-size:0.72rem">
                        <tr style="color:#475569;font-size:0.62rem">
                            <td style="padding:0.3rem 0.5rem"></td>
                            <td style="padding:0.3rem 0.5rem;text-align:center">4 Weeks</td>
                            <td style="padding:0.3rem 0.5rem;text-align:center">8 Weeks</td>
                            <td style="padding:0.3rem 0.5rem;text-align:center">12 Weeks</td>
                        </tr>
                        <tr style="border-top:1px solid #1e293b">
                            <td style="padding:0.4rem 0.5rem;color:#6ee7b7">✓ Signals avg return</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center">{fmt_ret(sig_4w)}</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center">{fmt_ret(sig_8w)}</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center">{fmt_ret(sig_12w)}</td>
                        </tr>
                        <tr style="border-top:1px solid #1e293b">
                            <td style="padding:0.4rem 0.5rem;color:#fca5a5">✗ Near-miss avg return</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center">{fmt_ret(ns_4w)}</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center">{fmt_ret(ns_8w)}</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center">{fmt_ret(ns_12w)}</td>
                        </tr>
                        <tr style="border-top:1px solid #1e293b">
                            <td style="padding:0.4rem 0.5rem;color:#94a3b8">Signal win rate (>0%)</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center;color:#f59e0b">{prec_4w or "—"}%</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center;color:#f59e0b">{prec_8w or "—"}%</td>
                            <td style="padding:0.4rem 0.5rem;text-align:center;color:#f59e0b">{prec_12w or "—"}%</td>
                        </tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)

                # ── Individual results ────────────────────────────────────────
                st.markdown('<div class="section-header">Individual Results</div>', unsafe_allow_html=True)

                for row in sorted(all_rows, key=lambda x: x["score"], reverse=True):
                    is_signal = row["passed"]
                    card_color = "#059669" if is_signal else "#64748b"
                    signal_label = "✓ SIGNAL" if is_signal else "◑ NEAR-MISS"
                    tv_link = f"https://www.tradingview.com/chart/?symbol={row['ticker']}&interval=W"

                    def ret_cell(v):
                        if v is None: return "—"
                        color = "#22c55e" if v > 0 else "#ef4444"
                        return f'<span style="color:{color}">{v:+.1f}%</span>'

                    badges = (
                        badge(row["wr"].get("pass_200sma_proximity"), f"200W {row['wr'].get('dist_200sma_pct',0):+.1f}%") +
                        badge(row["wr"].get("pass_prior_run"),        f"Run {row['wr'].get('prior_run_pct',0):.0f}%") +
                        badge(row["wr"].get("pass_correction"),       f"Corr {row['wr'].get('correction_from_ath_pct',0):.0f}%") +
                        badge(row["wr"].get("pass_volume_surge"),     f"Vol ×{row['wr'].get('vol_ratio',0):.1f}") +
                        badge(row["dr"].get("pass_atr"),              f"ATR {row['dr'].get('atr_pct',0):.1f}%") +
                        badge(row["dr"].get("pass_50sma"),            f"50D {row['dr'].get('pct_above_50sma',0):+.1f}%")
                    )

                    st.markdown(f"""
                    <div style="background:#111827;border:1px solid #1e293b;border-left:3px solid {card_color};
                                border-radius:10px;padding:1rem 1.2rem;margin-bottom:0.8rem">
                        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem">
                            <div style="display:flex;align-items:center;gap:0.8rem">
                                <span style="font-family:Syne,sans-serif;font-weight:800;font-size:1.2rem;color:#f59e0b">{row['ticker']}</span>
                                <span style="font-family:Space Mono,monospace;font-size:0.65rem;color:{card_color}">{signal_label}</span>
                                <span style="font-family:Space Mono,monospace;font-size:0.65rem;color:#64748b">{row['score']}/100</span>
                                <a class="tv-btn" href="{tv_link}" target="_blank">📈 Chart ↗</a>
                            </div>
                            <div style="font-family:Space Mono,monospace;font-size:0.72rem;display:flex;gap:1.2rem">
                                <span style="color:#64748b">Entry: <b style="color:#94a3b8">${row['entry']}</b></span>
                                <span style="color:#64748b">4W: {ret_cell(row['ret_4w'])}</span>
                                <span style="color:#64748b">8W: {ret_cell(row['ret_8w'])}</span>
                                <span style="color:#64748b">12W: {ret_cell(row['ret_12w'])}</span>
                            </div>
                        </div>
                        <div style="margin-top:0.5rem">{badges}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # ── Export ────────────────────────────────────────────────────
                export_rows = []
                for row in sorted(all_rows, key=lambda x: x["score"], reverse=True):
                    export_rows.append({
                        "Ticker":     row["ticker"],
                        "Signal":     "Yes" if row["passed"] else "Near-Miss",
                        "Score":      row["score"],
                        "Entry":      row["entry"],
                        "Ret 4W %":   row["ret_4w"],
                        "Ret 8W %":   row["ret_8w"],
                        "Ret 12W %":  row["ret_12w"],
                        "Price 4W":   row["price_4w"],
                        "Price 8W":   row["price_8w"],
                        "Price 12W":  row["price_12w"],
                    })
                df_fv = pd.DataFrame(export_rows)
                st.markdown('<div class="section-header">Export</div>', unsafe_allow_html=True)
                st.dataframe(df_fv, use_container_width=True)
                st.download_button("⬇ Download Forward Return CSV",
                    df_fv.to_csv(index=False), f"forward_returns_{fv_date}.csv", "text/csv")
