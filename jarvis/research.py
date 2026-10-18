import io
import re

import pandas as pd

from jarvis import db, market, signals

SYMBOL_COLUMNS = ("symbol", "ticker", "instrument")
SHARE_COLUMNS = ("quantity", "shares", "qty")
COST_COLUMNS = ("average cost basis", "avg cost basis", "average cost", "avg cost", "cost basis per share")


def tracked_symbols():
    return sorted(set(db.watchlist_symbols()) | {row["symbol"] for row in db.all_rows("holdings")})


def asset_types():
    return {row["symbol"]: row["asset_type"] for row in db.all_rows("watchlist")}


def combined_holdings():
    totals = {}
    for row in db.all_rows("holdings"):
        entry = totals.setdefault(row["symbol"], {"symbol": row["symbol"], "shares": 0.0, "cost": 0.0, "accounts": set()})
        entry["shares"] += row["shares"]
        entry["cost"] += row["shares"] * (row["avg_cost"] or 0)
        entry["accounts"].add(row["account"])
    return {
        symbol: {**entry, "avg_cost": entry["cost"] / entry["shares"] if entry["shares"] else 0, "accounts": ", ".join(sorted(entry["accounts"]))}
        for symbol, entry in totals.items()
    }


def portfolio(prices):
    holdings = combined_holdings()
    rows = [
        {
            "Symbol": symbol,
            "Accounts": entry["accounts"],
            "Shares": entry["shares"],
            "Avg cost": entry["avg_cost"],
            "Price": prices.get(symbol),
            "Value": entry["shares"] * prices[symbol] if symbol in prices else None,
            "Gain": (prices[symbol] / entry["avg_cost"] - 1) if symbol in prices and entry["avg_cost"] else None,
        }
        for symbol, entry in holdings.items()
    ]
    frame = pd.DataFrame(rows, columns=["Symbol", "Accounts", "Shares", "Avg cost", "Price", "Value", "Gain"])
    total = float(frame["Value"].fillna(0).sum()) if not frame.empty else 0.0
    return frame.assign(Weight=frame["Value"] / total if total else None), total


def run_analysis(fetch=None, symbols=None):
    fetch = fetch or market.fetch_history
    symbols = symbols or tracked_symbols()
    history = fetch(symbols)
    prices = {symbol: float(closes.iloc[-1]) for symbol, closes in history.items()}
    _, total = portfolio(prices)
    holdings = combined_holdings()
    types = asset_types()
    profile = db.profile()
    results = [
        signals.analyze(
            symbol,
            history[symbol],
            profile,
            asset_type=types.get(symbol, market.guess_type(symbol)),
            holding=holdings.get(symbol),
            portfolio_value=total,
        )
        for symbol in symbols
        if symbol in history and len(history[symbol]) > 20
    ]
    missing = [symbol for symbol in symbols if symbol not in history]
    return results, history, missing


def _find(columns, candidates):
    lowered = {re.sub(r"\s+", " ", column.strip().lower()): column for column in columns}
    return next((lowered[name] for name in candidates if name in lowered), None)


def _number(value):
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_positions_csv(content, account="Fidelity"):
    text = content.decode("utf-8-sig", errors="ignore") if isinstance(content, bytes) else content
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if any(name in line.lower() for name in SYMBOL_COLUMNS)), 0)
    frame = pd.read_csv(io.StringIO("\n".join(lines[start:])), on_bad_lines="skip", dtype=str)
    symbol_col, share_col, cost_col = _find(frame.columns, SYMBOL_COLUMNS), _find(frame.columns, SHARE_COLUMNS), _find(frame.columns, COST_COLUMNS)
    if not symbol_col or not share_col:
        raise ValueError("Couldn't find Symbol and Quantity columns in that file.")
    positions = []
    for _, row in frame.iterrows():
        symbol = str(row[symbol_col] or "").strip().upper()
        shares = _number(row[share_col])
        if not symbol or symbol == "NAN" or "*" in symbol or "PENDING" in symbol or not shares or not re.fullmatch(r"[A-Z0-9.\-^=]{1,12}", symbol):
            continue
        positions.append({"symbol": symbol, "shares": shares, "avg_cost": (_number(row[cost_col]) if cost_col else None) or 0.0, "account": account})
    return positions


def import_positions(positions, replace_account=True):
    if replace_account:
        for account in {position["account"] for position in positions}:
            for row in db.find("holdings", account=account):
                db.delete("holdings", row["id"])
    for position in positions:
        db.add("holdings", **position)
    return len(positions)
