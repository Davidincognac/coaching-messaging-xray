"""Strip David's banned words out of the stored research prose.

The rewrite prompt bans these, and the model still produces them now and again. Re-prompting costs
money and may fail the same way, so the reliable fix is a pass over what was actually written.

Deleting an adverb is always safe, and Hemingway wants it gone anyway. The rest are swapped for what
they actually mean. The buyer's own words are never touched: a real person is allowed to say "I
cannot find anyone appropriate there", and rewriting a quote to fix its grammar would make it a lie.

    python3 clean_banned.py            # clean and report
    python3 clean_banned.py --dry-run  # just report
"""
import json
import os
import re
import sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triggers_data.json")
NEVER_TOUCH = {"audience", "voice"}      # audience is checked elsewhere; voice is the buyer talking

RULES = [
    (r"\bquietly\s+", ""), (r"\s+quietly\b", ""), (r"\bquietly\b", ""),
    (r"\bno matter how much\b", "however much"), (r"\bno matter how\b", "however"),
    (r"\bno matter what\b", "whatever"), (r"\bno matter\b", "whatever"),
    (r"\bas a matter of fact\b", "in fact"), (r"\ba matter of time\b", "a question of time"),
    (r"\bfamily matters\b", "family business"),
    (r"\bwhat matters most\b", "what counts most"), (r"\bwhat matters\b", "what counts"),
    (r"\bmatters enormously\b", "counts for a lot"), (r"\bmatters hugely\b", "counts for a lot"),
    (r"\bmatters more\b", "counts more"), (r"\bmatters a lot\b", "counts for a lot"),
    (r"\bthe people who matter\b", "the people closest to them"),
    (r"\bpeople who matter\b", "people closest to them"),
    (r"\bmatters to them\b", "counts with them"), (r"\bmatters\b", "counts"), (r"\bmatter\b", "count"),
    (r"\bdon't land anymore\b", "don't do anything for them anymore"),
    (r"\bdoesn't land\b", "doesn't work on them"), (r"\bit lands\b", "it works"),
    (r"\bthat lands\b", "that works"), (r"\blands with\b", "works on"), (r"\blanded\b", "worked"),
    (r"\blands\b", "works"), (r"\bland with\b", "work on"),
    (r"\bland hard\b", "hurt"), (r"\bstill land\b", "still hurt"), (r"\bland badly\b", "hurt"),
    (r"\bwill actually land\b", "will actually work"), (r"\bactually land\b", "actually work"),
    (r"\bdoesn't even land\b", "does nothing for them"), (r"\beven land\b", "do anything"),
    (r"\bdon't even land\b", "do nothing for them"),
    (r"\bstopped landing\b", "stopped working on them"), (r"\bstops landing\b", "stops working"),
    (r"\bland first\b", "work first"), (r"\blanding with\b", "working on"),
    (r"\bdrifted back\b", "slid back"),
    # "most of them" claims a majority with nothing behind it. David bans "most" without a number.
    (r"\bmost of them\b", "a lot of them"), (r"\bmost people\b", "a lot of people"),
    (r"\bmost coaches\b", "plenty of coaches"), (r"\bmany of them\b", "a lot of them"),
    (r"\bmany people\b", "a lot of people"),
    (r"\bwill land\b", "will work"), (r"\bto land\b", "to work"), (r"\bever land\b", "ever work"),
    (r"\bdrifts\b", "slides"), (r"\bdrift\b", "slide"), (r"\bdrifting\b", "sliding"),
    (r"\bnavigating\b", "getting through"), (r"\bnavigate\b", "get through"),
    (r"\bunlock\b", "open up"), (r"\belevate\b", "lift"), (r"\bleverage\b", "use"),
    (r"\brobust\b", "solid"), (r"\bharness\b", "use"), (r"\bdelve into\b", "dig into"),
    (r"\brescue\b", "fix"), (r"\bat the end of the day,?\s*", ""),
    (r"\bThat's the whole thing\.\s*Under that is\s*", "There's "),
    (r"\bThat's the whole thing\.\s*", ""), (r"\bUnder that is\b", "Underneath it is"),
    (r"\banother layer\b", "another part of it"),
    # full-form negatives: his style file says contractions always
    (r"\bdo not\b", "don't"), (r"\bdoes not\b", "doesn't"), (r"\bdid not\b", "didn't"),
    (r"\bcannot\b", "can't"), (r"\bwill not\b", "won't"), (r"\bis not\b", "isn't"),
    (r"\bare not\b", "aren't"), (r"\bwas not\b", "wasn't"), (r"\bwere not\b", "weren't"),
    (r"\bhave not\b", "haven't"), (r"\bhas not\b", "hasn't"), (r"\bhad not\b", "hadn't"),
    (r"\bwould not\b", "wouldn't"), (r"\bcould not\b", "couldn't"),
    (r"\bshould not\b", "shouldn't"),
]

SENTENCE_START = [(r"(^|(?<=[.!?]\s))It is\b", "It's"), (r"(^|(?<=[.!?]\s))That is\b", "That's"),
                  (r"(^|(?<=[.!?]\s))There is\b", "There's"), (r"(^|(?<=[.!?]\s))They are\b", "They're"),
                  (r"(^|(?<=[.!?]\s))You are\b", "You're"), (r"(^|(?<=[.!?]\s))We are\b", "We're")]


# THEIR WORDS ARE NOT OURS TO EDIT. (David, and he is right.)
#
# A market is named by its own language. "foster care" contains a word we ban as a verb. "no matter
# how" is banned, but "grey matter" is a body part. Blind find-and-replace across a thousand markets
# turns their vocabulary into nonsense, and the coach reading it knows their own field better than we
# do. So every phrase that belongs to THEM gets masked out before any rule runs, and put back after.
#
# The protected list is built FROM THE DATA, not typed by hand: every market name, every audience
# label, and every insider word the buyer uses. Add a market and it protects itself.
FIXED_PROTECTED = [
    "grey matter", "gray matter", "subject matter", "foster care", "foster parent",
    "foster child", "foster famil", "foster-to-adopt", "landlord", "landing page",
    "lands a job", "netherlands", "highlands", "no-contact", "no contact",
]


def protected_phrases(data):
    out = set(FIXED_PROTECTED)
    for bucket in ("niches", "subniches"):
        for name, rec in data[bucket].items():
            out.add(name.lower())
            aud = (rec.get("prose_plain") or {}).get("audience")
            if aud:
                out.add(aud.lower())
            for word in (rec.get("voice") or {}).get("jargon", []) or []:
                if isinstance(word, str) and word.strip():
                    out.add(word.strip().lower())
    # longest first, so "foster care" is claimed before "foster"
    return sorted((p for p in out if len(p) > 3), key=len, reverse=True)


def clean(text, protected=()):
    # Mask their language, run our rules, put their language back exactly as it was.
    held = []

    def stash(m):
        held.append(m.group(0))
        return f"\x00{len(held)-1}\x00"

    out = text
    for phrase in protected:
        out = re.sub(re.escape(phrase), stash, out, flags=re.I)
    for pat, rep in RULES:
        out = re.sub(pat, rep, out, flags=re.I)
    for pat, rep in SENTENCE_START:
        out = re.sub(pat, rep, out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    out = re.sub(r"\s+([.,;:])", r"\1", out)
    out = re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], out)
    return (out[:1].upper() + out[1:]) if out else out


def main():
    dry = "--dry-run" in sys.argv
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    prot = protected_phrases(d)
    print(f"protecting {len(prot)} phrases that belong to the markets, not to us")
    changed = 0
    for bucket in ("niches", "subniches"):
        for rec in d[bucket].values():
            pp = rec.get("prose_plain") or {}
            for k, v in list(pp.items()):
                if k in NEVER_TOUCH or not isinstance(v, str):
                    continue
                new = clean(v, prot)
                if new != v:
                    changed += 1
                    if not dry:
                        pp[k] = new
    if not dry:
        tmp = DATA + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, DATA)
    print(f"{'would clean' if dry else 'cleaned'} {changed} field(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
