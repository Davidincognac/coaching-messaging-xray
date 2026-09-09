"""Build triggers_data.json for the Buying Triggers page.

Source of truth is the book + Cashvertising research in the Dino project:
  Market-Lenses-117-Niches.xlsx      117 niches, full lens (LF8 / awareness / sophistication / JTBD / Cialdini)
  Market-Lenses-918-Sub-niches.xlsx  918 micro-niches, each either its own lens or inheriting the parent's
  Niche-Intelligence-File.xlsx       the buyer's own words per niche
  Sub-niche-Buyer-Voice-Top100.xlsx  the buyer's own words for the top 100 micro-niches
  Master-Book-Niche-Index.xlsx       2,004 books mapped to niches and micro-niches

Nothing from the coaching-website corpus goes in here. Run it by hand when the research changes:
    python3 build_triggers_data.py
"""
import json, os, collections
import openpyxl

SRC = "/Users/davidpoole/Documents/claude/Projects/Dino"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triggers_data.json")
BOOKS_PER_NICHE = 10          # enough to prove we read them, small enough to ship in the repo


def sheet(fname, sname):
    wb = openpyxl.load_workbook(os.path.join(SRC, fname), read_only=True)
    rows = list(wb[sname].iter_rows(values_only=True))
    wb.close()
    hdr = [str(h).strip() if h else "" for h in rows[0]]
    return [dict(zip(hdr, r)) for r in rows[1:]]


def s(v):
    return str(v).strip() if v is not None else ""


def split_list(v):
    return [p.strip() for p in s(v).split(",") if p.strip()]


# Cashvertising's eight Life Force drivers, plus the secondary wants. Two of them have a comma INSIDE
# the name ("Freedom from fear, pain & danger"), so a plain comma split tears them in half. Match the
# known names first and only split what is left over.
LF_NAMES = [
    "Survival/health/life-extension", "Survival, enjoyment of life, life extension",
    "Enjoyment of food and beverages", "Freedom from fear, pain & danger",
    "Freedom from fear, pain and danger", "Sexual companionship",
    "Comfortable living conditions", "To be superior / win / keep up",
    "Care & protection of loved ones", "Social approval",
    "To be informed / curiosity", "To be informed", "Curiosity",
    "Economy/profit (survival of the business)", "Economy/profit",
    "dependability/quality", "Beauty/style", "Efficiency", "Convenience", "Cleanliness", "Bargains",
]


def split_forces(v):
    """Split an LF8 cell into whole driver names, longest known name first."""
    text = s(v)
    if not text:
        return []
    found = []
    for name in sorted(LF_NAMES, key=len, reverse=True):
        i = text.lower().find(name.lower())
        if i >= 0:
            found.append((i, name))
            text = text[:i] + "\x00" * len(name) + text[i + len(name):]
    for leftover in text.replace("\x00", "").split(","):
        leftover = leftover.strip(" ,")
        if leftover:
            found.append((999, leftover))
    return [n for _, n in sorted(found)]


def voice_phrases(v):
    """The voice cells hold phrases joined by ' | '."""
    return [p.strip() for p in s(v).split("|") if p.strip()]


niches = {}
for r in sheet("Market-Lenses-117-Niches.xlsx", "Market lenses"):
    n = s(r["Niche"])
    if not n:
        continue
    niches[n] = {
        "niche": n,
        "lf8_primary": split_forces(r["LF8 primary"]),
        "lf8_secondary": split_forces(r["LF8 secondary"]),
        "lf8_evidence": s(r["LF8 evidence"]),
        "awareness": s(r["Awareness"]),
        "lead_with": s(r["Lead with"]),
        "sophistication": s(r["Sophistication"]),
        "implication": s(r["Implication"]),
        "jtbd_job": s(r["JTBD job"]),
        "push": s(r["Push"]),
        "pull": s(r["Pull"]),
        "anxiety": s(r["Anxiety"]),
        "habit": s(r["Habit"]),
        "cialdini": split_list(r["Cialdini levers"]),
        "cialdini_why": s(r["Why"]),
        "confidence": s(r["Confidence"]).split("—")[0].strip().lower(),
        "voice": {}, "books": [],
    }

subs = {}
for r in sheet("Market-Lenses-918-Sub-niches.xlsx", "Sub-niche lenses"):
    n = s(r["Sub-niche"])
    if not n:
        continue
    subs[n] = {
        "subniche": n,
        "parent": s(r["Parent niche"]),
        "diverges": s(r["Diverges?"]).upper() == "YES",
        "lf8": split_forces(r["LF8"]),
        "awareness": s(r["Awareness"]),
        "sophistication": s(r["Sophistication"]),
        "jtbd_job": s(r["JTBD job"]),
        "cialdini": split_list(r["Cialdini"]),
        "note": s(r["Divergence note"]),
        "voice": {}, "books": [],
    }

VOICE_FIELDS = ["Pain words", "Desire words", "Blame", "Already tried", "Trigger",
                "Insider jargon", "Coach language"]
KEY = {"Pain words": "pain", "Desire words": "desire", "Blame": "blame",
       "Already tried": "tried", "Trigger": "trigger", "Insider jargon": "jargon",
       "Coach language": "coach_language"}

for r in sheet("Niche-Intelligence-File.xlsx", "Niche voice"):
    n = s(r["Niche"])
    if n in niches:
        niches[n]["voice"] = {KEY[f]: voice_phrases(r.get(f)) for f in VOICE_FIELDS}
        niches[n]["buyer_quotes"] = int(r.get("Buyer #") or 0)

for r in sheet("Sub-niche-Buyer-Voice-Top100.xlsx", "Sub-niche voice"):
    n = s(r["Sub-niche"])
    if n in subs:
        subs[n]["voice"] = {KEY[f]: voice_phrases(r.get(f)) for f in VOICE_FIELDS}
        subs[n]["buyer_quotes"] = int(r.get("Buyer #") or 0)

# Books: keep a handful per niche so the report can name real titles the market already buys.
by_niche = collections.defaultdict(list)
for r in sheet("Master-Book-Niche-Index.xlsx", "By niche"):
    by_niche[s(r["Niche"])].append({"title": s(r["Book"]), "author": s(r["Author"])})
by_sub = collections.defaultdict(list)
for r in sheet("Master-Book-Niche-Index.xlsx", "By sub-niche"):
    by_sub[s(r["Sub-niche"])].append({"title": s(r["Book"]), "author": s(r["Author"])})

for n, rec in niches.items():
    rec["books"] = by_niche.get(n, [])[:BOOKS_PER_NICHE]
    rec["book_count"] = len(by_niche.get(n, []))
for n, rec in subs.items():
    rec["books"] = by_sub.get(n, [])[:BOOKS_PER_NICHE]
    rec["book_count"] = len(by_sub.get(n, []))

# A rebuild must never throw away the plain-English rewrites. They cost API calls to make and they
# are checked by hand, so carry them across from the existing file.
if os.path.exists(OUT):
    try:
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f)
        carried = 0
        for bucket, table in (("niches", niches), ("subniches", subs)):
            for name, old_rec in prev.get(bucket, {}).items():
                if old_rec.get("prose_plain") and name in table:
                    table[name]["prose_plain"] = old_rec["prose_plain"]
                    carried += 1
        print(f"carried {carried} plain-English rewrite(s) across from the previous build")
    except Exception as ex:
        print(f"WARNING: could not read the previous build ({ex}). Rewrites were NOT carried across.")

data = {
    "niches": niches,
    "subniches": subs,
    "totals": {
        "niches": len(niches),
        "subniches": len(subs),
        "books": 2004,
        "buyer_quotes": sum(v.get("buyer_quotes", 0) for v in niches.values()),
    },
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
print(f"wrote {OUT}  {os.path.getsize(OUT)/1024:.0f} KB")
print(f"  {len(niches)} niches, {len(subs)} micro-niches, "
      f"{sum(1 for v in subs.values() if v['diverges'])} with their own lens")
