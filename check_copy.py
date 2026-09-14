"""Slop check for every word a coach reads.

David kept catching lines I had written and asked how to make it stop. The answer is that my own
judgement wrote them, so my judgement cannot be the thing that catches them. This is the thing that
catches them.

It renders real pages and real reports, strips the HTML, and greps the result. A line I hardcode
appears on all 1,023 reports, so this runs over a sample of markets AND the landing page.

    python3 check_copy.py            # fails loudly, lists every hit
    python3 check_copy.py --all      # every market, not a sample
"""
import html
import os
import re
import sys

import triggers as t
from clean_banned import protected_phrases

SAMPLE = 60

# The Poole house style blocklist, from ~/Documents/claude/poole-house-style.md. Banned JOBS, not
# banned words: each of these is almost always doing Pattern A (physical verb on an abstract noun),
# Pattern B (signposting that a line matters instead of writing one that does), or Pattern C (a mood
# word bolted to an abstraction). If one is ever genuinely doing work, keep it and exempt it here.
HOUSE_PHRASES = [
    "that matters", "in today's fast-moving world", "in today's fast-paced world",
    "at the end of the day", "the bottom line is", "let that sink in", "read that again",
    "here's the thing", "the truth is", "the reality is", "this is where the magic happens",
    "game-changer", "unlock your potential", "lean into", "embrace the journey",
    "show up as your best self", "step into your power", "create meaningful impact",
    "make an impact", "drive meaningful change", "move the needle", "foster a culture of",
    "create space for", "lead with intention", "lead with empathy", "lead with authenticity",
    "bring your whole self", "it starts with you", "it all starts with", "the key is",
    "the secret is", "the future belongs to", "now more than ever",
    "we need to shift the conversation", "reframe the way we think about",
    "challenge the status quo", "think outside the box", "a powerful reminder",
    "a gentle reminder", "food for thought", "pause and reflect", "ask yourself",
    "you're too close to it", "shallow end", "quantum leap", "vibrational alignment",
    "holding space", "in conclusion",
]
HOUSE_WORDS = [
    "delve", "leverage", "robust", "navigate", "unlock", "elevate", "harness", "foster",
    "realm", "tapestry", "testament", "furthermore", "moreover", "additionally", "ultimately",
    "drift", "rescue", "intake", "third-party", "credentials", "resource", "capture",
    "holistic", "curious",
]

# Words and marks David has banned outright.
BANNED_WORDS = [
    "land", "lands", "landed", "quietly", "the gap", "drift", "drifts", "drifted", "rescue",
    "delve", "leverage", "robust", "navigate", "unlock", "elevate", "harness", "foster", "realm",
    "tapestry", "testament", "furthermore", "moreover", "additionally", "ultimately",
    "in today's world", "guessing", "—", "matter", "matters", "mattered",
] + HOUSE_WORDS + [
]

# A banned word is banned in ONE sense. "foster care" is the literal thing a market is named after,
# not the verb David objects to. Without this the checker cries wolf on eleven markets forever.
ALLOWED_IN_CONTEXT = {
    "foster": ("foster care", "foster parent", "foster adult", "foster-to-adopt", "foster child",
               "foster famil", "adoptive and foster", "adoptees and foster", "foster or adoptive",
               "adopted or foster", "foster and adoptive"),
    "land": ("landlord", "england", "ireland", "scotland", "land on", "land somewhere",
             "land anywhere", "landed on", "landing on", "land a job", "landed a",
             "landing page", "land the first", "landing paying", "landing client",
             "land a client", "landing me", "lands me", "land in", "landed in",
             "land that", "landing them", "land them"),
    # A returning mother's CV gap is HER word for HER problem, not our slop phrase. Same for a
    # pay gap. David: when we are using language used by the client, that must be untouched.
    "the gap": ("career", "employment", "cv", "wage", "pay gap", "gap year", "employer",
                "work", "job", "maternity", "return", "standing", "cost them", "resume"),
    # "second-guessing" is the BUYER doubting themselves. The banned rule is about never calling
    # the COACH a guesser, which is a different thing entirely.
    "guessing": ("second-guessing", "second guessing", "they guess", "they can't stop",
                 "having to guess", "guessing got", "guessing stopped", "stop second",
                 "guessing themselves", "guessing every", "guessing feels", "guessing about",
                 "the guessing", "guessing whether", "guessing what"),
}

# Constructions. These are the ones that read as written-by-a-machine even when every word is plain,
# and they are what I keep producing when I try to smooth a transition or land a point.
BANNED_SHAPES = [
    (r"\banother layer\b|\bunder that is\b|\blayer under\b", "'layer' talk. Nobody says it."),
    (r"That's (the whole thing|it|all)\b", "performed punchline"),
    (r"\b(simple as that|that simple)\b", "performed punchline"),
    (r"\bit's not just\b.{0,40}\bit's\b", "the 'not just X, it's Y' polish"),
    (r"\bhere's the (harder|hard) truth\b", "banned phrase"),
    (r"\bthat's where\b.{0,25}\b(go|goes|live|lives)\b", "vague 'that's where X' closer"),
    (r"\b(most|many) (coaches|coaching websites|people)\b(?!.{0,30}\d)", "'most' with no number behind it"),
    (r"\byou're too close to it\b", "banned phrase"),
    (r"\bwhat this means (for you )?is\b", "throat-clearing"),
    (r"\bat the end of the day\b|\bwhen all is said\b", "filler"),
    (r"\bit is worth noting\b|\bit's worth noting\b", "throat-clearing"),
    # Abstract pictures with nothing behind them. A twelve-year-old has to understand every line.
    (r"\bpulls? (less|at them|harder|hard)\b", "'pull' as a metaphor. What is pulling?"),
    (r"\bthe ones (above|below)\b", "makes the reader scroll back to work out what you mean"),
    (r"\bbut (they|it) (are|is) there\b", "says nothing"),
    (r"\bsits? (under|beneath|underneath) (this|that|those|it)\b", "abstract picture"),
    (r"\bunder (that|this) (is|sits|lies)\b", "abstract picture"),
    (r"\bon (a|the) deeper level\b|\bat a deeper level\b", "abstract"),
    # Only the abstract sense. "Someone who speaks to them like a normal person" is a person
    # speaking, which is concrete and fine.
    (r"\bspeaks? to (them|their)\b(?! like)", "vague. Say what it actually does"),
    (r"\bresonates?\b", "jargon a coach would not say out loud"),
]

# ADVICE. The report explains the buyer; it never tells the coach what to do, because an instruction
# is a brief they can hand to a copywriter and never come back. David: "all they are going to do is
# copy what we have given them, we cannot give advice." The test: the BUYER is the subject. If a
# sentence orders the coach about, or its subject is "you" or "your page", it does not belong.
ADVICE = [
    (r"(?<![a-z])(start|lead|open|begin) with", "instruction to the coach"),
    (r"(?<![a-z])(show|tell|give|remind) them", "instruction to the coach"),
    (r"don't (lead|start|open|say|promise|use|write)", "instruction to the coach"),
    (r"your (page|headline|copy|website|first line|opening)", "telling them what to write"),
    (r"make (that|this|it) the", "instruction to the coach"),
    (r"you need to (explain|show|say|write|name)", "instruction to the coach"),
    (r"name the.{0,20}first", "instruction to the coach"),
]

# Kept for reference only. US spellings are fine, so nothing checks this any more.
AMERICAN = re.compile(
    r"\b(judgment|apologiz\w+|recogniz\w+|behavior\w*|realiz\w+|organiz\w+|prioritiz\w+|"
    r"minimiz\w+|maximiz\w+|normaliz\w+|analyz\w+|paralyz\w+|fulfill\w*|skillful|labeled|"
    r"canceled|practicing|traveling|colors?|favorite|favor|honor|centere?d?|defense|offense)\b",
    re.I)

# Full-form negatives. His style file says contractions always.
FORMAL = re.compile(
    r"\b(do not|does not|did not|cannot|will not|is not|are not|was not|were not|"
    r"have not|has not|had not|would not|could not|should not)\b", re.I)


# The markets' own language, loaded from the same place the cleaner loads it, so the two tools can
# never disagree about what belongs to us and what belongs to them. David's rule: when we are using
# language used by the client, that must be untouched by our editing.
_PROTECTED = None


def _protected():
    global _PROTECTED
    if _PROTECTED is None:
        import json
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "triggers_data.json"), encoding="utf-8") as f:
            _PROTECTED = [p.lower() for p in protected_phrases(json.load(f))]
    return _PROTECTED


def _inside_their_words(low, start, end):
    """Is this hit sitting inside a market name, an audience label, or the buyer's own jargon?"""
    window = low[max(0, start - 60):end + 60]
    for phrase in _protected():
        if phrase in window:
            i = window.find(phrase)
            hit_at = start - max(0, start - 60)
            if i <= hit_at < i + len(phrase):
                return True
    return False


def text_of(page_html):
    """Everything a coach reads that WE wrote.

    The buyer's own words are cut out first. They are quotes from real people, and a real person is
    allowed to say "I cannot find anyone appropriate there." Policing their grammar would be both
    wrong and pointless, since we would have to change the quote to fix it.
    """
    # HTML comments are notes from us to us. They ship inside the page but no coach ever reads
    # them, and treating a comment that explains a CSS decision as copy is how the checker starts
    # crying wolf about words that are not on the screen.
    stripped = re.sub(r"<!--.*?-->", " ", page_html, flags=re.S)
    stripped = re.sub(r"<script.*?</script>", " ", stripped, flags=re.S)
    # Same for the stylesheet. A CSS comment explaining why four headings share one size is a note
    # to whoever edits the CSS next, not a sentence anybody reads, and leaving it in the haystack
    # means the checker reports words that are nowhere on the screen.
    stripped = re.sub(r"<style.*?</style>", " ", stripped, flags=re.S)
    stripped = re.sub(r'<div class="voice">.*?</div>\s*</section>', " ", stripped, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", stripped)))


def check(label, page_html, hits):
    txt = text_of(page_html)
    low = txt.lower()
    for w in BANNED_WORDS:
        pat = r"\b" + re.escape(w) + r"\b" if w.isalpha() else re.escape(w)
        for m in re.finditer(pat, low):
            around = low[max(0, m.start() - 70):m.end() + 70]
            if any(ok in around for ok in ALLOWED_IN_CONTEXT.get(w, ())):
                continue                # the literal thing, not the banned sense
            if _inside_their_words(low, m.start(), m.end()):
                continue                # their word, not ours
            hits.append((label, f"banned word: {w!r}"))
            break
    for pat, why in BANNED_SHAPES:
        m = re.search(pat, txt, re.I)
        if m:
            hits.append((label, f"{why}: {m.group(0)!r}"))
    for pat, why in ADVICE:
        m = re.search(pat, txt, re.I)
        if m:
            hits.append((label, f"{why}: {m.group(0)!r}"))
    for phrase in HOUSE_PHRASES:
        i = low.find(phrase)
        if i >= 0 and not _inside_their_words(low, i, i + len(phrase)):
            hits.append((label, f"house style: {phrase!r}"))
    m = FORMAL.search(txt)
    if m:
        hits.append((label, f"no contraction: {m.group(0)!r}"))


# STRUCTURE. The copy rules catch words. They do not catch a button with no link on it, which is
# exactly what shipped today: the href was mangled into literal text, the page rendered, nothing
# errored, and every report had a dead call to action. These are the cheap tests that catch that.
LEFTOVERS = ["+ e(", "{audience}", '"""', "&lt;p", "&lt;div", "audit_url", "quote=True"]


def check_structure(label, page_html, hits):
    def bad(why):
        hits.append((label, f"STRUCTURE: {why}"))

    for a in re.finditer(r"<a\b[^>]*>", page_html):
        tag = a.group(0)
        href = re.search(r'href="([^"]*)"', tag)
        if not href or not href.group(1).strip():
            bad("a link with no href")
        elif href.group(1).strip() in ("#", "undefined", "None"):
            bad(f"a link going nowhere: {href.group(1)!r}")

    for img in re.finditer(r"<img\b[^>]*>", page_html):
        tag = img.group(0)
        if not re.search(r'src="[^"]+"', tag):
            bad("an image with no src")
        if not re.search(r'alt="[^"]+"', tag):
            bad("an image with no alt text")

    if re.search(r"<(p|h1|h2|h3|li)[^>]*>\s*</\1>", page_html):
        bad("an empty paragraph or heading")

    for junk in LEFTOVERS:
        if junk in page_html:
            bad(f"unrendered template text: {junk!r}")

    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", page_html, re.S):
        if not re.sub(r"<[^>]+>", "", m.group(1)).strip():
            bad("a heading with nothing in it")


def check_report_shape(market, page_html, hits):
    """The landing page promises six triggers. Every report has to have six, plus the proof."""
    if "read this market" in page_html:
        return                                   # the honest "we do not hold this one" page
    # Count the rails, not a class name that happens to be on the number today. Every section gets
    # exactly one, so this survives the next time somebody restyles the thing, which is precisely
    # what just happened to the check that counted "r-num".
    n = len(re.findall(r'class="r-rail"', page_html))
    if n != 7:
        hits.append((f"report: {market}", f"STRUCTURE: {n} sections, expected 6 triggers plus the proof"))
    if 'class="nextbtn"' not in page_html:
        hits.append((f"report: {market}", "STRUCTURE: no call to action at the end"))


def main():

    every = "--all" in sys.argv
    hits = []
    land = t.render_triggers()
    check("landing page", land, hits)
    check_structure("landing page", land, hits)
    check("landing page (error state)", t.render_triggers(error="Test"), hits)
    for field in ("first_name", "last_name", "email", "niche"):
        if 'name="' + field + '"' not in land:
            hits.append(("landing page", "STRUCTURE: the form has no " + field + " field"))
    if 'id="processing"' not in land or 'class="pbar"' not in land:
        hits.append(("landing page", "STRUCTURE: Angelo's progress panel is missing"))

    markets = [e["n"] for e in t.niche_list()]
    if not every:
        step = max(1, len(markets) // SAMPLE)
        markets = markets[::step]
    for m in markets:
        page = t.render_report(m, "David", fragment=True)
        check(f"report: {m}", page, hits)
        check_structure(f"report: {m}", page, hits)
        check_report_shape(m, page, hits)
    check("market we hold nothing for", t.render_report("zzz nothing", "David", fragment=True), hits)

    # One line I hardcode shows up on every report, so collapse by reason to see what matters.
    by_reason = {}
    for label, reason in hits:
        by_reason.setdefault(reason, []).append(label)
    print(f"checked {len(markets)} markets plus the landing page.")
    if not by_reason:
        print("clean.")
        return 0
    print(f"\n{len(by_reason)} problem(s):\n")
    for reason, where in sorted(by_reason.items(), key=lambda x: -len(x[1])):
        print(f"  {len(where):>4} page(s)  {reason}")
        print(f"            first seen on: {where[0]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
