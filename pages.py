"""The pages that are not the funnel: about, blog, and the three legal ones.

These share the funnel's palette through brand.py but get their own stylesheet, because
they are for reading rather than converting: one column, generous line height, no gold
button pulling at the corner of the eye.

The blog is file-backed. Drop a .md file in posts/ and push, and it is live. There is a
small markdown reader at the bottom of this file rather than a dependency, because the
only things a post needs are headings, paragraphs, lists, links, bold and quotes.

Pictures go in posts/images/ and are written `![alt text](filename.png)`. The alt text is
part of the syntax rather than an option, so a picture cannot go out without one. A line
that is only a picture becomes a figure at full prose width; one inside a sentence stays
inside the sentence. Width and height are read off the file and put on the tag, so the
words below a picture do not jump when it loads. `image:` in a post's front matter names
the picture it shares itself with, and without one it shares Angelo.
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
  .gb-hero{padding:72px 24px 78px}
  .gb-herowrap{max-width:1060px;margin:0 auto}
  .gb-hero .gb-lede{margin-bottom:0}
  @media(max-width:720px){.gb-hero{padding:48px 20px 54px}}
  .prose{max-width:680px;margin:0 auto;padding:56px 24px 78px}
  .prose > h2:first-child{margin-top:0}
  .prose h1{font-family:var(--display);font-weight:700;font-size:clamp(32px,5vw,46px);
    line-height:1.06;letter-spacing:-.035em;margin:0 0 28px;color:#111111}
  .prose h2{font-family:var(--display);font-weight:700;font-size:clamp(24px,3.4vw,32px);
    line-height:1.12;letter-spacing:-.028em;margin:52px 0 16px;color:#111111}
  /* the short gradient rule sits above every h2, the way the reference site marks a turn */
  .prose h2::before{content:"";display:block;width:48px;height:4px;border-radius:2px;
    background:var(--grad);margin:0 0 18px}
  .prose h3{font-family:var(--display);font-weight:700;font-size:19px;letter-spacing:-.02em;
    margin:34px 0 10px;color:#111111}
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
  .prose .postlist{list-style:none;padding:0;margin:0}
  .prose .postlist li{border-bottom:1px solid var(--line);padding:26px 0;margin:0}
  .prose .postlist li:first-child{padding-top:0}
  .prose .postlist a{font-family:var(--display);font-size:25px;font-weight:700;
    letter-spacing:-.025em;line-height:1.2;text-decoration:none;color:#111111;display:block}
  .prose .postlist a:hover{color:var(--cta)}
  .prose .postlist .when{display:block;font-size:12.5px;font-weight:700;letter-spacing:.12em;
    text-transform:uppercase;color:var(--cta);margin-top:10px}
  .prose .postlist .sum{margin:8px 0 0;color:var(--muted);font-size:16px}
  /* byline sits inside the dark hero, under the heading */
  .gb-byline{display:flex;align-items:center;gap:11px;margin-top:26px;
    font-size:15px;color:var(--ivory-dim)}
  .gb-byline img{width:40px;height:40px;border-radius:50%;object-fit:cover;
    border:2px solid var(--cta)}
  .gb-byline b{color:var(--ivory);font-weight:600}
  .backlink{display:inline-block;margin-top:40px;font-size:15px}
  /* ---------- blog furniture ---------- */
  .gb-crumbs{font-size:13.5px;color:var(--ivory-dim);margin:0 0 22px}
  .gb-crumbs a{color:var(--ivory-dim);text-decoration:none}
  .gb-crumbs a:hover{color:var(--cta-soft)}
  .gb-crumbs .sep{margin:0 9px;opacity:.45}
  .gb-crumbs [aria-current]{color:var(--ivory)}

  .prose .gb-faq{border-top:1px solid var(--line);padding:20px 0 0;margin:0 0 20px}
  .prose .gb-faq h3{margin:0 0 8px}
  .prose .gb-faq p{margin:0;color:var(--muted)}

  /* The point of the whole post. Dark, so it stops the page rather than blending in. */
  .gb-cta{background:var(--navy);border-radius:18px;padding:36px 34px;margin:52px 0 0;
    position:relative;overflow:hidden}
  .gb-cta::before{content:"";position:absolute;inset:0;background:var(--halo);pointer-events:none}
  .gb-cta > *{position:relative}
  .gb-cta h2{font-size:clamp(23px,3vw,30px);color:#fff;margin:0 0 12px}
  .gb-cta h2::before{display:none}
  .gb-cta p{color:var(--ivory-dim);font-size:16.5px;margin:0 0 22px;max-width:48ch}
  /* the prose column underlines every link; a button is not a link in that sense */
  .gb-cta .gb-btn{text-decoration:none;color:var(--cta-ink)}
  .gb-cta .gb-btn:hover{color:var(--cta-ink)}
  @media(max-width:560px){.gb-cta{padding:28px 22px}}

  /* A picture runs the full prose width and keeps its own shape. The aspect-ratio comes
     from the width and height on the tag, so nothing moves once the file arrives. */
  .prose figure{margin:30px 0}
  .prose figure img{display:block;width:100%;height:auto;border-radius:10px;
    border:1px solid var(--line)}
  .prose figure figcaption{margin-top:10px;font-size:15px;color:#5a5a5a}
  .prose p img{max-width:100%;height:auto}

  .prose .gb-know{background:#f6f6f4;border-left:3px solid var(--cta);
    border-radius:0 10px 10px 0;padding:22px 26px;margin:0 0 34px}
  .prose .gb-know ul{margin:10px 0 0;padding-left:20px}
  .prose .gb-know li{margin:0 0 8px;font-size:17px}
  .prose .gb-know li:last-child{margin-bottom:0}

  .prose .gb-related{list-style:none;padding:0;margin:0}
  .prose .gb-related li{border-bottom:1px solid var(--line);padding:14px 0;margin:0}
  .prose .gb-related a{font-family:var(--display);font-weight:700;font-size:18px;
    letter-spacing:-.02em;text-decoration:none;color:#111111}
  .prose .gb-related a:hover{color:var(--cta)}

"""

_SHELL = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
__SEO__
__EXTRA__
<style>__CSS__</style></head><body>
__NAV__
__HERO__
<main class="prose">
__BODY__
</main>
__FOOTER__
</body></html>"""


def hero(eyebrow, heading_html, lede="", buttons="", portrait=""):
    """The dark band every page opens on. `heading_html` is passed through unescaped so a
    single phrase can carry the gradient; everything in it is ours, never a coach's."""
    brow = f'<p class="gb-eyebrow">{html.escape(eyebrow)}</p>' if eyebrow else ""
    led = f'<p class="gb-lede">{lede}</p>' if lede else ""
    copy = f'<div class="gb-copy">{brow}<h1 class="gb-display">{heading_html}</h1>{led}{buttons}</div>'
    inner = f'<div class="gb-split">{copy}{portrait}</div>' if portrait else copy
    return f'<section class="gb-dark gb-hero"><div class="gb-herowrap">{inner}</div></section>'


def shell(body, title, desc="", active="", path="/", index=True, hero_html="", extra_head="",
          image=""):
    return (_SHELL
            .replace("__HERO__", hero_html)
            .replace("__EXTRA__", extra_head)
            .replace("__SEO__", _brand.head_meta(path, title, desc, index, share_image(image)))
            .replace("__CSS__", _brand.FONT_FACES + _brand.BRAND_TOKENS
                     + _brand.CHROME_CSS + _PROSE_CSS)
            .replace("__NAV__", _brand.nav_html(active))
            .replace("__FOOTER__", _brand.footer_html())
            .replace("__BODY__", body))


# --------------------------------------------------------------------------- about

def render_about():
    # The counts come from the live corpus, not from a number typed in here, so the page
    # can never claim a figure the tool would contradict two clicks later.
    cnt = f"{websites_read_count():,}"

    hero_html = hero(
        eyebrow="About",
        heading_html='I <span class="gb-grad">count things</span>, then I build from what the counting says',
        lede="That is the whole job. Everything below is how I got here and what I have "
             "counted so far.",
        buttons='<div class="gb-btnrow">'
                '<a class="gb-btn primary" href="/">See your buying triggers</a>'
                f'<a class="gb-btn ghost" href="mailto:{_brand.COMPANY["email"]}">Email me</a>'
                '</div>',
        portrait='<div class="gb-portrait">'
                 '<img src="/david.jpg" alt="David Poole">'
                 '<div class="gb-namecard">David Poole<span>Going Beyond The Illusion</span></div>'
                 '</div>',
    )

    body = f"""
<div class="gb-callout">
  <p class="gb-eyebrow">The short answer</p>
  <p>Most people advising coaches start from experience. I start from a count. I read
     {cnt} coaching websites and scored every one of them, and I build from what that
     says rather than from what sounds right.</p>
</div>

<p>Experience has real value and I am not going to pretend otherwise. It is also filtered
through somebody else's market and somebody else's situation, and you are in neither of
those.</p>

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

<h2>What the counting says</h2>

<p>So far: <a href="/website">{cnt} coaching websites read and scored out of 10</a>,
11,384 LinkedIn profiles, and 2,000 books their buyers actually paid for.</p>

<p><a href="/blog/2026-09-28-average-coaching-website">The average website scored
{MARKET_AVG_10}</a>.</p>

<p>That number is the reason I keep doing this. A coach who knows their subject cold, who
has done the inner work, who is genuinely good in the room, still ends up with a homepage
scoring under 5 to the stranger who lands on it. Not because they are lazy. Because they
wrote it from the inside, using the words they use with other coaches, and nobody ever
showed them what their buyer types at eleven at night.</p>

<h2>Why a cartoon reads your website</h2>

<p>Angelo does the reading, and Angelo is a cartoon.</p>

<p>That is deliberate. The audit really is a machine reading your homepage the way a
stranger would, in about a minute, and I would rather it looked like a machine than
pretend to be me leaning over your shoulder. When I am the one doing the work, you will
know, because it will have my name on it and it will take longer than a minute.</p>

<h2>Where to start</h2>

<p><a href="/">The buying triggers page</a> is the front door. It takes a couple of
minutes and it tells you what your market is already responding to. Nothing after that
happens unless you want it to.</p>

<p>If you would rather just talk, I am at
<a href="mailto:{_brand.COMPANY['email']}">{_brand.COMPANY['email']}</a>.</p>
"""
    return shell(body, "About David Poole", "Who runs Going Beyond The Illusion, and why "
                 "the research comes before the advice.", active="about", path="/about",
                 hero_html=hero_html, extra_head=_brand.person_schema("/about"))


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
            # `image:` in front matter is the picture the post shares itself with. A bare
            # filename means posts/images/, anything with a slash is taken as written.
            "image": meta.get("image", ""),
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


_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)\s]+\)")


def plain(text):
    """A FAQ answer with its markdown taken back off.

    The page renders an answer as markdown, because an answer that cannot link is an
    answer that has to repeat itself. Schema wants the sentence a person would read out,
    so the link keeps its words and loses its brackets.
    """
    text = _MD_LINK.sub(r"\1", text)
    return re.sub(r"[*`]", "", text)


WORDS_PER_MINUTE = 300


def reading_time(text):
    """Minutes, counting only what somebody actually reads.

    Two things were wrong with the obvious version. It counted a bulleted list at the same
    rate as prose, and a list of 117 niches is scanned rather than read, which turned a post
    that feels like three minutes into a promise of nine. And 220 words a minute is a book
    on a sofa. Somebody skimming a page on a phone goes a good deal faster.

    So list lines are left out of the count and the rate is 300. Rounded to nearest rather
    than up, because a number that consistently overshoots is the same lie in the other
    direction.
    """
    lines = (text or "").splitlines()
    prose = " ".join(l for l in lines if not l.strip().startswith(("- ", "* ", "#", "|")))
    words = len(re.sub(r"[*`>\[\]()]", " ", prose).split())
    return max(1, round(words / WORDS_PER_MINUTE))


def split_takeaways(body):
    """Lift a `## Things to know` list out of a post.

    Same convention as the FAQ: write an ordinary markdown list under the heading and it
    becomes the box at the top, rather than being kept in a second place that drifts out of
    step with the post. The heading counts its own bullets, so nothing claims four points
    and then shows three.

    Returns (body_without_the_section, [point, ...]).
    """
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+(Things to know|Key points|What to know)\s*$", line.strip(), re.I):
            start = i
            break
    if start is None:
        return body, []
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    points = [l.strip()[2:].strip() for l in lines[start + 1:end]
              if l.strip().startswith(("- ", "* "))]
    return "\n".join(lines[:start] + lines[end:]), points


def split_faq(body):
    """Separate a post's `## FAQ` section from the rest.

    The convention is one rule: everything under a `## FAQ` heading, as `### question`
    followed by its answer, until the next `##`. Write ordinary markdown and the schema
    comes out of it, so there is no second place to keep the questions in step.

    Returns (body_without_faq, [(question, answer_text), ...]).
    """
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+(FAQ|FAQs|Questions)\s*$", line.strip(), re.I):
            start = i
            break
    if start is None:
        return body, []
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    faqs, q, buf = [], None, []
    for line in lines[start + 1:end]:
        if line.startswith("### "):
            if q:
                faqs.append((q, " ".join(buf).strip()))
            q, buf = line[4:].strip(), []
        elif q and line.strip():
            buf.append(line.strip())
    if q:
        faqs.append((q, " ".join(buf).strip()))
    rest = "\n".join(lines[:start] + lines[end:])
    return rest, [(a, b) for a, b in faqs if a and b]


def related(posts, slug, limit=3):
    return [p for p in posts if p["slug"] != slug][:limit]


def render_blog_index():
    posts = _read_posts()
    hero_html = hero(
        eyebrow="Blog",
        heading_html='What the <span class="gb-grad">numbers</span> keep saying about coaching websites',
        lede="Not opinion pieces. If something goes up here it has a number in it and I "
             "will tell you where the number came from.",
    )
    if not posts:
        # An honest empty state beats three invented posts. It also says when to come back.
        body = """
<div class="gb-callout">
  <p class="gb-eyebrow">Nothing here yet</p>
  <p>I am writing the first ones. They will cover what the research keeps turning up
     across coaching markets, what the scores look like once you have read enough
     websites, and the parts of the method I am happy to give away.</p>
</div>
<h2>In the meantime</h2>
<p>The useful thing is <a href="/">the buying triggers page</a>. It takes a couple of
minutes and it tells you what your market is already responding to.</p>
"""
        return shell(body, "Blog", "Research notes from reading coaching websites.",
                     active="blog", path="/blog", hero_html=hero_html)

    items = []
    for p_ in posts:
        when = _pretty_date(p_["date"])
        meta = " · ".join(x for x in [html.escape(when)] if x)
        summ = f'<p class="sum">{html.escape(p_["summary"])}</p>' if p_["summary"] else ""
        items.append(
            f'<li><a href="/blog/{html.escape(p_["slug"])}">{html.escape(p_["title"])}</a>'
            + (f'<span class="when">{meta}</span>' if meta else "")
            + summ + "</li>")
    body = '<ul class="postlist">' + "".join(items) + "</ul>"
    return shell(body, "Blog", "Research notes from reading coaching websites.",
                 active="blog", path="/blog", hero_html=hero_html)


def render_post(slug):
    posts = _read_posts()
    for p_ in posts:
        if p_["slug"] != slug:
            continue
        path = "/blog/" + p_["slug"]
        when = _pretty_date(p_["date"])
        trail = [("Home", "/"), ("Blog", "/blog"), (p_["title"], path)]

        byline = (
            '<div class="gb-byline">'
            + ('<img src="/david.jpg" alt="">' if os.path.exists(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "david.jpg")) else "")
            + "<span>By <b>David Poole</b>"
            + (f" · {html.escape(when)}" if when else "")
            + f" · {reading_time(p_['body'])} minute read"
            + "</span></div>")

        hero_html = hero(
            eyebrow="Blog",
            heading_html=html.escape(p_["title"]),
        ).replace('<div class="gb-herowrap">',
                  '<div class="gb-herowrap">' + _brand.breadcrumbs(trail)
                  ).replace("</div></section>", byline + "</div></section>")

        rest, faqs = split_faq(p_["body"])
        rest, points = split_takeaways(rest)

        # The summary doubles as the answer-first paragraph. A model lifting one passage
        # from this page should be able to lift this one and be right.
        short = (f'<div class="gb-callout"><p class="gb-eyebrow">In short</p>'
                 f'<p>{html.escape(p_["summary"])}</p></div>') if p_["summary"] else ""

        # The box counts its own bullets, so the heading can never promise four and show three.
        know_html = ""
        if points:
            items = "".join(f"<li>{_inline(pt)}</li>" for pt in points)
            know_html = (f'<div class="gb-know"><p class="gb-eyebrow">'
                         f'{len(points)} things to know from this article</p>'
                         f'<ul>{items}</ul></div>')

        faq_html = ""
        if faqs:
            items = "".join(
                f'<div class="gb-faq"><h3>{html.escape(q)}</h3><p>{_inline(a)}</p></div>'
                for q, a in faqs)
            faq_html = f'<h2>Questions coaches ask about this</h2>{items}'

        rel = related(posts, slug)
        rel_html = ""
        if rel:
            links = "".join(
                f'<li><a href="/blog/{html.escape(r["slug"])}">{html.escape(r["title"])}</a></li>'
                for r in rel)
            rel_html = f'<h2>Read next</h2><ul class="gb-related">{links}</ul>'

        # Two callouts stacked is clutter, and "the short answer" answers a question the page
        # never asked. When a post carries its own points, they replace the summary box.
        body = ((know_html or short) + markdown(rest) + faq_html
                + _brand.cta_block() + rel_html)

        extra = _brand.article_schema(p_["title"], p_["summary"], path, p_["date"],
                                      [(q, plain(a)) for q, a in faqs], trail)
        return shell(body, p_["title"], p_["summary"], active="blog", path=path,
                     hero_html=hero_html, extra_head=extra, image=p_.get("image", ""))
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

IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts", "images")
IMAGE_URL = "/blog/images/"
_IMG_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}
_SIZES = {}


def image_size(name):
    """Intrinsic pixel size of a post image, read once and remembered.

    The numbers go on the tag as width and height. Without them the browser does not know
    how tall the picture will be until it arrives, so the text under it jumps when it does,
    and that jump is the thing Core Web Vitals measures and marks us down for.
    """
    if name in _SIZES:
        return _SIZES[name]
    size = None
    try:
        from PIL import Image
        with Image.open(os.path.join(IMAGE_DIR, name)) as im:
            size = im.size
    except Exception:
        # An unreadable or vector image simply goes out without dimensions rather than
        # taking the post down with it.
        size = None
    _SIZES[name] = size
    return size


def share_image(name):
    """Turn a front-matter `image:` into a path the share tags can use.

    A bare filename is one of ours in posts/images. Anything with a slash is taken as
    written, so a post can point at /angelo.png or at a full address. Empty stays empty
    and head_meta falls back to Angelo.
    """
    if not name:
        return ""
    if name.startswith(("http://", "https://", "/")):
        return name
    return IMAGE_URL + name


def _image_tag(alt, src):
    """A picture in a post. Alt text is required by the syntax, so it cannot be forgotten."""
    local = "/" not in src and "\\" not in src
    url = (IMAGE_URL + src) if local else src
    dims = ""
    if local:
        wh = image_size(src)
        if wh:
            dims = f' width="{wh[0]}" height="{wh[1]}"'
    # Lazy, because a picture below the fold should not hold up the words above it.
    return (f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(alt, quote=True)}"'
            f'{dims} loading="lazy" decoding="async">')


_INLINE = (
    (re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)"), lambda m: _image_tag(m.group(1), m.group(2))),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>'),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])"), r"<em>\1</em>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
)


def _inline(text):
    # Escaped first, always: a post file is ours, but the rule that nothing reaches the page
    # as markup unless a rule below puts it there is what makes that safe to keep saying.
    out = html.escape(text)
    for rx, rep in _INLINE:
        out = rx.sub(rep, out)
    return out


_ONLY_IMAGE = re.compile(r"^!\[[^\]]*\]\([^)\s]+\)$")


# A pipe table. Four posts shipped with one before anything here could read it, so the rows
# came out on the page as literal pipes and dashes. The rule row is what makes the row above
# it headings, and it is the only form a post uses.
_ROW = re.compile(r"^\|.*\|$")
_RULE = re.compile(r"^\|[\s:|-]+\|$")


def _cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def table_html(rows):
    """Rows of a pipe table, in the order they were written.

    Cells go through the inline reader, so a figure in a table can still carry a link, and a
    ragged row is shown as written rather than padded to match the heading. Padding it would
    hide a typo in a post instead of showing it.
    """
    head, body = [], rows
    if len(rows) > 1 and _RULE.match(rows[1]):
        head, body = _cells(rows[0]), rows[2:]
    out = ["<table>"]
    if head:
        out.append("<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>")
    for r in body:
        if _RULE.match(r):
            continue
        out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in _cells(r)) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def markdown(src):
    """Enough markdown for a blog post and no more.

    Headings, paragraphs, bullet and numbered lists, blockquotes, horizontal rules, pipe
    tables, pictures, and the inline forms above. Everything is escaped before any tag is
    inserted, so a post file cannot inject HTML even though only we can write one.

    A line that is nothing but a picture becomes a <figure> rather than a paragraph with
    an image in it, because the prose column is measured for text and a picture in it
    comes out the width of a sentence.
    """
    out, lst, quote, table = [], None, False, None

    def close():
        nonlocal lst, quote, table
        if lst:
            out.append(f"</{lst}>")
            lst = None
        if quote:
            out.append("</blockquote>")
            quote = False
        if table is not None:
            out.append(table_html(table))
            table = None

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
        elif _ONLY_IMAGE.match(s):
            close()
            out.append(f"<figure>{_inline(s)}</figure>")
        elif _ROW.match(s):
            if table is None:
                close()
                table = []
            table.append(s)
        else:
            close()
            out.append(f"<p>{_inline(s)}</p>")
    close()
    return "\n".join(out)
