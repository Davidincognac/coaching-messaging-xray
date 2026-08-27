"""
Coaching Website Audit, runnable web demo.

Launch:   python3 app.py
Then open http://localhost:8000 in your browser, type a coach's website, and
watch the Report Card render. This is your product's free tier, running locally.

No extra installs, uses only Python's built-in web server. The AI diagnosis
turns on automatically once ANTHROPIC_API_KEY is set in your environment.
"""

import base64
import html
import json as _json
import os
import re
import ssl
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote as _url_quote

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)
except ImportError:
    pass

from audit import (audit_url, LABELS, DEFINITIONS, DISPLAY_CRIT, websites_read_count,   # the engine we built
                   PCT_FAIL_5SEC, BUYER_VOICE_1_IN, MARKET_AVG_10, TOP10_10, BENCH)   # market stats: single source of truth in audit.py
# "1 in 14 speak their buyer's language" => the other 93%. Derived, so the pair can never disagree.
PCT_NOT_BUYER_VOICE = 100 - round(100 / BUYER_VOICE_1_IN)
from storage import save_audit, get_audit

PORT = int(os.getenv("PORT", "8000"))
MAILERLITE_API_KEY = os.getenv("MAILERLITE_API_KEY", "")
# On Render, set APP_BASE_URL to your service URL (e.g. https://your-app.onrender.com).
# Locally it falls back to localhost so email links still work during development.
APP_BASE_URL = os.getenv("APP_BASE_URL", f"http://localhost:{PORT}").rstrip("/")

def _pick_screenshots_dir():
    """Persistent disk on Render, app folder locally. Same fail-soft rule as storage.py: a
    missing /var/data degrades to non-persistent screenshots, never a dead site."""
    if os.getenv("RENDER"):
        d = "/var/data/screenshots"
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except Exception as e:
            print(f"[screenshots] WARNING: {d} unavailable ({e}); using the app folder (not persistent).",
                  flush=True)
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
    os.makedirs(d, exist_ok=True)
    return d

SCREENSHOTS_DIR = _pick_screenshots_dir()

# urllib needs an explicit CA bundle on python.org macOS builds (their Python ships without system certs
# wired in, so every https urlopen dies with CERTIFICATE_VERIFY_FAILED). certifi ships with requests,
# which the audit engine already depends on, so it's always installed.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()

def _screenshot_filename(domain: str) -> str:
    """Safe filename from a domain: strip protocol, keep alphanum/hyphen, collapse underscores."""
    clean = re.sub(r"https?://", "", domain).strip("/")
    return re.sub(r"[^a-zA-Z0-9\-]", "_", clean) + ".png"

def _save_playwright_shot(domain: str, thumbnail: str) -> str:
    """Persist the audit's own Playwright screenshot (a base64 data URI) to the screenshots folder.
    We already rendered the page during the audit, so saving it costs nothing and keeps microlink
    as a rare fallback instead of a per-audit dependency. Returns the web path, or '' if the
    thumbnail isn't a usable data URI (then the caller falls back to microlink)."""
    if not (thumbnail or "").startswith("data:image/png;base64,"):
        return ""
    try:
        raw = base64.b64decode(thumbnail.split(",", 1)[1])
        if len(raw) < 1000:
            return ""
        fname = _screenshot_filename(domain)
        with open(os.path.join(SCREENSHOTS_DIR, fname), "wb") as f:
            f.write(raw)
        return "/screenshots/" + fname
    except Exception:
        return ""

def _save_screenshot(domain: str) -> str:
    """Fetch a screenshot from microlink.io and write it to the screenshots folder.
    Returns the web-accessible path (/screenshots/<filename>) or, when the fetch fails but a
    previously saved PNG for this domain is still on disk, the path to that old image, so a
    rate-limit blip never blanks a screenshot we already had. '' only when we have nothing.
    A PNG younger than 24h (the audit-cache window) is reused WITHOUT calling microlink — the
    anonymous tier is ~50 requests/day per IP, and refetching on every report view was burning
    that quota, which is why screenshots 'randomly' went missing later in the day."""
    fname = _screenshot_filename(domain)
    web_path = "/screenshots/" + fname
    disk_path = os.path.join(SCREENSHOTS_DIR, fname)
    try:
        if os.path.isfile(disk_path) and (time.time() - os.path.getmtime(disk_path)) < 24 * 3600:
            return web_path
    except Exception:
        pass
    try:
        encoded = _url_quote("https://" + domain, safe="")
        api_url = f"https://api.microlink.io/?url={encoded}&screenshot=true&embed=screenshot.url"
        req = urllib.request.Request(api_url, headers={"User-Agent": "CoachAudit/1.0"})
        with urllib.request.urlopen(req, timeout=55, context=_SSL_CTX) as resp:
            img_bytes = resp.read()
        if not img_bytes or len(img_bytes) < 1000:
            # A tiny body is a microlink error payload (rate limit JSON etc.), not an image.
            print(f"[screenshot] {domain}: response too small ({len(img_bytes)} bytes), not an image", flush=True)
            return web_path if os.path.isfile(disk_path) else ""
        with open(disk_path, "wb") as f:
            f.write(img_bytes)
        return web_path
    except Exception as e:
        print(f"[screenshot] {domain}: {e}", flush=True)
        # Rate limit / timeout / network blip: fall back to the last good PNG if we have one.
        return web_path if os.path.isfile(disk_path) else ""

# Angelo, David's mascot. Drop the image in as coach_audit_app/angelo.png and it appears automatically.
MASCOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angelo.png")

def mascot_img():
    """Show Angelo only if the file is actually there, so we never render a broken image."""
    return ('<img class="mascot" src="/angelo.png" alt="Angelo, who reads your website like a cold buyer">'
            if os.path.exists(MASCOT_PATH) else "")

PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Coaching Website Report Card</title>
<style>
  @font-face{{font-family:'Inter';font-weight:100 900;font-display:swap;src:url(/inter.woff2) format('woff2')}}
  @font-face{{font-family:'SourceSerif';font-weight:200 900;font-display:swap;src:url(/serif.woff2) format('woff2')}}
  :root{{
    --serif:'SourceSerif',Georgia,'Times New Roman',serif;
    --navy:#0B132B;--navy-card:#131D3E;--navy-deep:#0F1834;--navy-line:#27335C;
    --ivory:#F4F5F7;--ivory-dim:#A9B1C4;
    --paper:#F4F5F7;--surface:#fff;--ink:#1B222C;--muted:#5A6472;--line:#E1E4EA;
    --accent:#3a76bd;--accent-ink:#234e83;--glow:#7FA9DD;--soft:#EBF1F8;
    --gold:#D4AF37;--gold-h:#C2A02F;
    --good:#2A7B56;--good-glow:#5CB88C;--warn:#A87B23;--critical:#A62626;}}
  *{{box-sizing:border-box}}
  html{{background:var(--navy)}}
  body{{margin:0;background:var(--navy);color:var(--ink);
    font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6}}
  .wrap{{max-width:760px;margin:0 auto;padding:64px 24px 72px}}
  .hero-band{{background:var(--navy);color:var(--ivory)}}
  .serif{{font-family:"Inter",sans-serif}}
  .eyebrow{{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.24em;
    text-transform:uppercase;color:var(--ivory-dim);font-weight:600}}
  h1{{font-family:"Inter",sans-serif;font-weight:700;font-size:clamp(30px,6.5vw,52px);
    letter-spacing:-.025em;line-height:1.08;margin:.35em 0 .3em;color:#fff}}
  .sub{{color:var(--ivory);font-weight:300;font-size:17px;line-height:1.7;margin:0 0 32px;max-width:58ch}}
  .sub b{{color:var(--glow);font-weight:600}}
  .hero{{display:flex;align-items:center;gap:32px;margin-bottom:32px}}
  .hero-copy{{flex:1;min-width:0}}
  .hero-copy h1{{margin-top:.1em}} .hero-copy .sub{{margin-bottom:0}}
  .mascot{{width:160px;height:auto;flex-shrink:0}}
  @media(max-width:560px){{.hero{{flex-direction:column;align-items:flex-start;gap:10px}}
    .mascot{{width:120px}}}}
  form{{display:flex;flex-direction:column;gap:12px;background:var(--navy-card);border:1px solid var(--navy-line);
    border-radius:10px;padding:24px}}
  input[type=text],input[type=email]{{border:1px solid var(--navy-line);border-radius:6px;
    padding:14px 16px;font-size:16px;color:var(--ivory);background:var(--navy-deep);width:100%}}
  input[type=text]::placeholder,input[type=email]::placeholder{{color:var(--ivory-dim)}}
  input[type=text]:focus,input[type=email]:focus{{outline:2px solid var(--accent);border-color:var(--accent)}}
  button{{background:var(--gold);color:var(--navy);border:0;border-radius:6px;padding:16px 24px;
    font-family:inherit;font-size:16px;font-weight:700;letter-spacing:.01em;cursor:pointer;margin-top:4px}}
  button:hover{{background:var(--gold-h)}}
  .hint{{font-size:13px;color:var(--ivory-dim);margin-top:16px;line-height:1.6}}
  .hint b{{color:var(--glow)}}
  .plan2{{margin-top:14px;background:var(--navy-card);border:1px solid var(--navy-line);
    border-radius:10px;padding:20px 22px}}
  .plan-wrap{{position:relative;display:block;width:min(560px,100%);margin:0 auto;container-type:inline-size}}
  .plan-img{{display:block;width:100%;height:auto}}
  .plan-lbl{{position:absolute;left:63%;top:15%;width:23.5%;height:44%;display:flex;flex-direction:column;
    justify-content:center;gap:7%;transform:rotate(-1deg)}}
  .pl-h{{font-weight:700;color:#141414;font-size:13px;font-size:2.8cqw;line-height:1.2}}
  .pl-step{{position:relative;padding-left:14%;color:#141414;font-size:11px;font-size:2.1cqw;
    line-height:1.3;font-weight:600}}
  .pl-step span{{position:absolute;left:0;top:.1em;width:10%;aspect-ratio:1;border-radius:50%;
    background:var(--gold);color:var(--navy);font-weight:700;display:flex;align-items:center;
    justify-content:center;font-size:1.7cqw}}
  .p2-cap{{color:var(--ivory);font-size:14px;line-height:1.6;margin:12px 0 0;text-align:center}}
  .p2-cap b{{color:var(--glow)}}
  .p2-note{{color:var(--ivory);font-size:14px;line-height:1.6;margin:12px 0 0;border-top:1px solid var(--navy-line);
    padding-top:12px}}
  .p2-note+.p2-note{{border-top:0;padding-top:0;margin-top:10px}}
  #result:not(:empty){{background:var(--paper);padding:56px 24px 88px}}
  #result>*{{max-width:760px;margin-left:auto;margin-right:auto}}
  #result>.card:first-child{{margin-top:0}}
  .card{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:32px;
    box-shadow:0 1px 3px rgba(11,19,43,.08);margin-top:28px}}
  @media(max-width:560px){{.card{{padding:24px 18px}}}}
  .report>*+*{{margin-top:28px}}
  .sec{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:36px 32px;
    box-shadow:0 1px 3px rgba(11,19,43,.08)}}
  @media(max-width:560px){{.sec{{padding:26px 18px}}}}
  .grade{{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);
    padding-bottom:18px;margin-bottom:20px}}
  .num{{font-family:var(--serif);font-size:72px;font-weight:650;letter-spacing:-.02em;line-height:1}}
  .num.crit{{color:var(--critical)}} .num.warn{{color:#7A5A16}} .num.good{{color:var(--good)}}
  .den{{font-family:"Inter",sans-serif;color:var(--muted);font-size:15px}}
  .tier{{margin-left:auto;font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.12em;
    text-transform:uppercase;color:var(--muted)}}
  .barwrap{{padding:16px 0;border-top:1px solid var(--line)}}
  .barwrap:first-child{{border-top:0;padding-top:2px}}
  .barhead{{display:flex;align-items:baseline;justify-content:space-between;gap:16px}}
  .lbl{{font-size:16px;font-weight:600;color:var(--ink);line-height:1.3}}
  .chip{{display:inline-block;font-weight:700;font-size:16px;padding:4px 12px;border-radius:8px;line-height:1.3}}
  .chip .den{{color:inherit;opacity:.65;font-weight:600;font-size:12px}}
  .chip.good{{background:#EDF5F0;color:var(--good)}}
  .chip.warn{{background:#F8F3E7;color:#7A5A16}}
  .chip.crit{{background:#F8EEEE;color:var(--critical)}}
  .mark{{display:inline-block;width:22px}}
  .mark.ok::before{{content:"✓";color:var(--good);font-weight:700}}
  .mark.no::before{{content:"✗";color:var(--critical);font-weight:700}}
  .mark.na::before{{content:"–";color:var(--muted);font-weight:700}}
  .track{{height:8px;background:#ECEFF4;border-radius:6px;overflow:hidden;margin:12px 0 0}}
  .fill{{height:100%;border-radius:6px}}
  .fill.crit{{background:var(--critical)}} .fill.warn{{background:var(--warn)}} .fill.good{{background:var(--good)}}
  .fill.na{{background:transparent}}
  .vs{{font-size:16px;font-weight:700;color:var(--ink);white-space:nowrap;text-align:right;line-height:1.1}}
  .vs .den{{font-weight:600;color:var(--muted);font-size:13px}}
  .vs .mkt{{display:block;font-weight:500;color:var(--muted);font-size:12px;margin-top:3px}}
  .def{{font-size:13px;color:var(--muted);margin:12px 0 0;line-height:1.5;max-width:64ch}}
  .barnote{{font-size:15px;color:var(--ink);margin:8px 0 0;line-height:1.6;max-width:62ch}}
  .barnote p{{margin:0 0 10px}} .barnote p:last-child{{margin:0}}
  .scores-h{{font-family:var(--serif);font-size:19px;color:var(--ink);line-height:1.55;margin:0 0 8px;max-width:58ch}}
  .honest{{margin-top:16px;font-size:14px;color:var(--muted);line-height:1.55;border-top:1px solid var(--line);
    padding-top:14px}}
  .diag{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:36px 32px;
    box-shadow:0 1px 3px rgba(11,19,43,.08);margin:0;line-height:1.65}}
  @media(max-width:560px){{.diag{{padding:26px 18px}}}}
  .diag h3{{font-family:var(--serif);font-size:25px;font-weight:600;margin:0 0 16px}}
  .diag .row{{margin:26px 0}}
  .diag .row p{{margin:0 0 10px}} .diag .row p:last-child{{margin-bottom:0}}
  .diag .k{{display:flex;align-items:center;gap:9px;font-family:"Inter",sans-serif;font-size:13px;
    letter-spacing:.12em;text-transform:uppercase;color:var(--accent-ink);font-weight:700;margin:0 0 10px}}
  .diag .k::before{{content:"";width:18px;height:4px;background:var(--accent);border-radius:2px;flex-shrink:0}}
  .diag ul{{margin:6px 0 0;padding-left:20px}} .diag li{{margin:0 0 14px}}
  .diag li p{{margin:0 0 8px}} .diag li p:last-child{{margin-bottom:0}}
  .diag .row+.row{{border-top:1px solid var(--line);padding-top:26px}}
  .fixlist{{margin:6px 0 0;padding:0;list-style:none;counter-reset:fix}}
  .fixlist li{{position:relative;padding:0 0 18px 44px;margin:0}}
  .fixlist li:last-child{{padding-bottom:0}}
  .fixlist li::before{{counter-increment:fix;content:counter(fix);position:absolute;left:0;top:0;
    width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;
    display:flex;align-items:center;justify-content:center;font-size:14px}}
  .verdict-note{{background:var(--soft);border-left:4px solid var(--accent);border-radius:0 8px 8px 0;
    padding:16px 20px;font-family:var(--serif);font-style:italic;font-size:17px;line-height:1.6}}
  .verdict-note p{{margin:0 0 10px}} .verdict-note p:last-child{{margin:0}}
  .diag h3+.row p:first-of-type::first-letter,.voice h4+p::first-letter{{font-family:var(--serif);
    float:left;font-size:52px;line-height:.85;padding:4px 8px 0 0;font-weight:600;color:var(--accent-ink)}}
  .qchip{{display:inline-block;background:#fff;border:1px solid var(--line);border-left:3px solid var(--accent);
    border-radius:8px;padding:2px 10px;margin:2px 0;font-weight:600}}
  .voice .statpane{{background:var(--soft);border:1px solid #CBD9EC;border-radius:10px;padding:16px 20px}}
  .verdict-img{{width:112px;aspect-ratio:1;object-fit:cover;border-radius:50%;flex-shrink:0;
    border:2px solid var(--accent);box-shadow:0 0 0 5px var(--soft);margin-left:auto;align-self:center}}
  @media(max-width:560px){{.verdict-img{{width:88px}}}}
  .ev-head{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:16px}}
  .ev-head .h{{margin-bottom:0}}
  .sec-angelo{{width:96px;aspect-ratio:1;object-fit:cover;border-radius:50%;flex-shrink:0;
    border:2px solid var(--accent);box-shadow:0 0 0 5px var(--soft)}}
  @media(max-width:560px){{.sec-angelo{{width:76px}}}}
  .mi-img{{display:block;width:min(300px,72%);height:auto;margin:0 auto 18px;
    filter:drop-shadow(0 8px 20px rgba(0,0,0,.4))}}
  .cta-angelo-wrap{{position:relative;display:block;width:min(400px,90%);margin:28px auto 0;
    container-type:inline-size}}
  .cta-angelo{{display:block;width:100%;height:auto}}
  .bubble-txt{{position:absolute;left:8%;top:14%;width:33%;height:23%;display:flex;
    align-items:center;justify-content:center;text-align:center;font-weight:700;color:#141414;
    font-size:13px;font-size:3.7cqw;line-height:1.25}}
  .caveat{{margin-top:12px;padding:16px 18px;background:var(--soft);border-left:4px solid var(--accent);
    border-radius:0 8px 8px 0;font-size:15px;line-height:1.55}}
  .caveat b{{color:var(--accent-ink)}}
  .caveat p{{margin:0 0 10px}} .caveat p:last-child{{margin:0}}
  .badge{{display:inline-block;font-family:"Inter",sans-serif;font-size:12px;
    padding:3px 8px;border-radius:20px;background:var(--soft);color:var(--accent-ink);margin-left:8px}}
  .dead{{color:var(--critical);font-size:17px}}
  .err{{color:var(--critical)}}
  .pctl{{font-family:"Inter",sans-serif;font-size:13px;color:var(--accent-ink);font-weight:600}}
  .ev{{background:var(--surface);border:1.5px solid var(--accent);border-radius:12px;padding:36px 32px;
    box-shadow:0 0 0 5px var(--soft),0 1px 3px rgba(11,19,43,.08);margin:0}}
  @media(max-width:560px){{.ev{{padding:26px 18px}}}}
  .ev .h{{font-family:var(--serif);font-size:21px;font-weight:600;color:var(--ink);line-height:1.4;margin-bottom:18px}}
  .ev .q{{font-family:var(--serif);font-style:italic;font-size:19px;line-height:1.5;color:var(--ink);
    border-left:3px solid var(--accent);padding-left:16px;margin:10px 0}}
  .ev .meta{{font-size:13px;color:var(--muted);margin-top:6px}}
  .ev .tag{{display:inline-block;font-family:"Inter",sans-serif;font-size:12px;padding:2px 8px;
    border-radius:20px;margin:4px 6px 0 0}}
  .tag.no{{background:#F5E9E9;color:var(--critical)}} .tag.yes{{background:var(--soft);color:var(--accent-ink)}}
  .tag.neutral{{background:#EEF0F4;color:var(--muted)}}
  .analysed{{font-family:var(--serif);font-size:clamp(19px,2.8vw,21px);line-height:1.5;
    margin:0 0 22px;padding-bottom:20px;border-bottom:1px solid var(--line)}}
  .analysed p{{margin:0 0 14px}} .analysed p:last-child{{margin:0}}
  .analysed b{{color:var(--accent-ink)}}
  .reframe{{background:var(--soft);color:var(--ink);border-left:4px solid var(--accent);
    border-radius:0 10px 10px 0;padding:22px 24px;margin:0 0 24px;line-height:1.6;font-size:15px}}
  .reframe p{{margin:0 0 12px}} .reframe p:last-child{{margin:0}}
  .reframe b{{color:var(--accent-ink)}}
  .checklist{{background:#F7F8FA;border:1px solid var(--line);border-radius:10px;padding:20px 22px;margin:0 0 24px}}
  .checklist .h{{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--muted);margin-bottom:10px}}
  .checklist ul{{margin:0;padding-left:20px;columns:2;column-gap:26px}}
  .checklist li{{margin:5px 0;font-size:14px;break-inside:avoid}}
  .checklist .foot{{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:14px}}
  @media(max-width:560px){{.checklist ul{{columns:1}}}}
  .reveal{{margin:0;padding:36px 32px;background:var(--surface);border:1px solid var(--line);border-radius:12px;
    box-shadow:0 1px 3px rgba(11,19,43,.08);border-top:4px solid var(--line)}}
  @media(max-width:560px){{.reveal{{padding:26px 18px}}}}
  .reveal.good{{border-top-color:var(--good)}}
  .reveal.warn{{border-top-color:var(--warn)}}
  .reveal.crit{{border-top-color:var(--critical)}}
  .reveal .h{{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.12em;text-transform:uppercase;
    color:var(--muted);margin-bottom:10px}}
  .verdict{{font-family:var(--serif);font-size:19px;line-height:1.45}}
  .strength{{background:#EDF5F0;border:1px solid #CBE2D6;border-radius:10px;padding:14px 18px;margin:18px 0;
    font-size:14px}}
  .strength b{{color:var(--good)}}
  .scope{{font-size:13px;color:var(--muted);margin:0 0 18px;padding:9px 13px;background:#F7F8FA;border-radius:8px}}
  .scope .date{{color:var(--accent-ink);font-weight:600}}
  .gap{{font-family:"Inter",sans-serif;font-size:13px;color:var(--accent-ink);font-weight:600;max-width:52ch}}
  .gap p{{margin:0 0 10px}} .gap p:last-child{{margin:0}}
  .secnum{{display:block;width:fit-content;font-family:"Inter",sans-serif;font-size:12px;
    letter-spacing:.14em;color:var(--accent-ink);background:transparent;border:1px solid var(--accent);
    font-weight:700;margin:0 0 12px;padding:5px 14px;border-radius:20px}}
  .thumb{{width:100%;border-radius:8px;border:1px solid var(--line);margin-bottom:14px;display:block}}
  .q.sm{{font-size:16px}}
  .fault{{margin-top:14px;padding:14px 16px;background:#F8EEEE;border:1px solid #E3CACA;border-radius:8px;
    font-size:14px;line-height:1.55}}
  .fault b{{color:var(--critical)}}
  .pricing{{background:#F8F3E7;border:1px solid #E6DAB9;border-radius:10px;padding:14px 18px;margin:18px 0;
    font-size:14px;line-height:1.5}}
  .pricing b{{color:#7A5A16}}
  .media{{background:var(--soft);border:1px solid #CBD9EC;border-radius:10px;padding:14px 18px;margin:0 0 20px;
    font-size:14px;line-height:1.5}}
  .voice{{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);
    border-radius:0 12px 12px 0;padding:36px 32px;margin:0;line-height:1.65;font-size:16px;
    box-shadow:0 1px 3px rgba(11,19,43,.08)}}
  @media(max-width:560px){{.voice{{padding:26px 18px}}}}
  .voice h4{{font-family:var(--serif);font-size:25px;font-weight:600;margin:0 0 14px;color:var(--accent-ink)}}
  .voice b{{color:var(--accent-ink)}}
  .voice.good{{border-left-color:var(--good)}}
  .voice.good h4{{color:var(--good)}}
  .voice p{{margin:0 0 12px}} .voice p:last-child{{margin:0}}
  .checks{{margin-top:14px;display:flex;flex-direction:column;gap:2px}}
  .checks .h{{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--muted);margin-bottom:8px}}
  .check{{font-size:14px;padding:6px 0;padding-left:26px;position:relative}}
  .check::before{{position:absolute;left:0;font-weight:700}}
  .check.ok{{color:var(--ink)}} .check.ok::before{{content:"✓";color:var(--good)}}
  .check.no{{color:var(--critical)}} .check.no::before{{content:"✗";color:var(--critical)}}
  .checks-foot{{margin-top:12px;padding-top:12px;border-top:1px solid var(--line);font-size:14px;
    line-height:1.55;color:var(--ink)}}
  .cta{{margin-top:32px;padding:40px 32px;background:var(--navy);color:var(--ivory);border-radius:16px;text-align:left}}
  @media(max-width:560px){{.cta{{padding:28px 20px}}}}
  .cta-h{{font-family:var(--serif);font-size:25px;font-weight:600;color:#fff;margin-bottom:16px;text-align:center}}
  .cta p{{max-width:60ch;margin:0 auto 16px;line-height:1.65;font-size:16px;color:var(--ivory)}}
  .cta ul{{max-width:60ch;margin:0 auto 16px;padding-left:24px;line-height:1.55;font-size:16px;color:var(--ivory)}}
  .cta li{{margin:5px 0}}
  .cta .hook{{max-width:60ch;margin:0 auto 24px;padding:18px 20px;border-radius:8px;
    background:rgba(166,38,38,.16);border:1px solid rgba(198,90,90,.55);
    font-size:17px;line-height:1.55;font-weight:600;color:#fff}}
  .cta .hook.good{{background:rgba(58,118,189,.16);border-color:rgba(127,169,221,.5)}}
  .cta .hook .sc{{color:#fff;font-size:19px;font-weight:700}}
  .cta .hook .hl{{color:#F0B9B4}}
  .cta .hook.good .hl{{color:var(--glow)}}
  .cta .hook .hl .sc{{color:inherit}}
  .cta .curi{{font-weight:600;color:#fff;font-size:17px}}
  .cta .btnwrap{{text-align:center;margin-top:8px}}
  .cta-btn{{display:inline-block;background:var(--gold);color:var(--navy);text-decoration:none;font-weight:700;
    padding:16px 32px;border-radius:6px;font-size:16px}}
  .cta-btn:hover{{background:var(--gold-h)}}
  .positioning{{margin-top:32px;padding:24px;background:var(--navy);color:var(--ivory);border-radius:16px;line-height:1.6;font-size:15px}}
  .positioning h4{{font-family:"Inter",sans-serif;font-size:20px;margin:0 0 10px;color:#fff}}
  .positioning b{{color:var(--glow)}}
  .steps{{margin-top:26px;padding:26px 26px;background:var(--surface);border:1px solid var(--line);
    border-radius:14px}}
  .steps-h{{font-family:var(--serif);font-size:25px;font-weight:600;margin-bottom:6px;color:var(--ink)}}
  .steps>p{{color:var(--muted);font-size:15px;margin:0 0 16px}}
  .steplist{{margin:0;padding:0;list-style:none;counter-reset:step}}
  .steplist li{{position:relative;padding:0 0 16px 46px;margin:0;line-height:1.55;font-size:16px}}
  .steplist li:before{{counter-increment:step;content:counter(step);position:absolute;left:0;top:0;
    width:30px;height:30px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;
    display:flex;align-items:center;justify-content:center;font-size:15px}}
  .steplist li b{{color:var(--accent-ink)}}
  .ben{{display:block;margin-top:6px;color:var(--accent-ink);font-weight:600;font-size:15px}}
  .ben:before{{content:"\\2192  ";font-weight:700}}
  .steps-foot{{margin:8px 0 20px;font-weight:600;color:var(--ink);font-size:15px}}
  .steps .cta-btn{{margin-top:0}}
  .taste{{background:var(--soft);border:1px solid #CBD9EC;border-left:4px solid var(--accent);
    border-radius:0 10px 10px 0;padding:24px;margin:24px 0}}
  .taste{{margin:0}}
  .taste .th{{font-family:var(--serif);font-weight:600;font-size:21px;color:var(--ink);margin-bottom:16px}}
  .taste .grid{{display:grid;grid-template-columns:118px 1fr;gap:12px 16px;align-items:center}}
  .taste .lbl{{font-size:12px;font-weight:700;color:var(--muted);line-height:1.3}}
  .taste .lbl.b{{color:var(--accent-ink)}}
  .taste .cw{{font-style:italic;color:var(--ink);font-size:16px}}
  .taste .bw{{background:#fff;border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:0 8px 8px 0;
    padding:9px 13px;font-weight:600;color:var(--ink);font-size:16px}}
  .taste .dvd{{grid-column:1/-1;height:1px;background:#C9D4E4;margin:2px 0}}
  .taste .kick{{margin-top:16px;font-weight:700;color:var(--accent-ink);font-size:16px}}
  .curi{{font-weight:600;color:var(--ink)}}
  .freegift{{margin-top:12px;font-size:14px;color:var(--muted)}}
  .report>.cta,.report>.steps,.report>.strength,.report>.pricing,.report>.media,.report>.scope,
  .report>.checklist{{margin-top:28px;margin-bottom:0}}
  .report>*:first-child{{margin-top:0}}
</style></head><body>
<div class="hero-band"><div class="wrap">
  <div class="hero">
    {mascot}
    <div class="hero-copy">
      <div class="eyebrow">{count} coaching websites read, and counting</div>
      <h1 class="serif">Coaches: in five seconds, does your website say &ldquo;I can fix your problem&rdquo;?</h1>
      <p class="sub"><b>That's all the time a cold buyer gives you.</b> If they don't see it, they leave, and you
      never even know they came. Paste your coaching website in and in about half a minute Angelo shows you what that
      cold buyer sees, why they stay or go, and how you score against <b>{count}</b> other coaching sites. More than 8 in 10
      get it wrong. (83%, for those who like it exact.)</p>
    </div>
  </div>
  <form method="get" action="/" id="auditform">
    <input type="text" name="first_name" id="firstnameinput" placeholder="Your first name" autocomplete="given-name" autofocus>
    <input type="text" name="last_name" id="lastnameinput" placeholder="Your last name" autocomplete="family-name">
    <input type="email" name="email" id="emailinput" placeholder="Your best email address" autocomplete="email">
    <input type="text" name="url" id="urlinput" placeholder="yourcoachingwebsite.com" value="{url_value}">
    <button type="submit">Show me what a cold buyer sees</button>
  </form>
  <!-- Angelo explains the plan: blank flipchart in the artwork, the words are real HTML
       overlaid on the pad (same pattern as the bubble and the signposts). -->
  <div class="plan2">
    <div class="plan-wrap">
      <img class="plan-img" src="/angelo_plan.png" alt="Angelo at his flipchart, explaining the two steps">
      <div class="plan-lbl">
        <div class="pl-h">Your homepage is a mirror.</div>
        <div class="pl-step"><span>1</span>Your report. Free, about half a minute.</div>
        <div class="pl-step"><span>2</span>What to do about it.</div>
      </div>
    </div>
    <p class="p2-cap">It shows how you <b>think</b> about your marketing, and Angelo reads it the way a cold buyer does.</p>
    <p class="p2-note">One thing before you start. This is not consultancy, coaching or mentoring, and we are
    not here to work on your mindset.</p>
    <p class="p2-note">You can leave with the report straight away, it will nail a few things down for you.
    And if you have 6 or 7 minutes more, there is a deeper dig waiting, into how to direct your marketing
    and put you on the right track.</p>
  </div>
  <div class="hint">This messaging X-ray normally costs £127, but your private results are entirely free. Angelo takes about half a minute to read your homepage exactly as a cold buyer would, then saves your dashboard link straight to your inbox.</div>
  <!--PROGRESS-->
</div></div>
<div id="result">{result}</div>
</body></html>"""

# The live-progress overlay. Kept as a PLAIN string (real braces) and injected into PAGE after .format(), so its
# CSS/JS braces don't collide with the template's format fields.
PROGRESS_UI = """
<style>
  #processing{display:none;margin:32px 0 0;padding:32px;border-radius:10px;
    background:var(--navy-card);border:1px solid var(--navy-line)}
  #processing.on{display:block}
  #processing .angelo-loader{display:block;width:150px;aspect-ratio:1;object-fit:cover;margin:0 auto 20px;
    border-radius:50%;border:2px solid var(--accent);box-shadow:0 0 0 5px rgba(58,118,189,.18)}
  #processing h3{font-family:"Inter",sans-serif;font-size:21px;margin:0 0 20px;color:var(--ivory);text-align:center}
  #processing ul{list-style:none;margin:0 0 18px;padding:0}
  #processing li{padding:11px 0;border-bottom:1px solid var(--navy-line);font-size:15px;line-height:1.5;color:var(--ivory)}
  #processing li b{color:#fff}
  #processing li:last-child{border-bottom:0}
  .ps-status{font-weight:700}
  .ps-done{color:var(--good-glow)}
  .ps-progress{color:var(--glow)}
  .ps-waiting{color:var(--ivory-dim)}
  #processing .p-note{font-size:13px;color:var(--ivory-dim);line-height:1.5;margin:0;font-style:italic}
</style>
<div id="processing">
  <img class="angelo-loader" src="/angelo_typing.png" alt="Angelo at work">
  <h3>Angelo is actively analyzing your homepage copy&hellip;</h3>
  <ul>
    <li><b>Step 1:</b> Calibrating secure pipeline data and initializing target network links&hellip; <span class="ps-status ps-done" id="ps1">[DONE]</span></li>
    <li><b>Step 2:</b> Launching Angelo&rsquo;s headless browser engine to lock down your above-the-fold hero matrix&hellip; <span class="ps-status ps-waiting" id="ps2">[WAITING]</span></li>
    <li><b>Step 3:</b> Activating semantic text extraction algorithms to isolate core phrasing&hellip; <span class="ps-status ps-waiting" id="ps3">[WAITING]</span></li>
    <li><b>Step 4:</b> Executing deep linguistic parsing arrays across target audience pain points&hellip; <span class="ps-status ps-waiting" id="ps4">[WAITING]</span></li>
    <li><b>Step 5:</b> Angelo is compiling toxic token and clich&eacute; density data profiles&hellip; <span class="ps-status ps-waiting" id="ps5">[WAITING]</span></li>
    <li><b>Step 6:</b> Formatting tactical copy adjustments and strategic alternative recommendations&hellip; <span class="ps-status ps-waiting" id="ps6">[WAITING]</span></li>
    <li><b>Step 7:</b> Binding persistent database files and generating secure endpoint parameters&hellip; <span class="ps-status ps-waiting" id="ps7">[WAITING]</span></li>
    <li><b>Step 8:</b> Angelo is finalizing your custom Marketing Intelligence File dashboard layout&hellip; <span class="ps-status ps-waiting" id="ps8">[WAITING]</span></li>
  </ul>
  <p class="p-note">This takes exactly 30 to 40 seconds. Do not close this window or hit refresh. Your personalized diagnostic dashboard will load automatically the moment processing concludes.</p>
</div>
<script>
document.addEventListener('DOMContentLoaded',function(){
  var form=document.getElementById('auditform');
  if(!form) return;
  var proc=document.getElementById('processing');
  var result=document.getElementById('result');
  var busy=false;

  function setStep(id,status){
    var el=document.getElementById(id);
    if(!el) return;
    el.textContent='['+status+']';
    el.className='ps-status '+(status==='DONE'?'ps-done':status==='IN PROGRESS'?'ps-progress':'ps-waiting');
  }

  function markAllDone(){
    for(var i=1;i<=8;i++) setStep('ps'+i,'DONE');
  }

  form.addEventListener('submit',function(e){
    var url=document.getElementById('urlinput').value.trim();
    var fn=document.getElementById('firstnameinput').value.trim();
    var ln=document.getElementById('lastnameinput').value.trim();
    var em=document.getElementById('emailinput').value.trim();
    if(!url) return;
    e.preventDefault();
    if(busy) return;
    busy=true;

    setStep('ps1','DONE');
    setStep('ps2','IN PROGRESS');
    for(var i=3;i<=8;i++) setStep('ps'+i,'WAITING');

    form.style.display='none';
    result.innerHTML='';
    proc.className='on';
    proc.scrollIntoView({behavior:'smooth',block:'center'});

    var t2=setTimeout(function(){setStep('ps2','DONE');setStep('ps3','IN PROGRESS');},6000);
    var t3=setTimeout(function(){setStep('ps3','DONE');setStep('ps4','IN PROGRESS');},13000);
    var t4=setTimeout(function(){setStep('ps4','DONE');setStep('ps5','IN PROGRESS');},20000);
    var t5=setTimeout(function(){setStep('ps5','DONE');setStep('ps6','IN PROGRESS');},25000);
    var t6=setTimeout(function(){setStep('ps6','DONE');setStep('ps7','IN PROGRESS');},29000);
    var t7=setTimeout(function(){setStep('ps7','DONE');setStep('ps8','IN PROGRESS');},33000);

    var qs='url='+encodeURIComponent(url);
    if(fn) qs+='&first_name='+encodeURIComponent(fn);
    if(ln) qs+='&last_name='+encodeURIComponent(ln);
    if(em) qs+='&email='+encodeURIComponent(em);

    var t0=Date.now();
    fetch('/audit?'+qs+'&_t='+Date.now(),{cache:'no-store'}).then(function(r){return r.text();}).then(function(html){
      clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
      clearTimeout(t5); clearTimeout(t6); clearTimeout(t7);
      markAllDone();
      setTimeout(function(){
        proc.className='';
        form.style.display='';
        result.innerHTML=html;
        var countEl=result.querySelector('[data-sites]');
        if(countEl){
          var nc=countEl.getAttribute('data-sites');
          var ey=document.querySelector('.eyebrow');
          if(ey) ey.textContent=nc+' coaching websites read, and counting';
          var bbs=document.querySelectorAll('.sub b');
          if(bbs.length>1) bbs[1].textContent=nc;
        }
        busy=false;
        result.scrollIntoView({behavior:'smooth',block:'start'});
      }, Math.max(0,500-(Date.now()-t0)));
    }).catch(function(){
      clearTimeout(t2); clearTimeout(t3); clearTimeout(t4);
      clearTimeout(t5); clearTimeout(t6); clearTimeout(t7);
      proc.className=''; form.style.display=''; busy=false;
      window.location.href='/?'+qs;
    });
  });
});
</script>
"""


def _push_mailerlite(email, first_name, last_name, hero_quote, generic_tokens_found, global_score, salespage_url=""):
    """Fire-and-forget MailerLite v3 subscriber upsert. Always runs in a daemon thread; never blocks the audit."""
    if not MAILERLITE_API_KEY or not email:
        return
    try:
        tokens_str = (", ".join(generic_tokens_found) if isinstance(generic_tokens_found, list)
                      else str(generic_tokens_found or ""))
        payload = _json.dumps({
            "email": email,
            "fields": {
                "name": first_name or "",
                "last_name": last_name or "",
                "current_headline": hero_quote or "",
                "failed_tokens": tokens_str,
                "global_score": str(global_score or ""),
                "salespage_url": salespage_url,
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://connect.mailerlite.com/api/subscribers",
            data=payload,
            headers={
                "Authorization": f"Bearer {MAILERLITE_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX):
            pass
    except Exception:
        pass   # never let a MailerLite failure touch the audit result


def sev_class(v):
    return "crit" if v < 3.5 else "warn" if v < 6 else "good"

# Bold the "we won't hand you a line to copy" line in the fallback headline critique (David's ask). Runs AFTER
# html.escape, and the phrase has no HTML-special characters, so a plain replace is safe.
_EMPH_PHRASES = [
    "We’re not going to hand you a line to copy, that would just be our guess",
]
def emph(escaped_html):
    for p in _EMPH_PHRASES:
        if p in escaped_html:
            escaped_html = escaped_html.replace(p, "<b>" + p + "</b>")
    return escaped_html

# Long AI-written blocks can run 7+ lines deep as one wall of text. David's readability rule: after
# ~4 lines there must be a gap. At our ~62ch measure, 4 lines ≈ 260 characters, so regroup whole
# sentences into <p> chunks under that budget. Words are untouched — only paragraph breaks added.
_SENT_RE = re.compile(r"(?<=[.!?])\s+")
def para_split(text, max_chars=260):
    text = (text or "").strip()
    if not text:
        return ""
    chunks, cur = [], ""
    for s in _SENT_RE.split(text):
        if cur and len(cur) + len(s) + 1 > max_chars:
            chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    return "".join(f"<p>{html.escape(c)}</p>" for c in chunks)

# What we check, plain, buyer-focused, so they know it's quick and what's coming.
# HARD RULE (David): this list must match the criteria the report actually details below —
# one item per DISPLAY_CRIT entry, in the same order. If the taxonomy changes, change this too.
CHECKLIST = [
    "Whether a stranger gets it <b>in five seconds</b>",          # clarity_5sec
    "Whether it's instantly clear <b>who you help</b>",           # specificity
    "Whether a visitor sees <b>their own problem</b> on the page",# symptom_resonance
    "Whether there's <b>proof</b> you can deliver",               # proof_cred
    "Whether your <b>offer</b> is clear",                         # offer_clarity
    "Whether there's <b>one obvious next step</b>",               # next_step
    "How easy it is to <b>take the first step</b>",               # friction
    "Whether saying yes feels <b>safe</b>",                       # shield
]

# Constructive verdicts, no harsh one-word labels
VERDICTS = {
    "strong": "Strong. Anyone who arrives gets it fast, and you're ahead of the field.",
    "decent": "Nearly there. A few clear fixes, and more of the people who do come would get in touch.",
    "weak": "Not working hard enough yet. When someone arrives on your page, they can't quickly tell it's for them, so they leave.",
    "poor": "Right now, when someone arrives on your page, they can't quickly tell that you're the one who can help them, so they don't get in touch.",
}


def overall_copy(clarity, tier, in_top_tier):
    """The three lines of the overall-score box — VERDICT, STANDING (den) and GAP — all derived from the SAME two
    facts so they can NEVER contradict each other: does the page read fast (the 5-second CLARITY score is the only
    thing that decides whether a stranger can tell who it's for), and how it ranks overall (tier / top-tier).
    ONE rule, obeyed by all three lines: if it reads fast we never say 'they can't tell it's for them'; if it doesn't
    we never say 'gets it fast'. Returns (verdict, den_line, gap_line). Pure + unit-tested across every combination."""
    reads_fast = clarity is not None and clarity >= 6
    if reads_fast:
        # A stranger CAN tell who this is for, fast. The only thing left to fix is turning that into action — never clarity.
        if tier == "strong":
            return (
                "Strong. A visitor gets who you help fast, and you're ahead of the field.",
                "You're in the top few coaching homepages we've read. The notes below are the final polish.",
                "<p>A visitor here gets it fast, and your page reads like the answer to a problem. That's rare. The "
                "notes below are where the last few clients are hiding.</p>")
        if tier == "decent":
            return (
                "Nearly there. A visitor gets who you help fast, so the gaps below are what stand between you and a "
                "page that turns readers into enquiries.",
                "You're ahead of most coaching homepages we've read. Close the gaps below and more of the people who "
                "land here get in touch.",
                "<p>A visitor gets who you help fast, which most coaching pages never manage. What's left is turning "
                "that recognition into action, and the notes below show where it leaks, usually the proof a stranger "
                "can check, or no way to catch the ones who aren't ready to book yet.</p>")
        # Reads fast, but weak/poor overall: the message LANDS, yet real gaps (thin proof, no opt-in, hazy offer) cost
        # clients. We say exactly that — never 'they can't tell it's for them', which would contradict the clear score.
        return (
            "A visitor can tell who you help, and quickly, so that part works. What's costing you clients sits below: "
            "real gaps a cold buyer trips on before they act.",
            "You read more clearly than most coaching homepages. But clear isn't the same as convincing, and the gaps "
            "below are where the clients slip away.",
            "<p>Your page does the hard part, a stranger gets who it's for. But getting it and acting on it are two "
            "different things. Without strong proof they can check, and without a way to catch the ones who aren't "
            "ready to book yet, they read, nod, and leave.</p>"
            "<p>The notes below are exactly where that happens, and what to do about it.</p>")
    if in_top_tier:
        # Doesn't read fast, yet ranks top-tier (a strong booking / CTA / story propping up a weak headline). Ahead of
        # most, but the 5-second test still fails — so we say THAT, and never 'gets it fast'.
        return (
            "You're ahead of most coaching pages, but the first thing a stranger sees still doesn't tell them who it's "
            "for in five seconds, so people leave before they reach the good stuff.",
            "You're in the top few coaching homepages we've read. But that's a low bar, most are poor, and top few "
            "still isn't landing in five seconds. Your headline doesn't yet. That's what the notes below are for.",
            "<p>Here's the honest bit. You're already ahead of most coaching pages, and plenty on here works. But the "
            "first thing a stranger sees, your headline, doesn't tell them in five seconds who it's for or what you "
            "fix. So even here, people leave before they reach the good stuff.</p>"
            "<p>Ahead of most isn't the same as landing. Getting a stranger to think &lsquo;that's me&rsquo; in "
            "seconds isn't a headline you polish on your own. It's knowing their real problem in their own words, and "
            "that's the part you can't see from the inside.</p>")
    # Doesn't read fast, and behind the field: the 5-second test failing IS the headline problem. The verdict MUST be a
    # clarity-fail line here (never VERDICTS['strong']/['decent'], which claim 'gets it fast') — a not-fast page can
    # never say it reads fast, whatever the tier nominally is.
    return (
        VERDICTS["poor"] if tier == "poor" else VERDICTS["weak"],
        "Only about 1 in 10 coaching homepages score 6 or more. That's the difference between a page people scroll "
        "past and one that gets you enquiries and paying clients.",
        "<p>The best coaching homepages make a visitor think &lsquo;that's exactly my problem, and they can fix "
        "it&rsquo; within seconds. Yours doesn't yet, so a potential client looks, doesn't see themselves in it, and "
        "leaves to find someone who does.</p>"
        "<p>And getting a stranger to feel that isn't a headline you can polish on your own. It's knowing their real "
        "problem in their own words, and that's the part you can't see from the inside.</p>")

# The list above reads like a to-do. This stops a coach thinking the checklist IS the cure. It isn't:
# every one of those fixes needs their buyer's real words, and that's the part you can't guess.
FIXES_CAVEAT = (
    '<div class="caveat"><p><b>But here\'s the catch. You probably feel sure you already know your client.</b> Maybe '
    'you do. But feeling sure and being right aren\'t the same thing, and you can\'t build a business on a hunch, '
    'even one you feel certain about.</p>'
    '<p>The words that make a stranger act are <b>their</b> words, not the ones you\'d reach for, and you can\'t '
    'pull those from your own head. Even done well, this was never a wording tweak. It\'s finding what your market '
    'actually buys, and why. That\'s the hard part. That\'s the part we do.</p></div>'
)


def render_result(res, first_name=""):
    if not res.get("ok"):
        return f'<div class="card"><p class="err">{html.escape(res.get("error",""))}</p></div>'
    if res.get("status") == "dead":
        return (f'<div class="card"><p class="dead">We couldn\'t load '
                f'<b>{html.escape(res["domain"])}</b> at all.</p><p>{html.escape(res["message"])}</p></div>')
    if res.get("status") == "blocked":
        shot = (f'<img src="{res["thumbnail"]}" alt="security check screenshot" '
                f'style="max-width:100%;border:1px solid #ddd;border-radius:8px;margin-top:12px">'
                if res.get("thumbnail") else "")
        return (f'<div class="card"><p class="dead">We couldn\'t read '
                f'<b>{html.escape(res.get("page_display") or res["domain"])}</b>.</p>'
                f'<p>{html.escape(res["message"])}</p>{shot}</div>')
    if res.get("status") == "not_coaching":
        shot = (f'<img src="{res["thumbnail"]}" alt="page screenshot" '
                f'style="max-width:100%;border:1px solid #ddd;border-radius:8px;margin-top:12px">'
                if res.get("thumbnail") else "")
        return (f'<div class="card"><p class="dead">'
                f'<b>{html.escape(res.get("page_display") or res["domain"])}</b> '
                f'doesn\'t look like a coaching or therapy website.</p>'
                f'<p>{html.escape(res["message"])}</p>{shot}</div>')
    if res.get("status") == "policy_page":
        shot = (f'<img src="{res["thumbnail"]}" alt="page screenshot" '
                f'style="max-width:100%;border:1px solid #ddd;border-radius:8px;margin-top:12px">'
                if res.get("thumbnail") else "")
        return (f'<div class="card"><p class="dead">We landed on a cookie or privacy page for '
                f'<b>{html.escape(res.get("page_display") or res["domain"])}</b>, not the real homepage.</p>'
                f'<p>{html.escape(res["message"])}</p>{shot}</div>')

    # Overall verdict colour aligned with Angelo's thumbs (David): green only at 7+, so a 6.5 never
    # shows a green number next to an unsure Angelo. Per-criterion chips/bars keep sev_class bands.
    try:
        _sd = float(res.get("score_10_display", res["score_10"]) or 0)
    except (TypeError, ValueError):
        _sd = float(res["score_10"])
    g = "crit" if _sd < 3.5 else "warn" if _sd < 7 else "good"
    ev = res["evidence"]
    cnt = f'{res.get("corpus_count", 10954):,}'   # the living count of coaching websites read
    # RULEBOOK §0: never claim "homepage" when a subpage was audited. Every personal claim below
    # that names their page uses this word, so it's right for both cases.
    _page_word = "homepage" if res.get("is_home", True) else "page"
    # The "who's really buying" step needs a vague-avatar example to push against. Pin it to THEIR OWN niche so a
    # leadership coach never reads a divorce-coach example and thinks "that's not me". Neutral fallback if unknown.
    _niche = ev.get("niche")
    # Raw niche words like "life" don't work as an adjective for "clients" ("life clients" is nonsense), so say
    # "life coaching clients", "leadership coaching clients", etc. Reads right for every niche.
    _niche_clients = f'{html.escape(_niche)} coaching clients' if _niche else 'clients'
    avatar_eg = (f'the vague avatar every coach gets handed, like &ldquo;{_niche_clients}, 35 to 55, '
                 f'who want to grow&rdquo;' if _niche else 'the vague avatar every coach gets handed')
    # Tie the file to the EXACT hole this page has: their weakest message score + their niche. Turns the CTA from
    # a generic upsell into "here's the fix for the specific wound we just showed you".
    # DAVID'S HOOK RULE: praise is earned, not defaulted. The candidates below are the criteria a Marketing
    # Intelligence File genuinely fixes. If ANY of them sits at 5/10 or under, the hook must name the weakest
    # one — never compliment Mind Reading while the page has a real message hole. The positive Mind-Reading
    # hook only shows when every candidate is 6+, i.e. there is truly nothing weak to point at.
    _HOLE = {"specificity": "who it's for", "clarity_5sec": "a stranger getting it in five seconds",
             "offer_clarity": "showing what you actually fix",
             "symptom_resonance": "describing the problem in your buyer's own words"}
    _sc = res.get("scores", {})
    _weak = min(_HOLE, key=lambda k: _sc.get(k, 99))
    hole_phrase, hole_score = _HOLE[_weak], _sc.get(_weak, 0)
    _mr_score = _sc.get("symptom_resonance", 0)
    niche_word = f'{_niche_clients} '   # "life coaching clients " / "clients " — used as "the real words your {…}use"
    steps_btn = (f'Show me how it works for {html.escape(_niche)} coaches &rarr;' if _niche
                 else 'Show me how it&rsquo;d work for me &rarr;')
    # Carry the coach's identity into the offer page. The domain is the DB key to everything we saved
    # (name, score, tokens, screenshot), so as long as it rides in the URL, every page downstream can
    # look the full record up — no other parameters needed.
    _offer_href = ("/offer?domain=" + _url_quote(res.get("domain", ""), safe="")
                   if res.get("domain") else "/offer")

    # scope: make it unmistakable we looked at the homepage only, + date
    scope = (f'<div class="scope">{html.escape(res["scope_note"])} '
             f'<span class="date">Analysed {html.escape(res["analysed_on"])}.</span></div>')

    # Verdict, standing and gap all come from ONE function driven by the same two facts (clarity + tier/top-tier), so
    # they can never disagree — see overall_copy(). Unit-tested across every (clarity, tier, top-tier) combination.
    _clar = (res["comparison"].get("clarity_5sec") or {}).get("you")
    verdict, den_line, gap_line = overall_copy(_clar, res.get("tier"), res.get("in_top_tier"))

    # Thumbnail: Playwright base64 or the /screenshots/ microlink path — whichever the /audit handler filled.
    # When BOTH failed, show Angelo instead of dead white space, so the layout never has an unexplained hole.
    thumb = (f'<img class="thumb" src="{res["thumbnail"]}" alt="Your homepage">' if res.get("thumbnail")
             else '<div class="thumb" style="display:flex;flex-direction:column;align-items:center;'
                  'justify-content:center;padding:26px 0;background:var(--surface);border:1px solid var(--line);'
                  'border-radius:10px"><img src="/angelo.png" alt="Angelo" '
                  'style="width:64px;height:auto;opacity:.55;margin-bottom:10px">'
                  '<div style="font-size:13px;color:var(--muted)">Screenshot unavailable — the words below are what count.</div></div>')

    # Headline block. Two things matter here, for different reasons: the biggest words a visitor reads
    # first (what we analyse), and the <h1> tag Google reads first (an SEO finding when they're not the same).
    quotes = ""
    if ev["headline"]:
        quotes += ('<div class="meta">This is the biggest text on your page, so it\'s the first thing a stranger\'s '
                   'eye goes to. We\'re taking it as your main headline:</div>')
        quotes += f'<div class="q">{html.escape(ev["headline"])}</div>'
        quotes += ('<div class="meta">Read it the way a stranger would, someone who\'s never heard of you. '
                   'Does it tell them <b>who you help</b>? Does it tell them <b>what changes for them</b>? '
                   'That\'s all a headline has to do.</div>')
    if ev.get("headline_differs_from_h1") and ev.get("h1_tag"):
        quotes += ('<div class="meta" style="margin-top:14px">There\'s a second headline on your page. People don\'t '
                   'see it, but Google does. It\'s called the <b>H1 tag</b>. On your page it isn\'t that big line. '
                   'It\'s this:</div>')
        quotes += f'<div class="q sm">{html.escape(ev["h1_tag"])}</div>'
        quotes += ('<div class="meta">So you\'ve got two headlines doing two jobs. The big one, the one a human reads '
                   'first, has to grab a stranger in a second. The H1 tag is what Google leans on to work out what '
                   'you do. Worth a look: does yours describe the problem people are searching for, or is it a '
                   'slogan or a brand line?</div>')
    elif not ev.get("h1_tag"):
        quotes += ('<div class="meta" style="margin-top:14px">There\'s a second headline Google reads first, called '
                   'the <b>H1 tag</b>. We couldn\'t find one on your page. That\'s worth fixing on its own.</div>')
    if ev["subheadings"]:
        subs = "".join(f'<div class="q sm">{html.escape(s)}</div>' for s in ev["subheadings"][:4])
        quotes += f'<div class="meta" style="margin-top:12px">The section headings we found on the page:</div>{subs}'
    # Always prompt them to read their own headings back — as a question, framed around the MARKET, not a verdict.
    if ev["subheadings"]:
        quotes += ('<div class="fault">Read those headings back like a stranger would. Do they name your buyer\'s '
                   '<b>problem</b>? Do they name how you fix it? Now the big one: is that how your <b>market</b> sees '
                   'it too, in their words? And is it something they\'ll pay to fix? It can all make sense to you '
                   'but not to them.</div>')

    evidence_html = (
        f'<div class="ev"><div class="ev-head"><div class="h"><span class="secnum">1 / 5</span>What we read on your {_page_word}: {html.escape(ev.get("page_display") or ev["domain"])}</div>'
        f'<img class="sec-angelo" src="/angelo_reading.png" alt="Angelo reading your page"></div>'
        f'{thumb}{quotes}</div>'
    )

    # --- the signature finding: whose words are these? (never a verdict on whether it sells) ---
    v = res.get("voice", {})
    coach_terms = ", ".join(f"&lsquo;{html.escape(t)}&rsquo;" for t in v.get("coach_terms", [])) or "coach language"
    first_coach = html.escape(v.get("coach_terms", ["clarity"])[0]) if v.get("coach_terms") else "clarity"
    if v.get("leaning") == "expert":
        voice_html = (
            '<div class="voice"><h4><span class="secnum">4 / 5</span>Whose words are these? Yours, or your buyer\'s?</h4>'
            f'<p>On your {_page_word} you reach for coach words like {coach_terms}. They\'re good words. But they\'re '
            '<b>your</b> words, not your customer\'s.</p>'
            '<p>Right now you\'re talking expert to expert. Another coach would read this and understand you easily. '
            'But your buyer isn\'t another expert. <b>They still have the problem.</b> They need you to talk '
            '<b>expert to buyer</b>.</p>'
            f'<p>Picture the person you help, lying awake at night, worried. <b>What do they type into Google?</b> Probably '
            f'not &lsquo;{first_coach}&rsquo;. More likely something real. A career coach\'s buyer might type '
            '<span class="qchip">&ldquo;I keep getting passed over at work&rdquo;</span>. A health coach\'s buyer might type '
            '<span class="qchip">&ldquo;why am I tired all the time&rdquo;</span>. '
            'Your buyer has their own version, in their own words.</p>'
            '<p>You talk like the expert who fixed the problem. They talk like someone who still has it. Those are two '
            'different languages.</p>'
            f'<p class="statpane">And hardly any coaches get this right. We looked at <b>{cnt}</b> coaching websites. Only about '
            f'<b>1 in {BUYER_VOICE_1_IN}</b> use their customer\'s words. The other <b>{PCT_NOT_BUYER_VOICE}%</b> sound just like this page does.</p>'
            '<p>That\'s good news for you. Nearly every coach sounds the same, so people can\'t tell them apart. Use '
            'the words your customers actually use, and <b>you stand out straight away</b>. You become <b>the coach who '
            'understands them</b>.</p>'
            '<p>And there\'s a bigger catch. Maybe you had this problem yourself once, and got through it. Maybe '
            'you\'ve helped a few people do the same. That feels like proof. But it\'s just a handful of people. It '
            'doesn\'t tell you there are <b>enough others out there who\'ll pay for exactly this</b>, said in exactly these '
            'words.</p>'
            '<p>And when your whole page is built on your own story and your own view, the people you want to reach '
            'don\'t feel understood. They don\'t feel you get them, so they move on to another coach, one who feels '
            'like they understand them better.</p>'
            '<p>You can\'t see your own blind spot, and you can\'t guess what your customers are really thinking. '
            'Finding it takes real digging into who is buying, and why. It isn\'t a five-minute rewrite. It isn\'t a '
            'weekend job either. <b>The words you need aren\'t in your own head to find.</b></p></div>')
    elif v.get("leaning") == "customer":
        voice_html = (
            '<div class="voice good"><h4><span class="secnum">4 / 5</span>You\'re speaking your buyer\'s language</h4>'
            f'<p>Here\'s something you\'re doing well. Your {_page_word} talks about the problem in words your customer '
            'would actually use, not just coach words.</p>'
            f'<p>That\'s rarer than you\'d think. Of the {cnt} coaching sites we scored, only about 1 in {BUYER_VOICE_1_IN} do this. The '
            f'other {PCT_NOT_BUYER_VOICE}% talk like the expert. You sound more like the person with the problem, and <b>that\'s a real edge</b>. '
            'Keep using the real words your clients say.</p></div>')
    else:
        voice_html = (
            '<div class="voice"><h4><span class="secnum">4 / 5</span>Whose words are these? Yours, or your buyer\'s?</h4>'
            f'<p>Your {_page_word} mixes your words with your customer\'s words.</p>'
            '<p>The closer you get to how your customer really talks, the words they\'d use for their own problem, the '
            'more of them will get in touch instead of just nodding and leaving.</p>'
            '<p>And that\'s harder than it sounds. You know your work so well that you\'ve forgotten how your customer '
            'talks about it. <b>Finding their real words takes proper digging, not a quick rewrite.</b></p></div>')

    strength_html = (f'<div class="strength">✓ <b>What you\'re doing right:</b> {html.escape(res["strength"])}</div>'
                     if res.get("strength") else "")

    pricing_html = (f'<div class="pricing">💷 <b>A note on pricing.</b> {html.escape(res["pricing_note"])}</div>'
                    if res.get("pricing_note") else "")

    rows = []
    # Render in the grouped, readable DISPLAY_CRIT order (opt-in -> focus -> booking sit together), not worst-first.
    for k in DISPLAY_CRIT:
        c = res["comparison"].get(k)
        if not c:
            continue
        info = res["notes"].get(k, {"pass": None, "note": ""})
        _def = html.escape(DEFINITIONS.get(k, ""))
        if c["you"] is None:                     # N/A: no bar, no red cross, an honest 'N/A'
            rows.append(
                f'<div class="barwrap"><div class="barhead">'
                f'<div class="lbl"><span class="mark na"></span>{html.escape(LABELS[k])}</div>'
                f'<div class="vs" style="color:var(--muted);font-size:14px">N/A</div></div>'
                f'<div class="def">{_def}</div>'
                f'<div class="barnote">{para_split(info["note"])}</div></div>'
            )
            continue
        pct = c["you"] * 10
        mark = "ok" if info["pass"] else "no"
        # technical_health is shown but NOT part of the overall score, so it shows 'not counted', not a market gap.
        _mkt = 'not counted' if k == "technical_health" else f'market {c["market"]}'
        rows.append(
            f'<div class="barwrap"><div class="barhead">'
            f'<div class="lbl"><span class="mark {mark}"></span>{html.escape(LABELS[k])}</div>'
            f'<div class="vs"><span class="chip {sev_class(c["you"])}">{c["you"]}<span class="den">/10</span></span>'
            f'<span class="mkt">{_mkt}</span></div></div>'
            f'<div class="track"><div class="fill {sev_class(c["you"])}" style="width:{pct}%"></div></div>'
            f'<div class="def">{_def}</div>'
            f'<div class="barnote">{para_split(info["note"])}</div></div>'
        )
    cr = res["critique"]
    fixes = "".join(f"<li>{para_split(f)}</li>" for f in cr["top_fixes"])
    ai = ('<span class="badge">AI diagnosis</span>' if res["ai_powered"]
          else '<span class="badge">add API key for AI</span>')
    # Greet the coach by name when the form gave us one. Falls back cleanly to the old opener.
    _greet = f'{html.escape(first_name.strip())}, we' if first_name.strip() else 'We'
    # Beckoning Angelo: the bubble in the artwork is blank; the words are HTML overlaid on it, so
    # each placement speaks its own personalised line (clean fallback when we have no name).
    _fn = html.escape(first_name.strip()) if first_name.strip() else ""
    # Personalised gold button in the pitch block (David): Angelo-voice, coach's name in the label.
    _mid_btn = (f'{_fn}, let me show you what a buyer actually wants &rarr;' if _fn
                else 'Let me show you what a buyer actually wants &rarr;')
    _bub_end = (f'Come on, {_fn}. Let me show you.' if _fn else 'Come on. Let me show you.')
    def _angelo_speaks(text, href):
        return (f'<a class="cta-angelo-wrap" href="{href}">'
                f'<img class="cta-angelo" src="/angelo_cta.png" alt="Angelo: {text}">'
                f'<span class="bubble-txt">{text}</span></a>')
    opener = (f'<div class="analysed"><p>{_greet} can tell in a few seconds what a cold buyer thinks when they arrive on your '
              f'page. We\'ve watched it go right and wrong on thousands of coaching sites.</p>'
              f'<p>We looked at '
              f'<b>{html.escape(ev.get("page_display") or ev["domain"])}</b>, scored it against all <b>{cnt}</b> of '
              f'them, and the screenshot below is your real page, not a template. Here\'s what we found.</p></div>')
    media = (f'<div class="media">🎬 {html.escape(res["media_note"])}</div>' if res.get("media_note") else "")
    popup = (f'<div class="media">🚫 {html.escape(res["popup_note"])}</div>' if res.get("popup_note") else "")
    reframe = ('<div class="reframe"><p>You\'ve probably had a website audit before. This isn\'t that. '
               'This isn\'t about how good your website <i>looks</i>. Forget the design for a minute.</p>'
               '<p>A stranger arrives on your page. In a few seconds they decide one thing about you: '
               '<b>&ldquo;can this person fix my problem?&rdquo;</b> If the answer isn\'t a clear yes, they leave. '
               'And you never even knew they were there.</p>'
               f'<p>We read {cnt} coaching homepages, and <b>{PCT_FAIL_5SEC}% fail that '
               'test.</b> The checks below show what\'s going wrong. The real reason is simpler: '
               '<b>the words on your page aren\'t the words your buyer uses in their own head.</b></p></div>')
    checklist_html = (
        '<div class="checklist"><div class="h">What we have looked at (detailed below)</div><ul>'
        + "".join(f"<li>{c}</li>" for c in CHECKLIST)
        + '</ul><div class="foot">Read on for what we found, your <b>overall score is at the very bottom.</b></div></div>'
    )

    # Angelo's verdict image (David's rule): under 5 = thumbs down, 5-6 = unsure, 7+ = thumbs up.
    _verdict_img = ("angelo_down.png" if _sd < 5 else "angelo_unsure.png" if _sd < 7 else "angelo_up.png")
    score_reveal = (
        f'<div class="reveal {g}"><div class="h"><span class="secnum">5 / 5</span>Your overall score</div>'
        '<div class="grade">'
        f'<div class="num {g}">{res.get("score_10_display", res["score_10"])}<span class="den">/10</span></div>'
        f'<div><div class="verdict">{verdict}</div>'
        f'<div class="den">{den_line}</div></div>'
        f'<img class="verdict-img" src="/{_verdict_img}" alt="Angelo&rsquo;s verdict">'
        '</div>'
        f'<div class="gap" style="margin-top:14px">{gap_line}</div>'
        f'<div class="honest">A word on your {res.get("score_10_display", res["score_10"])}/10. We\'re not marking you down to make a sale. Every '
        'homepage gets scored the same way, against the same cold buyers, and we call it exactly as we see it. A low '
        'number isn\'t us being harsh on you. It just shows how far the page is from where your buyers already are. '
        'What you do about it is up to you.</div></div>'
    )

    if hole_score > 5:
        hook_html = (
            f'<div class="hook good"><span class="hl">Your {_page_word} scored a strong <span class="sc">{_mr_score}/10</span> on Mind Reading.</span> '
            f'This means your instincts are lightyears ahead of the market average. However, maintaining that accuracy '
            f'across all your outbound copy, emails, and ads without a continuous stream of hard consumer data is '
            f'exhausting. The Marketing Intelligence File scales what you are already doing right, for the '
            f'{niche_word}you want more of.</div>'
        )
    else:
        hook_html = (
            f'<div class="hook"><span class="hl">Your {_page_word} scored <span class="sc">{hole_score}/10</span> on {hole_phrase},</span> not '
            f'because you don&rsquo;t know your clients, but because it&rsquo;s written in your words, not the words '
            f'a cold buyer uses in their own head. Getting those exact words, the ones your {niche_word}really use, '
            f'is the whole game.</div>'
        )

    return f"""<div class="report" data-sites="{cnt}">
      <div class="sec">
      {opener}
      {reframe}
      {checklist_html}
      </div>
      {scope}
      {media}
      {popup}
      {evidence_html}
      <div class="sec">
      <div class="scores-h"><span class="secnum">2 / 5</span>Here are your scores, with the reason behind each one. A green tick means it's working for you. A red cross means it's costing you clients.</div>
      <div>{''.join(rows)}</div>
      </div>
      <div class="diag">
        <h3><span class="secnum">3 / 5</span>What a visitor sees{ai}</h3>
        <div class="row"><div class="k">The biggest thing in the way</div>{emph(para_split(cr['headline_problem']))}</div>
        <div class="row"><div class="k">What it's costing you</div>{para_split(cr['why_it_costs_clients'])}</div>
        <div class="row"><div class="k">The obvious fixes</div><ol class="fixlist">{fixes}</ol>{FIXES_CAVEAT}</div>
        <div class="row"><div class="k">Bottom line</div><div class="verdict-note">{para_split(cr['money_left_on_table'])}</div></div>
      </div>
      {strength_html}
      {pricing_html}
      {voice_html}
      {score_reveal}
      <div class="taste">
        <div class="th">Here's the whole game, in two examples from the coaching world:</div>
        <div class="grid">
          <div class="lbl">Career coach</div>
          <div class="cw">&ldquo;I help professionals reach their full potential and find alignment.&rdquo;</div>
          <div class="lbl b">Her buyer, 11pm</div>
          <div class="bw">&ldquo;how do I quit my job without throwing away my salary.&rdquo;</div>
          <div class="dvd"></div>
          <div class="lbl">Health coach</div>
          <div class="cw">&ldquo;I help you become the healthiest, happiest version of yourself.&rdquo;</div>
          <div class="lbl b">Her buyer, 6am</div>
          <div class="bw">&ldquo;why do I start every diet on Monday and quit by Friday.&rdquo;</div>
        </div>
        <div class="kick">Same person, two languages. Whatever you coach, the one who writes the second line gets the call.</div>
      </div>
      <div class="cta">
        <div class="cta-h">So what do your buyers actually want?</div>
        {hook_html}
        <p>You've probably worked hard on this already. Rewritten the page, paid a designer, done the course, maybe
        hired a coach. And you know your clients, you've coached plenty of them.</p>
        <p>But your {_page_word} has to win over the people who aren't your clients yet. Cold strangers, deciding in five
        seconds, who've never heard of you. What's in their head before they meet you is the hard part, and no one
        sees the whole market from inside their own business.</p>
        <p>So here's what we make you: a <b>Marketing Intelligence File</b>. In plain English, it's everything we can
        find out about the person you're really selling to, pulled from thousands of real buyers, not just the handful
        you've worked with:</p>
        <img class="mi-img" src="/angelo_file.png" alt="Angelo with your Marketing Intelligence File">
        <ul>
          <li>the exact words your {niche_word}use for their problem</li>
          <li>the fears that hold them back</li>
          <li>the desires that make them pick up the phone</li>
          <li>what they'll pay to fix, and what they won't</li>
        </ul>
        <p>This isn't a rewrite of your website, and it isn't about swapping a few words. It's the understanding
        underneath them. Because right now, a potential client arrives on your page, feels nothing, and leaves for a
        coach whose words happen to fit. That won't change on its own.</p>
        <p>It isn't for everyone. If you already know the whole market better than they know themselves, you don't
        need it. If you want that edge, this is where it comes from.</p>
        <p class="curi">There's one thing your buyer wants that you've never put into words. It's the reason they pick
        one coach over another.</p>
        <div class="btnwrap"><a class="cta-btn" href="{_offer_href}">{_mid_btn}</a></div>
      </div>
      <div class="steps">
        <div class="steps-h">So how do you fix it?</div>
        <p>You have seen the problem. Here is the way out, step by step.</p>
        <ol class="steplist">
          <li><b>We find out what makes people want to invest in you.</b> Not {avatar_eg}. We find the real person and the exact burning problem
          they will pull out their wallet to fix. We go deep into your market: how they talk about the problem,
          how they buy, when they buy, and what finally makes them pay.
          <span class="ben">So you are talking to the people who actually buy, not a vague avatar.</span></li>
          <li><b>We uncover how your market lives and buys.</b> We do not estimate. Our research maps out exactly
          how your target audience describes their day, what empty promises they are tired of hearing, and the exact
          language that causes them to click &lsquo;buy.&rsquo;
          <span class="ben">So your marketing says what they are already thinking, and they feel understood.</span></li>
          <li><b>You get it all in your Marketing Intelligence File.</b> This is the exact data map you have been
          missing. No more staring at a blank page wondering what to write. Your website, your posts, and your
          emails will finally say exactly what your buyer is already thinking.
          <span class="ben">So everything you put out pulls the same way, not a different message in every place.</span></li>
        </ol>
        <p class="steps-foot">When your marketing sounds like your buyer, more of the right people get in touch, and more of them buy. More clients, the right ones, and the growth to reach your next level.</p>
        <a class="cta-btn" href="{_offer_href}">{steps_btn}</a>
        {_angelo_speaks(_bub_end, _offer_href)}
      </div>
    </div>"""


# ============================================================================
#  THE OFFER PAGE  (/offer), separate, trackable landing page for retargeting.
#  DRAFT COPY, David to refine. Payment/checkout not wired yet.
#  <<< Meta Pixel / Google tag goes in the <head> here once you have the IDs. >>>
# ============================================================================
OFFER_PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Marketing Intelligence File</title>
<!-- RETARGETING: paste your Meta Pixel and/or Google tag here. A visit to /offer = a warm audience. -->
<style>
  @font-face{font-family:'Inter';font-weight:100 900;font-display:swap;src:url(/inter.woff2) format('woff2')}
  :root{--paper:#eef1f5;--surface:#fff;--ink:#17222e;--muted:#5c6a67;--line:#dde3e0;--accent:#3a76bd;
    --accent-ink:#234e83;--soft:#e6edf8;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);
    font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6}
  .wrap{max-width:720px;margin:0 auto;padding:44px 22px 80px}
  .eyebrow{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.16em;text-transform:uppercase;
    color:var(--accent-ink);font-weight:600}
  h1{font-family:"Inter",sans-serif;font-weight:600;font-size:clamp(30px,6vw,46px);line-height:1.08;
    letter-spacing:-.015em;margin:.3em 0 .3em;text-wrap:balance}
  .lede{font-size:19px;color:var(--muted);margin:0 0 30px}
  h2{font-family:"Inter",sans-serif;font-size:clamp(22px,4vw,28px);margin:38px 0 12px}
  p{margin:0 0 16px}
  .card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:24px 26px;margin:22px 0;
    box-shadow:0 8px 30px rgba(20,40,36,.06)}
  ul{margin:8px 0 0;padding-left:22px}
  li{margin:9px 0}
  li b{color:var(--accent-ink)}
  .built li{margin:12px 0}
  .cta{margin-top:34px;padding:30px 26px;background:var(--ink);color:#eef1f5;border-radius:16px;text-align:center}
  .cta h2{color:#fff;margin-top:0}
  .cta p{max-width:48ch;margin:0 auto 20px;color:#dfe7e4;font-size:15px}
  .btn{display:inline-block;background:#e0691f;color:#fff;text-decoration:none;font-weight:600;
    padding:16px 30px;border-radius:9px;font-size:17px}
  .btn:hover{background:#c65a15}
  .note{font-size:12.5px;color:var(--muted);margin-top:14px}
  .back{display:inline-block;margin-bottom:24px;color:var(--accent-ink);text-decoration:none;font-size:14px}
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
    --paper:#0e1614;--surface:#16211e;--ink:#e9efec;--muted:#93a29d;--line:#243430;--soft:#16302b;
    --accent:#6ba6e0;--accent-ink:#9ec6f0;}}
</style></head><body data-domain="__DOMAIN__"><div class="wrap">
  <a class="back" href="/">&larr; Back to your free audit</a>
  <div class="eyebrow">The Marketing Intelligence File</div>
  <h1>Your buyers are already telling you exactly what to say. You just can't hear it yet.</h1>
  <p class="lede">A deep-research file on the exact people you help, their real problem, the words they use,
  and what makes them buy, so your marketing finally speaks their language instead of yours.</p>

  <div class="card">
    <h2 style="margin-top:0">Why you can't just do this yourself</h2>
    <p>You know your work too well. You describe it like the expert who <i>solved</i> the problem, not the person
    still living it. That's why your marketing sounds right to you, and to other coaches, but slides straight past the
    people you're trying to reach. And you probably feel sure you've got your buyer figured out. Feeling sure and
    being right aren't the same thing. You have to hear your buyer in their own words, and that takes research,
    not a rewrite.</p>
  </div>

  <h2>What's actually in it</h2>
  <ul>
    <li><b>Who your buyer really is</b>, well past "women, 35&ndash;50".</li>
    <li><b>The exact words and phrases</b> they use for their problem, so you can use them back.</li>
    <li><b>The real problem behind the problem</b>, the thing they'll actually pay to fix.</li>
    <li><b>The triggers and fears</b> that turn a browser into a booking.</li>
    <li><b>Ready-to-use language</b> for your website, lead magnets, emails and social, all built around your
    buyer, not your theory.</li>
  </ul>

  <h2>Why it's not guesswork</h2>
  <p>We don't use templates and we don't guess. Your file is built from three things almost nobody has together:</p>
  <ul class="built">
    <li><b>Your answers</b>, the deep detail you give us about your work and your clients.</li>
    <li><b>Our analysis of 10,000+ real coaching websites</b>, what works, what's ignored, and where your
    competitors leave the door wide open.</li>
    <li><b>2,000 books people bought to fix their own problems.</b> Every book that sells is a vote. It shows what
    people struggle with, and why they'll pay to fix it. We've studied why each one works, and mapped it to your
    niche.</li>
  </ul>

  <div class="cta">
    <h2>Become the coach who "just gets it"</h2>
    <p>When your buyer reads their own words on your page, they stop asking about price. You become the obvious
    choice.</p>
    <p style="color:#cdd8d4;font-size:14px">We build every file by hand, so we only take a few on each month. And
    it's not for everyone. It's for the coach who's ready to hear what their buyer really thinks, even the bits
    that sting.</p>
    <a class="btn" href="#">Get my Marketing Intelligence File</a>
    <div class="note">[Draft page &middot; pricing &amp; secure checkout to be added]</div>
  </div>
</div></body></html>"""


# ============================================================================
#  THE SALES PAGE  (/salespage) — the personalised Marketing Intelligence File
#  pitch. Keyed off everything the audit stored in pipeline.db (raw_json), and
#  wearing the same design system as the report: navy/ivory/gold, Angelo blue,
#  Inter + Source Serif, chapter cards. Static, no animations.
#  Every personalised block degrades to "" (or a generic fallback) when the
#  page is opened with URL params only and there is no stored record.
# ============================================================================

# Plain string (not a template), so the CSS braces need no doubling.
_SALES_CSS = """
  @font-face{font-family:'Inter';font-weight:100 900;font-display:swap;src:url(/inter.woff2) format('woff2')}
  @font-face{font-family:'SourceSerif';font-weight:200 900;font-display:swap;src:url(/serif.woff2) format('woff2')}
  :root{
    --serif:'SourceSerif',Georgia,'Times New Roman',serif;
    --navy:#0B132B;--navy-card:#131D3E;--navy-deep:#0F1834;--navy-line:#27335C;
    --ivory:#F4F5F7;--ivory-dim:#A9B1C4;
    --paper:#F4F5F7;--surface:#fff;--ink:#1B222C;--muted:#5A6472;--line:#E1E4EA;
    --accent:#3a76bd;--accent-ink:#234e83;--glow:#7FA9DD;--soft:#EBF1F8;
    --gold:#D4AF37;--gold-h:#C2A02F;
    --good:#2A7B56;--warn:#A87B23;--warn-ink:#7A5A16;--critical:#A62626;}
  *{box-sizing:border-box}
  html{background:var(--navy)}
  body{margin:0;background:var(--paper);color:var(--ink);
    font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6}
  .wrap{max-width:760px;margin:0 auto;padding:44px 22px 80px}
  h2{font-family:var(--serif);font-weight:600;font-size:clamp(19px,3.4vw,25px);margin:0 0 14px;line-height:1.3;color:var(--ink)}
  h3{font-weight:600;font-size:16px;margin:0 0 8px;color:var(--ink)}
  p{margin:0 0 14px;font-size:15px;line-height:1.65;color:var(--ink)}
  p:last-child{margin-bottom:0}
  .card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:36px 32px;
    box-shadow:0 1px 3px rgba(11,19,43,.08);margin-bottom:28px}
  @media(max-width:560px){.card{padding:26px 18px}}
  .label{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-ink);font-weight:700;margin-bottom:12px}
  .section-eyebrow{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent-ink);
    font-weight:700;margin-bottom:16px}
  .chip{display:inline-block;font-weight:700;font-size:15px;padding:3px 11px;border-radius:8px;line-height:1.3}
  .chip .den{opacity:.65;font-weight:600;font-size:12px}
  .chip.good{background:#EDF5F0;color:var(--good)}
  .chip.warn{background:#F8F3E7;color:var(--warn-ink)}
  .chip.crit{background:#F8EEEE;color:var(--critical)}

  /* ---------- sticky nav ---------- */
  .site-nav{background:var(--navy-deep);border-bottom:1px solid var(--navy-line);padding:0 28px;
    display:flex;align-items:center;gap:12px;height:58px;
    position:sticky;top:0;z-index:100}
  .site-nav img{height:36px;width:auto;display:block}
  .site-nav .brand-name{font-size:12px;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:var(--ivory);line-height:1.2}

  /* ---------- first fold (navy hero band) ---------- */
  .first-fold-section{background:var(--navy);color:var(--ivory);padding:60px 40px 56px}
  .ff-header{max-width:1100px;margin:0 auto 36px}
  .ff-eyebrow{font-size:12px;letter-spacing:.24em;text-transform:uppercase;
    color:var(--ivory-dim);font-weight:600;margin-bottom:18px}
  .ff-h1{font-size:clamp(26px,3.6vw,44px);font-weight:700;color:#fff;
    letter-spacing:-.02em;line-height:1.14;margin:0}
  .first-fold-inner{max-width:1100px;margin:0 auto;display:grid;
    grid-template-columns:1fr 1fr;gap:48px;align-items:center}
  @media(max-width:800px){.first-fold-inner{grid-template-columns:1fr;gap:32px}
    .first-fold-section{padding:44px 22px 48px}
    .ff-header{margin-bottom:24px}}
  .ff-body{font-size:16px;font-weight:300;color:var(--ivory);line-height:1.72;margin:0 0 16px}
  .ff-body:last-child{margin-bottom:0}
  .ff-body strong{color:var(--glow);font-weight:600}
  .ff-score{color:#fff;font-weight:700}
  .hook{max-width:1100px;margin:28px auto 0;padding:18px 20px;border-radius:8px;
    background:rgba(166,38,38,.16);border:1px solid rgba(198,90,90,.55);
    font-size:17px;line-height:1.55;font-weight:600;color:#fff}
  .hook.good{background:rgba(58,118,189,.16);border-color:rgba(127,169,221,.5)}
  .hook .sc{color:#fff;font-size:19px;font-weight:700}
  .hook .hl{color:#F0B9B4}
  .hook.good .hl{color:var(--glow)}
  .hook .hl .sc{color:inherit}
  .steps-wrap{position:relative;display:block;width:min(860px,96%);margin:36px auto 0;
    container-type:inline-size}
  .steps-img{display:block;width:100%;height:auto}
  .step-lbl{position:absolute;display:flex;align-items:center;justify-content:center;text-align:center;
    font-weight:700;color:#141414;font-size:13px;font-size:2.1cqw;line-height:1.15}
  .step-lbl.s1{left:34%;top:46.5%;width:17%;height:22%;transform:rotate(-4deg)}
  .step-lbl.s2{left:55%;top:26.5%;width:18%;height:21%;transform:rotate(-2deg)}
  .step-lbl.s3{left:76.5%;top:6.5%;width:18%;height:22%}
  .ff-bridge{max-width:1100px;margin:32px auto 0;padding:0 0 8px}
  .ff-bridge p{font-family:var(--serif);font-size:19px;font-weight:500;color:var(--ivory);line-height:1.55;margin:0;
    border-top:1px solid var(--navy-line);padding-top:28px}
  .ff-right{display:flex;align-items:stretch}
  .screenshot-container{width:100%;border-radius:12px;
    background:var(--navy-card);border:1px solid var(--navy-line);
    box-shadow:0 16px 56px rgba(0,0,0,.35);
    overflow:hidden;min-height:340px;
    display:flex;align-items:center;justify-content:center}
  .screenshot-container img{width:100%;height:100%;object-fit:cover;object-position:top;
    display:block}
  .sc-placeholder{font-size:13px;color:var(--ivory-dim);text-align:center;
    padding:48px 24px;line-height:1.7}

  /* ---------- parser / tokens ---------- */
  .xray-box{margin:22px 0 0;display:grid;grid-template-columns:1fr 1fr;gap:14px}
  @media(max-width:560px){.xray-box{grid-template-columns:1fr}}
  .xray-panel{border-radius:11px;overflow:hidden;border:1px solid var(--line)}
  .xray-panel.before{border-color:#E3CACA}
  .xray-panel.after{border-color:#CBD9EC}
  .xray-screen{min-height:120px;display:flex;align-items:center;justify-content:center;
    font-weight:600}
  .xray-panel.before .xray-screen{background:#F8EEEE;color:var(--critical)}
  .xray-panel.after .xray-screen{background:var(--soft);color:var(--accent-ink)}
  .xray-meta{padding:14px 16px;background:var(--surface)}
  .xray-meta .xm-label{font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;margin-bottom:6px}
  .xray-panel.before .xm-label{color:var(--critical)}
  .xray-panel.after .xm-label{color:var(--accent-ink)}
  .xray-meta .xm-body{font-size:13px;color:var(--muted);line-height:1.55}
  .xray-meta .xm-body em{color:var(--ink);font-style:normal;font-weight:600}

  /* ---------- voice (whose words) ---------- */
  .voice{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);
    border-radius:0 12px 12px 0;padding:36px 32px;margin-bottom:28px;line-height:1.65;font-size:16px;
    box-shadow:0 1px 3px rgba(11,19,43,.08)}
  @media(max-width:560px){.voice{padding:26px 18px}}
  .voice h4{font-family:var(--serif);font-size:25px;font-weight:600;margin:0 0 14px;color:var(--accent-ink)}
  .voice b{color:var(--accent-ink)}
  .voice.good{border-left-color:var(--good)}
  .voice.good h4{color:var(--good)}
  .voice p{margin:0 0 12px}.voice p:last-child{margin:0}
  .voice .statpane{background:var(--soft);border:1px solid #CBD9EC;border-radius:10px;padding:16px 20px}

  /* ---------- criteria + capture + strength ---------- */
  .evidence-section{margin-bottom:28px}
  .video-section{margin-bottom:28px}
  .video-section>p{font-size:14px;color:var(--muted);line-height:1.7;margin:0 0 22px}
  .evidence-grid{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-bottom:28px;align-items:start}
  @media(max-width:800px){.evidence-grid{grid-template-columns:1fr;gap:32px}}
  .evidence-eyebrow{font-size:12px;letter-spacing:.15em;text-transform:uppercase;font-weight:700;
    color:var(--accent-ink);margin-bottom:18px}
  .area-h{font-family:var(--serif);font-size:clamp(20px,3.6vw,27px);font-weight:600;color:var(--ink);
    margin:0 0 18px;line-height:1.3}
  .crit-block{background:var(--surface);border:1px solid var(--line);border-radius:12px;
    padding:20px 24px;margin-bottom:14px;box-shadow:0 1px 3px rgba(11,19,43,.08)}
  .crit-header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:6px}
  .crit-name{font-size:14px;font-weight:700;color:var(--ink)}
  .crit-vs{text-align:right;white-space:nowrap}
  .crit-mkt{display:block;font-size:12px;color:var(--muted);margin-top:3px}
  .crit-defn{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
    margin-bottom:10px;line-height:1.5}
  .crit-quote{font-family:var(--serif);font-style:italic;font-size:15px;color:var(--ink);border-left:3px solid var(--accent);
    padding-left:12px;margin:10px 0;line-height:1.55}
  .crit-obs{font-size:14px;color:var(--ink);line-height:1.65;margin:0}
  .crit-fallback{background:var(--soft);border:1px solid #CBD9EC;border-radius:12px;padding:20px 24px}
  .crit-fallback p{font-size:14px;color:var(--ink);line-height:1.65;margin:0}

  /* ---------- videos ---------- */
  .video-col{display:flex;flex-direction:column;gap:18px}
  .video-block{background:var(--surface);border:1px solid var(--line);border-radius:12px;
    overflow:hidden;box-shadow:0 1px 3px rgba(11,19,43,.08);margin-bottom:0}
  .video-embed{position:relative;width:100%;padding-top:56.25%}
  .video-embed iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
  .video-embed.shorts{padding-top:177.78%}
  .video-copy{padding:20px 24px}
  .video-copy h3{font-size:16px;font-weight:700;color:var(--ink);margin:0 0 10px;line-height:1.35}
  .video-copy p{font-size:14px;color:var(--muted);line-height:1.6;margin:0}

  /* ---------- the cost note (closes the areas section) ---------- */
  .cost-note{background:var(--soft);border:1px solid #CBD9EC;border-left:4px solid var(--accent);
    border-radius:0 10px 10px 0;padding:20px 22px;margin-top:14px}
  .cost-note .cn-h{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-ink);
    font-weight:700;margin-bottom:10px}
  .cost-note p{font-size:15px;line-height:1.65;margin:0 0 10px}
  .cost-note p:last-child{margin-bottom:0}

  /* ---------- protocol / bridge / choices ---------- */
  .protocol-section{margin-bottom:28px}
  .protocol-section .section-eyebrow{margin-bottom:16px}
  .protocol-container{background:var(--surface);border:1px solid var(--line);border-radius:12px;
    padding:24px 28px;margin-bottom:14px;box-shadow:0 1px 3px rgba(11,19,43,.08)}
  .protocol-container .pc-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--accent-ink);font-weight:700;margin-bottom:10px}
  .protocol-container h3{font-family:var(--serif);font-size:19px;font-weight:600;color:var(--ink);margin:0 0 12px;line-height:1.3}
  .protocol-container p{font-size:15px;color:var(--muted);line-height:1.65;margin:0 0 10px}
  .protocol-container p:last-child{margin-bottom:0}
  .protocol-container p b{color:var(--ink)}
  .protocol-container ul{margin:8px 0 0;padding-left:20px}
  .protocol-container li{font-size:15px;color:var(--muted);line-height:1.6;margin:6px 0}
  .protocol-container li b{color:var(--ink)}
  .narrative-bridge{background:var(--surface);border:1px solid var(--line);border-radius:12px;
    padding:36px 32px;box-shadow:0 1px 3px rgba(11,19,43,.08);margin-bottom:28px}
  @media(max-width:560px){.narrative-bridge{padding:26px 18px}}
  .narrative-bridge .nb-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--critical);font-weight:700;margin-bottom:12px}
  .narrative-bridge h2{margin-bottom:14px}
  .three-choices{margin-bottom:28px}
  .three-choices .tc-label{font-size:12px;letter-spacing:.16em;text-transform:uppercase;
    color:var(--accent-ink);font-weight:700;margin-bottom:14px}
  .choice-block{background:var(--surface);border:1px solid var(--line);border-radius:12px;
    padding:20px 24px;margin-bottom:12px;box-shadow:0 1px 3px rgba(11,19,43,.08)}
  .choice-block:last-child{border:1.5px solid var(--accent);background:var(--surface);
    box-shadow:0 0 0 5px var(--soft),0 1px 3px rgba(11,19,43,.08)}
  .choice-block .cb-num{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    font-weight:700;margin-bottom:8px}
  .choice-block:nth-child(2) .cb-num{color:var(--critical)}
  .choice-block:nth-child(3) .cb-num{color:var(--warn-ink)}
  .choice-block:last-child .cb-num{color:var(--accent-ink)}
  .choice-block h3{font-family:var(--serif);font-size:18px;font-weight:600;color:var(--ink);margin:0 0 10px;line-height:1.3}
  .choice-block p{font-size:15px;color:var(--muted);line-height:1.65;margin:0}
  .choice-block:last-child p{color:var(--ink)}

  /* ---------- payoffs / assumptions ---------- */
  .payoffs-section{margin-bottom:28px}
  .payoffs-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:14px}
  @media(max-width:540px){.payoffs-grid{grid-template-columns:1fr}}
  .payoff-tile{background:var(--surface);border:1px solid var(--line);border-radius:12px;
    padding:20px 22px;box-shadow:0 1px 3px rgba(11,19,43,.08);display:flex;flex-direction:column}
  .payoff-tile .pt-icon{font-size:24px;margin-bottom:10px}
  .payoff-tile .pt-title{font-size:14px;font-weight:700;color:var(--ink);margin-bottom:8px;line-height:1.3}
  .payoff-tile .pt-body{font-size:13px;color:var(--muted);line-height:1.6;flex:1}
  .assumptions-section{margin-bottom:28px}
  .assumption{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:24px 28px;
    margin-bottom:14px;box-shadow:0 1px 3px rgba(11,19,43,.08)}
  .assumption .a-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--warn-ink);
    font-weight:700;margin-bottom:10px}
  .assumption h3{font-family:var(--serif);font-size:19px;font-weight:600;color:var(--ink);margin:0 0 12px;line-height:1.3}
  .assumption p{font-size:15px;color:var(--muted);line-height:1.65;margin:0 0 10px}
  .assumption p:last-child{margin-bottom:0}
  .assumption p b{color:var(--ink)}

  /* ---------- product reveal / guarantee / checkout ---------- */
  .product-reveal{border:1.5px solid var(--accent);border-radius:12px;padding:36px 32px;margin-bottom:28px;
    background:var(--surface);box-shadow:0 0 0 5px var(--soft),0 1px 3px rgba(11,19,43,.08)}
  @media(max-width:560px){.product-reveal{padding:26px 18px}}
  .product-reveal .pr-eyebrow{font-size:12px;letter-spacing:.16em;text-transform:uppercase;
    color:var(--accent-ink);font-weight:700;margin-bottom:10px}
  .product-reveal h2{color:var(--accent-ink);margin-bottom:14px}
  .mi-img{display:block;width:min(280px,72%);height:auto;margin:0 auto 20px;
    filter:drop-shadow(0 10px 22px rgba(11,19,43,.25))}
  .price-anchor{font-size:14px;color:var(--muted);margin:16px 0 6px}
  .price-main{font-family:var(--serif);font-size:30px;font-weight:700;color:var(--accent-ink);margin:0 0 4px}
  .price-main span{font-family:"Inter",sans-serif;font-size:14px;font-weight:500;color:var(--muted)}
  .guarantee-block{background:var(--soft);border:1px solid #CBD9EC;border-left:4px solid var(--accent);
    border-radius:0 11px 11px 0;padding:20px 22px;margin-top:22px;
    display:flex;gap:20px;align-items:center}
  @media(max-width:560px){.guarantee-block{flex-direction:column}}
  .guarantee-block .g-copy{flex:1;min-width:0}
  .guarantee-block .g-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--accent-ink);font-weight:700;margin-bottom:10px}
  .guarantee-block p{font-size:14px;color:var(--ink);line-height:1.65;margin:0 0 10px}
  .guarantee-block p:last-child{margin-bottom:0}
  .guarantee-block p b{color:var(--accent-ink)}
  .angelo-relax{width:120px;aspect-ratio:1;object-fit:cover;border-radius:50%;flex-shrink:0;
    border:2px solid var(--accent);box-shadow:0 0 0 5px #fff}
  .cta-angelo-wrap{position:relative;display:block;width:min(400px,90%);margin:0 auto 20px;
    container-type:inline-size}
  .cta-angelo{display:block;width:100%;height:auto}
  .bubble-txt{position:absolute;left:8%;top:14%;width:33%;height:23%;display:flex;
    align-items:center;justify-content:center;text-align:center;font-weight:700;color:#141414;
    font-size:13px;font-size:3.7cqw;line-height:1.25}
  .checkout-section{background:var(--navy);border-radius:16px;padding:40px 32px;margin-bottom:28px}
  @media(max-width:560px){.checkout-section{padding:28px 20px}}
  .checkout-section h2{font-family:var(--serif);color:#fff;margin-bottom:6px;font-size:clamp(20px,4vw,26px)}
  .checkout-section .cs-sub{color:var(--ivory-dim);font-size:15px;margin-bottom:24px}
  .checkout-form-placeholder{background:var(--navy-card);border:1px dashed var(--navy-line);border-radius:11px;
    padding:28px 24px;text-align:center}
  .checkout-form-placeholder .cf-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--ivory-dim);font-weight:600;margin-bottom:12px}
  .checkout-form-placeholder .cf-note{font-size:14px;color:var(--ivory-dim);line-height:1.55}
  .checkout-form-placeholder .lock-icon{font-size:28px;margin-bottom:10px}
  .cta-btn{display:inline-block;background:var(--gold);color:var(--navy);text-decoration:none;font-weight:700;
    padding:16px 30px;border-radius:6px;font-size:16px;margin-top:18px;border:0;cursor:pointer;width:100%;
    text-align:center}
  .cta-btn:hover{background:var(--gold-h)}
  .cta-btn:disabled{opacity:.55;cursor:default}
  .guarantee{font-size:13px;color:var(--ivory-dim);margin-top:14px;text-align:center;line-height:1.5}
"""

# The criteria a Marketing Intelligence File genuinely fixes, and the plain phrase the hook uses
# for each. Mirrors render_result's hook: never praise while one of these sits at 5/10 or under.
_SALES_HOLE = {
    "specificity": "who it's for",
    "clarity_5sec": "a stranger getting it in five seconds",
    "offer_clarity": "showing what you actually fix",
    "symptom_resonance": "describing the problem in your buyer's own words",
}


def _sales_hook(data, page_word, niche_word):
    """The personalised hook box for the hero. Same rule as the report: if any MI-fixable
    criterion is 5/10 or under, name the weakest one; praise only when nothing is weak."""
    scores = (data or {}).get("scores") or {}
    if not scores:
        return ""
    weak = min(_SALES_HOLE, key=lambda k: scores.get(k, 99))
    hole_score = scores.get(weak, 0)
    mr_score = scores.get("symptom_resonance", 0)
    # The hook must explain its own number (David): the overall score is one figure, this is one
    # of the eight checks INSIDE it — say so, or a 4.6 followed by a bare 3/10 reads like a typo.
    if hole_score > 5:
        return (
            f'<div class="hook good"><span class="hl">Your overall score is built from eight separate checks, '
            f'and you scored a strong <span class="sc">{mr_score}/10</span> on Mind Reading.</span> '
            f'This means your instincts are lightyears ahead of the market average. However, maintaining that accuracy '
            f'across all your outbound copy, emails, and ads without a continuous stream of hard consumer data is '
            f'exhausting. The Marketing Intelligence File scales what you are already doing right, for the '
            f'{niche_word}you want more of.</div>'
        )
    return (
        f'<div class="hook"><span class="hl">Your overall score is built from eight separate checks. The one '
        f'holding yours down is {_SALES_HOLE[weak]}: <span class="sc">{hole_score}/10</span>.</span> Not '
        f'because you don&rsquo;t know your clients, but because the page is written in your words, not the words '
        f'a cold buyer uses in their own head. Getting those exact words, the ones your {niche_word}really use, '
        f'is the whole game.</div>'
    )


def _sales_voice(voice, page_word, cnt):
    """Follow-on to the X-ray card. Dissolved from the old 'whose words are these' card (David:
    it re-told the X-ray, and its best lines now live in Root 4) down to the two beats nothing
    else on the page carries: the 1-in-14 stat and the good-news flip. The rare coach who already
    speaks buyer language keeps their short praise variant instead. Empty without voice data."""
    leaning = (voice or {}).get("leaning")
    if not leaning:
        return ""
    if leaning == "customer":
        return (
            '<div class="voice good"><h4>You&rsquo;re speaking your buyer&rsquo;s language</h4>'
            f'<p>Here&rsquo;s something you&rsquo;re doing well. Your {page_word} talks about the problem in words your customer '
            'would actually use, not just coach words.</p>'
            f'<p>That&rsquo;s rarer than you&rsquo;d think. Of the {cnt} coaching sites we scored, only about 1 in {BUYER_VOICE_1_IN} do this. The '
            f'other {PCT_NOT_BUYER_VOICE}% talk like the expert. You sound more like the person with the problem, and <b>that&rsquo;s a real edge</b>. '
            'Keep using the real words your clients say.</p></div>')
    return (
        '<div class="voice">'
        f'<p class="statpane">And hardly any coaches get this right. We looked at <b>{cnt}</b> coaching websites. Only about '
        f'<b>1 in {BUYER_VOICE_1_IN}</b> use their customer&rsquo;s words. The other <b>{PCT_NOT_BUYER_VOICE}%</b> sound just like this page does.</p>'
        '<p>That&rsquo;s good news for you. Nearly every coach sounds the same, so people can&rsquo;t tell them apart. Use '
        'the words your customers actually use, and <b>you stand out straight away</b>. You become <b>the coach who '
        'understands them</b>. The rest of this page shows you where those words come from.</p></div>')


def _sales_cost(critique):
    """The one part of the stored diagnosis the criteria cards above don't already say: the COST.
    (David's call: 'the biggest thing in the way' and 'bottom line' re-told the cards; the fixes
    list never belonged on a salespage. What remains closes the areas section with why it hurts.)"""
    cost = (critique or {}).get("why_it_costs_clients")
    if not cost:
        return ""
    return (f'<div class="cost-note"><div class="cn-h">What it&rsquo;s costing you</div>'
            f'{para_split(cost)}</div>')


def _build_criteria_html(data, hero_quote):
    """Return the 3 lowest-scoring criteria blocks (with the you-vs-market number for each),
    or a plain fallback if no stored record is available."""
    _fallback = (
        '<div class="crit-fallback">'
        "<p>Your homepage copy does not name a specific, daily problem your buyer is living through. "
        "It describes what coaching does rather than what a stranger is already searching for. "
        "That is why cold visitors leave without making contact.</p>"
        "</div>"
    )
    if not data:
        return _fallback
    try:
        scores = data.get("scores", {})
        notes = data.get("notes", {})
        hero = html.escape(hero_quote or "")
        scored = [(k, scores[k]) for k in DISPLAY_CRIT if k in scores]
        scored.sort(key=lambda x: x[1])
        worst3 = scored[:3]
        if not worst3:
            return _fallback
        blocks = []
        for k, s in worst3:
            label = html.escape(LABELS.get(k, k))
            defn = html.escape(DEFINITIONS.get(k, ""))
            note_obj = notes.get(k, {})
            raw_note = (note_obj.get("note", "") if isinstance(note_obj, dict) else "") or ""
            # First sentence only — split on ". " so decimal numbers don't break it.
            dot = raw_note.find(". ")
            first_sent = html.escape((raw_note[:dot + 1] if dot != -1 else raw_note[:200]).strip())
            # Verbatim headline quote for criteria where the headline IS the evidence.
            quote_html = ""
            if k in ("clarity_5sec", "symptom_resonance", "specificity") and hero:
                quote_html = f'<blockquote class="crit-quote">&ldquo;{hero}&rdquo;</blockquote>'
            # The market number for the same criterion — read live from audit.py's BENCH (the single
            # source of truth), never from the stored record, so a re-benchmark updates old pages too.
            mkt = BENCH.get(k)
            mkt_html = f'<span class="crit-mkt">market {mkt}</span>' if mkt is not None else ""
            blocks.append(
                f'<div class="crit-block">'
                f'<div class="crit-header">'
                f'<span class="crit-name">{label}</span>'
                f'<span class="crit-vs"><span class="chip {sev_class(s)}">{s}<span class="den">/10</span></span>{mkt_html}</span>'
                f'</div>'
                f'<div class="crit-defn">{defn}</div>'
                f'{quote_html}'
                f'<p class="crit-obs">{first_sent}</p>'
                f'</div>'
            )
        return "\n".join(blocks)
    except Exception:
        return _fallback


def _render_salespage(first_name, headline, tokens, score, screenshot="", raw_json=""):
    fn = html.escape(first_name)
    fn_up = html.escape(first_name.upper())
    shot = html.escape(screenshot, quote=True)
    cnt = f"{websites_read_count():,}"

    # Parse the stored audit once. Every personalised block below degrades cleanly without it,
    # so the param-only fallback URL still renders a complete page.
    data = None
    if raw_json:
        try:
            data = _json.loads(raw_json)
        except Exception:
            data = None
    ev = (data or {}).get("evidence") or {}
    voice = (data or {}).get("voice") or {}
    critique = (data or {}).get("critique") or {}

    # RULEBOOK §0: never claim "homepage" when a subpage was audited.
    page_word = "homepage" if (data or {}).get("is_home", True) else "page"
    # Prefer the stored 1-decimal score over the coarse URL param.
    sc = html.escape(str((data or {}).get("score_10_display") or score))
    # The coach's actual words from the voice sweep beat the old generic-tokens param.
    _terms = [t for t in voice.get("coach_terms", []) if t]
    tok = html.escape(tokens or ", ".join(_terms) or "generic coaching terms")
    # Niche → "life coaching clients" (raw niche words don't work as an adjective on their own).
    _niche = ev.get("niche")
    niche_word = f"{html.escape(_niche)} coaching clients " if _niche else "clients "

    hook_html = _sales_hook(data, page_word, niche_word)
    voice_html = _sales_voice(voice, page_word, cnt)
    cost_html = _sales_cost(critique)
    criteria_html = _build_criteria_html(data, headline)

    # Softer opener for low scorers (David's rule + his copy): under 5 there is no "brutal",
    # the average is framed as within reach, and the low score as easier to improve. 5 and up
    # keeps the original opener. An unparseable score gets the soft version — it is safe for
    # everyone, the harsh one is only right for a page that can take it.
    try:
        _sc_num = float((data or {}).get("score_10_display") or score)
    except (TypeError, ValueError):
        _sc_num = 0.0
    if _sc_num <= 4.9:
        # The "bigger picture" line has to be true against the market average, not just under 5:
        # a 4.6 is ABOVE the 4.5 average, so "a few steps away from improving yours" read wrong
        # (David caught it). Below average -> David's original line; at/above it -> honest version:
        # ahead of the average, but the average page doesn't bring in clients, the top level does.
        if _sc_num > MARKET_AVG_10:
            _bigger = (
                f'<p class="ff-body">To give you the bigger picture, the average is {MARKET_AVG_10} out of ten, '
                f'so you are already above the average. But the average coaching homepage is not bringing in '
                f'clients, so that is a low bar. The top pages score {TOP10_10} or higher, and that is where a '
                f'page starts working. You are close to that level, and we are here to help you get there today.</p>')
        else:
            _bigger = (
                f'<p class="ff-body">To give you the bigger picture, the average is {MARKET_AVG_10} out of ten, '
                f'so you are only a few steps away from improving yours. Remember this, it&rsquo;s easier to '
                f'improve when the score is lower, and we are here to help you do that today.</p>')
        opener_html = (
            f'<p class="ff-body">Hi {fn}. It&rsquo;s never nice having a low score, we remember what '
            f'that was like at school. Your {page_word} text scored <strong class="ff-score">{sc}/10</strong>.</p>'
            + _bigger +
            f'<p class="ff-body">But please see this score for what it is: <strong>an area of easy growth</strong>. '
            f'This is not about a 1% shift in your business. It is about taking one big stride forward.</p>')
    elif _sc_num >= TOP10_10:
        # Top-tier (David's catch): at 5.7+ they ARE the top 10% — say so, then sell the last
        # edge, not a rescue job. The hook below still names a weak criterion if one exists.
        opener_html = (
            f'<p class="ff-body">Hello {fn}. Your {page_word} text scored <strong class="ff-score">{sc}/10</strong>. '
            f'Across the {cnt} coaching homepages we have read, the average is {MARKET_AVG_10} out of 10, and only '
            f'the top 10% score {TOP10_10} or higher. <strong>You are one of them.</strong></p>'
            f'<p class="ff-body">So this page is not about fixing a broken page. It is about the last edge: the '
            f'distance between a page that reads well and a page built on your buyer&rsquo;s actual words.</p>')
    else:
        opener_html = (
            f'<p class="ff-body">Hello {fn}. Your {page_word} text scored <strong class="ff-score">{sc}/10</strong>. '
            f'For context: across the {cnt} coaching homepages we have read, the average score is {MARKET_AVG_10} '
            f'out of 10, and the top 10% score {TOP10_10} or higher.</p>')

    # Benefit-first headline (David + Ogilvy panel): name the prize, never the product the
    # reader hasn't met yet. The coach's name leads when we have it.
    h1_line = (f'{fn}, here&rsquo;s what your buyers actually want, and the exact words that bring them to you.'
               if fn else
               'Here&rsquo;s what your buyers actually want, and the exact words that bring them to you.')

    # Beckoning Angelo: the bubble in the artwork is blank; the words are HTML overlaid on it
    # (same pattern as the report's _angelo_speaks), so the line is personalised per coach.
    # fn is never empty here — the handler falls back to "Coach" — but guard anyway.
    bub = f'Come on, {fn}. Let me show you.' if fn else 'Come on. Let me show you.'
    buy_btn = (f'{fn}, get your Marketing Intelligence File &rarr;' if fn
               else 'Get My Marketing Intelligence File &rarr;')

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your Marketing Intelligence File | {fn}</title>
<style>{_SALES_CSS}</style></head><body>

  <nav class="site-nav">
    <img src="/angelo.png" alt="Going Beyond The Illusion">
    <span class="brand-name">GOING BEYOND THE ILLUSION</span>
  </nav>

  <div class="first-fold-section">
    <div class="ff-header">
      <div class="ff-eyebrow">&#128309; YOUR PRIVATE RESULTS PAGE // PREPARED FOR: {fn_up}</div>
      <h1 class="ff-h1">{h1_line}</h1>
    </div>
    <div class="first-fold-inner">
      <div class="ff-left">
        {opener_html}
        <p class="ff-body">Someone arrived on your page yesterday with a specific, painful problem. They gave it five seconds. Your words did not describe their problem. They left. You never knew they were there.</p>
      </div>
      <div class="ff-right">
        <div class="screenshot-container">
          {"" if not shot else f'<img src="{shot}" alt="Your coaching website homepage" loading="eager">'}
          {"" if shot else '<div class="sc-placeholder"><img src="/angelo.png" alt="Angelo" style="width:72px;height:auto;opacity:.55;margin-bottom:14px"><div>Screenshot loading&hellip;</div></div>'}
        </div>
      </div>
    </div>
    {hook_html}
    <div class="ff-bridge">
      <p>So here is the plan. First, the areas that will grow your business fastest, the ones we found when we read your page. Then, why this happens to almost every coach. Once you can see the why, you can make a sound decision about what to do next.</p>
    </div>
    <div class="steps-wrap">
      <img class="steps-img" src="/angelo_steps.png" alt="Angelo pointing up the three steps of this page">
      <span class="step-lbl s1">The areas</span>
      <span class="step-lbl s2">The why</span>
      <span class="step-lbl s3">Your decision</span>
    </div>
  </div>

  <div class="wrap">

  <!-- SECTION 2: THE AREAS — their own evidence, growth-framed heading (David's pick) -->
  <div class="evidence-section">
    <h2 class="area-h">The areas that will grow your business fastest</h2>
    {criteria_html}
    {cost_html}
  </div>

  <!-- SECTION 3: THE WHY — the report said WHAT is wrong; this chapter explains WHY it happens.
       Thesis + their own words as live evidence, then the four roots. -->
  <div class="why-section">
    <div class="section-eyebrow">Why this happens to almost every coach</div>

    <div class="card">
      <h2>Your words do not match the thoughts already inside your client&rsquo;s head.</h2>
      <p>That is not a design problem, and it is not carelessness or a lack of talent. To see what it
      actually is, look at the words we found on your {page_word}, next to the words your buyer
      actually uses.</p>

      <div style="margin-top:18px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;
        color:var(--accent-ink);font-weight:700;margin-bottom:10px">The Messaging X-Ray: From Intuition to Intelligence</div>
      <div class="xray-box">
        <div class="xray-panel before">
          <div class="xray-screen" style="font-size:16px;letter-spacing:.02em;font-style:italic;padding:18px 22px;text-align:center">{tok}</div>
          <div class="xray-meta">
            <div class="xm-label">What your {page_word} says</div>
            <div class="xm-body">These words describe what you offer. A cold buyer is not searching for what you offer.
            They are searching for relief from a specific problem. These words do not name it.</div>
          </div>
        </div>
        <div class="xray-panel after">
          <div class="xray-screen" style="font-size:13px;line-height:1.6;padding:18px 22px;text-align:left">&ldquo;I cannot stop thinking about&hellip;&rdquo;<br>&ldquo;I wake up every morning and&hellip;&rdquo;<br>&ldquo;I have tried everything and&hellip;&rdquo;</div>
          <div class="xray-meta">
            <div class="xm-label">What your buyer actually says</div>
            <div class="xm-body">The sort of thing your market really types when they go looking for help and
            nobody is watching. When your page uses words like these, strangers stop and read.</div>
          </div>
        </div>
      </div>

      <p style="margin-top:16px">Each one is abstract. Each one could sit on any coaching page on the internet.
      When a stranger arrives on your page and reads words that do not describe their specific problem,
      they do not think &ldquo;this coach is too generic.&rdquo; They think &ldquo;this is not for me&rdquo;
      and they leave. The problem is not your design or your credentials. It is the words.</p>
      <p>Each of those terms means something specific to you.
      To a cold stranger who has never met you, they describe nobody&rsquo;s life in particular.
      Replacing them with different abstract terms is not a fix. The fix is to find out what language
      your specific buyer uses when they describe their own problem, and use those words instead.
      That is a research question, not a writing question.</p>
    </div>

    {voice_html}

    <div class="protocol-container">
      <div class="pc-label">Root 1</div>
      <h3>Nobody can see their own business from the outside.</h3>
      <p>You built this business from the inside, so you describe it from the inside. You know what your
      coaching does, so that is what the page says. But your buyer has never been inside. They only know
      what their problem feels like.</p>
      <p>Nobody sees their own business the way a stranger sees it. Not you, not us, nobody.</p>
    </div>

    <div class="protocol-container">
      <div class="pc-label">Root 2</div>
      <h3>The trends are coaches copying coaches.</h3>
      <p>When you look around for how to write your page, you look at other coaches. The sites that look
      professional. The phrases everyone uses. But we have read {cnt} coaching homepages, and
      {PCT_FAIL_5SEC}% fail the five-second test.</p>
      <p>That is who the trends come from. Follow them, and you inherit their results.</p>
    </div>

    <div class="protocol-container">
      <div class="pc-label">Root 3</div>
      <h3>The people you hired could only give you opinions.</h3>
      <p>Maybe you paid for help. A designer, a brand expert, a business coach, a course. Here is the
      problem: they gave you their opinion. It may have been a good opinion.</p>
      <p>But an opinion is not evidence, and nobody you hired was holding your buyer&rsquo;s actual words.</p>
    </div>

    <div class="protocol-container">
      <div class="pc-label">Root 4</div>
      <h3>You got through the problem you now fix.</h3>
      <p>That is exactly why you are good at fixing it. But it also means you talk like someone on the
      other side of it, while your buyer is still in it.</p>
      <p>You talk like the expert who fixed the problem. They talk like someone who still has it.
      Those are two different languages.</p>
    </div>

    <div class="card">
      <p><strong>Put those together and the mystery disappears.</strong> Nothing in your world contains
      your buyer&rsquo;s actual words. Not your own head, and not anyone you hired. So the page sounds
      like you, because your view is all anyone ever had to work with.</p>
      <p>That is why the score is what it is. And it is why rewriting the page with the same ingredients
      gets the same result.</p>
    </div>
  </div>

  <!-- SECTION 4: PERMISSION, THEN THE CURE -->
  <div class="narrative-bridge">
    <div class="nb-label">Before we go on</div>
    <h2>May we show you what the fix looks like?</h2>
    <p>The fix is not more opinions, and it is not trying harder with the same ingredients. It is the
    missing ingredient itself: your buyer&rsquo;s actual words, as evidence. Here it is.</p>
  </div>

  <!-- What the File is -->
  <div class="product-reveal" id="file">
    <img class="mi-img" src="/angelo_file.png" alt="Angelo with your Marketing Intelligence File">
    <div class="pr-eyebrow">The Marketing Intelligence File</div>
    <h2>The exact words your buyers use when they describe their own problem.</h2>
    <p>Not the polished version. Not the aspirational version. The raw, unedited language your specific market
    uses when they are searching for a solution at two in the morning and nobody is watching.
    The fears they do not say out loud. The specific outcomes that make them pick up the phone.
    The words that, when they appear on your homepage, make a cold stranger stop scrolling and think:
    <em>this person understands exactly what I am going through.</em></p>
    <p>This is not a template. It is not a questionnaire you fill in yourself. It is real research into your
    specific market, built on the evidence we have already read: {cnt} coaching websites, and 2,000 books
    your market bought to fix their own problems. Every book that sells is a vote, real proof of what people
    struggle with and what they will pay to fix. It all arrives as a single structured file you hand to anyone
    writing your copy, or load straight into any AI tool and watch it stop producing coaching clich&eacute;s.</p>
  </div>

  <!-- The benefits -->
  <div class="payoffs-section">
    <div class="section-eyebrow">What becomes possible when your words match your buyer&rsquo;s thoughts</div>
    <div class="payoffs-grid">

      <div class="payoff-tile">
        <div class="pt-icon">&#127919;</div>
        <div class="pt-title">The right people get in touch</div>
        <div class="pt-body">
          <p>When your page says what your buyer is already thinking, the right people recognise themselves and reach out.</p>
          <p>More clients, the right ones, and the growth to reach your next level.</p>
        </div>
      </div>

      <div class="payoff-tile">
        <div class="pt-icon">&#9997;&#65039;</div>
        <div class="pt-title">Writing stops being the hard part</div>
        <div class="pt-body">
          <p>The file gives you the words for everything you write, from your homepage to your emails. No more staring at a blank page wondering what to say.</p>
          <p>You read what your buyer says, and you answer it.</p>
        </div>
      </div>

      <div class="payoff-tile">
        <div class="pt-icon">&#128222;</div>
        <div class="pt-title">Sales calls get easier</div>
        <div class="pt-body">
          <p>When your public words show you understand the problem, people arrive at the call already half-decided.</p>
          <p>You spend less time convincing and more time coaching.</p>
        </div>
      </div>

      <div class="payoff-tile">
        <div class="pt-icon">&#129517;</div>
        <div class="pt-title">You stop wondering and start knowing</div>
        <div class="pt-body">
          <p>Every decision, from your next offer to your next post, rests on real facts about what your market pays to fix.</p>
          <p>Feeling sure and being right finally point the same way.</p>
        </div>
      </div>

    </div>
  </div>

  <!-- The four myths (false beliefs). "Myth" not "Assumption": a myth belongs to the industry,
       not the reader, which keeps the blame where the roots section put it. Each card holds to
       the Myth-3 standard: two short paragraphs, one idea each. -->
  <div class="assumptions-section">
    <div class="section-eyebrow">Four myths that keep coaches invisible</div>

    <div class="assumption">
      <div class="a-label">Myth 1</div>
      <h3>&ldquo;I just need to tweak my messaging.&rdquo;</h3>
      <p>Swapping a few words on a page built on the wrong foundation just gives the problem a fresh
      coat of paint, {fn}. The page is written around what you offer, not around what a stranger is
      searching for.</p>
      <p>And any new words you write come from the same place the old ones did. <b>Feeling sure and
      being right are not the same thing.</b> Nothing changes.</p>
    </div>

    <div class="assumption">
      <div class="a-label">Myth 2</div>
      <h3>&ldquo;I already talk to my clients every day. I know exactly what they want.&rdquo;</h3>
      <p>Your current clients talk to you after they have already decided to hire you. That is a small
      and very loyal sample. It tells you almost nothing about <b>the strangers who arrived on your
      page last Tuesday and left without getting in touch.</b></p>
      <p>Those strangers are the majority of your market. They searched in their own words, not yours,
      and your current clients cannot tell you what those words are, because they are not those people.</p>
    </div>

    <div class="assumption">
      <div class="a-label">Myth 3</div>
      <h3>&ldquo;My words are fine. I just need more people to see the page.&rdquo;</h3>
      <p>More visitors to a page that is not working just means more people leaving.
      If ten people arrive and nobody gets in touch, a hundred will give you ten times the silence,
      and you will have paid for the ads.</p>
      <p>Traffic multiplies what a page already does. Fix the words first, so the traffic has
      something to work with.</p>
    </div>

    <div class="assumption">
      <div class="a-label">Myth 4</div>
      <h3>&ldquo;Can&rsquo;t I just use AI to write my research for free?&rdquo;</h3>
      <p>AI writing tools do not do research. They predict the next word from what they have already
      read, and what they have read is the internet, full of coaching pages saying &ldquo;empower&rdquo;,
      &ldquo;mindset&rdquo; and &ldquo;clarity&rdquo;. Ask AI to research your market and it hands those
      same words back. <b>You sound like every other coach, which is the exact problem you started with.</b></p>
      <p>The Marketing Intelligence File does not ask AI what your market wants. It reads where your
      market actually speaks, and pulls out the language they use when nobody is selling to them.
      Different process, different output.</p>
    </div>
  </div>

  <!-- Proof of the cure: three coaches on video -->
  <div class="video-section">
    <div class="evidence-eyebrow">Three coaches who fixed the same problem</div>
    <p>They had low scores. Their words described what they offered, not what their buyers were already searching for. Below is what happened when that changed.</p>
    <div class="evidence-grid">

      <div class="video-col">
        <div class="video-block">
          <div class="video-embed shorts">
            <iframe src="https://www.youtube.com/embed/I2Q-BU3CQjo"
              title="Chad Peterson case study"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen></iframe>
          </div>
          <div class="video-copy">
            <h3>A language fix that corrected a blind spot for a coach in South America.</h3>
            <p>Chad explains how the Marketing Intelligence data forced him to change who he was speaking to. He discovered the exact questions his audience asks online at two in the morning.</p>
          </div>
        </div>
      </div>

      <div class="video-col">
        <div class="video-block">
          <div class="video-embed">
            <iframe src="https://www.youtube.com/embed/bdnCbMnHaZo"
              title="David Hyner case study"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen></iframe>
          </div>
          <div class="video-copy">
            <h3>Why ignoring standard advice gives you real authority.</h3>
            <p>David breaks down what happens when you replace fill-in-the-blank templates with hard customer facts. The shift is structural, not cosmetic.</p>
          </div>
        </div>
        <div class="video-block">
          <div class="video-embed">
            <iframe src="https://www.youtube.com/embed/JJf6rFjWqds"
              title="Brandon Croud deep-dive case study"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen></iframe>
          </div>
          <div class="video-copy">
            <h3>Long-term results after switching from instinct to evidence.</h3>
            <p>Brandon shows the financial difference between pages built on intuition and pages built on real buyer data. The difference is not subtle.</p>
          </div>
        </div>
      </div>

    </div>
  </div>

  <!-- What you get -->
  <div class="protocol-section" id="inside">
    <div class="section-eyebrow">What is inside your Marketing Intelligence File</div>

    <div class="protocol-container">
      <div class="pc-label">Container A</div>
      <h3>The Core Demographic Portrait</h3>
      <p>A detailed picture of the real person buying in your niche, built from evidence, not assumptions.</p>
      <ul>
        <li><b>Calibrated Avatar &amp; Niche.</b> A precise profile of who is actually spending money in your market right now, built from real buying signals, not a generic age bracket.</li>
        <li><b>3 AM Crisis Log.</b> A map of the specific real-life situations that keep your buyer awake. What they are staring at. What they are replaying in their head. What they typed into their phone at midnight.</li>
        <li><b>The Deep Emotions.</b> The feelings driving those moments. What they are scared of. What they are ashamed of. What they are desperate to stop feeling.</li>
        <li><b>What they want to feel, see, and touch.</b> The exact outcomes they are picturing when they imagine the problem being gone. In their words, not yours.</li>
        <li><b>Their secret hangups.</b> The hidden reasons they talk themselves out of buying. The doubts they do not say out loud when they speak to a coach.</li>
      </ul>
    </div>

    <div class="protocol-container">
      <div class="pc-label">Container B</div>
      <h3>The Language Filtering Matrix</h3>
      <p>A practical guide to what to cut from your marketing and what to replace it with.</p>
      <ul>
        <li><b>Clich&eacute; Deletion Blueprint.</b> A line-by-line audit of the abstract terms already found on your page, including the ones we found ourselves: <em>{tok}</em>. Each one explained plainly, with the reason it registers as noise to a cold buyer.</li>
        <li><b>AI Slop Deletion Guide.</b> A reference list of the predictable phrase styles that mark your writing as generated and generic. Things like &ldquo;unlock your potential&rdquo;, &ldquo;on your journey&rdquo;, and &ldquo;transform your life&rdquo;. Buyers have seen these lines everywhere, so they slide right past them.</li>
        <li><b>High-status buyer vocabulary.</b> The specific words and phrases premium clients actually use when they are ready to spend money. The language that signals to them that you understand the problem they are living with, not just the solution you sell.</li>
      </ul>
    </div>

    <div class="protocol-container">
      <div class="pc-label">Container C</div>
      <h3>The Universal Marketing Fuel Cell</h3>
      <p>Everything above is formatted as a master prompt framework you can copy and paste straight into any AI writing tool, including ChatGPT and Claude, and get output that reads like a real human wrote it about a real problem.</p>
      <p>Without this data sitting underneath it, any AI tool just repeats the same coaching clich&eacute;s it has seen a thousand times. <b>With this data loaded in, it writes from your buyer&rsquo;s actual reality.</b> The output stops sounding like every other coach on the internet and starts sounding like someone who understands the specific person reading it.</p>
      <p>You are not locked into using AI. You can hand this file to a copywriter, a VA, or use it yourself. It works the same way in any of those hands because the facts it contains do not change.</p>
    </div>
  </div>

  <!-- Price and guarantee -->
  <div class="product-reveal">
    <div class="pr-eyebrow">The price, and the guarantee</div>
    <p class="price-anchor">Real market research is a corporate purchase. Agencies charge thousands of pounds
    for even a small study, because a human analyst combs through the sources one by one. Our research engine
    has already done years of that reading, and a person still checks every file before it goes out. That is
    how the corporate tool reaches you at a coach&rsquo;s price.</p>
    <div class="price-main">&pound;75 <span>(One-Time Investment)</span></div>

    <div class="guarantee-block">
      <div class="g-copy">
        <div class="g-label">7-Day Certainty Guarantee</div>
        <p>If you read your file and feel it does not contain buyer language you could not have found yourself,
        or market facts you did not already know, contact us within 7 days and we will give you a full refund.
        No forms. No hoops. No awkward conversation.</p>
        <p>We can make this offer because the evidence is already in: {cnt} coaching websites read, and 2,000
        books analysed, the books your market bought to fix their own problems. We know what your market keeps
        paying for. <b>The risk is on us, not your wallet.</b></p>
      </div>
      <img class="angelo-relax" src="/angelo_relaxed.png" alt="Angelo, relaxed. The risk is on us.">
    </div>
  </div>

  <!-- The close -->
  <div class="narrative-bridge">
    <div class="nb-label">Where this leaves you</div>
    <h2>You cannot write your way out of a positioning problem.</h2>
    <p>You can rewrite your homepage. You can hire a copywriter. You can ask an AI to help you.
    None of those things change what your buyer is already thinking before they arrive on your page.
    The only fix is to find out what they are thinking, in their own words, not yours.
    That is a research problem. The Marketing Intelligence File solves it.</p>
    <p>You now have three options.</p>
  </div>

  <div class="three-choices">
    <div class="tc-label">Three options</div>

    <div class="choice-block">
      <div class="cb-num">Option 1</div>
      <h3>Do nothing</h3>
      <p>The strangers who left your page last month will leave it again next month.
      A low score reflects a structural problem. Without new data, the words on your page stay where they are.</p>
    </div>

    <div class="choice-block">
      <div class="cb-num">Option 2</div>
      <h3>Rewrite it yourself</h3>
      <p>Rewrite your homepage using the same instinct that wrote the current version.
      The words will change. The facts behind them will not.</p>
    </div>

    <div class="choice-block">
      <div class="cb-num">Option 3</div>
      <h3>Get the facts</h3>
      <p>For &pound;75, one time, our research engine maps the exact vocabulary your specific buyers
      use when they are ready to spend money. Your page starts working.</p>
    </div>
  </div>

  <!-- CHECKOUT -->
  <div class="checkout-section" id="checkout">
    <div class="cta-angelo-wrap">
      <img class="cta-angelo" src="/angelo_cta.png" alt="Angelo: {bub}">
      <span class="bubble-txt">{bub}</span>
    </div>
    <h2>Get My Marketing Intelligence File</h2>
    <div class="cs-sub">Your niche. Your buyers&rsquo; actual language. &pound;75, one-time. No subscription.</div>
    <div class="checkout-form-placeholder">
      <div class="lock-icon">&#128274;</div>
      <div class="cf-label">Secure checkout</div>
      <div class="cf-note">Card payment integration goes here.<br>
      Stripe / payment processor embed to be wired in.</div>
      <button class="cta-btn" disabled>{buy_btn}</button>
    </div>
    <p class="guarantee">Secure payment &middot; Instant confirmation &middot; Delivered within 5 working days &middot; 7-Day Certainty Guarantee</p>
  </div>

</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # Never cache the tool's HTML, so a code change always shows on a plain refresh (no more stale pages).
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _send_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/angelo.png", "/inter.woff2", "/serif.woff2", "/angelo_up.png", "/angelo_down.png",
                    "/angelo_unsure.png", "/angelo_reading.png", "/angelo_typing.png", "/angelo_file.png",
                    "/angelo_cta.png", "/angelo_relaxed.png", "/angelo_steps.png", "/angelo_plan.png"):
            fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path.lstrip("/"))
            if os.path.exists(fpath):
                ctype = "font/woff2" if path.endswith(".woff2") else "image/png"
                with open(fpath, "rb") as f:
                    self._send_bytes(f.read(), ctype)
            else:
                self.send_response(404); self.end_headers()
            return
        if path == "/offer":
            # The report card links here as /offer?domain=… — the DB key to everything we saved about
            # this coach. Stamp it into <body data-domain> so the checkout wiring (and any onward link
            # to the salespage) can pick it up without a second lookup. No domain = plain generic page.
            _dom = (parse_qs(parsed.query).get("domain", [""])[0]).strip()
            self._send(OFFER_PAGE.replace("__DOMAIN__", html.escape(_dom, quote=True)))
            return
        if path == "/salespage":
            qs = parse_qs(parsed.query)
            domain = (qs.get("domain", [""])[0]).strip()
            if domain:
                row = get_audit(domain)
                if row:
                    # LAZY RETRY: if the audit-time screenshot fetch failed (rate limit, timeout), try once
                    # more now — the salespage is usually visited hours later, so the window has reset.
                    # A success is persisted so every later visit is instant; a failure just shows the
                    # placeholder again, same as before.
                    shot = row.get("screenshot_path", "")
                    if not shot:
                        shot = _save_screenshot(domain)
                        if shot:
                            save_audit(
                                domain=domain,
                                first_name=row.get("first_name", ""),
                                email=row.get("email", ""),
                                headline=row.get("headline", ""),
                                score=row.get("score", ""),
                                tokens=row.get("tokens", ""),
                                screenshot_path=shot,
                                raw_json=row.get("raw_json", ""),
                            )
                    self._send(_render_salespage(
                        first_name = row.get("first_name", "")      or "Coach",
                        headline   = row.get("headline", "")         or "your website text",
                        # No fallback here: when the stored tokens are empty, _render_salespage
                        # falls back to the coach's actual words from the voice sweep instead.
                        tokens     = row.get("tokens", ""),
                        score      = row.get("score", "")            or "0.0",
                        screenshot = shot,
                        raw_json   = row.get("raw_json", ""),
                    ))
                    return
                # Domain recognised but no record yet — fall through to param fallback.
            # Backward-compatibility: read individual URL parameters (immediate post-audit flow).
            first_name = (qs.get("first_name", [""])[0]).strip() or "Coach"
            headline   = (qs.get("headline",   [""])[0]).strip() or "your website text"
            tokens     = (qs.get("tokens",     [""])[0]).strip()   # _render_salespage supplies the generic fallback
            score      = (qs.get("score",      [""])[0]).strip() or "0.0"
            screenshot = (qs.get("screenshot", [""])[0]).strip()
            self._send(_render_salespage(first_name, headline, tokens, score, screenshot))
            return
        if path.startswith("/screenshots/"):
            fname = os.path.basename(path)
            fpath = os.path.join(SCREENSHOTS_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith(".png"):
                with open(fpath, "rb") as f:
                    self._send_bytes(f.read(), "image/png")
            else:
                self.send_response(404); self.end_headers()
            return
        if path == "/audit":   # JUST the report fragment, so the page can fetch it and show live progress
            qs = parse_qs(parsed.query)
            url = (qs.get("url", [""])[0]).strip()
            first_name = (qs.get("first_name", [""])[0]).strip()
            last_name = (qs.get("last_name", [""])[0]).strip()
            email = (qs.get("email", [""])[0]).strip()
            res = audit_url(url) if url else {}
            shot_path = ""
            if url and res.get("ok") and res.get("status") == "ok":
                # OUR OWN RENDER FIRST: the audit's Playwright pass already screenshotted the page
                # (res["thumbnail"], a base64 data URI), so persist THAT to disk — the salespage and
                # every refresh reuse it for free, no third-party call, no quota. Microlink is only
                # the fallback for runs where Playwright produced no image (heavy sites, low-RAM
                # containers) — and _save_screenshot itself reuses a same-day PNG before refetching.
                _shot_key = res.get("page_display") or res.get("domain", url)   # subpages get their own PNG
                shot_path = _save_playwright_shot(_shot_key, res.get("thumbnail", ""))
                if not shot_path:
                    shot_path = _save_screenshot(_shot_key)
                if not res.get("thumbnail") and shot_path:
                    res["thumbnail"] = shot_path
            frag = render_result(res, first_name=first_name) if url else ""
            # Subpage audits are never SAVED: the DB record for a domain is its homepage audit (the
            # salespage and email funnel key off it), and a subpage result must not overwrite that.
            if url and res.get("ok") and res.get("status") == "ok" and res.get("is_home", True):
                # Strip the thumbnail before serialising — a base64 blob is huge, and a /screenshots/ path
                # is re-injected fresh on every request anyway, so the stored JSON never needs it.
                storable = {k: v for k, v in res.items() if k != "thumbnail"}
                tokens_raw = res.get("generic_tokens_found", [])
                tokens_str = (", ".join(tokens_raw) if isinstance(tokens_raw, list)
                              else str(tokens_raw or ""))
                save_audit(
                    domain=res.get("domain", url),
                    first_name=first_name,
                    email=email,
                    headline=res.get("hero_quote", ""),
                    score=str(res.get("score_10", "")),
                    tokens=tokens_str,
                    screenshot_path=shot_path,
                    raw_json=_json.dumps(storable),
                )
                salespage_url = f"{APP_BASE_URL}/salespage?domain={res.get('domain', url)}"
                threading.Thread(
                    target=_push_mailerlite,
                    args=(
                        email, first_name, last_name,
                        res.get("hero_quote", ""),
                        tokens_raw,
                        res.get("global_score", ""),
                        salespage_url,
                    ),
                    daemon=True,
                ).start()
            self._send(frag)
            return
        if path not in ("/", ""):
            self.send_response(404); self.end_headers(); return
        qs = parse_qs(parsed.query)
        url = (qs.get("url", [""])[0]).strip()
        result_html = ""
        if url:
            res = audit_url(url)
            if res.get("ok") and res.get("status") == "ok" and not res.get("thumbnail"):
                # Same microlink fallback as /audit — a refresh or shared link must never lock in the
                # placeholder. Cheap on repeat views: _save_screenshot reuses a same-day PNG from disk.
                _sp = _save_screenshot(res.get("page_display") or res.get("domain", url))
                if _sp:
                    res["thumbnail"] = _sp
            result_html = render_result(res, first_name=(qs.get("first_name", [""])[0]).strip())
        page = PAGE.format(url_value=html.escape(url, quote=True), result=result_html,
                           count=f"{websites_read_count():,}", mascot=mascot_img())
        self._send(page.replace("<!--PROGRESS-->", PROGRESS_UI))

    def log_message(self, *a):
        pass  # quiet


if __name__ == "__main__":
    print(f"\n  Coaching Website Audit is running.")
    print(f"  Open this in your browser:  http://localhost:{PORT}\n")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
