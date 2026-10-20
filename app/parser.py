"""Turn a free-form WhatsApp message into structured tasks."""
import json
import re
from datetime import datetime, timedelta
import httpx
from . import db
from .config import GROQ_API_KEY, GROQ_MODEL, GEMINI_API_KEY, GEMINI_MODEL, LLM_DAILY_CAP, TZ

SYSTEM = """You extract to-do items from a casual chat message. Return ONLY a JSON object {"tasks": [...]}.
Each item: {"title": str, "due": ISO8601 datetime with offset or null, "est_minutes": int, "importance": 1-5}.
importance: 5 = critical/urgent/consequences if missed, 3 = normal, 1 = nice-to-have.
Guess est_minutes realistically (default 30). Resolve relative dates against the given current time.
If the message contains no task, return {"tasks": []}."""

def parse_message(text, now=None):
    """Try Groq, then Gemini (both free tiers), then plain rules. Never loses the user's task."""
    now = now or datetime.now(TZ)
    for name, key, call in (("groq", GROQ_API_KEY, _groq), ("gemini", GEMINI_API_KEY, _gemini)):
        if not key:
            continue
        if not db.try_use_llm(LLM_DAILY_CAP):
            print(f"LLM daily cap ({LLM_DAILY_CAP}) reached; using rules")
            break
        try:
            return _extract(call(text, now))
        except Exception as e:
            print(f"{name} failed ({e}); trying next")
    return _parse_rules(text, now)

def _prompt(text, now):
    cal = ", ".join((now + timedelta(days=i)).strftime("%a %b %d") for i in range(15))
    return (f"Current time: {now.strftime('%A')} {now.isoformat()}\n"
            f"Calendar (use exactly these weekday/date pairs; 'next <weekday>' = the one after this coming one): {cal}\n"
            f"If no time of day is given use 17:00 for deadlines.\nMessage:\n{text}")

def _groq(text, now):
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions", timeout=20,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": GROQ_MODEL, "temperature": 0, "max_tokens": 3000,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _prompt(text, now)}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _gemini(text, now):
    r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        timeout=20, headers={"x-goog-api-key": GEMINI_API_KEY},
        json={"systemInstruction": {"parts": [{"text": SYSTEM}]},
              "contents": [{"role": "user", "parts": [{"text": _prompt(text, now)}]}],
              "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": 3000}})
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def _extract(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    data = json.loads(raw)
    items = data.get("tasks", []) if isinstance(data, dict) else data
    return [_clean(i) for i in items if i.get("title")]

def _clean(i):
    return {
        "title": str(i["title"]).strip(),
        "due": i.get("due") or None,
        "est_minutes": max(5, min(int(i.get("est_minutes") or 30), 480)),
        "importance": max(1, min(int(i.get("importance") or 3), 5)),
    }

def _parse_rules(text, now):
    """Cheap fallback: one task per line / bullet, with a few keyword heuristics."""
    items = []
    for line in re.split(r"[\n;]+|(?:^|\s)[-•*]\s", text):
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if re.fullmatch(r"(hi|hello|hey|yo|ok|okay|thanks|thank you|thx|test|help|\?)[.! ]*", low):
            continue   # chatter, not a task
        importance = 5 if re.search(r"urgent|asap|critical|!!", low) else 4 if "important" in low else 3
        est = 30
        if m := re.search(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)\b", low):
            est = int(float(m.group(1)) * 60)
        elif m := re.search(r"(\d+)\s*(m|min|mins|minutes)\b", low):
            est = int(m.group(1))
        due = None
        eod = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if "today" in low or "tonight" in low:
            due = eod
        elif "tomorrow" in low:
            due = eod + timedelta(days=1)
        elif "next week" in low:
            due = eod + timedelta(days=7)
        items.append(_clean({"title": line, "due": due.isoformat() if due else None,
                             "est_minutes": est, "importance": importance}))
    return items
