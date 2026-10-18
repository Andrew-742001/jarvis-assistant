from datetime import date

import pandas as pd
import streamlit as st

from jarvis import canvas, db, ui

ui.setup("School", "🎓")
ui.hero("🎓 School Assistant", "Tests, quizzes, assignments, due dates, and study sessions in one place.")

KINDS = ["Assignment", "Quiz", "Test", "Project", "Reading"]
PRIORITIES = ["High", "Medium", "Low"]

if canvas.is_configured():
    sync_cols = st.columns([3, 1])
    last = db.get_setting("canvas_last_sync")
    sync_cols[0].caption(f"Canvas connected · last sync {last.replace('T', ' ') if last else 'never'}")
    if sync_cols[1].button("🔄 Sync Canvas", width="stretch"):
        try:
            with st.spinner("Syncing…"):
                summary = canvas.sync()
            st.success(f"{summary['added']} new, {summary['updated']} updated from {summary['courses']} courses.")
        except canvas.CanvasError as error:
            st.error(str(error))
else:
    st.caption("Tip: connect Canvas in ⚙️ Settings to import assignments automatically.")

courses = sorted({row["course"] for row in db.all_rows("school_items")} | {row["course"] for row in db.all_rows("study_sessions")})

upcoming_tab, add_tab, study_tab, done_tab = st.tabs(["📋 Upcoming", "➕ Add item", "📚 Study sessions", "✔️ Completed"])

with add_tab:
    with st.form("add-school", clear_on_submit=True):
        course = st.text_input("Course", placeholder="e.g. Linear Algebra")
        title = st.text_input("Title", placeholder="e.g. Chapter 4 problem set")
        left, mid, right = st.columns(3)
        kind = left.selectbox("Type", KINDS)
        due = mid.date_input("Due date", value=db.local_today())
        priority = right.selectbox("Priority", PRIORITIES, index=1)
        notes = st.text_area("Notes", placeholder="Optional")
        if st.form_submit_button("Save", type="primary"):
            if course.strip() and title.strip():
                db.add("school_items", course=course.strip(), title=title.strip(), kind=kind, due_date=due, priority=priority, notes=notes)
                st.success(f"Saved {kind.lower()} for {course}.")
            else:
                st.error("Course and title are required.")

with upcoming_tab:
    items = db.school_items()
    selected = st.multiselect("Filter by course", courses)
    items = [item for item in items if not selected or item["course"] in selected]
    if not items:
        st.info("No upcoming school work. Add something in the ➕ tab.")
    for item in items:
        with st.container(border=True):
            st.markdown(
                f"{ui.pill(item['kind'], 'kind')}{ui.pill(item['priority'])} **{item['course']}** — {item['title']}",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Due {item['due_date']} · {ui.due_label(item['due_date'])}"
                + (f" · {item['notes']}" if item["notes"] else "")
                + (" · from Canvas" if item.get("source") == "canvas" else "")
            )
            if item.get("url"):
                st.markdown(f"[Open in Canvas ↗]({item['url']})")
            ui.row_actions("school_items", item, "school")

with study_tab:
    with st.form("add-study", clear_on_submit=True):
        left, right = st.columns(2)
        study_course = left.text_input("Course", placeholder="e.g. Differential Equations")
        topic = right.text_input("Topic", placeholder="e.g. Laplace transforms")
        left, mid, right = st.columns(3)
        session_day = left.date_input("Date", value=db.local_today(), key="study-date")
        minutes = mid.number_input("Minutes", min_value=5, max_value=600, value=45, step=5)
        completed = right.checkbox("Already done", value=False)
        if st.form_submit_button("Save session", type="primary"):
            if study_course.strip():
                db.add("study_sessions", course=study_course.strip(), topic=topic, session_date=session_day, minutes=int(minutes), done=completed)
                st.success("Study session saved.")
            else:
                st.error("Course is required.")

    sessions = db.all_rows("study_sessions", "session_date DESC")
    planned = [row for row in sessions if not row["done"]]
    if planned:
        st.markdown("**Planned sessions**")
        for row in planned:
            with st.container(border=True):
                st.markdown(f"**{row['course']}** — {row['topic'] or 'General review'} · {row['minutes']} min")
                st.caption(f"{row['session_date']} · {ui.due_label(row['session_date'])}")
                ui.row_actions("study_sessions", row, "study", "Completed")
    finished = [row for row in sessions if row["done"]]
    if finished:
        st.markdown("**Study log**")
        frame = pd.DataFrame(finished)
        st.metric("Total minutes logged", int(frame["minutes"].sum()))
        st.dataframe(
            frame[["session_date", "course", "topic", "minutes"]].rename(columns={"session_date": "Date", "course": "Course", "topic": "Topic", "minutes": "Minutes"}),
            hide_index=True,
            width="stretch",
        )

with done_tab:
    finished_items = [item for item in db.school_items(include_done=True) if item["done"]]
    if not finished_items:
        st.caption("Completed items show up here.")
    for item in finished_items:
        cols = st.columns([4, 1])
        cols[0].markdown(f"~~{item['course']} — {item['title']}~~ ({item['kind']}, {item['due_date']})")
        if cols[1].button("Undo", key=f"undo-{item['id']}"):
            db.update("school_items", item["id"], done=0)
            st.rerun()
