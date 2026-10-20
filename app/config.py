import os
from zoneinfo import ZoneInfo

def _load_dotenv():
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_dotenv()

TZ = ZoneInfo(os.getenv("TZ_NAME", "America/Chicago"))
WORK_START = int(os.getenv("WORK_START", "9"))
WORK_END = int(os.getenv("WORK_END", "18"))
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "todo.db"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
MS_TENANT = os.getenv("MS_TENANT", "common")
OUTLOOK_WRITE = os.getenv("OUTLOOK_WRITE", "1") == "1"
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
ALLOWED_WHATSAPP = os.getenv("ALLOWED_WHATSAPP", "")
