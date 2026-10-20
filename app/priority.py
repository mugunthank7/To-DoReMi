from datetime import datetime, timezone

def urgency(due_iso, now=None):
    """0-100: how soon the deadline is."""
    if not due_iso:
        return 10
    now = now or datetime.now(timezone.utc)
    hours = (datetime.fromisoformat(due_iso) - now).total_seconds() / 3600
    if hours < 0:
        return 100
    if hours <= 24:
        return 85
    if hours <= 72:
        return 65
    if hours <= 168:
        return 40
    return 20

def score(task, now=None):
    """Higher = do sooner. Importance dominates, urgency pushes, quick wins get a nudge."""
    quick_win = 8 if task["est_minutes"] <= 15 else 0
    return task["importance"] * 14 + urgency(task.get("due"), now) * 0.9 + quick_win

def rank(tasks, now=None):
    return sorted(tasks, key=lambda t: score(t, now), reverse=True)
