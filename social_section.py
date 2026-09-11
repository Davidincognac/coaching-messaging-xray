"""The social media section, built to sit INSIDE the website report.

It uses the audit's own classes — .ev, .ev-head, .secnum, .q, .meta, .fault — so it inherits the
report's design instead of bringing its own. Nothing new is styled, nothing is scored, and no
analysis runs: their banner, their bio, the opening of their post, and the questions a stranger asks.

David's rule for this half: show them their own material and ask. Never hand them an answer they
could paste.
"""
import html


def first_line(text, limit=145):
    """The opening of their last post. Two words or two hundred, the first line is what decides."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for mark in (". ", "! ", "? "):
        i = cut.rfind(mark)
        if i > 60:
            return text[:i + 1]
    return text[:cut.rfind(" ")]


QUESTIONS = [
    ("Is this person for me?", "Do they work with people like me, with my problem."),
    ("Are they any good?", "Any sign they know what they're talking about."),
    ("Is there more of what I just liked?",
     "Was that post a one-off, or is this consistently for me."),
    ("What do I do if I want more?", "Is there a next step, or is this a dead end."),
]


def render(banner_url="", bio="", post="", section_label="Section 5 of 5"):
    """Returns a fragment for the audit report. Empty string when they gave us no social."""
    if not (bio or post or banner_url):
        return ""
    e = html.escape
    # We do not ask which platform it is. It buys nothing on the form and nothing in the copy.

    seen = ""
    if banner_url:
        seen += (f'<img class="thumb" src="{e(banner_url, quote=True)}" alt="Your banner">'
                 f'<div class="meta">Your banner, as you uploaded it.</div>')
    if bio:
        seen += ('<div class="meta">This is your bio. It is the one place you get to say who you '
                 'help and what you fix.</div>'
                 f'<div class="q">{e(bio)}</div>')
    if post:
        opening = first_line(post)
        # Only claim we trimmed it when we actually did. Christie's post is nine words; telling her
        # we were "only showing the first few" of nine words is a lie she can see.
        trimmed = len(opening) < len(" ".join(post.split()))
        lead = ("And this is how your last post opens. We are only showing the first few words on "
                "purpose." if trimmed else "And this is your last post, all of it.")
        seen += (f'<div class="meta" style="margin-top:14px">{lead}</div>'
                 f'<div class="q sm">{e(opening)}</div>'
                 '<div class="meta">Whether a post is two words or two hundred, people read the '
                 'first line and decide whether to carry on. And that decision isn\'t about '
                 'reading the rest of your post, or your next one. It is whether to stay on your '
                 'profile or leave.</div>')

    asks = "".join(f'<p><b>{e(q)}</b> {e(a)}</p>' for q, a in QUESTIONS)

    # Only name what is actually on the page above. Telling a coach to re-read a banner they never
    # gave us is the same fault as claiming we trimmed a post that was never trimmed.
    shown_things = [n for n, ok in (("banner", banner_url), ("bio", bio), ("post", post)) if ok]
    if len(shown_things) > 1:
        what = ", your ".join(shown_things[:-1]) + " and your " + shown_things[-1]
    else:
        what = shown_things[0]
    reread = f"Read your {what} again, as a stranger who has just clicked your name."

    return (
        f'<div class="ev"><div class="ev-head"><div class="h">'
        f'<span class="secnum">{e(section_label)}</span>Now your social media profile</div>'
        f'<img class="sec-angelo" src="/angelo_reading.png" alt="Angelo reading your profile"></div>'
        f'{seen}'
        f'<div class="meta" style="margin-top:16px">Nobody arrives at your profile by accident. '
        f'Maybe they saw a post in a group, or on their newsfeed, or you came up as someone they '
        f'might want to follow. Either way, they clicked your name to check you out, because they '
        f'thought you might be worth a look. So they turn up already half interested.</div>'
        f'<div class="meta">The job now is to turn that interest into commitment. Following you, '
        f'sending a connection request, or messaging you.</div>'
        f'<div class="fault">{reread} They are asking four things, in this order.{asks}</div>'
        f'</div>')
