"""Rewrite the research prose into plain English a coach can read.

The lens files were written for us. They carry analyst shorthand: "elaborate the mechanism to explain
residual symptoms", "the specific cluster", "re-promise generic relief". None of that belongs in front
of a coach, and no amount of regex fixes it. So this makes ONE pass over the research, rewrites each
prose field in David's voice, and stores the result next to the original as a `*_plain` field.

It runs offline, by hand, not per report. The report reads the stored plain version and falls back to
the original when a market has not been rewritten yet. So a half-finished pass still ships.

    python3 rewrite_lens_prose.py --niche "Menopause & women's hormones"   # one, to eyeball it
    python3 rewrite_lens_prose.py --count                                  # what a full pass covers
    python3 rewrite_lens_prose.py --all                                    # the lot, resumable

Nothing is overwritten unless you pass --force, so a re-run only fills the gaps.
"""
import argparse
import concurrent.futures
import json
import re
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "triggers_data.json")
MODEL = os.getenv("AUDIT_MODEL", "claude-sonnet-5")

# The fields that are prose a coach reads. The rest are labels or already the buyer's own words.
PROSE_FIELDS = ["lf8_evidence", "lead_with", "implication", "jtbd_job", "push", "pull",
                "anxiety", "habit", "cialdini_why", "note"]

# Slop David has banned. A rewrite carrying one of these is kept but flagged, so the run ends with a
# list of the markets worth reading by eye.
SLOP = ("it's not just", "it is not just", " lands", " land ", "quietly", "the gap", "drift",
        "rescue", "delve", "leverage", "robust", "unlock", "elevate", "harness", "foster",
        "tapestry", "testament", "furthermore", "moreover", "ultimately", "guessing")
FLAGGED = []

VOICE = (
    "You are the voice of David Poole. Rewrite research notes into plain English a coach reads on a "
    "free report about what makes their clients buy.\n"
    "HOW TO WRITE. Blunt, warm, plain-spoken, like a straight-talking friend who knows marketing. "
    "USE CONTRACTIONS ALWAYS: don't, doesn't, they're, you're, it's, won't, can't, haven't. Writing "
    "them out in full is the loudest sign a machine wrote it. Vary sentence length hard, a short one "
    "then a longer one. Even, medium-length sentences all the same size is the other big tell. "
    "Plain everyday words a 12-year-old understands. Hemingway: short sentences, active voice, no "
    "adverbs propping up weak verbs, no clever phrasing. Be obvious, never clever. You are NOT "
    "writing for the Guardian. Say the thing, then stop.\n"
    "WHAT YOU ARE REWRITING. Notes written by an analyst for internal use. They are full of jargon: "
    "'mechanism', 'cluster', 'residual', 'sophistication', 'awareness stage', 'positioning', "
    "'elaborate', 'differentiate'. Strip every one of those and say what it MEANS in ordinary words.\n"
    "KEEP THE MEANING EXACTLY. Never add a fact, a number, a claim or an example that is not in the "
    "note. Never invent. If the note names a real thing (HRT, a job title, a symptom), keep it.\n"
    "NEVER NAME OUR SOURCES OR METHOD. No book titles, no counts, no framework names, no author "
    "names, no mention of Cashvertising, Life Force 8, Cialdini, awareness stages or sophistication "
    "stages. Say what the buyer does, not what a model calls it.\n"
    "BANNED, these read as AI slop: em dashes (never), 'land'/'lands', 'quietly', 'the gap', "
    "'drift', 'rescue', 'delve', 'leverage', 'robust', 'navigate', 'unlock', 'elevate', 'harness', "
    "'foster', 'realm', 'tapestry', 'testament', 'furthermore', 'moreover', 'additionally', "
    "'ultimately', \"it's not just X, it's Y\", 'guessing', 'matter', 'matters', 'no matter how'. "
    "No lists of three for rhythm. No neat "
    "endings that restate what you just said.\n"
    "Return ONLY a JSON object mapping each key you were given to its rewritten string. No commentary."
)


# Lower-casing the label reads naturally inside a heading, but it flattens the acronyms a market is
# actually named by. "adults with adhd" is wrong in a headline; "adults with ADHD" is what a coach
# would write themselves.
ACRONYMS = ["ADHD", "OCD", "PTSD", "HRT", "IBS", "ASD", "CBT", "CEO", "CTO", "HR", "NHS", "PhD",
            "ME/CFS", "CFS", "PCOS", "IVF", "MBA", "SEN", "STEM", "AI", "C-suite", "LGBTQ", "PMDD"]


def fix_acronyms(text):
    out = text
    for a in ACRONYMS:
        out = re.sub(r"\b" + re.escape(a.lower()) + r"\b", a, out)
    return out


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, DATA)


def rewrite(client, name, rec):
    """One market. Returns the plain versions, or None if the call gave us nothing usable."""
    payload = {k: rec[k] for k in PROSE_FIELDS if rec.get(k)}
    if not payload:
        return None
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1600,
        system=VOICE,
        messages=[{"role": "user", "content":
                   f"Market: {name}\n\nRewrite each value. Keep the keys exactly as given.\n\n"
                   + json.dumps(payload, ensure_ascii=False, indent=1)
                   + "\n\nAlso add one extra key, \"audience\": a short plain label for the people "
                     "this coach serves, written so it drops straight into a sentence like \"what "
                     "<audience> pay attention to\". Lower case, no ampersands, no slashes, no "
                     "jargon. For \"Menopause & women's hormones\" it would be \"women going through "
                     "menopause\". For \"First-time / new managers\" it would be \"first-time "
                     "managers\". FOUR WORDS AT MOST. It goes inside a heading, so a long one pushes "
                     "that heading onto four lines of a phone. Shorter always wins."}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        print(f"  ! {name}: model did not return JSON, left as is", file=sys.stderr)
        return None
    # A framework name coming back is a real failure and the field is dropped. An em dash is not
    # worth losing a good rewrite over, so it is swapped for a comma the same way the report does it.
    frameworks = ("Cashvertising", "Life Force", "Cialdini", "Schwartz")
    kept = {}
    for k, v in out.items():
        if k not in PROSE_FIELDS + ["audience"] or not isinstance(v, str) or not v.strip():
            continue
        if k == "audience":
            # A heading is built from this, so it has to be clean and short or it is not worth having.
            v = fix_acronyms(v.strip().rstrip(".").lower())
            if len(v.split()) > 5 or any(c in v for c in "&/"):
                print(f"  ! {name}/audience: {v!r} will not sit in a heading, dropped", file=sys.stderr)
                continue
            kept[k] = v
            continue
        if any(b.lower() in v.lower() for b in frameworks):
            print(f"  ! {name}/{k}: named the framework, dropped", file=sys.stderr)
            continue
        v = v.replace("\u2014", ",").replace("\u2013", ",").strip()
        slop = [w for w in SLOP if w in v.lower()]
        if slop:
            # Not dropped. The rewrite is still better than the analyst note, but David should see it.
            FLAGGED.append((name, k, slop))
        kept[k] = v
    return kept


AUDIENCE_ONLY = (
    "You name coaching markets in plain English. Given a market name, return ONE short label for the "
    "people that coach serves, written so it drops into a sentence like \"what <label> want enough to "
    "pay for\". Lower case, no ampersands, no slashes, FIVE WORDS AT MOST, shorter is better. Keep "
    "acronyms a market is named by (ADHD, OCD, PTSD, HRT). Examples: \"Menopause & women's hormones\" "
    "-> women in menopause. \"First-time / new managers\" -> first-time managers. \"ADHD in children\" "
    "-> parents of ADHD children. Return the label only. No quotes, no full stop, no explanation."
)


def audience_only(client, name, rec):
    """Just the heading label. A tenth the size of a full rewrite, and far more reliable, because the
    model is asked for one thing instead of being asked for it as an afterthought."""
    msg = client.messages.create(
        model=MODEL, max_tokens=40, system=AUDIENCE_ONLY,
        messages=[{"role": "user", "content": name}],
    )
    v = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    v = fix_acronyms(v.strip().strip('"').rstrip(".").lower())
    if not v or len(v.split()) > 5 or any(c in v for c in "&/"):
        return None
    return {"audience": v}


TRIGGERS_SYS = (
    "You write a report that EXPLAINS what makes a coach's clients buy. You never tell the coach what "
    "to do, write, say or lead with. They will copy any instruction you give and never need us again. "
    "THE RULE: the BUYER is the subject of every sentence. If a sentence's subject is 'you' or 'your "
    "page', it is wrong. 'Start by naming their exhaustion' is WRONG. 'They are exhausted and they "
    "say so before they say anything else' is RIGHT. Same fact, no instruction.\n"
    "VOICE: blunt, warm, plain. Everyday words a twelve-year-old reads out loud and gets. CONTRACTIONS "
    "ALWAYS (don't, they're, it's, won't, haven't). Vary sentence length hard, a short one then a "
    "longer one. Never a run of same-length sentences. Be obvious, never clever. No writerly flourish, "
    "no dramatic one-word sentences for effect, no 'That's the whole thing' punchlines.\n"
    "NEVER use a vague picture where a plain fact will do. Banned in names especially: winning, "
    "taking over, creeping, spiralling, drowning, crushing, eating away, slipping away. A "
    "twelve-year-old must understand every name on first reading.\n"
    "NEVER: name a framework, an author, a book, or a count of anything. No em dashes. No 'layer', "
    "'mechanism', 'positioning', 'leverage', 'unlock', 'navigate', 'elevate', 'foster', 'quietly', "
    "'drift', 'the gap', 'at the end of the day', 'it's not just X it's Y'. And NEVER the "
    "word 'matter' or 'matters' in any form, including 'no matter how'. David has banned it outright. "
    "Say what actually happens instead.\n"
    "Return ONLY a JSON object with exactly these keys and nothing else."
)

TRIGGER_KEYS = ["t1_name","t2_name","t3_name","t4_name","t5_name","t6_name",
                "implication","cialdini_why","push","pull","anxiety","habit"]


def merged(rec, niches):
    """A sub-market's own record holds only what DIVERGES from its parent. The naming pass needs the
    whole picture, so lay the sub over the parent first. Without this the pass sees empty push, pull,
    anxiety and habit fields and names the triggers off half the evidence."""
    parent = niches.get(rec.get("parent", ""), {})
    if not parent:
        return rec
    out = dict(parent)
    out.update(parent.get("prose_plain") or {})
    out.update({k: v for k, v in rec.items() if v and k not in ("voice", "books", "prose_plain")})
    out.update({k: v for k, v in (rec.get("prose_plain") or {}).items() if v})
    return out


def triggers_pass(client, name, rec):
    """Names the six triggers for one market, and rewrites the fields that came back as instructions
    into plain description of the buyer."""
    src = {k: rec.get(k, "") for k in
           ("lf8_primary","lf8_evidence","push","pull","anxiety","habit","jtbd_job",
            "awareness","sophistication","implication","cialdini","cialdini_why")}
    ask = (
        f"Market: {name}. The people are: {rec.get('audience','')}.\n\n"
        "Research:\n" + json.dumps(src, ensure_ascii=False, indent=1) + "\n\n"
        "Return JSON with these keys:\n"
        "t1_name: what this market is really buying, named in 3-7 words, buyer as subject. "
        "e.g. 'They want to stop hurting'\n"
        "t2_name: what made them start looking, 3-7 words. Name the actual EVENT or the moment it "
        "got too much, in words a twelve-year-old reads out loud and gets. e.g. 'They stopped "
        "sleeping through the night', 'Their doctor told them nothing was wrong'. NOT vague "
        "pictures like 'the symptoms started winning' or 'it started taking over', which mean "
        "nothing to a reader.\n"
        "t3_name: what they're reaching for, 3-7 words. e.g. 'They want to feel like themselves again'\n"
        "t4_name: what stops them, 3-7 words. e.g. 'They think nothing will work'\n"
        "t5_name: what they've stopped believing, 3-7 words. e.g. 'They've been promised relief before'\n"
        "t6_name: what tips them to one coach over another, 3-7 words. "
        "e.g. 'They need someone who can explain it'\n"
        "implication: 2-3 sentences on what this market has been promised before and why they no "
        "longer believe it. Describe THEM, never instruct the coach.\n"
        "cialdini_why: 2-3 sentences on why those particular things tip this buyer. Describe THEM.\n"
        "push, pull, anxiety, habit: keep the meaning, plain words, buyer as subject, no instructions."
    )
    msg = client.messages.create(model=MODEL, max_tokens=1200, system=TRIGGERS_SYS,
                                 messages=[{"role": "user", "content": ask}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        print(f"  ! {name}: not JSON", file=sys.stderr)
        return None
    # The framework's own words for the levers leak through as ordinary English ("Authority earns
    # their attention"). Swap them for what they mean, so the wall holds.
    LEVER_WORDS = [("Authority", "someone who plainly knows more"),
                   ("Social Proof", "seeing people like them come through"),
                   ("Social proof", "seeing people like them come through"),
                   ("Unity", "someone who is one of them"),
                   ("Reciprocity", "being given something real first"),
                   ("Scarcity", "a real limit"),
                   ("Commitment", "a small first step"),
                   ("Liking", "warming to someone")]
    kept = {}
    for k in TRIGGER_KEYS:
        v = out.get(k)
        if isinstance(v, str) and v.strip():
            for a, b in LEVER_WORDS:
                v = re.sub(r"(?<![a-z])" + a + r"(?![a-z])", b, v)
            v = v[:1].upper() + v[1:]
            kept[k] = fix_acronyms(v.replace("\u2014", ",").strip()) if k.endswith("_name") else \
                      v.replace("\u2014", ",").strip()
    return kept or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--niche")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--from-file",
                    help="rewrite exactly the markets named in this file, one per line")
    ap.add_argument("--triggers", action="store_true",
                    help="name the six triggers and strip instructions out of the prose")
    ap.add_argument("--audience-only", action="store_true",
                    help="fill in just the missing heading labels, without redoing the prose")
    ap.add_argument("--workers", type=int, default=5,
                    help="markets rewritten at once. Kept modest so we stay inside the rate limit.")
    ap.add_argument("--subniches", action="store_true",
                    help="rewrite the diverging micro-markets instead of the 117 parent markets")
    args = ap.parse_args()

    data = load()
    niches = data["niches"]
    # A micro-niche only needs its own pass when the research says it diverges. The rest inherit the
    # parent's rewrite for free.
    subs = {n: r for n, r in data["subniches"].items() if r.get("diverges")}
    table = subs if args.subniches else niches
    what = "micro-market" if args.subniches else "market"

    if args.count:
        for label, t in (("markets", niches), ("diverging micro-markets", subs)):
            done = sum(1 for r in t.values() if r.get("prose_plain"))
            print(f"{len(t)} {label}. {done} rewritten, {len(t) - done} to go.")
        return

    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Nothing was called and nothing was written.")
    import anthropic
    client = anthropic.Anthropic()

    if args.from_file:
        wanted = [l.strip() for l in open(args.from_file, encoding="utf-8") if l.strip()]
        targets = [n for n in wanted if n in table]
        skipped = len(wanted) - len(targets)
        if skipped:
            print(f"  ({skipped} of the listed markets are not in this table, skipped)")
    elif args.niche:
        targets = [args.niche] if args.niche in table else []
        if not targets:
            sys.exit(f"{args.niche!r} is not one of the {what}s.")
    elif args.all and args.triggers:
        targets = [n for n, r in table.items()
                   if not (r.get("prose_plain") or {}).get("t1_name")]
    elif args.all and args.audience_only:
        targets = [n for n, r in table.items()
                   if not (r.get("prose_plain") or {}).get("audience")]
    elif args.all:
        targets = [n for n, r in table.items() if args.force or not r.get("prose_plain")]
        if args.limit:
            targets = targets[:args.limit]
    else:
        sys.exit("Pass --niche NAME, --all, or --count.")

    print(f"{len(targets)} {what}(s) to rewrite with {MODEL}, {args.workers} at a time.", flush=True)
    written = 0
    done = 0
    started = time.time()

    def work(name):
        """Runs on a worker thread. Only ever READS the table, never writes it."""
        try:
            fn = (triggers_pass if args.triggers else
                  audience_only if args.audience_only else rewrite)
            src = merged(table[name], niches) if (args.subniches and args.triggers) else table[name]
            return name, fn(client, name, src), None
        except Exception as ex:
            return name, None, ex

    # Every write to `data` happens here on the main thread, so the save can never race a worker.
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for name, plain, err in pool.map(work, targets):
            done += 1
            if err:
                print(f"  ! {name}: {err}", file=sys.stderr)
                continue
            if plain:
                table[name].setdefault("prose_plain", {}).update(plain)
                written += 1
            if done % 20 == 0 or done == len(targets):
                save(data)              # a stopped run loses at most the last twenty
                rate = done / max(1e-9, time.time() - started)
                left = (len(targets) - done) / rate if rate else 0
                print(f"  [{done}/{len(targets)}] {written} written, "
                      f"about {left/60:.0f} min left", flush=True)
    save(data)
    print(f"done. {written} {what}(s) rewritten in {(time.time()-started)/60:.0f} min.")
    if FLAGGED:
        print(f"\n{len(FLAGGED)} field(s) came back with a banned word. Worth reading these by eye:")
        for nm, field, words in FLAGGED:
            print(f"  {nm} / {field}: {', '.join(words)}")


if __name__ == "__main__":
    main()
