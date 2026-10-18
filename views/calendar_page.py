from datetime import date, datetime, time, timedelta

import streamlit as st

from jarvis import db, ui

ui.setup("Calendar", "📅")
ui.hero("📅 Calendar & Reminders", "Events, school deadlines, and reminders on one timeline.")

calendar_tab, reminder_tab = st.tabs(["🗓️ Calendar", "🔔 Reminders"])

with calendar_tab:
    with st.expander("➕ Add event", expanded=False):
        with st.form("add-event", clear_on_submit=True):
            title = st.text_input("Event", placeholder="e.g. Badminton practice")
            left, mid, right = st.columns(3)
            day = left.date_input("Date", value=db.local_today())
            start = mid.time_input("Start", value=time(9, 0))
            end = right.time_input("End", value=time(10, 0))
            all_day = st.checkbox("All day")
            location = st.text_input("Location", placeholder="Optional")
            if st.form_submit_button("Save event", type="primary"):
                if title.strip():
                    db.add(
                        "events",
                        title=title.strip(),
                        event_date=day,
                        start_time="" if all_day else start.strftime("%H:%M"),
                        end_time="" if all_day else end.strftime("%H:%M"),
                        location=location,
                    )
                    st.success("Event saved.")
                else:
                    st.error("Event needs a name.")

    left, right = st.columns([1, 2])
    anchor = left.date_input("Week starting", value=db.local_today(), key="week-anchor")
    span = right.slider("Days to show", 1, 31, 7)
    window_end = anchor + timedelta(days=span - 1)

    events = db.events_between(anchor, window_end)
    deadlines = [item for item in db.school_items() if anchor.isoformat() <= item["due_date"] <= window_end.isoformat()]

    for offset in range(span):
        day = anchor + timedelta(days=offset)
        key = day.isoformat()
        todays_events = [event for event in events if event["event_date"] == key]
        todays_deadlines = [item for item in deadlines if item["due_date"] == key]
        if not todays_events and not todays_deadlines:
            continue
        st.markdown(f"#### {day.strftime('%A, %b %d')}" + (" · today" if day == db.local_today() else ""))
        for event in todays_events:
            cols = st.columns([5, 1])
            when = f"{event['start_time']}–{event['end_time']}" if event["start_time"] else "All day"
            cols[0].info(f"📅 **{when}** {event['title']}" + (f" · 📍 {event['location']}" if event["location"] else ""))
            if cols[1].button("Delete", key=f"del-event-{event['id']}"):
                db.delete("events", event["id"])
                st.rerun()
        for item in todays_deadlines:
            st.warning(f"🎓 {item['kind']} due: **{item['course']}** — {item['title']}")

    if not events and not deadlines:
        st.caption("Nothing scheduled in this window.")

with reminder_tab:
    with st.form("add-reminder", clear_on_submit=True):
        message = st.text_input("Remind me to…", placeholder="e.g. Email Professor Brennan about the essay")
        left, right = st.columns(2)
        remind_day = left.date_input("Day", value=db.local_today(), key="rem-day")
        remind_time = right.time_input("Time", value=(db.local_now() + timedelta(hours=1)).time().replace(second=0, microsecond=0))
        if st.form_submit_button("Set reminder", type="primary"):
            if message.strip():
                db.add("reminders", message=message.strip(), remind_at=datetime.combine(remind_day, remind_time).isoformat(timespec="minutes"))
                st.success("Reminder set.")
            else:
                st.error("What should I remind you about?")

    due = db.due_reminders()
    st.subheader(f"Due now ({len(due)})")
    for reminder in due:
        with st.container(border=True):
            st.markdown(f"🔔 **{reminder['message']}**")
            st.caption(reminder["remind_at"].replace("T", " "))
            ui.row_actions("reminders", reminder, "rem-due", "Dismiss")

    later = db.upcoming_reminders()
    st.subheader(f"Upcoming ({len(later)})")
    for reminder in later:
        with st.container(border=True):
            st.markdown(f"⏳ {reminder['message']}")
            st.caption(reminder["remind_at"].replace("T", " "))
            ui.row_actions("reminders", reminder, "rem-later", "Dismiss")
