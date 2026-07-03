import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-insegura-troque-em-producao")
    # Railway fornece postgres:// mas SQLAlchemy exige postgresql://
    _db_url = os.environ.get("DATABASE_URL", "sqlite:///rdsolucoes.db")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Flask-WTF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", 3600))

    # Flask-Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")
    MAIL_TIMEOUT = 10  # segundos — evita travar o worker gunicorn aguardando SMTP

    # Flask-Login
    REMEMBER_COOKIE_DURATION = 30 * 24 * 3600  # 30 dias
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Mercado Pago
    MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
    MP_PUBLIC_KEY = os.environ.get("MP_PUBLIC_KEY", "")
    MP_WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET", "")

    # Site
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
    SITE_NAME = os.environ.get("SITE_NAME", "RD Soluções OS")

    # Segurança
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", 5))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", 30))

    # Upload
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB para .exe
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "downloads")


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
