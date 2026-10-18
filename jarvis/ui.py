import hmac

import streamlit as st

from jarvis import db, market, research

CSS = """
<style>
.block-container {padding-top: 3rem; max-width: 1100px;}
.jarvis-hero {
    background: radial-gradient(circle at 20% 20%, #0ea5e9 0%, #0b1220 60%);
    border: 1px solid #1e3a5f; border-radius: 16px; padding: 1.25rem 1.5rem; margin-bottom: 1rem;
}
.jarvis-hero h1 {color: #e0f2fe; font-size: 1.6rem; margin: 0;}
.jarvis-hero p {color: #bae6fd; margin: .35rem 0 0 0;}
.pill {display:inline-block; padding:.1rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600; margin-right:.35rem;}
.pill-High {background:#7f1d1d; color:#fecaca;}
.pill-Medium {background:#78350f; color:#fde68a;}
.pill-Low {background:#14532d; color:#bbf7d0;}
.pill-kind {background:#1e3a5f; color:#bae6fd;}
.pill-Buy {background:#14532d; color:#bbf7d0;}
.pill-Hold {background:#1e3a5f; color:#bae6fd;}
.pill-Avoid {background:#7f1d1d; color:#fecaca;}
.reason-plus {color:#86efac;} .reason-minus {color:#fca5a5;} .reason-info {color:#94a3b8;}
</style>
"""


def _password():
    try:
        return st.secrets.get("APP_PASSWORD", "")
    except Exception:
        return ""


def require_login():
    password = _password()
    if not password or st.session_state.get("authed"):
        return
    st.markdown("### 🔒 JARVIS is locked")
    attempt = st.text_input("Password", type="password")
    if attempt and hmac.compare_digest(attempt, password):
        st.session_state.authed = True
        st.rerun()
    elif attempt:
        st.error("Wrong password.")
    st.stop()


def setup(title, icon="🤖"):
    st.set_page_config(page_title=f"JARVIS · {title}", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    require_login()
    db.init_db()


def hero(title, subtitle):
    st.markdown(f"<div class='jarvis-hero'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def pill(text, kind=None):
    return f"<span class='pill pill-{kind or text}'>{text}</span>"


def due_label(iso_day):
    days = db.days_until(iso_day)
    if days < 0:
        return f"⚠️ {abs(days)} day(s) overdue"
    if days == 0:
        return "🔥 due today"
    if days == 1:
        return "⏰ due tomorrow"
    return f"in {days} days"


def row_actions(table, row, key_prefix, done_label="Done"):
    left, right = st.columns(2)
    if "done" in row and left.button(done_label, key=f"{key_prefix}-done-{row['id']}", width="stretch"):
        db.update(table, row["id"], done=1)
        st.rerun()
    if right.button("Delete", key=f"{key_prefix}-del-{row['id']}", width="stretch"):
        db.delete(table, row["id"])
        st.rerun()


@st.cache_data(ttl=900, show_spinner="Fetching market data…")
def _cached_history(symbols):
    return market.fetch_history(list(symbols))


def market_analysis(symbols=None):
    symbols = tuple(sorted(symbols or research.tracked_symbols()))
    if not symbols:
        return [], {}, []
    try:
        history = _cached_history(symbols)
    except Exception as error:
        st.warning(f"Market data is unavailable right now: {error}")
        return [], {}, list(symbols)
    return research.run_analysis(fetch=lambda requested: {symbol: history[symbol] for symbol in requested if symbol in history}, symbols=list(symbols))


def reason_line(reason):
    css, mark = ("reason-plus", "▲") if reason["points"] > 0 else ("reason-minus", "▼") if reason["points"] < 0 else ("reason-info", "•")
    return f"<div class='{css}'>{mark} {reason['text']}</div>"


def speak(text):
    import base64

    from jarvis import voice

    page = f"<html><body>{voice.speech_html(text).replace('window.parent.speechSynthesis || ', '')}</body></html>"
    st.iframe(f"data:text/html;base64,{base64.b64encode(page.encode()).decode()}", height=1)
