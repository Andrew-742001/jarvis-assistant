from datetime import date, timedelta

import pandas as pd
import streamlit as st

from jarvis import db, research, signals, ui

ui.setup("Dashboard")

info = db.briefing()
ui.hero("🤖 J.A.R.V.I.S.", db.briefing_sentence(info))

metrics = st.columns(4)
metrics[0].metric("Due this week", len(info["school_this_week"]))
metrics[1].metric("Tests & quizzes", len(info["exams_this_week"]))
metrics[2].metric("Open tasks", len(db.tasks()))
metrics[3].metric("Events today", len(info["events_today"]))

if info["reminders_due"]:
    st.subheader("🔔 Reminders")
    for reminder in info["reminders_due"]:
        st.warning(f"{reminder['message']} — {reminder['remind_at'].replace('T', ' ')}")
        ui.row_actions("reminders", reminder, "dash-rem", "Dismiss")

school_col, life_col = st.columns(2)

with school_col:
    st.subheader("🎓 School — next 7 days")
    upcoming = info["overdue_school"] + info["school_this_week"]
    if not upcoming:
        st.success("Nothing due this week.")
    for item in upcoming:
        with st.container(border=True):
            st.markdown(
                f"{ui.pill(item['kind'], 'kind')}{ui.pill(item['priority'])} **{item['course']}** — {item['title']}",
                unsafe_allow_html=True,
            )
            st.caption(f"{item['due_date']} · {ui.due_label(item['due_date'])}")

with life_col:
    st.subheader("✅ Today")
    if not info["events_today"] and not info["tasks_due"]:
        st.success("Your day is clear.")
    for event in info["events_today"]:
        st.info(f"📅 {event['start_time'] or 'All day'} — {event['title']}" + (f" @ {event['location']}" if event["location"] else ""))
    for task in info["tasks_due"]:
        with st.container(border=True):
            st.markdown(f"{ui.pill(task['priority'])} {task['title']}", unsafe_allow_html=True)
            st.caption(ui.due_label(task["due_date"]))
            ui.row_actions("tasks", task, "dash-task")

if research.tracked_symbols():
    st.subheader("📈 Market check")
    results, _, _ = ui.market_analysis()
    if results:
        cards = st.columns(min(4, len(results)))
        for index, result in enumerate(sorted(results, key=lambda item: -abs(item["metrics"]["change_1d"] or 0))[:4]):
            data = result["metrics"]
            cards[index].metric(
                f"{result['symbol']} · {result['rating']}",
                f"${data['price']:,.2f}",
                f"{data['change_1d']:+.2%}" if data["change_1d"] is not None else None,
            )
        st.caption("Biggest movers on your watchlist. Full reasons on the Investments page. " + signals.DISCLAIMER)

st.subheader("📚 Study time — last 7 days")
minutes = db.study_minutes_by_course()
if minutes:
    st.bar_chart(
        pd.DataFrame(minutes.items(), columns=["Course", "Minutes"]).set_index("Course"),
        horizontal=True,
    )
else:
    st.caption("Log a completed study session on the School page to see your chart.")

week = db.events_between(db.local_today(), db.local_today() + timedelta(days=6))
if week:
    st.subheader("🗓️ This week's calendar")
    st.dataframe(
        pd.DataFrame(week)[["event_date", "start_time", "end_time", "title", "location"]]
        .rename(columns=str.title)
        .rename(columns={"Event_Date": "Date", "Start_Time": "Start", "End_Time": "End"}),
        hide_index=True,
        width="stretch",
    )
