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
st.markdown('<div class="subtitle">Finviz Pre-Filter · Weekly 200-SMA Retest · Daily Confirmation · Volume Surge</div>', unsafe_allow_html=True)

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
        "Finviz Pre-Filter (recommended)",
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

# ── Finviz Scraper ────────────────────────────────────────────────────────────
def scrape_finviz(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://finviz.com/",
    }
    from html.parser import HTMLParser

    class TickerParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tickers = []
            self._capture = False
        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "a" and attrs_dict.get("class") == "screener-link-primary":
                self._capture = True
        def handle_data(self, data):
            if self._capture:
                self.tickers.append(data.strip())
                self._capture = False
        def handle_endtag(self, tag):
            self._capture = False

    tickers = []
    try:
        for row_start in range(1, 601, 20):
            paged_url = url + f"&r={row_start}"
            r = requests.get(paged_url, headers=headers, timeout=15)
            if r.status_code != 200:
                break
            parser = TickerParser()
            parser.feed(r.text)
            page_tickers = parser.tickers
            if not page_tickers:
                break
            tickers.extend(page_tickers)
            if len(page_tickers) < 20:
                break
            time.sleep(0.6)
    except Exception:
        pass
    return list(dict.fromkeys(tickers))

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
tab1, tab2 = st.tabs(["🔍  Step 1 — Finviz Pre-Filter", "🚀  Step 2 — Run Scanner"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — FINVIZ
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">Build Your Candidate List — Free, No API Quota Used</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
    Finviz screens 8,000+ stocks for free using pre-market structural filters — big prior run, deep correction,
    sector focus — so your Tiingo quota is spent only on genuine candidates.
    <br><br>
    <b style="color:#f59e0b">Workflow:</b>&nbsp; Configure filters below → Auto-fetch tickers → Switch to Scanner tab → Run
    </div>
    """, unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<div class="section-header">Price & Liquidity</div>', unsafe_allow_html=True)
        min_price   = st.selectbox("Minimum share price ($)", [5, 10, 20, 50], index=2)
        min_avg_vol = st.selectbox("Minimum avg daily volume (K shares)", [100, 200, 300, 500], index=2)

        st.markdown('<div class="section-header">Market Cap</div>', unsafe_allow_html=True)
        market_caps = st.multiselect("Include market caps", [
            "Small ($300M–$2B)", "Mid ($2B–$10B)", "Large ($10B+)", "Mega ($200B+)"
        ], default=["Mid ($2B–$10B)", "Large ($10B+)"])

    with col_r:
        st.markdown('<div class="section-header">52-Week Performance (Correction Proxy)</div>', unsafe_allow_html=True)
        perf_range = st.selectbox("52-week return bucket", [
            "-20% to 0%   (mild pullback)",
            "-40% to -20% (moderate correction) ← recommended",
            "-60% to -40% (deep correction)",
            "Down >60%    (extreme — higher risk)",
        ], index=1)

        st.markdown('<div class="section-header">Sector Focus</div>', unsafe_allow_html=True)
        st.caption("Sectors that produce big-run-then-correct setups like TPL")
        sectors = st.multiselect("Sectors", [
            "Energy", "Technology", "Industrials", "Materials",
            "Healthcare", "Consumer Cyclical", "Financial", "Real Estate",
        ], default=["Energy", "Technology", "Industrials", "Materials"])

    # ── Build URL ────────────────────────────────────────────────────────────
    price_codes = {5: "sh_price_o5", 10: "sh_price_o10", 20: "sh_price_o20", 50: "sh_price_o50"}
    vol_codes   = {100: "sh_avgvol_o100", 200: "sh_avgvol_o200", 300: "sh_avgvol_o300", 500: "sh_avgvol_o500"}
    perf_codes  = {
        "-20% to 0%   (mild pullback)":                  "ta_perf2_-20to0",
        "-40% to -20% (moderate correction) ← recommended": "ta_perf2_-40to-20",
        "-60% to -40% (deep correction)":                "ta_perf2_-60to-40",
        "Down >60%    (extreme — higher risk)":           "ta_perf2_u",
    }
    sector_codes = {
        "Energy": "sec_energy", "Technology": "sec_technology",
        "Industrials": "sec_industrials", "Materials": "sec_basicmaterials",
        "Healthcare": "sec_healthcare", "Consumer Cyclical": "sec_consumercyclical",
        "Financial": "sec_financial", "Real Estate": "sec_realestate",
    }
    cap_codes = {
        "Small ($300M–$2B)": "cap_small", "Mid ($2B–$10B)": "cap_mid",
        "Large ($10B+)": "cap_large", "Mega ($200B+)": "cap_mega",
    }

    f_parts = []
    if min_price   in price_codes: f_parts.append(price_codes[min_price])
    if min_avg_vol in vol_codes:   f_parts.append(vol_codes[min_avg_vol])
    if perf_range  in perf_codes:  f_parts.append(perf_codes[perf_range])
    for s in sectors:
        if s in sector_codes: f_parts.append(sector_codes[s])
    for m in market_caps:
        if m in cap_codes: f_parts.append(cap_codes[m])

    finviz_url = f"https://finviz.com/screener.ashx?v=111&f={','.join(f_parts)}&o=-volume"

    st.markdown('<div class="section-header">Generated Finviz URL</div>', unsafe_allow_html=True)
    st.code(finviz_url, language=None)

    btn_col, link_col, _ = st.columns([1, 1, 2])
    with btn_col:
        fetch_btn = st.button("⬇ Auto-Fetch Tickers")
    with link_col:
        st.markdown(f'<br><a href="{finviz_url}" target="_blank" style="color:#f59e0b;font-family:Space Mono,monospace;font-size:0.8rem;">🔗 Open in Finviz ↗</a>', unsafe_allow_html=True)

    if fetch_btn:
        with st.spinner("Scraping Finviz — may take 10–30 seconds..."):
            found = scrape_finviz(finviz_url)
        if found:
            st.session_state["finviz_tickers"] = found
            st.success(f"✅ Fetched {len(found)} tickers — switch to the Scanner tab to run")
            pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in found[:100]])
            st.markdown(f'<div style="margin-top:0.5rem">{pills}{"&nbsp;..." if len(found) > 100 else ""}</div>', unsafe_allow_html=True)
        else:
            st.warning("Finviz blocked the automated request (rate limit). Use the manual method below.")

    # ── Manual Fallback ───────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Manual Fallback — If Auto-Fetch is Blocked</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="step-box"><span class="step-num">1</span><span class="step-text">Click "Open in Finviz" above and run the screener in your browser</span></div>
    <div class="step-box"><span class="step-num">2</span><span class="step-text">Click the <b>Export</b> button (top-right of results table) → open the downloaded CSV</span></div>
    <div class="step-box"><span class="step-num">3</span><span class="step-text">Copy the entire Ticker column and paste it into the box below</span></div>
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

    # ── Show loaded list ──────────────────────────────────────────────────────
    if "finviz_tickers" in st.session_state:
        loaded = st.session_state["finviz_tickers"]
        st.markdown(f'<div class="section-header">Currently Loaded — {len(loaded)} Tickers</div>', unsafe_allow_html=True)
        pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in loaded[:120]])
        st.markdown(f'<div>{pills}{"&nbsp;..." if len(loaded) > 120 else ""}</div>', unsafe_allow_html=True)
        st.download_button("⬇ Download Ticker List as CSV", ",".join(loaded), "finviz_tickers.csv", "text/csv")

        if st.button("🗑 Clear Loaded Tickers"):
            del st.session_state["finviz_tickers"]
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:

    # Resolve universe
    if universe_choice == "Finviz Pre-Filter (recommended)":
        scan_universe = st.session_state.get("finviz_tickers", [])
        if scan_universe:
            st.info(f"📋 {len(scan_universe)} tickers loaded from Finviz pre-filter. Adjust filters in the Pre-Filter tab if needed.")
        else:
            st.warning("No Finviz tickers loaded yet. Go to **Step 1 — Finviz Pre-Filter** first, or switch Universe in the sidebar.")
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
                    Go to <b style="color:#f59e0b">Step 1 — Finviz Pre-Filter</b> to build your candidate list first,<br>
                    then come back here and hit 🚀 Run Scanner.
                </div>
            </div>
            """, unsafe_allow_html=True)
