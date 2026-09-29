"""The Buying Triggers page — the first door into the funnel.

A coach tells us their niche, we send them the buying triggers for it. What sits behind it is the
book research: what each market actually buys, read through the buying-trigger lenses. "Best
sellers" must NOT appear in copy a coach reads: it points them at a shortcut they can take alone.
The frameworks and the counts stay on our side of the wall. They never appear on a page a coach sees.

Nothing here touches the coaching-website corpus. That is the audit's job, and it is the NEXT step.
"""
import html
import json
import re
import os

import brand as _brand   # palette, nav and footer

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_HERE, "triggers_data.json")

# Loaded once at import. ~1.4MB of research; the browser never sees it, it only gets the name list.
try:
    with open(_DATA_PATH, encoding="utf-8") as _f:
        DATA = json.load(_f)
except Exception:                      # a missing data file must not take the whole site down
    DATA = {"niches": {}, "subniches": {}, "totals": {}}

NICHES = DATA.get("niches", {})
SUBNICHES = DATA.get("subniches", {})
TOTALS = DATA.get("totals", {})


def is_complete(name):
    """Can we deliver all six triggers for this market?

    Trigger six is the buyer's own words, and it is the strongest thing in the report. A market with
    no record of how the buyer talks renders five, which would make the "six" on the landing page a
    lie and would send a coach the weakest version of the report. So a market has to be complete to
    be offered at all.
    """
    rec = report_data(name)
    if not rec:
        return False
    if not any((rec.get("voice") or {}).get(k) for k, _ in VOICE_LABELS):
        return False
    return bool(rec.get("lf8_primary") and rec.get("jtbd_job") and rec.get("cialdini"))


def niche_list():
    """The slim list the browser needs for the suggestions: every market we can actually deliver.

    A micro-niche carries its parent so the coach can see which family it sits in, and so two
    similarly named entries can be told apart.
    """
    out = []
    for name in sorted(NICHES):
        if is_complete(name):
            out.append({"n": name, "a": report_data(name).get("audience", "")})
    for name, rec in sorted(SUBNICHES.items()):
        if is_complete(name):
            out.append({"n": name, "p": rec.get("parent", ""),
                        "a": report_data(name).get("audience", "")})
    return out


def have_triggers_for(niche):
    """Do we hold a real lens for what they typed? Exact match first, then a forgiving one.

    Returns the matched name, or "" when we hold nothing. We would rather tell a coach we do not
    have their market yet than send them a report built on nothing.
    """
    if not niche:
        return ""
    q = niche.strip().lower()
    names = [n for n in list(NICHES) + list(SUBNICHES) if is_complete(n)]
    for name in names:
        if name.lower() == q:
            return name
    for name in names:
        if q in name.lower() or name.lower() in q:
            return name
    return ""


_CSS = _brand.FONT_FACES + _brand.BRAND_TOKENS + _brand.CHROME_CSS + """
  *{box-sizing:border-box}
  html{background:var(--navy)}
  body{margin:0;background:var(--navy);color:var(--ivory);
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:1020px;margin:0 auto;padding:60px 24px 76px;position:relative;z-index:1}
  /* the glow that stops a black band reading as a flat rectangle */
  body::before{content:"";position:fixed;inset:0;background:var(--halo);pointer-events:none;z-index:0}
  #heroblock{margin-bottom:26px}
  #heroblock .gb-split{gap:40px;align-items:center}
  #heroblock .gb-lede{margin-bottom:0}
  /* The instruction belongs at the point of action, not three lines up in the hero. */
  .f-head{font-size:clamp(22px,2.6vw,28px);margin:0 0 10px;color:#fff}
  /* Angelo has to hold his own against a 76px headline, so he is sized like the portrait
     block on the about page rather than like an icon. */
  .heromascot{width:250px;height:auto;flex-shrink:0;align-self:center}
  @media(max-width:820px){.heromascot{width:150px;align-self:flex-start}}
  .eyebrow{font-size:12px;letter-spacing:.24em;text-transform:uppercase;color:var(--ivory-dim);
    font-weight:600;margin:0 0 18px}
  h1.serif{font-family:var(--serif);font-weight:600;font-size:clamp(30px,5vw,48px);line-height:1.12;
    letter-spacing:-.015em;margin:0 0 20px;color:var(--ivory)}
  .sub{color:var(--ivory);font-weight:300;font-size:17px;line-height:1.7;margin:0 0 14px;max-width:60ch}
  .sub b{font-weight:600}
  form{display:flex;flex-direction:column;gap:12px;background:var(--navy-card);
    border:1px solid var(--navy-line);border-radius:12px;padding:22px;margin:32px 0 0}
  .f-lead{font-size:15px;line-height:1.6;color:var(--ivory);margin:0 0 4px}
  .f-lead .free{color:var(--cta-soft);font-weight:700}
  input[type=text],input[type=email]{border:1px solid var(--navy-line);border-radius:6px;
    padding:14px 16px;font-size:16px;color:var(--ivory);background:var(--navy-deep);width:100%;
    font-family:inherit}
  input::placeholder{color:var(--ivory-dim)}
  input:focus{outline:2px solid var(--glow);outline-offset:1px}
  button{background:var(--cta);color:var(--cta-ink);border:0;border-radius:var(--pill);padding:16px 30px;
    font-size:17px;font-weight:700;cursor:pointer;font-family:inherit}
  button:hover{background:var(--cta-h)}
  button[disabled]{opacity:.55;cursor:default}
  .hint{font-size:13px;color:var(--ivory-dim);margin:14px 0 0;line-height:1.6}
  .err{color:var(--coral);font-size:14px;line-height:1.6;margin:0 0 4px}

  /* The niche box and its suggestions. */
  .nichebox{position:relative}
  .nichelab{font-size:14px;color:var(--ivory);margin:6px 0 8px;line-height:1.6}
  .sugg{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:40;background:var(--navy-deep);
    border:1px solid var(--navy-line);border-radius:8px;max-height:290px;overflow-y:auto;display:none;
    box-shadow:0 12px 30px rgba(0,0,0,.45)}
  .sugg.open{display:block}
  .sugg li{list-style:none;padding:11px 14px;font-size:15px;cursor:pointer;color:var(--ivory);
    border-bottom:1px solid var(--navy-line);line-height:1.4}
  .sugg li:last-child{border-bottom:0}
  .sugg li:hover,.sugg li[aria-selected=true]{background:var(--navy-card)}
  .sugg ul{margin:0;padding:0}
  .sugg .par{display:block;font-size:12px;color:var(--ivory-dim);margin-top:3px}
  .sugg mark{background:transparent;color:var(--cta-soft);font-weight:700}
  .sugg .none{padding:12px 14px;font-size:14px;color:var(--ivory-dim);line-height:1.5}

  .whats{margin:40px 0 0;background:var(--navy-card);border:1px solid var(--navy-line);
    border-radius:12px;padding:26px}
  .whats h2{font-family:var(--serif);font-size:23px;font-weight:600;margin:0 0 14px;color:var(--ivory)}
  .whats ol{margin:0;padding:0;counter-reset:w}
  .whats li{list-style:none;position:relative;padding:0 0 0 42px;margin:0 0 14px;
    color:var(--ivory);font-size:15px;line-height:1.6}
  .whats li:last-child{margin-bottom:0}
  .whats li:before{counter-increment:w;content:counter(w);position:absolute;left:0;top:-1px;
    width:28px;height:28px;border-radius:50%;background:var(--glow);color:var(--navy);
    font-weight:700;font-size:14px;display:flex;align-items:center;justify-content:center}
  .whats b{font-weight:600}
  .base{margin:26px 0 0;font-size:14px;line-height:1.7;color:var(--ivory-dim);
    border-top:1px solid var(--navy-line);padding-top:18px}
  .base b{color:var(--ivory);font-weight:600}

  /* The thank-you state. */
  .done{background:var(--navy-card);border:1px solid var(--navy-line);border-radius:12px;
    padding:30px;margin:32px 0 0}
  .done h2{font-family:var(--serif);font-size:26px;font-weight:600;margin:0 0 12px;color:var(--ivory)}
  .done p{font-size:16px;line-height:1.7;margin:0 0 14px;color:var(--ivory);max-width:62ch}
  .done .tick{width:44px;height:44px;border-radius:50%;background:var(--cta);color:var(--cta-ink);
    display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;margin:0 0 16px}
  .nextbtn{display:inline-block;background:var(--cta);color:var(--cta-ink);text-decoration:none;
    font-weight:700;padding:15px 26px;border-radius:6px;font-size:16px;margin-top:6px}
  .nextbtn:hover{background:var(--cta-h)}
  /* Hero, with Angelo alongside the promise. */
  .hero{display:flex;gap:26px;align-items:flex-start;margin:0 0 6px}
  .mascot{width:118px;height:118px;border-radius:50%;object-fit:cover;flex:0 0 auto;
    border:2px solid var(--glow);box-shadow:0 0 0 5px rgba(127,169,221,.16)}
  .hero-copy{flex:1;min-width:0}
  .hero h1.serif{margin-top:0}

  /* The blocks under the form. */
  .whats.real{border-color:var(--cta-soft)}
  .whats .rl{font-size:15.5px;line-height:1.7;color:var(--ivory);margin:0 0 14px;max-width:64ch}
  .whats .rl:last-child{margin-bottom:0}
  .whats h2 + .rl{margin-top:-4px;margin-bottom:18px;color:var(--ivory-dim)}
  .closer{margin:40px 0 0;background:var(--navy-card);border:1px solid var(--cta);
    border-radius:12px;padding:30px}
  .closer h2{font-family:var(--serif);font-size:24px;font-weight:600;margin:0 0 12px;color:var(--ivory)}
  .closer p{font-size:16px;line-height:1.7;color:var(--ivory);margin:0 0 18px;max-width:62ch}
  .nextbtn{display:inline-block;background:var(--cta);color:var(--cta-ink);text-decoration:none;
    font-weight:700;padding:15px 26px;border-radius:6px;font-size:16px}
  .nextbtn:hover{background:var(--cta-h)}
  .backup{margin:0}
  .backup a{color:var(--glow);font-size:15px;text-decoration:underline;text-underline-offset:3px}
  .backup a:hover{color:var(--cta-soft)}
  @media(max-width:640px){
    .wrap{padding:36px 18px 56px}
    .hero{gap:16px}
    .mascot{width:76px;height:76px}
  }

  /* Angelo pulling the market. Same shape as the audit's progress panel, so the two pages feel
     like one product. */
  #processing{display:none;margin:32px 0 0;padding:32px;border-radius:12px;
    background:var(--navy-card);border:1px solid var(--navy-line)}
  #processing.on{display:block}
  .angelo-loader{display:block;width:150px;aspect-ratio:1;object-fit:cover;margin:0 auto 20px;
    border-radius:50%;border:2px solid var(--glow);box-shadow:0 0 0 5px rgba(127,169,221,.18)}
  #processing h3{font-size:21px;margin:0 0 8px;color:var(--ivory);text-align:center;font-weight:600}
  .pbar{height:6px;background:var(--navy-deep);border:1px solid var(--navy-line);border-radius:4px;
    overflow:hidden;margin:0 0 20px}
  .pbar i{display:block;height:100%;width:0;background:var(--cta);border-radius:4px;
    transition:width .6s linear}
  #processing ul{list-style:none;margin:0 0 18px;padding:0}
  #processing li{padding:11px 0;border-bottom:1px solid var(--navy-line);font-size:15px;
    line-height:1.5;color:var(--ivory);display:flex;gap:8px;align-items:baseline}
  #processing li .ps-status{margin-left:auto}
  #processing li:last-child{border-bottom:0}
  #processing li b{color:#fff;font-weight:600}
  .ps-status{font-weight:700;font-size:13px;white-space:nowrap}
  .ps-done{color:#5CB88C}
  .ps-progress{color:var(--glow)}
  .ps-waiting{color:var(--ivory-dim)}
  #processing .p-note{font-size:13px;color:var(--ivory-dim);line-height:1.6;margin:0;text-align:center}
  @media(max-width:640px){
    #processing{padding:22px 18px}
    #processing li{flex-direction:column;gap:3px}
  }
"""

_REPORT_CSS = """
  .rwrap{max-width:820px;margin:0 auto;padding:48px 24px 80px}
  .r-eyebrow{font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:var(--ivory-dim);
    font-weight:600;margin:0 0 14px}
  h1.r-title{font-family:var(--serif);font-weight:600;font-size:clamp(28px,4.4vw,42px);line-height:1.14;
    margin:0 0 10px;color:var(--ivory);letter-spacing:-.015em}
  .r-for{font-size:17px;color:var(--ivory);margin:0 0 8px;line-height:1.6;max-width:60ch}
  .r-parent{font-size:15px;color:var(--ivory-dim);margin:0 0 26px;line-height:1.6;max-width:60ch}
  .r-base{background:var(--navy-card);border:1px solid var(--navy-line);border-radius:10px;
    padding:18px 20px;font-size:14px;line-height:1.7;color:var(--ivory);margin:0 0 40px}
  .r-base b{font-weight:600}
  .r-what{font-size:17px;line-height:1.7;color:var(--ivory);margin:0 0 40px;max-width:62ch}
  .r-depth{font-size:16px;line-height:1.72;color:var(--ivory-dim);max-width:64ch;
    margin:44px 0 0;padding:20px 0 0;border-top:1px solid var(--navy-line)}
  /* Every gap used to be roughly the same, 40px between whole triggers and up to 14px inside one,
     with no rule anywhere, so the six ran together as one long column.
     Now each trigger is a numbered row: a narrow rail carrying the number, the trigger beside it.
     The numerals give the left edge a steady beat, which is what keeps very uneven block lengths
     from reading as a lurch, and the hairline says plainly where one ends. */
  section.r{display:grid;grid-template-columns:66px minmax(0,1fr);column-gap:26px;
    margin:0;padding:36px 0 0;border-top:1px solid var(--navy-line)}
  section.r:first-of-type{border-top:0;padding-top:0}
  section.r + section.r{margin-top:36px}

  .r-rail{text-align:right;padding-top:2px}
  .r-n{display:block;font-family:var(--serif);font-size:42px;font-weight:600;line-height:.86;
    color:var(--cta-soft);letter-spacing:-.02em}
  .r-n.r-mark{font-size:54px;line-height:.6}
  .r-lab{display:block;font-size:10px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--ivory-dim);font-weight:700;margin-top:10px;line-height:1.4}

  .r-main{min-width:0}
  .r-cat{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--ivory-dim);
    font-weight:700;margin:0 0 10px;line-height:1.6}
  .r-main > h2{font-family:var(--serif);font-size:28px;font-weight:600;color:var(--ivory);
    margin:0 0 13px;line-height:1.2;max-width:25ch;letter-spacing:-.012em;
    /* Without this every one of these broke with a single orphan word on line two:
       "feeling / dumb", "pulling / ahead". Balance splits them evenly instead. */
    text-wrap:balance}
  section.r p{font-size:16px;line-height:1.72;color:var(--ivory);margin:0 0 14px;max-width:64ch}
  section.r p:last-of-type{margin-bottom:0}
  .r-force{background:var(--navy-card);border-left:3px solid var(--cta);border-radius:0 8px 8px 0;
    padding:16px 20px;margin:0 0 14px}
  .r-force .fname{font-family:var(--serif);font-size:20px;color:var(--ivory);margin:0 0 4px;font-weight:600}
  .r-force .fplain{font-size:16px;color:var(--cta-soft);line-height:1.6;margin:0}
  .r-sec{font-size:14px;color:var(--ivory-dim);line-height:1.7;margin:10px 0 0}
  .r-ev{font-size:15px;line-height:1.7;color:var(--ivory);background:var(--navy-deep);
    border:1px solid var(--navy-line);border-radius:8px;padding:15px 18px;margin:18px 0 0}
  .r-ev b{color:var(--cta-soft);font-weight:600;display:block;font-size:12px;letter-spacing:.14em;
    text-transform:uppercase;margin:0 0 6px}
  .jt{margin:0;padding:0}
  .jt div{display:grid;grid-template-columns:150px 1fr;gap:14px;padding:13px 0;
    border-bottom:1px solid var(--navy-line);font-size:15px;line-height:1.65}
  .jt div:last-child{border-bottom:0}
  .jt dt{color:var(--cta-soft);font-weight:600}
  .jt dd{margin:0;color:var(--ivory)}
  .voice{background:var(--navy-card);border:1px solid var(--navy-line);border-radius:10px;
    padding:6px 20px;margin:0 0 14px}
  .voice h3{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--cta-soft);
    font-weight:700;margin:20px 0 10px}
  .voice ul{margin:0 0 18px;padding:0}
  .voice li{list-style:none;font-size:15.5px;line-height:1.6;color:var(--ivory);
    padding:9px 0 9px 20px;border-left:2px solid var(--navy-line);margin:0 0 7px;font-style:italic}
  .jargon{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px;padding:0}
  .jargon li{list-style:none;background:var(--navy-deep);border:1px solid var(--navy-line);
    border-radius:20px;padding:6px 14px;font-size:14px;color:var(--ivory)}
  .books{margin:0;padding:0}
  .books li{list-style:none;padding:11px 0;border-bottom:1px solid var(--navy-line);font-size:15px;
    line-height:1.5;color:var(--ivory)}
  .books li:last-child{border-bottom:0}
  .books .au{display:block;font-size:13px;color:var(--ivory-dim);margin-top:2px}
  .r-next{background:var(--navy-card);border:1px solid var(--cta);border-radius:12px;
    padding:28px;margin:48px 0 0}
  .r-next h2{font-family:var(--serif);font-size:25px;font-weight:600;margin:0 0 12px;color:var(--ivory)}
  .r-next p{font-size:16px;line-height:1.72;color:var(--ivory);margin:0 0 14px;max-width:64ch}
  .r-foot{margin:36px 0 0;padding-top:18px;border-top:1px solid var(--navy-line);
    font-size:13px;line-height:1.7;color:var(--ivory-dim)}
  @media(max-width:640px){
    .rwrap{padding:32px 18px 56px}
    .jt div{grid-template-columns:1fr;gap:3px}
    /* The rail becomes a single line above the trigger. A 66px column is 66px a phone cannot spare,
       and the numeral still has to arrive before the words it belongs to. */
    section.r{grid-template-columns:1fr}
    .r-rail{display:flex;align-items:baseline;gap:11px;text-align:left;margin:0 0 16px;padding:0}
    .r-n{font-size:31px;line-height:1}
    .r-n.r-mark{font-size:38px;line-height:1}
    .r-lab{margin-top:0;line-height:1.25;white-space:nowrap}
    .r-main > h2{font-size:24px;max-width:none}
    /* .2em of tracking is generous on a desktop and wasteful on a 375px phone, where it pushes
       a short category label onto two lines for no gain. */
    .r-cat{letter-spacing:.11em}
  }
"""


_JS = """
(function(){
  var input = document.getElementById('nicheinput');
  var box   = document.getElementById('nichesugg');
  if(!input || !box) return;
  var LIST = [], cur = -1, items = [];

  fetch('/triggers/niches.json').then(function(r){return r.json();}).then(function(d){ LIST = d; });

  function esc(s){ return s.replace(/[&<>"]/g, function(c){
    return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]; }); }

  function mark(name, q){
    var i = name.toLowerCase().indexOf(q);
    if(i < 0) return esc(name);
    return esc(name.slice(0,i)) + '<mark>' + esc(name.slice(i, i+q.length)) + '</mark>' + esc(name.slice(i+q.length));
  }

  function close(){ box.classList.remove('open'); box.innerHTML = ''; cur = -1; items = []; }

  function choose(name){ input.value = name; close(); input.focus(); }

  function render(q){
    // A word-start match first (typing "div" should offer Divorce before it offers anything that
    // merely contains those letters), then anything else that contains what they typed.
    // Three tiers. A word-start in the market NAME beats a match anywhere in the name, and both beat
    // a match on the audience label, so typing "divorce" still leads with the divorce market rather
    // than every market whose people happen to be described as divorced.
    var starts = [], has = [], aud = [];
    for(var i=0; i<LIST.length && starts.length + has.length + aud.length < 200; i++){
      var low = LIST[i].n.toLowerCase();
      var at = low.indexOf(q);
      if(at < 0){
        if((LIST[i].a || '').toLowerCase().indexOf(q) >= 0) aud.push(LIST[i]);
        continue;
      }
      if(at === 0 || /[^a-z0-9]/.test(low.charAt(at-1))) starts.push(LIST[i]); else has.push(LIST[i]);
    }
    var hits = starts.concat(has).concat(aud).slice(0, 8);
    if(!hits.length){
      box.innerHTML = '<div class="none">Not on our list yet. Type it in your own words and we will '
                    + 'tell you straight whether we have read the books for it.</div>';
      box.classList.add('open'); items = []; cur = -1; return;
    }
    var ul = document.createElement('ul');
    hits.forEach(function(h){
      var li = document.createElement('li');
      li.setAttribute('role','option');
      li.dataset.name = h.n;          // the real name, so Enter never has to read it back off the label
      var under = h.a ? 'for ' + esc(h.a) : (h.p ? 'part of ' + esc(h.p) : '');
      li.innerHTML = mark(h.n, q) + (under ? '<span class="par">' + under + '</span>' : '');
      li.addEventListener('mousedown', function(e){ e.preventDefault(); choose(h.n); });
      ul.appendChild(li);
    });
    box.innerHTML = '';
    box.appendChild(ul);
    box.classList.add('open');
    items = Array.prototype.slice.call(ul.children);
    cur = -1;
  }

  function move(step){
    if(!items.length) return;
    if(cur > -1) items[cur].setAttribute('aria-selected','false');
    cur = (cur + step + items.length) % items.length;
    items[cur].setAttribute('aria-selected','true');
    items[cur].scrollIntoView({block:'nearest'});
  }

  input.addEventListener('input', function(){
    var q = input.value.trim().toLowerCase();
    if(q.length < 2){ close(); return; }
    render(q);
  });
  input.addEventListener('keydown', function(e){
    if(e.key === 'ArrowDown'){ e.preventDefault(); move(1); }
    else if(e.key === 'ArrowUp'){ e.preventDefault(); move(-1); }
    else if(e.key === 'Enter'){
      if(cur > -1 && items[cur]){ e.preventDefault(); choose(items[cur].dataset.name); }
    }
    else if(e.key === 'Escape'){ close(); }
  });
  input.addEventListener('blur', function(){ setTimeout(close, 120); });
  input.addEventListener('focus', function(){
    var q = input.value.trim().toLowerCase();
    if(q.length >= 2) render(q);
  });
})();

// The submit. Angelo works for twenty seconds while the report is fetched behind him, then the
// report opens on this page. Without JavaScript the plain POST still returns the report, so nobody
// is left staring at a dead form.
(function(){
  var cta = document.getElementById('cta2');
  if(cta) cta.addEventListener('click', function(ev){
    ev.preventDefault();
    var form = document.getElementById('trigform');
    form.scrollIntoView({behavior:'smooth', block:'center'});
    // Put them in the first box they have not filled, so the button does the whole job.
    var first = ['fnameinput','lnameinput','emailinput','nicheinput']
                  .map(function(id){ return document.getElementById(id); })
                  .filter(function(el){ return el && !el.value.trim(); })[0];
    if(first) setTimeout(function(){ first.focus({preventScroll:true}); }, 400);
  });
})();

(function(){
  var form = document.getElementById('trigform');
  if(!form) return;
  var proc = document.getElementById('processing');
  var slot = document.getElementById('reportslot');
  var whats = document.getElementById('whatsin');
  var bar, busy = false;
  var STEPS = 5, HOLD = 20000;

  function setStep(n, state){
    var el = document.getElementById('tp' + n);
    if(!el) return;
    el.textContent = '[' + state + ']';
    el.className = 'ps-status ' + (state === 'DONE' ? 'ps-done'
                 : state === 'WORKING' ? 'ps-progress' : 'ps-waiting');
  }

  form.addEventListener('submit', function(ev){
    if(!form.checkValidity()) return;             // let the browser show its own message
    ev.preventDefault();
    if(busy) return;
    busy = true;

    form.style.display = 'none';
    if(whats) whats.style.display = 'none';
    slot.innerHTML = '';
    proc.className = 'on';
    bar = proc.querySelector('.pbar i');
    proc.scrollIntoView({behavior:'smooth', block:'center'});

    for(var i = 1; i <= STEPS; i++) setStep(i, i === 1 ? 'WORKING' : 'WAITING');
    var step = 1;
    var tick = setInterval(function(){
      setStep(step, 'DONE');
      step++;
      if(step <= STEPS) setStep(step, 'WORKING');
      if(bar) bar.style.width = Math.round((step - 1) / STEPS * 100) + '%';
      if(step > STEPS) clearInterval(tick);
    }, HOLD / STEPS);
    if(bar) setTimeout(function(){ bar.style.width = '4%'; }, 60);

    var started = Date.now();
    var body = new URLSearchParams(new FormData(form)).toString() + '&fragment=1';
    fetch('/triggers', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: body
    }).then(function(r){ return r.text(); }).then(function(htmlText){
      var wait = Math.max(0, HOLD - (Date.now() - started));
      setTimeout(function(){
        clearInterval(tick);
        for(var i = 1; i <= STEPS; i++) setStep(i, 'DONE');
        if(bar) bar.style.width = '100%';
        setTimeout(function(){
          proc.className = '';
          // The pitch has done its job. From here the report IS the page.
          ['heroblock','belowfold'].forEach(function(id){
            var el = document.getElementById(id);
            if(el) el.style.display = 'none';
          });
          slot.innerHTML = htmlText;
          window.scrollTo({top: 0, behavior: 'smooth'});
          busy = false;
        }, 450);
      }, wait);
    }).catch(function(){
      // Anything goes wrong and the plain form submit takes over, which returns the same report.
      clearInterval(tick);
      busy = false;
      form.style.display = '';
      proc.className = '';
      form.submit();
    });
  });
})();
"""

_SHELL = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
__SEO__
<style>__CSS__</style></head><body>
__NAV__
<div class="wrap">
__BODY__
</div>
__FOOTER__
<script>__JS__</script>
</body></html>"""


_HOME_TITLE = "The 6 buying triggers that turn a stranger into a client"


def _title(suffix=""):
    """The homepage title, plus whatever a report view wants after it.

    It leads on the triggers rather than on the product name because nobody is searching
    for "Buying Triggers" yet, and a searcher scanning a results page is looking for their
    own problem, not for what we called our page.
    """
    return f"{_HOME_TITLE}{suffix}" if suffix else _HOME_TITLE


def _shell(body, title_suffix=""):
    # The report is injected into the landing page after the progress bar, so its stylesheet has to be
    # on every page, not only on the standalone report URL.
    return (_SHELL
            .replace("__CSS__", _CSS + _REPORT_CSS)
            .replace("__JS__", _JS)
            .replace("__SEO__", _brand.head_meta("/", _title(title_suffix),
                     "The reason your clients actually buy, worked out from the books they buy.", True))
            .replace("__NAV__", _brand.nav_html("home"))
            .replace("__FOOTER__", _brand.footer_html())
            .replace("__BODY__", body))


PLAIN_FORCE = {
    "survival/health/life-extension":   "to stay well and live longer",
    "survival, enjoyment of life, life extension": "to stay well and live longer",
    "enjoyment of food and beverages":  "to enjoy food and drink",
    "freedom from fear, pain & danger": "to stop something that frightens them or hurts",
    "freedom from fear, pain and danger": "to stop something that frightens them or hurts",
    "sexual companionship":             "to be wanted and not be on their own",
    "comfortable living conditions":    "to have an easier life",
    "to be superior / win / keep up":   "to be better at something or keep up with the people around them",
    "care & protection of loved ones":  "to look after the people they love",
    "social approval":                  "to be thought well of by other people",
    "to be informed":                   "to understand what is happening to them",
    "to be informed / curiosity":       "to understand what is happening to them",
    "curiosity":                        "to find out for themselves",
    "efficiency":                       "to stop wasting time",
    "convenience":                      "an easier way of doing it",
    "dependability/quality":            "something that actually works",
    "beauty/style":                     "to look good",
    "economy/profit":                   "to save or make money",
    "economy/profit (survival of the business)": "to keep the business alive",
    "cleanliness":                      "to feel clean",
    "bargains":                         "a good deal",
}

# Where the buyer's head is when they find you.
PLAIN_AWARENESS = {
    "unaware":        "they still hadn't put a name to what was wrong. They only knew they felt bad.",
    "problem-aware":  "they knew something was wrong. They just didn't know what fixes it, so they "
                      "were searching for a name for it, not for a coach.",
    "solution-aware": "they already knew help like yours exists. So they weren't asking whether to "
                      "get help. They were asking who from.",
    "product-aware":  "they already knew who you are. They were weighing you up against the others.",
    "most-aware":     "they were ready to go. The only question left was when.",
}

# How worn out the promises in the market already are.
PLAIN_SOPH = {
    "1": "Nobody has made this promise to your market yet. It's new to them.",
    "2": "A few coaches have promised this already. Your market has heard it, but they're not sick "
         "of it yet.",
    "3": "Your market has heard this promise so many times they don't believe it on its own any "
         "more. Now they want to hear how it works.",
    "4": "They've heard coaches explain how it works too. A vague explanation doesn't move them "
         "now. They only believe one that is exact, or clearly built for someone like them.",
    "5": "They've heard all of it before. Being told something works doesn't move them any more. "
         "They need to see it.",
}

# The plain sentence only. The framework's name for each lever stays on our side of the wall.
PLAIN_LEVER = {
    "authority":     "They want someone who plainly knows more than they do.",
    "social proof":  "They want to see people like them who came out the other side.",
    "unity":         "They want someone who is one of them, not someone looking in.",
    "reciprocity":   "Give them something real first and they feel the pull to come back.",
    "commitment/consistency": "A small first step makes the bigger one feel normal to them.",
    "liking":        "They buy from someone they warm to.",
    "scarcity":      "A real limit moves them. A made-up one costs you the sale.",
}

# The six triggers.
#
# Every one is a thing that actually moves a buyer. The old structure numbered a state ("where their
# head is"), a history ("what they've heard") and the evidence as triggers, which they are not. David:
# "we are after triggers, that is what this whole thing is about."
#
# `cat` is the fixed category, shown small above the heading. `key` is the field holding the name we
# wrote for this market, which becomes the heading. `plain` is the fallback for any market that has
# not been through the naming pass, so a raw slot never renders.
SECTION_HEADINGS = [
    {"n": "Buying Trigger 1", "key": "t1_name", "plain": "What they're really buying"},
    {"n": "Buying Trigger 2", "key": "t2_name", "plain": "What made them start looking for help"},
    {"n": "Buying Trigger 3", "key": "t3_name", "plain": "What they want to happen instead"},
    {"n": "Buying Trigger 4", "key": "t4_name", "plain": "What stops them buying"},
    {"n": "Buying Trigger 5", "key": "t5_name", "plain": "What they've stopped believing"},
    {"n": "Buying Trigger 6", "key": "t6_name", "plain": "What makes them pick one coach over another"},
]

# The category line, so the reader knows what each trigger covers even when the name is specific.
SECTION_CATS = [
    "What they're really buying",
    "What made them start looking for help",
    "What they want to happen instead",
    "What stops them buying",
    "What they've stopped believing",
    "What makes them pick one coach over another",
]


def _heading(i, rec):
    """Trigger i, named for this market. Falls back to the plain category if it has no name yet."""
    h = SECTION_HEADINGS[i]
    return (rec.get(h["key"]) or "").strip() or h["plain"]


VOICE_LABELS = [
    ("pain",   "How they describe the problem"),
    ("desire", "What they say they want"),
    ("blame",  "Who or what they blame"),
    ("tried",  "What they have already tried"),
    ("trigger", "What made them start looking"),
    ("jargon", "Words they use that outsiders don't"),
]


def _plain(mapping, key, fallback=""):
    return mapping.get((key or "").strip().lower(), fallback)

def render_triggers(first_name="", last_name="", email="", niche="", error=""):
    """The landing page.

    The form sits high, because the whole promise is that the report arrives in twenty seconds and
    nothing has to be read first. Everything under the form is there for the coach who wants to know
    who we are before handing over an address.

    The "what you get" list is generated from SECTION_HEADINGS, so the page can never promise a
    section the report does not have.
    """
    e = html.escape
    err_html = '<p class="err">' + e(error) + '</p>' if error else ""

    # What each trigger gives them. Paired with the real headings, in the report's own order.
    PROMISE = [
        "The deep thing your market is trying to get, or trying to get away from.",
        "The moment it got too much for them, and they started looking for help.",
        "The picture in their head of what life looks like once this is sorted.",
        "The fear that keeps their card in their pocket, and what they do instead of buying.",
        "The promises they have heard so often they no longer believe them.",
        "Why a buyer picks one coach and not the next one, in your market.",
    ]
    gets = ""
    for i, why in enumerate(PROMISE):
        gets += ('<li><b>' + e(SECTION_HEADINGS[i]["plain"]) + '.</b> ' + why + '</li>')

    body = """
  <div id="heroblock">
  <div class="gb-split">
    <div class="gb-copy">
      <p class="gb-eyebrow">Buying triggers</p>
      <h1 class="gb-display">The 6 <span class="gb-grad">buying triggers</span> that turn a
        stranger into a client</h1>
      <p class="gb-lede"><b>Your client buys for a reason, and they will not tell you what it
      is.</b> So we went and worked out what your market already buys, and why.</p>
    </div>
    <img class="mascot heromascot" src="/angelo.png"
         alt="Angelo, who works out what your market already buys">
  </div>
  </div>

  <form method="post" action="/triggers" id="trigform" autocomplete="on">
    """ + err_html + """
    <h2 class="gb-display f-head">Tell us who you coach, and we will tell you why they&nbsp;buy</h2>
    <p class="f-lead">Your report opens on this page in about twenty seconds.
    <span class="free">Nothing to pay.</span> We built this research for our own work, so it
    costs us nothing to hand you a copy.</p>
    <input type="text"  name="first_name" id="fnameinput" placeholder="Your first name"
           autocomplete="given-name" value=\"""" + e(first_name, quote=True) + """\" required>
    <input type="text"  name="last_name"  id="lnameinput" placeholder="Your last name"
           autocomplete="family-name" value=\"""" + e(last_name, quote=True) + """\">
    <input type="email" name="email"      id="emailinput" placeholder="Your best email address"
           autocomplete="email" value=\"""" + e(email, quote=True) + """\" required>
    <div class="nichebox">
      <p class="nichelab">Start typing and pick yours from the list.</p>
      <input type="text" name="niche" id="nicheinput" placeholder="divorce, ADHD, first-time managers&hellip;"
             autocomplete="off" role="combobox" aria-expanded="false" aria-controls="nichesugg"
             value=\"""" + e(niche, quote=True) + """\" required>
      <div class="sugg" id="nichesugg" role="listbox"></div>
    </div>
    <button type="submit">Show me my buying triggers</button>
    <p class="hint">One report. No newsletter, nothing to unsubscribe from later.</p>
  </form>

  <div id="processing">
    <img class="angelo-loader" src="/angelo_reading.png"
         alt="Angelo reading your market">
    <h3>Angelo is pulling your market</h3>
    <div class="pbar"><i></i></div>
    <ul>
      <li><b>One:</b> Finding your market in the research
          <span class="ps-status ps-progress" id="tp1">[WORKING]</span></li>
      <li><b>Two:</b> Pulling what your buyers already spend money on
          <span class="ps-status ps-waiting" id="tp2">[WAITING]</span></li>
      <li><b>Three:</b> Reading what they say is wrong, in their words
          <span class="ps-status ps-waiting" id="tp3">[WAITING]</span></li>
      <li><b>Four:</b> Working out what they're really paying for
          <span class="ps-status ps-waiting" id="tp4">[WAITING]</span></li>
      <li><b>Five:</b> Building your report
          <span class="ps-status ps-waiting" id="tp5">[WAITING]</span></li>
    </ul>
    <p class="p-note">About twenty seconds. Leave this page open. Your report opens here on its own.</p>
  </div>
  <div id="reportslot"></div>

  <div id="belowfold">
  <div class="whats">
    <h2>The six triggers Angelo pulls for your market</h2>
    <p class="rl">He does it on this page while you watch. Takes about twenty seconds.</p>
    <ol>""" + gets + """</ol>
  </div>

  <div class="whats real">
    <h2>Why this isn't another AI freebie</h2>
    <p class="rl">We didn't guess these, and we didn't ask an AI what it reckons. We went to what your
    market already spends money on. Then we got the words your buyers use about their own problem,
    written by them, not by a coach.</p>
    <p class="rl">Check it yourself before you type anything. Start typing your niche in the box above.
    Every market it offers you is one we've already read. If yours isn't in there, we'll say so, rather
    than send you somebody else's market with your name on it.</p>
  </div>

  <div class="closer">
    <h2>Your buyer already told us why they buy</h2>
    <p>They wrote it down. We went and read it. Costs you nothing to see, and the coaches you're up
    against are working without it.</p>
    <p class="backup"><a href="#trigform" id="cta2">Take me back up to the form</a></p>
  </div>

  <p class="base" id="baseline">Buying Triggers comes from what your market already buys, and from your
  buyers describing the problem in their own words. <b>Going Beyond The Illusion.</b></p>
  </div>
"""
    return _shell(body)


# The research prose was written for us, not for a coach. It carries analyst shorthand: category tags
# in brackets like "(health/pain/appearance)", "(comfort)", "(tried: medication)", and semicolons
# joining two thoughts. None of that belongs on a page a coach reads.
_TAG_WORDS = {
    "health", "pain", "appearance", "comfort", "validation", "danger", "fear", "superiority",
    "winning", "status", "approval", "social", "belonging", "identity", "money", "profit",
    "curiosity", "efficiency", "convenience", "beauty", "style", "survival", "companionship",
    "authority", "proof", "unity", "scarcity", "liking", "reciprocity", "commitment", "consistency",
    "self", "directed", "external", "blame", "tried", "trigger", "desire", "pull", "push",
}


def _is_tag(inner):
    """A bracket is analyst shorthand when every word inside it is a category label."""
    if inner.lower().startswith(("tried:", "blame:", "trigger:", "source:")):
        return True
    words = [w for w in re.split(r"[\s/,&+-]+", inner.lower()) if w]
    return bool(words) and len(words) <= 5 and all(w in _TAG_WORDS for w in words)


def _clean(text):
    """Research prose goes through here on its way to the page.

    Three things come out. Em dashes, which David bans. The bracketed category tags we wrote for
    ourselves. And semicolons, which become full stops, because a coach reading this should get two
    plain sentences rather than one long one.
    """
    t = str(text or "")
    t = re.sub(r"\s*\(([^()]*)\)", lambda m: "" if _is_tag(m.group(1)) else m.group(0), t)
    t = t.replace("\u2014", ",").replace("\u2013", ",").replace(" -- ", ", ")
    t = re.sub(r"\s*;\s*", ". ", t)
    t = re.sub(r"\s*,\s*", ", ", t)
    t = re.sub(r",\s*([.;:,])", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip().rstrip(",").strip()
    # A full stop from a semicolon leaves the next word lowercase. Lift it.
    t = re.sub(r"(?<=\.\s)([a-z])", lambda m: m.group(1).upper(), t)
    return t[:1].upper() + t[1:] if t else t


def report_data(name):
    """Pull the research for one market. A micro-niche that does not diverge falls back to its parent,
    and says so, rather than pretending to be its own study."""
    if name in NICHES:
        rec = dict(NICHES[name])
        rec.update(rec.get("prose_plain") or {})   # the plain rewrite wins where we have one
        rec["level"] = "niche"
        rec["shown_as"] = name
        return rec
    if name in SUBNICHES:
        sub = SUBNICHES[name]
        parent = NICHES.get(sub.get("parent", ""), {})
        rec = dict(parent)
        rec.update(parent.get("prose_plain") or {})
        rec.update({k: v for k, v in sub.items() if v and k not in ("voice", "books", "prose_plain")})
        rec.update(sub.get("prose_plain") or {})
        # A micro-niche only overrides the parent where the research says it genuinely differs.
        if sub.get("lf8"):
            rec["lf8_primary"] = sub["lf8"]
        if sub.get("voice"):
            rec["voice"] = sub["voice"]
        if sub.get("books"):
            rec["books"] = sub["books"]
            rec["book_count"] = sub.get("book_count", 0)
        rec["level"] = "subniche"
        rec["shown_as"] = name
        rec["parent"] = sub.get("parent", "")
        rec["diverges"] = sub.get("diverges", False)
        return rec
    return {}





_LEVER_WORDS = ("authority", "social proof", "unity", "reciprocity", "liking", "scarcity",
                "commitment", "consistency")


def _strip_levers(text):
    """The research prose names the persuasion framework in brackets, like "(Social Proof)". We keep
    the framework on our side of the wall, so the brackets come out and the sentence stands alone."""
    t = str(text or "")
    t = re.sub(r"\s*\((?:[^()]*)\)", lambda m: "" if any(
        w in m.group(0).lower() for w in _LEVER_WORDS) else m.group(0), t)
    return re.sub(r"\s+", " ", t).strip(" ,;")


def render_report(niche, first_name="", audit_url="/", fragment=False):
    """One market's buying triggers, straight off the research.

    Three rules the copy obeys, all for the same reason. We never name the frameworks the research was
    read against, we never list the books by title, and we never give a count of anything. Each one
    hands the coach a shortcut to doing it themselves, and none of them makes the report more useful.
    """
    # The gate is enforced HERE as well as in the box, because the POST falls back to whatever the
    # coach typed when nothing matched, and that raw string can still name a market we hold but hold
    # back. Without this check a held-back market renders five triggers under a headline promising six.
    rec = report_data(niche) if is_complete(niche) else {}
    e = html.escape
    if not rec:
        # No promise of an email here. Nothing in the app sends one. What we CAN do is hand them
        # straight back to the form, where the list only ever offers markets we actually hold.
        miss = ('<div class="done"><h2>We haven’t read this market yet.</h2>'
                f'<p>We hold a long list of markets, and the smaller ones inside them. {e(niche)} '
                'isn’t on it. We’d rather tell you straight than hand you somebody else’s market '
                'with your name typed over the top.</p>'
                '<p>We’ve kept your details and put it on the list to read. If something close enough '
                'to yours is on the list, type that in and we’ll build it now. Every market the box '
                'offers you is one we’ve read.</p>'
                '<a class="nextbtn" href="/triggers">Try another market</a></div>')
        return miss if fragment else _shell(miss)

    shown = rec.get("shown_as", niche)
    voice = rec.get("voice", {}) or {}
    audience = rec.get("audience", "")
    H = [_heading(i, rec) for i in range(len(SECTION_HEADINGS))]

    def sect(i, paras, box=None, box_label="How we know"):
        """One trigger. Category, name, explanation. The explanation only ever describes the buyer."""
        # A numbered rail on the left, the trigger beside it. The six ARE a sequence, so numbering
        # them states something true rather than decorating. It also gives the page a steady beat
        # down the left edge, which is what stops wildly uneven block lengths reading as a lurch.
        out = ('<section class="r">'
               '<div class="r-rail"><span class="r-n">' + str(i + 1) + '</span>'
               '<span class="r-lab">Buying Trigger</span></div>'
               '<div class="r-main">'
               '<p class="r-cat">' + e(SECTION_CATS[i]) + '</p>'
               '<h2>' + e(H[i]) + '</h2>')
        for para in paras:
            if para:
                out += "<p>" + para + "</p>"
        if box:
            out += '<div class="r-ev"><b>' + e(box_label) + '</b>' + e(box) + '</div>'
        return out + "</div></section>"

    # 1. What they're really buying. Written as one paragraph, not floating fragments in boxes.
    primary = [x for x in (_plain(PLAIN_FORCE, f, "") for f in rec.get("lf8_primary", [])[:2]) if x]
    if len(primary) > 1:
        want = "Here it's two things: " + e(primary[0]) + ", and " + e(primary[1]) + "."
    elif primary:
        want = "Here it's one thing: " + e(primary[0]) + "."
    else:
        want = ""
    secondary = [x for x in (_plain(PLAIN_FORCE, y, "") for y in rec.get("lf8_secondary", [])[:2]) if x]
    if len(secondary) > 1:
        want += (" Wanting " + e(secondary[0]) + " and " + e(secondary[1])
                 + " comes into it too, but those are smaller reasons.")
    elif secondary:
        want += " Wanting " + e(secondary[0]) + " comes into it too, but that's a smaller reason."
    s1 = sect(0, ["Nobody buys coaching. They buy what coaching gets them. " + want],
              _clean(rec.get("lf8_evidence", "")) or None)

    # 2. What made them start looking. The push, plus how far along they already were.
    aw = (rec.get("awareness") or "").lower()
    aw_plain = ""
    for stage in sorted(PLAIN_AWARENESS, key=len, reverse=True):
        if stage in aw:
            aw_plain = PLAIN_AWARENESS[stage]
            break
    aw_line = ("By the time they started looking, " + aw_plain) if aw_plain else ""
    s2 = sect(1, [e(_clean(rec.get("push",""))), aw_line])

    # 3. What they're reaching for.
    s3 = sect(2, [e(_clean(rec.get("pull","")))])

    # 4. What stops them, and what they do instead of buying.
    s4 = sect(3, [e(_clean(rec.get("anxiety",""))),
                  ("So instead of buying, " + e(_clean(rec.get("habit",""))[0:1].lower()
                   + _clean(rec.get("habit",""))[1:])) if rec.get("habit") else ""])

    # 5. What they've stopped believing.
    soph_digit = re.search(r"[1-5]", str(rec.get("sophistication", "")))
    soph_plain = PLAIN_SOPH.get(soph_digit.group(0), "") if soph_digit else ""
    s5 = sect(4, [soph_plain, e(_clean(rec.get("implication","")))])

    # 6. What tips them to one coach over another.
    # A list of lines, not a pre-wrapped blob. sect() does the wrapping, and handing it HTML that
    # was already wrapped nested a <p> inside a <p>.
    lev = [e(line) for line in
           (_plain(PLAIN_LEVER, l, "") for l in rec.get("cialdini", [])[:3]) if line]
    # Built through sect() like every other trigger rather than by splicing onto a closing tag.
    # The old version string-replaced "</section>", which put this content on the wrong side of
    # the div that closes the text column the moment the markup grew one, and the levers ended up
    # rendering down the number rail a word at a time.
    s6 = sect(5, lev,
              box=_clean(_strip_levers(rec.get("cialdini_why", ""))) or None,
              box_label="Why these three work")

    # The proof. Deliberately NOT numbered as a trigger: their own words are evidence, not a trigger.
    vhtml = ""
    seen = set()
    for key, label in VOICE_LABELS:
        items = []
        for phrase in (voice.get(key) or []):
            phrase = _clean(phrase)
            if phrase and phrase.lower() not in seen:
                seen.add(phrase.lower())
                items.append(phrase)
            if len(items) == 4:
                break
        if not items:
            continue
        if key == "jargon":
            vhtml += ("<h3>" + label + "</h3><ul class='jargon'>"
                      + "".join("<li>" + e(x) + "</li>" for x in items) + "</ul>")
        else:
            vhtml += ("<h3>" + label + "</h3><ul>"
                      + "".join("<li>&ldquo;" + e(x) + "&rdquo;</li>" for x in items) + "</ul>")
    voice_section = ""
    if vhtml:
        voice_section = ('<section class="r"><div class="r-rail">'
                         '<span class="r-n r-mark">&ldquo;</span>'
                         '<span class="r-lab">The proof</span></div>'
                         '<div class="r-main">'
                         '<h2>In their own words</h2>'
                         "<p>These are your buyer's own words. This is how they talk about it to "
                         "each other, not to a coach.</p>"
                         '<div class="voice">' + vhtml + '</div></div></section>')

    fn = first_name.strip().split(" ")[0] if first_name.strip() else ""
    if fn.islower():
        fn = fn.capitalize()
    fn = e(fn)
    for_line = ((fn + ", here are your buying triggers. This is why people buy&hellip;")
                if fn else "Here are your buying triggers. This is why people buy&hellip;")
    parent_line = ""
    if rec.get("level") == "subniche" and rec.get("parent"):
        if rec.get("diverges"):
            parent_line = ("Your market sits inside " + e(rec["parent"])
                           + ", and it buys its own way.")
        else:
            parent_line = ("Your market buys the same way as " + e(rec["parent"])
                           + ", so that's the research you're getting.")

    # Built here, not inside the body string. A quote escaped next to the triple-quote terminator
    # silently produced "href= + e(audit_url) +" as literal text, and the button had no link at all.
    cta_link = ('<a class="nextbtn" href="' + e(audit_url, quote=True)
                + '">Show me what a potential client sees</a>')

    body = """
  <div class="rwrap">
  <p class="r-eyebrow">Your Buying Triggers report is ready</p>
  <h1 class="r-title">""" + e(shown) + """</h1>
  <p class="r-for">""" + for_line + """</p>
  """ + ('<p class="r-parent">' + parent_line + "</p>" if parent_line else "") + """

  <div class="r-base"><b>We didn't guess at these triggers.</b> They're real. This isn't an AI making
  things up when it doesn't know. You see, we went direct to your niche, worked out exactly what they
  already spend money on, and took the words your next buyers use to describe their problem. Your
  competitors don't have this.</div>

  <p class="r-what">A trigger is anything that pushes your buyer towards you, or holds them back. Here
  are the six in your market.</p>

  """ + s1 + s2 + s3 + s4 + s5 + s6 + voice_section + """



  <div class="r-next">
    <h2>Now let's look at you</h2>
    <p>We built this report in about 20 seconds, and it's an excellent view of your market. But
    there's more to find, and more you can use to your advantage. So let's look at your social media
    profile, and your website if you have one.</p>
    <p>You've just read the words your buyers use. Next you see your own words the way a stranger
    sees them, and the four questions they're asking while they read. It's free like this one&hellip;</p>
    """ + cta_link + """
  </div>

  <p class="r-foot">Buying Triggers comes from what your market already buys, and from your buyers
  describing the problem in their own words. Going Beyond The Illusion.</p>
  </div>
"""
    if fragment:
        return body
    page = _shell(body, title_suffix="&mdash; " + e(shown))
    return page.replace("</style>", _REPORT_CSS + "</style>")
