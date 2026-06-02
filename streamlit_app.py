"""
streamlit_app.py — Market Universe Dashboard
Deploy free at streamlit.io/cloud — point it at this repo.
"""

import os
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
import glob

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Market Universe Scanner",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

.main { background: #0d0f14; }

/* Header */
.scanner-header {
    background: linear-gradient(135deg, #0d0f14 0%, #141820 100%);
    border: 1px solid #1e2433;
    border-radius: 8px;
    padding: 24px 32px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.scanner-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #4a9eff;
    margin: 0 0 6px 0;
}
.scanner-subtitle {
    font-size: 22px;
    font-weight: 700;
    color: #e8eaf0;
    margin: 0;
}

/* Metric cards */
.metric-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}
.metric-card {
    background: #141820;
    border: 1px solid #1e2433;
    border-radius: 8px;
    padding: 18px 20px;
}
.metric-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #5a6478;
    margin-bottom: 8px;
}
.metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 600;
    color: #e8eaf0;
    line-height: 1;
}
.metric-value.green { color: #2ecc71; }
.metric-value.amber { color: #f39c12; }
.metric-value.blue  { color: #4a9eff; }

/* Score badge */
.score-high   { color: #2ecc71; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.score-mid    { color: #f39c12; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.score-low    { color: #5a6478; font-weight: 400; font-family: 'IBM Plex Mono', monospace; }

/* Gap */
.gap-pos { color: #2ecc71; font-family: 'IBM Plex Mono', monospace; }
.gap-neg { color: #e74c3c; font-family: 'IBM Plex Mono', monospace; }
.gap-nil { color: #5a6478; font-family: 'IBM Plex Mono', monospace; }

/* Status dot */
.dot-green { color: #2ecc71; }
.dot-amber { color: #f39c12; }
.dot-grey  { color: #5a6478; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0d0f14;
    border-right: 1px solid #1e2433;
}

/* Dataframe overrides */
.stDataFrame { border: 1px solid #1e2433; border-radius: 8px; overflow: hidden; }

/* Footer */
.footer {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: #2a3040;
    text-align: center;
    padding: 24px 0 8px;
    letter-spacing: 1px;
}
</style>
""", unsafe_allow_html=True)


# ── Data loader ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_universe():
    path = "output/universe.csv"
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df = df[df["ticker"] != "Ticker"].drop_duplicates(subset="ticker")
    numeric = ["score", "gap_pct", "rvol", "premarket_rvol",
               "premarket_momentum", "breakout_score", "trend_5d",
               "premarket_price", "avg_volume_10d"]
    for col in numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


def get_csv_timestamp():
    path = "output/universe.csv"
    if os.path.exists(path):
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "—"


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style='font-family:"IBM Plex Mono",monospace;font-size:10px;
                letter-spacing:2px;color:#4a9eff;text-transform:uppercase;
                margin-bottom:20px;'>
        ▸ FILTERS
    </div>
    """, unsafe_allow_html=True)

    min_score = st.slider("Min Score", 0.0, 20.0, 10.0, 0.5)
    min_gap   = st.slider("Min Gap %", -5.0, 10.0, 0.0, 0.1)
    min_rvol  = st.slider("Min RVOL", 0.0, 5.0, 0.0, 0.1)
    top_n     = st.slider("Show top N", 5, 50, 20, 5)

    st.markdown("---")
    st.markdown("""
    <div style='font-family:"IBM Plex Mono",monospace;font-size:10px;
                letter-spacing:2px;color:#4a9eff;text-transform:uppercase;
                margin-bottom:12px;'>
        ▸ SCORE GUIDE
    </div>
    <div style='font-family:"IBM Plex Mono",monospace;font-size:11px;color:#5a6478;line-height:2;'>
        <span style='color:#2ecc71'>●</span> ≥ 15 — Strong momentum<br>
        <span style='color:#f39c12'>●</span> 10–15 — Watchlist<br>
        <span style='color:#5a6478'>●</span> &lt; 10 — No signal<br><br>
        Long-only: gap &lt; 0 → score = 0<br>
        Flat: score capped at 9
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🔄  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown(f"""
    <div style='font-family:"IBM Plex Mono",monospace;font-size:9px;color:#2a3040;margin-top:12px;'>
        Last update: {get_csv_timestamp()}
    </div>
    """, unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────

df = load_universe()

if df.empty:
    st.markdown("""
    <div style='text-align:center;padding:80px 0;'>
        <div style='font-family:"IBM Plex Mono",monospace;font-size:13px;
                    color:#4a9eff;letter-spacing:3px;'>NO DATA</div>
        <p style='color:#5a6478;margin-top:12px;'>
            Run <code>universe.py</code> locally or wait for the GitHub Action.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Apply filters
filtered = df[
    (df["score"]   >= min_score) &
    (df["gap_pct"] >= min_gap / 100) &
    (df["rvol"]    >= min_rvol)
].head(top_n)


# ── Header ────────────────────────────────────────────────────────────────────

now_et = datetime.now(timezone.utc).strftime("%H:%M UTC")
st.markdown(f"""
<div class="scanner-header">
    <div>
        <div class="scanner-title">📡 Market Universe Scanner</div>
        <div class="scanner-subtitle">NASDAQ 100 + S&P 500 · Pre-Market Momentum</div>
    </div>
    <div style='font-family:"IBM Plex Mono",monospace;font-size:11px;color:#5a6478;text-align:right;'>
        {now_et}<br>
        <span style='color:#2a3040;font-size:9px;'>{get_csv_timestamp()}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Metrics ───────────────────────────────────────────────────────────────────

total        = len(df)
strong       = len(df[df["score"] >= 15])
watchlist    = len(df[(df["score"] >= 10) & (df["score"] < 15)])
gapping      = len(df[df["gap_pct"] > 0.01])

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Universe</div>
        <div class="metric-value blue">{total}</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Strong (≥15)</div>
        <div class="metric-value green">{strong}</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Watchlist (10–15)</div>
        <div class="metric-value amber">{watchlist}</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Gapping Up</div>
        <div class="metric-value blue">{gapping}</div>
    </div>""", unsafe_allow_html=True)


# ── Candidate table ───────────────────────────────────────────────────────────

st.markdown(f"""
<div style='font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:2px;
            text-transform:uppercase;color:#4a9eff;margin:24px 0 12px;'>
    ▸ CANDIDATES ({len(filtered)} shown)
</div>
""", unsafe_allow_html=True)

if filtered.empty:
    st.info("No tickers match current filters.")
else:
    # Build display dataframe
    display = filtered.copy()

    def fmt_score(s):
        if s >= 15:   return f"🟢 {s:.1f}"
        elif s >= 10: return f"🟡 {s:.1f}"
        else:         return f"⚫ {s:.1f}"

    def fmt_gap(g):
        pct = g * 100
        if pct > 0.1:  return f"+{pct:.2f}%"
        elif pct < -0.1: return f"{pct:.2f}%"
        else:           return "—"

    def fmt_trend(t):
        filled = "█" * int(t)
        empty  = "░" * (5 - int(t))
        return f"{filled}{empty} {int(t)}/5"

    display["Score"]       = display["score"].apply(fmt_score)
    display["Gap"]         = display["gap_pct"].apply(fmt_gap)
    display["RVOL"]        = display["rvol"].apply(lambda x: f"{x:.1f}x")
    display["PM RVOL"]     = display["premarket_rvol"].apply(lambda x: f"{x:.1f}x")
    display["Momentum"]    = display["premarket_momentum"].apply(lambda x: f"{x:.3f}")
    display["Breakout"]    = display["breakout_score"].apply(lambda x: f"{x:.3f}")
    display["Trend"]       = display["trend_5d"].apply(fmt_trend)
    display["PM Price"]    = display["premarket_price"].apply(lambda x: f"${x:.2f}")

    show_cols = ["ticker", "Score", "Gap", "PM Price", "RVOL", "PM RVOL",
                 "Momentum", "Breakout", "Trend"]
    display = display[show_cols].rename(columns={"ticker": "Ticker"})

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=min(50 + len(display) * 35, 600),
    )


# ── Score distribution chart ──────────────────────────────────────────────────

st.markdown("""
<div style='font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:2px;
            text-transform:uppercase;color:#4a9eff;margin:28px 0 12px;'>
    ▸ SCORE DISTRIBUTION
</div>
""", unsafe_allow_html=True)

col_a, col_b = st.columns([2, 1])

with col_a:
    import json
    # Build histogram data manually (no extra deps)
    bins   = list(range(0, 22, 1))
    counts = pd.cut(df["score"], bins=bins).value_counts().sort_index()

    chart_df = pd.DataFrame({
        "Score Bucket": [f"{b.left:.0f}" for b in counts.index],
        "Count": counts.values,
    })
    st.bar_chart(chart_df.set_index("Score Bucket"), color="#4a9eff")

with col_b:
    st.markdown("""
    <div style='background:#141820;border:1px solid #1e2433;border-radius:8px;
                padding:20px;font-family:"IBM Plex Mono",monospace;font-size:11px;
                color:#5a6478;line-height:2.2;'>
    """, unsafe_allow_html=True)

    if not df.empty:
        top1 = df.iloc[0]
        gap_str = f"+{top1['gap_pct']*100:.2f}%" if top1['gap_pct'] > 0 else "—"
        st.markdown(f"""
        <div style='background:#141820;border:1px solid #1e2433;border-radius:8px;
                    padding:20px;font-family:"IBM Plex Mono",monospace;font-size:11px;
                    color:#5a6478;line-height:2.2;'>
            <div style='color:#4a9eff;font-size:9px;letter-spacing:2px;
                        text-transform:uppercase;margin-bottom:10px;'>TOP CANDIDATE</div>
            <div style='font-size:22px;font-weight:700;color:#e8eaf0;
                        margin-bottom:4px;'>{top1['ticker']}</div>
            <div>Score &nbsp;<span style='color:#2ecc71'>{top1['score']:.1f}</span></div>
            <div>Gap &nbsp;&nbsp;&nbsp;<span style='color:#2ecc71'>{gap_str}</span></div>
            <div>RVOL &nbsp;&nbsp;<span style='color:#e8eaf0'>{top1['rvol']:.1f}x</span></div>
            <div>Trend &nbsp;<span style='color:#e8eaf0'>{int(top1['trend_5d'])}/5</span></div>
        </div>
        """, unsafe_allow_html=True)


# ── Raw data expander ─────────────────────────────────────────────────────────

with st.expander("📄  Full raw universe (all tickers)"):
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv = df.to_csv(index=False)
    st.download_button(
        "⬇️  Download CSV",
        data=csv,
        file_name=f"universe_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="footer">
    AUTOMATED SCANNER · NOT FINANCIAL ADVICE · DATA VIA YFINANCE
</div>
""", unsafe_allow_html=True)
