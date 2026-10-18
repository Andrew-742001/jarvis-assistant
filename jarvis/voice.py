import io
import json
import re


class VoiceError(Exception):
    pass


def transcribe(audio_bytes, recognizer=None):
    import speech_recognition as sr

    recognizer = recognizer or sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError as error:
        raise VoiceError("I couldn't make out any words. Try again a little closer to the mic.") from error
    except sr.RequestError as error:
        raise VoiceError(f"The speech service is unreachable right now: {error}") from error


def speakable(text):
    text = re.sub(r"\(JARVIS ratings are educational.*?\)", "", text, flags=re.DOTALL)
    text = re.sub(r"[*_#`>|]", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    text = text.replace("\n", ". ").replace("..", ".")
    return re.sub(r"\s{2,}", " ", text).strip()[:1200]


def speech_html(text, rate=0.95):
    payload = json.dumps(speakable(text))
    return f"""
<script>
const say = () => {{
  const synth = window.parent.speechSynthesis || window.speechSynthesis;
  synth.cancel();
  const utterance = new SpeechSynthesisUtterance({payload});
  utterance.rate = {rate};
  utterance.pitch = 0.85;
  const voices = synth.getVoices();
  const preferred = voices.find(v => /Microsoft Ryan|Microsoft Thomas|Google UK English Male|Daniel|Arthur/i.test(v.name)) || voices.find(v => /en-GB/i.test(v.lang)) || voices.find(v => /^en/i.test(v.lang));
  if (preferred) utterance.voice = preferred;
  synth.speak(utterance);
}};
if (speechSynthesis.getVoices().length) say(); else speechSynthesis.onvoiceschanged = say;
</script>
"""


VOICES = {
    "Ryan — deep British (closest to JARVIS)": "en-GB-RyanNeural",
    "Thomas — calm British": "en-GB-ThomasNeural",
    "Andrew — warm American": "en-US-AndrewNeural",
    "Guy — classic American": "en-US-GuyNeural",
    "Sonia — British female": "en-GB-SoniaNeural",
}
DEFAULT_VOICE = "en-GB-RyanNeural"


def neural_mp3(text, voice=DEFAULT_VOICE, rate="-6%", pitch="-6Hz"):
    import asyncio

    import edge_tts

    async def collect():
        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        return bytes(audio)

    return asyncio.run(collect())


def google_mp3(text):
    from gtts import gTTS

    buffer = io.BytesIO()
    gTTS(text, lang="en", tld="co.uk").write_to_fp(buffer)
    return buffer.getvalue()


def tts_mp3(text, voice=None):
    from jarvis.config import setting

    if setting("JARVIS_NO_TTS"):
        return None
    spoken = speakable(text)
    for engine in (lambda: neural_mp3(spoken, voice or DEFAULT_VOICE), lambda: google_mp3(spoken)):
        try:
            audio = engine()
            if audio:
                return audio
        except Exception:
            continue
    return None
