"""Turn a free-form WhatsApp message into structured tasks."""
import json
import re
from datetime import datetime, timedelta
from .config import ANTHROPIC_API_KEY, TZ

SYSTEM = """You extract to-do items from a casual chat message. Return ONLY a JSON array.
Each item: {"title": str, "due": ISO8601 datetime with offset or null, "est_minutes": int, "importance": 1-5}.
importance: 5 = critical/urgent/consequences if missed, 3 = normal, 1 = nice-to-have.
Guess est_minutes realistically (default 30). Resolve relative dates against the given current time.
If the message contains no task, return []."""

def parse_message(text, now=None):
    now = now or datetime.now(TZ)
    if ANTHROPIC_API_KEY:
        try:
            return _parse_llm(text, now)
        except Exception as e:  # network/JSON problems: don't lose the user's task
            print("LLM parse failed, using fallback:", e)
    return _parse_rules(text, now)

def _parse_llm(text, now):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-5-5",
        max_tokens=1000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Current time: {now.isoformat()}\nMessage:\n{text}"}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    return [_clean(i) for i in json.loads(raw) if i.get("title")]

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
