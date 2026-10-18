import json
import random
import re
from datetime import date, datetime, timedelta

from jarvis import db, market, research, signals
from jarvis.config import setting

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
KINDS = {"test": "Test", "exam": "Test", "midterm": "Test", "final": "Test", "quiz": "Quiz", "assignment": "Assignment", "homework": "Assignment", "hw": "Assignment", "project": "Project", "essay": "Assignment", "reading": "Reading"}


ACKNOWLEDGEMENTS = ["Right away.", "Consider it done.", "Done.", "Of course.", "As you wish."]


def acknowledge(text):
    return f"{random.choice(ACKNOWLEDGEMENTS)} {text}"


class Toolkit:
    def __init__(self, fetch=None):
        self.fetch = fetch or market.fetch_history

    def get_briefing(self):
        return db.briefing_sentence(db.briefing())

    def list_school_work(self, days=7, kind=None):
        today = db.local_today()
        end = (today + timedelta(days=int(days))).isoformat()
        items = [item for item in db.school_items() if item["due_date"] <= end and (not kind or item["kind"] == kind)]
        if not items:
            return f"No {'' if not kind else kind.lower() + ' '}school work due in the next {days} days."
        return "\n".join(f"- {item['course']}: {item['title']} ({item['kind']}) due {item['due_date']}, {self._when(item['due_date'])}" for item in items)

    def list_tasks(self):
        open_tasks = db.tasks()
        if not open_tasks:
            return "Your task list is empty."
        return "\n".join(f"- {task['title']} [{task['priority']}]" + (f" due {task['due_date']}" if task["due_date"] else "") for task in open_tasks)

    def get_calendar(self, days=7):
        today = db.local_today()
        events = db.events_between(today, today + timedelta(days=int(days) - 1))
        if not events:
            return f"Nothing on your calendar for the next {days} days."
        return "\n".join(f"- {event['event_date']} {event['start_time'] or 'all day'}: {event['title']}" + (f" at {event['location']}" if event["location"] else "") for event in events)

    def add_task(self, title, due_date=None, priority="Medium", category="Personal"):
        db.add("tasks", title=title, due_date=due_date, priority=priority, category=category)
        return acknowledge(f"Added task '{title}'") + (f" due {due_date}." if due_date else ".")

    def add_school_item(self, course, title, kind="Assignment", due_date=None, priority="Medium"):
        due_date = due_date or db.local_today().isoformat()
        db.add("school_items", course=course, title=title, kind=kind, due_date=due_date, priority=priority)
        return acknowledge(f"Added {kind.lower()} for {course}: '{title}' due {due_date}.")

    def add_event(self, title, event_date, start_time="", end_time="", location=""):
        db.add("events", title=title, event_date=event_date, start_time=start_time or "", end_time=end_time or "", location=location or "")
        return acknowledge(f"Added '{title}' on {event_date}" + (f" at {start_time}." if start_time else "."))

    def add_reminder(self, message, remind_at):
        db.add("reminders", message=message, remind_at=remind_at[:16])
        return acknowledge(f"I'll remind you to {message} at {remind_at[:16].replace('T', ' ')}.")

    def analyze_asset(self, symbol):
        symbol = market.normalize(symbol)
        results, _, missing = research.run_analysis(fetch=self.fetch, symbols=[symbol])
        if not results:
            return f"I couldn't get price data for {symbol}. Check the ticker symbol."
        result = results[0]
        reasons = "\n".join(f"- {reason['text']}" for reason in result["reasons"])
        return f"{signals.summary_line(result)}\n\n{result['action']}\n\n**Why:**\n{reasons}\n\n_({signals.DISCLAIMER})_"

    def portfolio_overview(self):
        symbols = research.tracked_symbols()
        if not symbols:
            return "Your watchlist is empty. Add symbols on the Investments page."
        results, _, _ = research.run_analysis(fetch=self.fetch, symbols=symbols)
        return "\n".join(signals.summary_line(result) for result in results) or "No price data available right now."

    def top_picks(self, limit=3):
        symbols = research.tracked_symbols()
        if not symbols:
            return "Your watchlist is empty. Add some symbols on the Investments page and I'll rate them for you."
        results, _, _ = research.run_analysis(fetch=self.fetch, symbols=symbols)
        if not results:
            return "I couldn't get price data right now. Try again in a few minutes."
        ranked = sorted(results, key=lambda result: -result["score"])
        buys = [result for result in ranked if result["rating"] == "Buy"][: int(limit)]
        if not buys:
            best = ranked[0]
            return (
                f"Nothing on your watchlist is rated Buy right now. The strongest is {best['symbol']} ({best['rating']}). "
                "Waiting is a perfectly good choice; add more symbols to widen the search."
                f"\n\n_({signals.DISCLAIMER})_"
            )
        lines = [
            f"- **{result['symbol']}** — {result['confidence'].lower()} confidence. {next((reason['text'] for reason in result['reasons'] if reason['points'] > 0), '')}"
            for result in buys
        ]
        avoid = [result["symbol"] for result in ranked if result["rating"] == "Avoid"]
        tail = f"\n\nCurrently rated Avoid: {', '.join(avoid)}." if avoid else ""
        return (
            f"From your watchlist, the strongest Buy signals are:\n" + "\n".join(lines) + tail
            + "\n\nIf you start, consider small amounts spread over time. Ask 'should I buy " + buys[0]["symbol"] + "?' for the full reasoning."
            + f"\n\n_({signals.DISCLAIMER})_"
        )

    @staticmethod
    def _when(iso_day):
        days = db.days_until(iso_day)
        return "overdue" if days < 0 else "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"


TOOL_SPECS = [
    {"name": "get_briefing", "description": "Short summary of today: events, tasks due, upcoming tests, overdue work, reminders.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "list_school_work", "description": "List upcoming school items (tests, quizzes, assignments).", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "description": "Look-ahead window in days"}, "kind": {"type": "string", "enum": ["Test", "Quiz", "Assignment", "Project", "Reading", "Discussion"]}}}},
    {"name": "list_tasks", "description": "List open personal tasks.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_calendar", "description": "List calendar events for the next N days.", "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}}},
    {"name": "add_task", "description": "Add a personal task.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "due_date": {"type": "string", "description": "YYYY-MM-DD"}, "priority": {"type": "string", "enum": ["High", "Medium", "Low"]}, "category": {"type": "string"}}, "required": ["title"]}},
    {"name": "add_school_item", "description": "Add a test, quiz, assignment, project or reading.", "input_schema": {"type": "object", "properties": {"course": {"type": "string"}, "title": {"type": "string"}, "kind": {"type": "string", "enum": ["Test", "Quiz", "Assignment", "Project", "Reading"]}, "due_date": {"type": "string", "description": "YYYY-MM-DD"}, "priority": {"type": "string", "enum": ["High", "Medium", "Low"]}}, "required": ["course", "title", "kind", "due_date"]}},
    {"name": "add_event", "description": "Add a calendar event.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "event_date": {"type": "string", "description": "YYYY-MM-DD"}, "start_time": {"type": "string", "description": "HH:MM 24h"}, "end_time": {"type": "string", "description": "HH:MM 24h"}, "location": {"type": "string"}}, "required": ["title", "event_date"]}},
    {"name": "add_reminder", "description": "Set a reminder.", "input_schema": {"type": "object", "properties": {"message": {"type": "string"}, "remind_at": {"type": "string", "description": "YYYY-MM-DDTHH:MM local time"}}, "required": ["message", "remind_at"]}},
    {"name": "analyze_asset", "description": "Explainable Buy/Hold/Avoid research rating for a stock, ETF, crypto (e.g. BTC) or gold, using price history and the user's risk profile.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "top_picks", "description": "The highest-rated Buy candidates on the user's watchlist, with the main reason for each. Use for 'what should I buy', 'which stock', 'best investment'.", "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "portfolio_overview", "description": "Ratings for every symbol on the user's watchlist and holdings.", "input_schema": {"type": "object", "properties": {}}},
]


def parse_day(text, today=None):
    today = today or db.local_today()
    lowered = text.lower()
    if "tomorrow" in lowered:
        return today + timedelta(days=1)
    if "today" in lowered or "tonight" in lowered:
        return today
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", lowered)
    if match:
        return date(*map(int, match.groups()))
    match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", lowered)
    if match:
        month, day = map(int, match.groups())
        guess = date(today.year, month, day)
        return guess if guess >= today else date(today.year + 1, month, day)
    match = re.search(r"\b(" + "|".join(MONTHS) + r")[a-z]*\.?\s+(\d{1,2})\b", lowered)
    if match:
        guess = date(today.year, MONTHS.index(match.group(1)) + 1, int(match.group(2)))
        return guess if guess >= today else date(today.year + 1, guess.month, guess.day)
    for index, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{name}\b", lowered):
            ahead = (index - today.weekday()) % 7 or 7
            return today + timedelta(days=ahead)
    match = re.search(r"in (\d+) days?", lowered)
    if match:
        return today + timedelta(days=int(match.group(1)))
    return None


def parse_time(text):
    match = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", text.lower())
    if match:
        hour, minute, meridiem = int(match.group(1)) % 12, int(match.group(2) or 0), match.group(3)
        return f"{hour + (12 if meridiem.startswith('p') else 0):02d}:{minute:02d}"
    match = re.search(r"\bat\s+(\d{1,2}):(\d{2})\b", text.lower())
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    return None


def strip_when(text):
    patterns = [
        r"\b(today|tonight|tomorrow)\b",
        r"\bon\s+\w+day\b",
        r"\b(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b(due|on|by)\s*$",
        r"\b(at\s+)?\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)",
        r"\bat\s+\d{1,2}:\d{2}\b",
        r"\d{4}-\d{2}-\d{2}",
        r"\b\d{1,2}/\d{1,2}\b",
        r"\bin \d+ (minutes?|hours?|days?)\b",
        r"\b(" + "|".join(MONTHS) + r")[a-z]*\.?\s+\d{1,2}\b",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+(due|on|by|for|at)\s*$", "", re.sub(r"\s{2,}", " ", text)).strip(" ,.")


FILLER = re.compile(r"\s*\b(rn|right now|now|today|at the moment|currently|lately|this week|these days|stock|stocks|etf|crypto|coin|shares?)\b\s*$", re.IGNORECASE)
NOT_SYMBOLS = {
    "it", "that", "this", "things", "everything", "you", "we", "i", "me", "my", "the", "market", "markets", "the market",
    "my portfolio", "portfolio", "my stocks", "stocks", "crypto", "my crypto", "my investments", "investments", "life",
    "school", "my day", "today", "going", "it going", "your day", "the economy", "economy", "the weather", "weather",
}


def symbol_from(phrase):
    phrase = phrase.strip().strip("?.!$ ")
    previous = None
    while previous != phrase:
        previous, phrase = phrase, FILLER.sub("", phrase).strip()
    if not phrase or phrase.lower() in NOT_SYMBOLS or " " in phrase or not re.fullmatch(r"[A-Za-z0-9.\-^=&]{1,10}", phrase):
        return None
    return phrase


ASSET_PATTERN = re.compile(
    r"(?:should i (?:buy|sell|hold)|how(?:'s| is| are)|rate|rating (?:for|on)|analy[sz]e|price of|what about|thoughts on|check)\s+\$?([A-Za-z0-9.\-^&= ]{1,15}?)(?:\s+(?:stock|etf|now|today|right now|crypto))?\s*\??$",
    re.IGNORECASE,
)


def rule_based_reply(message, tools):
    text = message.strip()
    lowered = text.lower()
    now = db.local_now()

    match = re.match(r"(?:please\s+)?remind me (?:to\s+)?(.+)", text, re.IGNORECASE)
    if match:
        body = match.group(1)
        relative = re.search(r"in (\d+) (minute|hour)s?", body, re.IGNORECASE)
        if relative:
            amount = int(relative.group(1))
            when = now + (timedelta(minutes=amount) if relative.group(2).lower() == "minute" else timedelta(hours=amount))
        else:
            day = parse_day(body) or now.date()
            clock = parse_time(body) or "09:00"
            when = datetime.combine(day, datetime.strptime(clock, "%H:%M").time())
        return tools.add_reminder(strip_when(body), when.isoformat(timespec="minutes"))

    match = re.match(r"(?:add|new|create)\s+(?:a\s+)?(test|exam|midterm|final|quiz|assignment|homework|hw|project|essay|reading)\s+(?:for|in)\s+(.+?)(?:\s*[:\-—]\s*|\s+called\s+)(.+)", text, re.IGNORECASE)
    if match:
        kind = KINDS[match.group(1).lower()]
        day = parse_day(match.group(3)) or parse_day(text) or db.local_today()
        title = strip_when(match.group(3)) or match.group(1).title()
        return tools.add_school_item(match.group(2).strip(), title, kind, day.isoformat(), "High" if kind in ("Test", "Quiz") else "Medium")

    match = re.match(r"(?:add|new|create)\s+(?:a\s+)?(test|exam|midterm|final|quiz)\s+(?:for|in)\s+(.+)", text, re.IGNORECASE)
    if match:
        kind = KINDS[match.group(1).lower()]
        day = parse_day(match.group(2)) or db.local_today()
        course = strip_when(match.group(2))
        return tools.add_school_item(course, f"{course} {kind.lower()}", kind, day.isoformat(), "High")

    match = re.match(r"(?:add|new|create)\s+(?:an?\s+)?(?:event|meeting|appointment)\s+(.+)", text, re.IGNORECASE)
    if match:
        day = parse_day(match.group(1)) or db.local_today()
        return tools.add_event(strip_when(match.group(1)), day.isoformat(), parse_time(match.group(1)) or "")

    match = re.match(r"(?:add|new|create)\s+(?:a\s+)?(?:task|todo|to-do)\s*:?\s*(.+)", text, re.IGNORECASE)
    if match:
        day = parse_day(match.group(1))
        return tools.add_task(strip_when(match.group(1)), day.isoformat() if day else None)

    match = ASSET_PATTERN.search(text)
    symbol = symbol_from(match.group(1)) if match else None
    if symbol and not re.search(r"\b(due|homework|tasks?|calendar|schedule)\b", lowered):
        return tools.analyze_asset(symbol)

    if re.search(r"\b(which|what|best|top|good|recommend\w*|suggest\w*|pick\w*|any)\b.*\b(stocks?|etfs?|crypto|coins?|buy|invest\w*|picks?)\b", lowered) and not re.search(r"\b(due|homework|task)", lowered):
        return tools.top_picks()
    if re.search(r"\b(portfolio|holdings|watchlist|investments?|market)\b", lowered):
        return tools.portfolio_overview()
    if re.search(r"\b(tests?|quiz(zes)?|exams?|midterms?)\b", lowered):
        return tools.list_school_work(14, "Test") + "\n" + tools.list_school_work(14, "Quiz")
    if re.search(r"\b(due|homework|assignments?|school|class(es)?)\b", lowered):
        return tools.list_school_work(7)
    if re.search(r"\b(tasks?|to-?dos?)\b", lowered):
        return tools.list_tasks()
    if re.search(r"\b(calendar|schedule|events?|agenda)\b", lowered):
        return tools.get_calendar(7)
    if re.search(r"\b(brief|briefing|morning|update|status|what'?s up|hello|hi|hey|jarvis)\b", lowered):
        return tools.get_briefing()
    return (
        "I didn't quite catch that. Try: 'what's due this week', 'which stock should I buy', "
        "'should I buy NVDA', 'add task call the bank tomorrow', or 'remind me to study at 7pm'."
    )


def system_prompt():
    profile = db.profile()
    return (
        f"You are JARVIS, {profile['name']}'s personal assistant, inspired by the AI from Iron Man: calm, concise, slightly witty. "
        f"Today is {db.local_now():%A %Y-%m-%d %H:%M} (Pacific time). "
        f"Investor profile: risk {profile['risk']}, horizon {profile['horizon_years']} years, goal: {profile['goal']}. "
        "Use the tools to read and change school work, tasks, calendar and reminders, and to research assets. "
        "Convert relative dates like 'Friday' into YYYY-MM-DD yourself. "
        "For investments you only suggest; you never place trades and cannot access brokerage accounts. "
        "When giving a Buy/Hold/Avoid view, use analyze_asset, explain the reasons plainly, and remind the user it is research, not financial advice. "
        "Replies are often spoken aloud, so keep them short and natural, without markdown tables."
    )


def llm_reply(message, history, tools, client=None, max_rounds=6):
    if client is None:
        import anthropic

        client = anthropic.Anthropic(api_key=setting("ANTHROPIC_API_KEY"))
    messages = [*history[-10:], {"role": "user", "content": message}]
    for _ in range(max_rounds):
        response = client.messages.create(
            model=setting("JARVIS_MODEL", "claude-haiku-5-5"),
            max_tokens=1024,
            system=system_prompt(),
            tools=TOOL_SPECS,
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text").strip()
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                output = getattr(tools, block.name)(**block.input)
            except Exception as error:
                output = f"Error: {error}"
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output) if not isinstance(output, str) else output})
        messages.append({"role": "user", "content": results})
    return "Sorry, that took too many steps. Try asking in a simpler way."


def ai_enabled():
    return bool(setting("ANTHROPIC_API_KEY"))


def reply(message, history=None, tools=None, client=None):
    tools = tools or Toolkit()
    if client is not None or ai_enabled():
        try:
            return llm_reply(message, history or [], tools, client)
        except Exception as error:
            return rule_based_reply(message, tools) + f"\n\n(AI brain unavailable, used basic mode: {error})"
    return rule_based_reply(message, tools)
