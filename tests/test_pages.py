from datetime import timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from jarvis import db

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["app.py", "views/dashboard.py", "views/school.py", "views/tasks.py", "views/calendar_page.py", "views/investments.py", "views/settings.py", "views/assistant_page.py"]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_loads_empty(page):
    app = AppTest.from_file(str(ROOT / page), default_timeout=30).run()
    assert not app.exception


@pytest.mark.parametrize("page", PAGES)
def test_every_page_loads_with_data(page):
    today = db.local_today()
    db.add("school_items", course="Linear Algebra", title="Quiz 3", kind="Quiz", due_date=today + timedelta(days=2), priority="High")
    db.add("study_sessions", course="Diff Eq", topic="Laplace", session_date=today, minutes=40, done=True)
    db.add("study_sessions", course="Diff Eq", topic="Series", session_date=today + timedelta(days=1), minutes=30)
    db.add("tasks", title="Update resume", due_date=today, priority="High")
    db.add("events", title="Badminton", event_date=today, start_time="18:00", end_time="19:30")
    db.add("watchlist", symbol="VOO", asset_type="ETF")
    db.add("watchlist", symbol="BTC-USD", asset_type="Crypto")
    db.add("holdings", symbol="VOO", shares=3, avg_cost=480, account="Fidelity")
    db.add("price_alerts", symbol="VOO", direction="below", price=400)
    db.add("reminders", message="Call mom", remind_at=(db.local_now() - timedelta(minutes=5)).isoformat(timespec="minutes"))
    app = AppTest.from_file(str(ROOT / page), default_timeout=30).run()
    assert not app.exception


def test_add_task_through_form():
    app = AppTest.from_file(str(ROOT / "views/tasks.py"), default_timeout=30).run()
    app.text_input[0].input("Buy groceries")
    app.button[0].click().run()
    assert not app.exception
    assert [task["title"] for task in db.tasks()] == ["Buy groceries"]


def test_add_school_item_through_form():
    app = AppTest.from_file(str(ROOT / "views/school.py"), default_timeout=30).run()
    app.text_input[0].input("Discrete Math")
    app.text_input[1].input("Proofs worksheet")
    next(button for button in app.button if button.label == "Save").click().run()
    assert not app.exception
    assert db.school_items()[0]["course"] == "Discrete Math"


def test_dashboard_greets_with_briefing():
    db.add("tasks", title="Pay bill", due_date=db.local_today())
    app = AppTest.from_file(str(ROOT / "views/dashboard.py"), default_timeout=30).run()
    assert any("task(s) due" in block.value for block in app.markdown)


def test_chat_answers_typed_question():
    db.add("tasks", title="Pay rent", due_date=db.local_today())
    app = AppTest.from_file(str(ROOT / "views/assistant_page.py"), default_timeout=30).run()
    app.chat_input[0].set_value("what are my tasks").run()
    assert not app.exception
    assert any("Pay rent" in block.value for block in app.markdown)


def test_starter_watchlist_button_and_ratings():
    app = AppTest.from_file(str(ROOT / "views/investments.py"), default_timeout=60).run()
    next(button for button in app.button if button.label.startswith("Add a starter watchlist")).click().run()
    assert not app.exception
    assert "VOO" in db.watchlist_symbols()
    assert any("VOO" in block.value for block in app.markdown)


def test_settings_profile_save():
    app = AppTest.from_file(str(ROOT / "views/settings.py"), default_timeout=30).run()
    app.text_input[0].set_value("Tony")
    next(button for button in app.button if button.label == "Save profile").click().run()
    assert not app.exception
    assert db.get_setting("name") == "Tony"
