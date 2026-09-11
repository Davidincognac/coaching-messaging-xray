"""The form that asks a coach for their own material.

Step two of the funnel. By the time anyone sees this we already know their name, their email and
their market, so this asks for none of it. The token in the link is the identity.

Four fields and not one of them is required on its own. A coach with no website, no recent post or
no banner still gets a report, because the report was built to survive every combination. The only
rule is that they give us something.

Nothing here promises what we do not yet do. There is no line about deleting the screenshot after
thirty days, because that job is not built. The day it is, the line goes in.
"""
import html


def _val(values, key):
    return html.escape((values or {}).get(key, ""), quote=True)


def render_form(first_name="", audience="", token="", error="", values=None):
    """The form, as a fragment for the standard page shell."""
    e = html.escape
    fn = e(first_name.strip().split(" ")[0]) if first_name.strip() else ""
    hello = f"{fn}, now " if fn else "Now "
    who = e(audience) if audience else "your buyers"
    lede = (f"You've read what {who} buy on. This next part shows you what they get from you."
            if audience else
            "This next part shows you what a stranger sees when they find you.")
    err = f'<div class="formerr">{e(error)}</div>' if error else ""

    return f'''<div class="card">
  <h2 class="sec-h">{hello}let's look at you</h2>
  <p class="sec-lede">{lede}</p>
</div>
<form method="post" action="/social" enctype="multipart/form-data">
  {err}
  <input type="hidden" name="token" value="{e(token, quote=True)}">
  <div class="fieldset">
    <label for="banner">Your banner</label>
    <p class="sub">The picture across the top of your profile. Take a screenshot of it and pick the
    file here.</p>
    <input type="file" id="banner" name="banner" accept="image/*">
  </div>
  <div class="fieldset">
    <label for="bio">Your bio</label>
    <p class="sub">The words underneath your name. Copy them and paste them in.</p>
    <textarea id="bio" name="bio" rows="3"
      placeholder="Paste your bio here">{_val(values, "bio")}</textarea>
  </div>
  <div class="fieldset">
    <label for="post">Your last post</label>
    <p class="sub">The one you put up most recently. Not your best one. Your last one.</p>
    <textarea id="post" name="post" rows="4"
      placeholder="Paste your last post here">{_val(values, "post")}</textarea>
  </div>
  <div class="fieldset">
    <label for="website">Your website</label>
    <p class="sub">Only if you've got one. Leave it empty if you haven't, and you'll still get
    everything else.</p>
    <input type="text" id="website" name="website" placeholder="yourwebsite.com"
      inputmode="url" autocapitalize="off" autocorrect="off" spellcheck="false"
      value="{_val(values, "website")}">
  </div>
  <button type="submit">Show me what they see</button>
  <p class="hint">You don't have to fill in all four. We'll read whatever you give us.</p>
</form>'''


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
        known = (f'<p class="sub">You gave us <b>{e(website)}</b>, so we already know where to '
                 'look.</p>')
    else:
        known = '<p class="sub">You tell us the address on the next page.</p>'
    return f'''<div class="card">
  <h2 class="sec-h">So what next</h2>
  <p>That was someone who already knew a little about you. They'd seen something of yours and
  clicked your name.</p>
  <p>Your website gets a colder version of that person. They arrive from a search or a link, they
  know nothing about you, and nothing has made them interested yet. Everything your profile got for
  free, your website has to earn.</p>
</div>
<div class="card">
  <h3 class="scores-h">Have your website read</h3>
  <p class="sub">{reading}</p>
  {known}
  <p class="btnwrap"><a class="btn" href="/{q}">Read my website</a></p>
</div>
<div class="card">
  <h3 class="scores-h">No website?</h3>
  <p class="sub">Plenty of coaches haven't got one, and it isn't a problem. You can carry on from
  here.</p>
  <p class="btnwrap"><a class="btn" href="/salespage{q}">Carry on without one</a></p>
</div>'''
