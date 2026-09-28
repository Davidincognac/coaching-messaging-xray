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

import os

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
"""

# --------------------------------------------------------------------------- palette

BRAND_TOKENS = """
  :root{
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
"""


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
