from app.core.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_EXPIRES_MIN", "60")
    monkeypatch.setenv("TZ_CLINICA", "America/Argentina/Buenos_Aires")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "mp-token")
    monkeypatch.setenv("MP_WEBHOOK_SECRET", "mp-secret")
    monkeypatch.setenv("MP_TTL_MIN", "15")
    monkeypatch.setenv("TWILIO_SID", "twilio-sid")
    monkeypatch.setenv("TWILIO_TOKEN", "twilio-token")
    monkeypatch.setenv("TWILIO_WA_FROM", "whatsapp:+14155238886")
    monkeypatch.setenv("GCAL_CALENDAR_ID", "calendar-id")
    monkeypatch.setenv("SMTP_URL", "smtp://user:pass@host:587")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/db"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.jwt_secret == "test-secret"
    assert settings.jwt_expires_min == 60
    assert settings.tz_clinica == "America/Argentina/Buenos_Aires"
    assert settings.mp_access_token == "mp-token"
    assert settings.mp_webhook_secret == "mp-secret"
    assert settings.mp_ttl_min == 15
    assert settings.twilio_sid == "twilio-sid"
    assert settings.twilio_token == "twilio-token"
    assert settings.twilio_wa_from == "whatsapp:+14155238886"
    assert settings.gcal_calendar_id == "calendar-id"
    assert settings.smtp_url == "smtp://user:pass@host:587"
    assert settings.frontend_url == "http://localhost:3000"
    assert settings.log_level == "DEBUG"


def test_settings_uses_defaults(monkeypatch):
    # Clear all env vars
    for key in [
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_SECRET",
        "JWT_EXPIRES_MIN",
        "TZ_CLINICA",
        "MP_ACCESS_TOKEN",
        "MP_WEBHOOK_SECRET",
        "MP_TTL_MIN",
        "TWILIO_SID",
        "TWILIO_TOKEN",
        "TWILIO_WA_FROM",
        "GCAL_CALENDAR_ID",
        "SMTP_URL",
        "FRONTEND_URL",
        "LOG_LEVEL",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = Settings()

    assert (
        settings.database_url
        == "postgresql+asyncpg://postgres:postgres@localhost:5432/turnos_odontologia"
    )
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.jwt_secret == "dev-secret-change-in-production"
    assert settings.jwt_expires_min == 30
    assert settings.tz_clinica == "America/Argentina/Buenos_Aires"
    assert settings.mp_access_token == ""
    assert settings.mp_webhook_secret == ""
    assert settings.mp_ttl_min == 30
    assert settings.twilio_sid == ""
    assert settings.twilio_token == ""
    assert settings.twilio_wa_from == ""
    assert settings.gcal_calendar_id == ""
    assert settings.smtp_url == ""
    assert settings.frontend_url == "http://localhost:5173"
    assert settings.log_level == "INFO"


def test_settings_type_coercion(monkeypatch):
    monkeypatch.setenv("JWT_EXPIRES_MIN", "45")
    monkeypatch.setenv("MP_TTL_MIN", "20")

    settings = Settings()

    assert isinstance(settings.jwt_expires_min, int)
    assert settings.jwt_expires_min == 45
    assert isinstance(settings.mp_ttl_min, int)
    assert settings.mp_ttl_min == 20
