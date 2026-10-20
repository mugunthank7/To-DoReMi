import base64, hashlib, hmac, re
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from xml.sax.saxutils import escape
from . import db, service
from .config import TWILIO_AUTH_TOKEN, PUBLIC_URL, ALLOWED_WHATSAPP
from .parser import parse_message
import os

app = FastAPI(title="To-Do-Re-Mi")
STATIC = os.path.join(os.path.dirname(__file__), "..", "static")

class NewTask(BaseModel):
    title: str
    due: str | None = None
    est_minutes: int = 30
    importance: int = 3

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))

@app.get("/api/tasks")
def tasks():
    return service.ranked_view()

@app.post("/api/tasks")
def add(t: NewTask):
    tid = db.add_task(t.title, t.due, t.est_minutes, t.importance)
    service.replan(sync_outlook=False)
    return {"id": tid}

@app.post("/api/tasks/{task_id}/done")
def done(task_id: int):
    t = db.get_task(task_id)
    if not t:
        raise HTTPException(404)
    if t["event_id"]:
        from . import outlook
        outlook.delete_event(t["event_id"])
    db.update_task(task_id, status="done", event_id=None, slot_start=None, slot_end=None)
    return {"ok": True}

@app.delete("/api/tasks/{task_id}")
def remove(task_id: int):
    db.delete_task(task_id)
    return {"ok": True}

@app.post("/api/replan")
def replan(sync: bool = True):
    return service.replan(sync_outlook=None if sync else False)

# ---------- WhatsApp (Twilio) ----------

def _valid_twilio(request: Request, form: dict) -> bool:
    if not TWILIO_AUTH_TOKEN:
        return True   # dev mode: no auth configured
    data = PUBLIC_URL + request.url.path + "".join(k + form[k] for k in sorted(form))
    expected = base64.b64encode(hmac.new(TWILIO_AUTH_TOKEN.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, request.headers.get("X-Twilio-Signature", ""))

def _twiml(text):
    return Response(f"<?xml version='1.0'?><Response><Message>{escape(text)}</Message></Response>",
                    media_type="application/xml")

@app.post("/webhook/whatsapp")
async def whatsapp(request: Request):
    form = dict(await request.form())
    if not _valid_twilio(request, form):
        raise HTTPException(403, "bad signature")
    if ALLOWED_WHATSAPP and form.get("From") != ALLOWED_WHATSAPP:
        raise HTTPException(403, "sender not allowed")
    body = (form.get("Body") or "").strip()
    low = body.lower()

    if low in ("list", "ls", "plan", "today"):
        return _twiml(service.summary())
    if low in ("replan", "reschedule"):
        r = service.replan()
        return _twiml(f"Replanned: {r['scheduled']} scheduled, {len(r['unscheduled'])} didn't fit.\n{service.summary()}")
    if m := re.fullmatch(r"(?:done|finished|✅)\s*#?(\d+)", low):
        tid = int(m.group(1))
        if not db.get_task(tid):
            return _twiml(f"No task #{tid}.")
        done(tid)
        return _twiml(f"✅ Done #{tid}.\n{service.summary(5)}")
    if m := re.fullmatch(r"(?:delete|remove|del)\s*#?(\d+)", low):
        db.delete_task(int(m.group(1)))
        return _twiml(f"🗑 Removed #{m.group(1)}.")

    items = parse_message(body)
    if not items:
        return _twiml("I couldn't find a task in that. Send e.g. 'finish report by tomorrow, 2h, urgent'. Commands: list, done 3, replan.")
    for it in items:
        db.add_task(it["title"], it["due"], it["est_minutes"], it["importance"], source="whatsapp")
    service.replan()
    return _twiml(f"Added {len(items)} task(s).\n{service.summary()}")
