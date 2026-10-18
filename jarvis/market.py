import hashlib

import numpy as np
import pandas as pd

from jarvis.config import setting

CRYPTO = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "AVAX", "DOT", "LINK", "MATIC", "BNB", "SHIB"}

CORE_INDEX_FUNDS = {"VOO", "SPY", "IVV", "SPLG", "VTI", "ITOT", "SCHB", "VT", "VXUS", "SCHX", "FXAIX", "FSKAX", "SWPPX", "^GSPC"}

STARTER_WATCHLIST = [
    ("VOO", "ETF", "Vanguard S&P 500"),
    ("QQQ", "ETF", "Nasdaq-100"),
    ("VTI", "ETF", "Total US market"),
    ("GLD", "Gold", "Gold ETF"),
    ("BTC-USD", "Crypto", "Bitcoin"),
    ("ETH-USD", "Crypto", "Ethereum"),
    ("AAPL", "Stock", "Apple"),
    ("NVDA", "Stock", "Nvidia"),
]


def normalize(symbol, asset_type=""):
    symbol = symbol.strip().upper()
    if (asset_type == "Crypto" or symbol in CRYPTO) and "-" not in symbol:
        return f"{symbol}-USD"
    if symbol in ("GOLD", "XAU"):
        return "GC=F"
    if symbol in ("S&P500", "S&P 500", "SP500", "SPX"):
        return "^GSPC"
    return symbol


def guess_type(symbol):
    if symbol.endswith("-USD"):
        return "Crypto"
    if symbol in ("GC=F", "GLD", "IAU", "SGOL"):
        return "Gold"
    if symbol in CORE_INDEX_FUNDS or symbol.startswith("^"):
        return "Index"
    return "Stock"


DEMO_PROFILES = {
    "VOO": (550, 0.10, 0.16), "SPY": (600, 0.10, 0.16), "QQQ": (500, 0.13, 0.22), "VTI": (290, 0.10, 0.17),
    "GLD": (240, 0.08, 0.14), "GC=F": (2600, 0.08, 0.14), "BTC-USD": (90000, 0.25, 0.55), "ETH-USD": (3200, -0.20, 0.75),
    "AAPL": (230, 0.05, 0.28), "NVDA": (140, 0.30, 0.50), "TSLA": (250, -0.35, 0.65),
}


def demo_history(symbols, days=520):
    history = {}
    for symbol in symbols:
        seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
        start, drift, vol = DEMO_PROFILES.get(symbol, (100 + seed % 300, (seed % 40 - 15) / 100, 0.25 + (seed % 30) / 100))
        rng = np.random.default_rng(seed)
        returns = rng.normal(drift / 252, vol / np.sqrt(252), days)
        index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
        history[symbol] = pd.Series(start * np.exp(np.cumsum(returns)) / np.exp(returns.sum()), index=index, name=symbol)
    return history


def using_demo_data():
    return setting("JARVIS_FAKE_MARKET", "") not in ("", "0", "false", "False")


def fetch_history(symbols, period="2y"):
    symbols = sorted(set(symbols))
    if not symbols:
        return {}
    if using_demo_data():
        return demo_history(symbols)
    import yfinance as yf

    raw = yf.download(symbols, period=period, interval="1d", auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        return {}
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": symbols[0]})
    return {symbol: closes[symbol].dropna() for symbol in closes.columns if symbol in symbols and not closes[symbol].dropna().empty}
