import argparse
import os
from datetime import timedelta

from jarvis import alerts, canvas, db, research, signals


def price_alerts(results):
    prices = {result["symbol"]: result["metrics"]["price"] for result in results}
    found = []
    for row in db.all_rows("price_alerts"):
        price = prices.get(row["symbol"])
        if row["done"] or price is None:
            continue
        hit = price >= row["price"] if row["direction"] == "above" else price <= row["price"]
        if hit:
            found.append((f"price:{row['id']}", f"🎯 {row['symbol']} is ${price:,.2f}, {row['direction']} your ${row['price']:,.2f} target.", row["id"]))
    return found


def market_alerts(results):
    threshold = float(db.get_setting("move_alert_pct") or 5) / 100
    found = []
    for result in results:
        data = result["metrics"]
        if data["change_1d"] is not None and abs(data["change_1d"]) >= threshold:
            direction = "up" if data["change_1d"] > 0 else "down"
            found.append((f"move:{result['symbol']}:{data['as_of']}", f"📈 {result['symbol']} is {direction} {abs(data['change_1d']):.1%} today (${data['price']:,.2f}). Rating: {result['rating']}."))
        previous = db.get_setting(f"rating:{result['symbol']}")
        if previous and previous != result["rating"]:
            top = next((reason["text"] for reason in result["reasons"] if reason["points"]), "")
            found.append((f"rating:{result['symbol']}:{data['as_of']}:{result['rating']}", f"🔄 {result['symbol']} rating changed {previous} → {result['rating']}. {top}"))
    return found


def school_alerts(today=None):
    today = today or db.local_today()
    tomorrow = (today + timedelta(days=1)).isoformat()
    soon = (today + timedelta(days=3)).isoformat()
    found = []
    for item in db.school_items():
        if item["due_date"] == tomorrow:
            found.append((f"due:{item['id']}:{item['due_date']}", f"⏰ Due tomorrow: {item['course']} — {item['title']} ({item['kind']})"))
        elif item["kind"] in ("Test", "Quiz") and today.isoformat() < item["due_date"] <= soon:
            found.append((f"exam:{item['id']}:{item['due_date']}", f"📝 {item['kind']} in {db.days_until(item['due_date'], today)} days: {item['course']} — {item['title']}. Time to plan a study session."))
    for reminder in db.due_reminders():
        found.append((f"reminder:{reminder['id']}", f"🔔 Reminder: {reminder['message']}"))
    return found


def digest(results):
    lines = [db.briefing_sentence(db.briefing()), ""]
    if results:
        lines.append("Market check:")
        lines.extend(f"• {signals.summary_line(result)}" for result in results)
        lines.extend(["", signals.DISCLAIMER])
    return "\n".join(lines)


def run(send_digest=False, dry_run=False, fetch=None, sync_canvas=True):
    db.init_db()
    log = []
    if sync_canvas and canvas.is_configured():
        try:
            log.append(f"Canvas sync: {canvas.sync()}")
        except Exception as error:
            log.append(f"Canvas sync failed: {error}")
    results, _, missing = research.run_analysis(fetch=fetch) if research.tracked_symbols() else ([], {}, [])
    if missing:
        log.append(f"No price data for: {', '.join(missing)}")
    triggered = price_alerts(results)
    candidates = [(key, text) for key, text, _ in triggered] + market_alerts(results) + school_alerts()
    fresh = [(key, text) for key, text in candidates if not db.already_alerted(key)]
    messages = [text for _, text in fresh]
    if send_digest:
        messages.append(digest(results))
    if messages and not dry_run:
        sent, errors = alerts.notify("JARVIS update" if not send_digest else "JARVIS daily briefing", "\n\n".join(messages), urgent=bool(triggered))
        log.append(f"Sent via {', '.join(sent) or 'nothing (no alert channels configured)'}")
        log.extend(errors)
        if sent:
            for key, _ in fresh:
                db.mark_alerted(key)
            for _, _, alert_id in triggered:
                db.update("price_alerts", alert_id, done=1)
    if not dry_run:
        for result in results:
            db.set_setting(f"rating:{result['symbol']}", result["rating"])
    return messages, log


def main():
    parser = argparse.ArgumentParser(description="JARVIS market + school monitor")
    parser.add_argument("--digest", action="store_true", help="also send the full daily briefing")
    parser.add_argument("--dry-run", action="store_true", help="print alerts without sending or saving")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") and not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL secret is missing, so the monitor can't see your data. Add it in GitHub → Settings → Secrets → Actions.")
        return
    messages, log = run(send_digest=args.digest, dry_run=args.dry_run)
    print("\n\n".join(messages) or "No new alerts.")
    print("\n".join(log))


if __name__ == "__main__":
    main()
