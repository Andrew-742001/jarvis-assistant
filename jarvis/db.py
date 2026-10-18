import os
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine, inspect, text

from jarvis.config import setting

metadata = MetaData()

TABLES = {
    table.name: table
    for table in [
        Table(
            "school_items",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("course", String(200), nullable=False),
            Column("title", String(500), nullable=False),
            Column("kind", String(50), nullable=False),
            Column("due_date", String(10), nullable=False),
            Column("priority", String(20), default="Medium"),
            Column("notes", Text, default=""),
            Column("done", Integer, default=0),
            Column("source", String(20), default="manual"),
            Column("canvas_id", String(100), unique=True),
            Column("url", Text, default=""),
        ),
        Table(
            "study_sessions",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("course", String(200), nullable=False),
            Column("topic", String(500), default=""),
            Column("session_date", String(10), nullable=False),
            Column("minutes", Integer, nullable=False),
            Column("done", Integer, default=0),
        ),
        Table(
            "tasks",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("title", String(500), nullable=False),
            Column("category", String(50), default="Personal"),
            Column("due_date", String(10)),
            Column("priority", String(20), default="Medium"),
            Column("done", Integer, default=0),
        ),
        Table(
            "events",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("title", String(500), nullable=False),
            Column("event_date", String(10), nullable=False),
            Column("start_time", String(5), default=""),
            Column("end_time", String(5), default=""),
            Column("location", String(300), default=""),
            Column("notes", Text, default=""),
        ),
        Table(
            "reminders",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("message", String(500), nullable=False),
            Column("remind_at", String(16), nullable=False),
            Column("done", Integer, default=0),
        ),
        Table(
            "watchlist",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False, unique=True),
            Column("asset_type", String(20), default="Stock"),
            Column("note", String(300), default=""),
        ),
        Table(
            "holdings",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False),
            Column("shares", Float, nullable=False),
            Column("avg_cost", Float, default=0.0),
            Column("account", String(50), default="Fidelity"),
        ),
        Table(
            "price_alerts",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False),
            Column("direction", String(10), nullable=False),
            Column("price", Float, nullable=False),
            Column("done", Integer, default=0),
        ),
        Table(
            "settings",
            metadata,
            Column("key", String(100), primary_key=True),
            Column("value", Text, default=""),
        ),
        Table(
            "alert_log",
            metadata,
            Column("key", String(300), primary_key=True),
            Column("sent_at", String(19), nullable=False),
        ),
    ]
}

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}

DEFAULT_SETTINGS = {
    "name": "Andrew",
    "risk": "Moderate",
    "horizon_years": "10",
    "goal": "Long-term growth",
    "move_alert_pct": "5",
    "voice": "en-GB-RyanNeural",
}


def local_now():
    return datetime.now(ZoneInfo(setting("JARVIS_TZ", "America/Los_Angeles"))).replace(tzinfo=None)


def local_today():
    return local_now().date()


def db_path():
    return Path(os.environ.get("JARVIS_DB", Path(__file__).resolve().parent.parent / "data" / "jarvis.db"))


def database_url():
    url = setting("DATABASE_URL", "")
    if url:
        return url.replace("postgres://", "postgresql+psycopg://", 1).replace("postgresql://", "postgresql+psycopg://", 1)
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


@lru_cache(maxsize=8)
def _engine(url):
    return create_engine(url, pool_pre_ping=True)


def engine():
    return _engine(database_url())


def init_db():
    eng = engine()
    metadata.create_all(eng)
    existing = inspect(eng)
    with eng.begin() as conn:
        for table in TABLES.values():
            present = {column["name"] for column in existing.get_columns(table.name)}
            for column in table.columns:
                if column.name not in present:
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(eng.dialect)}"))


def _table(name):
    if name not in TABLES:
        raise ValueError(f"Unknown table: {name}")
    return TABLES[name]


def _clean(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def _order(table, order_by):
    clauses = []
    for part in [piece.strip() for piece in order_by.split(",") if piece.strip()]:
        name, _, direction = part.partition(" ")
        column = table.c[name]
        clauses.append(column.desc() if direction.strip().upper() == "DESC" else column.asc())
    return clauses


def add(table_name, **fields):
    table = _table(table_name)
    with engine().begin() as conn:
        result = conn.execute(table.insert().values({key: _clean(value) for key, value in fields.items()}))
        return result.inserted_primary_key[0]


def update(table_name, row_id, **fields):
    table = _table(table_name)
    with engine().begin() as conn:
        conn.execute(table.update().where(table.c.id == row_id).values({key: _clean(value) for key, value in fields.items()}))


def delete(table_name, row_id):
    table = _table(table_name)
    with engine().begin() as conn:
        conn.execute(table.delete().where(table.c.id == row_id))


def all_rows(table_name, order_by="id"):
    table = _table(table_name)
    order_by = order_by if "id" in table.c or order_by != "id" else "key"
    with engine().connect() as conn:
        return [dict(row._mapping) for row in conn.execute(table.select().order_by(*_order(table, order_by)))]


def find(table_name, **criteria):
    table = _table(table_name)
    query = table.select()
    for key, value in criteria.items():
        query = query.where(table.c[key] == _clean(value))
    with engine().connect() as conn:
        return [dict(row._mapping) for row in conn.execute(query)]


def upsert_canvas_item(canvas_id, **fields):
    match = find("school_items", canvas_id=canvas_id)
    if match:
        update("school_items", match[0]["id"], **fields)
        return "updated"
    add("school_items", canvas_id=canvas_id, source="canvas", **fields)
    return "added"


def get_setting(key):
    match = find("settings", key=key)
    return match[0]["value"] if match else DEFAULT_SETTINGS.get(key, "")


def set_setting(key, value):
    table = _table("settings")
    with engine().begin() as conn:
        if conn.execute(table.select().where(table.c.key == key)).first():
            conn.execute(table.update().where(table.c.key == key).values(value=str(value)))
        else:
            conn.execute(table.insert().values(key=key, value=str(value)))


def profile():
    return {key: get_setting(key) for key in DEFAULT_SETTINGS}


def already_alerted(key):
    return bool(find("alert_log", key=key))


def mark_alerted(key):
    table = _table("alert_log")
    with engine().begin() as conn:
        if not conn.execute(table.select().where(table.c.key == key)).first():
            conn.execute(table.insert().values(key=key, sent_at=local_now().isoformat(timespec="seconds")))


def school_items(include_done=False):
    rows = all_rows("school_items", "due_date")
    return rows if include_done else [row for row in rows if not row["done"]]


def tasks(include_done=False):
    rows = sorted(
        all_rows("tasks"),
        key=lambda row: (row["due_date"] or "9999-12-31", PRIORITY_ORDER.get(row["priority"], 1)),
    )
    return rows if include_done else [row for row in rows if not row["done"]]


def events_between(start, end):
    return [row for row in all_rows("events", "event_date, start_time") if start.isoformat() <= row["event_date"] <= end.isoformat()]


def due_reminders(now=None):
    now = (now or local_now()).isoformat(timespec="minutes")
    return [row for row in all_rows("reminders", "remind_at") if not row["done"] and row["remind_at"] <= now]


def upcoming_reminders(now=None):
    now = (now or local_now()).isoformat(timespec="minutes")
    return [row for row in all_rows("reminders", "remind_at") if not row["done"] and row["remind_at"] > now]


def watchlist_symbols():
    return [row["symbol"] for row in all_rows("watchlist", "symbol")]


def days_until(iso_day, today=None):
    return (date.fromisoformat(iso_day) - (today or local_today())).days


def study_minutes_by_course(since=None):
    since = (since or local_today() - timedelta(days=7)).isoformat()
    totals = {}
    for row in all_rows("study_sessions"):
        if row["done"] and row["session_date"] >= since:
            totals[row["course"]] = totals.get(row["course"], 0) + row["minutes"]
    return totals


def briefing(today=None, now=None):
    today = today or local_today()
    week_ahead = today + timedelta(days=7)
    school = school_items()
    overdue_school = [item for item in school if item["due_date"] < today.isoformat()]
    this_week = [item for item in school if today.isoformat() <= item["due_date"] <= week_ahead.isoformat()]
    exams = [item for item in this_week if item["kind"] in ("Test", "Quiz")]
    open_tasks = tasks()
    tasks_today = [task for task in open_tasks if task["due_date"] and task["due_date"] <= today.isoformat()]
    return {
        "overdue_school": overdue_school,
        "school_this_week": this_week,
        "exams_this_week": exams,
        "tasks_due": tasks_today,
        "events_today": events_between(today, today),
        "reminders_due": due_reminders(now),
    }


def briefing_sentence(info, name=None):
    name = name or get_setting("name")
    hour = local_now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    parts = []
    if info["events_today"]:
        parts.append(f"{len(info['events_today'])} event(s) on your calendar today")
    if info["tasks_due"]:
        parts.append(f"{len(info['tasks_due'])} task(s) due")
    if info["exams_this_week"]:
        first = info["exams_this_week"][0]
        parts.append(f"{len(info['exams_this_week'])} test/quiz this week, starting with {first['course']} {first['kind'].lower()} on {first['due_date']}")
    if info["overdue_school"]:
        parts.append(f"{len(info['overdue_school'])} overdue school item(s) that need attention")
    if info["reminders_due"]:
        parts.append(f"{len(info['reminders_due'])} reminder(s) waiting")
    if not parts:
        return f"{greeting}, {name}. All systems clear — nothing urgent today."
    return f"{greeting}, {name}. You have " + "; ".join(parts) + "."
