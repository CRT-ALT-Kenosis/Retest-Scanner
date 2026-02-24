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
.category-header {
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1rem;
    padding: 0.6rem 1rem; border-radius: 8px; margin: 1.5rem 0 0.8rem;
    display: flex; align-items: center; gap: 0.6rem;
}
.cat-full  { background: linear-gradient(135deg,#064e3b,#065f46); color: #6ee7b7; border: 1px solid #059669; }
.cat-strong{ background: linear-gradient(135deg,#1e1a03,#292400); color: #fcd34d; border: 1px solid #ca8a04; }
.cat-watch { background: linear-gradient(135deg,#1e1a2e,#1a1a3e); color: #a5b4fc; border: 1px solid #6366f1; }
.tv-btn {
    display: inline-block; background: #1e3a5f; color: #60a5fa;
    font-family: 'Space Mono', monospace; font-size: 0.62rem;
    padding: 3px 10px; border-radius: 4px; text-decoration: none;
    border: 1px solid #2563eb; margin-left: 8px;
    transition: background 0.15s;
}
.tv-btn:hover { background: #2563eb; color: #fff; }
.known-setup-card {
    background: #0d1117; border: 1px solid #1e293b; border-radius: 10px;
    padding: 1rem 1.2rem; margin-bottom: 0.6rem;
    font-family: 'Space Mono', monospace; font-size: 0.72rem; color: #94a3b8;
}
.known-setup-card .ks-ticker { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1.1rem; color: #f59e0b; }
.known-setup-card .ks-date   { font-size: 0.65rem; color: #64748b; margin-left: 8px; }
.known-setup-card .ks-desc   { margin-top: 0.3rem; font-size: 0.68rem; color: #64748b; line-height: 1.5; }
.bt-result-pass { background:#064e3b; border:1px solid #059669; border-radius:8px; padding:0.8rem 1rem; margin-bottom:0.8rem; }
.bt-result-fail { background:#450a0a; border:1px solid #7f1d1d; border-radius:8px; padding:0.8rem 1rem; margin-bottom:0.8rem; }
.bt-result-warn { background:#1e1a03; border:1px solid #ca8a04; border-radius:8px; padding:0.8rem 1rem; margin-bottom:0.8rem; }
.bt-ticker { font-family:'Syne',sans-serif; font-weight:800; font-size:1.2rem; }
.bt-score  { font-family:'Space Mono',monospace; font-size:0.72rem; color:#94a3b8; margin-left:10px; }
.bt-meta   { font-family:'Space Mono',monospace; font-size:0.65rem; color:#64748b; margin-top:0.4rem; line-height:1.7; }
.replay-bar { display:flex; gap:0.8rem; align-items:center; margin-bottom:1rem; flex-wrap:wrap; }
.week-label { font-family:'Space Mono',monospace; font-size:0.75rem; color:#f59e0b; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">📡 Institutional Retest Scanner</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">TradingView Pre-Filter · Weekly 200-SMA Retest · Daily Confirmation · Volume Surge</div>', unsafe_allow_html=True)

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
        w_dist_200sma_lo = st.slider("Max % BELOW 200W SMA", 0, 60, 25,
            help="Catches deep bear lows under the 200W SMA (META, TSLA style)")
        w_dist_200sma_hi = st.slider("Max % ABOVE 200W SMA", 0, 60, 20,
            help="Early recoveries just above 200W SMA (TPL style)")
        w_prior_run  = st.slider("Min prior run from base (%)", 100, 1000, 300)
        w_correction = st.slider("Min correction from ATH (%)", 30, 80, 45)
        w_vol_mult   = st.slider("Weekly volume surge (4W/20W)", 1.0, 5.0, 1.5)
        # Base breakout params not used in retest mode — set neutral defaults
        bb_base_years     = 2
        bb_range_pct      = 60
        bb_atr_max        = 4.0
        bb_vol_mult       = 1.5
        bb_sma_lo         = 10
        bb_sma_hi         = 40
        bb_sectors        = []

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
        w_dist_200sma_lo = 25
        w_dist_200sma_hi = 20
        w_prior_run      = 300
        w_correction     = 45
        w_vol_mult       = 1.5

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

# ── yfinance Data Helpers ─────────────────────────────────────────────────────
_yf_cache = {}

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
    if len(df_w) < 100:
        return False, {"error": "short"}
    closes = df_w["close"]; vols = df_w["volume"]

    # Use 200-period SMA (or all available if < 200 weeks)
    sma200_series = calc_sma(closes, min(200, len(closes) - 1))
    sma200 = sma200_series.iloc[-1]
    cur    = closes.iloc[-1]

    # ATH = highest close in the FIRST 80% of history (avoids using future data)
    # This prevents the current price from being the ATH if stock is still rising
    history_cutoff = int(len(closes) * 0.85)
    ath = closes.iloc[:history_cutoff].max()
    atl = closes.min()

    dist = (cur - sma200) / sma200 * 100
    run  = (ath - atl) / atl * 100
    corr = (ath - cur) / ath  * 100

    # Volume: use 4-week avg vs 20-week avg for smoother signal
    avg_vol_4w  = vols.rolling(4).mean().iloc[-1]
    avg_vol_20w = vols.rolling(20).mean().iloc[-1]
    vr = avg_vol_4w / avg_vol_20w if avg_vol_20w > 0 else 0

    slope = sma200_series.iloc[-1] - sma200_series.iloc[-5] if len(sma200_series) >= 5 else 0

    # 200W SMA proximity: allow both below (bear lows) and above (early recovery)
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

def check_base_breakout(df_w, bb_base_atr_max, bb_base_weeks, bb_vol_mult, bb_sma200_hi):
    """
    Base Breakout Mode criteria:
    - Long consolidation: low ATR% over bb_base_weeks
    - Price breaking above or near 200W SMA (0 to +bb_sma200_hi%)
    - Volume surge on breakout week vs 20W average
    - Prior range tightness measured by high/low spread over base period
    """
    res = {}
    if len(df_w) < max(bb_base_weeks, 50):
        return False, {"error": "short"}

    closes = df_w["close"]
    highs  = df_w["high"]
    lows   = df_w["low"]
    vols   = df_w["volume"]

    cur    = closes.iloc[-1]
    sma200 = calc_sma(closes, min(200, len(closes)-1)).iloc[-1]
    dist   = (cur - sma200) / sma200 * 100

    # Base period = last bb_base_weeks weeks
    base_closes = closes.iloc[-bb_base_weeks:]
    base_highs  = highs.iloc[-bb_base_weeks:]
    base_lows   = lows.iloc[-bb_base_weeks:]

    # Tightness: range of base highs/lows as % of base midpoint
    base_high   = base_highs.max()
    base_low    = base_lows.min()
    base_mid    = (base_high + base_low) / 2
    range_pct   = (base_high - base_low) / base_mid * 100

    # ATR% over base period
    prev_c  = closes.shift(1)
    tr      = pd.concat([highs - lows,
                         (highs - prev_c).abs(),
                         (lows  - prev_c).abs()], axis=1).max(axis=1)
    base_atr_pct = (tr.iloc[-bb_base_weeks:].mean() / base_mid * 100)

    # Volume surge: current 4-week avg vs 20-week avg
    avg_vol_4w  = vols.rolling(4).mean().iloc[-1]
    avg_vol_20w = vols.rolling(20).mean().iloc[-1]
    vr = avg_vol_4w / avg_vol_20w if avg_vol_20w > 0 else 0

    # 200W SMA slope
    sma200_series = calc_sma(closes, min(200, len(closes)-1))
    slope = sma200_series.iloc[-1] - sma200_series.iloc[-5] if len(sma200_series) >= 5 else 0

    # Prior run (from all-time low to base high)
    atl = closes.min()
    prior_run = (base_high - atl) / atl * 100

    pass_dist    = 0 <= dist <= bb_sma200_hi
    pass_atr     = base_atr_pct <= bb_base_atr_max
    pass_vol     = vr >= bb_vol_mult
    pass_range   = range_pct <= (bb_base_atr_max * 20)  # proportional tightness

    res.update({
        "dist_200sma_pct":         round(dist, 2),
        "sma200":                  round(sma200, 2),
        "current_close":           round(cur, 2),
        "base_atr_pct":            round(base_atr_pct, 2),
        "base_range_pct":          round(range_pct, 1),
        "vol_ratio":               round(vr, 2),
        "prior_run_pct":           round(prior_run, 1),
        "sma200_slope":            round(slope, 2),
        "base_weeks":              bb_base_weeks,
        "pass_200sma_proximity":   pass_dist,
        "pass_base_tightness":     pass_atr,
        "pass_volume_surge":       pass_vol,
        "pass_range_tightness":    pass_range,
        "pass_sma200_slope":       slope >= 0,
        # Aliases so badge rendering works with same keys
        "pass_prior_run":          prior_run >= 50,
        "pass_correction":         True,
        "correction_from_ath_pct": 0,
        "prior_run_pct":           round(prior_run, 1),
    })
    passed = pass_dist and pass_atr and pass_vol
    return passed, res

def score_base_breakout(wr, dr):
    pts = 0
    if wr.get("pass_200sma_proximity"):  pts += 25
    if wr.get("pass_base_tightness"):    pts += 25
    if wr.get("pass_volume_surge"):      pts += 25
    if wr.get("pass_range_tightness"):   pts += 10
    if wr.get("pass_sma200_slope"):      pts += 5
    if dr.get("pass_atr"):               pts += 5
    if dr.get("pass_50sma"):             pts += 5
    return pts

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
                "pass_50sma": -15 <= p50 <= d_above_50sma,  # allow up to 15% below 50D
                "pass_ema_cross": ema_sp > -5,
                "pass_candle_position": rng_pos >= 0.4})
    return res["pass_atr"] and res["pass_50sma"], res

def check_base_breakout(df_w, df_d, bb_base_years, bb_range_pct, bb_atr_max,
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
        w_pass, wr = check_base_breakout(df_w, df_d, bb_base_years, bb_range_pct,
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
    st.markdown('''
    <div class="info-box">
    Uses TradingView's screener API to pull stocks matching your structural criteria — market cap $1B+,
    in a correction, with enough volume — with no API key or rate limits required.
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
        # No API key needed for yfinance
        if not scan_universe:
            st.error("No tickers to scan.")
            st.stop()

        _yf_cache.clear()  # fresh cache each scan run

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
                w_pass, wr = check_base_breakout(df_w, bb_base_atr_max, bb_base_weeks, bb_vol_mult, bb_sma200_hi)

            df_d = get_yf_data(ticker, period="1y", freq="1d")
            d_pass, dr = (False, {}) if (df_d is None or len(df_d) < 55) else check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma)

            sc = score_setup(wr, dr) if is_retest else score_base_breakout(wr, dr)

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

        pbar.progress(1.0)
        status_txt.markdown('<span style="font-family:Space Mono;font-size:0.75rem;color:#22c55e;">✓ Scan complete</span>', unsafe_allow_html=True)

        mode_label = '🔄 Retest Mode' if is_retest else '📦 Base Breakout Mode'
        st.markdown(f'<div class="section-header">Results — {mode_label}</div>', unsafe_allow_html=True)

        if not hits:
            st.warning("No stocks passed. Try relaxing the criteria sliders in the sidebar.")
        else:
            hits_sorted = sorted(hits, key=lambda x: x["score"], reverse=True)

            # ── Categorise ────────────────────────────────────────────────────
            full_hits    = [h for h in hits_sorted if h["score"] >= 85 and not h.get("partial")]
            strong_hits  = [h for h in hits_sorted if 65 <= h["score"] < 85 and not h.get("partial")]
            watchlist    = [h for h in hits_sorted if h["score"] < 65 or h.get("partial")]

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
                        detail = (f"200W SMA: <b style='color:#94a3b8'>${wr.get('sma200','—')}</b> &nbsp;|&nbsp;"
                                  f"Dist: <b style='color:#94a3b8'>{wr.get('dist_200sma_pct','—')}%</b> &nbsp;|&nbsp;"
                                  f"Run: <b style='color:#94a3b8'>{wr.get('prior_run_pct','—')}%</b> &nbsp;|&nbsp;"
                                  f"Corr: <b style='color:#94a3b8'>{wr.get('correction_from_ath_pct','—')}%</b><br>"
                                  f"Vol ×<b style='color:#94a3b8'>{wr.get('vol_ratio','—')}</b> &nbsp;|&nbsp;"
                                  f"ATR: <b style='color:#94a3b8'>{dr.get('atr_pct','—')}%</b> &nbsp;|&nbsp;"
                                  f"50D: <b style='color:#94a3b8'>{dr.get('pct_above_50sma','—')}%</b>")
                    else:
                        badges = (
                            badge(wr.get("pass_200sma_proximity"), f"200W {wr.get('dist_200sma_pct',0):+.1f}%") +
                            badge(wr.get("pass_base_range"),       f"Base range {wr.get('base_range_pct',0):.0f}%") +
                            badge(wr.get("pass_base_atr"),         f"Base ATR {wr.get('base_atr_pct',0):.1f}%") +
                            badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                            badge(wr.get("pass_base_duration"),    f"Base {wr.get('base_duration_yrs',0):.1f}yr") +
                            badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%")
                        )
                        detail = (f"200W SMA: <b style='color:#94a3b8'>${wr.get('sma200','—')}</b> &nbsp;|&nbsp;"
                                  f"Dist: <b style='color:#94a3b8'>{wr.get('dist_200sma_pct','—')}%</b> &nbsp;|&nbsp;"
                                  f"Base range: <b style='color:#94a3b8'>{wr.get('base_range_pct','—')}%</b> &nbsp;|&nbsp;"
                                  f"Base ATR: <b style='color:#94a3b8'>{wr.get('base_atr_pct','—')}%</b><br>"
                                  f"Base duration: <b style='color:#94a3b8'>{wr.get('base_duration_yrs','—')}yr</b> &nbsp;|&nbsp;"
                                  f"Vol ×<b style='color:#94a3b8'>{wr.get('vol_ratio','—')}</b> &nbsp;|&nbsp;"
                                  f"ATR: <b style='color:#94a3b8'>{dr.get('atr_pct','—')}%</b>")

                    mode_tag = '<span style="font-family:Space Mono;font-size:0.6rem;color:#64748b;margin-left:6px">[RETEST]</span>' if is_retest else '<span style="font-family:Space Mono;font-size:0.6rem;color:#fcd34d;margin-left:6px">[BASE BREAKOUT]</span>'
                    st.markdown(f"""
                    <div class="hit-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.4rem">
                            <div style="display:flex;align-items:center;flex-wrap:wrap;gap:0.3rem">
                                <span class="ticker">{h['ticker']}</span>{mode_tag}
                                {partial_tag}
                                <a class="tv-btn" href="{tv_link}" target="_blank">📈 View on TradingView ↗</a>
                            </div>
                            <div style="display:flex;align-items:center;gap:1rem">
                                <span style="font-family:Space Mono;font-size:0.8rem;color:#94a3b8;">${wr.get('current_close','—')}</span>
                                <span style="font-family:Space Mono;font-size:0.75rem;color:#f59e0b;font-weight:700">{h['score']}/100</span>
                            </div>
                        </div>
                        <div style="margin-top:0.6rem">{badges}</div>
                        <div style="margin-top:0.5rem;font-size:0.62rem;color:#475569;font-family:Space Mono;line-height:1.8">{detail}</div>
                    </div>
                    """, unsafe_allow_html=True)

            render_category("Full Hit",  "🟢", "cat-full",   full_hits)
            render_category("Strong",    "🟡", "cat-strong",  strong_hits)
            render_category("Watchlist", "🔵", "cat-watch",   watchlist)

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
                    "ATR %":           h["dr"].get("atr_pct"),
                    "% Above 50D SMA": h["dr"].get("pct_above_50sma"),
                    "TradingView":     tv_url(h["ticker"]),
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
            <div style="background:#0f1a2e;border:1px solid #1e3a5f;border-radius:12px;padding:2.5rem;text-align:center;margin-top:1rem;">
                <div style="font-size:2rem;margin-bottom:0.5rem;">⬅</div>
                <div style="font-family:Space Mono,monospace;font-size:0.8rem;color:#94a3b8;">
                    Go to <b style="color:#f59e0b">Step 1 — TradingView Pre-Filter</b> to build your candidate list first,<br>
                    then come back here and hit 🚀 Run Scanner.
                </div>
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
                        bb_base_atr_max=bb_base_atr_max, bb_base_weeks=bb_base_weeks,
                        bb_vol_mult=bb_vol_mult, bb_sma200_hi=bb_sma200_hi,
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
                full_pass = w_pass and d_pass
                if full_pass: passed_count += 1

                result_class = "bt-result-pass" if full_pass else ("bt-result-warn" if w_pass else "bt-result-fail")
                status_icon  = "✅ CAUGHT" if full_pass else ("◑ WEEKLY ONLY" if w_pass else "❌ MISSED")
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
                    bb_base_atr_max=bb_base_atr_max, bb_base_weeks=bb_base_weeks,
                    bb_vol_mult=bb_vol_mult, bb_sma200_hi=bb_sma200_hi,
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
                    bb_base_atr_max=bb_base_atr_max, bb_base_weeks=bb_base_weeks,
                    bb_vol_mult=bb_vol_mult, bb_sma200_hi=bb_sma200_hi,
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
