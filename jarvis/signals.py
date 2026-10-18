import math

import pandas as pd

from jarvis.market import CORE_INDEX_FUNDS

VOL_LIMITS = {"Conservative": 0.20, "Moderate": 0.35, "Aggressive": 0.70}

DISCLAIMER = (
    "JARVIS ratings are educational research signals built from price history and your stated goals. "
    "They are not financial advice and cannot predict the future. Always make your own decision."
)


def rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    strength = gain / loss.replace(0, math.nan)
    return float((100 - 100 / (1 + strength)).fillna(100).iloc[-1])


def pct_change(closes, days):
    if len(closes) <= days:
        return None
    return float(closes.iloc[-1] / closes.iloc[-1 - days] - 1)


def metrics(closes, trading_days=252):
    closes = closes.dropna()
    last = float(closes.iloc[-1])
    window = closes.tail(trading_days)
    return {
        "price": last,
        "as_of": str(pd.Timestamp(closes.index[-1]).date()),
        "change_1d": pct_change(closes, 1),
        "change_1w": pct_change(closes, 5),
        "change_1m": pct_change(closes, 21),
        "change_1y": pct_change(closes, trading_days),
        "sma50": float(closes.tail(50).mean()) if len(closes) >= 50 else None,
        "sma200": float(closes.tail(200).mean()) if len(closes) >= 200 else None,
        "rsi14": rsi(closes) if len(closes) > 15 else None,
        "high_52w": float(window.max()),
        "drawdown": float(last / window.max() - 1),
        "volatility": float(closes.pct_change().tail(trading_days).std() * math.sqrt(trading_days)) if len(closes) > 20 else None,
    }


def analyze(symbol, closes, profile, asset_type="Stock", holding=None, portfolio_value=None):
    trading_days = 365 if asset_type == "Crypto" or symbol.endswith("-USD") else 252
    data = metrics(closes, trading_days)
    risk = profile.get("risk", "Moderate")
    horizon = int(float(profile.get("horizon_years", 10) or 10))
    reasons = []
    score = 0.0

    def note(points, text):
        nonlocal score
        score += points
        reasons.append({"points": points, "text": text})

    price, sma50, sma200 = data["price"], data["sma50"], data["sma200"]

    if sma200:
        if price > sma200:
            note(1, f"Long-term uptrend: price is {price / sma200 - 1:+.1%} vs its 200-day average.")
        else:
            note(-1, f"Long-term downtrend: price is {price / sma200 - 1:+.1%} below its 200-day average.")
    else:
        reasons.append({"points": 0, "text": "Less than 200 days of history, so the long-term trend is unclear."})

    if sma50 and sma200:
        if sma50 > sma200:
            note(0.5, "Momentum positive: 50-day average is above the 200-day average.")
        else:
            note(-0.5, "Momentum negative: 50-day average is below the 200-day average.")

    drawdown = data["drawdown"]
    if sma200 and price > sma200 and -0.20 <= drawdown <= -0.05:
        note(1, f"Pullback within an uptrend: {drawdown:.0%} from its 52-week high, often a better entry point.")
    elif drawdown < -0.30:
        note(-1, f"Deep slump: {drawdown:.0%} from its 52-week high.")
    elif drawdown > -0.02:
        reasons.append({"points": 0, "text": "Trading near its 52-week high."})

    if data["rsi14"] is not None:
        if data["rsi14"] < 30:
            note(0.5, f"Oversold (RSI {data['rsi14']:.0f}): selling may be overdone in the short term.")
        elif data["rsi14"] > 70:
            note(-0.5, f"Overbought (RSI {data['rsi14']:.0f}): short-term run-up, consider waiting for a dip.")

    volatility = data["volatility"]
    limit = VOL_LIMITS.get(risk, 0.35)
    if volatility is not None:
        if volatility > limit:
            note(-1, f"Too volatile for your {risk.lower()} risk level: swings about {volatility:.0%} a year (your comfort zone is under {limit:.0%}).")
        else:
            reasons.append({"points": 0, "text": f"Volatility of about {volatility:.0%} a year fits your {risk.lower()} risk level."})

    core = symbol.upper() in CORE_INDEX_FUNDS
    if core and horizon >= 5:
        note(1.5, f"Broad, diversified index fund that matches a {horizon}-year horizon. Steady investing (dollar-cost averaging) has historically worked well for funds like this.")

    if holding and portfolio_value:
        position = holding["shares"] * price
        weight = position / portfolio_value
        gain = price / holding["avg_cost"] - 1 if holding.get("avg_cost") else None
        if weight > 0.25 and not core:
            note(-1, f"Concentration risk: this is {weight:.0%} of your tracked portfolio.")
        if gain is not None:
            reasons.append({"points": 0, "text": f"You hold {holding['shares']:g} shares, {gain:+.1%} vs your average cost."})

    rating = "Buy" if score >= 2 else "Avoid" if score <= -1.5 else "Hold"
    if core and rating == "Avoid":
        rating = "Hold"
        reasons.append({"points": 0, "text": "Core index funds are rated Hold at worst: for long-term investors, timing broad-market dips rarely beats staying invested."})
    confidence = "High" if abs(score) >= 3 else "Medium" if abs(score) >= 1.5 else "Low"
    action = {
        "Buy": "Consider buying or adding (in steps, not all at once).",
        "Hold": "Keep what you have; no strong signal to buy more or sell.",
        "Avoid": "Consider not buying now; if you own it, review whether it still fits your plan.",
    }[rating]
    return {
        "symbol": symbol,
        "asset_type": asset_type,
        "rating": rating,
        "score": round(score, 2),
        "confidence": confidence,
        "action": action,
        "reasons": reasons,
        "metrics": data,
    }


def summary_line(result):
    data = result["metrics"]
    day = f", {data['change_1d']:+.1%} today" if data["change_1d"] is not None else ""
    return f"{result['symbol']}: {result['rating']} ({result['confidence'].lower()} confidence), ${data['price']:,.2f}{day}."
