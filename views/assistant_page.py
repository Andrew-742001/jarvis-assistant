import hashlib

import streamlit as st

from jarvis import assistant, db, ui, voice

ui.setup("Ask JARVIS", "🎙️")
ui.hero("🎙️ Ask JARVIS", "Type or talk. Try: “what's due this week?”, “remind me to study at 7pm”, “should I buy VOO?”")

st.session_state.setdefault("chat", [])
st.session_state.setdefault("last_audio", None)

controls = st.columns([2, 1])
speak_replies = controls[1].toggle("🔊 Speak replies", value=True)
controls[0].caption("Brain: " + ("Claude AI — talk naturally." if assistant.ai_enabled() else "basic commands. Add ANTHROPIC_API_KEY in secrets for natural conversation."))

for turn in st.session_state.chat:
    with st.chat_message(turn["role"], avatar="🧑" if turn["role"] == "user" else "🤖"):
        st.markdown(turn["content"])

audio = st.audio_input("🎤 Tap to speak")
typed = st.chat_input("Message JARVIS…")

prompt = typed
if audio is not None:
    digest = hashlib.sha1(audio.getvalue()).hexdigest()
    if digest != st.session_state.last_audio:
        st.session_state.last_audio = digest
        try:
            with st.spinner("Listening…"):
                prompt = voice.transcribe(audio.getvalue())
        except voice.VoiceError as error:
            st.error(str(error))

if prompt:
    history = [{"role": turn["role"], "content": turn["content"]} for turn in st.session_state.chat]
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking…"):
            answer = assistant.reply(prompt, history)
        st.markdown(answer)
    st.session_state.chat.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}])
    if speak_replies:
        spoken = voice.tts_mp3(answer, db.get_setting("voice"))
        if spoken:
            st.audio(spoken, format="audio/mp3", autoplay=True)
            st.caption("No sound? Tap play — some phones block automatic audio.")
        else:
            ui.speak(answer)

if st.session_state.chat and st.button("Clear conversation"):
    st.session_state.chat = []
    st.rerun()
