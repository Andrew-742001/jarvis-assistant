import streamlit as st

from jarvis import alerts, assistant, canvas, db, monitor, ui, voice

ui.setup("Settings", "⚙️")
ui.hero("⚙️ Settings", "Your profile, connections and alerts.")

profile_tab, canvas_tab, alerts_tab, system_tab = st.tabs(["👤 Profile", "🎓 Canvas", "🔔 Alerts", "🧩 System"])

RISKS = ["Conservative", "Moderate", "Aggressive"]

with profile_tab:
    profile = db.profile()
    with st.form("profile"):
        name = st.text_input("What should JARVIS call you?", value=profile["name"])
        risk = st.select_slider(
            "Risk tolerance",
            RISKS,
            value=profile["risk"] if profile["risk"] in RISKS else "Moderate",
            help="Conservative: big drops would stress you out. Aggressive: you can stomach 50%+ swings for higher potential growth.",
        )
        horizon = st.slider("Investment horizon (years until you need the money)", 1, 40, int(float(profile["horizon_years"])))
        goal = st.text_input("Long-term goal", value=profile["goal"], placeholder="e.g. Grow savings for a house in 10 years")
        move = st.slider("Alert me when an asset moves more than this in a day (%)", 1, 20, int(float(profile["move_alert_pct"])))
        labels = list(voice.VOICES)
        current = next((label for label, code in voice.VOICES.items() if code == profile["voice"]), labels[0])
        voice_label = st.selectbox("JARVIS voice", labels, index=labels.index(current))
        if st.form_submit_button("Save profile", type="primary"):
            for key, value in {"name": name, "risk": risk, "horizon_years": horizon, "goal": goal, "move_alert_pct": move, "voice": voice.VOICES[voice_label]}.items():
                db.set_setting(key, value)
            st.cache_data.clear()
            st.success("Profile saved. Ratings now use your new settings.")
    if st.button("🔊 Hear JARVIS's voice"):
        sample = voice.tts_mp3(f"Good evening, {db.get_setting('name')}. All systems are online. How may I assist you?", db.get_setting("voice"))
        if sample:
            st.audio(sample, format="audio/mp3", autoplay=True)
        else:
            st.warning("Couldn't reach the voice service. Check your internet connection.")

with canvas_tab:
    if canvas.is_configured():
        url, _ = canvas.credentials()
        st.success(f"Connected to {url}")
        last = db.get_setting("canvas_last_sync")
        st.caption(f"Last sync: {last.replace('T', ' ') if last else 'never'}")
        if st.button("🔄 Sync from Canvas now", type="primary"):
            try:
                with st.spinner("Talking to Canvas…"):
                    summary = canvas.sync()
                st.success(f"Synced {summary['courses']} courses: {summary['added']} new, {summary['updated']} updated.")
            except canvas.CanvasError as error:
                st.error(str(error))
    else:
        st.info("Canvas isn't connected yet.")
        st.markdown(
            """
1. Log in to Canvas in a browser → **Account → Settings**.
2. Under **Approved Integrations**, click **+ New Access Token**, name it `JARVIS`, and copy the token.
   *(If you don't see that button, your college has turned tokens off — keep adding work by hand.)*
3. Add these two lines to your secrets (`.streamlit/secrets.toml` locally, or the app's **Secrets** box online):
```toml
CANVAS_URL = "https://yourcollege.instructure.com"
CANVAS_TOKEN = "paste-the-token-here"
```
4. Restart JARVIS and click **Sync** here. Your automatic monitor will also re-sync every run.
"""
        )

with alerts_tab:
    ready = alerts.channels()
    st.markdown(f"**Active channels:** {', '.join(ready) if ready else 'none yet'}")
    cols = st.columns(2)
    cols[0].markdown("📧 **Email** " + ("✅" if alerts.email_configured() else "— add `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO`"))
    cols[1].markdown("📱 **Phone (ntfy app)** " + ("✅" if alerts.push_configured() else "— add `NTFY_TOPIC`"))
    if st.button("Send a test alert", disabled=not ready):
        sent, errors = alerts.notify("JARVIS test", "Hello from JARVIS 👋 Alerts are working.")
        if sent:
            st.success(f"Sent via {', '.join(sent)}.")
        for error in errors:
            st.error(error)
    st.divider()
    st.markdown("**Preview what the automatic monitor would send right now** (nothing is sent):")
    if st.button("Run a dry run"):
        with st.spinner("Checking markets and school work…"):
            messages, log = monitor.run(dry_run=True, sync_canvas=False)
        st.code("\n\n".join(messages) or "No new alerts right now.", language=None)
        for line in log:
            st.caption(line)

with system_tab:
    url = db.database_url()
    if url.startswith("sqlite"):
        st.warning("Storage: **local file** (`data/jarvis.db`). Great on your computer; on the free cloud it resets on restart. Add `DATABASE_URL` from Supabase to keep data permanently.")
    else:
        st.success("Storage: **cloud database** — your data is saved permanently.")
    st.markdown(f"Brain: **{'Claude AI' if assistant.ai_enabled() else 'basic commands'}**" + ("" if assistant.ai_enabled() else " — add `ANTHROPIC_API_KEY` to let JARVIS understand free-form requests."))
    st.markdown(f"Canvas: **{'connected' if canvas.is_configured() else 'not connected'}** · Alerts: **{', '.join(alerts.channels()) or 'off'}**")
