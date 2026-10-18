import streamlit as st

st.navigation(
    {
        "JARVIS": [
            st.Page("views/dashboard.py", title="Dashboard", icon="🤖", default=True),
            st.Page("views/assistant_page.py", title="Ask JARVIS", icon="🎙️", url_path="ask"),
        ],
        "Life": [
            st.Page("views/school.py", title="School", icon="🎓"),
            st.Page("views/tasks.py", title="Tasks", icon="✅"),
            st.Page("views/calendar_page.py", title="Calendar", icon="📅", url_path="calendar"),
        ],
        "Money": [
            st.Page("views/investments.py", title="Investments", icon="📈"),
        ],
        "System": [
            st.Page("views/settings.py", title="Settings", icon="⚙️"),
        ],
    }
).run()
