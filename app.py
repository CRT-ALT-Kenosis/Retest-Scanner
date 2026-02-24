import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import re

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Institutional Retest Scanner",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
html, body, [class*="css"] { font-family: 'Syne', sans-serif; background-color: #0a0c10; color: #e2e8f0; }
.stApp { background-color: #0a0c10; }
.main-title {
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 2.4rem;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #f59e0b, #ef4444, #a855f7);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.subtitle {
    font-family: 'Space Mono', monospace; font-size: 0.75rem; color: #64748b;
    letter-spacing: 0.1em; text-transform: uppercase; margin-top: 0.2rem; margin-bottom: 2rem;
}
.metric-card {
    background: #111827; border: 1px solid #1e293b; border-radius: 12px;
    padding: 1.2rem 1.5rem; margin-bottom: 1rem;
}
.metric-card .label { font-family: 'Space Mono', monospace; font-size: 0.65rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; }
.metric-card .value { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 2rem; color: #f59e0b; }
.hit-card {
    background: linear-gradient(135deg, #0f1a2e 0%, #111827 100%);
    border: 1px solid #1e3a5f; border-left: 3px solid #f59e0b;
    border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 1rem;
    font-family: 'Space Mono', monospace;
}
.hit-card .ticker { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1.4rem; color: #f59e0b; }
.hit-card .score { font-size: 0.75rem; color: #94a3b8; }
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 0.65rem; font-family: 'Space Mono', monospace; margin-right: 4px; margin-top: 4px;
}
.badge-green { background: #064e3b; color: #6ee7b7; border: 1px solid #065f46; }
.badge-red { background: #450a0a; color: #fca5a5; border: 1px solid #7f1d1d; }
.section-header {
    font-family: 'Space Mono', monospace; font-size: 0.7rem; color: #475569;
    text-transform: uppercase; letter-spacing: 0.12em;
    border-bottom: 1px solid #1e293b; padding-bottom: 0.5rem;
    margin-bottom: 1rem; margin-top: 1.5rem;
}
div[data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #1e293b; }
.stButton > button {
    background: linear-gradient(135deg, #f59e0b, #d97706); color: #0a0c10;
    font-family: 'Syne', sans-serif; font-weight: 700; border: none;
    border-radius: 8px; padding: 0.6rem 2rem; font-size: 0.9rem;
    letter-spacing: 0.03em; width: 100%; transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }
.log-box {
    background: #0d1117; border: 1px solid #1e293b; border-radius: 8px;
    padding: 1rem; font-family: 'Space Mono', monospace; font-size: 0.7rem;
    color: #475569; max-height: 300px; overflow-y: auto;
}
.stProgress > div > div > div > div { background: linear-gradient(90deg, #f59e0b, #ef4444); }
.info-box {
    background: #0f1a2e; border: 1px solid #1e3a5f; border-radius: 10px;
    padding: 1.2rem 1.5rem; margin-bottom: 1rem;
    font-family: 'Space Mono', monospace; font-size: 0.75rem; color: #94a3b8; line-height: 1.7;
}
.step-box {
    background: #111827; border: 1px solid #1e293b; border-radius: 10px;
    padding: 1rem 1.5rem; margin-bottom: 0.8rem;
}
.step-num { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1.1rem; color: #f59e0b; margin-right: 0.5rem; }
.step-text { font-family: 'Space Mono', monospace; font-size: 0.75rem; color: #94a3b8; }
.ticker-pill {
    display: inline-block; background: #1e293b; color: #f59e0b;
    font-family: 'Space Mono', monospace; font-size: 0.7rem;
    padding: 3px 8px; border-radius: 4px; margin: 2px;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">📡 Institutional Retest Scanner</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">TradingView Pre-Filter · Weekly 200-SMA Retest · Daily Confirmation · Volume Surge</div>', unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-header">Configuration</div>', unsafe_allow_html=True)
    # Auto-load from Streamlit Cloud secrets if available
    _default_key = st.secrets.get("TIINGO_KEY", "") if hasattr(st, "secrets") else ""
    api_key = st.text_input("Tiingo API Key", value=_default_key, type="password", placeholder="your-tiingo-key")
    if _default_key:
        st.caption("🔒 Key loaded from Streamlit secrets")

    st.markdown('<div class="section-header">Weekly Criteria</div>', unsafe_allow_html=True)
    w_dist_200sma = st.slider("Max % above 200-week SMA", 0, 30, 15)
    w_prior_run   = st.slider("Min prior run from base (%)", 100, 1000, 300)
    w_correction  = st.slider("Min correction from ATH (%)", 30, 80, 45)
    w_vol_mult    = st.slider("Weekly volume surge multiplier", 1.0, 5.0, 1.8)

    st.markdown('<div class="section-header">Daily Criteria</div>', unsafe_allow_html=True)
    d_atr_pct_min = st.slider("Min ATR% (daily)", 2.0, 8.0, 3.0)
    d_atr_pct_max = st.slider("Max ATR% (daily)", 4.0, 15.0, 8.0)
    d_above_50sma = st.slider("Price above 50-day SMA by max (%)", 0, 20, 10)

    st.markdown('<div class="section-header">Universe</div>', unsafe_allow_html=True)
    universe_choice = st.selectbox("Stock Universe", [
        "TradingView Pre-Filter (recommended)",
        "S&P 500 (505 stocks)",
        "Custom Tickers",
    ])
    custom_tickers_input = ""
    if universe_choice == "Custom Tickers":
        custom_tickers_input = st.text_area("Tickers (comma separated)", "TPL, NVDA, TSLA")

    max_stocks = st.number_input("Max stocks to scan", 50, 1000, 200, step=50)
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

# ── Tiingo + Analysis Helpers ─────────────────────────────────────────────────
def get_tiingo_data(ticker, api_key, start_date, freq="daily"):
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices"
    params = {"startDate": start_date, "token": api_key,
               "resampleFreq": "weekly" if freq == "weekly" else "daily"}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception:
        return None

def calc_sma(series, period):
    return series.rolling(window=period, min_periods=period).mean()

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_atr_pct(df, period=14):
    high  = df.get("adjHigh",  df.get("high"))
    low   = df.get("adjLow",   df.get("low"))
    close = df.get("adjClose", df.get("close"))
    prev  = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return (tr.rolling(period).mean() / close * 100).iloc[-1]

def check_weekly(df_w, w_dist_200sma, w_prior_run, w_correction, w_vol_mult):
    res = {}
    cc  = "adjClose" if "adjClose" in df_w.columns else "close"
    if len(df_w) < 210:
        return False, {"error": "short"}
    closes = df_w[cc]; vols = df_w["volume"]
    sma200 = calc_sma(closes, 200).iloc[-1]
    cur    = closes.iloc[-1]
    atl    = closes.min(); ath = closes.max()
    dist   = (cur - sma200) / sma200 * 100
    run    = (ath - atl) / atl * 100
    corr   = (ath - cur)  / ath  * 100
    vr     = vols.iloc[-1] / vols.rolling(20).mean().iloc[-1]
    slope  = calc_sma(closes, 200).iloc[-1] - calc_sma(closes, 200).iloc[-5]
    res.update({"dist_200sma_pct": round(dist,2), "sma200": round(sma200,2),
                "current_close": round(cur,2), "prior_run_pct": round(run,1),
                "correction_from_ath_pct": round(corr,1), "vol_ratio": round(vr,2),
                "sma200_slope": round(slope,2),
                "pass_200sma_proximity": 0 <= dist <= w_dist_200sma,
                "pass_prior_run": run >= w_prior_run,
                "pass_correction": corr >= w_correction,
                "pass_volume_surge": vr >= w_vol_mult,
                "pass_sma200_slope": slope >= 0})
    passed = all([res["pass_200sma_proximity"], res["pass_prior_run"],
                  res["pass_correction"], res["pass_volume_surge"]])
    return passed, res

def check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma):
    res = {}
    cc  = "adjClose" if "adjClose" in df_d.columns else "close"
    if len(df_d) < 55:
        return False, {"error": "short"}
    closes = df_d[cc]; cur = closes.iloc[-1]
    sma50  = calc_sma(closes, 50).iloc[-1]
    ema10  = calc_ema(closes, 10).iloc[-1]
    ema20  = calc_ema(closes, 20).iloc[-1]
    atr    = calc_atr_pct(df_d)
    p50    = (cur - sma50) / sma50 * 100
    ema_sp = (ema10 - ema20) / ema20 * 100
    hi = df_d.get("adjHigh", df_d.get("high")).iloc[-1]
    lo = df_d.get("adjLow",  df_d.get("low")).iloc[-1]
    rng_pos = (cur - lo) / (hi - lo) if hi != lo else 0.5
    res.update({"atr_pct": round(atr,2), "pct_above_50sma": round(p50,2),
                "ema10_vs_ema20_pct": round(ema_sp,2), "candle_range_position": round(rng_pos,2),
                "pass_atr": d_atr_pct_min <= atr <= d_atr_pct_max,
                "pass_50sma": 0 <= p50 <= d_above_50sma,
                "pass_ema_cross": ema_sp > -5,
                "pass_candle_position": rng_pos >= 0.4})
    return res["pass_atr"] and res["pass_50sma"], res

def score_setup(wr, dr):
    pts = 0
    if wr.get("pass_200sma_proximity"): pts += 25
    if wr.get("pass_prior_run"):        pts += 20
    if wr.get("pass_correction"):       pts += 15
    if wr.get("pass_volume_surge"):     pts += 20
    if wr.get("pass_sma200_slope"):     pts += 5
    if dr.get("pass_atr"):             pts += 5
    if dr.get("pass_50sma"):           pts += 5
    if dr.get("pass_ema_cross"):       pts += 3
    if dr.get("pass_candle_position"): pts += 2
    return pts

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🔍  Step 1 — TradingView Pre-Filter", "🚀  Step 2 — Run Scanner"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TRADINGVIEW PRE-FILTER
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('''
    <div class="info-box">
    Uses TradingView's screener API to pull stocks matching your structural criteria — market cap $1B+,
    in a correction, with enough volume — before touching any Tiingo quota.
    <br><br>
    <b style="color:#f59e0b">Workflow:</b>&nbsp; Set filters → Fetch Tickers → Switch to Scanner tab → Run
    </div>
    ''', unsafe_allow_html=True)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<div class="section-header">Market Cap & Liquidity</div>', unsafe_allow_html=True)
        min_mcap = st.selectbox("Minimum Market Cap ($B)", [1, 2, 5, 10], index=0,
            help="$1B+ captures mid-caps where big-run-then-correct setups are most common")
        max_mcap_options = {"No limit": None, "$10B": 10, "$50B": 50, "$200B": 200}
        max_mcap_label = st.selectbox("Maximum Market Cap", list(max_mcap_options.keys()), index=0)
        max_mcap = max_mcap_options[max_mcap_label]
        min_vol_k = st.selectbox("Min Avg Daily Volume (shares)", [100_000, 200_000, 300_000, 500_000],
            format_func=lambda x: f"{x//1000}K", index=1)
        exchanges = st.multiselect("Exchanges", ["NYSE", "NASDAQ", "AMEX"],
            default=["NYSE", "NASDAQ"])

    with col_r:
        st.markdown('<div class="section-header">Performance Filter (Correction Proxy)</div>', unsafe_allow_html=True)
        perf_presets = {
            "Mild pullback    (-15% to -20%)":   (-20,  -15),
            "Moderate         (-40% to -15%) ← recommended": (-40, -15),
            "Deep correction  (-60% to -40%)":   (-60,  -40),
            "Extreme          (-80% to -60%)":   (-80,  -60),
            "Custom range":                       None,
        }
        perf_choice = st.selectbox("1-Year Performance", list(perf_presets.keys()), index=1)
        if perf_presets[perf_choice] is None:
            c1, c2 = st.columns(2)
            perf_min = c1.number_input("Min 1Y perf (%)", value=-60, min_value=-100, max_value=0)
            perf_max = c2.number_input("Max 1Y perf (%)", value=-15, min_value=-100, max_value=0)
        else:
            perf_min, perf_max = perf_presets[perf_choice]

        st.markdown('<div class="section-header">Sector Focus</div>', unsafe_allow_html=True)
        st.caption("Sectors that produce big-run-then-correct setups")
        tv_sectors = st.multiselect("Sectors (leave empty = all sectors)", list(SECTOR_MAP.keys()),
            default=["Energy", "Technology", "Industrials", "Basic Materials"])

    # ── Fetch button ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Fetch Tickers from TradingView</div>', unsafe_allow_html=True)

    # Show what will be sent
    filter_summary_parts = [
        f"Market cap ≥ ${min_mcap}B",
        f"Max: {max_mcap_label}",
        f"Avg vol ≥ {min_vol_k//1000}K",
        f"1Y perf {perf_min}% to {perf_max}%",
        f"Sectors: {', '.join(tv_sectors) if tv_sectors else 'All'}",
        f"Exchanges: {', '.join(exchanges)}",
    ]
    st.markdown(
        '<div style="font-family:Space Mono,monospace;font-size:0.7rem;color:#64748b;margin-bottom:1rem;">' +
        " &nbsp;·&nbsp; ".join(filter_summary_parts) + '</div>',
        unsafe_allow_html=True)

    max_tv_results = st.slider("Max results to fetch", 100, 1000, 400, step=50)

    fetch_col, _ = st.columns([1, 3])
    with fetch_col:
        fetch_btn = st.button("⬇ Fetch Tickers from TradingView")

    if fetch_btn:
        with st.spinner("Querying TradingView screener..."):
            found, err = fetch_tradingview_tickers(
                min_market_cap_b=float(min_mcap),
                max_market_cap_b=float(max_mcap) if max_mcap else None,
                min_avg_vol=min_vol_k,
                perf_1y_min=float(perf_min),
                perf_1y_max=float(perf_max),
                sectors=tv_sectors if tv_sectors else None,
                exchanges=tuple(exchanges),
                max_results=max_tv_results,
            )
        if err:
            st.error(f"TradingView error: {err}")
        elif found:
            st.session_state["finviz_tickers"] = found
            st.success(f"✅ Fetched {len(found)} tickers from TradingView — switch to the Scanner tab to run")
            pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in found[:120]])
            st.markdown(f'<div style="margin-top:0.5rem">{pills}{"&nbsp;..." if len(found) > 120 else ""}</div>',
                unsafe_allow_html=True)
        else:
            st.warning("No tickers matched. Try broadening your filters.")

    # ── Manual paste fallback ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">Manual Fallback — Paste from TradingView or Any Screener</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="step-box"><span class="step-num">1</span><span class="step-text">Open TradingView Screener at <b>tradingview.com/screener</b> and apply your filters</span></div>
    <div class="step-box"><span class="step-num">2</span><span class="step-text">Select all rows → Export → open CSV → copy the Symbol column</span></div>
    <div class="step-box"><span class="step-num">3</span><span class="step-text">Paste tickers below and click Load</span></div>
    """, unsafe_allow_html=True)

    manual_paste = st.text_area("Paste tickers (comma, space, or newline separated)", height=100,
                                placeholder="AAPL, NVDA, TPL, TSLA\nor one per line...")
    if st.button("✓ Load Pasted Tickers"):
        raw   = re.split(r"[\s,;]+", manual_paste.strip())
        clean = [t.upper() for t in raw if re.match(r"^[A-Z]{1,5}$", t.upper())]
        if clean:
            st.session_state["finviz_tickers"] = clean
            st.success(f"✅ Loaded {len(clean)} tickers — switch to the Scanner tab to run")
        else:
            st.error("No valid tickers found.")

    # ── Show loaded tickers ───────────────────────────────────────────────────
    if "finviz_tickers" in st.session_state:
        loaded = st.session_state["finviz_tickers"]
        st.markdown(f'<div class="section-header">Currently Loaded — {len(loaded)} Tickers</div>', unsafe_allow_html=True)
        pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in loaded[:120]])
        st.markdown(f'<div>{pills}{"&nbsp;..." if len(loaded) > 120 else ""}</div>', unsafe_allow_html=True)
        st.download_button("⬇ Download Ticker List as CSV", ",".join(loaded), "tv_tickers.csv", "text/csv")
        if st.button("🗑 Clear Loaded Tickers"):
            del st.session_state["finviz_tickers"]
            st.rerun()

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
        if not api_key:
            st.error("Enter your Tiingo API key in the sidebar first.")
            st.stop()
        if not scan_universe:
            st.error("No tickers to scan.")
            st.stop()

        start_w = (datetime.now() - timedelta(days=365*6)).strftime("%Y-%m-%d")
        start_d = (datetime.now() - timedelta(days=365*1)).strftime("%Y-%m-%d")

        st.markdown('<div class="section-header">Scan in Progress</div>', unsafe_allow_html=True)
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

        def badge(ok, label):
            cls = "badge-green" if ok else "badge-red"
            return f'<span class="badge {cls}">{"✓" if ok else "✗"} {label}</span>'

        for i, ticker in enumerate(scan_universe):
            pbar.progress((i + 1) / total)
            status_txt.markdown(
                f'<span style="font-family:Space Mono;font-size:0.75rem;color:#64748b;">Scanning {ticker} ({i+1}/{total})</span>',
                unsafe_allow_html=True)

            df_w = get_tiingo_data(ticker, api_key, start_w, "weekly")
            if df_w is None or len(df_w) < 100:
                skipped += 1
                logs.append(f"⚠ {ticker} — no data")
                log_ph.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
                time.sleep(0.05)
                continue

            w_pass, wr = check_weekly(df_w, w_dist_200sma, w_prior_run, w_correction, w_vol_mult)

            df_d = get_tiingo_data(ticker, api_key, start_d, "daily")
            d_pass, dr = (False, {}) if (df_d is None or len(df_d) < 55) else check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma)

            sc = score_setup(wr, dr)

            if w_pass and d_pass:
                hits.append({"ticker": ticker, "score": sc, "wr": wr, "dr": dr})
                logs.append(f"✅ {ticker} — FULL HIT  {sc}/100")
            elif w_pass and sc >= 60:
                hits.append({"ticker": ticker, "score": sc, "wr": wr, "dr": dr, "partial": True})
                logs.append(f"◑ {ticker} — weekly only  {sc}/100")
            else:
                logs.append(f"✗ {ticker} — {sc}/100")

            log_ph.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
            met_scanned.markdown(f'<div class="metric-card"><div class="label">Scanned</div><div class="value">{i+1}</div></div>', unsafe_allow_html=True)
            met_hits.markdown(f'<div class="metric-card"><div class="label">Hits</div><div class="value" style="color:#22c55e">{len(hits)}</div></div>', unsafe_allow_html=True)
            met_skipped.markdown(f'<div class="metric-card"><div class="label">Skipped</div><div class="value" style="color:#ef4444">{skipped}</div></div>', unsafe_allow_html=True)
            time.sleep(0.12)

        pbar.progress(1.0)
        status_txt.markdown('<span style="font-family:Space Mono;font-size:0.75rem;color:#22c55e;">✓ Scan complete</span>', unsafe_allow_html=True)

        st.markdown('<div class="section-header">Results — Ranked by Setup Score</div>', unsafe_allow_html=True)

        if not hits:
            st.warning("No stocks passed. Try relaxing the criteria sliders in the sidebar.")
        else:
            for h in sorted(hits, key=lambda x: x["score"], reverse=True):
                wr = h["wr"]; dr = h["dr"]
                partial_tag = " <span style='color:#64748b;font-size:0.65rem'>(weekly only)</span>" if h.get("partial") else ""
                badges = (
                    badge(wr.get("pass_200sma_proximity"), f"200W-SMA {wr.get('dist_200sma_pct',0):+.1f}%") +
                    badge(wr.get("pass_prior_run"),        f"Run {wr.get('prior_run_pct',0):.0f}%") +
                    badge(wr.get("pass_correction"),       f"Corr {wr.get('correction_from_ath_pct',0):.0f}%") +
                    badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                    badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                    badge(dr.get("pass_50sma"),            f"50D +{dr.get('pct_above_50sma',0):.1f}%")
                )
                st.markdown(f"""
                <div class="hit-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span class="ticker">{h['ticker']}</span>{partial_tag}
                            <span class="score" style="margin-left:12px;">Score: <b style="color:#f59e0b">{h['score']}/100</b></span>
                        </div>
                        <div style="font-family:Space Mono;font-size:0.8rem;color:#94a3b8;">${wr.get('current_close','—')}</div>
                    </div>
                    <div style="margin-top:0.6rem">{badges}</div>
                    <div style="margin-top:0.5rem;font-size:0.65rem;color:#475569;font-family:Space Mono">
                        200W SMA: ${wr.get('sma200','—')} &nbsp;|&nbsp;
                        Correction: {wr.get('correction_from_ath_pct','—')}% &nbsp;|&nbsp;
                        Daily ATR%: {dr.get('atr_pct','—')}% &nbsp;|&nbsp;
                        EMA10 vs EMA20: {dr.get('ema10_vs_ema20_pct','—')}%
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Export
            st.markdown('<div class="section-header">Export Results</div>', unsafe_allow_html=True)
            rows = []
            for h in sorted(hits, key=lambda x: x["score"], reverse=True):
                rows.append({
                    "Ticker": h["ticker"], "Score": h["score"],
                    "Close": h["wr"].get("current_close"),
                    "200W SMA": h["wr"].get("sma200"),
                    "Dist 200W SMA %": h["wr"].get("dist_200sma_pct"),
                    "Prior Run %": h["wr"].get("prior_run_pct"),
                    "Correction %": h["wr"].get("correction_from_ath_pct"),
                    "Vol Ratio": h["wr"].get("vol_ratio"),
                    "ATR %": h["dr"].get("atr_pct"),
                    "% Above 50D SMA": h["dr"].get("pct_above_50sma"),
                    "Partial": h.get("partial", False),
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
                <div style="font-family:Space Mono,monospace;font-size:0.75rem;color:#94a3b8;">tickers queued · click <b>🚀 Run Scanner</b> in the sidebar</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#0f1a2e;border:1px solid #1e3a5f;border-radius:12px;padding:2.5rem;text-align:center;margin-top:1rem;">
                <div style="font-size:2rem;margin-bottom:0.5rem;">⬅</div>
                <div style="font-family:Space Mono,monospace;font-size:0.8rem;color:#94a3b8;">
                    Go to <b style="color:#f59e0b">Step 1 — TradingView Pre-Filter</b> to build your candidate list first,<br>
                    then come back here and hit 🚀 Run Scanner.
                </div>
            </div>
            """, unsafe_allow_html=True)
