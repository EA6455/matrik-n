"""XAUUSD / gold composite signal engine (GC=F via yfinance)."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

SYMBOL = "GC=F"

PERIOD_INTERVAL = {
    "1d": ("1d", "5m"),
    "5d": ("5d", "15m"),
    "1mo": ("1mo", "1h"),
    "1m": ("1mo", "1h"),
}


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    ru = up.ewm(alpha=1 / n, adjust=False).mean()
    rd = dn.ewm(alpha=1 / n, adjust=False).mean()
    rs = ru / rd.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _stoch(df: pd.DataFrame, n: int = 14) -> pd.Series:
    ll = df["Low"].rolling(n).min()
    hh = df["High"].rolling(n).max()
    return 100 * (df["Close"] - ll) / (hh - ll).replace(0, np.nan)


def _cci(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    sma = tp.rolling(n).mean()
    mad = tp.rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - sma) / (0.015 * mad.replace(0, np.nan))


def _willr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hh = df["High"].rolling(n).max()
    ll = df["Low"].rolling(n).min()
    return -100 * (hh - df["Close"]) / (hh - ll).replace(0, np.nan)


def _adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    up = h.diff()
    dn = -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def _macd(close: pd.Series):
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd = ema12 - ema26
    signal = _ema(macd, 9)
    hist = macd - signal
    return macd, signal, hist


def _pivots(df: pd.DataFrame) -> dict:
    h, l, c = float(df["High"].iloc[-2]), float(df["Low"].iloc[-2]), float(df["Close"].iloc[-2])
    p = (h + l + c) / 3
    r1 = 2 * p - l
    s1 = 2 * p - h
    r2 = p + (h - l)
    s2 = p - (h - l)
    r3 = h + 2 * (p - l)
    s3 = l - 2 * (h - p)
    return {"pivot": p, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}


def _clamp(x, a=-100, b=100):
    return max(a, min(b, x))


def _nan_none(v):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    if isinstance(v, (np.floating,)):
        v = float(v)
        return None if math.isnan(v) else v
    return v


def _series_list(s: pd.Series):
    out = []
    for v in s.tolist():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(None)
        else:
            out.append(float(v))
    return out


def fetch_df(period: str = "5d") -> pd.DataFrame:
    p, interval = PERIOD_INTERVAL.get(period, ("5d", "15m"))
    t = yf.Ticker(SYMBOL)
    df = t.history(period=p, interval=interval, auto_adjust=False)
    if df is None or df.empty:
        df = t.history(period="5d", interval="15m", auto_adjust=False)
    if df.empty:
        raise RuntimeError("No market data from Yahoo Finance")
    df = df.dropna(subset=["Close"])
    return df


def get_signal(period: str = "5d") -> dict[str, Any]:
    df = fetch_df(period)
    close = df["Close"]
    ema9 = _ema(close, 9)
    ema21 = _ema(close, 21)
    ema50 = _ema(close, 50)
    ema200 = _ema(close, 200) if len(df) >= 50 else ema50
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    rsi = _rsi(close, 14)
    macd, macd_sig, macd_hist = _macd(close)
    stoch = _stoch(df)
    cci = _cci(df)
    willr = _willr(df)
    atr = _atr(df)
    adx = _adx(df)
    vol = df["Volume"].fillna(0)
    vol_ma = vol.rolling(20).mean()

    last = df.iloc[-1]
    price = float(last["Close"])
    prev = float(df["Close"].iloc[-2]) if len(df) > 1 else price
    change_pct = (price - prev) / prev * 100 if prev else 0.0

    e9, e21, e50, e200 = float(ema9.iloc[-1]), float(ema21.iloc[-1]), float(ema50.iloc[-1]), float(ema200.iloc[-1])
    trend = 0.0
    trend += 30 if price > e50 else -30
    trend += 25 if e50 > e200 else -25
    trend += 25 if e9 > e21 else -25
    if len(ema9) > 2:
        if ema9.iloc[-2] <= ema21.iloc[-2] and e9 > e21:
            trend += 20
        elif ema9.iloc[-2] >= ema21.iloc[-2] and e9 < e21:
            trend -= 20
    trend = _clamp(trend)

    mh = float(macd_hist.iloc[-1]) if pd.notna(macd_hist.iloc[-1]) else 0
    mv = float(macd.iloc[-1]) if pd.notna(macd.iloc[-1]) else 0
    rv = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50
    sk = float(stoch.iloc[-1]) if pd.notna(stoch.iloc[-1]) else 50
    cciv = float(cci.iloc[-1]) if pd.notna(cci.iloc[-1]) else 0
    wr = float(willr.iloc[-1]) if pd.notna(willr.iloc[-1]) else -50
    mom = 0.0
    mom += 20 if mh > 0 else -20
    mom += 15 if mv > 0 else -15
    mom += _clamp((rv - 50) * 1.2, -25, 25)
    mom += _clamp((sk - 50) * 0.4, -15, 15)
    mom += _clamp(cciv / 10, -15, 15)
    mom += _clamp((wr + 50) * 0.3, -10, 10)
    mom = _clamp(mom)

    adxv = float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else 20
    bu = float(bb_upper.iloc[-1]) if pd.notna(bb_upper.iloc[-1]) else price
    bl = float(bb_lower.iloc[-1]) if pd.notna(bb_lower.iloc[-1]) else price
    bw = bu - bl if bu != bl else 1
    pos = (price - bl) / bw  # 0 lower, 1 upper
    reversion = (0.5 - pos) * 200  # fade extremes
    if adxv > 25:
        reversion *= 0.35  # favour follow-through in strong trend
    vola = _clamp(reversion)

    vma = float(vol_ma.iloc[-1]) if pd.notna(vol_ma.iloc[-1]) and vol_ma.iloc[-1] else 1
    vratio = float(vol.iloc[-1]) / vma if vma else 1
    upbar = price >= float(last["Open"])
    vol_score = _clamp((vratio - 1) * 80 * (1 if upbar else -1))

    score = 0.42 * trend + 0.28 * mom + 0.18 * vola + 0.12 * vol_score
    score = round(_clamp(score), 1)

    if score >= 25:
        signal = "BUY"
    elif score <= -25:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    strength = "High" if abs(score) >= 55 else ("Medium" if abs(score) >= 35 else "Low")
    confidence = _clamp(30 + abs(score) * 0.5 + min(adxv, 40) * 0.4, 30, 98)

    atrv = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else price * 0.005
    stop_dist = max(atrv * 1.5, price * 0.0035)
    entry = price
    if signal == "BUY":
        stop, target = entry - stop_dist, entry + 2 * stop_dist
    elif signal == "SELL":
        stop, target = entry + stop_dist, entry - 2 * stop_dist
    else:
        stop, target = entry - stop_dist, entry + 2 * stop_dist

    swing_low = float(df["Low"].tail(40).min())
    swing_high = float(df["High"].tail(40).max())
    piv = _pivots(df) if len(df) >= 2 else {"pivot": price, "r1": price, "r2": price, "r3": price, "s1": price, "s2": price, "s3": price}

    supports = sorted([x for x in [swing_low, piv["s1"], piv["s2"], piv["pivot"]] if x < price], reverse=True)
    resists = sorted([x for x in [swing_high, piv["r1"], piv["r2"], piv["pivot"]] if x > price])
    nearest_s = supports[0] if supports else swing_low
    nearest_r = resists[0] if resists else swing_high

    def bias_label(name, val, lab, bias):
        return {"name": name, "value": val, "label": lab, "bias": bias}

    readings = [
        bias_label("RSI (14)", f"{rv:.1f}", "Overbought" if rv > 70 else ("Oversold" if rv < 30 else ("Bullish" if rv > 50 else "Bearish")), 1 if rv > 50 else -1),
        bias_label("MACD", f"{mv:.2f}", "Bullish" if mv > 0 else "Bearish", 1 if mv > 0 else -1),
        bias_label("MACD Hist", f"{mh:.2f}", "Rising" if mh > 0 else "Falling", 1 if mh > 0 else -1),
        bias_label("Stochastic %K", f"{sk:.1f}", "Overbought" if sk > 80 else ("Oversold" if sk < 20 else "Neutral"), 1 if sk > 50 else (-1 if sk < 50 else 0)),
        bias_label("CCI", f"{cciv:.1f}", "Bullish" if cciv > 0 else "Bearish", 1 if cciv > 0 else -1),
        bias_label("Williams %R", f"{wr:.1f}", "Oversold" if wr < -80 else ("Overbought" if wr > -20 else "Neutral"), 1 if wr > -50 else -1),
        bias_label("ADX", f"{adxv:.1f}", "Strong trend" if adxv > 25 else "Weak trend", 0 if adxv < 20 else 1),
        bias_label("EMA 9/21", f"{e9:.1f} / {e21:.1f}", "Bullish" if e9 > e21 else "Bearish", 1 if e9 > e21 else -1),
        bias_label("EMA 50", f"{e50:.1f}", "Price above" if price > e50 else "Price below", 1 if price > e50 else -1),
        bias_label("Bollinger", f"{pos*100:.0f}%", "Upper half" if pos > 0.5 else "Lower half", 1 if pos > 0.5 else -1),
        bias_label("Volume vs 20", f"{vratio:.2f}x", "Above avg" if vratio > 1 else "Below avg", 1 if (vratio > 1 and upbar) else (-1 if vratio > 1 else 0)),
    ]

    times = [i.strftime("%m-%d %H:%M") if hasattr(i, "strftime") else str(i) for i in df.index]
    chart = {
        "times": times,
        "open": _series_list(df["Open"]),
        "high": _series_list(df["High"]),
        "low": _series_list(df["Low"]),
        "close": _series_list(close),
        "volume": _series_list(vol),
        "ema9": _series_list(ema9),
        "ema21": _series_list(ema21),
        "ema50": _series_list(ema50),
        "bb_upper": _series_list(bb_upper),
        "bb_lower": _series_list(bb_lower),
        "rsi": _series_list(rsi),
        "macd": _series_list(macd),
        "macd_signal": _series_list(macd_sig),
        "macd_hist": _series_list(macd_hist),
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    day_high = float(df["High"].max())
    day_low = float(df["Low"].min())

    return {
        "symbol": SYMBOL,
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "time": now,
        "signal": signal,
        "score": score,
        "strength": strength,
        "confidence": round(confidence, 1),
        "components": {
            "trend": round(trend, 1),
            "momentum": round(mom, 1),
            "volatility": round(vola, 1),
            "volume": round(vol_score, 1),
        },
        "levels": {
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "rr": 2.0,
            "atr": round(atrv, 2),
            "nearest_support": round(nearest_s, 2),
            "nearest_resistance": round(nearest_r, 2),
        },
        "pivots": {k: round(v, 2) for k, v in piv.items()},
        "readings": readings,
        "session": {
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "range": round(day_high - day_low, 2),
            "volatility_pct": round(atrv / price * 100, 2) if price else 0,
        },
        "chart": chart,
    }
