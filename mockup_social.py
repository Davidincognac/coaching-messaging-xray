"""A drawn mockup of the social half of the combined report.

Nothing here is real. The coach, the bio, the banner and the numbers are invented so David can look
at the SHAPE before we build any of the plumbing behind it. Served at /mockup/social.

Delete this file once the real thing exists.
"""
import triggers as _t

# An invented menopause coach whose profile has the faults most coaching profiles have.
FAKE = {
    "name": "Sarah",
    "platform": "LinkedIn",
    "handle": "sarah-whitfield-coaching",
    "bio": ("Certified Menopause Coach | NBHWC Board Certified | Speaker | Author | "
            "Helping women thrive in midlife and beyond. DM for details."),
    "post": ("Excited to share that I'll be speaking at the Midlife Wellness Summit next month! "
             "It's been an incredible journey since I qualified in 2019 and I'm so grateful to "
             "everyone who has supported me. Link in comments to register."),
    "audience": "women in menopause",
}

_CSS = """
  .mock-note{background:#3a2a10;border:1px solid var(--gold);border-radius:8px;padding:12px 16px;
    font-size:13px;color:var(--ivory);margin:0 0 30px;line-height:1.6}
  .banner{border:1px solid var(--navy-line);border-radius:10px;overflow:hidden;margin:0 0 8px}
  .banner .strip{height:140px;background:linear-gradient(120deg,#2b3a55,#4a5f7d);
    display:flex;align-items:center;justify-content:center;color:#cdd6e4;
    font-family:var(--serif);font-size:19px;font-style:italic;text-align:center;padding:0 30px}
  .banner .cap{font-size:12px;color:var(--ivory-dim);padding:8px 12px;background:var(--navy-deep)}
  .theirs{background:var(--navy-card);border:1px solid var(--navy-line);border-radius:10px;
    padding:18px 20px;margin:0 0 8px;font-size:16px;line-height:1.65;color:var(--ivory)}
  .theirs .lab{display:block;font-size:11px;letter-spacing:.16em;text-transform:uppercase;
    color:var(--gold);font-weight:700;margin:0 0 8px}
  .asks{margin:0;padding:0}
  .asks li{list-style:none;padding:14px 0;border-bottom:1px solid var(--navy-line);
    font-size:16px;line-height:1.6;color:var(--ivory)}
  .asks li:last-child{border-bottom:0}
  .asks b{display:block;font-family:var(--serif);font-size:19px;font-weight:600;margin:0 0 3px}
  .facts{margin:0;padding:0}
  .facts li{list-style:none;padding:13px 0 13px 26px;position:relative;font-size:16px;
    line-height:1.62;color:var(--ivory);border-bottom:1px solid var(--navy-line)}
  .facts li:last-child{border-bottom:0}
  .facts li:before{content:"";position:absolute;left:0;top:21px;width:9px;height:9px;
    border-radius:50%;background:var(--gold)}
  .facts b{color:#fff;font-weight:600}
  .rem{margin:0;padding:0}
  .rem li{list-style:none;padding:12px 0;border-bottom:1px solid var(--navy-line);
    font-family:var(--serif);font-size:19px;color:var(--ivory);line-height:1.35}
  .rem li:last-child{border-bottom:0}
  .rem .cat{display:block;font-family:'Inter',sans-serif;font-size:12px;letter-spacing:.1em;
    text-transform:uppercase;color:var(--ivory-dim);font-weight:600;margin:0 0 4px}
"""


def first_lines(text, limit=145):
    """What the feed actually shows before it cuts the post off.

    A post can be three words or three hundred. Every platform truncates after a line or two and
    hides the rest behind "see more", so the opening is doing nearly all the work. We show what
    a scroller sees, and dim the rest.
    """
    text = " ".join(text.split())
    if len(text) <= limit:
        return text, ""
    cut = text[:limit]
    for mark in (". ", "! ", "? "):          # prefer to break where a sentence ends
        i = cut.rfind(mark)
        if i > 60:
            return text[:i + 1], text[i + 1:].strip()
    i = cut.rfind(" ")
    return text[:i], text[i:].strip()


def render():
    f = FAKE
    # Only the opening. The rest is not shown at all: two words or two hundred, the first line is
    # the bit that decides, and showing the rest invites them to read past the problem.
    shown, _ = first_lines(f["post"])
    # Pulled from part one of their own report. Nothing new is worked out here.
    reminders = [
        ("What they're really buying", "They want to feel like themselves again"),
        ("What made them start looking for help", "They felt awful even after starting HRT"),
        ("What they want to happen instead", "They want to be happy, sharp, and in control"),
        ("What stops them buying", "They think nothing actually works"),
        ("What they've stopped believing", "They've been promised relief too many times"),
        ("What makes them pick one coach over another", "They need someone who can explain why"),
    ]
    rem = "".join(f'<li><span class="cat">{c}</span>{n}</li>' for c, n in reminders)

    body = f"""
  <div class="rwrap">
  <p class="mock-note"><b>This is a mockup.</b> The coach, the bio, the banner and the post are
  invented. Nothing behind it is built. It is here so you can look at the shape.</p>

  <p class="r-eyebrow">Your social media</p>
  <h1 class="r-title">Your {f['platform']} profile</h1>
  <p class="r-for">{f['name']}, this is what a stranger sees when they click your name.</p>

  <section class="r">
    <h2>Here's what they see</h2>
    <div class="banner">
      <div class="strip">&ldquo;She believed she could, so she did&rdquo;</div>
      <div class="cap">Your banner</div>
    </div>
    <div class="theirs"><span class="lab">Your bio</span>{f['bio']}</div>
    <div class="theirs"><span class="lab">The start of your last post</span>{shown}</div>
    <p class="r-sec">We're only showing you the first few words. Whether a post is two words or two
    hundred, people read the first line and decide whether to carry on. And that decision isn't
    about reading the rest of your post, or your next one. It's whether to stay on your profile
    or leave.</p>
  </section>

  <section class="r">
    <h2>Nobody arrives at your profile by accident</h2>
    <p>Maybe they saw a post in a group, or on their newsfeed, or {f['platform']} put you up as
    someone to follow. Either way, they clicked your name to check you out, because they thought
    you might be worth a look. So they turn up already half interested.</p>
    <p>The job now is to turn that interest into commitment. Following you, sending a connection
    request, or messaging you.</p>
  </section>

  <section class="r">
    <h2>A reminder of your six triggers</h2>
    <p>This is what {f['audience']} buy on. Keep it in your head while you read the next bit.</p>
    <ul class="rem">{rem}</ul>
  </section>

  <section class="r">
    <h2>Now read your profile as a stranger</h2>
    <p>Someone who has just clicked your name is asking four things, in this order. Go back up,
    read your banner and your bio again, and answer them honestly.</p>
    <ul class="asks">
      <li><b>Is this person for me?</b> Do they work with people like me, with my problem.</li>
      <li><b>Are they any good?</b> Any sign they know what they're talking about.</li>
      <li><b>Is there more of what I just liked?</b> Was that post a one-off, or is this
      consistently for me.</li>
      <li><b>What do I do if I want more?</b> Is there a next step, or is this a dead end.</li>
    </ul>
  </section>

  <div class="r-next">
    <h2>So what now</h2>
    <p>You've seen what your buyers buy on, and you've read your own profile as a stranger reads
    it. If those two don't match, that's where your next clients are going instead.</p>
    <p>Closing that is a different job, and it's the one we do.</p>
    <a class="nextbtn" href="#">Show me how that works</a>
  </div>
  </div>
"""
    page = _t._shell(body, title_suffix="&mdash; mockup")
    return page.replace("</style>", _t._REPORT_CSS + _CSS + "</style>")
