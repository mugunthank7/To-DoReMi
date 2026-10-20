"""Pure scheduling logic: free slots from working hours minus busy blocks, first-fit by priority."""
from datetime import datetime, timedelta, timezone
from .config import TZ, WORK_START, WORK_END
from .priority import rank

STEP = 15          # minutes; slots start on a 15-min grid
BUFFER = 10        # minutes of breathing room after each block

def _ceil(dt):
    dt = dt.replace(second=0, microsecond=0)
    extra = (-dt.minute) % STEP
    return dt + timedelta(minutes=extra)

def free_slots(now, busy, days=7, tz=TZ, work_start=WORK_START, work_end=WORK_END):
    slots = []
    today = now.astimezone(tz).date()
    for d in range(days):
        day = today + timedelta(days=d)
        if day.weekday() >= 5:      # skip weekends
            continue
        s = datetime(day.year, day.month, day.day, work_start, tzinfo=tz).astimezone(timezone.utc)
        e = datetime(day.year, day.month, day.day, work_end, tzinfo=tz).astimezone(timezone.utc)
        s = max(s, _ceil(now))
        cur = [(s, e)] if s < e else []
        for bs, be in sorted(busy):
            nxt = []
            for a, b in cur:
                if be <= a or bs >= b:
                    nxt.append((a, b))
                    continue
                if bs > a:
                    nxt.append((a, bs))
                if be < b:
                    nxt.append((_ceil(be), b))
            cur = nxt
        slots += [(a, b) for a, b in cur if b > a]
    return sorted(slots)

def plan(tasks, busy, now=None, **kw):
    """Return ({task_id: (start,end)}, [unscheduled task ids])."""
    now = now or datetime.now(timezone.utc)
    slots = free_slots(now, busy, **kw)
    placed, missed = {}, []
    for t in rank(tasks, now):
        need = timedelta(minutes=t["est_minutes"])
        due = datetime.fromisoformat(t["due"]) if t.get("due") else None
        for i, (a, b) in enumerate(slots):
            if b - a < need:
                continue
            if due and a + need > due:
                break   # slots are chronological; nothing later can meet the deadline
            placed[t["id"]] = (a, a + need)
            rest = _ceil(a + need + timedelta(minutes=BUFFER))
            slots[i:i + 1] = [(rest, b)] if rest < b else []
            break
        else:
            missed.append(t["id"])
            continue
        if t["id"] not in placed:
            missed.append(t["id"])
    return placed, missed
