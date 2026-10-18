import os


def setting(name, default=""):
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, default))
    except Exception:
        return default
