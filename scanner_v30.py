import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import re
import yfinance as yf

import json
import os

# ── Persistence — survives websocket drops on Streamlit Cloud ─────────────────
SAVE_PATH = "/tmp/scanner_state.json"
# ── GitHub Gist Persistence ──────────────────────────────────────────────────
# Watchlist is stored as JSON in a private GitHub Gist.
# Survives Streamlit container restarts and works across all devices.
#
# Required Streamlit secrets:
#   [gist]
#   token   = "ghp_..."   ← GitHub personal access token with "gist" scope
#   gist_id = ""          ← blank on first run; scanner auto-creates and saves it
#
# To get a token: github.com/settings/tokens → Generate new token → tick "gist"

GIST_FILENAME = "scanner_watchlist.json"

def _gist_headers():
    try:
        token = st.secrets["gist"]["token"]
        return {"Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"}
    except Exception:
        return None

def _gist_enabled():
    """True if gist token is configured in Streamlit secrets."""
    try:
        t = st.secrets["gist"]["token"]
        return bool(t and t != "ghp_yourtoken")
    except Exception:
        return False

def gist_load_watchlist():
    """
    Fetch watchlist from Gist on app load.
    Returns dict or None if unavailable.
    """
    if not _gist_enabled():
        return None
    try:
        gist_id = st.secrets["gist"].get("gist_id", "")
        if not gist_id:
            return None   # no gist yet — will be created on first save
        headers = _gist_headers()
        r = requests.get(f"https://api.github.com/gists/{gist_id}",
                         headers=headers, timeout=10)
        if r.status_code == 200:
            files = r.json().get("files", {})
            if GIST_FILENAME in files:
                raw = files[GIST_FILENAME].get("content", "{}")
                return json.loads(raw)
    except Exception:
        pass
    return None

def gist_save_watchlist(watchlist_dict):
    """
    Save watchlist to Gist. Creates a new Gist on first call if none exists.
    Gist ID is cached in session state to avoid re-reading secrets mid-session.
    Returns True on success.
    """
    if not _gist_enabled():
        return False
    try:
        headers = _gist_headers()
        content_str = json.dumps(watchlist_dict, indent=2)
        # Use cached id first (set on creation), then fall back to secrets
        gist_id = (st.session_state.get("_gist_id_cache") or
                   st.secrets["gist"].get("gist_id", "").strip())

        if gist_id:
            # Update existing gist
            payload = {"files": {GIST_FILENAME: {"content": content_str}}}
            r = requests.patch(f"https://api.github.com/gists/{gist_id}",
                               json=payload, headers=headers, timeout=10)
            return r.status_code == 200
        else:
            # Create new private gist
            payload = {
                "description": "Retest Scanner — Watchlist (auto-managed)",
                "public": False,
                "files": {GIST_FILENAME: {"content": content_str}},
            }
            r = requests.post("https://api.github.com/gists",
                              json=payload, headers=headers, timeout=10)
            if r.status_code == 201:
                new_id = r.json().get("id", "")
                # Cache for rest of session so repeated saves go to same gist
                st.session_state["_gist_id_cache"] = new_id
                # Flag for UI to display prominently
                return True
    except Exception as e:
        st.session_state["_gist_last_error"] = str(e)
    return False



def gist_checkpoint_hits(hits, scan_ts, mode):
    """Save scan hits to Gist as a checkpoint — survives container restarts.
    Called every 10 new hits during scan so mobile users don't lose progress."""
    if not _gist_enabled():
        return
    try:
        serialisable = []
        for h in hits:
            serialisable.append({
                "ticker":      h["ticker"],
                "score":       h["score"],
                "norm_score":  h.get("norm_score", 0),
                "sector":      h.get("sector", ""),
                "sector_rel":  h.get("sector_rel"),
                "structure":   h.get("rr", {}).get("structure_label", ""),
                "close":       h["wr"].get("current_close"),
                "slope":       h["wr"].get("sma200_slope_grade", ""),
                "wr": {k: v for k, v in h["wr"].items()
                       if isinstance(v, (int, float, str, bool, type(None)))},
                "dr": {k: v for k, v in h["dr"].items()
                       if isinstance(v, (int, float, str, bool, type(None)))},
                "rr": {k: v for k, v in h.get("rr", {}).items()
                       if isinstance(v, (int, float, str, bool, type(None)))},
                "w_pass":      h.get("w_pass", False),
                "d_pass":      h.get("d_pass", False),
                "base_score":  h.get("base_score", 0),
                "bonus_score": h.get("bonus_score", 0),
                "sector_pts":  h.get("sector_pts", 0),
            })
        checkpoint = {"hits": serialisable, "scan_ts": scan_ts, "mode": mode,
                      "checkpoint": True, "hit_count": len(hits)}
        gist_id = st.session_state.get("_gist_id_cache") or ""
        try:
            gist_id = gist_id or st.secrets["gist"].get("gist_id", "").strip()
        except Exception:
            pass
        headers = _gist_headers()
        if not headers:
            return
        payload = {"files": {"scanner_checkpoint.json": {"content": json.dumps(checkpoint)}}}
        if gist_id:
            requests.patch(f"https://api.github.com/gists/{gist_id}",
                          json=payload, headers=headers, timeout=8)
    except Exception:
        pass  # best-effort — never interrupt scan

def gist_load_checkpoint():
    """Load scan checkpoint from Gist on session start."""
    if not _gist_enabled():
        return None
    try:
        gist_id = st.session_state.get("_gist_id_cache") or ""
        try:
            gist_id = gist_id or st.secrets["gist"].get("gist_id", "").strip()
        except Exception:
            pass
        if not gist_id:
            return None
        headers = _gist_headers()
        if not headers:
            return None
        r = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers, timeout=8)
        if r.status_code != 200:
            return None
        files = r.json().get("files", {})
        cp_file = files.get("scanner_checkpoint.json", {})
        raw_url = cp_file.get("raw_url")
        if not raw_url:
            return None
        r2 = requests.get(raw_url, timeout=8)
        data = r2.json()
        return data if data.get("checkpoint") else None
    except Exception:
        return None

def _save_state(hits, logs, scanned, skipped, total, universe, sector_returns,
                watchlist, mode, scan_ts):
    """Write incremental scan state to /tmp. Called after each hit."""
    try:
        # hits contains DataFrames in wr/dr — serialise only JSON-safe fields
        serialisable_hits = []
        for h in hits:
            serialisable_hits.append({
                "ticker":      h["ticker"],
                "score":       h["score"],
                "norm_score":  h.get("norm_score", 0),
                "base_score":  h.get("base_score", 0),
                "bonus_score": h.get("bonus_score", 0),
                "w_pass":      h["w_pass"],
                "d_pass":      h["d_pass"],
                "sector":      h.get("sector", ""),
                "sector_rel":  h.get("sector_rel"),
                "sector_pts":  h.get("sector_pts", 0),
                "wr": {k: v for k, v in h["wr"].items()
                       if isinstance(v, (int, float, str, bool, type(None)))},
                "dr": {k: v for k, v in h["dr"].items()
                       if isinstance(v, (int, float, str, bool, type(None)))},
                "rr": {k: v for k, v in h.get("rr", {}).items()
                       if isinstance(v, (int, float, str, bool, type(None)))},
            })
        state = {
            "hits":           serialisable_hits,
            "logs":           logs[-200:],          # last 200 log lines
            "scanned":        scanned,
            "skipped":        skipped,
            "total":          total,
            "universe":       universe,
            "sector_returns": sector_returns,
            "watchlist":      watchlist,
            "mode":           mode,
            "scan_ts":        scan_ts,
            "complete":       False,
        }
        with open(SAVE_PATH, "w") as f:
            json.dump(state, f)
    except Exception:
        pass  # persistence is best-effort — never crash the scan

def _save_complete(hits, logs, scanned, skipped, total, universe,
                   sector_returns, watchlist, mode, scan_ts):
    """Mark scan as complete in the save file."""
    _save_state(hits, logs, scanned, skipped, total, universe,
                sector_returns, watchlist, mode, scan_ts)
    try:
        with open(SAVE_PATH, "r") as f:
            state = json.load(f)
        state["complete"] = True
        with open(SAVE_PATH, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def _load_state():
    """Load persisted state. Returns dict or None."""
    try:
        if not os.path.exists(SAVE_PATH):
            return None
        with open(SAVE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None

def _clear_state():
    """Delete the save file."""
    try:
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)
    except Exception:
        pass

# ── Restore persisted state into session_state on first load ─────────────────
if "persistence_checked" not in st.session_state:
    st.session_state["persistence_checked"] = True
    saved = _load_state()
    if saved:
        st.session_state["_restored_hits"]    = saved.get("hits", [])
        st.session_state["_restored_logs"]    = saved.get("logs", [])
        st.session_state["_restored_meta"]    = {
            "scanned":   saved.get("scanned", 0),
            "skipped":   saved.get("skipped", 0),
            "total":     saved.get("total", 0),
            "mode":      saved.get("mode", "retest"),
            "scan_ts":   saved.get("scan_ts", ""),
            "complete":  saved.get("complete", False),
        }
        if saved.get("sector_returns"):
            st.session_state["sector_returns_26"] = saved["sector_returns"]
        if saved.get("watchlist"):
            st.session_state["watchlist"] = saved["watchlist"]
        if saved.get("universe"):
            st.session_state["finviz_tickers"] = saved["universe"]
        # ── BRIDGE: populate last_hits so star→rerun path works after restore ──
        if saved.get("hits"):
            st.session_state["last_hits"] = saved["hits"]
            st.session_state["last_hits_mode"] = saved.get("mode", "retest")
            st.session_state["show_restored"] = True  # auto-show on reconnect
    # ── Gist checkpoint fallback (if /tmp wiped — container restart on mobile) ──
    if not saved or not saved.get("hits"):
        _gist_cp = gist_load_checkpoint()
        if _gist_cp and _gist_cp.get("hits"):
            cp_hits = _gist_cp["hits"]
            st.session_state["_restored_hits"] = cp_hits
            st.session_state["_restored_meta"] = {
                "scanned":  _gist_cp.get("hit_count", len(cp_hits)),
                "skipped":  0,
                "total":    _gist_cp.get("hit_count", len(cp_hits)),
                "mode":     _gist_cp.get("mode", "retest"),
                "scan_ts":  _gist_cp.get("scan_ts", ""),
                "complete": False,
            }
            # ── BRIDGE: populate last_hits from Gist checkpoint too ──
            st.session_state["last_hits"] = cp_hits
            st.session_state["last_hits_mode"] = _gist_cp.get("mode", "retest")
            st.session_state["show_restored"] = True  # auto-show on reconnect

# ── Gist watchlist load (runs once per session, after local restore) ─────────
# Gist takes priority over /tmp — it's the source of truth across devices.
if "gist_watchlist_loaded" not in st.session_state:
    st.session_state["gist_watchlist_loaded"] = True
    if _gist_enabled():
        _gist_wl = gist_load_watchlist()
        if _gist_wl is not None:
            st.session_state["watchlist"] = _gist_wl

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

st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
""", unsafe_allow_html=True)

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


/* ══ P01+P03: Progressive Disclosure — 3-layer card ══ */
/* Layer 1 always visible. Layer 2+3 toggle via hidden checkbox (no rerun). */
.card-expand-toggle {{ display: none; }}

.card-layer2 {{
    max-height: 0; overflow: hidden;
    transition: max-height 0.28s cubic-bezier(0.4,0,0.2,1),
                opacity 0.22s ease,
                padding 0.22s ease;
    opacity: 0; padding-top: 0;
}}
.card-expand-toggle:checked ~ .card-layer2 {{
    max-height: 300px; opacity: 1; padding-top: 0.65rem;
}}
.card-layer3 {{
    max-height: 0; overflow: hidden;
    transition: max-height 0.25s ease, opacity 0.2s ease;
    opacity: 0;
}}
.card-expand-toggle:checked ~ .card-layer3,
.card-detail-toggle:checked ~ .card-layer3 {{
    max-height: 200px; opacity: 1;
}}
.expand-btn {{
    background: none; border: none; cursor: pointer;
    color: var(--text-muted); font-size: 0.7rem;
    font-family: DM Mono, monospace; padding: 2px 6px;
    border-radius: 4px; transition: color 0.15s, background 0.15s;
    display: inline-flex; align-items: center; gap: 3px;
}}
.expand-btn:hover {{ color: var(--text-primary); background: var(--bg-raised); }}
.card-expand-toggle:checked + label .expand-chevron {{ transform: rotate(180deg); }}
.expand-chevron {{ display: inline-block; transition: transform 0.2s; }}

/* ══ P01: Signal summary line ══ */
.signal-summary {{
    font-family: DM Mono, monospace; font-size: 0.62rem;
    color: var(--text-muted); margin-top: 0.15rem;
    letter-spacing: 0.01em; line-height: 1.4;
}}

/* ══ P02: Star button — always bottom-right of card, 44px tap target ══ */
.star-area {{ margin-top: 0.4rem; display: flex; justify-content: flex-end; }}
.star-btn-inline {{
    background: none; border: 1px solid var(--border);
    border-radius: 8px; padding: 6px 14px; cursor: pointer;
    font-size: 1rem; transition: all 0.15s; color: var(--text-muted);
    font-family: DM Mono, monospace; font-size: 0.72rem;
    min-width: 44px; min-height: 44px;
    display: inline-flex; align-items: center; justify-content: center; gap: 4px;
}}
.star-btn-inline.starred {{
    background: rgba(240,180,41,0.12); border-color: var(--accent);
    color: var(--accent);
}}
.star-btn-inline:hover {{ border-color: var(--accent); color: var(--accent); }}

/* ══ P04: Scan feedback animations ══ */
@keyframes cardSlideIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
.hit-card {{ animation: cardSlideIn 0.25s ease forwards; }}

@keyframes starPulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(240,180,41,0.5); }}
    70%  {{ box-shadow: 0 0 0 8px rgba(240,180,41,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(240,180,41,0); }}
}}
.star-pulse {{ animation: starPulse 0.4s ease; }}

/* ══ P04: Live scan hits panel ══ */
.live-hits-header {{
    font-family: DM Mono, monospace; font-size: 0.6rem;
    color: var(--amber); text-transform: uppercase; letter-spacing: 0.12em;
    margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;
}}
@keyframes liveDot {{
    0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.2; }}
}}
.live-dot {{
    width: 7px; height: 7px; background: var(--amber);
    border-radius: 50%; display: inline-block;
    animation: liveDot 1s ease-in-out infinite;
}}

/* ══ P05: Score arc container ══ */
.score-arc-wrap {{
    display: flex; flex-direction: column; align-items: center;
    min-width: 76px;
}}

/* ══ P05: Sector heat strip ══ */
/* ── Bar card layout ── */
.sector-heat {{
    display: flex; flex-direction: column; gap: 4px;
    padding: 0.8rem 0.9rem;
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; margin: 0.6rem 0;
}}
.sector-heat-title {{
    font-family: DM Mono, monospace; font-size: 0.55rem;
    color: var(--text-muted); text-transform: uppercase;
    letter-spacing: 0.1em; margin-bottom: 4px;
}}
.sector-row {{
    display: flex; align-items: center; gap: 8px;
    height: 24px; cursor: default;
}}
.sector-row-label {{
    font-family: DM Mono, monospace; font-size: 0.68rem;
    font-weight: 600; color: var(--text-primary);
    width: 58px; flex-shrink: 0; text-align: right;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.sector-row-bar-wrap {{
    flex: 1; background: var(--bg-raised);
    border-radius: 4px; height: 14px; overflow: hidden;
    position: relative;
}}
.sector-row-bar {{
    height: 100%; border-radius: 4px;
    transition: width 0.4s ease;
}}
.sector-row-val {{
    font-family: DM Mono, monospace; font-size: 0.68rem;
    font-weight: 700; width: 42px; flex-shrink: 0;
    text-align: left; white-space: nowrap;
}}
.sector-row-hits {{
    font-family: DM Mono, monospace; font-size: 0.6rem;
    color: var(--text-muted); width: 28px; flex-shrink: 0;
    text-align: right; white-space: nowrap;
}}

/* ══ P02: Bottom-tab nav on mobile ══ */
@media (max-width: 768px) {{
    .stTabs [data-baseweb="tab-list"] {{
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 9999 !important;
        border-radius: 0 !important;
        border-top: 1px solid var(--border) !important;
        border-left: none !important;
        border-right: none !important;
        border-bottom: none !important;
        padding: 0.3rem 0.25rem !important;
        padding-bottom: calc(0.3rem + env(safe-area-inset-bottom, 0px)) !important;
        background: rgba(15, 23, 42, 0.96) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        justify-content: space-evenly !important;
        gap: 2px !important;
        transform: translateY(0) !important;
        -webkit-transform: translateY(0) !important;
        box-shadow: 0 -2px 20px rgba(0,0,0,0.5) !important;
    }}
    .stTabs [data-baseweb="tab-list"]::after {{
        /* iOS home indicator padding */
        content: ""; display: block;
        height: env(safe-area-inset-bottom, 0px);
    }}
    .stTabs [data-baseweb="tab"] {{
        flex: 1 1 0 !important;
        flex-direction: column !important;
        font-size: 0.58rem !important;
        padding: 0.35rem 0.2rem !important;
        min-width: 0 !important;
        max-width: 25% !important;
        border-radius: 8px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        text-align: center !important;
        line-height: 1.3 !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background: rgba(245, 158, 11, 0.12) !important;
        color: var(--accent) !important;
        font-weight: 700 !important;
        border-bottom: 2px solid var(--accent) !important;
    }}
    /* Content area: pad enough for tab bar + iOS safe area + browser chrome */
    .main .block-container {{
        padding-bottom: calc(7rem + env(safe-area-inset-bottom, 34px)) !important;
        margin-bottom: 0 !important;
    }}
}}
/* Desktop: horizontal tabs at top (default Streamlit behaviour) */
@media (min-width: 769px) {{
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.5rem !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        padding: 0.6rem 1.2rem !important;
        font-size: 0.82rem !important;
        border-radius: 8px !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background: rgba(245, 158, 11, 0.1) !important;
        border-bottom: 2px solid var(--accent) !important;
    }}
}}
/* Ensure interactive controls are not obscured by the tab bar */
.stSlider, .stSelectSlider, .stRadio, .stCheckbox,
.stMultiSelect, .stSelectbox, .stButton {{
    padding-bottom: 0.3rem !important;
}}
/* Hide Streamlit footer that can block the tab bar */
footer {{ display: none !important; }}
#MainMenu {{ visibility: hidden !important; }}

/* ══ P04: Scan complete summary ══ */
.scan-summary {{
    background: var(--bg-card); border: 1px solid var(--green);
    border-radius: 16px; padding: 1.2rem 1.5rem; margin: 1rem 0;
    display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
}}
.scan-summary-stat {{
    display: flex; flex-direction: column; align-items: center; gap: 2px;
}}
.scan-summary-num {{
    font-family: DM Mono, monospace; font-size: 1.6rem; font-weight: 800;
    line-height: 1;
}}
.scan-summary-lbl {{
    font-family: DM Mono, monospace; font-size: 0.55rem;
    color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em;
}}
/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}
</style>
""", unsafe_allow_html=True)

# P04: Star pulse JS
st.markdown("""
<script>
(function() {
    function attachStarHandlers() {
        document.querySelectorAll('button[kind="secondary"]').forEach(function(btn) {
            if (btn.dataset.starHandled) return;
            btn.dataset.starHandled = "1";
            btn.addEventListener("click", function() {
                this.classList.add("star-pulse");
                var self = this;
                setTimeout(function() { self.classList.remove("star-pulse"); }, 400);
            });
        });
    }
    // Run on load and on DOM changes
    attachStarHandlers();
    var obs = new MutationObserver(attachStarHandlers);
    obs.observe(document.body, { childList: true, subtree: true });
})();
</script>
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

# min_price is set in Tab 1 — define fallback so scan loop always has it
if "min_price" not in st.session_state:
    st.session_state["min_price"] = 5

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

# ── Market cap tier definitions ───────────────────────────────────────────────
CAP_TIERS = {
    "Micro  < $300M":   (0,      0.3),
    "Small  $300M–$2B": (0.3,    2.0),
    "Mid    $2B–$10B":  (2.0,   10.0),
    "Large  $10B–$200B":(10.0, 200.0),
    "Mega   > $200B":   (200.0, None),
}

# Dollar volume labels → actual daily $ volume thresholds
# Uses average_volume_10d_calc (shares) * close price approximation.
# TradingView has no native dollar-volume field so we use share volume
# with a minimum that approximates the dollar threshold at typical prices.
# $500K/day ≈ 50K shares at $10 avg price → conservative floor
# $2M/day   ≈ 200K shares at $10 → balanced
# $5M/day   ≈ 500K shares at $10 → liquid
# $10M/day  ≈ 1M shares           → highly liquid
VOL_TIERS = {
    "$500K/day":  500_000,
    "$2M/day":    200_000,   # share-vol proxy (many stocks $10–20)
    "$5M/day":    500_000,   # share-vol proxy
    "$10M/day": 1_000_000,   # share-vol proxy
}

def fetch_tradingview_tickers(
    cap_tiers=("Small  $300M–$2B", "Mid    $2B–$10B", "Large  $10B–$200B"),
    min_share_vol=200_000,
    exchanges=("NASDAQ", "NYSE", "AMEX", "CBOE"),
    max_results=500,
    min_price=5.0,
):
    """
    Fetch tickers from TradingView screener.
    Filters: market cap tiers + min daily share volume + min price.
    min_price eliminates sub-penny stocks, OTC shells, and distressed names
    that technically pass cap/vol filters but have no institutional sponsorship.
    NO performance/correction filter — let the scanner decide signal quality.
    Sorted by dollar volume descending (most liquid first).
    """
    url = "https://scanner.tradingview.com/america/scan"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }

    # Build market cap range from selected tiers
    selected_mins = [CAP_TIERS[t][0] for t in cap_tiers if t in CAP_TIERS]
    selected_maxs = [CAP_TIERS[t][1] for t in cap_tiers if t in CAP_TIERS]
    cap_min_b = min(selected_mins) if selected_mins else 0.3
    cap_max_b = max((m for m in selected_maxs if m is not None), default=None)
    # Check if Mega is selected (no upper bound)
    if any(CAP_TIERS.get(t, (None, None))[1] is None for t in cap_tiers):
        cap_max_b = None

    filters = [
        {"left": "average_volume_10d_calc", "operation": "greater",  "right": min_share_vol},
        {"left": "close",                    "operation": "greater",  "right": min_price},
        {"left": "exchange",               "operation": "in_range", "right": list(exchanges)},
        {"left": "type",                   "operation": "equal",    "right": "stock"},  # no ETFs
    ]
    if cap_min_b > 0:
        filters.append({"left": "market_cap_basic", "operation": "greater",
                         "right": int(cap_min_b * 1e9)})
    if cap_max_b is not None:
        filters.append({"left": "market_cap_basic", "operation": "less",
                         "right": int(cap_max_b * 1e9)})

    payload = {
        "filter": filters,
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "close", "market_cap_basic", "average_volume_10d_calc",
                    "Value.Traded", "sector"],
        "sort":    {"sortBy": "Value.Traded", "sortOrder": "desc"},
        "range":   [0, max_results],
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=25)
        if r.status_code != 200:
            return [], [], f"TradingView returned HTTP {r.status_code}"
        rows = r.json().get("data", [])
        tickers = []
        meta    = []
        for row in rows:
            d = row.get("d", [])
            if not d: continue
            t = str(d[0] or "")
            if not re.match(r"^[A-Z]{1,5}$", t): continue
            tickers.append(t)
            meta.append({
                "ticker": t,
                "close":  d[1],
                "mcap_b": round(d[2] / 1e9, 2) if d[2] else None,
                "vol":    d[3],
                "sector": d[5] if len(d) > 5 else "",
            })
        return tickers, meta, None
    except Exception as e:
        return [], [], str(e)

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


def sector_heat_strip(sector_returns, hit_sectors=None):
    """
    Sector heat strip — ranked horizontal bar cards.
    Sorted best → worst 26W momentum vs SPY.
    Each row: label | filled bar | +/- % | hit count badge
    """
    if not sector_returns:
        return ""

    ETF_FULL = {
        "XLK":"Technology","XLF":"Financials","XLE":"Energy","XLV":"Healthcare",
        "XLY":"Cons Cycl","XLI":"Industrials","XLB":"Materials","XLRE":"Real Estate",
        "XLU":"Utilities","XLP":"Cons Def","XLC":"Comms","GDX":"Gold Miners",
    }
    ETF_SHORT = {
        "XLK":"Tech","XLF":"Fin","XLE":"Energy","XLV":"Health",
        "XLY":"Cons","XLI":"Indus","XLB":"Mater","XLRE":"RE",
        "XLU":"Utils","XLP":"Staples","XLC":"Comms","GDX":"GDX",
    }
    hit_sectors = hit_sectors or {}

    # Sort best → worst, include GDX, cap at 12 rows
    sorted_items = sorted(sector_returns.items(), key=lambda x: -x[1])[:12]

    # Compute bar widths: scale relative to max abs value, min bar 4%
    max_abs = max(abs(v) for _, v in sorted_items) if sorted_items else 1
    max_abs = max(max_abs, 1)

    rows_html = []
    for etf, rel in sorted_items:
        short   = ETF_SHORT.get(etf, etf)
        full    = ETF_FULL.get(etf, etf)
        sign    = "+" if rel >= 0 else ""

        # Color thresholds — matched to score_sector() logic
        if rel >= 15:
            color = "#10b981"; text_color = "#10b981"   # strong outperform — green
        elif rel >= 5:
            color = "#34d399"; text_color = "#34d399"   # mild outperform — light green
        elif rel >= -5:
            color = "#64748b"; text_color = "#94a3b8"   # neutral — muted
        elif rel >= -15:
            color = "#f97316"; text_color = "#f97316"   # mild underperform — orange
        else:
            color = "#f43f5e"; text_color = "#f43f5e"   # weak — red

        bar_w   = max(4, round(abs(rel) / max_abs * 100))
        hits    = hit_sectors.get(short, 0)
        hits_txt = f"{hits}✦" if hits else ""

        # Inline styles used as fallback — Safari sometimes ignores CSS classes
        # in Streamlit's unsafe_allow_html markdown
        rows_html.append(
            f'<div style="display:flex;align-items:center;gap:8px;height:26px;cursor:default" title="{full}: {sign}{rel}% vs SPY (26W)">'
            f'  <div style="font-family:DM Mono,monospace;font-size:0.68rem;font-weight:600;'
            f'       color:#e2e8f0;width:58px;flex-shrink:0;text-align:right;'
            f'       white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{short}</div>'
            f'  <div style="flex:1;background:#1e293b;border-radius:4px;height:14px;overflow:hidden;position:relative">'
            f'    <div style="width:{bar_w}%;background:{color};opacity:0.85;'
            f'         height:100%;border-radius:4px"></div>'
            f'  </div>'
            f'  <div style="font-family:DM Mono,monospace;font-size:0.68rem;font-weight:700;'
            f'       color:{text_color};width:48px;flex-shrink:0;text-align:left;white-space:nowrap">{sign}{rel}%</div>'
            f'  <div style="font-family:DM Mono,monospace;font-size:0.6rem;'
            f'       color:{color};width:28px;flex-shrink:0;text-align:right;white-space:nowrap">{hits_txt}</div>'
            f'</div>'
        )

    joined = "\n".join(rows_html)
    return (
        f'<div style="display:flex;flex-direction:column;gap:4px;'
        f'padding:0.8rem 0.9rem;background:#0f172a;border:1px solid #1e293b;'
        f'border-radius:12px;margin:0.6rem 0">'
        f'  <div style="font-family:DM Mono,monospace;font-size:0.55rem;'
        f'       color:#64748b;text-transform:uppercase;letter-spacing:0.1em;'
        f'       margin-bottom:4px">Sector momentum · 26W vs SPY</div>'
        f'  {joined}'
        f'</div>'
    )

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

# Sector-aware prior run thresholds
# Cyclical/commodity sectors have full cycles at 100-150%
# Growth sectors need 300%+ to signal a genuine institutional run
SECTOR_RUN_THRESHOLDS = {
    "Energy":             150,
    "Materials":          150,
    "Industrials":        200,
    "Utilities":          120,
    "Real Estate":        120,
    "Financials":         200,
    "Consumer Staples":   150,
    "Consumer Discretionary": 250,
    "Health Care":        250,
    "Communication Services": 300,
    "Technology":         300,
    "Unknown":            300,  # conservative default
}

def get_sector_run_threshold(ticker):
    """Return the min prior run % for this stock's sector."""
    _, sector = get_stock_sector_etf(ticker)
    return SECTOR_RUN_THRESHOLDS.get(sector, 300)

# Known ADR tickers — common foreign names trading as ADRs on US exchanges
# Used to switch from absolute volume floor to relative volume check
_KNOWN_ADRS = {
    "BHP", "RIO", "VALE", "SID", "PBR", "CX", "BABA", "JD", "NIO", "XPEV",
    "LI", "BIDU", "TME", "BILI", "IQ", "WB", "GRAB", "SE", "SHOP", "ASML",
    "TSM", "UMC", "SNY", "AZN", "NVS", "RHHBY", "BAYRY", "SAP", "SIEGY",
    "TM", "HMC", "SONY", "SAN", "BBVA", "IBN", "HDB", "INFY", "WIT",
    "BP", "SHEL", "TOT", "E", "ENI", "EQNR", "STO",
}

def is_adr(ticker):
    return ticker.upper() in _KNOWN_ADRS


# ── Design System Helpers ─────────────────────────────────────────────────────

def score_arc(score, category="watch"):
    """
    SVG semicircle arc — Principle 05.
    score: 0-100
    category: full / strong / watch
    Returns raw HTML string (no extra wrapper needed).
    """
    colors = {
        "full":   "#10b981",   # green
        "strong": "#f59e0b",   # amber
        "watch":  "#818cf8",   # indigo
    }
    c = colors.get(category, "#818cf8")
    r = 30
    cx, cy = 38, 38
    circ = 3.14159 * r
    prog = max(0, min(1, score / 100)) * circ
    # Track arc (grey)
    track = f'<path d="M {cx-r} {cy} A {r} {r} 0 0 1 {cx+r} {cy}" fill="none" stroke="#1a1d27" stroke-width="7" stroke-linecap="round"/>'
    # Progress arc
    filled = f'<path d="M {cx-r} {cy} A {r} {r} 0 0 1 {cx+r} {cy}" fill="none" stroke="{c}" stroke-width="7" stroke-linecap="round" stroke-dasharray="{prog:.1f} {circ:.1f}" style="filter:drop-shadow(0 0 5px {c}88)"/>'
    # Score text
    text = f'<text x="{cx}" y="{cy-4}" text-anchor="middle" fill="{c}" style="font-size:14px;font-weight:800;font-family:DM Mono,monospace">{score}</text>'
    sub  = f'<text x="{cx}" y="{cy+9}" text-anchor="middle" fill="#4a5068" style="font-size:8px;font-family:DM Mono,monospace">/100</text>'
    glow = f'<circle cx="{cx}" cy="{cy}" r="{r+8}" fill="{c}" opacity="0.03"/>'
    return f'<svg width="76" height="46" viewBox="0 0 76 46" style="overflow:visible">{glow}{track}{filled}{text}{sub}</svg>'

def signal_summary(wr, dr, rr, is_retest):
    """
    2-3 word signal tag — Principle 01/04.
    Distils the most important signal into a one-line verdict.
    """
    tags = []
    if is_retest:
        # Most important signals first
        if wr.get("undercut_reclaim"):
            tags.append("U&R")
        slope = wr.get("sma200_slope_grade", "declining")
        if slope == "rising":
            tags.append("SMA ↑")
        struct = rr.get("structure", "none")
        if struct == "ma_stack":
            tags.append("MA stack")
        elif struct == "bounce_ema":
            tags.append("EMA bounce")
        elif struct == "first_pullback":
            tags.append("1st pullback")
        if wr.get("multiyear_vol_high"):
            tags.append("3yr vol")
        elif wr.get("pass_volume_surge"):
            tags.append("Vol surge")
        corr = wr.get("correction_from_ath_pct", 0)
        if corr >= 70:
            tags.append(f"Corr {corr:.0f}%")
        if wr.get("resistance_flip"):
            tags.append("R→S flip")
    else:
        sub = wr.get("base_subtype", "commodity")
        tags.append("Growth base" if sub == "growth" else "Commodity base")
        dot_stage = dr.get("post_dot_stage")
        if dot_stage == "breakout":
            tags.append("⚡ Breakout")
        elif dot_stage == "basing":
            tags.append("⚡ Basing")
        elif dot_stage == "ma_reclaim":
            tags.append("⚡ MA reclaim")
        if wr.get("pass_volume_surge"):
            tags.append("Vol surge")
    return " · ".join(tags[:3]) if tags else "Setup forming"

def correction_bar(corr_pct, color):
    """
    Horizontal fill bar showing correction depth — Principle 05.
    Deeper correction = longer bar = more interesting setup.
    """
    fill = min(100, corr_pct)
    return (
        f'<div style="display:flex;align-items:center;gap:0.5rem;margin-top:0.3rem">'
        f'<div style="flex:1;height:3px;background:#1a1d27;border-radius:2px;overflow:hidden">'
        f'<div style="width:{fill:.0f}%;height:100%;background:{color};border-radius:2px;'
        f'box-shadow:0 0 4px {color}66;transition:width 0.4s ease"></div></div>'
        f'<span style="font-family:DM Mono,monospace;font-size:0.58rem;color:#4a5068;white-space:nowrap">Corr {corr_pct:.0f}%</span>'
        f'</div>'
    )

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

def calc_atr_pct(df, period=14, use_median=True):
    """
    ATR as % of close. use_median=True uses median TR to reduce earnings
    gap noise — a single gap week inflates mean ATR for the full period,
    causing valid post-earnings coiling setups to fail the ATR filter.
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]
    prev  = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    if use_median:
        atr_val = tr.iloc[-period:].median() if len(tr) >= period else tr.median()
    else:
        atr_val = tr.rolling(period).mean().iloc[-1]
    return float(atr_val / close.iloc[-1] * 100)

def check_weekly(df_w, w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult, ticker=None):
    """
    Weekly retest criteria.
    ticker: if provided, uses sector-aware run threshold (commodities need less
    prior run than tech to be considered a genuine institutional cycle).
    """
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

    # Sector-aware run threshold — commodity/cyclical cycles are smaller than tech
    if ticker:
        sector_run_min = get_sector_run_threshold(ticker)
        effective_run_min = min(w_prior_run, sector_run_min)
    else:
        effective_run_min = w_prior_run

    # ── Volume: best of 4W rolling OR peak single week in last 12W ────────────
    # Catches both sustained accumulation AND a single explosive volume week.
    avg_vol_20w = vols.rolling(20).mean().iloc[-1]
    avg_vol_4w  = vols.rolling(4).mean().iloc[-1]
    peak_12w    = vols.iloc[-12:].max() if len(vols) >= 12 else vols.max()
    vr_rolling  = avg_vol_4w  / avg_vol_20w if avg_vol_20w > 0 else 0
    vr_peak     = peak_12w    / avg_vol_20w if avg_vol_20w > 0 else 0
    vr          = max(vr_rolling, vr_peak)

    # ── FIX 5: ADR relative volume ───────────────────────────────────────────
    # ADRs have structurally lower absolute share volume than domestic names.
    # For ADRs, measure vol vs own 52W history rather than absolute level.
    # This prevents BHP/ASML/TSM being filtered for "low volume" unfairly.
    adr_flag = is_adr(ticker) if ticker else False
    if adr_flag and avg_vol_20w > 0:
        # Vol rank: where does recent 4W sit in its own 52W distribution?
        vol_52w = vols.iloc[-52:] if len(vols) >= 52 else vols
        vol_pct_rank = (avg_vol_4w > vol_52w).mean() * 100  # percentile
        # Override vr with percentile-based equivalent if ADR
        # 80th percentile → treat as 1.5× (good), 95th → 2.5× (strong)
        if vol_pct_rank >= 95:
            vr = max(vr, 2.5)
        elif vol_pct_rank >= 80:
            vr = max(vr, 1.5)
        elif vol_pct_rank >= 60:
            vr = max(vr, 1.2)
    else:
        adr_flag = False
        vol_pct_rank = None

    # ── FIX 3: Multi-year volume high ──────────────────────────────────────────
    # Is the recent volume surge the highest in 3 years (156 weeks)?
    # This is a different magnitude of signal to a ratio — it means institutions
    # entered at a scale not seen since the last major cycle.
    vol_lookback = min(156, len(vols) - 1)
    hist_vol_max = vols.iloc[-vol_lookback:-1].max() if vol_lookback > 1 else 0
    recent_peak  = vols.iloc[-12:].max() if len(vols) >= 12 else vols.max()
    multiyear_vol_high = recent_peak >= hist_vol_max * 0.95  # within 5% of 3yr high
    vol_rank_pct = (recent_peak / hist_vol_max * 100) if hist_vol_max > 0 else 0

    # ── FIX 2: Undercut and reclaim of 200W SMA ──────────────────────────────
    # Look back 8 weeks for any week where:
    #   weekly low < 200W SMA AND weekly close > 200W SMA
    # This is the capitulation wick pattern — stronger than a clean touch.
    # The false breakdown flushes weak holders and traps short sellers.
    highs_w = df_w["high"]
    lows_w  = df_w["low"]
    undercut_reclaim = False
    undercut_reclaim_weeks_ago = None
    lookback_uc = min(8, len(closes) - 1)
    for _i in range(1, lookback_uc + 1):
        _sma = sma200_series.iloc[-_i] if len(sma200_series) >= _i else sma200
        _lo  = lows_w.iloc[-_i]
        _cl  = closes.iloc[-_i]
        if _lo < _sma and _cl > _sma:
            undercut_reclaim = True
            undercut_reclaim_weeks_ago = _i
            break

    # ── 200W SMA Slope — graded, normalised, with deceleration check ────────────
    # Raw slope is dollar-denominated and not comparable across price levels.
    # Normalised slope = (sma[-1] - sma[-5]) / sma[-5] * 100  (% change over 5W)
    # Acceleration = difference in 5W slope between two consecutive 5W windows.
    # Positive acceleration = slope is improving (less negative or more positive).
    if len(sma200_series) >= 10:
        sma_now   = sma200_series.iloc[-1]
        sma_5w    = sma200_series.iloc[-5]
        sma_10w   = sma200_series.iloc[-9]   # start of prior 5W window
        slope_now = (sma_now  - sma_5w)  / sma_5w  * 100 if sma_5w  > 0 else 0
        slope_5w  = (sma_5w   - sma_10w) / sma_10w * 100 if sma_10w > 0 else 0
        slope_accel = slope_now - slope_5w   # positive = flattening/turning
    else:
        slope_now   = 0.0
        slope_5w    = 0.0
        slope_accel = 0.0

    # Slope grade:
    #   "rising"      slope_now > +0.10%
    #   "flattening"  slope_now between -0.10% and +0.10% OR accel > 0.05 while declining
    #   "declining"   slope_now < -0.10% and still deteriorating
    if slope_now >= 0.10:
        slope_grade = "rising"
    elif slope_now >= -0.10 or (slope_now < -0.10 and slope_accel >= 0.05):
        slope_grade = "flattening"
    else:
        slope_grade = "declining"

    pass_dist = (-w_dist_200sma_lo <= dist <= w_dist_200sma_hi)

    res.update({
        "dist_200sma_pct":        round(dist, 2),
        "sma200":                 round(sma200, 2),
        "current_close":          round(cur, 2),
        "prior_run_pct":          round(run, 1),
        "correction_from_ath_pct":round(corr, 1),
        "vol_ratio":              round(vr, 2),
        "sma200_slope_pct":       round(slope_now, 3),
        "sma200_slope_accel":     round(slope_accel, 3),
        "sma200_slope_grade":     slope_grade,
        # keep legacy key for base breakout compat
        "sma200_slope":           round(slope_now, 3),
        "pass_200sma_proximity":  pass_dist,
        "pass_prior_run":         run >= effective_run_min,
        "sector_run_min":         effective_run_min,
        "pass_correction":        corr >= w_correction,
        "pass_volume_surge":      vr >= w_vol_mult,
        "pass_sma200_slope":      slope_grade != "declining",
        "undercut_reclaim":       undercut_reclaim,
        "undercut_reclaim_wks":   undercut_reclaim_weeks_ago,
        "multiyear_vol_high":     multiyear_vol_high,
        "vol_rank_pct":           round(vol_rank_pct, 0),
        "adr_flag":               adr_flag,
        "adr_vol_pct_rank":       round(vol_pct_rank, 0) if vol_pct_rank is not None else None,
    })
    # ── FIX 4: Resistance flip to support ──────────────────────────────────────
    # Find the highest weekly close in a 3-month window that ended 6+ months ago.
    # If current price is sitting within 3% above that level, it flipped to support.
    res_flip = False
    res_flip_level = None
    if len(closes) >= 52:
        # Resistance window: 26W to 52W ago (roughly 6-12 months back)
        res_window = closes.iloc[-52:-26]
        if len(res_window) > 0:
            prior_resistance = res_window.max()
            # Current price within 0–3% above that resistance level
            dist_from_res = (cur - prior_resistance) / prior_resistance * 100
            if 0 <= dist_from_res <= 3.0:
                res_flip = True
                res_flip_level = round(prior_resistance, 2)

    res["resistance_flip"]       = res_flip
    res["resistance_flip_level"] = res_flip_level

    passed = all([res["pass_200sma_proximity"], res["pass_prior_run"],
                  res["pass_correction"], res["pass_volume_surge"]])
    return passed, res

def check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma):
    """
    Daily checks + two-stage ATR-exhaustion signal.

    Stage 1 — Alert (yellow dot):
        Did price reach ≤ −10× ATR from the rising 50D SMA at any point
        in the last 60 days? If yes, yellow_dot_fired = True.
        This is context only — no points awarded.

    Stage 2 — Response (what happened after the dot):
        "ma_reclaim"  +8pts  — price crossed back above rising 10D EMA,
                                volume expanding, EMA slope turning up
        "basing"      +8pts  — ATR contracting, price coiling in <3% range,
                                volume drying up (base forming, not yet broken)
        "breakout"   +12pts  — price breaks above 5-day range top with vol surge
        "watching"     0pts  — dot fired but no actionable response yet
        None                 — dot never fired, signal irrelevant
    """
    res = {}
    if len(df_d) < 55:
        return False, {"error": "short"}

    closes  = df_d["close"]
    highs   = df_d["high"]
    lows    = df_d["low"]
    vols    = df_d["volume"]
    cur     = closes.iloc[-1]

    sma50_series = calc_sma(closes, 50)
    ema10_series = calc_ema(closes, 10)
    ema20_series = calc_ema(closes, 20)

    sma50 = sma50_series.iloc[-1]
    ema10 = ema10_series.iloc[-1]
    ema20 = ema20_series.iloc[-1]
    atr   = calc_atr_pct(df_d)
    p50   = (cur - sma50) / sma50 * 100
    ema_sp = (ema10 - ema20) / ema20 * 100
    hi     = highs.iloc[-1]
    lo     = lows.iloc[-1]
    rng_pos = (cur - lo) / (hi - lo) if hi != lo else 0.5

    # ── 50D SMA slope ─────────────────────────────────────────────────────────
    sma50_slope = (sma50_series.iloc[-1] - sma50_series.iloc[-20])                   / sma50_series.iloc[-20] * 100                   if len(sma50_series) >= 20 and sma50_series.iloc[-20] > 0 else 0
    sma50_rising = sma50_slope > 0

    # ── Current ATR multiple from 50D ─────────────────────────────────────────
    atr_abs = atr / 100 * cur  # ATR in dollar terms
    atr_mult_from_50d = (cur - sma50) / atr_abs if atr_abs > 0 else 0

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 1 — Yellow dot: did ≤ −10× ATR fire in last 60 days?
    # ══════════════════════════════════════════════════════════════════════════
    yellow_dot_fired  = False
    yellow_dot_day    = None   # how many days ago the most recent dot fired
    lookback_d        = min(60, len(closes) - 1)

    for i in range(1, lookback_d + 1):
        day_close = closes.iloc[-i]
        day_sma50 = sma50_series.iloc[-i] if len(sma50_series) >= i else sma50
        day_atr_abs = atr_abs  # use current ATR as proxy (stable enough over 60D)
        if day_atr_abs > 0:
            day_mult = (day_close - day_sma50) / day_atr_abs
            if day_mult <= -10.0:
                yellow_dot_fired = True
                yellow_dot_day   = i
                break   # find most recent occurrence

    # ══════════════════════════════════════════════════════════════════════════
    # STAGE 2 — Response detection (only if dot fired)
    # ══════════════════════════════════════════════════════════════════════════
    post_dot_stage = None
    post_dot_pts   = 0

    if yellow_dot_fired and yellow_dot_day is not None:
        # ── A) Base Breakout ─────────────────────────────────────────────────
        # Price breaks above the 5-day range top (measured from just before
        # today) with a volume surge — strongest signal, highest pts
        if len(closes) >= 6:
            range_5d_high = highs.iloc[-6:-1].max()
            range_5d_low  = lows.iloc[-6:-1].min()
            avg_vol_20d   = vols.rolling(20).mean().iloc[-1]
            vol_today     = vols.iloc[-1]
            broke_out     = cur > range_5d_high * 1.005   # 0.5% buffer
            vol_surge     = vol_today > avg_vol_20d * 1.5
            if broke_out and vol_surge and sma50_rising:
                post_dot_stage = "breakout"
                post_dot_pts   = 12

        # ── B) MA Reclaim ────────────────────────────────────────────────────
        # Price has crossed back above the rising 10D EMA after having been
        # below it. Volume on the reclaim is above average.
        if post_dot_stage is None and len(closes) >= 5:
            # Was below EMA10 yesterday, above today
            was_below = closes.iloc[-2] < ema10_series.iloc[-2]
            now_above = cur >= ema10_series.iloc[-1]
            ema10_slope_5d = (ema10_series.iloc[-1] - ema10_series.iloc[-5])                               / ema10_series.iloc[-5] * 100                               if len(ema10_series) >= 5 and ema10_series.iloc[-5] > 0 else 0
            ema10_turning  = ema10_slope_5d >= 0   # flattening or rising
            vol_expanding  = vols.iloc[-1] > vols.rolling(20).mean().iloc[-1] * 1.2
            if was_below and now_above and ema10_turning and sma50_rising:
                post_dot_stage = "ma_reclaim"
                post_dot_pts   = 8

        # ── C) Basing ────────────────────────────────────────────────────────
        # ATR contracting + price coiling in narrow range + volume drying up
        # Means institutions are absorbing supply quietly after the selloff
        if post_dot_stage is None and len(closes) >= 15:
            atr_5d  = calc_atr_pct(df_d.iloc[-5:])   if len(df_d) >= 5  else atr
            atr_10d = calc_atr_pct(df_d.iloc[-15:-5]) if len(df_d) >= 15 else atr
            range_5d_hi = highs.iloc[-5:].max()
            range_5d_lo = lows.iloc[-5:].min()
            range_5d_pct = (range_5d_hi - range_5d_lo) / range_5d_lo * 100                            if range_5d_lo > 0 else 999
            avg_vol_20d  = vols.rolling(20).mean().iloc[-1]
            avg_vol_5d   = vols.iloc[-5:].mean()
            atr_contracting = atr_5d < atr_10d * 0.80   # 20%+ contraction
            coiling         = range_5d_pct < 4.0         # price in <4% range
            vol_drying      = avg_vol_5d < avg_vol_20d * 0.8
            if atr_contracting and coiling and sma50_rising:
                post_dot_stage = "basing"
                post_dot_pts   = 10 if vol_drying else 8   # extra if vol also dry

        # ── D) Watching ──────────────────────────────────────────────────────
        # Dot fired but no clear response pattern yet — on radar, not actionable
        if post_dot_stage is None:
            post_dot_stage = "watching"
            post_dot_pts   = 0

    res.update({
        "atr_pct":            round(atr, 2),
        "pct_above_50sma":    round(p50, 2),
        "ema10_vs_ema20_pct": round(ema_sp, 2),
        "candle_range_position": round(rng_pos, 2),
        "atr_mult_from_50d":  round(atr_mult_from_50d, 2),
        "sma50_rising":       sma50_rising,
        "yellow_dot_fired":   yellow_dot_fired,
        "yellow_dot_day":     yellow_dot_day,
        "post_dot_stage":     post_dot_stage,
        "post_dot_pts":       post_dot_pts,
        "pass_atr":           d_atr_pct_min <= atr <= d_atr_pct_max,
        "pass_50sma":         -40 <= p50 <= d_above_50sma,
        "pass_ema_cross":     ema_sp > -5,
        "pass_candle_position": rng_pos >= 0.4,
        # Legacy key — True if currently AT the dot level (for retest mode compat)
        "pass_atr_mult":      yellow_dot_fired and post_dot_stage != "watching",
    })
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

    # ── Sub-type detection ────────────────────────────────────────────────────
    # Growth stock base (PLTR style):
    #   - 200W SMA well below price (price never retested it, SMA still rising)
    #   - MAs beginning to stack in bull order
    #   - Base tighter on shorter timeframe (18mo vs 3yr)
    # Commodity cycle base (KGC style):
    #   - Price near 200W SMA (just breaking above)
    #   - Longer multi-year base
    #   - Lower ATR expected during base
    ema10w = calc_ema(closes, 10).iloc[-1]  if len(closes) >= 10  else cur
    ema20w = calc_ema(closes, 20).iloc[-1]  if len(closes) >= 20  else cur
    sma50w = calc_sma(closes, min(50, len(closes)-1)).iloc[-1]
    ma_stack = (cur > ema10w > ema20w > sma50w > sma200)
    ma_partial = sum([cur > ema10w, ema10w > ema20w, ema20w > sma50w, sma50w > sma200]) >= 3
    # Growth: price >50% above 200W SMA, MAs stacking, base was 12-30 months
    is_growth_base = dist > 50 and (ma_stack or ma_partial) and duration_weeks <= 130
    # Commodity: price within 40% of 200W SMA, longer base typical
    is_commodity_base = dist <= 60
    sub_type = "growth" if is_growth_base else "commodity"

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
        "sub_type":           sub_type,
        "ma_stack":           ma_stack,
        "ma_partial":         ma_partial,
        "ema10w":             round(ema10w, 2),
        "ema20w":             round(ema20w, 2),
        "sma50w":             round(sma50w, 2),
        # Compat fields for shared badge renderer
        "pass_prior_run":     True,
        "correction_from_ath_pct": 0,
        "prior_run_pct":      0,
    })
    # ── Sub-type detection: Growth Stock Base vs Commodity Cycle ────────────────
    # Growth base: shorter history OK, higher ATR acceptable, MA stack forming,
    #   stock recently broke out of base (dist from 200W SMA elevated),
    #   typically tech/AI/healthcare sector
    # Commodity cycle: longer base, lower ATR, 200W SMA acts as floor,
    #   vol surge at breakout is primary signal
    #
    # Heuristic: if base_atr > 3% OR dist > 50% above 200W SMA → growth profile
    if base_atr > 3.0 or dist > 50:
        base_subtype = "growth"
        # Growth: relax base duration (min 12 months), tighter vol requirement
        pass_duration_growth = duration_weeks >= 52
    else:
        base_subtype = "commodity"
        pass_duration_growth = pass_duration

    res["base_subtype"]        = base_subtype
    res["pass_duration_typed"] = pass_duration_growth

    passed = all([pass_sma, pass_range, pass_atr_base, pass_vol,
                  pass_duration_growth if base_subtype == "growth" else pass_duration])
    return passed, res

def score_base_breakout(br, dr):
    """
    Base Breakout scoring — sub-typed for Growth vs Commodity.
    Growth base: shorter duration OK, higher ATR acceptable, MA stack forming.
    Commodity cycle: longer base, lower ATR, 200W SMA proximity critical.
    ATR-multiple-from-50D bonus: rewards precise pullback entry (PLTR signal).
    """
    pts = 0
    subtype = br.get("base_subtype", "commodity")

    if subtype == "growth":
        # Growth: base range + vol + MA stack more important than duration
        if br.get("pass_200sma_proximity"): pts += 15   # less critical — can be well above
        if br.get("pass_base_range"):       pts += 20
        if br.get("pass_base_atr"):         pts += 15   # relaxed — growth is volatile
        if br.get("pass_volume_surge"):     pts += 25   # most important for growth breakouts
        if br.get("pass_duration_typed"):   pts += 10
        if br.get("pass_sma200_slope"):     pts += 5
        if dr.get("pass_atr"):              pts += 5
        if dr.get("pass_50sma"):            pts += 5    # MA stack alignment
        # ATR-exhaustion response bonus — points come from Stage 2, not Stage 1
        # Stage 1 (dot firing) = alert only, no pts
        # Stage 2 (response):  breakout=12, basing=8-10, ma_reclaim=8, watching=0
        pts += dr.get("post_dot_pts", 0)
        if dr.get("pass_ema_cross"):        pts += 3
        if dr.get("pass_candle_position"):  pts += 2
        # partial: -13 for the 15 not awarded on proximity
    else:
        # Commodity: proximity + duration + vol all equally critical
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
    SMA slope  (0-8pts): graded — rising=8, flattening=5, declining=0
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

    # 200W SMA slope — graded 0/3/5/8pts
    slope_grade = wr.get("sma200_slope_grade", "declining")
    slope_accel = wr.get("sma200_slope_accel", 0)
    if slope_grade == "rising":
        pts += 8    # cleanest signal — SMA actively rising
    elif slope_grade == "flattening":
        pts += 5    # floor forming — acceptable for early-stage setups
    else:
        pts += 0    # still declining — penalise, PYPL/ENPH style trap

    # Binary daily criteria
    if dr.get("pass_atr"):              pts += 5
    if dr.get("pass_50sma"):            pts += 5
    if dr.get("pass_ema_cross"):        pts += 3
    if dr.get("pass_candle_position"):  pts += 2

    # Fix 4 bonus: resistance flip to support (+5pts)
    if wr.get("resistance_flip"):
        pts += 5

    # Fix 2 bonus: undercut and reclaim of 200W SMA (+8pts)
    # Most powerful when recent (within 4W) — decays to 4pts for older signals
    if wr.get("undercut_reclaim"):
        wks = wr.get("undercut_reclaim_wks", 8)
        pts += 8 if wks <= 4 else 4

    # Fix 3 bonus: multi-year volume high (+6pts)
    # Institutional participation at a scale not seen since last cycle
    if wr.get("multiyear_vol_high"):
        pts += 6

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
        "ticker": "NVDA",
        "date": "2024-01-08",
        "label": "NVIDIA — Jan 2024 (ideal entry)",
        "desc": "Post-consolidation breakout after the Jan 2023 bottom. 200W SMA now "
                "rising strongly. MAs stacking in bull order. First clean weekly close "
                "above all key MAs with expanding volume — the textbook re-entry.",
        "expected_score": 85,
    },
    {
        "ticker": "AMD",
        "date": "2022-10-17",
        "label": "AMD — Oct 2022 (200W SMA retest)",
        "desc": "~70% correction from $164 ATH. 200W SMA beginning to flatten after "
                "steep decline. Massive prior run 2018–2021. Similar setup to NVDA Jan 2023 "
                "— AI/data centre tailwind drove subsequent 300%+ run.",
        "expected_score": 75,
    },
    {
        "ticker": "COIN",
        "date": "2023-01-09",
        "label": "Coinbase — Jan 2023 (crypto cycle bottom)",
        "desc": "~90% correction from $430 ATH during crypto winter. 200W SMA beginning "
                "to flatten. Accumulated at lows before BTC ETF approval catalyst. "
                "Ran from ~$30 to $280+ in 2023-2024.",
        "expected_score": 70,
    },
    {
        "ticker": "PYPL",
        "date": "2023-01-09",
        "label": "PayPal — Jan 2023 ⚠ TRAP",
        "desc": "NEGATIVE EXAMPLE: 200W SMA still steeply declining at entry. No base "
                "formed, no accumulation volume, no macro catalyst. Price drifted sideways "
                "for 2 years. Kept as a calibration trap — scanner should score this LOW.",
        "expected_score": 45,
        "is_trap": True,
    },
    {
        "ticker": "ENPH",
        "date": "2023-10-30",
        "label": "Enphase Energy — Oct 2023 ⚠ TRAP",
        "desc": "NEGATIVE EXAMPLE: Still in freefall at entry date. 200W SMA declining "
                "steeply, never retested, correction ongoing to $47 by Feb 2026. "
                "Kept as calibration — scanner should score this LOW.",
        "expected_score": 40,
        "is_trap": True,
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
    {
        "ticker": "PLTR",
        "date": "2024-10-28",
        "label": "Palantir — Oct 2024 (growth base entry)",
        "desc": "Multi-year base 2022–2024 between $6–$20. 200W SMA well below "
                "price (~$12) — growth stock base, not a SMA retest. "
                "MAs stacking in bull order. First ATR-zone yellow dot appears. "
                "Broke out from base top to $125+ by Feb 2026.",
        "expected_score": 72,
        "mode": "base_breakout",
    },
    {
        "ticker": "PLTR",
        "date": "2024-11-04",
        "label": "Palantir — Nov 2024 (growth base breakout)",
        "desc": "Multi-year base from 2022–2024 between $6–$20. Full MA stack "
                "forming (EMA10=$42.55, EMA20=$36.92, SMA50=$26.66, SMA200=$18.40). "
                "Massive vol surge on election week (604M shares). Price broke "
                "above 200W SMA and accelerated. ATR-mult from 50D = ideal pullback zone. "
                "Classic growth base breakout — NOT a 200W SMA retest.",
        "expected_score": 72,
        "mode": "base_breakout",
    },
    {
        "ticker": "BHP",
        "date": "2025-01-13",
        "label": "BHP Group — Jan 2025 (commodity retest)",
        "desc": "53% correction from $85 ATH to $39.73 low. 200W SMA rising throughout — "
                "never lost upward angle. Classic undercut and reclaim: weekly low briefly "
                "below 200W SMA then snapped back above. Highest volume in 3 years on "
                "breakout. ADR on NYSE — relative vol used. Prior run ~110% "
                "(commodities threshold, not 300% tech threshold).",
        "expected_score": 68,
        "mode": "retest",
    },
    {
        "ticker": "PLTR",
        "date": "2024-10-30",
        "label": "Palantir — Oct 2024 (first yellow dot)",
        "desc": "First yellow dot fires — price extended −10× ATR below the rising 50D SMA. "
                "This exhaustion level marked the final shakeout before the Nov surge. "
                "Volume quiet, 50D rising, MAs stacking — textbook growth base entry.",
        "expected_score": 65,
        "mode": "base_breakout",
    },
]

def get_yf_data_asof(ticker, as_of_date, lookback_years=12, freq="1wk"):
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
    df_w = get_yf_data_asof(ticker, as_of_date, lookback_years=10, freq="1wk")
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
tab1, tab2, tab4, tab3 = st.tabs(["🔍 Pre-Filter", "🚀 Scanner", "⭐ Watchlist", "🕰 Backtest"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TRADINGVIEW PRE-FILTER
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── Header status chip ────────────────────────────────────────────────────
    loaded_count = len(st.session_state.get("finviz_tickers", []))
    status_color = "var(--green)" if loaded_count > 0 else "var(--text-muted)"
    status_text  = f"{loaded_count} tickers ready" if loaded_count > 0 else "No universe loaded — scanner will use S&P 500"

    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.2rem">' +
        f'<div><div style="font-size:1.05rem;font-weight:700;color:var(--text-primary)">Universe Builder</div>' +
        f'<div style="font-family:DM Mono,monospace;font-size:0.68rem;color:var(--text-muted);margin-top:0.2rem">' +
        f'Volume-first filter — pull everything tradeable, let the scorer decide quality' +
        f'</div></div>' +
        f'<div style="font-family:DM Mono,monospace;font-size:0.72rem;color:{status_color};' +
        f'background:var(--bg-raised);border:1px solid var(--border);border-radius:8px;padding:0.4rem 0.9rem">' +
        f'{status_text}</div></div>',
        unsafe_allow_html=True)

    # ── Philosophy callout ────────────────────────────────────────────────────
    st.markdown('''
    <div class="info-box">
    <b style="color:var(--accent)">Volume is the only hard filter here.</b>
    A stock with no volume is untradeable regardless of how well it scores technically.
    Everything else — correction depth, prior run, SMA proximity — is handled by the
    scorer in Tab 2. This means you pull in a wider pool and let the scoring system
    surface the quality, rather than pre-filtering signal away before you even see it.<br><br>
    No performance filter. No correction depth preset. Just: <i>is this stock liquid enough to trade?</i>
    </div>
    ''', unsafe_allow_html=True)

    # ── Controls: 3 columns ───────────────────────────────────────────────────
    col_caps, col_vol, col_size = st.columns([2, 1, 1], gap="large")

    with col_caps:
        st.markdown('<div class="section-header">Market Cap Tiers</div>', unsafe_allow_html=True)
        st.caption("Select which cap tiers to include — union of selected ranges")

        # Cap tier descriptions with context
        tier_labels = list(CAP_TIERS.keys())
        tier_help = {
            "Micro  < $300M":    "Rarely has institutional cycles. High noise, wide spreads. Use cautiously.",
            "Small  $300M–$2B":  "Occasional gems (LITE, early KGC). Higher vol floor recommended.",
            "Mid    $2B–$10B":   "Sweet spot. Best retest setups live here — big enough for institutions, small enough to move.",
            "Large  $10B–$200B": "Clean setups, liquid. NVDA, META, TSLA at their retest dates.",
            "Mega   > $200B":    "AAPL, MSFT. Rarely correct 40%+. Include only for bear market scans.",
        }

        selected_tiers = []
        for tier in tier_labels:
            lo, hi = CAP_TIERS[tier]
            hi_str = f"${hi}B" if hi else "no limit"
            default_on = tier in ("Small  $300M–$2B", "Mid    $2B–$10B", "Large  $10B–$200B")
            checked = st.checkbox(
                f"{tier}",
                value=default_on,
                help=tier_help[tier],
                key=f"tier_{tier}"
            )
            if checked:
                selected_tiers.append(tier)

        if not selected_tiers:
            st.warning("Select at least one cap tier.")
            selected_tiers = ["Mid    $2B–$10B"]  # fallback

    with col_vol:
        st.markdown('<div class="section-header">Min Daily Volume</div>', unsafe_allow_html=True)
        st.caption("Dollar volume floor — filters out illiquid names")

        vol_choice = st.radio(
            "Volume floor",
            list(VOL_TIERS.keys()),
            index=1,  # default $2M/day
            help="$2M/day is the balanced default — catches mid-caps like LITE while filtering genuine illiquid stocks",
            label_visibility="collapsed"
        )
        min_share_vol = VOL_TIERS[vol_choice]

        st.markdown(
            f'<div style="margin-top:1rem;font-family:DM Mono,monospace;font-size:0.65rem;color:var(--text-muted)">' +
            f'Using share vol proxy: {min_share_vol:,} avg shares/day' +
            f'</div>',
            unsafe_allow_html=True)

        st.markdown('<div class="section-header" style="margin-top:1.5rem">Min Price</div>', unsafe_allow_html=True)
        st.caption("Exclude stocks trading below this price")
        min_price = st.select_slider(
            "Min price",
            options=[1, 2, 5, 10, 15, 20],
            value=st.session_state.get("min_price", 5),
            label_visibility="collapsed",
            help="$5 default removes most distressed/shell names while keeping genuine small-caps. "
                 "$10+ if you want to focus on stocks with real institutional interest."
        )
        st.session_state["min_price"] = min_price
        st.markdown(
            f'<div style="font-family:DM Mono,monospace;font-size:0.65rem;color:var(--text-muted);margin-top:0.3rem">'
            f'Filtering: close > ${min_price}</div>',
            unsafe_allow_html=True)

        st.markdown('<div class="section-header" style="margin-top:1.5rem">Exchanges</div>', unsafe_allow_html=True)
        # CBOE added — covers stocks that list/transfer away from NYSE/NASDAQ
        # NYSE + NASDAQ + AMEX + CBOE captures all US-listed common stocks
        exchanges = st.multiselect(
            "Exchanges",
            ["NYSE", "NASDAQ", "AMEX", "CBOE"],
            default=["NYSE", "NASDAQ", "AMEX", "CBOE"],
            label_visibility="collapsed",
            help="NYSE+NASDAQ+AMEX+CBOE = full US listed stock universe. "
                 "AMEX skews small/micro. CBOE captures transfers from NASDAQ. "
                 "OTC excluded — volume floor filters most illiquid names anyway."
        )

    with col_size:
        st.markdown('<div class="section-header">Scan Size</div>', unsafe_allow_html=True)
        st.caption("How many tickers to fetch from TradingView")

        max_tv_results = st.slider(
            "Max tickers",
            min_value=100,
            max_value=1000,
            value=500,
            step=50,
            label_visibility="collapsed",
            help="Sorted by $ volume descending — so the 500 most liquid names come first"
        )

        # Estimated scan time
        est_min = round(max_tv_results * 1.2 / 60, 0)
        est_max = round(max_tv_results * 1.8 / 60, 0)
        time_color = "var(--green)" if max_tv_results <= 300 else ("var(--amber)" if max_tv_results <= 600 else "var(--red)")
        st.markdown(
            f'<div style="margin-top:0.8rem;font-family:DM Mono,monospace;font-size:0.68rem">' +
            f'<span style="color:{time_color}">≈ {est_min:.0f}–{est_max:.0f} min scan time</span>' +
            f'</div>',
            unsafe_allow_html=True)

        # Cap tier summary
        if selected_tiers:
            mins_b = [CAP_TIERS[t][0] for t in selected_tiers]
            maxs_b = [CAP_TIERS[t][1] for t in selected_tiers if CAP_TIERS[t][1]]
            cap_lo = min(mins_b)
            cap_hi = max(maxs_b) if maxs_b and not any(CAP_TIERS.get(t,(None,None))[1] is None for t in selected_tiers) else None
            hi_str = f"${cap_hi}B" if cap_hi else "no limit"
            st.markdown(
                f'<div style="margin-top:0.6rem;font-family:DM Mono,monospace;font-size:0.65rem;color:var(--text-muted)">' +
                f'Cap range: ${cap_lo}B → {hi_str}' +
                f'</div>',
                unsafe_allow_html=True)

    # ── Fetch + Paste ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header" style="margin-top:1.5rem"></div>', unsafe_allow_html=True)
    fetch_col, paste_col = st.columns([1, 1], gap="large")

    with fetch_col:
        st.markdown('<div style="font-weight:600;font-size:0.85rem;margin-bottom:0.5rem">Auto-fetch from TradingView</div>', unsafe_allow_html=True)
        fetch_btn = st.button("⬇  Fetch Universe", use_container_width=True)

        if fetch_btn:
            if not exchanges:
                st.error("Select at least one exchange.")
            else:
                with st.spinner(f"Querying TradingView — fetching up to {max_tv_results} stocks..."):
                    found, meta, err = fetch_tradingview_tickers(
                        cap_tiers=tuple(selected_tiers),
                        min_share_vol=min_share_vol,
                        exchanges=tuple(exchanges),
                        max_results=max_tv_results,
                        min_price=min_price,
                    )
                if err:
                    st.error(f"TradingView error: {err}")
                elif found:
                    st.session_state["finviz_tickers"] = found
                    st.session_state["finviz_meta"]    = meta
                    with st.spinner("Pre-fetching sector momentum data..."):
                        fetch_sector_returns(26)
                    st.success(f"✅ {len(found)} tickers loaded · sector data cached — go to Scanner tab")
                    # Show cap tier breakdown
                    if meta:
                        micro  = sum(1 for m in meta if m["mcap_b"] and m["mcap_b"] < 0.3)
                        small  = sum(1 for m in meta if m["mcap_b"] and 0.3 <= m["mcap_b"] < 2)
                        mid    = sum(1 for m in meta if m["mcap_b"] and 2 <= m["mcap_b"] < 10)
                        large  = sum(1 for m in meta if m["mcap_b"] and 10 <= m["mcap_b"] < 200)
                        mega   = sum(1 for m in meta if m["mcap_b"] and m["mcap_b"] >= 200)
                        breakdown = (
                            (f'<span style="color:var(--text-muted)">Micro {micro}</span>  ' if micro else "") +
                            (f'<span style="color:var(--blue)">Small {small}</span>  ' if small else "") +
                            (f'<span style="color:var(--green)">Mid {mid}</span>  ' if mid else "") +
                            (f'<span style="color:var(--amber)">Large {large}</span>  ' if large else "") +
                            (f'<span style="color:var(--indigo)">Mega {mega}</span>' if mega else "")
                        )
                        st.markdown(
                            f'<div style="font-family:DM Mono,monospace;font-size:0.7rem;margin-top:0.4rem">' +
                            breakdown + '</div>', unsafe_allow_html=True)
                    pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in found[:100]])
                    st.markdown(
                        f'<div style="margin-top:0.6rem;line-height:2">{pills}' +
                        (f'&nbsp;<span style="color:var(--text-muted);font-size:0.65rem">+{len(found)-100} more</span>' if len(found) > 100 else "") +
                        '</div>', unsafe_allow_html=True)
                else:
                    st.warning("No tickers matched. Try selecting more cap tiers or lowering the volume floor.")

    with paste_col:
        st.markdown('<div style="font-weight:600;font-size:0.85rem;margin-bottom:0.5rem">Or paste manually</div>', unsafe_allow_html=True)
        st.caption("From TradingView screener export, Finviz, or any watchlist")
        manual_paste = st.text_area("Tickers (comma, space, or newline separated)",
            height=150, placeholder="AAPL, NVDA, TPL, TSLA\nor one per line...",
            label_visibility="collapsed")
        if st.button("✓ Load Pasted Tickers", use_container_width=True):
            raw   = re.split(r"[\s,;]+", manual_paste.strip())
            clean = [t.upper() for t in raw if re.match(r"^[A-Z]{1,5}$", t.upper())]
            if clean:
                st.session_state["finviz_tickers"] = clean
                st.session_state.pop("finviz_meta", None)
                st.success(f"✅ {len(clean)} tickers loaded — go to Scanner tab")
            else:
                st.error("No valid tickers found.")

    # ── Loaded state ──────────────────────────────────────────────────────────
    if "finviz_tickers" in st.session_state:
        loaded = st.session_state["finviz_tickers"]
        meta   = st.session_state.get("finviz_meta", [])
        st.markdown('<div class="section-header"></div>', unsafe_allow_html=True)
        lcol1, lcol2, lcol3 = st.columns([2, 1, 1])
        lcol1.markdown(
            f'<div style="font-family:DM Mono,monospace;font-size:0.72rem;color:var(--text-muted);padding-top:0.5rem">' +
            f'<b style="color:var(--green)">{len(loaded)}</b> tickers ready · sorted by $ volume</div>',
            unsafe_allow_html=True)
        # CSV includes meta if available
        if meta:
            csv_rows = ["ticker,mcap_b,sector"] + [f"{m['ticker']},{m.get('mcap_b','')},{m.get('sector','')}" for m in meta]
            csv_data = "\n".join(csv_rows)
        else:
            csv_data = ",".join(loaded)
        lcol2.download_button("⬇ CSV", csv_data, "universe.csv", "text/csv",
            use_container_width=True)
        if lcol3.button("🗑 Clear", use_container_width=True):
            st.session_state.pop("finviz_tickers", None)
            st.session_state.pop("finviz_meta", None)
            st.rerun()
        pills = " ".join([f'<span class="ticker-pill">{t}</span>' for t in loaded[:200]])
        st.markdown(
            f'<div style="margin-top:0.6rem;line-height:2">{pills}' +
            (f'&nbsp;<span style="color:var(--text-muted);font-size:0.65rem">+{len(loaded)-200} more</span>' if len(loaded) > 200 else "") +
            '</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:

    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = {}

    # ── Resume banner — shown when a previous session was restored ────────────
    if "_restored_hits" in st.session_state and st.session_state["_restored_hits"]:
        _meta  = st.session_state.get("_restored_meta", {})
        _ts    = _meta.get("scan_ts", "unknown time")
        _n     = _meta.get("scanned", "?")
        _total = _meta.get("total", "?")
        _nhits = len(st.session_state["_restored_hits"])
        _done  = _meta.get("complete", False)
        _status_label = "✅ Scan completed" if _done else f"⚡ Scan interrupted at {_n}/{_total} tickers"
        _status_color = "#10b981" if _done else "#f59e0b"

        _rb1, _rb2, _rb3 = st.columns([4, 1, 1])
        _rb1.markdown(
            f'<div style="background:var(--bg-card);border:1px solid {_status_color};' +
            f'border-radius:10px;padding:0.75rem 1.1rem;display:flex;align-items:center;gap:1rem">' +
            f'<span style="font-size:1.4rem">🔄</span>' +
            f'<div><div style="font-family:DM Mono,monospace;font-size:0.72rem;color:{_status_color};font-weight:700">' +
            f'{_status_label}</div>' +
            f'<div style="font-family:DM Mono,monospace;font-size:0.65rem;color:var(--text-muted);margin-top:0.2rem">' +
            f'{_ts} &nbsp;·&nbsp; {_nhits} hits recovered &nbsp;·&nbsp; session reconnected</div></div></div>',
            unsafe_allow_html=True)
        if _rb2.button("📋 Show Results", use_container_width=True, key="resume_show"):
            st.session_state["show_restored"] = True
        if _rb3.button("🗑 Discard", use_container_width=True, key="resume_discard"):
            st.session_state.pop("_restored_hits", None)
            st.session_state.pop("_restored_logs", None)
            st.session_state.pop("_restored_meta", None)
            st.session_state.pop("show_restored", None)
            _clear_state()
            st.rerun()

    # ── Restored results view ─────────────────────────────────────────────────
    if st.session_state.get("show_restored") and st.session_state.get("_restored_hits"):
        _r_hits = st.session_state["_restored_hits"]
        _r_meta = st.session_state.get("_restored_meta", {})
        st.markdown(
            f'<div class="section-header">Restored Results — ' +
            f'{_r_meta.get("scan_ts", "")} · {len(_r_hits)} hits</div>',
            unsafe_allow_html=True)
        _r_rows = []
        for _h in sorted(_r_hits, key=lambda x: -x["score"]):
            _ns = _h.get("norm_score", min(100, round(_h["score"]/1.25)))
            _tv = f"https://www.tradingview.com/chart/?symbol={_h['ticker']}&interval=W"
            st.markdown(
                f'<div class="hit-card hit-card-' +
                ('full" ' if _h["score"] >= 80 else ('strong" ' if _h["score"] >= 60 else 'watch" ')) +
                f'style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">' +
                f'<span class="ticker-label">{_h["ticker"]}</span>' +
                f'<span style="font-family:DM Mono,monospace;font-size:0.65rem;color:var(--text-muted)">' +
                f'{_h["wr"].get("dist_200sma_pct",0):+.1f}% from 200W · ' +
                f'Corr {_h["wr"].get("correction_from_ath_pct",0):.0f}% · ' +
                f'Vol ×{_h["wr"].get("vol_ratio",0):.1f} · ' +
                f'{_h["rr"].get("structure_label","")}</span>' +
                f'<div style="display:flex;align-items:center;gap:0.75rem">' +
                f'<span class="score-chip">{_ns}/100</span>' +
                f'<a class="tv-btn" href="{_tv}" target="_blank">📈 Chart</a></div>' +
                f'</div>',
                unsafe_allow_html=True)
            _r_rows.append({
                "Ticker": _h["ticker"], "Score": _ns,
                "Close": _h["wr"].get("current_close"),
                "200W SMA Dist %": _h["wr"].get("dist_200sma_pct"),
                "Correction %": _h["wr"].get("correction_from_ath_pct"),
                "Vol Ratio": _h["wr"].get("vol_ratio"),
                "Structure": _h["rr"].get("structure_label",""),
                "Sector": _h.get("sector",""),
                "TradingView": f"https://www.tradingview.com/chart/?symbol={_h['ticker']}&interval=W",
            })
        if _r_rows:
            _r_df = pd.DataFrame(_r_rows)
            st.download_button("⬇ Export Restored Results", _r_df.to_csv(index=False),
                               "restored_scan.csv", "text/csv")
        st.markdown("---")

    # Resolve universe
    if universe_choice == "TradingView Pre-Filter (recommended)":
        scan_universe = st.session_state.get("finviz_tickers", [])
        if scan_universe:
            st.info(f"📋 {len(scan_universe)} tickers loaded from TradingView pre-filter. Adjust filters in 🔍 Pre-Filter tab if needed.")
        else:
            st.warning("No tickers loaded yet. Go to **🔍 Pre-Filter** tab first, or switch Universe in the sidebar.")
    elif universe_choice == "Custom Tickers":
        scan_universe = [t.strip().upper() for t in custom_tickers_input.split(",") if t.strip()]
    else:
        scan_universe = SP500_TICKERS

    scan_universe = list(dict.fromkeys(scan_universe))[:int(max_stocks)]
    min_price = st.session_state.get("min_price", 5)

    if run_scan:
        # No API key needed for yfinance
        if not scan_universe:
            st.error("No tickers to scan.")
            st.stop()

        _yf_cache.clear()  # fresh cache each scan run

        st.markdown('<div class="section-header">Scan in Progress</div>', unsafe_allow_html=True)
        sector_returns = fetch_sector_returns(26)  # instant if pre-fetched in Tab 1
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
        scan_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        if "watchlist" not in st.session_state:
            st.session_state["watchlist"] = {}
        # Clear any previous restored state since we're starting fresh
        st.session_state.pop("_restored_hits", None)
        st.session_state.pop("_restored_meta", None)
        st.session_state.pop("show_restored", None)

        # ── P04: Live hits panel ───────────────────────────────────────────
        live_hits_ph = st.empty()
        _sector_hit_counts = {}  # sector name → hit count for heat strip

        for i, ticker in enumerate(scan_universe):
            pbar.progress((i + 1) / total)
            status_txt.markdown(
                f'<span style="font-family:Space Mono;font-size:0.75rem;color:#64748b;">Scanning {ticker} ({i+1}/{total})</span>',
                unsafe_allow_html=True)

            df_w = get_yf_data(ticker, period="max", freq="1wk")
            if df_w is None or len(df_w) < 100:
                skipped += 1
                logs.append(f"⚠ {ticker} — no data")
                log_ph.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
                continue

            # ── Price filter backstop ─────────────────────────────────────────
            _cur_price = df_w["close"].iloc[-1]
            if _cur_price < min_price:
                skipped += 1
                logs.append(f"✗ {ticker} — price ${_cur_price:.2f} below ${min_price} floor")
                log_ph.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
                continue

            if is_retest:
                w_pass, wr = check_weekly(df_w, w_dist_200sma_lo, w_dist_200sma_hi, w_prior_run, w_correction, w_vol_mult, ticker=ticker)
            else:
                w_pass, wr = check_base_breakout(df_w, bb_base_years, bb_range_pct, bb_atr_max, bb_vol_mult, bb_sma_lo, bb_sma_hi)

            df_d = get_yf_data(ticker, period="1y", freq="1d")
            d_pass, dr = (False, {}) if (df_d is None or len(df_d) < 55) else check_daily(df_d, d_atr_pct_min, d_atr_pct_max, d_above_50sma)

            # Stash daily ATR-mult into wr so card renderer can display it
            if not is_retest and dr:
                wr["atr_mult_from_50d"] = dr.get("atr_mult_from_50d")
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
            base_sc  = score_setup(wr, dr) if is_retest else score_base_breakout(wr, dr)
            bonus_sc = sc - base_sc
            norm_sc  = round(min(100, sc / 1.25))
            if sc >= min_display:
                hits.append({"ticker": ticker, "score": sc, "norm_score": norm_sc,
                             "base_score": base_sc, "bonus_score": bonus_sc,
                             "wr": wr, "dr": dr,
                             "w_pass": w_pass, "d_pass": d_pass,
                             "sector": sector_name, "sector_rel": sector_rel,
                             "sector_pts": sector_pts, "rr": rr})
                flag = "✅" if (w_pass and d_pass) else ("◑" if w_pass else "○")
                logs.append(f"{flag} {ticker} — {norm_sc}/100 (raw {sc})")
                # ── Track sector hits for heat strip ─────────────────────
                _sn = sector_name or "Unknown"
                _sector_hit_counts[_sn] = _sector_hit_counts.get(_sn, 0) + 1
                # ── P04: Update live hits panel ───────────────────────────
                _live_sorted = sorted(hits, key=lambda x: x["norm_score"], reverse=True)[:6]
                _live_html = '<div style="margin:0.5rem 0"><div class="live-hits-header"><span class="live-dot"></span>Live hits — ' + str(len(hits)) + ' found</div>'
                for _lh in _live_sorted:
                    _lcat = "full" if _lh["score"] >= 80 else ("strong" if _lh["score"] >= 60 else "watch")
                    _lcolor = "#10b981" if _lcat == "full" else ("#f59e0b" if _lcat == "strong" else "#818cf8")
                    _lsig = signal_summary(_lh["wr"], _lh["dr"], _lh.get("rr",{}), is_retest)
                    _live_html += (
                        f'<div style="display:flex;align-items:center;gap:0.75rem;'
                        f'background:var(--bg-card);border:1px solid var(--border);'
                        f'border-left:3px solid {_lcolor};border-radius:10px;'
                        f'padding:0.45rem 0.8rem;margin-bottom:0.3rem;'
                        f'animation:cardSlideIn 0.25s ease forwards">'
                        f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:{_lcolor};font-weight:800;min-width:40px">{_lh["norm_score"]}</span>'
                        f'<span style="font-family:Bricolage Grotesque,sans-serif;font-weight:700;font-size:0.9rem">{_lh["ticker"]}</span>'
                        f'<span style="font-family:DM Mono,monospace;font-size:0.58rem;color:var(--text-muted);flex:1">{_lsig}</span>'
                        f'</div>'
                    )
                _live_html += '</div>'
                live_hits_ph.markdown(_live_html, unsafe_allow_html=True)
                # ── Incremental save after every hit ─────────────────────
                _save_state(hits, logs, i + 1, skipped, total,
                            scan_universe, sector_returns,
                            st.session_state.get("watchlist", {}),
                            "retest" if is_retest else "base",
                            scan_ts)
                # ── Gist checkpoint every 5 hits — survives container restart ──
                if len(hits) % 5 == 0:
                    gist_checkpoint_hits(hits, scan_ts,
                                        "retest" if is_retest else "base")
            else:
                logs.append(f"✗ {ticker} — {norm_sc}/100 (raw {sc})")

            log_ph.markdown(f'<div class="log-box">{"<br>".join(logs[-20:])}</div>', unsafe_allow_html=True)
            met_scanned.markdown(f'<div class="metric-card"><div class="label">Scanned</div><div class="value">{i+1}</div></div>', unsafe_allow_html=True)
            met_hits.markdown(f'<div class="metric-card"><div class="label">Hits</div><div class="value" style="color:#22c55e">{len(hits)}</div></div>', unsafe_allow_html=True)
            met_skipped.markdown(f'<div class="metric-card"><div class="label">Skipped</div><div class="value" style="color:#ef4444">{skipped}</div></div>', unsafe_allow_html=True)

        pbar.progress(1.0)
        status_txt.markdown('<span style="font-family:Space Mono;font-size:0.75rem;color:#22c55e;">✓ Scan complete</span>', unsafe_allow_html=True)
        # Mark complete in persisted state
        _save_complete(hits, logs, total, skipped, total, scan_universe,
                       sector_returns, st.session_state.get("watchlist", {}),
                       "retest" if is_retest else "base", scan_ts)
        # Final Gist checkpoint — catches any hits since last 5-hit checkpoint
        gist_checkpoint_hits(hits, scan_ts, "retest" if is_retest else "base")

        # Persist hits to session state so star-button reruns don't lose results
        hits_sorted_final = sorted(hits, key=lambda x: x["norm_score"], reverse=True)
        st.session_state["last_hits"]      = hits_sorted_final
        st.session_state["last_hits_mode"] = "retest" if is_retest else "base"

        mode_label = '🔄 Retest Mode' if is_retest else '📦 Base Breakout Mode'
        # ── P04: Scan complete summary ─────────────────────────────────────
        _full_n   = len([h for h in hits if h["norm_score"] >= 80])
        _strong_n = len([h for h in hits if 60 <= h["norm_score"] < 80])
        _watch_n  = len([h for h in hits if h["norm_score"] < 60])
        live_hits_ph.empty()
        if hits:
            _summary_html = (
                f'<div class="scan-summary">'
                f'<div style="font-size:1.5rem">✅</div>'
                f'<div class="scan-summary-stat"><span class="scan-summary-num" style="color:#10b981">{_full_n}</span><span class="scan-summary-lbl">Full Hits</span></div>'
                f'<div class="scan-summary-stat"><span class="scan-summary-num" style="color:#f59e0b">{_strong_n}</span><span class="scan-summary-lbl">Strong</span></div>'
                f'<div class="scan-summary-stat"><span class="scan-summary-num" style="color:#818cf8">{_watch_n}</span><span class="scan-summary-lbl">Watch</span></div>'
                f'<div class="scan-summary-stat"><span class="scan-summary-num" style="color:var(--text-muted)">{total}</span><span class="scan-summary-lbl">Scanned</span></div>'
                f'<div style="flex:1;text-align:right;font-family:DM Mono,monospace;font-size:0.6rem;color:var(--text-muted)">{scan_ts}</div>'
                f'</div>'
            )
            st.markdown(_summary_html, unsafe_allow_html=True)
            # Sector heat strip with hit counts
            st.markdown(sector_heat_strip(sector_returns, _sector_hit_counts), unsafe_allow_html=True)
        st.markdown(f'<div class="section-header">Results — {mode_label}</div>', unsafe_allow_html=True)

        if not hits:
            st.warning("No stocks passed. Try relaxing the criteria sliders in the sidebar.")
        else:
            hits_sorted = sorted(hits, key=lambda x: x["norm_score"], reverse=True)
            # Also saved to session state above for star-button rerun persistence

            # ── Categorise ────────────────────────────────────────────────────
            full_hits    = [h for h in hits_sorted if h["norm_score"] >= 80]
            strong_hits  = [h for h in hits_sorted if 60 <= h["norm_score"] < 80]
            watch_hits   = [h for h in hits_sorted if h["norm_score"] < 60]

            def tv_url(ticker):
                """Clean weekly chart URL — TV does not reliably load study params via URL."""
                return f"https://www.tradingview.com/chart/?symbol={ticker}&interval=W"

            if "tv_tip_shown" not in st.session_state:
                st.session_state["tv_tip_shown"] = True
                st.info(
                    "📈 **TradingView setup tip** — Add these indicators once and save as a template: "
                    "**SMA 200** (green) · **SMA 50** (orange) · **EMA 20** (white) · "
                    "**EMA 10** (blue) · **Volume** with 20W MA overlay. "
                    "Save as a chart template and it loads on every ticker automatically."
                )

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
                    # mi() defined here — in scope for both retest and base breakout branches
                    def mi(label, val):
                        return f'<span class="metric-item"><b>{label}</b> {val}</span>'

                    if is_retest:
                        _sg = wr.get("sma200_slope_grade", "declining")
                        _sa = wr.get("sma200_slope_accel", 0)
                        _slope_color = "#10b981" if _sg == "rising" else ("#f59e0b" if _sg == "flattening" else "#f43f5e")
                        _slope_icon  = "↑" if _sg == "rising" else ("→" if _sg == "flattening" else "↓")
                        _accel_tag   = f" +accel" if _sa >= 0.05 and _sg == "flattening" else ""
                        _slope_badge = (
                            f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;' +
                            f'color:{_slope_color};background:var(--bg-raised);border:1px solid {_slope_color};' +
                            f'border-radius:4px;padding:2px 7px">' +
                            f'SMA {_slope_icon} {_sg}{_accel_tag}</span>'
                        )
                        # ── Signal badges: U&R, multi-year vol, R→S, ADR ─────
                        _uc      = wr.get("undercut_reclaim", False)
                        _uc_wks  = wr.get("undercut_reclaim_wks")
                        _uc_badge = (
                            f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;'
                            f'color:#10b981;background:rgba(16,185,129,0.1);'
                            f'border:1px solid #10b981;border-radius:4px;padding:2px 7px">'
                            f'⚡ U&R {_uc_wks}W ago</span>'
                        ) if _uc else ""

                        _mvy = wr.get("multiyear_vol_high", False)
                        _mv_badge = (
                            f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;'
                            f'color:#f59e0b;background:rgba(245,158,11,0.1);'
                            f'border:1px solid #f59e0b;border-radius:4px;padding:2px 7px">'
                            f'🔥 3yr vol high</span>'
                        ) if _mvy else ""

                        _rf      = wr.get("resistance_flip", False)
                        _rf_lvl  = wr.get("resistance_flip_level")
                        _rf_badge = (
                            f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;'
                            f'color:#3b82f6;background:rgba(59,130,246,0.1);'
                            f'border:1px solid #3b82f6;border-radius:4px;padding:2px 7px">'
                            f'🔵 R→S ${_rf_lvl}</span>'
                        ) if _rf else ""

                        _adr     = wr.get("adr_flag", False)
                        _adr_rank = wr.get("adr_vol_pct_rank", "?")
                        _adr_badge = (
                            f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;'
                            f'color:#a78bfa;background:rgba(167,139,250,0.1);'
                            f'border:1px solid #a78bfa;border-radius:4px;padding:2px 7px">'
                            f'ADR vol {_adr_rank}p</span>'
                        ) if _adr else ""

                        _run_min = wr.get("sector_run_min", 300)
                        badges = (
                            badge(wr.get("pass_200sma_proximity"), f"200W {wr.get('dist_200sma_pct',0):+.1f}%") +
                            badge(wr.get("pass_prior_run"),        f"Run {wr.get('prior_run_pct',0):.0f}% (min {_run_min:.0f}%)") +
                            badge(wr.get("pass_correction"),       f"Corr {wr.get('correction_from_ath_pct',0):.0f}%") +
                            badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                            badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                            badge(dr.get("pass_50sma"),            f"50D +{dr.get('pct_above_50sma',0):.1f}%") +
                            _slope_badge + _uc_badge + _mv_badge + _rf_badge + _adr_badge
                        )
                        detail = (
                            mi("200W SMA", f"${wr.get('sma200','—')}") +
                            mi("Dist",     f"{wr.get('dist_200sma_pct','—')}%") +
                            mi("Run",      f"{wr.get('prior_run_pct','—')}% (min {_run_min:.0f}%)") +
                            mi("Corr",     f"{wr.get('correction_from_ath_pct','—')}%") +
                            mi("Vol",      f"×{wr.get('vol_ratio','—')}") +
                            (mi("Vol rank", f"3yr high") if _mvy else "") +
                            (mi("U&R",     f"{_uc_wks}W ago") if _uc else "") +
                            (mi("R→S",     f"${_rf_lvl}") if _rf else "") +
                            mi("ATR",      f"{dr.get('atr_pct','—')}%") +
                            mi("50D",      f"{dr.get('pct_above_50sma','—')}%")
                        )
                    else:
                        _base_type = wr.get("base_subtype", "commodity")
                        _bt_color  = "var(--blue)" if _base_type == "growth" else "var(--amber)"
                        _bt_label  = "Growth Base" if _base_type == "growth" else "Commodity Cycle"
                        _bt_badge  = (
                            f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;' +
                            f'color:{_bt_color};background:var(--bg-raised);border:1px solid {_bt_color};' +
                            f'border-radius:4px;padding:2px 7px">{_bt_label}</span>'
                        )
                        _atr_mult    = wr.get("atr_mult_from_50d")
                        _dot_fired   = dr.get("yellow_dot_fired", False)
                        _dot_day     = dr.get("yellow_dot_day")
                        _dot_stage   = dr.get("post_dot_stage")
                        _dot_pts     = dr.get("post_dot_pts", 0)
                        _stage_cfg   = {
                            "breakout":   ("#10b981", "🟢 Breakout"),
                            "basing":     ("#f59e0b", "🟡 Basing"),
                            "ma_reclaim": ("#3b82f6", "🔵 MA Reclaim"),
                            "watching":   ("#64748b", "👁 Watching"),
                        }
                        _atr_mult_badge = ""
                        if _dot_fired and _dot_stage:
                            _sc, _sl = _stage_cfg.get(_dot_stage, ("#64748b", _dot_stage))
                            _day_str = f" ({_dot_day}d ago)" if _dot_day else ""
                            _pts_str = f" +{_dot_pts}pts" if _dot_pts > 0 else ""
                            _atr_mult_badge = (
                                f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;' +
                                f'color:{_sc};background:var(--bg-raised);border:1px solid {_sc};' +
                                f'border-radius:4px;padding:2px 7px">' +
                                f'⚡ 10× dot{_day_str} → {_sl}{_pts_str}</span>'
                            )
                        elif _atr_mult is not None and _atr_mult <= -10:
                            _atr_mult_badge = (
                                f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;' +
                                f'color:#f59e0b;background:var(--bg-raised);border:1px solid #f59e0b;' +
                                f'border-radius:4px;padding:2px 7px">⚡ {_atr_mult:.1f}× ATR now</span>'
                            )
                        badges = (
                            badge(wr.get("pass_200sma_proximity"), f"200W {wr.get('dist_200sma_pct',0):+.1f}%") +
                            badge(wr.get("pass_base_range"),       f"Base range {wr.get('base_range_pct',0):.0f}%") +
                            badge(wr.get("pass_base_atr"),         f"Base ATR {wr.get('base_atr_pct',0):.1f}%") +
                            badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                            badge(wr.get("pass_base_duration"),    f"Base {wr.get('base_duration_yrs',0):.1f}yr") +
                            badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                            _bt_badge + _atr_mult_badge
                        )
                        detail = (
                            mi("200W SMA",   f"${wr.get('sma200','—')}") +
                            mi("Dist",       f"{wr.get('dist_200sma_pct','—')}%") +
                            mi("Base range", f"{wr.get('base_range_pct','—')}%") +
                            mi("Base ATR",   f"{wr.get('base_atr_pct','—')}%") +
                            mi("Duration",   f"{wr.get('base_duration_yrs','—')}yr") +
                            mi("Vol",        f"×{wr.get('vol_ratio','—')}") +
                            mi("ATR",        f"{dr.get('atr_pct','—')}%") +
                            mi("SubType",    _bt_label) +
                            (mi("Dot stage",  _dot_stage) if _dot_fired else "") +
                            (mi("ATR×50D",   f"{_atr_mult:+.1f}×") if _atr_mult is not None else "")
                        )

                    card_class = "hit-card-full" if h["score"] >= 80 else ("hit-card-strong" if h["score"] >= 60 else "hit-card-watch")
                    price      = wr.get("current_close", "—")
                    score      = h["norm_score"]
                    raw_score  = h["score"]
                    bonus_score= h.get("bonus_score", 0)
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
                        _sg2 = wr.get("sma200_slope_grade","")
                        _sa2 = wr.get("sma200_slope_accel", 0)
                        _accel_str = f" (accel {_sa2:+.3f})" if _sa2 != 0 else ""
                        ema_detail = (
                            mi("10W EMA", f"${rr['ema10w']}") +
                            mi("20W EMA", f"${rr['ema20w']}") +
                            mi("50W SMA", f"${rr['sma50w']}") +
                            mi("SMA slope", f"{_sg2}{_accel_str}") +
                            (mi("Pullback from hi", f"{rr['local_high_pct']}%") if rr.get("local_high_pct") is not None else "") +
                            (mi("ATR contracting", "yes") if rr.get("atr_contracting") else "")
                        )


                    # ── Determine category for score arc color ─────────────────
                    _cat = "full" if h["score"] >= 80 else ("strong" if h["score"] >= 60 else "watch")
                    _arc = score_arc(score, _cat)
                    _sig = signal_summary(wr, dr, rr, is_retest)
                    _corr = wr.get("correction_from_ath_pct", 0)
                    _cat_color = "#10b981" if _cat == "full" else ("#f59e0b" if _cat == "strong" else "#818cf8")
                    _cbar = correction_bar(_corr, _cat_color) if is_retest and _corr > 0 else ""

                    # ── Unique ID for CSS checkbox expand ──────────────────────
                    _uid = f"{ticker}_{score}_{id(h) % 9999}"

                    _bonus_tag = (
                        f'<span style="font-family:DM Mono,monospace;font-size:0.5rem;color:var(--amber)">+{bonus_score}b</span>'
                        if bonus_score > 0 else ""
                    )
                    html = (
                        # LAYER 1 — always visible
                        f'<div class="hit-card {card_class}" style="padding:0.9rem 1.1rem">'
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem">'
                        f'<div class="score-arc-wrap">{_arc}{_cbar}</div>'
                        f'<div style="flex:1;min-width:0;padding:0 0.6rem">'
                        f'<div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap">'
                        f'<span class="ticker-label">{ticker}</span>'
                        f'<a class="tv-btn" href="{tv_link}" target="_blank">📈</a>'
                        + (partial_tag if h.get("partial") else "") +
                        f'</div>'
                        f'<div class="signal-summary">{_sig}</div>'
                        f'<div style="margin-top:0.25rem;display:flex;gap:0.4rem;flex-wrap:wrap">{sec_badge}{struct_badge}</div>'
                        f'</div>'
                        f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:0.4rem;white-space:nowrap">'
                        f'<span class="price-label">${price}</span>'
                        + _bonus_tag +
                        f'<label for="exp_{_uid}" class="expand-btn" title="Show criteria">'
                        f'<span class="expand-chevron">▼</span> Details'
                        f'</label>'
                        f'</div>'
                        f'</div>'
                        # LAYER 2 — CSS checkbox expand (badges + metrics)
                        f'<input type="checkbox" id="exp_{_uid}" class="card-expand-toggle">'
                        f'<div class="card-layer2" style="border-top:1px solid var(--border-soft)">'
                        f'<div style="padding-top:0.55rem;display:flex;flex-wrap:wrap;gap:0.35rem">{badges}</div>'
                        f'<div class="metric-strip" style="margin-top:0.4rem">{detail}{ema_detail}</div>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(html, unsafe_allow_html=True)
                    _wl     = st.session_state["watchlist"]
                    _in_wl  = ticker in _wl
                    _blabel = "★ Watching" if _in_wl else "☆ Watch"
                    if st.button(_blabel, key=f"wl_{ticker}_{score}", help="Add/remove from watchlist"):
                        if _in_wl:
                            del st.session_state["watchlist"][ticker]
                        else:
                            st.session_state["watchlist"][ticker] = {
                                "score": score, "raw": raw_score,
                                "close": wr.get("current_close"),
                                "sector": h.get("sector", ""),
                                "structure": h.get("rr", {}).get("structure_label", ""),
                                "slope": wr.get("sma200_slope_grade", ""),
                                "added": datetime.now().strftime("%Y-%m-%d"),
                            }
                        # Save to Gist (cross-device) + /tmp (fast local backup)
                        gist_save_watchlist(st.session_state["watchlist"])
                        try:
                            if os.path.exists(SAVE_PATH):
                                with open(SAVE_PATH, "r") as _pf:
                                    _ps = json.load(_pf)
                                _ps["watchlist"] = st.session_state["watchlist"]
                                with open(SAVE_PATH, "w") as _pf:
                                    json.dump(_ps, _pf)
                        except Exception:
                            pass
                        st.rerun()

            # ── Chart setup tip (collapsed by default) ───────────────────────
            with st.expander("📋 TradingView chart setup — add these indicators once, saved forever"):
                st.markdown("""
                **One-time setup** — TradingView saves your layout so every chart opens with the right MAs:

                1. Open any chart → **Indicators** (top toolbar)
                2. Search **"Moving Average"** → add **Simple Moving Average**, set length = **200** (this is your 200W SMA)
                3. Add another **SMA**, set length = **50** (50W SMA)
                4. Search **"Moving Average Exponential"** → add **EMA**, set length = **20** (20W EMA)
                5. Add another **EMA**, set length = **10** (10W EMA)
                6. Right-click chart → **Save as template** → name it "Retest Scanner"

                After that, click **Load template** on any chart to instantly apply all 4 MAs.
                The 200W SMA is the most important — green line, far below for retest setups.
                """)

            render_category("Full Hit  ≥80",  "🟢", "cat-full",   full_hits)
            render_category("Strong  60–79",  "🟡", "cat-strong",  strong_hits)
            render_category("Watchlist  <60", "🔵", "cat-watch",   watch_hits)

            # ── Export ────────────────────────────────────────────────────────
            st.markdown('<div class="section-header">Export Results</div>', unsafe_allow_html=True)
            rows = []
            for h in hits_sorted:
                score = h["score"]
                norm_sc_ex = h["norm_score"]
                category = "Full Hit" if norm_sc_ex >= 80 else ("Strong" if norm_sc_ex >= 60 else "Watchlist")
                rows.append({
                    "Category":        category,
                    "Ticker":          h["ticker"],
                    "Score (norm/100)":h["norm_score"],
                    "Score (raw/125)": h["score"],
                    "Bonus pts":       h.get("bonus_score", 0),
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
                    "SMA Slope Grade":    h["wr"].get("sma200_slope_grade", ""),
                    "SMA Slope Accel":    h["wr"].get("sma200_slope_accel", ""),
                    "Recovery Structure": h.get("rr", {}).get("structure_label", ""),
                    "Structure Pts":      h.get("rr", {}).get("structure_pts", 0),
                    "TradingView":        tv_url(h["ticker"]),
                })
            df_out = pd.DataFrame(rows)
            st.dataframe(df_out, use_container_width=True)
            st.download_button("⬇ Download Results CSV", df_out.to_csv(index=False), "scanner_results.csv", "text/csv")

    # ── Compact watchlist indicator — full management in ⭐ Watchlist tab ────────
    watchlist_data = st.session_state.get("watchlist", {})
    if watchlist_data:
        _wl_tickers = list(watchlist_data.keys())
        _wl_pills = " ".join(
            f'<span style="font-family:DM Mono,monospace;font-size:0.7rem;font-weight:700;'
            f'color:var(--accent);background:var(--bg-raised);border:1px solid var(--border);'
            f'border-radius:6px;padding:2px 9px">{t}</span>'
            for t in _wl_tickers[:8]
        )
        _wl_more = (f' <span style="color:var(--text-muted);font-size:0.6rem">+{len(_wl_tickers)-8} more</span>'
                    if len(_wl_tickers) > 8 else "")
        st.markdown(
            f'<div style="background:var(--bg-card);border:1px solid var(--border);'
            f'border-radius:12px;padding:0.5rem 1rem;margin:0.6rem 0;'
            f'display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap">'
            f'<span style="font-family:DM Mono,monospace;font-size:0.58rem;'
            f'color:var(--accent);font-weight:700;white-space:nowrap">⭐ {len(_wl_tickers)}</span>'
            f'<span style="color:var(--border);margin:0 2px">|</span>'
            f'{_wl_pills}{_wl_more}'
            f'</div>',
            unsafe_allow_html=True
        )

    # ── Rerun path: star was clicked, render persisted results ─────────────
    # NOTE: this is now INDEPENDENT of watchlist — watchlist renders below unconditionally.
    if not run_scan and st.session_state.get("last_hits"):
        hits_sorted   = st.session_state["last_hits"]
        _mode_was     = st.session_state.get("last_hits_mode", "retest")
        _mode_label   = "🔄 Retest Mode" if _mode_was == "retest" else "📦 Base Breakout Mode"
        is_retest     = (_mode_was == "retest")
        st.markdown(f'<div class="section-header">Results — {_mode_label}</div>', unsafe_allow_html=True)

        full_hits   = [h for h in hits_sorted if h["norm_score"] >= 80]
        strong_hits = [h for h in hits_sorted if 60 <= h["norm_score"] < 80]
        watch_hits  = [h for h in hits_sorted if h["norm_score"] < 60]

        def tv_url(ticker):
            return f"https://www.tradingview.com/chart/?symbol={ticker}&interval=W"

        def render_category(label, emoji, cat_class, group):
            if not group:
                return
            st.markdown(
                f'<div class="category-header {cat_class}">{emoji} {label} — {len(group)} stock{"s" if len(group)!=1 else ""}</div>',
                unsafe_allow_html=True)
            for h in group:
                wr = h["wr"]; dr = h["dr"]
                rr = h.get("rr", {})
                tv_link     = tv_url(h["ticker"])
                ticker      = h["ticker"]
                score       = h["norm_score"]
                raw_score   = h["score"]
                bonus_score = h.get("bonus_score", 0)
                price       = wr.get("current_close", "—")
                card_class  = "hit-card-full" if h["score"] >= 80 else ("hit-card-strong" if h["score"] >= 60 else "hit-card-watch")
                sec_name    = h.get("sector", "")
                sec_rel     = h.get("sector_rel")
                sec_pts     = h.get("sector_pts", 0)

                # ── Sector badge ──────────────────────────────────────────────
                if sec_rel is not None:
                    sec_color = "var(--green)" if sec_rel >= 5 else ("var(--red)" if sec_rel <= -5 else "var(--text-muted)")
                    sec_sign  = "+" if sec_rel >= 0 else ""
                    sec_bonus = f" ({sec_sign}{sec_pts:+d}pts)" if sec_pts != 0 else ""
                    sec_badge = f'<span style="font-family:DM Mono,monospace;font-size:0.6rem;color:{sec_color};background:var(--bg-raised);border:1px solid var(--border);border-radius:4px;padding:2px 7px">{sec_name} {sec_sign}{sec_rel}%{sec_bonus}</span>'
                else:
                    sec_badge = ""

                # ── Recovery structure badge ──────────────────────────────────
                struct     = rr.get("structure", "none")
                struct_pts = rr.get("structure_pts", 0)
                struct_lbl = rr.get("structure_label", "")
                if struct == "none" or not is_retest:
                    struct_badge = ""
                else:
                    s_color_map = {
                        "ma_stack":       ("var(--green)", "🟢"),
                        "bounce_ema":     ("var(--blue)",  "🔵"),
                        "first_pullback": ("var(--amber)", "🟡"),
                    }
                    s_color, s_icon = s_color_map.get(struct, ("var(--text-muted)", "⚪"))
                    pts_tag = f" +{struct_pts}pts" if struct_pts else ""
                    struct_badge = (
                        f'<span style="font-family:DM Mono,monospace;font-size:0.6rem;'
                        f'color:{s_color};background:var(--bg-raised);border:1px solid {s_color};'
                        f'border-radius:4px;padding:2px 7px;margin-left:6px">'
                        f'{s_icon} {struct_lbl}{pts_tag}</span>'
                    )

                # ── New-design card elements ───────────────────────────────────
                _cat       = "full" if h["score"] >= 80 else ("strong" if h["score"] >= 60 else "watch")
                _arc       = score_arc(score, _cat)
                _sig       = signal_summary(wr, dr, rr, is_retest)
                _corr      = wr.get("correction_from_ath_pct", 0)
                _cat_color = "#10b981" if _cat == "full" else ("#f59e0b" if _cat == "strong" else "#818cf8")
                _cbar      = correction_bar(_corr, _cat_color) if is_retest and _corr > 0 else ""
                _uid       = f"r_{ticker}_{score}_{id(h) % 9999}"
                _bonus_tag = (
                    f'<span style="font-family:DM Mono,monospace;font-size:0.5rem;color:var(--amber)">+{bonus_score}b</span>'
                    if bonus_score > 0 else ""
                )

                # ── Build badges / detail (same as main scan path) ────────────
                def mi(lbl, val):
                    return f'<span class="metric-item"><b>{lbl}</b> {val}</span>'

                if is_retest:
                    _sg = wr.get("sma200_slope_grade", "declining")
                    _sa = wr.get("sma200_slope_accel", 0)
                    _slope_color = "#10b981" if _sg == "rising" else ("#f59e0b" if _sg == "flattening" else "#f43f5e")
                    _slope_icon  = "↑" if _sg == "rising" else ("→" if _sg == "flattening" else "↓")
                    _accel_tag   = " +accel" if _sa >= 0.05 and _sg == "flattening" else ""
                    _slope_badge = f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:{_slope_color};background:var(--bg-raised);border:1px solid {_slope_color};border-radius:4px;padding:2px 7px">SMA {_slope_icon} {_sg}{_accel_tag}</span>'
                    _uc      = wr.get("undercut_reclaim", False)
                    _uc_wks  = wr.get("undercut_reclaim_wks")
                    _uc_badge = (f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:#10b981;background:rgba(16,185,129,0.1);border:1px solid #10b981;border-radius:4px;padding:2px 7px">⚡ U&R {_uc_wks}W ago</span>') if _uc else ""
                    _mvy = wr.get("multiyear_vol_high", False)
                    _mv_badge = (f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:#f59e0b;background:rgba(245,158,11,0.1);border:1px solid #f59e0b;border-radius:4px;padding:2px 7px">🔥 3yr vol high</span>') if _mvy else ""
                    _rf = wr.get("resistance_flip", False)
                    _rf_lvl = wr.get("resistance_flip_level")
                    _rf_badge = (f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:#3b82f6;background:rgba(59,130,246,0.1);border:1px solid #3b82f6;border-radius:4px;padding:2px 7px">🔵 R→S ${_rf_lvl}</span>') if _rf else ""
                    _adr = wr.get("adr_flag", False)
                    _adr_rank = wr.get("adr_vol_pct_rank", "?")
                    _adr_badge = (f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:#a78bfa;background:rgba(167,139,250,0.1);border:1px solid #a78bfa;border-radius:4px;padding:2px 7px">ADR vol {_adr_rank}p</span>') if _adr else ""
                    _run_min = wr.get("sector_run_min", 300)
                    badges = (
                        badge(wr.get("pass_200sma_proximity"), f"200W {wr.get('dist_200sma_pct',0):+.1f}%") +
                        badge(wr.get("pass_prior_run"),        f"Run {wr.get('prior_run_pct',0):.0f}%") +
                        badge(wr.get("pass_correction"),       f"Corr {wr.get('correction_from_ath_pct',0):.0f}%") +
                        badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                        badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                        badge(dr.get("pass_50sma"),            f"50D +{dr.get('pct_above_50sma',0):.1f}%") +
                        _slope_badge + _uc_badge + _mv_badge + _rf_badge + _adr_badge
                    )
                    ema_detail = ""
                    if rr.get("ema10w") is not None:
                        _sg2 = wr.get("sma200_slope_grade","")
                        _sa2 = wr.get("sma200_slope_accel", 0)
                        _accel_str = f" (accel {_sa2:+.3f})" if _sa2 != 0 else ""
                        ema_detail = (
                            mi("10W EMA", f"${rr['ema10w']}") + mi("20W EMA", f"${rr['ema20w']}") +
                            mi("50W SMA", f"${rr['sma50w']}") + mi("SMA slope", f"{_sg2}{_accel_str}") +
                            (mi("Pullback from hi", f"{rr['local_high_pct']}%") if rr.get("local_high_pct") is not None else "") +
                            (mi("ATR contracting", "yes") if rr.get("atr_contracting") else "")
                        )
                    detail = (
                        mi("200W SMA", f"${wr.get('sma200','—')}") + mi("Dist", f"{wr.get('dist_200sma_pct','—')}%") +
                        mi("Run", f"{wr.get('prior_run_pct','—')}%") + mi("Corr", f"{wr.get('correction_from_ath_pct','—')}%") +
                        mi("Vol", f"×{wr.get('vol_ratio','—')}") + mi("ATR", f"{dr.get('atr_pct','—')}%") +
                        mi("50D", f"{dr.get('pct_above_50sma','—')}%")
                    )
                else:
                    _base_type = wr.get("base_subtype", "commodity")
                    _bt_color  = "var(--blue)" if _base_type == "growth" else "var(--amber)"
                    _bt_label  = "Growth Base" if _base_type == "growth" else "Commodity Cycle"
                    _bt_badge  = f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:{_bt_color};background:var(--bg-raised);border:1px solid {_bt_color};border-radius:4px;padding:2px 7px">{_bt_label}</span>'
                    _atr_mult  = wr.get("atr_mult_from_50d")
                    _dot_fired = dr.get("yellow_dot_fired", False)
                    _dot_stage = dr.get("post_dot_stage")
                    _dot_pts   = dr.get("post_dot_pts", 0)
                    _dot_day   = dr.get("yellow_dot_day")
                    _atr_mult_badge = ""
                    if _dot_fired and _dot_stage:
                        _stage_cfg = {"breakout":("#10b981","🟢 Breakout"),"basing":("#f59e0b","🟡 Basing"),"ma_reclaim":("#3b82f6","🔵 MA Reclaim"),"watching":("#64748b","👁 Watching")}
                        _sc, _sl = _stage_cfg.get(_dot_stage, ("#64748b", _dot_stage))
                        _day_str = f" ({_dot_day}d ago)" if _dot_day else ""
                        _pts_str = f" +{_dot_pts}pts" if _dot_pts > 0 else ""
                        _atr_mult_badge = f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:{_sc};background:var(--bg-raised);border:1px solid {_sc};border-radius:4px;padding:2px 7px">⚡ 10× dot{_day_str} → {_sl}{_pts_str}</span>'
                    elif _atr_mult is not None and _atr_mult <= -10:
                        _atr_mult_badge = f'<span style="font-family:DM Mono,monospace;font-size:0.62rem;color:#f59e0b;background:var(--bg-raised);border:1px solid #f59e0b;border-radius:4px;padding:2px 7px">⚡ {_atr_mult:.1f}× ATR now</span>'
                    badges = (
                        badge(wr.get("pass_200sma_proximity"), f"200W {wr.get('dist_200sma_pct',0):+.1f}%") +
                        badge(wr.get("pass_base_range"),       f"Base range {wr.get('base_range_pct',0):.0f}%") +
                        badge(wr.get("pass_base_atr"),         f"Base ATR {wr.get('base_atr_pct',0):.1f}%") +
                        badge(wr.get("pass_volume_surge"),     f"Vol ×{wr.get('vol_ratio',0):.1f}") +
                        badge(wr.get("pass_base_duration"),    f"Base {wr.get('base_duration_yrs',0):.1f}yr") +
                        badge(dr.get("pass_atr"),              f"ATR {dr.get('atr_pct',0):.1f}%") +
                        _bt_badge + _atr_mult_badge
                    )
                    detail = (
                        mi("200W SMA", f"${wr.get('sma200','—')}") + mi("Dist", f"{wr.get('dist_200sma_pct','—')}%") +
                        mi("Base range", f"{wr.get('base_range_pct','—')}%") + mi("Base ATR", f"{wr.get('base_atr_pct','—')}%") +
                        mi("Duration", f"{wr.get('base_duration_yrs','—')}yr") + mi("Vol", f"×{wr.get('vol_ratio','—')}") +
                        mi("ATR", f"{dr.get('atr_pct','—')}%")
                    )
                    ema_detail = ""

                html = (
                    f'<div class="hit-card {card_class}" style="padding:0.9rem 1.1rem">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem">'
                    f'<div class="score-arc-wrap">{_arc}{_cbar}</div>'
                    f'<div style="flex:1;min-width:0;padding:0 0.6rem">'
                    f'<div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap">'
                    f'<span class="ticker-label">{ticker}</span>'
                    f'<a class="tv-btn" href="{tv_link}" target="_blank">📈</a>'
                    f'</div>'
                    f'<div class="signal-summary">{_sig}</div>'
                    f'<div style="margin-top:0.25rem;display:flex;gap:0.4rem;flex-wrap:wrap">{sec_badge}{struct_badge}</div>'
                    f'</div>'
                    f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:0.4rem;white-space:nowrap">'
                    f'<span class="price-label">${price}</span>'
                    + _bonus_tag +
                    f'<label for="exp_{_uid}" class="expand-btn" title="Show criteria">'
                    f'<span class="expand-chevron">▼</span> Details'
                    f'</label>'
                    f'</div>'
                    f'</div>'
                    f'<input type="checkbox" id="exp_{_uid}" class="card-expand-toggle">'
                    f'<div class="card-layer2" style="border-top:1px solid var(--border-soft)">'
                    f'<div style="padding-top:0.55rem;display:flex;flex-wrap:wrap;gap:0.35rem">{badges}</div>'
                    f'<div class="metric-strip" style="margin-top:0.4rem">{detail}{ema_detail}</div>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(html, unsafe_allow_html=True)
                _wl    = st.session_state["watchlist"]
                _in_wl = ticker in _wl
                _lbl   = "★ Watching" if _in_wl else "☆ Watch"
                if st.button(_lbl, key=f"wl_r_{ticker}_{score}", help="Add/remove from watchlist"):
                    if _in_wl:
                        del st.session_state["watchlist"][ticker]
                    else:
                        st.session_state["watchlist"][ticker] = {
                            "score": score, "raw": raw_score,
                            "close": wr.get("current_close"),
                            "sector": h.get("sector", ""),
                            "structure": h.get("rr", {}).get("structure_label", ""),
                            "slope": wr.get("sma200_slope_grade", ""),
                            "added": datetime.now().strftime("%Y-%m-%d"),
                        }
                    gist_save_watchlist(st.session_state["watchlist"])
                    try:
                        if os.path.exists(SAVE_PATH):
                            with open(SAVE_PATH, "r") as _pf:
                                _ps = json.load(_pf)
                            _ps["watchlist"] = st.session_state["watchlist"]
                            with open(SAVE_PATH, "w") as _pf:
                                json.dump(_ps, _pf)
                    except Exception:
                        pass
                    st.rerun()

        render_category("Full Hit  ≥80",  "🟢", "cat-full",   full_hits)
        render_category("Strong  60–79",  "🟡", "cat-strong",  strong_hits)
        render_category("Watchlist  <60", "🔵", "cat-watch",   watch_hits)

    elif not run_scan:
        # Idle state — no scan running, no results, no watchlist
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
                <div class="idle-sub">Go to <b>🔍 Pre-Filter</b> to build your<br>candidate list, then hit 🚀 Run Scanner.</div>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — BACKTEST & VALIDATE
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = {}
    _wl_data = st.session_state.get("watchlist", {})

    # ── Header with sync status ──────────────────────────────────────────────
    _gs_c = "#10b981" if _gist_enabled() else "#64748b"
    _gs_l = "● Gist sync active" if _gist_enabled() else "○ Local only — enable Gist for cross-device sync"
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:0.8rem;flex-wrap:wrap;gap:0.5rem">'
        f'<div class="section-header" style="margin:0">⭐ Watchlist — {len(_wl_data)} stock{"s" if len(_wl_data)!=1 else ""}</div>'
        f'<span style="font-family:DM Mono,monospace;font-size:0.6rem;color:{_gs_c};'
        f'font-weight:600">{_gs_l}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    if not _wl_data:
        st.markdown(
            '<div style="background:var(--bg-card);border:1px solid var(--border);'
            'border-radius:12px;padding:2rem;text-align:center;margin:1rem 0">'
            '<div style="font-size:2rem;margin-bottom:0.5rem">⭐</div>'
            '<div style="font-family:Bricolage Grotesque,sans-serif;font-weight:700;'
            'font-size:1.1rem;color:var(--text-primary);margin-bottom:0.3rem">No stocks watched yet</div>'
            '<div style="font-family:DM Mono,monospace;font-size:0.7rem;color:var(--text-muted)">'
            'Run a scan in 🚀 Scanner and tap ☆ Watch on any result card</div>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        # ── Watchlist cards ──────────────────────────────────────────────────
        _wl_rows_export = []
        for tk, d in _wl_data.items():
            _tv_wl = f"https://www.tradingview.com/chart/?symbol={tk}&interval=W"
            _sn = min(100, round(d.get("score", 0) / 1.25))
            _cat_c = "#10b981" if _sn >= 80 else ("#f59e0b" if _sn >= 60 else "#818cf8")
            _detail_parts = [x for x in [
                d.get("structure"),
                d.get("slope"),
                d.get("sector"),
            ] if x]
            _detail_str = " · ".join(_detail_parts) if _detail_parts else "—"

            _wl_c1, _wl_c2, _wl_c3 = st.columns([5, 1, 1])
            _wl_c1.markdown(
                f'<div style="display:flex;align-items:center;gap:0.75rem;'
                f'background:var(--bg-card);border:1px solid var(--border);'
                f'border-left:3px solid {_cat_c};border-radius:10px;'
                f'padding:0.6rem 1rem;margin:0.2rem 0">'
                f'<span style="font-family:DM Mono,monospace;font-size:0.65rem;'
                f'color:{_cat_c};font-weight:800;min-width:32px">{_sn}</span>'
                f'<div style="flex:1;min-width:0">'
                f'<div style="display:flex;align-items:center;gap:0.4rem">'
                f'<span style="font-family:Bricolage Grotesque,sans-serif;font-weight:700;'
                f'font-size:0.95rem">{tk}</span>'
                f'<a href="{_tv_wl}" target="_blank" style="font-size:0.65rem;text-decoration:none">📈</a>'
                f'</div>'
                f'<div style="font-family:DM Mono,monospace;font-size:0.6rem;'
                f'color:var(--text-muted);margin-top:0.15rem">'
                f'${d.get("close", "—")} · {_detail_str} · added {d.get("added", "?")}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if _wl_c2.button("📈", key=f"wl4_tv_{tk}", help=f"Open {tk} chart"):
                import webbrowser
                st.markdown(f'<meta http-equiv="refresh" content="0;url={_tv_wl}">', unsafe_allow_html=True)
            if _wl_c3.button("✕", key=f"wl4_rm_{tk}", help=f"Remove {tk}"):
                del st.session_state["watchlist"][tk]
                gist_save_watchlist(st.session_state["watchlist"])
                st.rerun()

            _wl_rows_export.append({
                "Ticker": tk, "Close": d.get("close"),
                "Score": _sn, "Structure": d.get("structure", ""),
                "Slope": d.get("slope", ""), "Sector": d.get("sector", ""),
                "Added": d.get("added", ""), "TradingView": _tv_wl,
            })

        # ── Export + Clear ─────────────────────────────────────────────────
        st.markdown("---")
        _exp_c1, _exp_c2, _exp_c3 = st.columns([2, 1, 1])
        if _wl_rows_export:
            _wl_df = pd.DataFrame(_wl_rows_export)
            _exp_c1.download_button(
                "⬇ Export Watchlist CSV", _wl_df.to_csv(index=False),
                "watchlist.csv", "text/csv", use_container_width=True
            )
        if _exp_c2.button("🔄 Refresh from Gist", use_container_width=True, key="wl4_refresh"):
            _gist_wl_ref = gist_load_watchlist()
            if _gist_wl_ref:
                st.session_state["watchlist"] = _gist_wl_ref
                st.rerun()
            else:
                st.warning("No Gist data found")
        if _exp_c3.button("🗑 Clear All", use_container_width=True, key="wl4_clear"):
            st.session_state["watchlist"] = {}
            gist_save_watchlist({})
            st.rerun()

    # ── Gist setup instructions ──────────────────────────────────────────────
    if not _gist_enabled():
        with st.expander("🔗 Enable cross-device sync (3 min setup)"):
            st.markdown("""
**Watchlist persists on iPhone, desktop, anywhere:**

1. [github.com/settings/tokens](https://github.com/settings/tokens) → Generate classic token, tick **gist** scope
2. Streamlit Cloud → **Manage App → Secrets**, add:
```toml
[gist]
token   = "ghp_yourtoken"
gist_id = ""
```
3. Save → app restarts → star any ticker → Gist ID appears below → paste into secrets as `gist_id`
            """)
    else:
        _gist_cache_id = st.session_state.get("_gist_id_cache", "")
        _secrets_gist = ""
        try:
            _secrets_gist = st.secrets["gist"].get("gist_id", "").strip()
        except Exception:
            pass
        if _gist_cache_id and not _secrets_gist:
            st.info(
                f"✅ Gist created — paste this as `gist_id` in secrets:\n\n"
                f"```\n{_gist_cache_id}\n```",
                icon="🔗"
            )


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
            is_trap = s.get("is_trap", False)
            trap_style = "border-left:3px solid #f43f5e;background:rgba(244,63,94,0.06)" if is_trap else ""
            trap_label = '<span style="font-family:DM Mono,monospace;font-size:0.6rem;color:#f43f5e;background:rgba(244,63,94,0.1);border-radius:3px;padding:1px 6px;margin-left:8px">TRAP — should score LOW</span>' if is_trap else ""
            st.markdown(f"""
            <div class="known-setup-card" style="{trap_style}">
                <span class="ks-ticker">{s['ticker']}</span>
                <span class="ks-date">@ {s['date']}</span>
                <a class="tv-btn" href="{tv_link}" target="_blank" style="margin-left:12px">📈 Chart ↗</a>
                {trap_label}
                <div class="ks-desc">{s['desc']}</div>
                <div style="margin-top:0.3rem;font-size:0.63rem;color:#475569">Expected score: ~{s['expected_score']}/125</div>
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
                # NOTE: sector bonus intentionally excluded from backtest scores.
                # sector_returns always reflects today, not the validation date,
                # so adding it would give random/misleading bonus points.
                # The base score (100pts max) is used for validation comparisons.
                is_trap_setup = s.get("is_trap", False)
                if is_trap_setup:
                    full_pass = sc <= 55   # traps should score LOW — pass if scanner correctly rejects them
                else:
                    full_pass = sc >= 60
                if full_pass: passed_count += 1

                if is_trap_setup:
                    result_class = "bt-result-pass" if sc <= 55 else ("bt-result-warn" if sc <= 65 else "bt-result-fail")
                    status_icon  = "✅ CORRECTLY REJECTED" if sc <= 55 else ("⚠ BORDERLINE" if sc <= 65 else "❌ FALSE POSITIVE")
                else:
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
                            <span style="font-family:Space Mono,monospace;font-size:0.72rem;color:#f59e0b">{sc}/100 <span style="color:#64748b;font-size:0.62rem">(base only · no sector/structure bonus)</span>
                                <span style="color:#64748b;font-size:0.62rem">expected ~{s['expected_score']} · delta {delta_str}</span>
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
