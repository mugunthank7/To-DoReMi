"""Outlook calendar via Microsoft Graph (delegated, device-code login).

Needs an Azure app registration (public client, delegated Calendars.ReadWrite).
Without MS_CLIENT_ID everything degrades to 'calendar is empty, nothing is written'.
"""
import os
from datetime import datetime, timezone
import httpx
import msal
from .config import MS_CLIENT_ID, MS_TENANT

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.ReadWrite"]
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", ".msal_cache.json")
CATEGORY = "ToDoReMi"

def enabled():
    return bool(MS_CLIENT_ID)

def _app():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        cache.deserialize(open(CACHE_FILE).read())
    app = msal.PublicClientApplication(
        MS_CLIENT_ID, authority=f"https://login.microsoftonline.com/{MS_TENANT}", token_cache=cache)
    return app, cache

def _save(cache):
    if cache.has_state_changed:
        open(CACHE_FILE, "w").write(cache.serialize())

def login():
    """Interactive one-time sign-in (run: python -m app.outlook)."""
    app, cache = _app()
    flow = app.initiate_device_flow(scopes=SCOPES)
    print(flow["message"])
    app.acquire_token_by_device_flow(flow)
    _save(cache)
    print("Signed in.")

def _token():
    app, cache = _app()
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    _save(cache)
    if not result or "access_token" not in result:
        raise RuntimeError("Not signed in to Outlook. Run: python -m app.outlook")
    return result["access_token"]

def _h(extra=None):
    return {"Authorization": f"Bearer {_token()}", 'Prefer': 'outlook.timezone="UTC"', **(extra or {})}

def _z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def _parse(s):
    return datetime.fromisoformat(s.split(".")[0]).replace(tzinfo=timezone.utc)

def busy_blocks(start, end):
    """Existing meetings in [start,end) as (start,end) UTC pairs, ignoring our own blocks."""
    if not enabled():
        return []
    out, url = [], f"{GRAPH}/me/calendarView"
    params = {"startDateTime": _z(start), "endDateTime": _z(end),
              "$select": "start,end,showAs,categories,isCancelled", "$top": 100}
    with httpx.Client(timeout=30) as c:
        while url:
            r = c.get(url, headers=_h(), params=params)
            r.raise_for_status()
            data = r.json()
            for ev in data["value"]:
                if ev.get("isCancelled") or ev.get("showAs") == "free" or CATEGORY in ev.get("categories", []):
                    continue
                out.append((_parse(ev["start"]["dateTime"]), _parse(ev["end"]["dateTime"])))
            url, params = data.get("@odata.nextLink"), None
    return out

def create_block(title, start, end):
    body = {"subject": f"▶ {title}", "categories": [CATEGORY], "showAs": "busy",
            "start": {"dateTime": _z(start), "timeZone": "UTC"},
            "end": {"dateTime": _z(end), "timeZone": "UTC"}}
    r = httpx.post(f"{GRAPH}/me/events", headers=_h(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()["id"]

def delete_event(event_id):
    r = httpx.delete(f"{GRAPH}/me/events/{event_id}", headers=_h(), timeout=30)
    if r.status_code not in (204, 404):
        r.raise_for_status()

if __name__ == "__main__":
    login()
