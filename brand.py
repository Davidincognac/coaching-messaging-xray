"""Single source of truth for the look of every page we serve.

Before this file there were three near-identical `:root` blocks (app.py PAGE, app.py
_SALES_CSS, triggers.py _CSS) and changing a colour meant changing it three times and
missing one. Everything visual that is shared now lives here and the three stylesheets
import it.

The palette is taken from goingbeyondtheillusion.com so the funnel pages and the main
site read as one business: near-black #111111 for the hero and footer bands, red
#C8102E for anything you click, #2E75B6 blue for accents, #333333 body text on white.

TWO THINGS THAT WILL BITE IF YOU FORGET THEM:

1. `--cta` is red, and red takes WHITE text. The old gold took navy text. Any new
   button must use `color:var(--cta-ink)`, never `var(--navy)`.
2. `--cta` at #C8102E on a near-black background is about 3:1 contrast, which is not
   readable. For red TEXT or small marks on a dark band use `--cta-soft`, which is the
   same red lifted until it passes. Fills and borders can use `--cta` on either.

PAGE in app.py is a .format() template, so its CSS braces have to be doubled. Use
`fmt(BRAND_TOKENS)` there and the plain string everywhere else.
"""

import html
import os
from datetime import datetime

# --------------------------------------------------------------------------- company

COMPANY = {
    "site": "Going Beyond The Illusion",
    "legal": "David Poole and Associates",
    "street": "12 Impasse St Benoit",
    "town": "Cognac",
    "postcode": "16100",
    "country": "France",
    "siret": "78989173600025",
    "vat": "FR43789891736",
    "email": "david@goingbeyondtheillusion.com",
}

# --------------------------------------------------------------------------- type

# Both faces are served by us from the app directory, so no request ever leaves for a
# font CDN and nothing shifts while a page loads.
FONT_FACES = """
  @font-face{font-family:'Inter';font-weight:100 900;font-display:swap;src:url(/inter.woff2) format('woff2')}
  @font-face{font-family:'SourceSerif';font-weight:200 900;font-display:swap;src:url(/serif.woff2) format('woff2')}
  @font-face{font-family:'Outfit';font-weight:100 900;font-display:swap;src:url(/outfit.woff2) format('woff2')}
"""

# --------------------------------------------------------------------------- palette

BRAND_TOKENS = """
  :root{
    --display:'Outfit',-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
    --serif:'SourceSerif',Georgia,'Times New Roman',serif;

    /* dark bands: hero, footer, the triggers and social pages */
    --navy:#111111;          /* the site's black, straight off the homepage hero */
    --navy-card:#1A1A2E;     /* the homepage's deep navy, used for cards on black */
    --navy-deep:#131320;     /* inset surfaces: inputs sitting inside a card */
    --navy-line:#2E2E4A;     /* borders on dark */
    --ivory:#F4F5F7;         /* body text on dark */
    --ivory-dim:#A8AAB8;     /* secondary text on dark */

    /* light bands: the report canvas and the salespage */
    --paper:#F4F5F7;--surface:#fff;
    --ink:#333333;           /* the site's body colour */
    --muted:#6B6B6B;--line:#E3E3E6;

    /* blue accent, lifted straight from the homepage */
    --accent:#2E75B6;--accent-ink:#1F5286;--glow:#6FAED9;--soft:#EAF2F9;

    /* the click colour. white text on it, always. */
    --cta:#C8102E;--cta-h:#A50D26;--cta-ink:#FFFFFF;
    --cta-soft:#F05A6E;      /* the readable red, for text and marks on a dark band */
    --grad:linear-gradient(100deg,#F05A6E 0%,#C8102E 55%,#8F1D1D 100%);
    --halo:radial-gradient(900px 480px at 78% -8%,rgba(200,16,46,.28),transparent 68%);
    --pill:999px;
    --card-dark:rgba(255,255,255,.045);
    --card-dark-line:rgba(255,255,255,.10);

    /* verdicts. --critical is deliberately a duller red than --cta so a bad score
       does not read as something you are meant to click. */
    --good:#2A7B56;--good-glow:#5CB88C;--warn:#A87B23;--warn-ink:#7A5A16;
    --critical:#8F1D1D;--coral:#F0B9B4;}
"""

# --------------------------------------------------------------- shared page furniture

CHROME_CSS = """
  /* ---------- top bar ---------- */
  /* Deliberately quiet. This is a funnel, and every link in a nav is a way out of it,
     so the bar carries the name, About and Blog and nothing else. The salespage gets
     the same bar with no links at all. */
  .gb-nav{background:var(--navy);border-bottom:1px solid var(--navy-line);
    display:flex;align-items:center;gap:14px;padding:0 24px;height:56px}
  .gb-nav img{height:34px;width:auto;display:block}
  .gb-nav .gb-name{font-size:12px;font-weight:700;letter-spacing:.08em;
    text-transform:uppercase;color:var(--ivory);text-decoration:none}
  .gb-nav .gb-links{margin-left:auto;display:flex;gap:22px}
  .gb-nav .gb-links a{color:var(--ivory-dim);text-decoration:none;font-size:14px;font-weight:600}
  .gb-nav .gb-links a:hover,.gb-nav .gb-links a.on{color:var(--cta-soft)}
  @media(max-width:560px){.gb-nav{padding:0 16px;gap:10px}
    .gb-nav .gb-name{font-size:10px}
    .gb-nav .gb-links{gap:14px}
    .gb-nav .gb-links a{font-size:13px}}

  /* ---------- footer ---------- */
  .gb-foot{background:var(--navy);color:var(--ivory-dim);
    border-top:1px solid var(--navy-line);padding:44px 24px 40px;font-size:14px;line-height:1.65}
  /* 1060 and a 32px gap so all four columns sit on one row on a laptop. At 900 the
     fourth wrapped underneath and ran the full width, which read like a second footer. */
  .gb-foot .gb-fwrap{max-width:1060px;margin:0 auto;display:flex;gap:32px;flex-wrap:wrap}
  .gb-foot .gb-col{flex:1;min-width:190px}
  .gb-foot h4{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
    color:var(--ivory);margin:0 0 12px;font-weight:700}
  .gb-foot a{color:var(--ivory-dim);text-decoration:none}
  .gb-foot a:hover{color:var(--cta-soft)}
  .gb-foot p{margin:0 0 8px}
  .gb-foot .gb-legal{font-size:12.5px;color:var(--muted)}
  .gb-foot ul{list-style:none;margin:0;padding:0}
  .gb-foot li{margin-bottom:7px}
  /* David, discreetly. Angelo fronts the pages; this is the one place a face appears. */
  .gb-foot .gb-me{display:flex;gap:13px;align-items:flex-start}
  .gb-foot .gb-me img{width:46px;height:46px;border-radius:50%;object-fit:cover;
    flex-shrink:0;border:1px solid var(--navy-line)}
  .gb-foot .gb-me p{font-size:13.5px;margin:0}
  .gb-foot .gb-rule{max-width:1060px;margin:32px auto 0;padding-top:18px;
    border-top:1px solid var(--navy-line);font-size:12.5px;color:var(--muted)}

  /* ---------- the craft layer ---------- */
  /* Borrowed in shape from noneed2shout.com, kept in David's colours: Outfit headings
     set tight and large, pill buttons, a gradient on the phrase that carries the idea,
     and a glow so a dark band has depth rather than reading as a flat rectangle. */

  .gb-display{font-family:var(--display);font-weight:700;letter-spacing:-.035em;line-height:1.04}
  h1.gb-display{font-size:clamp(38px,6.4vw,76px)}
  h2.gb-display{font-size:clamp(27px,3.6vw,40px);letter-spacing:-.028em;line-height:1.1}
  h3.gb-display{font-size:clamp(19px,1.8vw,22px);letter-spacing:-.022em;line-height:1.3}

  /* The one phrase per page that carries the idea. Used once, or it stops meaning anything. */
  .gb-grad{background:var(--grad);-webkit-background-clip:text;background-clip:text;
    color:transparent;-webkit-text-fill-color:transparent}

  /* A dark band with light behind it, rather than a flat fill. */
  .gb-dark{background:var(--navy);color:var(--ivory);position:relative;overflow:hidden}
  .gb-dark::before{content:"";position:absolute;inset:0;background:var(--halo);pointer-events:none}
  .gb-dark > *{position:relative}

  .gb-eyebrow{font-size:12.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;
    color:var(--cta-soft);margin:0 0 14px}
  .gb-dark .gb-lede{font-size:clamp(16px,1.5vw,19px);line-height:1.62;color:var(--ivory-dim);
    max-width:56ch;margin:0 0 30px}

  /* Pill buttons. Filled red is the one real action; the outline is the way out. */
  .gb-btn{display:inline-block;border-radius:var(--pill);padding:14px 26px;font-weight:600;
    font-size:16px;text-decoration:none;border:1.5px solid transparent;cursor:pointer;
    font-family:inherit;transition:background .15s,color .15s}
  .gb-btn.primary{background:var(--cta);color:var(--cta-ink)}
  .gb-btn.primary:hover{background:var(--cta-h)}
  .gb-btn.ghost{background:transparent;color:var(--ivory);border-color:rgba(255,255,255,.30)}
  .gb-btn.ghost:hover{border-color:var(--ivory);background:rgba(255,255,255,.06)}
  .gb-btnrow{display:flex;gap:13px;flex-wrap:wrap;align-items:center}

  /* Cards on a dark band: barely-there fill, one hairline, a big numeral doing the work. */
  .gb-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px;margin:34px 0 0}
  .gb-card{background:var(--card-dark);border:1px solid var(--card-dark-line);
    border-radius:16px;padding:28px 26px}
  .gb-card .num{font-family:var(--display);font-weight:800;font-size:40px;line-height:1;
    color:var(--cta-soft);margin-bottom:14px;letter-spacing:-.03em}
  .gb-card h3{font-family:var(--display);font-weight:700;font-size:19px;letter-spacing:-.02em;
    margin:0 0 9px;color:#fff;line-height:1.28}
  .gb-card p{margin:0;font-size:15.5px;line-height:1.62;color:var(--ivory-dim)}

  /* A short gradient rule above a heading on a light band. Replaces an eyebrow where the
     heading can carry itself. */
  .gb-rule-sm{width:48px;height:4px;border-radius:2px;background:var(--grad);margin:0 0 20px}

  /* The bordered callout. Gradient edge, white fill, for the one paragraph that answers
     the question the page title asked. */
  .gb-callout{position:relative;background:var(--surface);border-radius:16px;
    padding:26px 30px;margin:0 0 30px}
  .gb-callout::before{content:"";position:absolute;inset:0;border-radius:16px;padding:1.5px;
    background:var(--grad);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
    -webkit-mask-composite:xor;mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
    mask-composite:exclude;pointer-events:none}
  .gb-callout .gb-eyebrow{color:var(--cta)}
  .gb-callout p{margin:0;font-size:17.5px;line-height:1.6;color:var(--ink)}

  /* Portrait with an offset gradient block behind it. */
  .gb-portrait{position:relative;flex-shrink:0}
  .gb-portrait img{display:block;width:100%;border-radius:18px;position:relative;z-index:1}
  .gb-portrait::after{content:"";position:absolute;inset:16px -16px -16px 16px;border-radius:18px;
    background:var(--grad);z-index:0}
  .gb-namecard{position:absolute;left:-14px;bottom:26px;z-index:2;background:#fff;color:var(--ink);
    border-radius:10px;padding:10px 14px;font-size:13.5px;line-height:1.35;font-weight:600;
    box-shadow:0 6px 22px rgba(0,0,0,.28)}
  .gb-namecard span{display:block;font-weight:400;color:var(--muted)}

  .gb-split{display:flex;gap:56px;align-items:center}
  .gb-split .gb-copy{flex:1;min-width:0}
  .gb-split .gb-portrait{width:38%;max-width:380px}
  @media(max-width:820px){.gb-split{flex-direction:column;gap:36px}
    .gb-split .gb-portrait{width:100%;max-width:320px}}
"""


# ------------------------------------------------------------ the funnel's shared pieces

# Three things the triggers pages and the social pages both use, kept here so the two halves of the
# funnel cannot drift apart: the step tracker, Angelo in a framed card, and the six triggers as cards.
FUNNEL_CSS = """
  /* ---------- step tracker: where the coach is, out of three ---------- */
  .gb-steps{display:flex;flex-wrap:wrap;align-items:center;gap:8px;list-style:none;margin:0 0 22px;padding:0}
  /* is-done / is-now, not done / now: triggers.py already has a .done box with 30px of padding. */
  .gb-steps li{margin:0;display:flex;align-items:center;gap:8px;padding:6px 13px 6px 7px;border-radius:var(--pill);
    background:var(--navy-card);border:1px solid var(--navy-line);font-size:13px;font-weight:600;
    color:var(--ivory-dim);line-height:1.2}
  .gb-steps .sn{width:20px;height:20px;border-radius:50%;background:var(--navy-line);color:var(--ivory);
    display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;flex-shrink:0}
  .gb-steps li.is-done{color:var(--ivory)}
  .gb-steps li.is-done .sn{background:var(--good)}
  .gb-steps li.is-now{color:#fff;border-color:var(--cta-soft);background:rgba(200,16,46,.14)}
  .gb-steps li.is-now .sn{background:var(--cta)}
  @media(max-width:480px){.gb-steps li{font-size:12px;padding:5px 10px 5px 6px}}

  /* ---------- Angelo in a frame, for the hero of an inner page ---------- */
  .gb-angelo{width:155px;aspect-ratio:4/3;object-fit:cover;border-radius:14px;flex-shrink:0;
    border:1px solid var(--navy-line);box-shadow:0 12px 30px rgba(0,0,0,.45);background:#fff}
  .gb-ihero{display:flex;gap:26px;align-items:center;justify-content:space-between;margin:0 0 26px}
  .gb-ihero .gb-icopy{flex:1;min-width:0}
  .gb-ihero h1{font-family:var(--display);font-weight:700;letter-spacing:-.03em;line-height:1.06;
    font-size:clamp(30px,4.6vw,42px);margin:0 0 12px;color:#fff;text-wrap:balance}
  .gb-ihero .gb-eyebrow{margin-bottom:10px}
  .gb-ihero .gb-ilede{font-size:16px;line-height:1.65;color:var(--ivory-dim);margin:0;max-width:56ch}
  @media(max-width:600px){
    .gb-ihero{flex-direction:column-reverse;align-items:flex-start;gap:16px}
    .gb-angelo{width:120px}}

  /* ---------- the six triggers as cards ---------- */
  .gb-six{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0;padding:0;list-style:none}
  .gb-six li{margin:0}
  .gb-six a,.gb-six .gb-sixc{display:block;height:100%;background:var(--navy-card);border:1px solid var(--navy-line);
    border-radius:10px;padding:14px 13px;text-decoration:none;color:var(--ivory)}
  .gb-six a:hover{border-color:var(--cta-soft)}
  .gb-six .n{width:22px;height:22px;border-radius:50%;background:var(--cta);color:#fff;font-size:11.5px;
    font-weight:800;display:flex;align-items:center;justify-content:center;margin:0 0 10px}
  .gb-six .c{display:block;font-size:9.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--ivory-dim);
    font-weight:700;line-height:1.4;margin:0 0 5px}
  .gb-six .t{display:block;font-family:var(--serif);font-size:16px;font-weight:600;line-height:1.3;color:#fff}
  @media(max-width:700px){.gb-six{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:420px){.gb-six{grid-template-columns:1fr}}

  /* ---------- Angelo working: one panel, used by both working screens ---------- */
  .gb-work{max-width:760px;margin:20px auto 0;background:var(--navy-card);border:1px solid var(--navy-line);
    border-radius:16px;padding:28px;box-shadow:0 18px 50px rgba(0,0,0,.45)}
  .gb-work-head{display:flex;gap:22px;align-items:center;margin:0 0 22px}
  .gb-work-head img{width:180px;aspect-ratio:3/2;object-fit:cover;border-radius:12px;flex-shrink:0;
    background:#fff;border:1px solid var(--navy-line);animation:gb-bob 2.6s ease-in-out infinite}
  .gb-work-head .gb-eyebrow{font-size:11px;margin:0 0 6px}
  .gb-work-head h3{font-family:var(--display);font-weight:700;font-size:30px;letter-spacing:-.025em;
    line-height:1.12;margin:0 0 8px;color:#fff;text-align:left}
  .gb-work-head p{font-size:14px;line-height:1.55;color:var(--ivory-dim);margin:0}
  .gb-work-head p.gb-eyebrow{color:var(--cta-soft)}
  .gb-work .pbar{height:8px;background:var(--navy-deep);border:1px solid var(--navy-line);border-radius:6px;
    overflow:hidden;margin:0 0 10px}
  .gb-work .pbar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--cta),var(--cta-soft));
    border-radius:6px;transition:width .6s linear}
  .gb-work ul{list-style:none;margin:0;padding:0}
  .gb-work li{margin:0;display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid var(--navy-line);
    font-size:14.5px;line-height:1.45;color:var(--ivory-dim)}
  .gb-work li:last-child{border-bottom:0}
  .gb-work li .ic{width:20px;height:20px;border-radius:50%;border:2px solid var(--navy-line);flex-shrink:0;
    display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;color:#fff}
  .gb-work li .st{margin-left:auto;font-size:10.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
    padding:4px 9px;border-radius:var(--pill);background:rgba(255,255,255,.06);color:var(--ivory-dim);white-space:nowrap}
  .gb-work li.is-working{color:#fff;font-weight:600}
  .gb-work li.is-working .ic{border-color:var(--navy-line);border-top-color:var(--cta-soft);animation:gb-spin .8s linear infinite}
  .gb-work li.is-working .st{background:rgba(200,16,46,.18);color:var(--cta-soft)}
  .gb-work li.is-done{color:var(--ivory)}
  .gb-work li.is-done .ic{background:var(--good);border-color:var(--good)}
  .gb-work li.is-done .ic::after{content:"\\2713"}
  .gb-work li.is-done .st{background:rgba(42,123,86,.22);color:var(--good-glow)}
  @keyframes gb-spin{to{transform:rotate(360deg)}}
  @keyframes gb-bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
  @media(prefers-reduced-motion:reduce){.gb-work-head img,.gb-work li.is-working .ic{animation:none}}
  @media(max-width:560px){
    .gb-work{padding:20px 16px}
    .gb-work-head{flex-direction:column;align-items:flex-start;gap:14px}
    .gb-work-head img{width:130px}
    .gb-work-head h3{font-size:22px}}
"""

STEP_NAMES = ("Your buying triggers", "Your profile", "Your website")


def steps_html(current):
    """The three steps of the funnel. `current` is 1, 2 or 3; anything before it shows ticked."""
    out = []
    for i, name in enumerate(STEP_NAMES, start=1):
        cls = "is-done" if i < current else ("is-now" if i == current else "")
        mark = "&#10003;" if i < current else str(i)
        cur = ' aria-current="step"' if i == current else ""
        out.append(f'<li class="{cls}"{cur}><span class="sn">{mark}</span>{name}</li>')
    return '<ol class="gb-steps" aria-label="Your progress">' + "".join(out) + "</ol>"


def six_cards(items, link=False):
    """The six triggers at a glance. `items` is [(category, name), ...] in trigger order.

    With link=True each card jumps to that trigger further down the page (#t1 to #t6).
    """
    e = html.escape
    out = []
    for i, (cat, name) in enumerate(items, start=1):
        inner = (f'<span class="n">{i}</span><span class="c">{e(cat)}</span>'
                 f'<span class="t">{e(name)}</span>')
        out.append(f'<li><a href="#t{i}">{inner}</a></li>' if link
                   else f'<li><div class="gb-sixc">{inner}</div></li>')
    return '<ul class="gb-six">' + "".join(out) + "</ul>"


def nav_html(active="", links=True):
    """The top bar. `active` is one of home, about, blog and just bolds that link.

    links=False gives the brand bar with nothing to click, which is what the salespage
    and the report want: once somebody is reading their own result we are not offering
    them the exit.
    """
    items = ""
    if links:
        pages = [("home", "/", "Home"), ("about", "/about", "About"), ("blog", "/blog", "Blog")]
        parts = []
        for key, href, label in pages:
            on = ' class="on"' if key == active else ""
            parts.append('<a href="' + href + '"' + on + ">" + label + "</a>")
        items = '<div class="gb-links">' + "".join(parts) + "</div>"
    return (
        '<nav class="gb-nav">'
        '<img src="/angelo.png" alt="">'
        f'<a class="gb-name" href="/">{COMPANY["site"]}</a>'
        f"{items}</nav>"
    )


def footer_html():
    """Every page ends here. Address, SIRET and VAT are a legal requirement on a French
    business site, not decoration, so they are in the markup rather than an image."""
    c = COMPANY
    # The photo is optional on purpose. Until david.jpg is in the app directory the
    # footer runs the text on its own rather than showing a broken image icon.
    _here = os.path.dirname(os.path.abspath(__file__))
    face = ('<img src="/david.jpg" alt="David Poole">'
            if os.path.exists(os.path.join(_here, "david.jpg")) else "")
    return f"""<footer class="gb-foot">
  <div class="gb-fwrap">
    <div class="gb-col">
      <h4>{c['site']}</h4>
      <p class="gb-legal">by {c['legal']}<br>
        {c['street']}<br>{c['town']}, {c['postcode']}<br>{c['country']}</p>
      <p class="gb-legal">SIRET {c['siret']}<br>VAT {c['vat']}</p>
    </div>
    <div class="gb-col">
      <h4>Pages</h4>
      <ul>
        <li><a href="/">Buying triggers</a></li>
        <li><a href="/about">About</a></li>
        <li><a href="/blog">Blog</a></li>
        <li><a href="/methodology">How we score</a></li>
        <li><a href="mailto:{c['email']}">{c['email']}</a></li>
      </ul>
    </div>
    <div class="gb-col">
      <h4>Legal</h4>
      <ul>
        <li><a href="/privacy">Privacy</a></li>
        <li><a href="/terms">Terms</a></li>
        <li><a href="/cookies">Cookies</a></li>
      </ul>
    </div>
    <div class="gb-col">
      <h4>Who runs this</h4>
      <div class="gb-me">
        {face}
        <p>David Poole. I research coaching markets and build the marketing
           around what the research finds. <a href="/about">More about me</a>.</p>
      </div>
    </div>
  </div>
  <div class="gb-rule">&copy; {c['legal']}. Angelo is our own illustration.</div>
</footer>"""


def fmt(css):
    """Double the braces so a stylesheet survives being passed through str.format().

    app.py's PAGE is a .format() template. Anything with real CSS braces going into it
    has to be escaped first or format() reads them as field names and raises.
    """
    return css.replace("{", "{{").replace("}", "}}")


# ------------------------------------------------------------------------ seo

# The one address search engines should ever see. Everything else 301s here, so every
# page names this as its canonical and no two URLs compete for the same content.
BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")

# Search Console and Bing both verify a site by a string they generate. It is not a secret:
# it sits in the source of every page we serve, which is the whole point of it. Google's is
# here as the default so that deploying is the only step, with the environment able to
# override it the day the property is rebuilt or the token rotated.
GOOGLE_SITE_VERIFICATION = os.getenv(
    "GOOGLE_SITE_VERIFICATION",
    "vBTi2DXa4Mg6QLj1HI4el391T6tfWBkrxT0oYDHCS4E",   # property: https://go.goingbeyondtheillusion.com/
).strip()
BING_SITE_VERIFICATION = os.getenv("BING_SITE_VERIFICATION", "").strip()

# Google shows roughly 60 characters of a title. A bare "Blog" wastes that room, so short
# titles get the company name after them and long ones are left alone: the words that say
# what the page is worth more than a brand nobody is searching for yet.
TITLE_SUFFIX = " | " + COMPANY["site"]


def page_title(title):
    """The <title> as a searcher sees it in a result."""
    title = (title or "").strip()
    if not title:
        return COMPANY["site"]
    if COMPANY["site"].lower() in title.lower():
        return title
    return title + TITLE_SUFFIX if len(title) + len(TITLE_SUFFIX) <= 60 else title


def head_meta(path="/", title="", description="", index=True, image=""):
    """The whole head: title, description, canonical, robots and the social-share tags.

    The title and description live here rather than in each page shell because they were in
    both, and the two drifted. The homepage went out as "Buying Triggers" while the social
    card carried the sentence we actually wanted, and /website shipped with no description
    at all. One function owns them now, so they cannot disagree again.

    `index=False` is for anything personal: a coach's own report, their salespage, any
    URL carrying their token. Those must never reach a search result. They are thin and
    duplicated across thousands of coaches, and the token in the URL is theirs, not
    something to publish.
    """
    canonical = BASE_URL + path
    robots = ("index,follow" if index
              else "noindex,nofollow,noarchive")
    og_title = html.escape(title or COMPANY["site"], quote=True)
    og_desc = html.escape(description or "", quote=True)
    tags = []
    if title:
        tags.append(f'<title>{html.escape(page_title(title))}</title>')
    if description:
        tags.append(f'<meta name="description" content="{og_desc}">')
    tags += [
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">',
        f'<meta name="robots" content="{robots}">',
        f'<meta property="og:site_name" content="{html.escape(COMPANY["site"], quote=True)}">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{og_title}">',
        f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">',
        f'<link rel="alternate" type="application/rss+xml" title="{html.escape(COMPANY["site"], quote=True)}" href="{BASE_URL}/feed.xml">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{og_title}">',
    ]
    if og_desc:
        tags.append(f'<meta property="og:description" content="{og_desc}">')
        tags.append(f'<meta name="twitter:description" content="{og_desc}">')
    # A post that carries its own picture shares that picture. Angelo is the fallback
    # because he is the only image we have that still reads at thumbnail size.
    card = image if image.startswith("http") else (BASE_URL + (image or "/angelo.png"))
    tags.append(f'<meta property="og:image" content="{html.escape(card, quote=True)}">')
    tags.append(f'<meta name="twitter:image" content="{html.escape(card, quote=True)}">')
    if GOOGLE_SITE_VERIFICATION:
        tags.append('<meta name="google-site-verification" content="'
                    + html.escape(GOOGLE_SITE_VERIFICATION, quote=True) + '">')
    if BING_SITE_VERIFICATION:
        tags.append('<meta name="msvalidate.01" content="'
                    + html.escape(BING_SITE_VERIFICATION, quote=True) + '">')
    return "\n".join(tags)


# The pages worth a search engine's time. Everything else is either personal or a
# duplicate of one of these, so the sitemap lists these and only these.
PUBLIC_PAGES = [
    ("/", "1.0", "weekly"),
    ("/about", "0.8", "monthly"),
    ("/blog", "0.7", "weekly"),
    # Every post cites the corpus; this is the page that says what the corpus is.
    ("/methodology", "0.6", "yearly"),
    ("/website", "0.6", "monthly"),
    ("/privacy", "0.2", "yearly"),
    ("/terms", "0.2", "yearly"),
    ("/cookies", "0.2", "yearly"),
]


def robots_txt():
    """Public pages open, everything personal closed.

    The Disallow lines are not a privacy control (a token in a URL is still a token), they
    stop thousands of near-identical coach reports being crawled and treated as thin
    duplicate content across the whole site.
    """
    return (
        "User-agent: *\n"
        "Allow: /$\n"
        "Disallow: /social\n"
        "Disallow: /salespage\n"
        "Disallow: /offer\n"
        "Disallow: /mockup/\n"
        "Disallow: /uploads/\n"
        "Disallow: /audit\n"
        "Disallow: /*?lead=\n"
        "Disallow: /*?url=\n"
        "Disallow: /*?domain=\n"
        "\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )


def sitemap_xml(blog_urls=()):
    """The public pages plus whatever posts exist. No dates we cannot stand behind:
    a lastmod we invent is worse than no lastmod at all.

    A post is the exception, because its date is written in its own front matter. Passing
    `blog_urls` as (path, date) pairs reports that date; passing bare paths still works and
    simply says nothing, which is the same promise as before.
    """
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, priority, freq in PUBLIC_PAGES:
        out.append(f"  <url><loc>{BASE_URL}{path}</loc>"
                   f"<changefreq>{freq}</changefreq><priority>{priority}</priority></url>")
    for entry in blog_urls:
        path, date = entry if isinstance(entry, (tuple, list)) else (entry, "")
        stamp = f"<lastmod>{date}</lastmod>" if _is_iso_date(date) else ""
        out.append(f"  <url><loc>{BASE_URL}{path}</loc>{stamp}"
                   f"<changefreq>monthly</changefreq><priority>0.6</priority></url>")
    out.append("</urlset>")
    return "\n".join(out)


def _is_iso_date(value):
    """A malformed date in a post would invalidate the whole sitemap, so it is dropped
    rather than passed through."""
    try:
        datetime.strptime((value or "").strip(), "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------- blog furniture

def cta_block(heading="Want to know why your market buys?"):
    """The one thing every blog post is for. Same trade as the homepage heading, because
    a reader who meets the offer twice in two different wordings is being sold to twice;
    meeting the same sentence twice is being told the same thing.

    It used to be a heading, a sentence and a button, which is a link wearing a box. A
    reader who has just read two thousand words of evidence gets told what is in the thing
    and what it was built from, because by our own scoring a page that names the free thing
    beats one that just points at it.
    """
    return f"""<aside class="gb-cta">
  <h2 class="gb-display">{html.escape(heading)}</h2>
  <p>Tell us who you coach and Angelo pulls the six things that decide it, from the research
     behind this article: 918 coaching markets, 2,004 books those buyers paid for, and 1,547
     things real buyers wrote about their own situation.</p>
  <ul class="gb-ctalist">
    <li>What they are really buying, under the thing they say they want</li>
    <li>The moment it got too much and they started looking</li>
    <li>What they picture once it is sorted</li>
    <li>The fear that keeps their card in their pocket</li>
    <li>The promises they have stopped believing</li>
    <li>Why they pick one coach over the next one</li>
  </ul>
  <p class="gb-ctafoot">It opens on the page in about 20 seconds. Nothing to pay.</p>
  <a class="gb-btn primary" href="/">Show me my buying triggers</a>
</aside>"""


def cta_inline():
    """The same offer, halfway down, for the reader who will not reach the end.

    Two thousand words is a long way to carry somebody before asking them anything, and the
    posts themselves say a page with one ask and no other way to stay in touch loses the
    people who are not ready today.
    """
    return """<aside class="gb-midcta">
  <p><b>Reading this because your enquiries are thin?</b> The same research behind these
     numbers will tell you what your own market buys and why, market by market.
     <a href="/">See your buying triggers</a>, free, about 20 seconds.</p>
</aside>"""


def breadcrumbs(trail):
    """`trail` is [(label, href), ...] ending with the current page, whose href is ignored."""
    parts = []
    for i, (label, href) in enumerate(trail):
        last = i == len(trail) - 1
        parts.append(f'<span aria-current="page">{html.escape(label)}</span>' if last
                     else f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')
    return '<nav class="gb-crumbs">' + '<span class="sep">/</span>'.join(parts) + "</nav>"


def _jsonld(obj):
    import json as _j
    # "</" inside a script block would close it early, so it is escaped rather than trusted.
    return ('<script type="application/ld+json">'
            + _j.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
            + "</script>")


PERSON = {
    "@type": "Person",
    "name": "David Poole",
    "url": BASE_URL + "/about",
    "jobTitle": "Market researcher and marketing builder",
    "worksFor": {"@type": "Organization", "name": COMPANY["legal"]},
}


ORGANISATION = {
    "@type": "Organization",
    "@id": BASE_URL + "/#organisation",
    "name": COMPANY["site"],
    "legalName": COMPANY["legal"],
    "url": BASE_URL,
    "email": COMPANY["email"],
    "logo": BASE_URL + "/angelo.png",
    "founder": {"@id": BASE_URL + "/#david"},
    "address": {
        "@type": "PostalAddress",
        "streetAddress": COMPANY["street"],
        "addressLocality": COMPANY["town"],
        "postalCode": COMPANY["postcode"],
        "addressCountry": "FR",
    },
    # The registration numbers are the part a search engine can check against a public
    # register, which is most of what separates a real company from a page claiming to be one.
    "vatID": COMPANY["vat"],
    "taxID": COMPANY["siret"],
}


def site_schema():
    """Who runs this site, on the page that is the site.

    Every page carried a canonical and a title and not one of them said who was behind it.
    The Organization and the Person are the entities the rest of the markup already points
    at, so they are declared once here with ids the blog posts can reference rather than
    repeat.
    """
    return _jsonld({"@context": "https://schema.org", "@graph": [
        ORGANISATION,
        {**PERSON, "@id": BASE_URL + "/#david"},
        {
            "@type": "WebSite",
            "@id": BASE_URL + "/#website",
            "url": BASE_URL,
            "name": COMPANY["site"],
            "publisher": {"@id": BASE_URL + "/#organisation"},
        },
    ]})


def person_schema(path="/about"):
    """The about page is about a person, and saying so is the whole job."""
    return _jsonld({"@context": "https://schema.org", "@graph": [
        {
            "@type": "ProfilePage",
            "url": BASE_URL + path,
            "mainEntity": {"@id": BASE_URL + "/#david"},
        },
        {**PERSON, "@id": BASE_URL + "/#david",
         "description": "Reads and scores coaching websites, then builds from what the "
                        "counting says rather than from what sounds right."},
        ORGANISATION,
    ]})


def tool_schema(name, description, path):
    """A free tool is a thing a searcher can use, not an article they can read.

    price 0 is stated rather than left out, because "free" in prose is a claim and an offer
    with a zero price is a fact a search engine can carry into the result.
    """
    return _jsonld({"@context": "https://schema.org", "@graph": [
        {
            "@type": "WebApplication",
            "name": name,
            "description": description,
            "url": BASE_URL + path,
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Any",
            "provider": {"@id": BASE_URL + "/#organisation"},
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        },
        ORGANISATION,
    ]})


def article_schema(title, description, path, date="", faqs=(), trail=(), image=""):
    """Article + BreadcrumbList + FAQPage in one block, plus the author and publisher entities.

    The Person entity is what ties a claim to David rather than to an anonymous site, and
    it is the half most blogs leave out. It carries the same @id as the one on /about, and
    the full node ships with every post, so a post read on its own still resolves to the
    person with the address, the company number and the biography behind it. The publisher
    is the same organisation entity rather than a name and a URL retyped.

    FAQPage is only emitted when the post actually has questions, because claiming a
    structure the page does not have is the kind of thing that gets a site ignored rather
    than rewarded.
    """
    graph = [
        {
            "@type": "Article",
            "headline": title[:110],
            "description": description,
            "url": BASE_URL + path,
            "mainEntityOfPage": BASE_URL + path,
            "author": {"@id": BASE_URL + "/#david"},
            "publisher": {"@id": BASE_URL + "/#organisation"},
            "image": image if image.startswith("http") else BASE_URL + (image or "/angelo.png"),
            **({"datePublished": date, "dateModified": date} if date else {}),
        },
        {**PERSON, "@id": BASE_URL + "/#david"},
        ORGANISATION,
    ]
    if trail:
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": label,
                 "item": BASE_URL + href}
                for i, (label, href) in enumerate(trail)
            ],
        })
    if faqs:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faqs
            ],
        })
    return _jsonld({"@context": "https://schema.org", "@graph": graph})


# The WordPress site that lived here from 2021 to 2024, and where each page goes now.
#
# 490 pages were archived from the old site. Only these have a successor that answers the
# same question, and only those get a 301. The other ~457 keep their 404 on purpose:
#
#   160 coach directory profiles ("life-coaching-by-<name>") — no equivalent page exists,
#       and pointing them at the blog would be a redirect to something the visitor did not
#       ask for, which Google reads as a soft 404 and treats the same as the 404 we already
#       have. A 404 is the honest answer to "that coach's profile is gone".
#    75 angel-number pages — a different website's subject entirely.
#   ~222 pricing posts, local landing pages, course funnels and thank-you pages with
#       nothing on the new site that replaces them.
#
# Redirecting those anywhere would buy nothing and would tell a search engine the new blog
# is about angel numbers. The rule here is one question, one successor, or leave it dead.
LEGACY_REDIRECTS = {
    # getting clients
    "/3-no-cost-ways-to-get-more-coaching-clients": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/create-new-coaching-clients": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/how-can-i-find-coaching-clients-in-2023": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/how-do-life-coaches-get-customers": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/where-do-life-coaches-find-clients": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/how-do-i-sell-myself-as-a-life-coach": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/free-clients-from-google": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/get-clients-free-program": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/how-to-find-clients-as-a-life-coach-using-chatgpt": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/how-to-find-coaching-clients-with-the-law-of-attraction": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/networking-to-find-coaching-clients": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/how-a-life-coach-can-get-referrals": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/client-acquisition-breakdown": "/blog/2026-09-29-how-to-get-coaching-clients",
    "/how-to-find-coaching-clients-without-a-website": "/blog/2026-09-29-coaching-clients-without-a-website",
    "/attract-new-clients-with-free-webinars": "/blog/2026-09-29-attract-coaching-clients",
    "/how-speaking-engagements-can-help-coaches-attract-clients": "/blog/2026-09-29-attract-coaching-clients",
    "/why-sales-doesnt-work-for-coaches": "/blog/2026-09-29-attract-coaching-clients",
    "/4-secret-things-your-coaching-clients-really-want": "/blog/2026-09-29-ideal-coaching-client",
    # niche
    "/whats-the-difference-between-a-coaching-niche-and-an-avatar": "/blog/2026-09-29-niche-versus-audience",
    "/how-to-find-a-great-coaching-niche": "/blog/2026-09-29-how-to-choose-a-coaching-niche",
    "/stuck-at-finding-a-coaching-niche-you-love": "/blog/2026-09-29-how-to-choose-a-coaching-niche",
    # websites
    "/how-to-create-a-coaching-website": "/blog/2026-09-29-website-design-for-life-coaches",
    "/how-to-make-a-coaching-website": "/blog/2026-09-29-website-design-for-life-coaches",
    "/website-for-a-coaching-business": "/blog/2026-09-29-website-design-for-life-coaches",
    # marketing
    "/life-coach-marketing": "/blog/2026-09-29-marketing-for-coaches",
    "/better-marketing": "/blog/2026-09-29-marketing-for-coaches",
    "/are-life-coaches-accidentally-investing-in-marketing": "/blog/2026-09-29-marketing-for-coaches",
    "/the-1-marketing-hack-that-created-70-discovery-calls": "/blog/2026-09-29-marketing-for-coaches",
    "/what-are-the-needle-movers-in-your-coaching-business": "/blog/2026-09-29-marketing-for-coaches",
    "/a-marketing-plan-for-coaches": "/blog/2026-09-29-life-coach-marketing-plan",
    "/5-key-strategies-for-marketing-your-life-coaching-business": "/blog/2026-09-29-life-coach-marketing-plan",
    "/grow-your-coaching-business-with-social-media": "/blog/2026-09-29-social-media-marketing-for-coaches",
    "/social-media-for-finding-clients": "/blog/2026-09-29-social-media-marketing-for-coaches",
    "/how-to-create-a-youtube-channel-for-coaches": "/blog/2026-09-29-social-media-marketing-for-coaches",
    "/blog-for-coaches": "/blog/2026-09-29-content-marketing-for-coaches",
    "/blogging-for-coaches": "/blog/2026-09-29-content-marketing-for-coaches",
    "/how-to-find-coaching-clients-with-blogging": "/blog/2026-09-29-content-marketing-for-coaches",
    "/branding-coach": "/blog/2026-09-29-branding-coaching-business",
    "/how-to-make-your-coaching-business-look-amazing-in-5-days": "/blog/2026-09-29-branding-coaching-business",
}


def legacy_target(path):
    """Where an old WordPress address goes, or None if it is one we let die.

    WordPress served everything with a trailing slash and was case-insensitive in practice,
    so a link out there in the world could be any of four spellings of the same page.
    """
    p = (path or "").rstrip("/").lower()
    return LEGACY_REDIRECTS.get(p or "/")


def rss_xml(posts=()):
    """The blog as a feed.

    A research blog with no feed is one a reader can only keep up with by remembering to
    come back, which nobody does. Descriptions are the post summaries, so the feed says the
    same thing the search result says.
    """
    import email.utils as _eu
    from datetime import datetime as _dt

    def rfc822(iso):
        try:
            return _eu.format_datetime(_dt.strptime(iso, "%Y-%m-%d"))
        except (ValueError, TypeError):
            return ""

    items = []
    for p in posts:
        url = f"{BASE_URL}/blog/{p['slug']}"
        when = rfc822(p.get("date", ""))
        items.append(
            "    <item>\n"
            f"      <title>{html.escape(p['title'])}</title>\n"
            f"      <link>{html.escape(url)}</link>\n"
            f"      <guid isPermaLink=\"true\">{html.escape(url)}</guid>\n"
            + (f"      <pubDate>{when}</pubDate>\n" if when else "")
            + f"      <description>{html.escape(p.get('summary', ''))}</description>\n"
            f"      <dc:creator>{html.escape(PERSON['name'])}</dc:creator>\n"
            "    </item>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            "  <channel>\n"
            f"    <title>{html.escape(COMPANY['site'])}</title>\n"
            f"    <link>{BASE_URL}/blog</link>\n"
            f'    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>\n'
            "    <description>What comes out of scoring 10,954 coaching websites and "
            "mapping 918 coaching markets.</description>\n"
            "    <language>en</language>\n"
            + "\n".join(items) + "\n"
            "  </channel>\n</rss>\n")


def llms_txt(posts=()):
    """A plain-language file telling a model what this site is and which facts are ours.

    The point is not to rank. It is that the numbers below exist nowhere else, so a model
    that cites them has to cite us. Which is exactly why they cannot be a second copy of
    the corpus figures: audit.py owns them, this reads them.
    """
    import audit as _a          # imported here, not at module load, to keep brand.py standalone
    lines = [
        f"# {COMPANY['site']}",
        "",
        "> Market research for coaches. We read and scored 10,954 coaching websites out of 10 "
        "against eleven criteria, and we publish what the scoring found.",
        "",
        "Run by David Poole (David Poole and Associates, Cognac, France). Twelve years building "
        "the marketing infrastructure for the UK driving-instructor market, sold in 2019. Now the "
        "same work for coaches.",
        "",
        "## Original findings you can cite",
        "",
        # These were typed out here as 4.5 / 5.7 / 83, the same figures that had drifted in
        # audit.py and were corrected there against the corpus. This file is the one a model
        # quotes, so it reads the constants now rather than carrying its own copy.
        f"- The average coaching homepage scores {_a.MARKET_AVG_10} out of 10 across eleven "
        f"criteria (n=10,954).",
        f"- The top 10% score {_a.TOP10_10} or higher.",
        f"- {_a.PCT_FAIL_5SEC}% fail the five-second test: a stranger cannot say what the coach does.",
        f"- About 1 in {_a.BUYER_VOICE_1_IN} use their buyer's own language. The rest use their own.",
        "",
        "Source: our own corpus, scored by the tool at " + BASE_URL + "/website",
        "",
        "## Pages",
        "",
        f"- [Buying triggers]({BASE_URL}/): what a given coaching market already buys, and why.",
        f"- [Website X-ray]({BASE_URL}/website): scores any coaching homepage against the corpus.",
        f"- [About]({BASE_URL}/about): who runs this and the evidence behind it.",
        f"- [Blog]({BASE_URL}/blog): what the scoring keeps turning up.",
    ]
    if posts:
        lines.append("")
        lines.append("## Articles")
        lines.append("")
        for p in posts:
            summ = f" — {p['summary']}" if p.get("summary") else ""
            lines.append(f"- [{p['title']}]({BASE_URL}/blog/{p['slug']}){summ}")
    lines.append("")
    return "\n".join(lines)
