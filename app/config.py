import os


class Config:
    # In production, SECRET_KEY MUST be set via environment variable.
    # In development, a fallback is provided for convenience.
    _secret = os.environ.get('SECRET_KEY')
    if not _secret and os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError(
            "SECRET_KEY environment variable is required in production. "
            "Set it in your .env file or environment."
        )
    SECRET_KEY = _secret or 'dev-secret-key-change-in-production'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///ldms.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Maximum upload size: 100 MB
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    # ── AI Image Analysis (Google Gemini) ──────────────────────────
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    # ── Email Notifications (Flask-Mail) ───────────────────────────
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    NOTIFICATION_EMAILS = os.environ.get('NOTIFICATION_EMAILS', '')