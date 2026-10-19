"""The form that asks a coach for their own material, and the page their profile comes back on.

Step two of the funnel. By the time anyone sees this we already know their name, their email and
their market, so this asks for none of it. The token in the link is the identity.

Four fields and not one of them is required on its own. A coach with no website, no recent post or
no banner still gets a report, because the report was built to survive every combination. The only
rule is that they give us something.

Nothing here promises what we do not yet do. There is no line about deleting the screenshot after
thirty days, because that job is not built. The day it is, the line goes in.
"""
import html

import brand as _brand


# The social pages used to borrow the website audit's light shell, so the coach went from two dark
# pages to a light grey one and it looked like somebody else's website. They have their own dark
# shell now, built from the same brand pieces as the triggers pages, so the funnel reads as one thing.
_CSS = _brand.FONT_FACES + _brand.BRAND_TOKENS + _brand.CHROME_CSS + _brand.FUNNEL_CSS + """
  *{box-sizing:border-box}
  html{background:var(--navy)}
  body{margin:0;background:var(--navy);color:var(--ivory);line-height:1.6;
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    -webkit-font-smoothing:antialiased}
  body::before{content:"";position:fixed;inset:0;background:var(--halo);pointer-events:none;z-index:0}
  .soc{max-width:760px;margin:0 auto;padding:44px 24px 76px;position:relative;z-index:1}
  .gb-nav,.gb-foot{position:relative;z-index:1}

  /* ---------- the form ---------- */
  .formerr{background:rgba(200,16,46,.14);border:1px solid var(--cta-soft);color:#fff;border-radius:10px;
    padding:12px 16px;font-size:15px;margin:0 0 14px}
  .scard{display:grid;grid-template-columns:26px minmax(0,1fr);column-gap:14px;background:var(--navy-card);
    border:1px solid var(--navy-line);border-radius:14px;padding:22px 20px;margin:0 0 12px}
  .scard .sn{width:26px;height:26px;border-radius:50%;background:var(--cta);color:#fff;font-size:12.5px;
    font-weight:800;display:flex;align-items:center;justify-content:center;margin-top:2px}
  .scard label.lab{display:block;font-family:var(--display);font-weight:700;font-size:18px;
    letter-spacing:-.015em;color:#fff;line-height:1.3}
  .scard .sub{font-size:14px;line-height:1.55;color:var(--ivory-dim);margin:3px 0 14px}
  .scard textarea,.scard input[type=text]{width:100%;border:1px solid rgba(255,255,255,.22);border-radius:8px;
    padding:13px 14px;font-size:16px;color:var(--ivory);background:var(--navy-deep);font-family:inherit;
    line-height:1.5}
  .scard textarea{min-height:84px;resize:vertical}
  .scard textarea::placeholder,.scard input::placeholder{color:var(--ivory-dim)}
  .scard textarea:focus,.scard input:focus{outline:2px solid var(--glow);outline-offset:1px}

  /* The banner drop box. The real file input sits inside it, invisible, so a click anywhere on the box
     opens the picker and a screen reader still finds an ordinary file field. */
  .drop{position:relative;display:flex;align-items:center;gap:14px;border:1.5px dashed rgba(255,255,255,.28);
    border-radius:10px;padding:14px;background:var(--navy-deep);cursor:pointer;
    transition:border-color .15s,background .15s}
  .drop:hover,.drop.over{border-color:var(--cta-soft);background:rgba(200,16,46,.07)}
  .drop input[type=file]{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
  .drop:focus-within{outline:2px solid var(--glow);outline-offset:2px}
  .drop .di{width:36px;height:36px;border-radius:8px;background:var(--navy-card);border:1px solid var(--navy-line);
    display:flex;align-items:center;justify-content:center;flex-shrink:0;color:var(--glow)}
  .drop .dt{font-size:14.5px;font-weight:600;color:#fff;line-height:1.35}
  .drop .dt small{display:block;font-size:12.5px;font-weight:400;color:var(--ivory-dim)}
  .drop img.prev{display:none;width:100%;max-height:160px;object-fit:cover;border-radius:6px}
  .drop.has{flex-direction:column;align-items:stretch}
  .drop.has img.prev[src]{display:block}
  .drop.has .di{display:none}

  .sgo{display:block;width:100%;background:var(--cta);color:var(--cta-ink);border:0;border-radius:var(--pill);
    padding:17px 30px;font-size:17px;font-weight:700;cursor:pointer;font-family:inherit;margin:6px 0 0;
    box-shadow:0 10px 30px rgba(200,16,46,.25)}
  .sgo:hover{background:var(--cta-h)}
  .soc .hint{text-align:center;font-size:13.5px;color:var(--ivory-dim);margin:12px 0 0}
  #socwork{display:none}
  #socwork.on{display:block}

  /* ---------- the report ---------- */
  .sbox{background:var(--navy-card);border:1px solid var(--navy-line);border-radius:16px;padding:24px 22px;
    margin:0 0 14px}
  .sbox h2,.sbox h3{font-family:var(--display);font-weight:700;letter-spacing:-.02em;color:#fff;
    font-size:24px;line-height:1.2;margin:0 0 10px}
  .sbox p{font-size:15.5px;line-height:1.65;color:var(--ivory);margin:0 0 12px;max-width:62ch}
  .sbox p:last-child{margin-bottom:0}
  .sbox .gb-six{margin-top:16px}
  .sbox .gb-six .gb-sixc{background:var(--navy-deep)}

  /* social_section.render's own classes, dark. Scoped to .soc so the light /combined page is untouched. */
  .soc .ev{background:var(--navy-card);border:1px solid rgba(111,174,217,.35);border-radius:16px;
    padding:24px 22px;margin:0 0 14px}
  .soc .ev-head{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 16px}
  .soc .ev .h{font-family:var(--display);font-weight:700;font-size:26px;letter-spacing:-.02em;color:#fff;
    line-height:1.2}
  .soc .secnum{display:block;width:fit-content;font-size:10.5px;font-weight:700;letter-spacing:.14em;
    text-transform:uppercase;color:var(--glow);border:1px solid rgba(111,174,217,.55);border-radius:var(--pill);
    padding:3px 10px;margin:0 0 10px}
  .soc .sec-angelo{width:96px;aspect-ratio:3/2;object-fit:cover;border-radius:10px;flex-shrink:0;
    background:#fff;border:1px solid var(--navy-line)}
  .soc .thumb{width:100%;border-radius:10px;border:1px solid var(--navy-line);margin:0 0 6px;display:block}
  .soc .ev .meta{font-size:14.5px;line-height:1.6;color:var(--ivory-dim);margin:8px 0 0}
  .soc .ev .q{font-family:var(--serif);font-style:italic;font-size:19px;line-height:1.5;color:#fff;
    background:var(--navy-deep);border-left:3px solid var(--cta);border-radius:0 8px 8px 0;
    padding:14px 18px;margin:10px 0 0}
  .soc .ev .q.sm{font-size:16.5px}
  .soc .fault{margin:18px 0 0;padding:18px 18px 6px;background:rgba(200,16,46,.08);
    border:1px solid rgba(240,90,110,.35);border-radius:12px;font-size:15px;line-height:1.6;
    color:var(--ivory);counter-reset:sq}
  /* The four stranger questions, numbered, because they are asked in that order. */
  .soc .fault p{position:relative;margin:12px 0 0;padding:12px 0 12px 38px;
    border-top:1px solid rgba(255,255,255,.08);color:var(--ivory-dim);counter-increment:sq}
  .soc .fault p::before{content:counter(sq);position:absolute;left:0;top:13px;width:24px;height:24px;
    border-radius:50%;background:var(--cta);color:#fff;font-size:12px;font-weight:800;
    display:flex;align-items:center;justify-content:center}
  .soc .fault p b{display:block;color:#fff;font-weight:700;font-size:16px}

  .sexits{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:12px}
  .sexit{background:var(--navy-card);border:1px solid var(--navy-line);border-radius:16px;padding:24px 22px;
    display:flex;flex-direction:column}
  .sexit.main{border-color:var(--cta-soft);
    background:linear-gradient(160deg,rgba(200,16,46,.16),transparent 55%),var(--navy-card)}
  .sexit p.gb-eyebrow{font-size:11px;margin:0 0 8px;color:var(--cta-soft)}
  .sexit.alt p.gb-eyebrow{color:var(--ivory-dim)}
  .sexit h3{font-family:var(--display);font-weight:700;font-size:20px;letter-spacing:-.02em;color:#fff;
    margin:0 0 8px}
  .sexit p{font-size:15px;line-height:1.6;color:var(--ivory);margin:0 0 10px}
  .sexit p b{color:#fff}
  .sexit .sp{flex:1;min-height:6px}
  .sexit .gb-btn{text-align:center;width:100%}

  @media(max-width:640px){
    .soc{padding:30px 16px 56px}
    .scard{grid-template-columns:1fr;row-gap:10px;padding:18px 16px}
    .sexits{grid-template-columns:1fr}
    .soc .ev,.sbox{padding:20px 16px}
    .soc .ev .h{font-size:22px}
  }
"""

# Angelo's working screen for this step. Same panel as the triggers one, so the two feel like a pair.
_WORK = """<div id="socwork" class="gb-work" aria-live="polite">
  <div class="gb-work-head">
    <img src="/angelo_typing.png" alt="Angelo at his computer, reading your profile">
    <div>
      <p class="gb-eyebrow">Working on it</p>
      <h3>Angelo is reading your profile</h3>
      <p>A few seconds. Leave this page open. Your page opens here on its own.</p>
    </div>
  </div>
  <div class="pbar"><i></i></div>
  <ul>
    <li id="sw1" class="is-working"><span class="ic"></span>Looking at your banner<span class="st">Working</span></li>
    <li id="sw2"><span class="ic"></span>Reading your bio<span class="st">Waiting</span></li>
    <li id="sw3"><span class="ic"></span>Reading how your last post opens<span class="st">Waiting</span></li>
    <li id="sw4"><span class="ic"></span>Putting it next to your six triggers<span class="st">Waiting</span></li>
  </ul>
</div>"""

# The drop box and the working screen. Both are extras: with JavaScript off the file field still works
# when clicked, and the form posts the ordinary way and lands on the same page.
_JS = """
(function(){
  var form = document.getElementById('socform');
  if(!form) return;
  var drop = document.getElementById('drop');
  var file = document.getElementById('banner');
  var prev = document.getElementById('dropprev');
  var name = document.getElementById('dropname');

  function show(f){
    if(!f) return;
    drop.classList.add('has');
    if(name){
      name.textContent = 'Got it: ' + f.name;
      var sm = document.createElement('small');
      sm.textContent = 'Click or drop another to change it';
      name.appendChild(sm);
    }
    if(prev && /^image\\//.test(f.type)){
      var r = new FileReader();
      r.onload = function(){ prev.src = r.result; };
      r.readAsDataURL(f);
    }
  }
  if(drop && file){
    file.addEventListener('change', function(){ show(file.files[0]); });
    ['dragenter','dragover'].forEach(function(t){
      drop.addEventListener(t, function(e){ e.preventDefault(); drop.classList.add('over'); });
    });
    ['dragleave','drop'].forEach(function(t){
      drop.addEventListener(t, function(e){ e.preventDefault(); drop.classList.remove('over'); });
    });
    drop.addEventListener('drop', function(e){
      if(e.dataTransfer && e.dataTransfer.files.length){
        try { file.files = e.dataTransfer.files; } catch(err) {}
        show(e.dataTransfer.files[0]);
      }
    });
  }

  var work = document.getElementById('socwork');
  var STEPS = 4, HOLD = 9000, busy = false;
  function setStep(n, state){
    var el = document.getElementById('sw' + n);
    if(!el) return;
    el.className = state === 'DONE' ? 'is-done' : state === 'WORKING' ? 'is-working' : '';
    el.querySelector('.st').textContent = state === 'DONE' ? 'Done' : state === 'WORKING' ? 'Working' : 'Waiting';
  }
  form.addEventListener('submit', function(ev){
    if(!window.fetch || !window.FormData || !work) return;
    ev.preventDefault();
    if(busy) return;
    busy = true;
    var data = new FormData(form);
    document.getElementById('sochead').style.display = 'none';
    form.style.display = 'none';
    work.classList.add('on');
    window.scrollTo(0, 0);
    var bar = work.querySelector('.pbar i');
    for(var i = 1; i <= STEPS; i++) setStep(i, i === 1 ? 'WORKING' : 'WAITING');
    var step = 1;
    setTimeout(function(){ bar.style.width = '6%'; }, 60);
    var tick = setInterval(function(){
      setStep(step, 'DONE'); step++;
      if(step <= STEPS) setStep(step, 'WORKING');
      bar.style.width = Math.round((step - 1) / STEPS * 100) + '%';
      if(step > STEPS) clearInterval(tick);
    }, HOLD / STEPS);
    var started = Date.now();
    fetch(form.action, {method: 'POST', body: data}).then(function(r){
      if(!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function(html){
      setTimeout(function(){
        clearInterval(tick);
        for(var i = 1; i <= STEPS; i++) setStep(i, 'DONE');
        bar.style.width = '100%';
        setTimeout(function(){
          // The answer is a whole page: the report, or the form again with a message. Swap it in whole.
          document.open(); document.write(html); document.close();
          window.scrollTo(0, 0);
        }, 450);
      }, Math.max(0, HOLD - (Date.now() - started)));
    }).catch(function(){
      // Something went wrong in the fetch. Send the form the plain way, which still works.
      clearInterval(tick);
      busy = false;
      HTMLFormElement.prototype.submit.call(form);
    });
  });
})();
"""


def page(body, title="Your coaching social media, read the way a stranger reads it"):
    """The whole page for both social screens: the dark shell, a quiet nav, the footer."""
    return ('<!doctype html><html lang="en"><head>'
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            + _brand.head_meta("/social", title, index=False)
            + '<style>' + _CSS + '</style></head><body>'
            + _brand.nav_html(links=False)
            + '<main class="soc">' + body + '</main>'
            + _brand.footer_html()
            + '<script>' + _JS + '</script></body></html>')


def _hero(eyebrow, heading, lede, img, alt):
    """Heading on the left, Angelo in a frame on the right. `heading` and `lede` arrive escaped."""
    e = html.escape
    return (f'<div class="gb-ihero"><div class="gb-icopy">'
            f'<p class="gb-eyebrow">{e(eyebrow)}</p><h1>{heading}</h1>'
            f'<p class="gb-ilede">{lede}</p></div>'
            f'<img class="gb-angelo" src="{img}" alt="{e(alt, quote=True)}"></div>')


def _val(values, key):
    return html.escape((values or {}).get(key, ""), quote=True)


_UPLOAD_ICON = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                '<path d="M12 19V5M5 12l7-7 7 7"/></svg>')


def render_form(first_name="", audience="", token="", error="", values=None):
    """Step two: the form, as the body for page()."""
    e = html.escape
    fn = e(first_name.strip().split(" ")[0]) if first_name.strip() else ""
    hello = f"{fn}, now " if fn else "Now "
    who = e(audience) if audience else "your buyers"
    lede = (f"You've read what {who} buy on. This next part shows you what they get from you."
            if audience else
            "This next part shows you what a stranger sees when they find you.")
    err = f'<div class="formerr" role="alert">{e(error)}</div>' if error else ""

    # Angelo at his flipchart, not giving a verdict. Nothing has been read yet, so a thumbs down here
    # would judge the coach before we have seen a word of theirs.
    head = ('<div id="sochead">' + _brand.steps_html(2)
            + _hero("Step 2: Your profile", f"{hello}let's look at you", lede,
                    "/angelo_plan.png", "Angelo at his flipchart, ready to go through your profile")
            + '</div>')

    return head + _WORK + f'''
<form method="post" action="/social" enctype="multipart/form-data" id="socform">
  {err}
  <input type="hidden" name="token" value="{e(token, quote=True)}">
  <div class="scard">
    <span class="sn">1</span>
    <div>
      <label class="lab" for="banner">Your banner</label>
      <p class="sub">The picture across the top of your profile. Take a screenshot of it and pick the
      file here.</p>
      <div class="drop" id="drop">
        <span class="di">{_UPLOAD_ICON}</span>
        <img class="prev" id="dropprev" alt="">
        <span class="dt" id="dropname">Pick your screenshot<small>or drag it onto this box</small></span>
        <input type="file" id="banner" name="banner" accept="image/*">
      </div>
    </div>
  </div>
  <div class="scard">
    <span class="sn">2</span>
    <div>
      <label class="lab" for="bio">Your bio</label>
      <p class="sub">The words underneath your name. Copy them and paste them in.</p>
      <textarea id="bio" name="bio" rows="3"
        placeholder="Paste your bio here">{_val(values, "bio")}</textarea>
    </div>
  </div>
  <div class="scard">
    <span class="sn">3</span>
    <div>
      <label class="lab" for="post">Your last post</label>
      <p class="sub">The one you put up most recently. Not your best one. Your last one.</p>
      <textarea id="post" name="post" rows="4"
        placeholder="Paste your last post here">{_val(values, "post")}</textarea>
    </div>
  </div>
  <div class="scard">
    <span class="sn">4</span>
    <div>
      <label class="lab" for="website">Your website</label>
      <p class="sub">Only if you've got one. Leave it empty if you haven't, and you'll still get
      everything else.</p>
      <input type="text" id="website" name="website" placeholder="yourwebsite.com"
        inputmode="url" autocapitalize="off" autocorrect="off" spellcheck="false"
        value="{_val(values, "website")}">
    </div>
  </div>
  <button type="submit" class="sgo">Show me what they see</button>
  <p class="hint">You don't have to fill in all four. We'll read whatever you give us.</p>
</form>'''


def report_head(first_name="", audience=""):
    """The top of their social report: where they are, and what this page is."""
    e = html.escape
    fn = e(first_name.strip().split(" ")[0]) if first_name.strip() else ""
    hello = f"{fn}, here's" if fn else "Here's"
    lede = (f"We've looked at your social media profile. You've already read what {e(audience)} "
            "buy on. This is what they get from you.")
    return (_brand.steps_html(2)
            + _hero("Your profile, read back to you",
                    f"{hello} what a stranger sees when they find you", lede,
                    "/angelo_unsure.png", "Angelo, weighing up your profile"))


def reminder(audience, triggers):
    """Their six triggers as cards, because they are the lens for everything underneath.

    `triggers` is [(category, name), ...] in trigger order.
    """
    e = html.escape
    return ('<div class="sbox"><h3>A reminder of your six buying triggers</h3>'
            f'<p>This is what {e(audience)} buy on. Keep it in your head while you read the rest.</p>'
            + _brand.six_cards(triggers) + '</div>')


def exits(token="", website="", count=""):
    """Where they go after the social report.

    Two doors, and they are deliberately not the same size. The website route ends in a real score
    against every site we have read, which is the strongest thing we have, so it is the obvious one.
    The other door is there because a coach with no website is not a coach we want to lose.
    """
    e = html.escape
    q = f"?lead={e(token, quote=True)}" if token else ""
    reading = (f"We've read {e(count)} coaching websites. Yours gets the same treatment."
               if count else "Yours gets read the same way we read every other coaching site.")
    if website:
        known = f'<p>You gave us <b>{e(website)}</b>, so we already know where to look.</p>'
    else:
        known = '<p>You tell us the address on the next page.</p>'
    return f'''<div class="sbox">
  <h2>So what next</h2>
  <p>That was someone who already knew a little about you. They'd seen something of yours and
  clicked your name.</p>
  <p>Your website gets a colder version of that person. They arrive from a search or a link, they
  know nothing about you, and nothing has made them interested yet. Everything your profile got for
  free, your website has to earn.</p>
</div>
<div class="sexits">
  <div class="sexit main">
    <p class="gb-eyebrow">Step 3</p>
    <h3>Have your website read</h3>
    <p>{reading}</p>
    {known}
    <span class="sp"></span>
    <a class="gb-btn primary" href="/website{q}">Read my website</a>
  </div>
  <div class="sexit alt">
    <p class="gb-eyebrow">Or</p>
    <h3>No website?</h3>
    <p>Plenty of coaches haven't got one, and it isn't a problem. You can carry on from here.</p>
    <span class="sp"></span>
    <a class="gb-btn ghost" href="/salespage{q}">Carry on without one</a>
  </div>
</div>'''
