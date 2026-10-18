from datetime import date, datetime, timedelta

import pytest

from jarvis import db

TODAY = date(2026, 10, 17)


def test_add_and_list_school_items_sorted_by_due_date():
    db.add("school_items", course="Linear Algebra", title="Quiz 3", kind="Quiz", due_date=TODAY + timedelta(days=3))
    db.add("school_items", course="Diff Eq", title="HW 5", kind="Assignment", due_date=TODAY + timedelta(days=1))
    assert [item["title"] for item in db.school_items()] == ["HW 5", "Quiz 3"]


def test_marking_done_hides_item():
    item_id = db.add("school_items", course="English", title="Essay", kind="Assignment", due_date=TODAY)
    db.update("school_items", item_id, done=True)
    assert db.school_items() == []
    assert len(db.school_items(include_done=True)) == 1


def test_delete_removes_row():
    task_id = db.add("tasks", title="Laundry")
    db.delete("tasks", task_id)
    assert db.all_rows("tasks") == []


def test_tasks_sort_by_date_then_priority_with_undated_last():
    db.add("tasks", title="Someday", priority="High")
    db.add("tasks", title="Low today", priority="Low", due_date=TODAY)
    db.add("tasks", title="High today", priority="High", due_date=TODAY)
    assert [task["title"] for task in db.tasks()] == ["High today", "Low today", "Someday"]


def test_events_between_is_inclusive():
    db.add("events", title="Before", event_date=TODAY - timedelta(days=1))
    db.add("events", title="Start", event_date=TODAY)
    db.add("events", title="End", event_date=TODAY + timedelta(days=6))
    db.add("events", title="After", event_date=TODAY + timedelta(days=7))
    titles = [event["title"] for event in db.events_between(TODAY, TODAY + timedelta(days=6))]
    assert titles == ["Start", "End"]


def test_reminders_split_into_due_and_upcoming():
    now = datetime(2026, 10, 17, 12, 0)
    db.add("reminders", message="Past", remind_at="2026-10-17T11:59")
    db.add("reminders", message="Future", remind_at="2026-10-17T12:01")
    assert [row["message"] for row in db.due_reminders(now)] == ["Past"]
    assert [row["message"] for row in db.upcoming_reminders(now)] == ["Future"]


def test_study_minutes_only_count_completed_recent_sessions():
    db.add("study_sessions", course="Diff Eq", session_date=db.local_today(), minutes=30, done=True)
    db.add("study_sessions", course="Diff Eq", session_date=db.local_today(), minutes=45, done=True)
    db.add("study_sessions", course="Diff Eq", session_date=db.local_today(), minutes=99, done=False)
    db.add("study_sessions", course="Diff Eq", session_date=db.local_today() - timedelta(days=30), minutes=60, done=True)
    assert db.study_minutes_by_course() == {"Diff Eq": 75}


def test_briefing_finds_exams_overdue_and_due_tasks():
    db.add("school_items", course="Calc", title="Midterm", kind="Test", due_date=TODAY + timedelta(days=2))
    db.add("school_items", course="CS", title="Lab", kind="Assignment", due_date=TODAY - timedelta(days=1))
    db.add("tasks", title="Pay phone bill", due_date=TODAY)
    info = db.briefing(today=TODAY, now=datetime(2026, 10, 17, 9, 0))
    assert [item["title"] for item in info["exams_this_week"]] == ["Midterm"]
    assert [item["title"] for item in info["overdue_school"]] == ["Lab"]
    assert [task["title"] for task in info["tasks_due"]] == ["Pay phone bill"]
    sentence = db.briefing_sentence(info)
    assert "Calc test" in sentence and "overdue" in sentence


def test_briefing_when_empty():
    assert "All systems clear" in db.briefing_sentence(db.briefing(today=TODAY))


def test_unknown_table_rejected():
    with pytest.raises(ValueError):
        db.add("hackers; DROP TABLE tasks", title="x")
