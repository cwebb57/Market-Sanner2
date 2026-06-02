"""
universe.py — Daily pre-market universe builder.
Scans NASDAQ 100 + S&P 500 tickers, scores by momentum, writes output/universe.csv.
"""

import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone


# ── Ticker universe ──────────────────────────────────────────────────────────

NASDAQ_100 = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","GOOG","AVGO","COST",
    "NFLX","AMD","ADBE","QCOM","LIN","AMAT","ISRG","TXN","INTU","CMCSA",
    "BKNG","VRTX","REGN","PANW","ADI","LRCX","KLAC","SNPS","CDNS","MELI",
    "ASML","CSX","MDLZ","ORLY","ABNB","CRWD","MNST","FTNT","KDP","MAR",
    "CTAS","ROST","WDAY","DXCM","TEAM","SGEN","BIIB","IDXX","ALGN","EXC",
    "PCAR","ODFL","PAYX","FAST","VRSK","CPRT","GEHC","AEP","EA","DDOG",
    "ON","XEL","CTSH","FANG","ANSS","MCHP","SMCI","ZS","ILMN","MTCH",
    "ENPH","LCID","WBA","RIVN","SIRI","DLTR","MRNA","JD","PDD","BIDU",
    "NTES","TCOM","WBD","TTWO","EBAY","ZM","DOCU","OKTA","PINS","SNAP",
    "LYFT","UBER","DASH","RBLX","COIN","HOOD","SOFI","AFRM","UPST","OPEN",
]

SP500_SAMPLE = [
    "JPM","BAC","WFC","GS","MS","BLK","C","USB","PNC","TFC",
    "BRK-B","V","MA","PYPL","AXP","COF","DFS","SYF","ALL","MET",
    "JNJ","PFE","MRK","ABBV","LLY","BMY","AMGN","GILD","CVS","UNH",
    "HD","LOW","TGT","WMT","COST","TJX","ROST","DG","DLTR","KR",
    "XOM","CVX","COP","EOG","SLB","MPC","VLO","PSX","OXY","DVN",
    "CAT","DE","HON","MMM","GE","RTX","LMT","NOC","BA","GD",
    "NEE","DUK","SO","AEE","EIX","PCG","ED","AWK","WEC","ETR",
    "PG","KO","PEP","PM","MO","CL","GIS","K","CPB","SJM",
    "T","VZ","TMUS","CHTR","CMCSA","DIS","NFLX","PARA","FOX","NWS",
    "UPS","FDX","DAL","UAL","AAL","LUV","JBLU","ALK","HA","SAVE",
    "AMT","CCI","EQIX","PLD","SPG","O","VICI","WPC","NNN","STAG",
    "LIN","APD","ECL","EMN","DD","DOW","PPG","SHW","NEM","FCX",
    "AMZN","AAPL","MSFT","GOOGL","META","TSLA","NVDA","NFLX","CRM","NOW",
    "ORCL","IBM","CSCO","INTC","HPQ","HPE","DELL","ANET","KEYS","CDNS",
]

# Deduplicated combined universe
ALL_TICKERS = sorted(set(NASDAQ_100 + SP500_SAMPLE))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize(series, mn, mx):
    return ((series - mn) / (mx - mn)).clip(0, 1)


def _safe_min_max(series):
    if series is None or len(series) == 0:
        return 0.0, 1.0
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return 0.0, 1.0
    mn, mx = float(s.min()), float(s.max())
    if mx == mn:
        return mn, mn + 1.0
    return mn, mx


# ── Main ─────────────────────────────────────────────────────────────────────

def build_universe(target_date=None):
    today    = target_date or datetime.now(timezone.utc).date()
    end_dt   = today
    start_dt = today - timedelta(days=20)

    records = []

    for t in ALL_TICKERS:
        try:
            ticker = yf.Ticker(t)

            # ── Historical daily data ────────────────────────────────────────
            hist = ticker.history(start=start_dt, end=end_dt)
            if hist.empty or len(hist) < 10:
                print(f"Skipping {t}: insufficient history")
                continue

            yesterday_close  = float(hist["Close"].iloc[-1])
            yesterday_volume = float(hist["Volume"].iloc[-1])

            if yesterday_close < 1.0:
                print(f"Skipping {t}: price ${yesterday_close:.2f} below $1 minimum")
                continue

            last_10         = hist.tail(10)
            avg_volume_10d  = float(hist["Volume"].tail(10).mean())
            avg_close_10d   = float(hist["Close"].tail(10).mean())
            atr_10d         = float((last_10["High"] - last_10["Low"]).mean())
            trend_5d        = int((hist["Close"].diff() > 0).tail(5).sum())

            breakout_score  = float(
                (yesterday_close - avg_close_10d) / avg_close_10d
                if avg_close_10d else 0
            )

            # ── Pre-market data ──────────────────────────────────────────────
            premarket_price  = None
            premarket_volume = 0

            try:
                info = ticker.info
                premarket_price  = info.get("preMarketPrice")
                premarket_volume = info.get("preMarketVolume") or 0
            except Exception:
                pass

            if not premarket_price or premarket_price <= 0:
                premarket_price = yesterday_close

            # ── Feature engineering ──────────────────────────────────────────
            gap_pct         = (premarket_price - yesterday_close) / yesterday_close
            rvol            = yesterday_volume / avg_volume_10d if avg_volume_10d else 0
            premarket_rvol  = premarket_volume / avg_volume_10d if avg_volume_10d else 0
            volatility_score = atr_10d / yesterday_close if yesterday_close else 0

            records.append({
                "ticker":           t,
                "premarket_price":  round(premarket_price, 2),
                "premarket_volume": int(premarket_volume),
                "gap_pct":          float(gap_pct),
                "rvol":             float(rvol),
                "premarket_rvol":   float(premarket_rvol),
                "avg_volume_10d":   int(avg_volume_10d),
                "trend_5d":         int(trend_5d),
                "breakout_score":   float(breakout_score),
                "atr_10d":          float(atr_10d),
                "volatility_score": float(volatility_score),
            })

        except Exception:
            continue

    if not records:
        print("Warning: no records generated")
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # ── Normalization ────────────────────────────────────────────────────────
    gap_min,     gap_max     = _safe_min_max(df["gap_pct"])
    rvol_min,    rvol_max    = _safe_min_max(df["rvol"])
    pre_rvol_min,pre_rvol_max = _safe_min_max(df["premarket_rvol"])
    brk_min,     brk_max     = _safe_min_max(df["breakout_score"])
    vol_min,     vol_max     = _safe_min_max(df["volatility_score"])

    df["norm_gap"]         = _normalize(df["gap_pct"],         gap_min,      gap_max)
    df["norm_rvol"]        = _normalize(df["rvol"],            rvol_min,     rvol_max)
    df["norm_pre_rvol"]    = _normalize(df["premarket_rvol"],  pre_rvol_min, pre_rvol_max)
    df["norm_breakout"]    = _normalize(df["breakout_score"],  brk_min,      brk_max)
    df["norm_volatility"]  = _normalize(df["volatility_score"],vol_min,      vol_max)
    df["norm_trend"]       = df["trend_5d"] / 5.0

    # Premarket momentum = gap + premarket RVOL
    pm_raw = df["norm_gap"].clip(lower=0) + df["norm_pre_rvol"].clip(lower=0)
    pm_min, pm_max = _safe_min_max(pm_raw)
    df["premarket_momentum"] = _normalize(pm_raw, pm_min, pm_max)

    # ── Scoring ──────────────────────────────────────────────────────────────
    base_score = (
        5.0 * df["premarket_momentum"] +
        3.0 * df["norm_gap"] +
        2.0 * df["norm_rvol"] +
        1.5 * df["norm_breakout"] +
        1.0 * df["norm_trend"] +
        0.5 * df["norm_volatility"]
    )

    score = base_score.copy()
    score[df["gap_pct"] < 0]  = 0.0
    score[df["gap_pct"] == 0] = score[df["gap_pct"] == 0].clip(upper=9.0)

    df["score"] = score.round(4)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)
    return df


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    df = build_universe()

    if df.empty:
        print("No data — nothing written")
    else:
        out_path = "output/universe.csv"
        df.to_csv(out_path, index=False)
        print(f"Universe written — {len(df)} tickers scored")

        top = df[df["score"] > 9].head(5)
        if not top.empty:
            print("\nTop candidates (score > 9):")
            print(top[["ticker", "score", "gap_pct", "premarket_rvol",
                        "premarket_momentum", "breakout_score"]].to_string(index=False))
        else:
            print("\nNo tickers above score 9 today")
