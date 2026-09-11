"""The pieces that wrap around the two halves of the combined report.

The opening, their six triggers, the bridge between the halves, and the ending. All built from the
audit's own classes, so the whole report is one design rather than two stitched together.

Everything adapts to what the coach actually gave us. A coach who pastes only a bio never sees a
bridge to a website section that is not there, and the ending never mentions a half that was never
written. This is the fault that produced "Section 5 of 5" on a one-section report.
"""
import html


def opening(first_name, audience, has_social, has_website):
    """Greeting plus what we looked at. Never promises a half that is not below it."""
    e = html.escape
    fn = e(first_name.strip().split(" ")[0]) if first_name.strip() else ""
    hello = f"{fn}, " if fn else ""
    if has_social and has_website:
        looked = "We've looked at your social media profile and your website."
    elif has_social:
        looked = "We've looked at your social media profile."
    else:
        looked = "We've looked at your website."
    return (
        '<div class="card">'
        f'<h2 class="sec-h">{hello}here\'s what a stranger sees when they find you</h2>'
        f'<p class="sec-lede">{looked} You\'ve already read what {e(audience)} buy on. '
        'This is what they get from you.</p>'
        '</div>')


def trigger_reminder(audience, triggers):
    """Their six, up top, because they are the lens for everything underneath."""
    e = html.escape
    rows = "".join(
        f'<div class="q sm" style="margin:0 0 10px">{e(name)}'
        f'<span class="meta" style="display:block;margin:2px 0 0">{e(cat)}</span></div>'
        for cat, name in triggers)
    return (
        '<div class="card">'
        '<h3 class="scores-h">A reminder of your six buying triggers</h3>'
        f'<p class="meta">This is what {e(audience)} buy on. Keep it in your head while you read '
        'the rest.</p>'
        f'{rows}'
        '</div>')


def bridge():
    """Only shown when BOTH halves are present. Its whole job is the handover.

    The two readers are genuinely different, and that is worth saying: the profile visitor arrived
    already half interested, the website visitor arrives cold. Same coach, harder audience.
    """
    return (
        '<div class="card">'
        '<h3 class="scores-h">Now the harder reader</h3>'
        '<p>That was someone who already knew a little about you. They had seen something of yours '
        'and clicked your name.</p>'
        '<p>Your website gets a colder version of that person. They arrive from a search or a link, '
        'they know nothing about you, and nothing has made them interested yet. Everything your '
        'profile got for free, your website has to earn.</p>'
        '</div>')


def ending(audience, has_social, has_website):
    """Closes across whatever was actually covered, and hands over to the ask."""
    e = html.escape
    if has_social and has_website:
        what = "your profile and your website"
    elif has_social:
        what = "your profile"
    else:
        what = "your website"
    return (
        '<div class="card">'
        '<h2 class="sec-h">So where does that leave you</h2>'
        f'<p>You\'ve read what {e(audience)} buy on. And you\'ve read {what} the way a stranger '
        'reads it, which is the one thing you can never do on your own, because you know your work '
        'too well.</p>'
        '<p>Where those two don\'t meet is where your next client goes somewhere else instead.</p>'
        '</div>')
