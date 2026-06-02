"""
send_alert.py — runs after universe.py in the GitHub Action.

Three scheduled runs daily (Mon-Fri, US Eastern time):
  06:00 ET (10:00 UTC) — morning scan: score > THRESHOLD AND gap > 0
  07:30 ET (11:30 UTC) — mid-morning check: score > THRESHOLD
  09:00 ET (13:00 UTC) — final check: 30 min before open

Sends a Telegram message to your bot/channel.

Required GitHub Secrets:
  TELEGRAM_BOT_TOKEN  — from @BotFather
  TELEGRAM_CHAT_ID    — your chat or channel ID
"""

import os
import sys
import urllib.request
import urllib.parse
import json
import pandas as pd
from datetime import datetime, timezone

SCORE_THRESHOLD = 10


# ── Run context ───────────────────────────────────────────────────────────────

def get_run_context():
    utc_hour = datetime.now(timezone.utc).hour
    if utc_hour == 10:
        return "Morning scan", "06:00 ET", True
    elif utc_hour == 11:
        return "Mid-morning check", "07:30 ET", False
    elif utc_hour == 13:
        return "Final check before open", "09:00 ET", False
    else:
        return "Manual scan", "Now", True


# ── Data ─────────────────────────────────────────────────────────────────────

def load_universe():
    path = "output/universe.csv"
    if not os.path.exists(path):
        print("No universe.csv found — skipping alert")
        sys.exit(0)
    df = pd.read_csv(path)
    df = df[df["ticker"] != "Ticker"].drop_duplicates(subset="ticker")
    for col in ["score", "gap_pct", "rvol", "premarket_rvol",
                "breakout_score", "trend_5d"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def get_candidates(df, is_morning_scan):
    if is_morning_scan:
        return df[
            (df["score"] > SCORE_THRESHOLD) &
            (df["gap_pct"] > 0)
        ].head(5)
    else:
        return df[df["score"] > SCORE_THRESHOLD].head(5)


# ── Message builder ───────────────────────────────────────────────────────────

def build_message(candidates, run_name, et_time, is_morning_scan):
    today = datetime.now(timezone.utc).strftime("%a %b %-d %Y")
    count = len(candidates)

    if is_morning_scan:
        context = "Gapping up pre-market with elevated volume. Review before entry."
        action  = "Market opens 09:30 ET"
    elif "07:30" in et_time:
        context = "Momentum holding. 2 hours to open."
        action  = "Run pre-trade check — 09:30 ET open"
    else:
        context = "Final check — 30 min to open. Decide now."
        action  = "⏰ Market opens in 30 minutes"

    lines = [
        f"🔍 *Momentum Scanner — {run_name}*",
        f"📅 {today} | {et_time}",
        f"📊 *{count} candidate{'s' if count > 1 else ''} above score {SCORE_THRESHOLD}*",
        f"_{context}_",
        "",
    ]

    for _, row in candidates.iterrows():
        gap_pct  = row["gap_pct"] * 100
        gap_str  = f"+{gap_pct:.1f}%" if gap_pct > 0 else "—"
        score    = row["score"]
        emoji    = "🟢" if score >= 15 else "🟡" if score >= 12 else "🔵"
        lines.append(
            f"{emoji} *{row['ticker']}*  Score: `{score:.1f}`  "
            f"Gap: `{gap_str}`  RVOL: `{row['rvol']:.1f}x`  "
            f"Trend: `{int(row['trend_5d'])}/5`"
        )

    lines += [
        "",
        f"⚡ Entry window: *09:30–10:15 ET*",
        f"🎯 Target: *+10%* | 🛑 Hard exit: *10:45 ET*",
        f"_{action}_",
        "",
        "_Not financial advice_",
    ]

    return "\n".join(lines)


# ── Telegram sender ───────────────────────────────────────────────────────────

def send_telegram(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping alert")
        sys.exit(0)

    url     = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id":    chat_id,
        "text":       message,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print(f"Telegram alert sent to chat_id {chat_id}")
            else:
                print(f"Telegram error: {result}")
                sys.exit(1)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_name, et_time, is_morning_scan = get_run_context()
    print(f"Running as: {run_name} ({et_time})")

    df         = load_universe()
    candidates = get_candidates(df, is_morning_scan)

    if candidates.empty:
        print(
            f"No candidates above score {SCORE_THRESHOLD}"
            + (" with real gap" if is_morning_scan else "")
            + f" at {et_time} — no alert sent"
        )
        sys.exit(0)

    tickers = ", ".join(candidates["ticker"].tolist())
    print(f"Found {len(candidates)} candidate(s): {tickers}")

    message = build_message(candidates, run_name, et_time, is_morning_scan)
    send_telegram(message)
