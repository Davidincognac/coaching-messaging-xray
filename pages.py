"""The pages that are not the funnel: about, blog, and the three legal ones.

These share the funnel's palette through brand.py but get their own stylesheet, because
they are for reading rather than converting: one column, generous line height, no gold
button pulling at the corner of the eye.

The blog is file-backed. Drop a .md file in posts/ and push, and it is live. There is a
small markdown reader at the bottom of this file rather than a dependency, because the
only things a post needs are headings, paragraphs, lists, links, bold and quotes.
"""

import html
import os
import re
from datetime import datetime

import brand as _brand
from audit import websites_read_count, MARKET_AVG_10

POSTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts")

_PROSE_CSS = """
  *{box-sizing:border-box}
  html{background:var(--paper)}
  body{margin:0;background:var(--paper);color:var(--ink);
    font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.68;-webkit-font-smoothing:antialiased}
  .prose{max-width:680px;margin:0 auto;padding:56px 24px 72px}
  .prose h1{font-family:var(--serif);font-weight:600;font-size:clamp(28px,5vw,42px);
    line-height:1.14;letter-spacing:-.02em;margin:0 0 28px;color:#111111}
  .prose h2{font-family:var(--serif);font-weight:600;font-size:clamp(20px,3.4vw,26px);
    line-height:1.3;margin:44px 0 14px;color:#111111}
  .prose h3{font-weight:700;font-size:17px;margin:32px 0 10px;color:#111111}
  .prose p{font-size:17px;margin:0 0 18px}
  .prose li{font-size:17px;margin-bottom:9px}
  .prose ul,.prose ol{padding-left:22px;margin:0 0 18px}
  .prose a{color:var(--accent-ink);text-decoration:underline;text-underline-offset:2px}
  .prose a:hover{color:var(--cta)}
  .prose strong{font-weight:700;color:#111111}
  .prose blockquote{margin:0 0 18px;padding:2px 0 2px 18px;border-left:3px solid var(--cta);
    color:var(--muted)}
  .prose .lede{font-size:19px;color:var(--muted);margin:0 0 30px}
  .prose .stamp{font-size:13px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--muted);font-weight:700;margin:0 0 10px}
  .prose table{border-collapse:collapse;width:100%;margin:0 0 20px;font-size:15px}
  .prose td,.prose th{border-bottom:1px solid var(--line);padding:9px 12px;text-align:left;
    vertical-align:top}
  .prose th{font-weight:700;color:#111111}
  .prose .note{background:#fff;border:1px solid var(--line);border-left:3px solid var(--accent);
    border-radius:0 8px 8px 0;padding:16px 20px;margin:0 0 22px;font-size:15.5px}
  .prose .postlist{list-style:none;padding:0}
  .prose .postlist li{border-bottom:1px solid var(--line);padding:18px 0;margin:0}
  .prose .postlist a{font-size:19px;font-weight:600;text-decoration:none;color:#111111}
  .prose .postlist a:hover{color:var(--cta)}
  .prose .postlist .when{display:block;font-size:13px;color:var(--muted);margin-top:4px}
  .backlink{display:inline-block;margin-top:40px;font-size:15px}
"""

_SHELL = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
__SEO__
<style>__CSS__</style></head><body>
__NAV__
<main class="prose">
__BODY__
</main>
__FOOTER__
</body></html>"""


def shell(body, title, desc="", active="", path="/", index=True):
    return (_SHELL
            .replace("__SEO__", _brand.head_meta(path, title, desc, index))
            .replace("__CSS__", _brand.FONT_FACES + _brand.BRAND_TOKENS
                     + _brand.CHROME_CSS + _PROSE_CSS)
            .replace("__NAV__", _brand.nav_html(active))
            .replace("__FOOTER__", _brand.footer_html())
            .replace("__TITLE__", html.escape(title))
            .replace("__DESC__", html.escape(desc))
            .replace("__BODY__", body))


# --------------------------------------------------------------------------- about

def render_about():
    # The counts come from the live corpus, not from a number typed in here, so the page
    # can never claim a figure the tool would contradict two clicks later.
    cnt = f"{websites_read_count():,}"
    body = f"""
<h1>I count things, then I build from what the counting says</h1>

<p class="lede">That is the whole job. Everything below is how I got here and what I have
counted so far.</p>

<p>Most people advising coaches start from experience. What worked for them, what they
have seen, what sounds right. That has real value and I am not going to pretend
otherwise. It is also filtered through somebody else's market and somebody else's
situation, and you are in neither of those.</p>

<p>I start somewhere else. I count what a market is already doing, and then I build to
match it.</p>

<h2>Before this</h2>

<p>I have been selling things since I was eight. Copying computer games at school and
selling them to the other kids, which I am not especially proud of, then a door to door
car wash before I was tall enough to reach the roofs.</p>

<p>In 2007 I went into the driving school market with one eBook about marketing for
driving instructors.</p>

<p>Twelve years followed. A call centre answering sales calls for my clients. A media
centre building their websites and running their local SEO. A column in the national
trade magazine. A Facebook community of 6,000 instructors. Training products, paid
speaking including a trip to Australia, workshops, international retreats, and three
national conferences with 150, 150 and 268 people in the room.</p>

<p>I sold it in 2019.</p>

<p>I never told those instructors what ought to work. I researched how their market
moved, built everything to match it, and ran that for twelve years before I sold it.</p>

<h2>Now</h2>

<p>The same thing, for coaches.</p>

<p>So far that is {cnt} coaching websites read and scored out of 10, 11,384 LinkedIn
profiles, and 2,000 books their buyers actually paid for.</p>

<p>The average website scored {MARKET_AVG_10}.</p>

<p>That number is the reason I keep doing this. A coach who knows their subject cold,
who has done the inner work, who is genuinely good in the room, still ends up with a
homepage scoring under 5 to the stranger who lands on it. Not because they are lazy.
Because they wrote it from the inside, using the words they use with other coaches, and
nobody ever showed them what their buyer types at eleven at night.</p>

<h2>Why a cartoon reads your website</h2>

<p>Angelo does the reading, and Angelo is a cartoon.</p>

<p>That is deliberate. The audit really is a machine reading your homepage the way a
stranger would, in about a minute, and I would rather it looked like a machine than
pretend to be me leaning over your shoulder. When I am the one doing the work, you will
know, because it will have my name on it and it will take longer than a minute.</p>

<p>I am in the footer. Also deliberate.</p>

<h2>Where to start</h2>

<p><a href="/">The buying triggers page</a> is the front door. It takes a couple of
minutes and it tells you what your market is already responding to. Nothing after that
happens unless you want it to.</p>

<p>If you would rather just talk, I am at
<a href="mailto:{_brand.COMPANY['email']}">{_brand.COMPANY['email']}</a>.</p>
"""
    return shell(body, "About David Poole", "Who runs Going Beyond The Illusion, and why "
                 "the research comes before the advice.", active="about", path="/about")


# --------------------------------------------------------------------------- blog

_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _read_posts():
    """Every .md file in posts/, newest first.

    Front matter is optional. Without it the filename becomes the slug and the title is
    the first heading, so a post can be published by saving a file and pushing.
    """
    if not os.path.isdir(POSTS_DIR):
        return []
    out = []
    for name in os.listdir(POSTS_DIR):
        if not name.endswith(".md"):
            continue
        path = os.path.join(POSTS_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            continue
        meta, body = {}, raw
        m = _FRONT.match(raw)
        if m:
            body = raw[m.end():]
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
        title = meta.get("title") or _first_heading(body) or name[:-3].replace("-", " ")
        out.append({
            "slug": meta.get("slug") or name[:-3],
            "title": title,
            "date": meta.get("date", ""),
            "summary": meta.get("summary", ""),
            "body": body,
        })
    out.sort(key=lambda p: (p["date"] or "0000-00-00", p["slug"]), reverse=True)
    return out


def _first_heading(body):
    for line in body.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def _pretty_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %B %Y")
    except (ValueError, TypeError):
        return iso or ""


def render_blog_index():
    posts = _read_posts()
    if not posts:
        # An honest empty state beats three invented posts. It also says when to come back.
        body = """
<h1>Blog</h1>
<p class="lede">Nothing here yet.</p>
<p>What will go here: what the research keeps turning up across coaching markets, what
the scores look like when you read enough websites, and the bits of the method I am
happy to give away.</p>
<p>Not opinion pieces. If I write something here it will have a number in it.</p>
<p>In the meantime, <a href="/">the buying triggers page</a> is the useful thing.</p>
"""
        return shell(body, "Blog", "Research notes from reading coaching websites.",
                     active="blog", path="/blog")
    items = []
    for p in posts:
        when = _pretty_date(p["date"])
        summary = f'<span class="when">{html.escape(p["summary"])}</span>' if p["summary"] else ""
        items.append(
            f'<li><a href="/blog/{html.escape(p["slug"])}">{html.escape(p["title"])}</a>'
            + (f'<span class="when">{html.escape(when)}</span>' if when else "")
            + summary + "</li>")
    body = ("<h1>Blog</h1>\n<ul class=\"postlist\">" + "".join(items) + "</ul>")
    return shell(body, "Blog", "Research notes from reading coaching websites.", active="blog", path="/blog")


def render_post(slug):
    for p in _read_posts():
        if p["slug"] == slug:
            when = _pretty_date(p["date"])
            stamp = f'<p class="stamp">{html.escape(when)}</p>' if when else ""
            body = stamp + markdown(p["body"]) + '<p><a class="backlink" href="/blog">Back to the blog</a></p>'
            return shell(body, p["title"], p["summary"], active="blog", path="/blog/" + p["slug"])
    return None


# --------------------------------------------------------------------------- legal

def render_privacy():
    c = _brand.COMPANY
    body = f"""
<h1>Privacy</h1>
<p class="lede">What this site collects, why, and who else sees it. Written to match what
the code actually does.</p>

<div class="note">We set no cookies and run no analytics or advertising tags. There is no
consent banner on this site because there is nothing to consent to.</div>

<h2>Who is responsible</h2>
<p>{c['legal']}, {c['street']}, {c['town']} {c['postcode']}, {c['country']}.
SIRET {c['siret']}. VAT {c['vat']}.
Contact <a href="mailto:{c['email']}">{c['email']}</a>.</p>

<h2>What we collect, and when</h2>
<table>
  <tr><th>Step</th><th>What we store</th></tr>
  <tr><td>Buying triggers</td><td>Your first name, last name, email address, and the
    market you typed along with the market we matched it to.</td></tr>
  <tr><td>Social review</td><td>The banner image you upload, plus the text you paste
    about yourself and your recent posts.</td></tr>
  <tr><td>Website audit</td><td>The website address you give us, the visible text of that
    page, a screenshot of it, and the scores we work out from both.</td></tr>
  <tr><td>Purchase</td><td>Stripe takes the payment and holds the card details. We never
    see or store a card number.</td></tr>
</table>

<h2>Why</h2>
<p>To produce the report you asked for, to email you the link to it, and to send you
follow-up emails about the work we sell. The lawful basis for the report is performing
what you asked for. The lawful basis for the marketing emails is your consent, given when
you entered your email address, and you can take it back at any time using the
unsubscribe link in any email.</p>

<h2>Who else sees it</h2>
<ul>
  <li><strong>Anthropic</strong> reads the text and screenshot of the website being
    audited so it can score it. Your name and email are not sent.</li>
  <li><strong>MailerLite</strong> holds your name, email and which stage you reached, and
    sends the emails.</li>
  <li><strong>Stripe</strong> handles payment.</li>
  <li><strong>Render</strong> hosts the site and therefore stores the database.</li>
  <li><strong>Google Workspace</strong> carries the mail sent to and from
    {c['email']}.</li>
</ul>
<p>Some of these are based outside the EU. They operate under the transfer safeguards
their own terms describe. We sell your data to nobody, ever.</p>

<h2>How long we keep it</h2>
<p>Your record stays while you are on the email list. Unsubscribe and we stop mailing you
immediately; ask us to delete and we remove the record. Website scores are also kept
without your name as part of the research corpus behind the market averages, and that
anonymous scoring data is not deleted, because the averages depend on it.</p>

<h2>Your rights</h2>
<p>You can ask for a copy of what we hold, ask us to correct it, ask us to delete it, ask
us to stop using it, or object. Email
<a href="mailto:{c['email']}">{c['email']}</a> and we will answer within 30 days. If you
are not happy with how we handle it you can complain to the CNIL, the French data
protection regulator, at cnil.fr.</p>

<h2>Other people's websites</h2>
<p>The audit reads a public web page the way any visitor would, and stores the score and
a screenshot. If a page belongs to you and you want it removed from our corpus, email us
the address and we will remove it.</p>

<p class="stamp">Last updated {datetime.utcnow().strftime('%d %B %Y')}</p>
"""
    return shell(body, "Privacy", "What this site collects and who else sees it.", path="/privacy")


def render_terms():
    c = _brand.COMPANY
    body = f"""
<h1>Terms</h1>
<p class="lede">The short version: the free tools are free and come with no promises
about outcomes, the paid file is a research document, and if it is not what you expected
you get your money back.</p>

<h2>Who you are dealing with</h2>
<p>{c['legal']}, {c['street']}, {c['town']} {c['postcode']}, {c['country']}.
SIRET {c['siret']}. VAT {c['vat']}. Contact
<a href="mailto:{c['email']}">{c['email']}</a>.</p>

<h2>The free tools</h2>
<p>The buying triggers page, the social review and the website audit are free. They are
produced partly by software and partly by an AI model reading a public web page, and
neither is infallible. Treat the output as a considered opinion, not a fact. Nothing in
them is a promise that your business will perform in any particular way.</p>

<h2>The Marketing Intelligence File</h2>
<p>What you buy is a research document about your market: the language your buyers use,
what they are already paying for, and what to stop saying. It is research, not copywriting
and not a done-for-you website. Price and delivery time are stated on the page where you
buy it, and nowhere else.</p>

<h2>Refunds</h2>
<p>If the file is not what you expected, email
<a href="mailto:{c['email']}">{c['email']}</a> and ask for your money back. You do not
have to argue your case.</p>
<p>Because the file is a digital product delivered to you, EU consumer law would normally
let you waive your 14 day right of withdrawal at the point of purchase. We would rather
not rely on that, so the refund above stands regardless.</p>

<h2>What you may do with it</h2>
<p>The file is for you and your business. Use everything in it in your own marketing.
Do not resell it, publish it, or pass it to another coach as their own research.</p>

<h2>Limits</h2>
<p>We are not liable for business losses, lost profit, or decisions you take on the back
of the research. Nothing here limits liability that cannot lawfully be limited.</p>

<h2>Law</h2>
<p>French law applies, and the French courts have jurisdiction. If you are a consumer,
this does not remove the protections of your own country's law.</p>

<p class="stamp">Last updated {datetime.utcnow().strftime('%d %B %Y')}</p>
"""
    return shell(body, "Terms", "The terms covering the free tools and the paid file.", path="/terms")


def render_cookies():
    c = _brand.COMPANY
    body = f"""
<h1>Cookies</h1>
<p class="lede">This site sets none.</p>

<p>No analytics, no advertising tags, no session cookies, nothing dropped in your browser
by us. That is why there is no consent banner: there is nothing to ask you about.</p>

<p>Two things worth knowing anyway.</p>

<p>Our host puts a security check in front of the site, and the network in front of that
may set a short-lived technical cookie to tell a browser apart from a bot. It carries no
advertising data and we cannot read anything from it.</p>

<p>When you buy, the payment page is Stripe's, and Stripe sets what it needs to take a
payment safely. Their policy covers that page, not this one.</p>

<p>If we ever add a tracking tag, this page changes first and a banner appears with it.
Question about any of it, email <a href="mailto:{c['email']}">{c['email']}</a>.</p>

<p class="stamp">Last updated {datetime.utcnow().strftime('%d %B %Y')}</p>
"""
    return shell(body, "Cookies", "This site sets no cookies.", path="/cookies")


# ------------------------------------------------------------------- tiny markdown

_INLINE = (
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>'),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])"), r"<em>\1</em>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
)


def _inline(text):
    out = html.escape(text)
    for rx, rep in _INLINE:
        out = rx.sub(rep, out)
    return out


def markdown(src):
    """Enough markdown for a blog post and no more.

    Headings, paragraphs, bullet and numbered lists, blockquotes, horizontal rules, and
    the four inline forms above. Everything is escaped before any tag is inserted, so a
    post file cannot inject HTML even though only we can write one.
    """
    out, lst, quote = [], None, False

    def close():
        nonlocal lst, quote
        if lst:
            out.append(f"</{lst}>")
            lst = None
        if quote:
            out.append("</blockquote>")
            quote = False

    for line in src.splitlines():
        s = line.strip()
        if not s:
            close()
            continue
        if s.startswith("#"):
            close()
            level = min(len(s) - len(s.lstrip("#")), 3)
            out.append(f"<h{level}>{_inline(s.lstrip('#').strip())}</h{level}>")
        elif s in ("---", "***", "___"):
            close()
            out.append("<hr>")
        elif s.startswith(("- ", "* ")):
            if lst != "ul":
                close()
                out.append("<ul>")
                lst = "ul"
            out.append(f"<li>{_inline(s[2:])}</li>")
        elif re.match(r"^\d+\.\s", s):
            if lst != "ol":
                close()
                out.append("<ol>")
                lst = "ol"
            out.append(f"<li>{_inline(re.sub(r'^\d+\.\s', '', s))}</li>")
        elif s.startswith("> "):
            if not quote:
                close()
                out.append("<blockquote>")
                quote = True
            out.append(f"<p>{_inline(s[2:])}</p>")
        else:
            close()
            out.append(f"<p>{_inline(s)}</p>")
    close()
    return "\n".join(out)
