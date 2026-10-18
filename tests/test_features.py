import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from jarvis import alerts, assistant, canvas, db, market, monitor, research, signals, voice

MODERATE = {"risk": "Moderate", "horizon_years": "10"}


def series(start, daily_drift, days=300, noise=0.0, seed=1):
    rng = np.random.default_rng(seed)
    steps = daily_drift + rng.normal(0, noise, days)
    return pd.Series(start * np.exp(np.cumsum(steps)), index=pd.bdate_range(end="2026-10-16", periods=days))


def fake_fetch(prices):
    return lambda symbols: {symbol: prices[symbol] for symbol in symbols if symbol in prices}


def test_v1_database_gets_new_columns(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE school_items (id INTEGER PRIMARY KEY AUTOINCREMENT, course TEXT NOT NULL, title TEXT NOT NULL, kind TEXT NOT NULL, due_date TEXT NOT NULL, priority TEXT DEFAULT 'Medium', notes TEXT DEFAULT '', done INTEGER DEFAULT 0)")
        conn.execute("INSERT INTO school_items (course, title, kind, due_date) VALUES ('Calc', 'HW', 'Assignment', '2026-10-20')")
    monkeypatch.setenv("JARVIS_DB", str(path))
    db.init_db()
    row = db.school_items()[0]
    assert row["title"] == "HW" and "canvas_id" in row


def test_postgres_urls_are_normalized(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/postgres")
    assert db.database_url() == "postgresql+psycopg://user:pw@host:5432/postgres"


def test_settings_default_and_override():
    assert db.get_setting("risk") == "Moderate"
    db.set_setting("risk", "Aggressive")
    db.set_setting("risk", "Conservative")
    assert db.profile()["risk"] == "Conservative"


class FakeResponse:
    def __init__(self, payload, status=200, next_url=None):
        self.payload, self.status_code = payload, status
        self.ok = status < 400
        self.text = str(payload)
        self.links = {"next": {"url": next_url}} if next_url else {}

    def json(self):
        return self.payload


class FakeCanvas:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(url)
        return self.routes[url]


def canvas_routes(state="unsubmitted"):
    base = "https://school.instructure.com/api/v1"
    return {
        f"{base}/courses": FakeResponse([{"id": 1, "course_code": "MATH 61"}, {"id": 2, "name": "English 1A"}]),
        f"{base}/courses/1/assignments": FakeResponse(
            [
                {"id": 10, "name": "Quiz 4", "due_at": "2026-10-21T06:59:00Z", "submission_types": ["online_quiz"], "html_url": "https://x/10"},
                {"id": 11, "name": "Midterm Exam", "due_at": "2026-10-23T17:00:00Z", "submission_types": ["on_paper"]},
            ],
            next_url=f"{base}/courses/1/assignments?page=2",
        ),
        f"{base}/courses/1/assignments?page=2": FakeResponse([{"id": 12, "name": "No due date", "due_at": None}]),
        f"{base}/courses/2/assignments": FakeResponse([{"id": 20, "name": "Essay draft", "due_at": "2026-10-25T06:59:00Z", "submission": {"workflow_state": state}}]),
    }


def test_canvas_sync_classifies_paginates_and_upserts():
    session = FakeCanvas(canvas_routes())
    summary = canvas.sync(session=session, base_url="https://school.instructure.com", token="t")
    assert summary == {"added": 3, "updated": 0, "skipped": 1, "courses": 2}
    items = {item["title"]: item for item in db.school_items()}
    assert items["Quiz 4"]["kind"] == "Quiz" and items["Quiz 4"]["due_date"] == "2026-10-20"
    assert items["Midterm Exam"]["kind"] == "Test" and items["Midterm Exam"]["priority"] == "High"
    assert items["Essay draft"]["course"] == "English 1A"
    again = canvas.sync(session=FakeCanvas(canvas_routes("submitted")), base_url="https://school.instructure.com", token="t")
    assert again["updated"] == 3 and len(db.school_items(include_done=True)) == 3
    assert "Essay draft" not in {item["title"] for item in db.school_items()}


def test_canvas_bad_token():
    session = FakeCanvas({"https://s/api/v1/courses": FakeResponse({}, status=401)})
    with pytest.raises(canvas.CanvasError, match="token"):
        canvas.sync(session=session, base_url="https://s", token="bad")


def test_index_fund_in_steady_uptrend_is_buy():
    result = signals.analyze("VOO", series(400, 0.001, noise=0.004), MODERATE, "ETF")
    assert result["rating"] == "Buy"
    assert any("index fund" in reason["text"] for reason in result["reasons"])


def test_falling_volatile_stock_is_avoid():
    result = signals.analyze("ZZZ", series(100, -0.003, noise=0.04), MODERATE, "Stock")
    assert result["rating"] == "Avoid"
    assert any("downtrend" in reason["text"].lower() for reason in result["reasons"])


def test_crypto_too_volatile_for_conservative_investor():
    closes = series(50000, 0.004, noise=0.03)
    conservative = signals.analyze("BTC-USD", closes, {"risk": "Conservative", "horizon_years": "10"}, "Crypto")
    aggressive = signals.analyze("BTC-USD", closes, {"risk": "Aggressive", "horizon_years": "10"}, "Crypto")
    assert any("Too volatile" in reason["text"] for reason in conservative["reasons"])
    assert aggressive["score"] > conservative["score"]


def test_index_fund_never_rated_avoid():
    result = signals.analyze("VOO", series(400, -0.002, noise=0.02), MODERATE, "ETF")
    assert result["rating"] in ("Hold", "Buy")


def test_concentration_warning():
    closes = series(100, 0.0002, noise=0.01)
    result = signals.analyze("ABC", closes, MODERATE, "Stock", holding={"shares": 100, "avg_cost": 80}, portfolio_value=float(closes.iloc[-1]) * 120)
    assert any("Concentration" in reason["text"] for reason in result["reasons"])


def test_normalize_symbols():
    assert market.normalize("btc") == "BTC-USD"
    assert market.normalize("sol", "Crypto") == "SOL-USD"
    assert market.normalize("gold") == "GC=F"
    assert market.normalize(" voo ") == "VOO"


FIDELITY_CSV = """Account Number,Account Name,Symbol,Description,Quantity,Last Price,Current Value,Average Cost Basis,Type
Z123,Individual,SPAXX**,HELD IN MONEY MARKET,,,$1200.00,,Cash
Z123,Individual,VOO,VANGUARD S&P 500 ETF,4.5,$552.10,"$2,484.45",$480.25,Cash
Z123,Individual,AAPL,APPLE INC,10,$230.00,"$2,300.00","$1,150.00",Margin
Z123,Individual,Pending Activity,,,,$50.00,,

"The data and information in this spreadsheet is provided to you solely for your use."
"""


def test_fidelity_csv_import_replaces_account():
    db.add("holdings", symbol="OLD", shares=1, avg_cost=1, account="Fidelity")
    db.add("holdings", symbol="ETH-USD", shares=0.5, avg_cost=2000, account="Robinhood")
    positions = research.parse_positions_csv(FIDELITY_CSV.encode(), "Fidelity")
    assert [(p["symbol"], p["shares"], p["avg_cost"]) for p in positions] == [("VOO", 4.5, 480.25), ("AAPL", 10.0, 1150.0)]
    research.import_positions(positions)
    assert sorted(row["symbol"] for row in db.all_rows("holdings")) == ["AAPL", "ETH-USD", "VOO"]


def test_portfolio_combines_accounts():
    db.add("holdings", symbol="VOO", shares=2, avg_cost=400, account="Fidelity")
    db.add("holdings", symbol="VOO", shares=2, avg_cost=500, account="Robinhood")
    frame, total = research.portfolio({"VOO": 550})
    row = frame.iloc[0]
    assert row["Shares"] == 4 and row["Avg cost"] == 450 and total == 2200
    assert row["Accounts"] == "Fidelity, Robinhood"


def test_run_analysis_reports_missing_symbols():
    db.add("watchlist", symbol="VOO", asset_type="ETF")
    db.add("watchlist", symbol="NOPE", asset_type="Stock")
    results, _, missing = research.run_analysis(fetch=fake_fetch({"VOO": series(400, 0.0005)}))
    assert [result["symbol"] for result in results] == ["VOO"] and missing == ["NOPE"]


def test_monitor_alerts_once_and_marks_price_alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "notify", lambda title, body, urgent=False: (sent.append(body), (["phone"], []))[1])
    closes = series(400, 0.0005, noise=0.003)
    closes.iloc[-1] = closes.iloc[-2] * 1.08
    db.add("watchlist", symbol="VOO", asset_type="ETF")
    db.add("price_alerts", symbol="VOO", direction="above", price=1)
    db.add("school_items", course="Calc", title="Quiz 5", kind="Quiz", due_date=db.local_today() + timedelta(days=2))
    db.add("school_items", course="CS", title="Lab 3", kind="Assignment", due_date=db.local_today() + timedelta(days=1))
    messages, log = monitor.run(fetch=fake_fetch({"VOO": closes}), sync_canvas=False)
    text = "\n".join(messages)
    assert "above your $1.00 target" in text and "up 8.0% today" in text
    assert "Quiz in 2 days" in text and "Due tomorrow: CS" in text
    assert db.all_rows("price_alerts")[0]["done"] == 1
    again, _ = monitor.run(fetch=fake_fetch({"VOO": closes}), sync_canvas=False)
    assert again == [] and len(sent) == 1


def test_monitor_rating_change_alert(monkeypatch):
    monkeypatch.setattr(alerts, "notify", lambda *args, **kwargs: (["email"], []))
    db.add("watchlist", symbol="ZZZ", asset_type="Stock")
    db.set_setting("rating:ZZZ", "Buy")
    messages, _ = monitor.run(fetch=fake_fetch({"ZZZ": series(100, -0.003, noise=0.04)}), sync_canvas=False)
    assert any("rating changed Buy → Avoid" in message for message in messages)
    assert db.get_setting("rating:ZZZ") == "Avoid"


def test_monitor_keeps_alerts_when_no_channel(monkeypatch):
    db.add("school_items", course="CS", title="Lab", kind="Assignment", due_date=db.local_today() + timedelta(days=1))
    messages, log = monitor.run(sync_canvas=False)
    assert messages and "nothing" in log[-1]
    assert not db.already_alerted(f"due:1:{(db.local_today() + timedelta(days=1)).isoformat()}")


def test_email_and_push_formatting(monkeypatch):
    for key, value in {"SMTP_USER": "me@gmail.com", "SMTP_PASSWORD": "app-pw", "ALERT_EMAIL_TO": "me@gmail.com", "NTFY_TOPIC": "jarvis-abc"}.items():
        monkeypatch.setenv(key, value)
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port):
            captured["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, user, password):
            captured["login"] = user

        def send_message(self, message):
            captured["subject"] = message["Subject"]

    alerts.send_email("JARVIS test", "body", smtp_factory=FakeSMTP)
    alerts.send_push("JARVIS 📈 test", "body", post=lambda url, **kwargs: captured.update(url=url, headers=kwargs["headers"]) or SimpleNamespace(raise_for_status=lambda: None))
    assert captured["server"] == ("smtp.gmail.com", 465) and captured["subject"] == "JARVIS test"
    assert captured["url"] == "https://ntfy.sh/jarvis-abc" and captured["headers"]["Title"] == "JARVIS  test"
    assert alerts.channels() == ["email", "phone"]


@pytest.fixture
def tools():
    return assistant.Toolkit(fetch=fake_fetch({"VOO": series(400, 0.001, noise=0.004), "BTC-USD": series(50000, 0.004, noise=0.03)}))


def test_parse_day_and_time():
    today = db.local_today()
    assert assistant.parse_day("tomorrow", today) == today + timedelta(days=1)
    assert assistant.parse_day("on friday", today).weekday() == 4
    assert assistant.parse_day("2026-11-03", today).isoformat() == "2026-11-03"
    assert assistant.parse_time("at 7pm") == "19:00" and assistant.parse_time("at 9:30 am") == "09:30" and assistant.parse_time("at 14:15") == "14:15"


def test_rule_based_add_task(tools):
    reply = assistant.rule_based_reply("add task call the bank tomorrow", tools)
    task = db.tasks()[0]
    assert task["title"] == "call the bank" and task["due_date"] == (db.local_today() + timedelta(days=1)).isoformat()
    assert "call the bank" in reply


def test_rule_based_add_quiz(tools):
    assistant.rule_based_reply("add quiz for Linear Algebra: chapter 5 eigenvalues on friday", tools)
    item = db.school_items()[0]
    assert (item["course"], item["title"], item["kind"], item["priority"]) == ("Linear Algebra", "chapter 5 eigenvalues", "Quiz", "High")
    assert assistant.parse_day("friday") == datetime.fromisoformat(item["due_date"]).date()


def test_rule_based_reminder_relative(tools):
    assistant.rule_based_reply("remind me to stretch in 30 minutes", tools)
    reminder = db.all_rows("reminders")[0]
    assert reminder["message"] == "stretch"
    assert reminder["remind_at"] > db.local_now().isoformat(timespec="minutes")


def test_rule_based_event(tools):
    assistant.rule_based_reply("add event dentist on 12/24 at 3pm", tools)
    event = db.all_rows("events")[0]
    assert event["title"] == "dentist" and event["event_date"].endswith("-12-24") and event["start_time"] == "15:00"


def test_rule_based_asset_question(tools):
    reply = assistant.rule_based_reply("should I buy VOO?", tools)
    assert reply.startswith("VOO: Buy") and "Why:" in reply and "not financial advice" in reply
    assert "BTC-USD" in assistant.rule_based_reply("how is btc", tools)


def test_rule_based_lists(tools):
    db.add("school_items", course="Calc", title="Midterm", kind="Test", due_date=db.local_today() + timedelta(days=3))
    assert "Midterm" in assistant.rule_based_reply("any tests coming up?", tools)
    assert "Midterm" in assistant.rule_based_reply("what's due this week", tools)
    assert "All systems clear" in assistant.rule_based_reply("hey jarvis", tools) or "You have" in assistant.rule_based_reply("hey jarvis", tools)
    assert "didn't quite catch" in assistant.rule_based_reply("sing me a song", tools)


class FakeClaude:
    def __init__(self):
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(stop_reason="tool_use", content=[SimpleNamespace(type="tool_use", id="t1", name="add_task", input={"title": "Buy milk", "due_date": "2026-10-18"})])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Done, sir. Milk is on the list.")])


def test_llm_tool_loop(tools):
    client = FakeClaude()
    answer = assistant.reply("I need to buy milk tomorrow", tools=tools, client=client)
    assert answer == "Done, sir. Milk is on the list."
    assert db.tasks()[0]["title"] == "Buy milk"
    tool_result = client.calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "Buy milk" in tool_result["content"]
    assert {spec["name"] for spec in client.calls[0]["tools"]} >= {"add_task", "analyze_asset", "add_reminder"}


def test_llm_failure_falls_back(tools):
    class Broken:
        messages = SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no key")))

    answer = assistant.reply("what are my tasks", tools=tools, client=Broken())
    assert "basic mode" in answer


def test_speakable_strips_markup():
    text = voice.speakable("VOO: Buy\nWhy:\n- **Uptrend**\n(JARVIS ratings are educational research signals... decision.)")
    assert text == "VOO: Buy. Why:. Uptrend."
    assert "speechSynthesis" in voice.speech_html("hi")


def test_tts_prefers_neural_voice_then_falls_back(monkeypatch):
    monkeypatch.delenv("JARVIS_NO_TTS")
    calls = []
    monkeypatch.setattr(voice, "neural_mp3", lambda text, voice_name: calls.append(("neural", voice_name)) or b"neural")
    monkeypatch.setattr(voice, "google_mp3", lambda text: calls.append(("google", None)) or b"google")
    assert voice.tts_mp3("Hello", "en-GB-ThomasNeural") == b"neural" and calls == [("neural", "en-GB-ThomasNeural")]
    monkeypatch.setattr(voice, "neural_mp3", lambda *args: (_ for _ in ()).throw(OSError("offline")))
    assert voice.tts_mp3("Hello") == b"google"
    monkeypatch.setattr(voice, "google_mp3", lambda text: (_ for _ in ()).throw(OSError("offline")))
    assert voice.tts_mp3("Hello") is None


def test_default_voice_setting():
    assert db.get_setting("voice") == "en-GB-RyanNeural"
    assert "en-GB-RyanNeural" in voice.VOICES.values()


def test_filler_words_are_not_tickers(tools):
    assert assistant.symbol_from("the market rn") is None
    assert assistant.symbol_from("at the moment") is None
    assert assistant.symbol_from("nvda right now") == "nvda"
    assert "BTC-USD" in assistant.rule_based_reply("how is btc today", tools)
    reply = assistant.rule_based_reply("how is the market rn", tools)
    assert "couldn't get price data" not in reply


def test_which_stock_should_i_buy(tools):
    db.add("watchlist", symbol="VOO", asset_type="ETF")
    db.add("watchlist", symbol="BTC-USD", asset_type="Crypto")
    for question in ["which stock should i buy ?", "what should I invest in", "any good crypto to buy", "recommend me a stock"]:
        reply = assistant.rule_based_reply(question, tools)
        assert "strongest" in reply and "VOO" in reply, question
    assert "what's due" not in assistant.rule_based_reply("what's due this week", tools)


def test_top_picks_empty_watchlist(tools):
    assert "watchlist is empty" in assistant.rule_based_reply("which stock should i buy", tools)
