from datetime import datetime, timedelta, timezone
from . import db, outlook, scheduler
from .config import OUTLOOK_WRITE, TZ
from .priority import rank, score

def replan(sync_outlook=None):
    """Recompute time blocks for all open tasks; optionally mirror them into Outlook."""
    sync = OUTLOOK_WRITE and outlook.enabled() if sync_outlook is None else sync_outlook
    now = datetime.now(timezone.utc)
    tasks = db.list_tasks("todo")
    for t in tasks:                      # clear our previous blocks first
        if t["event_id"] and sync:
            outlook.delete_event(t["event_id"])
        db.update_task(t["id"], slot_start=None, slot_end=None, event_id=None)
    busy = outlook.busy_blocks(now, now + timedelta(days=8)) if outlook.enabled() else []
    placed, missed = scheduler.plan(tasks, busy, now)
    for tid, (a, b) in placed.items():
        eid = outlook.create_block(next(t["title"] for t in tasks if t["id"] == tid), a, b) if sync else None
        db.update_task(tid, slot_start=a.isoformat(), slot_end=b.isoformat(), event_id=eid)
    return {"scheduled": len(placed), "unscheduled": missed}

def ranked_view():
    now = datetime.now(timezone.utc)
    return [{**t, "score": round(score(t, now), 1)} for t in rank(db.list_tasks("todo"), now)]

def fmt_slot(iso):
    return datetime.fromisoformat(iso).astimezone(TZ).strftime("%a %-I:%M%p").replace("AM", "am").replace("PM", "pm")

def summary(limit=8):
    rows = ranked_view()[:limit]
    if not rows:
        return "Nothing on your list 🎉"
    lines = []
    for i, t in enumerate(rows, 1):
        when = f" → {fmt_slot(t['slot_start'])}" if t["slot_start"] else " (no slot yet)"
        lines.append(f"{i}. #{t['id']} {t['title']} [{t['est_minutes']}m, P{t['importance']}]{when}")
    return "\n".join(lines)
