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
    ("50.0% score under 5 on five-second read", share(lambda r: f(r, "clarity_5sec") < 5), 50.0),
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

bad = 0
for label, got, want in CLAIMS:
    ok = got == want
    if not ok:
        bad += 1
    print(f"{'ok ' if ok else 'BAD'}  {label:44} got {got!r}" + ("" if ok else f"  want {want!r}"))
print(f"\n{len(CLAIMS)} claims, {bad} wrong.")
sys.exit(1 if bad else 0)
