from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.scheduler import plan, free_slots
from app.priority import rank
from app.parser import _parse_rules

TZ = ZoneInfo("America/Chicago")
MON = datetime(2026, 10, 19, 8, 0, tzinfo=TZ).astimezone(timezone.utc)   # Monday 8am local

def T(id, mins=60, imp=3, due=None):
    return {"id": id, "title": f"t{id}", "est_minutes": mins, "importance": imp, "due": due}

def test_rank_importance_and_deadline():
    r = rank([T(1, imp=2), T(2, imp=5), T(3, imp=3)], MON)
    assert [t["id"] for t in r] == [2, 3, 1]
    soon = (MON + timedelta(hours=5)).isoformat()
    assert rank([T(1, imp=5), T(2, imp=3, due=soon)], MON)[0]["id"] == 2   # imminent deadline beats undated critical

def test_meeting_is_avoided():
    meeting = (MON + timedelta(hours=1), MON + timedelta(hours=3))   # 9-11 local
    placed, _ = plan([T(1, 60)], [meeting], MON, tz=TZ)
    a, b = placed[1]
    assert a >= meeting[1] and b - a == timedelta(minutes=60)

def test_weekend_skipped_and_work_hours():
    sat = datetime(2026, 10, 24, 8, 0, tzinfo=TZ).astimezone(timezone.utc)
    s = free_slots(sat, [], days=3, tz=TZ)
    assert s[0][0].astimezone(TZ).weekday() == 0     # next slot is Monday

def test_deadline_unmeetable_is_flagged():
    due = (MON + timedelta(minutes=30)).isoformat()   # before work starts / too soon
    placed, missed = plan([T(1, 120, due=due)], [], MON, tz=TZ)
    assert 1 in missed and 1 not in placed

def test_no_overlap():
    placed, _ = plan([T(i, 90) for i in range(1, 6)], [], MON, tz=TZ)
    spans = sorted(placed.values())
    assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1))

def test_rule_parser():
    r = _parse_rules("finish report tomorrow 2h urgent\nbuy milk", MON.astimezone(TZ))
    assert len(r) == 2 and r[0]["importance"] == 5 and r[0]["est_minutes"] == 120 and r[0]["due"]

def test_rule_parser_ignores_chatter():
    assert _parse_rules("hello", MON.astimezone(TZ)) == []
    assert len(_parse_rules("hey\ncall mom", MON.astimezone(TZ))) == 1
