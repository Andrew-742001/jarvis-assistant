from datetime import date

import streamlit as st

from jarvis import db, ui

ui.setup("Tasks", "✅")
ui.hero("✅ Tasks", "Your personal to-do list, sorted by due date and priority.")

CATEGORIES = ["Personal", "Work", "Errands", "Health", "Career", "Other"]
PRIORITIES = ["High", "Medium", "Low"]

with st.form("add-task", clear_on_submit=True):
    title = st.text_input("What needs doing?", placeholder="e.g. Update resume")
    left, mid, right, far = st.columns(4)
    category = left.selectbox("Category", CATEGORIES)
    priority = mid.selectbox("Priority", PRIORITIES, index=1)
    has_due = right.checkbox("Has due date", value=True)
    due = far.date_input("Due", value=db.local_today())
    if st.form_submit_button("Add task", type="primary"):
        if title.strip():
            db.add("tasks", title=title.strip(), category=category, priority=priority, due_date=due if has_due else None)
            st.success("Task added.")
        else:
            st.error("Give the task a name.")

open_tasks = db.tasks()
category_filter = st.segmented_control("Show", ["All"] + CATEGORIES, default="All")
visible = [task for task in open_tasks if category_filter in (None, "All") or task["category"] == category_filter]

st.subheader(f"Open ({len(visible)})")
if not visible:
    st.info("Nothing open here. Nice.")
for task in visible:
    with st.container(border=True):
        st.markdown(f"{ui.pill(task['priority'])}{ui.pill(task['category'], 'kind')} {task['title']}", unsafe_allow_html=True)
        st.caption(f"{task['due_date']} · {ui.due_label(task['due_date'])}" if task["due_date"] else "No due date")
        ui.row_actions("tasks", task, "task")

finished = [task for task in db.tasks(include_done=True) if task["done"]]
with st.expander(f"Completed ({len(finished)})"):
    for task in finished:
        cols = st.columns([4, 1])
        cols[0].markdown(f"~~{task['title']}~~")
        if cols[1].button("Undo", key=f"undo-task-{task['id']}"):
            db.update("tasks", task["id"], done=0)
            st.rerun()
