"""Matrik-N Flask dashboard."""
from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file

from signal_engine import get_signal

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
INDEX_PATH = ROOT / "index.html"

app = Flask(__name__)

_cache: dict = {}
CACHE_TTL = 15.0


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"bot_username": "matrixauusdbot", "chat_id": ""}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def cached_signal(period: str) -> dict:
    now = time.time()
    key = period
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    data = get_signal(period)
    _cache[key] = (now, data)
    return data


@app.get("/")
def index():
    period = request.args.get("period", "5d")
    html = INDEX_PATH.read_text(encoding="utf-8")
    try:
        state = cached_signal(period)
        inject = f"<script>window.__INITIAL_STATE__={json.dumps(state)};</script>"
        html = html.replace("</head>", inject + "\n</head>")
    except Exception as e:
        inject = f"<script>window.__INITIAL_STATE__=null;console.warn({json.dumps(str(e))});</script>"
        html = html.replace("</head>", inject + "\n</head>")
    return Response(html, mimetype="text/html")


@app.get("/api/signal")
def api_signal():
    period = request.args.get("period", "5d")
    try:
        return jsonify(cached_signal(period))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.get("/api/snapshot")
def api_snapshot():
    s = cached_signal(request.args.get("period", "5d"))
    text = (
        f"Matrik-N XAUUSD Signal\n"
        f"{s['signal']}  score {s['score']}  conf {s['confidence']}%\n"
        f"Price {s['price']}  ({s['change_pct']}%)\n"
        f"Entry {s['levels']['entry']}  SL {s['levels']['stop']}  TP {s['levels']['target']}\n"
        f"{s['time']} UTC  {s['symbol']}\n"
    )
    return Response(text, mimetype="text/plain")


@app.get("/api/signal/card.png")
def api_card():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = cached_signal(request.args.get("period", "5d"))
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="#0b0f16")
    ax.set_facecolor("#121722")
    ax.axis("off")
    color = {"BUY": "#22c55e", "SELL": "#ef4444", "NEUTRAL": "#64748b"}[s["signal"]]
    ax.text(0.05, 0.88, "Matrik-N  ·  XAUUSD", color="#f5b301", fontsize=12, fontweight="bold")
    ax.text(0.05, 0.68, s["signal"], color=color, fontsize=36, fontweight="bold")
    ax.text(0.05, 0.50, f"Price  {s['price']}", color="#e7edf6", fontsize=18)
    ax.text(0.05, 0.36, f"Score {s['score']}   Confidence {s['confidence']}%", color="#8ba0bd", fontsize=12)
    ax.text(0.05, 0.22, f"Entry {s['levels']['entry']}   SL {s['levels']['stop']}   TP {s['levels']['target']}", color="#e7edf6", fontsize=11)
    ax.text(0.05, 0.08, f"{s['time']} UTC  ·  not financial advice", color="#5f7189", fontsize=9)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.get("/api/bot/config")
def bot_config_get():
    return jsonify(load_config())


@app.post("/api/bot/config")
def bot_config_post():
    body = request.get_json(silent=True) or {}
    cfg = load_config()
    if "bot_username" in body:
        cfg["bot_username"] = str(body["bot_username"]).lstrip("@")
    if "chat_id" in body:
        cfg["chat_id"] = str(body["chat_id"])
    save_config(cfg)
    return jsonify(cfg)


@app.get("/api/bot/target")
def bot_target():
    u = (load_config().get("bot_username") or "matrixauusdbot").lstrip("@")
    return jsonify({"url": f"https://t.me/{u}", "username": u})


@app.get("/api/bot/qr")
def bot_qr():
    user = (request.args.get("user") or load_config().get("bot_username") or "matrixauusdbot").lstrip("@")
    url = f"https://t.me/{user}"
    try:
        import urllib.parse
        import urllib.request
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(url)}"
        with urllib.request.urlopen(qr_url, timeout=10) as r:
            data = r.read()
        return Response(data, mimetype="image/png")
    except Exception:
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="150" height="150">
        <rect width="150" height="150" fill="#f5b301"/>
        <text x="75" y="80" text-anchor="middle" font-size="12">t.me/{user}</text></svg>'''
        return Response(svg, mimetype="image/svg+xml")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
