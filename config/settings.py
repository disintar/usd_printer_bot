import os
import sys
from pathlib import Path

from loguru import logger
from .env_file import EnvFileLoader

BASE_DIR = Path(__file__).resolve().parent.parent
EnvFileLoader.load_env_file(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-dev-secret-key")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "*").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "wallet",
    "onchain",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "wallet.middleware.ApiRequestLoggingMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

POSTGRES_NAME = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_CONFIG = {
    "host": "postgres.openclaw.svc.cluster.local",
    "port": 5432,
}
POSTGRES_HOST = os.getenv("POSTGRES_HOST", DB_CONFIG["host"])
POSTGRES_PORT = os.getenv("POSTGRES_PORT", str(DB_CONFIG["port"]))

if all([POSTGRES_NAME, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST]):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": POSTGRES_NAME,
            "USER": POSTGRES_USER,
            "PASSWORD": POSTGRES_PASSWORD,
            "HOST": POSTGRES_HOST,
            "PORT": POSTGRES_PORT,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "")
MCP_TIMEOUT_SECONDS = float(os.getenv("MCP_TIMEOUT_SECONDS", "10"))
MCP_PROTOCOL_VERSION = os.getenv("MCP_PROTOCOL_VERSION", "2025-03-26")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.minimax.io/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "MiniMax-M2.7-highspeed")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", OPENAI_API_KEY)
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", OPENAI_MODEL)
DEFAULT_OPENAI_TIMEOUT_SECONDS = "120"
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", DEFAULT_OPENAI_TIMEOUT_SECONDS))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "1024"))
OPENAI_FORCE_JSON_OBJECT = os.getenv("OPENAI_FORCE_JSON_OBJECT", "true").lower() == "true"

# Loguru configuration
LOGURU_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOGURU_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logger.remove()
logger.add(
    sys.stderr,
    format=LOGURU_FORMAT,
    level=LOGURU_LEVEL,
    colorize=True,
)

RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"
FMP_ENABLED = os.getenv("FMP_ENABLED", "false" if RUNNING_TESTS else "true").lower() == "true"
FMP_API_KEY = os.getenv("FMP_API_KEY", "")
PRICE_CRON_ENABLED = os.getenv("PRICE_CRON_ENABLED", "true" if not RUNNING_TESTS else "false").lower() == "true"
PRICE_CRON_INTERVAL_SECONDS = int(os.getenv("PRICE_CRON_INTERVAL_SECONDS", "60"))
TEST_TIME_WARP_ENABLED = os.getenv("TEST_TIME_WARP_ENABLED", "true" if not RUNNING_TESTS else "false").lower() == "true"
TEST_TIME_WARP_INTERVAL_SECONDS = int(os.getenv("TEST_TIME_WARP_INTERVAL_SECONDS", "1"))
