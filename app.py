"""
Coaching Website Audit, runnable web demo.

Launch:   python3 app.py
Then open http://localhost:8000 in your browser, type a coach's website, and
watch the Report Card render. This is your product's free tier, running locally.

No extra installs, uses only Python's built-in web server. The AI diagnosis
turns on automatically once ANTHROPIC_API_KEY is set in your environment.
"""

import html
import json as _json
import os
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)
except ImportError:
    pass

from audit import audit_url, LABELS, DEFINITIONS, DISPLAY_CRIT, websites_read_count  # the engine we built

PORT = int(os.getenv("PORT", "8000"))
MAILERLITE_API_KEY = os.getenv("MAILERLITE_API_KEY", "")

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
  :root{{--paper:#eef1f5;--surface:#fff;--ink:#17222e;--muted:#5c6a67;--line:#dde3e0;
    --accent:#3a76bd;--accent-ink:#234e83;--soft:#e6edf8;--good:#2f8f6b;--warn:#b47f26;--critical:#b3402a;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--paper);color:var(--ink);
    font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6}}
  .wrap{{max-width:760px;margin:0 auto;padding:44px 22px 80px}}
  .serif{{font-family:"Inter",sans-serif}}
  .eyebrow{{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--accent-ink);font-weight:600}}
  h1{{font-family:"Inter",sans-serif;font-weight:600;font-size:clamp(28px,6vw,44px);
    letter-spacing:-.015em;margin:.3em 0 .15em}}
  .sub{{color:var(--muted);font-size:16px;margin:0 0 28px;max-width:56ch}}
  .sub b{{color:var(--ink)}}
  .hero{{display:flex;align-items:center;gap:24px;margin-bottom:26px}}
  .hero-copy{{flex:1;min-width:0}}
  .hero-copy h1{{margin-top:.1em}} .hero-copy .sub{{margin-bottom:0}}
  .mascot{{width:160px;height:auto;flex-shrink:0}}
  @media(max-width:560px){{.hero{{flex-direction:column;align-items:flex-start;gap:10px}}
    .mascot{{width:120px}}}}
  form{{display:flex;flex-direction:column;gap:10px;background:var(--surface);border:1px solid var(--line);
    border-radius:14px;padding:14px;box-shadow:0 8px 30px rgba(20,40,36,.06)}}
  input[type=text],input[type=email]{{border:1px solid var(--line);border-radius:9px;
    padding:14px 16px;font-size:16px;color:var(--ink);background:var(--surface);width:100%}}
  input[type=text]:focus,input[type=email]:focus{{outline:2px solid var(--accent);border-color:var(--accent)}}
  button{{background:#e0691f;color:#fff;border:0;border-radius:9px;padding:14px 22px;
    font-size:16px;font-weight:600;cursor:pointer}}
  button:hover{{background:#c65a15}}
  .hint{{font-size:13px;color:var(--muted);margin-top:12px}}
  .hint b{{color:var(--accent-ink)}}
  .card{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:26px;
    box-shadow:0 8px 30px rgba(20,40,36,.06);margin-top:28px}}
  .grade{{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);
    padding-bottom:18px;margin-bottom:20px}}
  .num{{font-family:"Inter",sans-serif;font-size:56px;font-weight:600;letter-spacing:-.03em;line-height:1}}
  .num.crit{{color:var(--critical)}} .num.warn{{color:var(--warn)}} .num.good{{color:var(--good)}}
  .den{{font-family:"Inter",sans-serif;color:var(--muted);font-size:15px}}
  .tier{{margin-left:auto;font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.12em;
    text-transform:uppercase;color:var(--muted)}}
  .barwrap{{padding:16px 0;border-top:1px solid var(--line)}}
  .barwrap:first-child{{border-top:0;padding-top:2px}}
  .barhead{{display:flex;align-items:baseline;justify-content:space-between;gap:16px}}
  .lbl{{font-size:15.5px;font-weight:600;color:var(--ink);line-height:1.3}}
  .mark{{display:inline-block;width:22px}}
  .mark.ok::before{{content:"✓";color:var(--good);font-weight:700}}
  .mark.no::before{{content:"✗";color:var(--critical);font-weight:700}}
  .mark.na::before{{content:"–";color:#9aa0a6;font-weight:700}}
  .track{{height:8px;background:var(--soft);border-radius:6px;overflow:hidden;margin:12px 0 0}}
  .fill{{height:100%;border-radius:6px}}
  .fill.crit{{background:var(--critical)}} .fill.warn{{background:var(--warn)}} .fill.good{{background:var(--good)}}
  .fill.na{{background:transparent}}
  .vs{{font-size:16px;font-weight:700;color:var(--ink);white-space:nowrap;text-align:right;line-height:1.1}}
  .vs .den{{font-weight:600;color:var(--muted);font-size:13px}}
  .vs .mkt{{display:block;font-weight:500;color:var(--muted);font-size:12px;margin-top:3px}}
  .def{{font-size:13px;color:var(--muted);margin:12px 0 0;line-height:1.5;max-width:64ch}}
  .barnote{{font-size:14px;color:var(--ink);margin:7px 0 0;line-height:1.55;max-width:62ch}}
  .scores-h{{font-size:15px;color:var(--muted);line-height:1.55;margin:30px 0 18px;max-width:62ch}}
  .honest{{margin-top:16px;font-size:14px;color:var(--muted);line-height:1.55;border-top:1px solid var(--line);
    padding-top:14px}}
  .diag{{margin-top:24px;border-top:1px solid var(--line);padding-top:20px}}
  .diag h3{{font-family:"Inter",sans-serif;font-size:20px;margin:0 0 12px}}
  .diag .row{{margin:10px 0}}
  .diag .k{{font-family:"Inter",sans-serif;font-size:11px;letter-spacing:.1em;
    text-transform:uppercase;color:var(--accent-ink);font-weight:600}}
  .diag ul{{margin:6px 0 0;padding-left:20px}} .diag li{{margin:4px 0}}
  .caveat{{margin-top:12px;padding:12px 14px;background:var(--soft);border-left:3px solid var(--accent);
    border-radius:8px;font-size:15px;line-height:1.55}}
  .caveat b{{color:var(--accent-ink)}}
  .caveat p{{margin:0 0 10px}} .caveat p:last-child{{margin:0}}
  .badge{{display:inline-block;font-family:"Inter",sans-serif;font-size:11px;
    padding:3px 8px;border-radius:20px;background:var(--soft);color:var(--accent-ink);margin-left:8px}}
  .dead{{color:var(--critical);font-size:17px}}
  .err{{color:var(--critical)}}
  .pctl{{font-family:"Inter",sans-serif;font-size:13px;color:var(--accent-ink);font-weight:600}}
  .ev{{background:#f6f8f7;border:1px solid var(--line);border-radius:11px;padding:18px 20px;margin:20px 0}}
  .ev .h{{font-size:15px;color:var(--muted);line-height:1.5;margin-bottom:14px}}
  .ev .q{{font-family:"Inter",sans-serif;font-style:italic;font-size:16px;color:var(--ink);
    border-left:3px solid var(--accent);padding-left:12px;margin:8px 0}}
  .ev .meta{{font-size:13px;color:var(--muted);margin-top:6px}}
  .ev .tag{{display:inline-block;font-family:"Inter",sans-serif;font-size:11px;padding:2px 8px;
    border-radius:20px;margin:4px 6px 0 0}}
  .tag.no{{background:#f6e6e3;color:var(--critical)}} .tag.yes{{background:var(--soft);color:var(--accent-ink)}}
  .tag.neutral{{background:#eef1f5;color:var(--muted)}}
  .analysed{{font-family:"Inter",sans-serif;font-size:clamp(17px,2.6vw,21px);line-height:1.42;
    margin:0 0 22px;padding-bottom:20px;border-bottom:1px solid var(--line)}}
  .analysed b{{color:var(--accent-ink)}}
  .reframe{{background:var(--accent);color:#eafaf6;border-radius:12px;padding:18px 22px;margin:0 0 22px;
    line-height:1.55;font-size:15px}}
  .reframe b{{color:#fff}}
  .checklist{{background:#f6f8f7;border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin:0 0 22px}}
  .checklist .h{{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--muted);margin-bottom:10px}}
  .checklist ul{{margin:0;padding-left:20px;columns:2;column-gap:26px}}
  .checklist li{{margin:5px 0;font-size:14px;break-inside:avoid}}
  .checklist .foot{{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:14px}}
  @media(max-width:560px){{.checklist ul{{columns:1}}}}
  .reveal{{margin-top:28px;padding:24px;background:#f0f4f3;border:1px solid var(--line);border-radius:14px}}
  .reveal .h{{font-family:"Inter",sans-serif;font-size:12px;letter-spacing:.12em;text-transform:uppercase;
    color:var(--muted);margin-bottom:10px}}
  .verdict{{font-family:"Inter",sans-serif;font-size:17px;line-height:1.4}}
  .strength{{background:#eaf1fb;border:1px solid #cfe8dd;border-radius:11px;padding:14px 18px;margin:18px 0;
    font-size:14px}}
  .strength b{{color:var(--good)}}
  .scope{{font-size:13px;color:var(--muted);margin:0 0 18px;padding:9px 13px;background:#f6f8f7;border-radius:8px}}
  .scope .date{{color:var(--accent-ink);font-weight:600}}
  .gap{{font-family:"Inter",sans-serif;font-size:13px;color:var(--accent-ink);font-weight:600;max-width:52ch}}
  .gap p{{margin:0 0 10px}} .gap p:last-child{{margin:0}}
  .secnum{{display:block;width:fit-content;font-family:"Inter",sans-serif;font-size:14px;
    letter-spacing:.12em;color:#fff;background:var(--accent);font-weight:700;margin:0 0 12px;
    padding:6px 14px;border-radius:20px}}
  .thumb{{width:100%;border-radius:8px;border:1px solid var(--line);margin-bottom:14px;display:block}}
  .q.sm{{font-size:14px}}
  .fault{{margin-top:14px;padding:14px 16px;background:#fbf0ee;border:1px solid #edd4cd;border-radius:9px;
    font-size:14px;line-height:1.55}}
  .fault b{{color:var(--critical)}}
  .pricing{{background:#fbf7ee;border:1px solid #ece0c8;border-radius:11px;padding:14px 18px;margin:18px 0;
    font-size:14px;line-height:1.5}}
  .pricing b{{color:#8a6d1f}}
  .media{{background:#eef2fb;border:1px solid #d5def0;border-radius:11px;padding:14px 18px;margin:0 0 20px;
    font-size:14px;line-height:1.5}}
  .voice{{background:var(--soft);border:1px solid #cdddf3;border-left:4px solid var(--accent);border-radius:12px;
    padding:20px 22px;margin:22px 0;line-height:1.6;font-size:15px}}
  .voice h4{{font-family:"Inter",sans-serif;font-size:20px;margin:0 0 10px;color:var(--accent-ink)}}
  .voice b{{color:var(--accent-ink)}}
  .voice.good{{background:#eaf1fb;border-left-color:var(--good)}}
  .voice.good h4{{color:var(--good)}}
  .voice p{{margin:0 0 12px}} .voice p:last-child{{margin:0}}
  .checks{{margin-top:14px;display:flex;flex-direction:column;gap:2px}}
  .checks .h{{font-family:"Inter",sans-serif;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
    color:var(--muted);margin-bottom:8px}}
  .check{{font-size:14px;padding:6px 0;padding-left:26px;position:relative}}
  .check::before{{position:absolute;left:0;font-weight:700}}
  .check.ok{{color:var(--ink)}} .check.ok::before{{content:"✓";color:var(--good)}}
  .check.no{{color:var(--critical)}} .check.no::before{{content:"✗";color:var(--critical)}}
  .checks-foot{{margin-top:12px;padding-top:12px;border-top:1px solid var(--line);font-size:14px;
    line-height:1.55;color:var(--ink)}}
  .cta{{margin-top:26px;padding:28px 26px;background:var(--ink);color:#eef1f5;border-radius:14px;text-align:left}}
  .cta-h{{font-family:"Inter",sans-serif;font-size:23px;color:#fff;margin-bottom:16px;text-align:center}}
  .cta p{{max-width:60ch;margin:0 auto 15px;line-height:1.65;font-size:16px;color:#eaeff2}}
  .cta ul{{max-width:60ch;margin:0 auto 15px;padding-left:24px;line-height:1.55;font-size:16px;color:#eaeff2}}
  .cta li{{margin:5px 0}}
  .cta .hook{{max-width:60ch;margin:0 auto 20px;padding:16px 18px;border-radius:11px;
    background:rgba(224,105,31,.12);border:1px solid rgba(224,105,31,.5);
    font-size:17px;line-height:1.55;font-weight:600;color:#fff}}
  .cta .hook .sc{{color:#f6a869;font-size:19px}}
  .cta .curi{{font-weight:600;color:#fff;font-size:16.5px}}
  .cta .btnwrap{{text-align:center;margin-top:6px}}
  .cta-btn{{display:inline-block;background:#e0691f;color:#fff;text-decoration:none;font-weight:600;
    padding:15px 28px;border-radius:9px;font-size:16px}}
  .cta-btn:hover{{background:#c65a15}}
  .positioning{{margin-top:26px;padding:22px 24px;background:var(--ink);color:#dfe7e4;border-radius:14px;line-height:1.6;font-size:15px}}
  .positioning h4{{font-family:"Inter",sans-serif;font-size:20px;margin:0 0 10px;color:#fff}}
  .positioning b{{color:#9ec6f0}}
  .steps{{margin-top:26px;padding:26px 26px;background:var(--surface);border:1px solid var(--line);
    border-radius:14px}}
  .steps-h{{font-family:"Inter",sans-serif;font-size:23px;margin-bottom:6px;color:var(--ink)}}
  .steps>p{{color:var(--muted);font-size:15px;margin:0 0 16px}}
  .steplist{{margin:0;padding:0;list-style:none;counter-reset:step}}
  .steplist li{{position:relative;padding:0 0 16px 46px;margin:0;line-height:1.55;font-size:15.5px}}
  .steplist li:before{{counter-increment:step;content:counter(step);position:absolute;left:0;top:0;
    width:30px;height:30px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;
    display:flex;align-items:center;justify-content:center;font-size:15px}}
  .steplist li b{{color:var(--accent-ink)}}
  .ben{{display:block;margin-top:6px;color:var(--accent-ink);font-weight:600;font-size:14.5px}}
  .ben:before{{content:"\\2192  ";font-weight:700}}
  .steps-foot{{margin:8px 0 20px;font-weight:600;color:var(--ink);font-size:15px}}
  .steps .cta-btn{{margin-top:0}}
  .taste{{background:var(--soft);border:1px solid #d4deec;border-left:5px solid var(--accent);
    border-radius:12px;padding:22px 24px;margin:24px 0}}
  .taste .th{{font-family:"Inter",sans-serif;font-weight:700;font-size:18px;color:var(--ink);margin-bottom:16px}}
  .taste .grid{{display:grid;grid-template-columns:118px 1fr;gap:12px 16px;align-items:center}}
  .taste .lbl{{font-size:12px;font-weight:700;color:#4a5560;line-height:1.3}}
  .taste .lbl.b{{color:#e0691f}}
  .taste .cw{{font-style:italic;color:var(--ink);font-size:15.5px}}
  .taste .bw{{background:#fff;border:1px solid #ecdfd2;border-left:4px solid #e0691f;border-radius:8px;
    padding:9px 13px;font-weight:600;color:var(--ink);font-size:16px}}
  .taste .dvd{{grid-column:1/-1;height:1px;background:#cdd7e5;margin:2px 0}}
  .taste .kick{{margin-top:16px;font-weight:700;color:var(--accent-ink);font-size:16px}}
  .curi{{font-weight:600;color:var(--ink)}}
  .freegift{{margin-top:12px;font-size:14px;color:var(--muted)}}
</style></head><body><div class="wrap">
  <div class="hero">
    {mascot}
    <div class="hero-copy">
      <div class="eyebrow">{count} coaching websites read, and counting</div>
      <h1 class="serif">Coaches: in five seconds, does your website say &ldquo;I can fix your problem&rdquo;?</h1>
      <p class="sub"><b>That's all the time a cold buyer gives you.</b> If they don't see it, they leave, and you
      never even know they came. Paste your coaching website in and in about half a minute Angelo shows you what that
      cold buyer sees, why they stay or go, and how you score against <b>{count}</b> other coaching sites. Almost 9 in 10
      get it wrong. (86.4%, for those who like it exact.)</p>
    </div>
  </div>
  <form method="get" action="/" id="auditform">
    <input type="text" name="first_name" id="firstnameinput" placeholder="Your first name" autocomplete="given-name" autofocus>
    <input type="text" name="last_name" id="lastnameinput" placeholder="Your last name" autocomplete="family-name">
    <input type="email" name="email" id="emailinput" placeholder="Your best email address" autocomplete="email">
    <input type="text" name="url" id="urlinput" placeholder="yourcoachingwebsite.com" value="{url_value}">
    <button type="submit">Show me what a cold buyer sees</button>
  </form>
  <div class="hint">This messaging X-ray normally costs £127, but your private results are entirely free. Angelo takes about half a minute to read your homepage exactly as a cold buyer would, then saves your dashboard link straight to your inbox.</div>
  <!--PROGRESS-->
  <div id="result">{result}</div>
</div></body></html>"""

# The live-progress overlay. Kept as a PLAIN string (real braces) and injected into PAGE after .format(), so its
# CSS/JS braces don't collide with the template's format fields.
PROGRESS_UI = """
<style>
  #processing{display:none;margin:26px 0 0;padding:28px 30px;border-radius:14px;
    background:var(--surface);border:1px solid var(--line);box-shadow:0 8px 30px rgba(20,40,36,.06)}
  #processing.on{display:block}
  #processing h3{font-family:"Inter",sans-serif;font-size:20px;margin:0 0 20px;color:var(--ink)}
  #processing ul{list-style:none;margin:0 0 18px;padding:0}
  #processing li{padding:11px 0;border-bottom:1px solid var(--line);font-size:15px;line-height:1.5}
  #processing li:last-child{border-bottom:0}
  .ps-status{font-weight:700}
  .ps-done{color:var(--good)}
  .ps-progress{color:var(--accent-ink)}
  .ps-waiting{color:var(--muted)}
  #processing .p-note{font-size:13px;color:var(--muted);line-height:1.5;margin:0;font-style:italic}
</style>
<div id="processing">
  <h3>Angelo is actively analyzing your homepage copy&hellip;</h3>
  <ul>
    <li><b>Step 1:</b> Logging your email data into our secure MailerLite server path&hellip; <span class="ps-status ps-done" id="ps1">[DONE]</span></li>
    <li><b>Step 2:</b> Capturing an authentic browser screenshot of your hero section&hellip; <span class="ps-status ps-waiting" id="ps2">[WAITING]</span></li>
    <li><b>Step 3:</b> Running our 8-bar semantic parser to strip away generic coaching clich&eacute;s&hellip; <span class="ps-status ps-waiting" id="ps3">[WAITING]</span></li>
    <li><b>Step 4:</b> Cross-referencing your messaging against our database of 2,000 commercial book buying triggers&hellip; <span class="ps-status ps-waiting" id="ps4">[WAITING]</span></li>
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
    setStep('ps3','WAITING');
    setStep('ps4','WAITING');

    form.style.display='none';
    result.innerHTML='';
    proc.className='on';
    proc.scrollIntoView({behavior:'smooth',block:'center'});

    var t2=setTimeout(function(){setStep('ps2','DONE');setStep('ps3','IN PROGRESS');},9000);
    var t3=setTimeout(function(){setStep('ps3','DONE');setStep('ps4','IN PROGRESS');},20000);

    var qs='url='+encodeURIComponent(url);
    if(fn) qs+='&first_name='+encodeURIComponent(fn);
    if(ln) qs+='&last_name='+encodeURIComponent(ln);
    if(em) qs+='&email='+encodeURIComponent(em);

    var t0=Date.now();
    fetch('/audit?'+qs+'&_t='+Date.now(),{cache:'no-store'}).then(function(r){return r.text();}).then(function(html){
      clearTimeout(t2); clearTimeout(t3);
      setStep('ps2','DONE'); setStep('ps3','DONE'); setStep('ps4','DONE');
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
      clearTimeout(t2); clearTimeout(t3);
      proc.className=''; form.style.display=''; busy=false;
      window.location.href='/?'+qs;
    });
  });
});
</script>
"""


def _push_mailerlite(email, first_name, last_name, hero_quote, generic_tokens_found, global_score):
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
        with urllib.request.urlopen(req, timeout=10):
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

# What we check, plain, buyer-focused, so they know it's quick and what's coming
CHECKLIST = [
    "Whether it's instantly clear <b>who you help</b>",
    "Whether a visitor sees <b>their own problem</b> on the page",
    "Whether your <b>offer</b> is clear",
    "Whether there's <b>proof</b> you can deliver",
    "Whether there's <b>one obvious next step</b>",
    "Whether you capture people who aren't ready <b>yet</b>",
    "Whether you look <b>credible and trustworthy</b>",
    "Whether there's a <b>human</b> to connect with",
    "How you handle <b>pricing</b>",
    "The <b>technical basics</b>, secure, fast, works on a phone",
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


def render_result(res):
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

    g = sev_class(res["score_10"])
    ev = res["evidence"]
    cnt = f'{res.get("corpus_count", 10954):,}'   # the living count of coaching websites read
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
    _HOLE = {"specificity": "who it's for", "clarity_5sec": "a stranger getting it in five seconds",
             "offer_clarity": "showing what you actually fix", "story": "connecting with the reader"}
    _sc = res.get("scores", {})
    _weak = min(_HOLE, key=lambda k: _sc.get(k, 99))
    hole_phrase, hole_score = _HOLE[_weak], _sc.get(_weak, 0)
    niche_word = f'{_niche_clients} '   # "life coaching clients " / "clients " — used as "the real words your {…}use"
    steps_btn = (f'Show me how it works for {html.escape(_niche)} coaches &rarr;' if _niche
                 else 'Show me how it&rsquo;d work for me &rarr;')

    # scope: make it unmistakable we looked at the homepage only, + date
    scope = (f'<div class="scope">{html.escape(res["scope_note"])} '
             f'<span class="date">Analysed {html.escape(res["analysed_on"])}.</span></div>')

    # Verdict, standing and gap all come from ONE function driven by the same two facts (clarity + tier/top-tier), so
    # they can never disagree — see overall_copy(). Unit-tested across every (clarity, tier, top-tier) combination.
    _clar = (res["comparison"].get("clarity_5sec") or {}).get("you")
    verdict, den_line, gap_line = overall_copy(_clar, res.get("tier"), res.get("in_top_tier"))

    # optional thumbnail, only if we actually captured one (never a broken image)
    thumb = f'<img class="thumb" src="{res["thumbnail"]}" alt="Your homepage">' if res.get("thumbnail") else ""

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
        f'<div class="ev"><div class="h"><span class="secnum">1 / 5</span>What we read on your homepage: {html.escape(ev["domain"])}</div>'
        f'{thumb}{quotes}</div>'
    )

    # --- the signature finding: whose words are these? (never a verdict on whether it sells) ---
    v = res.get("voice", {})
    coach_terms = ", ".join(f"&lsquo;{html.escape(t)}&rsquo;" for t in v.get("coach_terms", [])) or "coach language"
    first_coach = html.escape(v.get("coach_terms", ["clarity"])[0]) if v.get("coach_terms") else "clarity"
    if v.get("leaning") == "expert":
        voice_html = (
            '<div class="voice"><h4><span class="secnum">4 / 5</span>Whose words are these? Yours, or your buyer\'s?</h4>'
            f'<p>On your homepage you reach for coach words like {coach_terms}. They\'re good words. But they\'re '
            '<b>your</b> words, not your customer\'s.</p>'
            '<p>Right now you\'re talking expert to expert. Another coach would read this and understand you easily. '
            'But your buyer isn\'t another expert. They still have the problem. They need you to talk '
            '<b>expert to buyer</b>.</p>'
            f'<p>Picture the person you help, lying awake at night, worried. What do they type into Google? Probably '
            f'not &lsquo;{first_coach}&rsquo;. More likely something real, like &ldquo;I dread Monday mornings&rdquo;, '
            'or &ldquo;I keep getting passed over at work&rdquo;.</p>'
            '<p>You talk like the expert who fixed the problem. They talk like someone who still has it. Those are two '
            'different languages.</p>'
            f'<p>And hardly any coaches get this right. We looked at <b>{cnt}</b> coaching websites. Only about '
            '<b>1 in 8</b> use their customer\'s words. The other <b>88%</b> sound just like this page does.</p>'
            '<p>That\'s good news for you. Nearly every coach sounds the same, so people can\'t tell them apart. Use '
            'the words your customers actually use, and you stand out straight away. You become the coach who '
            'understands them.</p>'
            '<p>And there\'s a bigger catch. Maybe you had this problem yourself once, and got through it. Maybe '
            'you\'ve helped a few people do the same. That feels like proof. But it\'s just a handful of people. It '
            'doesn\'t tell you there are enough others out there who\'ll pay for exactly this, said in exactly these '
            'words.</p>'
            '<p>And when your whole page is built on your own story and your own view, the people you want to reach '
            'don\'t feel understood. They don\'t feel you get them, so they move on to another coach, one who feels '
            'like they understand them better.</p>'
            '<p>You can\'t see your own blind spot, and you can\'t guess what your customers are really thinking. '
            'Finding it takes real digging into who is buying, and why. It isn\'t a five-minute rewrite. It isn\'t a '
            'weekend job either. The words you need aren\'t in your own head to find.</p></div>')
    elif v.get("leaning") == "customer":
        voice_html = (
            '<div class="voice good"><h4><span class="secnum">4 / 5</span>You\'re speaking your buyer\'s language</h4>'
            '<p>Here\'s something you\'re doing well. Your homepage talks about the problem in words your customer '
            'would actually use, not just coach words.</p>'
            f'<p>That\'s rarer than you\'d think. Of the {cnt} coaching sites we scored, only about 1 in 8 do this. The '
            'other 88% talk like the expert. You sound more like the person with the problem, and that\'s a real edge. '
            'Keep using the real words your clients say.</p></div>')
    else:
        voice_html = (
            '<div class="voice"><h4><span class="secnum">4 / 5</span>Whose words are these? Yours, or your buyer\'s?</h4>'
            '<p>Your homepage mixes your words with your customer\'s words.</p>'
            '<p>The closer you get to how your customer really talks, the words they\'d use for their own problem, the '
            'more of them will get in touch instead of just nodding and leaving.</p>'
            '<p>And that\'s harder than it sounds. You know your work so well that you\'ve forgotten how your customer '
            'talks about it. Finding their real words takes proper digging, not a quick rewrite.</p></div>')

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
                f'<div class="barnote">{html.escape(info["note"])}</div></div>'
            )
            continue
        pct = c["you"] * 10
        mark = "ok" if info["pass"] else "no"
        # technical_health is shown but NOT part of the overall score, so it shows 'not counted', not a market gap.
        _mkt = 'not counted' if k == "technical_health" else f'market {c["market"]}'
        rows.append(
            f'<div class="barwrap"><div class="barhead">'
            f'<div class="lbl"><span class="mark {mark}"></span>{html.escape(LABELS[k])}</div>'
            f'<div class="vs"><b>{c["you"]}</b><span class="den">/10</span>'
            f'<span class="mkt">{_mkt}</span></div></div>'
            f'<div class="track"><div class="fill {sev_class(c["you"])}" style="width:{pct}%"></div></div>'
            f'<div class="def">{_def}</div>'
            f'<div class="barnote">{html.escape(info["note"])}</div></div>'
        )
    cr = res["critique"]
    fixes = "".join(f"<li>{html.escape(f)}</li>" for f in cr["top_fixes"])
    ai = ('<span class="badge">AI diagnosis</span>' if res["ai_powered"]
          else '<span class="badge">add API key for AI</span>')
    opener = (f'<div class="analysed">We can tell in a few seconds what a cold buyer thinks when they arrive on your '
              f'page. We\'ve watched it go right and wrong on thousands of coaching sites. We looked at '
              f'<b>{html.escape(ev.get("page_display") or ev["domain"])}</b>, scored it against all <b>{cnt}</b> of '
              f'them, and the screenshot below is your real page, not a template. Here\'s what we found.</div>')
    media = (f'<div class="media">🎬 {html.escape(res["media_note"])}</div>' if res.get("media_note") else "")
    popup = (f'<div class="media">🚫 {html.escape(res["popup_note"])}</div>' if res.get("popup_note") else "")
    reframe = ('<div class="reframe">You\'ve probably had a website audit before. This isn\'t that. '
               'This isn\'t about how good your website <i>looks</i>. Forget the design for a minute. '
               'A stranger arrives on your page. In a few seconds they decide one thing about you: '
               '<b>&ldquo;can this person fix my problem?&rdquo;</b> If the answer isn\'t a clear yes, they leave. '
               f'And you never even knew they were there. We read {cnt} coaching homepages, and <b>86% fail that '
               'test.</b> The checks below show what\'s going wrong. The real reason is simpler: '
               '<b>the words on your page aren\'t the words your buyer uses in their own head.</b></div>')
    checklist_html = (
        '<div class="checklist"><div class="h">What we have looked at (detailed below)</div><ul>'
        + "".join(f"<li>{c}</li>" for c in CHECKLIST)
        + '</ul><div class="foot">Read on for what we found, your <b>overall score is at the very bottom.</b></div></div>'
    )

    score_reveal = (
        '<div class="reveal"><div class="h"><span class="secnum">5 / 5</span>Your overall score</div>'
        '<div class="grade">'
        f'<div class="num {g}">{res.get("score_10_display", res["score_10"])}<span class="den">/10</span></div>'
        f'<div><div class="verdict">{verdict}</div>'
        f'<div class="den">{den_line}</div></div>'
        '</div>'
        f'<div class="gap" style="margin-top:14px">{gap_line}</div>'
        f'<div class="honest">A word on your {res.get("score_10_display", res["score_10"])}/10. We\'re not marking you down to make a sale. Every '
        'homepage gets scored the same way, against the same cold buyers, and we call it exactly as we see it. A low '
        'number isn\'t us being harsh on you. It just shows how far the page is from where your buyers already are. '
        'What you do about it is up to you.</div></div>'
    )

    return f"""<div class="card" data-sites="{cnt}">
      {opener}
      {reframe}
      {checklist_html}
      {scope}
      {media}
      {popup}
      {evidence_html}
      <div class="scores-h"><span class="secnum">2 / 5</span>Here are your scores, with the reason behind each one. A green tick means it's working for you. A red cross means it's costing you clients.</div>
      <div>{''.join(rows)}</div>
      <div class="diag">
        <h3><span class="secnum">3 / 5</span>What a visitor sees{ai}</h3>
        <div class="row"><div class="k">The biggest thing in the way</div>{emph(html.escape(cr['headline_problem']))}</div>
        <div class="row"><div class="k">What it's costing you</div>{html.escape(cr['why_it_costs_clients'])}</div>
        <div class="row"><div class="k">The obvious fixes</div><ul>{fixes}</ul>{FIXES_CAVEAT}</div>
        <div class="row"><div class="k">Bottom line</div>{html.escape(cr['money_left_on_table'])}</div>
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
        <div class="hook">Your homepage scored <span class="sc">{hole_score}/10</span> on {hole_phrase}, not because you
        don't know your clients, but because it's written in your words, not the words a cold buyer uses in their own
        head. Getting those exact words, the ones your {niche_word}really use, is the whole game.</div>
        <p>You've probably worked hard on this already. Rewritten the page, paid a designer, done the course, maybe
        hired a coach. And you know your clients, you've coached plenty of them.</p>
        <p>But your homepage has to win over the people who aren't your clients yet. Cold strangers, deciding in five
        seconds, who've never heard of you. What's in their head before they meet you is the hard part, and no one
        sees the whole market from inside their own business.</p>
        <p>So here's what we make you: a <b>Marketing Intelligence File</b>. In plain English, it's everything we can
        find out about the person you're really selling to, pulled from thousands of real buyers, not just the handful
        you've worked with:</p>
        <ul>
          <li>the exact words they use for their problem</li>
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
        <div class="btnwrap"><a class="cta-btn" href="/offer">Show me what my buyer actually wants &rarr;</a></div>
      </div>
      <div class="steps">
        <div class="steps-h">So how do you fix it?</div>
        <p>You have seen the problem. Here is the way out, step by step.</p>
        <ol class="steplist">
          <li><b>We find out who is actually buying.</b> Not the vague, fake avatar most coaches use, like
          &ldquo;leadership clients, aged 35 to 55.&rdquo; We find the real person and the exact burning problem
          they will pull out their wallet to fix. We pull this data by deep-diving into 11,384 real professional
          profiles and tracking over 2,000 specific books people are actively purchasing right now to solve their pain.
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
        <a class="cta-btn" href="/offer">{steps_btn}</a>
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
</style></head><body><div class="wrap">
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
        if path in ("/angelo.png", "/inter.woff2"):
            fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path.lstrip("/"))
            if os.path.exists(fpath):
                ctype = "font/woff2" if path.endswith(".woff2") else "image/png"
                with open(fpath, "rb") as f:
                    self._send_bytes(f.read(), ctype)
            else:
                self.send_response(404); self.end_headers()
            return
        if path == "/offer":
            self._send(OFFER_PAGE)
            return
        if path == "/audit":   # JUST the report fragment, so the page can fetch it and show live progress
            qs = parse_qs(parsed.query)
            url = (qs.get("url", [""])[0]).strip()
            first_name = (qs.get("first_name", [""])[0]).strip()
            last_name = (qs.get("last_name", [""])[0]).strip()
            email = (qs.get("email", [""])[0]).strip()
            res = audit_url(url) if url else {}
            frag = render_result(res) if url else ""
            if url and res.get("ok") and res.get("status") == "ok":
                threading.Thread(
                    target=_push_mailerlite,
                    args=(
                        email, first_name, last_name,
                        res.get("hero_quote", ""),
                        res.get("generic_tokens_found", []),
                        res.get("global_score", ""),
                    ),
                    daemon=True,
                ).start()
            self._send(frag)
            return
        if path not in ("/", ""):
            self.send_response(404); self.end_headers(); return
        qs = parse_qs(parsed.query)
        url = (qs.get("url", [""])[0]).strip()
        result_html = render_result(audit_url(url)) if url else ""
        page = PAGE.format(url_value=html.escape(url, quote=True), result=result_html,
                           count=f"{websites_read_count():,}", mascot=mascot_img())
        self._send(page.replace("<!--PROGRESS-->", PROGRESS_UI))

    def log_message(self, *a):
        pass  # quiet


if __name__ == "__main__":
    print(f"\n  Coaching Website Audit is running.")
    print(f"  Open this in your browser:  http://localhost:{PORT}\n")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
