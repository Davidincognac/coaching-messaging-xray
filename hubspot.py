"""HubSpot, the database and sender for every lead the app collects.

Portal 149459867 (EU, "David Poole and Associates"). The token is a private app token in the
HUBSPOT_TOKEN environment variable and is never in the repo.

Two things get written. The contact: first name, email, the Lead magnets checkbox gains the magnet
they just took ("Buying Triggers" or "Website Audit"), the Brand dropdown is set to the brand. And
one note on the contact's timeline. For Buying Triggers the note holds the three answers as typed
and, once chosen, the market. For the website audit it holds the headline read, the score and the
sales page link. These go in a note and not in properties because the free property cap is tight
and a note is where a human reads them anyway.

Nothing here raises. Every call logs its failure and returns None, and every caller runs it in a
daemon thread, so a HubSpot outage can never cost a coach their report. The lead is already in our own
database before any of this runs.
"""
import html
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TOKEN = os.getenv("HUBSPOT_TOKEN", "")
BASE = "https://api.hubapi.com"
LEAD_MAGNET = "Buying Triggers"
LEAD_MAGNET_AUDIT = "Website Audit"
BRAND = "Going Beyond The Illusion"
NOTE_TO_CONTACT = 202          # HubSpot's own association type: note to contact

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()


def enabled():
    return bool(TOKEN)


def _call(method, path, body=None, ok404=False):
    """One request. Returns the decoded JSON, or None on any failure (logged). A 404 is returned as
    None quietly when ok404 is set, because "no such contact yet" is an answer, not a fault."""
    if not TOKEN:
        return None
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12, context=_SSL_CTX) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        if e.code == 404 and ok404:
            return None
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            detail = ""
        print(f"[hubspot] {method} {path} failed: HTTP {e.code} {detail}", flush=True)
    except Exception as e:
        print(f"[hubspot] {method} {path} failed: {type(e).__name__}: {e}", flush=True)
    return None


def upsert_contact(email, first_name="", lead_magnet=LEAD_MAGNET):
    """Create the contact, or update the one that already has this email. Returns the contact id,
    or None. The Lead magnets checkbox is a multi-select, so the existing ticks are kept and this
    one is added. HubSpot stores a multi-select as values joined by semicolons."""
    email = (email or "").strip().lower()
    if not (TOKEN and email):
        return None
    existing = _call("GET", f"/crm/v3/objects/contacts/{urllib.parse.quote(email, safe='')}"
                            "?idProperty=email&properties=lead_magnets,firstname", ok404=True)
    props = {"brand": BRAND}
    if first_name:
        props["firstname"] = first_name
    if existing and existing.get("id"):
        have = [v for v in ((existing.get("properties") or {}).get("lead_magnets") or "").split(";")
                if v]
        if lead_magnet not in have:
            have.append(lead_magnet)
        props["lead_magnets"] = ";".join(have)
        # A first name they typed earlier stays unless they gave one this time.
        if not first_name:
            props.pop("firstname", None)
        res = _call("PATCH", f"/crm/v3/objects/contacts/{existing['id']}", {"properties": props})
        return existing["id"] if res is not None else None
    props["email"] = email
    props["lead_magnets"] = lead_magnet
    res = _call("POST", "/crm/v3/objects/contacts", {"properties": props})
    return (res or {}).get("id")


def _note_body(answers, questions, market="", offered=()):
    e = html.escape
    lines = ["<b>Buying Triggers</b>"]
    for q in questions:
        a = (answers.get(q["key"]) or "").strip()
        lines.append(f"<b>{e(q['ask'])}</b><br>{e(a) if a else '(blank)'}")
    if answers.get("q_more"):
        lines.append(f"<b>None of the first cards fit. In their words:</b><br>{e(answers['q_more'])}")
    if offered:
        lines.append("<b>Markets offered:</b> " + e(", ".join(offered)))
    lines.append(f"<b>Market chosen:</b> {e(market) if market else 'not chosen yet'}")
    return "<br><br>".join(lines)


def _post_note(contact_id, body):
    """One note on the contact's timeline, body already HTML. Returns the note id, or None."""
    if not (TOKEN and contact_id):
        return None
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    res = _call("POST", "/crm/v3/objects/notes", {
        "properties": {"hs_timestamp": str(now_ms), "hs_note_body": body},
        "associations": [{"to": {"id": str(contact_id)},
                          "types": [{"associationCategory": "HUBSPOT_DEFINED",
                                     "associationTypeId": NOTE_TO_CONTACT}]}],
    })
    return (res or {}).get("id")


def create_note(contact_id, answers, questions, market="", offered=()):
    """The Buying Triggers note: the three answers and the market. Returns the note id, or None."""
    return _post_note(contact_id, _note_body(answers, questions, market, offered))


def create_audit_note(contact_id, domain, headline, score, salespage_url):
    """The website audit note: what their homepage said, the score they were shown, and the sales
    page built from it. Returns the note id, or None."""
    e = html.escape
    lines = [f"<b>Website Audit</b><br>{e(domain or '')}",
             f"<b>Headline read:</b><br>{e(headline) if headline else '(none found)'}",
             f"<b>Score:</b> {e(str(score)) if score not in ('', None) else 'not scored'}/10"]
    if salespage_url:
        lines.append(f'<b>Sales page:</b><br><a href="{e(salespage_url)}">{e(salespage_url)}</a>')
    return _post_note(contact_id, "<br><br>".join(lines))


def update_note(note_id, answers, questions, market="", offered=()):
    """The same note, rewritten now the market is chosen. Returns True on success."""
    if not (TOKEN and note_id):
        return False
    res = _call("PATCH", f"/crm/v3/objects/notes/{note_id}", {
        "properties": {"hs_note_body": _note_body(answers, questions, market, offered)}})
    return res is not None
