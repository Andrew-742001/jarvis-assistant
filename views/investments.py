import pandas as pd
import streamlit as st

from jarvis import db, market, research, signals, ui

ui.setup("Investments", "📈")
ui.hero("📈 Investment Research", "Explainable Buy / Hold / Avoid suggestions for your watchlist. JARVIS never trades — you decide and act in Fidelity or Robinhood.")

if market.using_demo_data():
    st.info("Demo mode: prices are simulated (JARVIS_FAKE_MARKET is on).")

profile = db.profile()
st.caption(f"Your profile: **{profile['risk']}** risk · **{profile['horizon_years']}-year** horizon · goal: {profile['goal']} — change it in Settings.")

ratings_tab, portfolio_tab, manage_tab, alerts_tab = st.tabs(["🧭 Ratings", "💼 Portfolio", "🛠️ Watchlist & holdings", "🎯 Price alerts"])

with manage_tab:
    st.markdown("#### Watchlist")
    with st.form("add-watch", clear_on_submit=True):
        left, mid, right = st.columns([2, 1, 2])
        symbol = left.text_input("Symbol", placeholder="VOO, AAPL, BTC, GLD…")
        asset_type = mid.selectbox("Type", ["Auto", "Stock", "ETF", "Index", "Crypto", "Gold"])
        note = right.text_input("Note", placeholder="Why you're watching it")
        if st.form_submit_button("Add to watchlist", type="primary") and symbol.strip():
            normalized = market.normalize(symbol, asset_type)
            if normalized in db.watchlist_symbols():
                st.warning(f"{normalized} is already on your watchlist.")
            else:
                db.add("watchlist", symbol=normalized, asset_type=market.guess_type(normalized) if asset_type == "Auto" else asset_type, note=note)
                st.success(f"Watching {normalized}.")
    rows = db.all_rows("watchlist", "symbol")
    if not rows and st.button("Add a starter watchlist (VOO, QQQ, VTI, gold, BTC, ETH, AAPL, NVDA)"):
        for starter_symbol, starter_type, starter_note in market.STARTER_WATCHLIST:
            db.add("watchlist", symbol=starter_symbol, asset_type=starter_type, note=starter_note)
        st.rerun()
    for row in rows:
        cols = st.columns([1, 1, 3, 1])
        cols[0].markdown(f"**{row['symbol']}**")
        cols[1].caption(row["asset_type"])
        cols[2].caption(row["note"])
        if cols[3].button("Remove", key=f"unwatch-{row['id']}"):
            db.delete("watchlist", row["id"])
            st.rerun()

    st.markdown("#### Holdings (optional)")
    st.caption("Tell JARVIS what you own so it can check concentration and gains. Nothing connects to your brokerage.")
    with st.form("add-holding", clear_on_submit=True):
        cols = st.columns(4)
        holding_symbol = cols[0].text_input("Symbol", key="holding-symbol")
        shares = cols[1].number_input("Shares", min_value=0.0, step=0.01, format="%.6f")
        avg_cost = cols[2].number_input("Average cost ($)", min_value=0.0, step=0.01)
        account = cols[3].selectbox("Account", ["Fidelity", "Robinhood", "Other"])
        if st.form_submit_button("Add holding") and holding_symbol.strip() and shares > 0:
            db.add("holdings", symbol=market.normalize(holding_symbol), shares=shares, avg_cost=avg_cost, account=account)
            st.success("Holding saved.")
    uploaded = st.file_uploader("Or import a Fidelity positions CSV (Accounts → Positions → Download)", type="csv")
    if uploaded and st.button("Import positions"):
        try:
            count = research.import_positions(research.parse_positions_csv(uploaded.getvalue(), "Fidelity"))
            st.success(f"Imported {count} Fidelity positions (replaced previous Fidelity holdings).")
        except ValueError as error:
            st.error(str(error))
    for row in db.all_rows("holdings", "symbol"):
        cols = st.columns([1, 1, 1, 1, 1])
        cols[0].markdown(f"**{row['symbol']}**")
        cols[1].caption(f"{row['shares']:g} sh")
        cols[2].caption(f"avg ${row['avg_cost']:,.2f}")
        cols[3].caption(row["account"])
        if cols[4].button("Remove", key=f"unhold-{row['id']}"):
            db.delete("holdings", row["id"])
            st.rerun()

results, history, missing = ui.market_analysis()

with ratings_tab:
    if not research.tracked_symbols():
        st.info("Add symbols in the 🛠️ tab to get ratings.")
    if missing:
        st.warning(f"No price data for: {', '.join(missing)}. Check the symbols.")
    order = {"Buy": 0, "Hold": 1, "Avoid": 2}
    for result in sorted(results, key=lambda item: (order[item["rating"]], -item["score"])):
        data = result["metrics"]
        with st.container(border=True):
            top = st.columns([3, 2])
            top[0].markdown(
                f"### {result['symbol']} {ui.pill(result['rating'])}<span class='pill pill-kind'>{result['confidence']} confidence</span>",
                unsafe_allow_html=True,
            )
            top[0].markdown(f"**{result['action']}**")
            top[1].metric("Price", f"${data['price']:,.2f}", f"{data['change_1d']:+.2%} today" if data["change_1d"] is not None else None)
            stats = st.columns(4)
            stats[0].caption(f"1 month: {data['change_1m']:+.1%}" if data["change_1m"] is not None else "1 month: n/a")
            stats[1].caption(f"1 year: {data['change_1y']:+.1%}" if data["change_1y"] is not None else "1 year: n/a")
            stats[2].caption(f"From 52w high: {data['drawdown']:+.1%}")
            stats[3].caption(f"Volatility: {data['volatility']:.0%}/yr" if data["volatility"] else "Volatility: n/a")
            with st.expander("Why this rating?", expanded=result["rating"] != "Hold"):
                st.markdown("".join(ui.reason_line(reason) for reason in result["reasons"]), unsafe_allow_html=True)
                closes = history[result["symbol"]].tail(252)
                st.line_chart(
                    pd.DataFrame({"Price": closes, "50-day avg": closes.rolling(50).mean(), "200-day avg": history[result["symbol"]].rolling(200).mean().tail(252)}),
                    height=220,
                )
                st.caption(f"Data as of {data['as_of']}. Score {result['score']:+}.")
    if results:
        st.caption(signals.DISCLAIMER)

with portfolio_tab:
    prices = {symbol: float(closes.iloc[-1]) for symbol, closes in history.items()}
    frame, total = research.portfolio(prices)
    if frame.empty:
        st.info("Add holdings in the 🛠️ tab to see your portfolio.")
    else:
        cost = float((frame["Shares"] * frame["Avg cost"]).sum())
        cols = st.columns(3)
        cols[0].metric("Tracked value", f"${total:,.2f}")
        cols[1].metric("Cost basis", f"${cost:,.2f}")
        cols[2].metric("Total gain", f"${total - cost:,.2f}", f"{(total / cost - 1):+.1%}" if cost else None)
        st.dataframe(
            frame,
            hide_index=True,
            width="stretch",
            column_config={
                "Avg cost": st.column_config.NumberColumn(format="$%.2f"),
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "Value": st.column_config.NumberColumn(format="$%.2f"),
                "Gain": st.column_config.NumberColumn(format="percent"),
                "Weight": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            },
        )

with alerts_tab:
    st.caption("JARVIS checks these automatically (see Settings → Alerts) and messages your phone or email when a target is hit.")
    with st.form("add-price-alert", clear_on_submit=True):
        cols = st.columns(3)
        alert_symbol = cols[0].text_input("Symbol", key="alert-symbol", placeholder="VOO")
        direction = cols[1].selectbox("When price goes", ["below", "above"])
        target = cols[2].number_input("Target price ($)", min_value=0.0, step=1.0)
        if st.form_submit_button("Create alert", type="primary") and alert_symbol.strip() and target > 0:
            normalized = market.normalize(alert_symbol)
            db.add("price_alerts", symbol=normalized, direction=direction, price=target)
            if normalized not in research.tracked_symbols():
                db.add("watchlist", symbol=normalized, asset_type=market.guess_type(normalized), note="Added for a price alert")
            st.success(f"Alert set: {normalized} {direction} ${target:,.2f}.")
    for row in db.all_rows("price_alerts"):
        with st.container(border=True):
            status = "✅ triggered" if row["done"] else "⏳ watching"
            current = prices.get(row["symbol"]) if results else None
            st.markdown(f"**{row['symbol']}** {row['direction']} **${row['price']:,.2f}** · {status}" + (f" · now ${current:,.2f}" if current else ""))
            ui.row_actions("price_alerts", {**row, "done": row["done"]}, "palert", "Mark done")
