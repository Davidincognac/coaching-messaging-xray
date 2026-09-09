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
import re
import sys

import triggers as t

SAMPLE = 60

# Words and marks David has banned outright.
BANNED_WORDS = [
    "land", "lands", "landed", "quietly", "the gap", "drift", "drifts", "drifted", "rescue",
    "delve", "leverage", "robust", "navigate", "unlock", "elevate", "harness", "foster", "realm",
    "tapestry", "testament", "furthermore", "moreover", "additionally", "ultimately",
    "in today's world", "guessing", "—",
]

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
]

# Full-form negatives. His style file says contractions always.
FORMAL = re.compile(
    r"\b(do not|does not|did not|cannot|will not|is not|are not|was not|were not|"
    r"have not|has not|had not|would not|could not|should not)\b", re.I)


def text_of(page_html):
    stripped = re.sub(r"<script.*?</script>", " ", page_html, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", stripped)))


def check(label, page_html, hits):
    txt = text_of(page_html)
    low = txt.lower()
    for w in BANNED_WORDS:
        if re.search(r"\b" + re.escape(w) + r"\b" if w.isalpha() else re.escape(w), low):
            hits.append((label, f"banned word: {w!r}"))
    for pat, why in BANNED_SHAPES:
        m = re.search(pat, txt, re.I)
        if m:
            hits.append((label, f"{why}: {m.group(0)!r}"))
    m = FORMAL.search(txt)
    if m:
        hits.append((label, f"no contraction: {m.group(0)!r}"))


def main():
    every = "--all" in sys.argv
    hits = []
    check("landing page", t.render_triggers(), hits)
    check("landing page (error state)", t.render_triggers(error="Test"), hits)

    markets = [e["n"] for e in t.niche_list()]
    if not every:
        step = max(1, len(markets) // SAMPLE)
        markets = markets[::step]
    for m in markets:
        check(f"report: {m}", t.render_report(m, "David", fragment=True), hits)
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
