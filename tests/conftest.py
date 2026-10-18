import pytest

from jarvis import db

SECRETS = ["DATABASE_URL", "CANVAS_URL", "CANVAS_TOKEN", "ANTHROPIC_API_KEY", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO", "NTFY_TOPIC", "APP_PASSWORD"]


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("JARVIS_FAKE_MARKET", "1")
    monkeypatch.setenv("JARVIS_NO_TTS", "1")
    for name in SECRETS:
        monkeypatch.delenv(name, raising=False)
    db.init_db()
