# apps/api/integrations/webhooks.py
from __future__ import annotations
import os
import json
import time
import logging
from typing import Optional
import urllib.request
import urllib.error

log = logging.getLogger("webhooks")

# ENV:
# TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# DISCORD_WEBHOOK_URL

def _http_post(url: str, payload: dict, timeout=8) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode()
    except urllib.error.HTTPError as e:
        log.warning("HTTPError %s: %s", e.code, e.read().decode())
        return e.code
    except Exception as e:
        log.warning("POST error: %s", e)
        return 599

def send_discord(text: str) -> bool:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        log.info("Discord webhook not set")
        return False
    payload = {"content": text[:1990]}
    # prosty retry
    for _ in range(3):
        code = _http_post(url, payload)
        if 200 <= code < 300:
            return True
        time.sleep(1.0)
    return False

def send_telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        log.info("Telegram creds not set")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "Markdown"}
    for _ in range(3):
        code = _http_post(url, payload)
        if 200 <= code < 300:
            return True
        time.sleep(1.0)
    return False

def format_signal_message(sig: dict) -> str:
    """
    sig: {symbol, dir, entry, sl, tp[], lev, risk, expected_net_pct, confidence, ts}
    """
    tp = sig.get("tp") or []
    tps = ", ".join([str(x) for x in tp])
    return (
        f"📈 *Trader AI*\n"
        f"Symbol: {sig.get('symbol')}\n"
        f"Side: {sig.get('dir')}  Lev: {sig.get('lev')}x  Risk: {sig.get('risk')}\n"
        f"Entry: {sig.get('entry')}  SL: {sig.get('sl')}\n"
        f"TPs: {tps}\n"
        f"Expected net %: {sig.get('expected_net_pct')}  Conf: {sig.get('confidence')}\n"
    )
