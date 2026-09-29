"""Every figure the blog asserts, recomputed from source and checked.

A wrong number in a post cannot be taken back, because somebody has already read it. So no
figure goes into a post on my word. It comes from here, and this runs again whenever the
corpus is rescored or a post is edited.

    python3 check_post_numbers.py

Covers the figures used by the coaching-websites posts and the getting-clients posts. Sources
are both ours: the scorecard CSV in coach_site_research, and triggers_data.json.
"""
import collections, csv, json, os, statistics, sys

# coach_site_research is a sibling of this repo, so the corpus is found without a machine path.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
rows = list(csv.DictReader(open(os.path.join(
    ROOT, "coach_site_research/scorecard/output/scorecard_FULL.csv"),
    encoding="utf-8", errors="replace")))
d = json.load(open(os.path.join(ROOT, "coach_audit_app/triggers_data.json")))
SUB, NI, TOT = d["subniches"], d["niches"], d["totals"]
N, S = len(rows), len(SUB)
f = lambda r, c: float(r[c])
share = lambda test: round(100 * sum(1 for r in rows if test(r)) / N, 1)
mean = lambda c, rs=None: round(statistics.mean(f(r, c) for r in (rs or rows)), 2)
subshare = lambda test: round(100 * sum(1 for v in SUB.values() if test(v)) / S, 1)
cial = lambda name: subshare(lambda v: any(name.lower() in (x or "").lower() for x in v.get("cialdini") or []))


def aware(v):
    s = (v.get("awareness") or "").lower()
    for k, o in (("unaware", "Unaware"), ("problem", "Problem-aware"), ("solution", "Solution-aware"),
                 ("product", "Product-aware"), ("most", "Most-aware")):
        if s.startswith(k):
            return o
    return "?"


def soph(v):
    s = str(v.get("sophistication") or "").strip()
    return s[0] if s[:1].isdigit() else "?"


good = [r for r in rows if r["tier"] in ("strong", "decent")]
poor = [r for r in rows if r["tier"] == "poor"]
parents = collections.defaultdict(set)
for v in SUB.values():
    if v.get("parent") in NI:
        parents[v["parent"]].add(aware(v))

CLAIMS = [
    ("10,954 live sites scored",                N, 10954),
    ("918 markets mapped",                      S, 918),
    ("117 niches",                              len(NI), 117),
    ("2,004 books",                             TOT["books"], 2004),
    ("1,547 buyer quotes",                      TOT["buyer_quotes"], 1547),
    ("market average out of 10 = 3.65",         mean("score_10"), 3.65),
    ("94.3% have a clear next step",            share(lambda r: f(r, "clear_cta") > 0), 94.3),
    ("66.5% show no proof at all",              share(lambda r: f(r, "proof") == 0), 66.5),
    ("82.3% show no price at all",              share(lambda r: f(r, "pricing_shown") == 0), 82.3),
    ("33.8% nothing human on the page",         share(lambda r: f(r, "story") == 0), 33.8),
    # The five-second read is scored 0/2/4/6/8/10 and 7 or better is the pass, so "under 7" and
    # "under 8" are the same set. Posts say 86% fail; this is where that comes from.
    ("85.7% fail the five-second read",          share(lambda r: f(r, "clarity_5sec") < 7), 85.7),
    ("50.0% score 4 or lower on it",             share(lambda r: f(r, "clarity_5sec") < 5), 50.0),
    ("61.2% next step but no proof",            share(lambda r: f(r, "clear_cta") > 0 and f(r, "proof") == 0), 61.2),
    ("20.4% next step, no proof/price/story",   share(lambda r: f(r, "clear_cta") > 0 and f(r, "proof") == 0
                                                       and f(r, "pricing_shown") == 0 and f(r, "story") == 0), 20.4),
    ("18.2% next step, no lead capture",        share(lambda r: f(r, "clear_cta") > 0 and f(r, "lead_capture") == 0), 18.2),
    ("47.9% below the market average",          share(lambda r: f(r, "score_10") < 3.65), 47.9),
    ("22.7% score under 3",                     share(lambda r: f(r, "score_10") < 3), 22.7),
    ("14.3% understandable in five seconds",    share(lambda r: f(r, "clarity_5sec") >= 8), 14.3),
    ("proof: market mean 1.51",                 mean("proof"), 1.51),
    ("proof: good tier mean 4.56",              mean("proof", good), 4.56),
    ("proof: poor tier mean 0.78",              mean("proof", poor), 0.78),
    ("good tier n = 646",                       len(good), 646),
    ("poor tier n = 6,820",                     len(poor), 6820),
    ("89.5% of good sites show proof",          round(100*sum(1 for r in good if f(r, "proof") > 0)/len(good), 1), 89.5),
    ("18.5% of poor sites show proof",          round(100*sum(1 for r in poor if f(r, "proof") > 0)/len(poor), 1), 18.5),
    ("credibility market mean 2.68",            mean("credibility"), 2.68),
    ("credibility gap 1.43",                    round(mean("credibility", good) - mean("credibility", poor), 2), 1.43),
    ("proof gap 3.78",                          round(mean("proof", good) - mean("proof", poor), 2), 3.78),
    ("clarity gap 6.33",                        round(mean("clarity_5sec", good) - mean("clarity_5sec", poor), 2), 6.33),
    ("specificity gap 5.03",                    round(mean("specificity", good) - mean("specificity", poor), 2), 5.03),
    ("clarity good 9.25",                       mean("clarity_5sec", good), 9.25),
    ("clarity poor 2.92",                       mean("clarity_5sec", poor), 2.92),
    ("social proof 92.9% of markets",           cial("social proof"), 92.9),
    ("authority 87.9%",                         cial("authority"), 87.9),
    ("unity/belonging 43.5%",                   cial("unity"), 43.5),
    ("liking 38.1%",                            cial("liking"), 38.1),
    ("commitment/consistency 27.5%",            cial("commitment"), 27.5),
    ("scarcity 4.4%",                           cial("scarcity"), 4.4),
    ("reciprocity 3.4%",                        cial("reciprocity"), 3.4),
    ("relief from fear/pain 49.9%",             subshare(lambda v: any("freedom from fear" in (x or "").lower()
                                                                       for x in v.get("lf8") or [])), 49.9),
    ("unaware 1.3%",                            subshare(lambda v: aware(v) == "Unaware"), 1.3),
    ("problem-aware 38.9%",                     subshare(lambda v: aware(v) == "Problem-aware"), 38.9),
    ("solution-aware 52.2%",                    subshare(lambda v: aware(v) == "Solution-aware"), 52.2),
    ("not shopping yet 40.2%",                  subshare(lambda v: aware(v) in ("Unaware", "Problem-aware")), 40.2),
    ("sophistication 4 or 5 = 47.7%",           subshare(lambda v: soph(v) in ("4", "5")), 47.7),
    ("79.8% of subniches diverge from parent",  subshare(lambda v: bool(v.get("diverges"))), 79.8),
    ("30.6% at a different awareness stage",    subshare(lambda v: v.get("parent") in NI
                                                         and aware(v) != aware(NI[v["parent"]])), 30.6),
    ("90.6% of niches hold >1 awareness stage", round(100*sum(1 for s in parents.values() if len(s) > 1)/len(parents), 1), 90.6),
    # 12,294 domains attempted, 10,954 scored. 1,156 would not load at all and 184 loaded
    # with nothing readable, which is 1,340 missing rather than 1,156. Four posts said 1,156
    # and the subtraction did not work; this is here so it cannot drift back.
    ("1,340 attempted but not scored",           12294 - N, 1340),
]

# The weights the /methodology page publishes. They are not written down anywhere that still
# runs: the corpus was scored by versions/v1.0/deps/score_all.py and the research repo's own
# scorer has since moved on. These reproduce all 10,954 published totals exactly, which is the
# only proof available that the published table is the one that made the numbers.
CORPUS_WEIGHTS = {
    "clarity_5sec": 2.0, "specificity": 2.0, "offer_clarity": 1.5, "proof": 1.5,
    "lead_capture": 1.0, "credibility": 1.0, "story": 1.0,
    "clear_cta": 0.5, "technical_health": 0.3, "pricing_shown": 0.2,
}
_wsum = sum(CORPUS_WEIGHTS.values())
_off = sum(1 for r in rows
           if abs(round(10 * sum(CORPUS_WEIGHTS[k] * f(r, k) for k in CORPUS_WEIGHTS) / _wsum, 1)
                  - float(r["total_100"])) > 0.051)
CLAIMS += [
    ("published weights sum to 11",              _wsum, 11.0),
    ("weights reproduce every published total",  _off, 0),
    ("13 strong",  sum(1 for r in rows if r["tier"] == "strong"), 13),
    ("633 decent", sum(1 for r in rows if r["tier"] == "decent"), 633),
    ("3,488 weak", sum(1 for r in rows if r["tier"] == "weak"), 3488),
] + [(f"per-criterion mean {c}", mean(c), v) for c, v in (
    ("clarity_5sec", 4.49), ("specificity", 4.38), ("offer_clarity", 2.89), ("proof", 1.51),
    ("lead_capture", 4.64), ("credibility", 2.68), ("story", 2.54), ("clear_cta", 5.60),
    ("technical_health", 9.03), ("pricing_shown", 1.77))]

# The third dataset, and the one the content plan said did not exist: 11,377 coaches'
# LinkedIn headlines, scored the same way a homepage is. It is what cluster 4 stands on.
_li = list(csv.DictReader(open(os.path.join(
    ROOT, "coach_site_research/linkedin/output/headline_scores.csv"),
    encoding="utf-8", errors="replace")))
_LN = len(_li)
_T = lambda r, f: str(r.get(f, "")).strip().lower() == "true"
_lip = lambda f: round(100 * sum(1 for r in _li if _T(r, f)) / _LN, 1)
_lsc = [float(r["headline_score"]) for r in _li]
_titles = collections.Counter((r["Title"] or "").strip() for r in _li)
CLAIMS += [
    ("11,377 LinkedIn headlines",               _LN, 11377),
    ("headline mean 2.56 out of 10",            round(statistics.mean(_lsc), 2), 2.56),
    ("70.1% score 3 or less",                   round(100*sum(1 for x in _lsc if x <= 3)/_LN, 1), 70.1),
    ("2.2% score 8 or more",                    round(100*sum(1 for x in _lsc if x >= 8)/_LN, 1), 2.2),
    ("247 coaches score 8 or more",             sum(1 for x in _lsc if x >= 8), 247),
    ("32.5% are a bare role word",              _lip("bare"), 32.5),
    ("68.2% name a niche",                      _lip("niche"), 68.2),
    ("25.2% name an audience",                  _lip("audience"), 25.2),
    ("7.5% state an outcome",                   _lip("outcome"), 7.5),
    ("6.9% show a credential",                  _lip("credential"), 6.9),
    ("33.2% are multi-part",                    _lip("structured"), 33.2),
    ("4.3% name both audience and outcome",
     round(100*sum(1 for r in _li if _T(r, "audience") and _T(r, "outcome"))/_LN, 1), 4.3),
    ("420 share the headline Executive Coach",  _titles["Executive Coach"], 420),
    ("364 are just Coach",                      _titles["Coach"], 364),
    ("41.5% share a headline with somebody",
     round(100*sum(n for t, n in _titles.items() if n > 1 and t)/_LN, 1), 41.5),
]

bad = 0
for label, got, want in CLAIMS:
    ok = got == want
    if not ok:
        bad += 1
    print(f"{'ok ' if ok else 'BAD'}  {label:44} got {got!r}" + ("" if ok else f"  want {want!r}"))
print(f"\n{len(CLAIMS)} claims, {bad} wrong.")
sys.exit(1 if bad else 0)
