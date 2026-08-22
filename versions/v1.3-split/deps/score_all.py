"""
Coaching Website Scorecard  —  clean single-pass scorer.

Reads the already-scraped homepage copy for ~10,965 coaching sites and scores
every site 0-10 against the 10-criteria rubric, then a headline score out of 10.

Input : coach_site_research/output/website_copy_dataset_corrected.csv  (the scrape)
Output: scorecard/output/scorecard_all_sites.csv   (every site, every score)
        scorecard/output/benchmarks.csv            (the market numbers)
        scorecard/output/findings.md               (quotable headline findings)

Rules only. No live requests, no API cost. Runs in seconds.
"""

import os
import re
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "output", "website_copy_dataset_corrected.csv")
OUT = os.path.join(HERE, "output")

# ---------------------------------------------------------------- helpers
def s(val):
    """Safe lower-cased string."""
    return str(val).lower().strip() if pd.notna(val) else ""

def present(val):
    v = s(val)
    return v not in ("", "nan", "none", "no", "0")

# ---------------------------------------------------------------- pattern libraries (reused/expanded from old detectors)
WHO_PATTERNS = [
    r"\bfor\s+(coaches|entrepreneurs|executives|leaders|founders|women|men|parents|managers|therapists|consultants|professionals|teams|business owners|creatives|freelancers|solopreneurs|corporate|couples|individuals|moms|dads|students|athletes|nurses|doctors|lawyers|ceos)\b",
    r"i help\s+\w+",
    r"we help\s+\w+",
    r"helping\s+\w+",
    r"\bfor\s+ambitious\s+\w+",
]

WHAT_SPECIFIC = [
    r"\b\d+\s*(days?|weeks?|months?|years?)\b",
    r"[£$€]\s?\d[\d,]*",
    r"\b\d+%\b",
    r"\b(double|triple|10x|2x|3x|5x)\b",
    r"\b(clients?|revenue|income|sales|bookings?|leads?|profit)\b",
    r"\b(anxiety|divorce|weight|burnout|confidence|leadership|relationships?|career|fertility|menopause|sobriety|debt|retirement)\b",
]

VAGUE_ONLY = [
    "best life", "full potential", "authentic", "meaningful", "fulfilling",
    "your journey", "inner peace", "live fully", "be yourself", "show up",
    "greater purpose", "next chapter", "true self", "best self", "thrive",
    "transform your life", "unlock your", "empower",
]

OFFER_KEYWORDS = [
    "program", "programme", "course", "membership", "package", "packages",
    "session", "sessions", "group coaching", "1:1 coaching", "one on one",
    "one-on-one", "workshop", "mastermind", "bootcamp", "academy", "intensive",
    "retreat", "curriculum",
]
STRUCTURE_KEYWORDS = [
    "week", "weeks", "month", "months", "module", "modules", "step", "steps",
    "phase", "phases",
]

LEAD_MAGNET_KEYWORDS = [
    "free guide", "free download", "download", "free training", "free masterclass",
    "masterclass", "free webinar", "webinar", "free ebook", "ebook", "e-book",
    "checklist", "cheat sheet", "cheatsheet", "workbook", "free workshop",
    "quiz", "free assessment", "free consultation", "free call", "free session",
    "free chapter", "free video", "toolkit", "template",
]
# A newsletter is value to the COACH, not the buyer, it shouldn't count as a real lead magnet.
NEWSLETTER_KW = [
    "newsletter", "subscribe", "sign up", "join the list", "mailing list", "updates", "shots of",
    "join my", "stay in touch", "join the community", "weekly email",
]
# A story that speaks to the READER (not just the coach's CV) is what makes it work.
STORY_CONNECT = [
    "i was where you are", "i know what it's like", "been where you", "i struggled with", "if you're",
    "like you", "i get it", "been in your shoes", "i felt", "i remember feeling", "same place you",
    "you might", "you may", "you're not alone", "sound familiar", "do you ", "have you ever",
]

AUTHORITY_KEYWORDS = [
    "as featured in", "as seen in", "as seen on", "featured in", "certified",
    "accredited", "icf", "pcc", "acc", "mcc", "author of", "bestselling",
    "best-selling", "published", "tedx", "ted talk", "forbes", "bbc", "keynote",
    "award", "awards", "award-winning", "years of experience", "phd", "psychologist",
    "board certified", "trusted by", "featured on",
]

STORY_KEYWORDS = [
    "my story", "about me", "my journey", "why i", "i struggled", "i was",
    "meet ", "my name is", "hi, i'm", "hi i'm", "founder", "my mission",
    "my background", "i started", "years ago i", "my own", "i've been",
    "i have been", "personally",
]
# A REAL personal story, not just a name or a 'founder' line. One of these is needed before a page
# counts as telling a story at all.
STRONG_STORY = [
    "my story", "my journey", "i struggled", "i started", "years ago i", "when i", "i was",
    "my mission", "i failed", "i discovered", "i learned", "i've been", "i have been",
    "i remember", "i grew up", "i realised", "i realized", "my name is", "hi, i'm", "hi i'm",
]

# Numbers that are actually PROOF of client results, not just any digit. '20 years' is experience, not proof,
# so it's deliberately excluded.
NUMBER_PROOF = [
    r"\b\d[\d,]*\+?\s*(clients?|students?|customers?|people|women|men|leaders|companies|businesses|reviews?)\b",
    r"\b\d+%\b",
    r"[£$€]\s?\d[\d,]*",
    r"\b\d+(\.\d+)?\s*(star|stars|rating)\b",
]

def any_kw(text, kws):
    return any(k in text for k in kws)

def any_re(text, pats):
    return any(re.search(p, text, re.IGNORECASE) for p in pats)

# ---------------------------------------------------------------- the 10 criteria (each returns 0-10)
# --- STRICT scoring: judge the page the way a COLD visitor sees it (headline first).
#     Generic, could-be-anyone fluff must FAIL. Only concrete, specific language scores high. ---
AUDIENCE_NOUNS = [
    "women", "men", "entrepreneurs", "founders", "executives", "ceos", "ceo", "leaders", "managers",
    "parents", "mums", "moms", "dads", "mothers", "fathers", "couples", "teams", "business owners",
    "professionals", "coaches", "consultants", "therapists", "creatives", "freelancers", "solopreneurs",
    "students", "athletes", "nurses", "doctors", "lawyers", "teachers", "introverts", "expats", "veterans",
    "millennials", "startups", "smes", "teenagers", "teens", "new managers", "small business owners",
    # life-stage + situation audiences (a headline naming these IS naming who it's for)
    "midlife", "mid-life", "midlifers", "40+", "over 40", "over-40", "50+", "over 50", "over-50", "60+",
    "career changers", "career changer", "career change", "career reinventors", "career switchers",
    "empty nesters", "retirees", "retirement", "graduates", "new grads", "first-time managers",
    "high achievers", "high-achievers", "high performers", "caregivers", "carers", "widows", "widowers",
    "immigrants", "single parents", "working mums", "working moms", "new mums", "new moms", "new dads",
]
# EXPAND THE AUDIENCE LIST WITHOUT TOUCHING CODE: add one audience per line to
# scorecard/keywords/audience_extra.txt (lines starting with # are ignored). They merge in on load.
try:
    import os as _os
    _extra = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "keywords", "audience_extra.txt")
    with open(_extra, encoding="utf-8") as _f:
        for _ln in _f:
            _ln = _ln.strip().lower()
            if _ln and not _ln.startswith("#") and _ln not in AUDIENCE_NOUNS:
                AUDIENCE_NOUNS.append(_ln)
except Exception:
    pass
VAGUE_HEADLINE = [
    "energize", "energise", "elevate", "impact", "grow", "growth", "purpose", "potential", "thrive",
    "transform", "transformation", "journey", "empower", "fulfil", "fulfill", "clarity", "confidence",
    "authentic", "aligned", "alignment", "mindset", "breakthrough", "unlock", "inspire", "ignite",
    "flourish", "next level", "level up", "dream life", "limitless", "unstoppable", "shine", "wellbeing",
    "well-being", "balance", "meaning", "vision", "values", "abundance", "freedom", "holistic", "wholeness",
    "presence", "live fully", "your best", "best self", "best life", "reach your", "live with purpose",
]
CONCRETE_RE = [
    r"\b\d+\s*(day|days|week|weeks|month|months|year|years)\b",
    r"[£$€]\s?\d", r"\b\d+%\b", r"\b(double|triple|2x|3x|5x|10x)\b",
    r"\b(anxiety|divorce|weight\s*loss|menopause|fertility|burnout|burn-out|redundan|promotion|debt|"
    r"retirement|adhd|insomnia|sleep|revenue|sales|leads?|clients?|income|profit|imposter|procrastinat|"
    r"public speaking|career change|grief|addiction|sobriety|dating|marriage|perimenopause|fatigue)\b",
]

def _headline(r):
    # What a cold visitor actually reads in the first few seconds.
    return " ".join([s(r.h1), s(r.h2_headings), s(r.page_title)])

def has_audience(t):
    tl = t.lower()
    return any(re.search(r"\b" + re.escape(a) + r"\b", tl) for a in AUDIENCE_NOUNS)

def has_concrete(t):
    return any(re.search(p, t, re.I) for p in CONCRETE_RE)

def vague_dominated(t):
    tl = t.lower()
    return sum(1 for v in VAGUE_HEADLINE if v in tl) >= 2 and not has_concrete(t)

def score_clarity(r):
    """1. 5-second clarity, judged on the headline a COLD visitor sees. Fluff fails."""
    head = _headline(r)
    who = has_audience(head)
    what = has_concrete(head)
    cta = present(r.cta_type) or present(r.cta_text) or s(r.booking_link_present) == "yes"
    score = (4 if who else 0) + (4 if what else 0) + (2 if cta else 0)
    # Only cap for fluff when the headline names NEITHER an audience NOR a concrete problem. Naming one
    # of those means it isn't "could be anyone", even if it also uses some coach words.
    if vague_dominated(head) and not (who or what):
        score = min(score, 3)
    return score

def score_specificity(r):
    """2. Does the headline name a specific person AND a specific problem? Generic = 1.
    Naming an audience or a concrete problem beats the fluff penalty, so 'Reignite Your Career at Midlife'
    (names midlife) scores as specific-ish, not 1."""
    head = _headline(r)
    who = has_audience(head)
    what = has_concrete(head)
    if who and what:
        return 9
    if who or what:
        return 5                     # names an audience OR a concrete problem
    if vague_dominated(head):
        return 1                     # pure fluff, names neither
    return 3                         # neutral: neither clearly specific nor pure fluff

def score_offer(r):
    """3. Is there a real, defined offer, not just 'book a call'? Be conservative."""
    text = " ".join([s(r.h1), s(r.h2_headings), s(r.cta_text), s(r.body_text)[:1500]])
    offer = any_kw(text, OFFER_KEYWORDS)
    structure = any_kw(text, STRUCTURE_KEYWORDS)
    priced = present(r.pricing_mentions)
    if offer and priced and structure:
        return 9
    if offer and priced:
        return 7
    if offer and structure:
        return 3                     # named-ish but no price: a cold buyer still can't tell what they'd pay for
    if offer:
        return 2
    if s(r.booking_link_present) == "yes" or present(r.cta_type):
        return 2                     # only a way to contact, no defined offer
    return 1

def score_proof(r):
    """4. Proof a cold buyer believes: real testimonials, specific outcome numbers, case studies / success stories.
    Generic claims ('great results', '20 years experience') are NOT proof and score nothing. General across all sites."""
    text = " ".join([s(r.body_text), s(r.h2_headings), s(r.testimonial_text)])
    score = 0
    if present(r.testimonial_text):
        score += 5                                       # actual testimonial text on the page
    if any_re(text, NUMBER_PROOF):
        score += 3                                       # specific outcome numbers (%, £, N clients, N stars)
    # a named proof section (case studies / success stories) only counts ALONGSIDE real proof, never on its own,
    # because the section title alone doesn't prove there's anything real inside it.
    if score and any_kw(text, ["case study", "case studies", "success stor", "client results", "before and after"]):
        score += 2
    return min(score, 10)

# A real CALL TO ACTION tells the visitor to DO something — an active step toward becoming a client.
# Note: 'call me/us' counts (it's an instruction); a bare phone number or 'Contact' link does not.
STRONG_CTA = [
    "schedule", "apply", "enquire", "inquire", "get started", "start now", "work with",
    "free consultation", "free call", "discovery call", "strategy call", "consultation",
    # 'book' must mean BOOK A CALL, not a link to the coach's actual book — so require the booking phrasing.
    "book a call", "book now", "book a ", "book your", "book an ", "book online", "book my", "booking",
    "request a", "claim your", "reserve", "let's talk", "let us talk",
    "arrange a", "call me", "call us", "call today", "call now", "speak to", "speak with",
    "get in touch", "reach out", "contact me", "contact us",
]
# Passive contact details are NOT a call to action — a bare phone number, an email, a lone 'Contact' link.
PASSIVE_CONTACT = ["contact", "email", "phone", "mail us", "find us", "location", "directions"]
# A WEAK next step: it keeps them on the page or just collects an email. Not a move toward buying.
WEAK_CTA = [
    "learn more", "read more", "find out more", "subscribe", "sign up", "newsletter", "join our list",
    "join the list", "download", "follow", "watch", "explore", "see more", "view more", "join now",
]

def score_cta(r):
    """5. One clear call to action, judged on how strong the step is — not just that a button exists.
    A stranger needs one obvious next step that moves them toward becoming a client (book a call, apply,
    enquire), not 'subscribe' or 'learn more'. General across every site, not tuned to any one."""
    cta_text = s(r.cta_text)
    has_type = present(r.cta_type)
    booking = s(r.booking_link_present) == "yes"
    if not cta_text and not has_type and not booking:
        return 0
    text = cta_text.lower()
    # count distinct CTA phrases (pipe / comma separated in the scrape)
    parts = [p.strip() for p in re.split(r"[|,/]", cta_text) if p.strip()]
    distinct = len(set(parts))
    strong = booking or any(k in text for k in STRONG_CTA)
    weak = any(k in text for k in WEAK_CTA)
    passive = any(k in text for k in PASSIVE_CONTACT)
    # The criterion is ONE clear call to action. A strong step only counts if it isn't buried in a
    # pile of competing buttons. Six buttons with 'Book' in the mix is not one clear CTA.
    if strong:
        if distinct <= 3:
            return 9                   # one clear, strong step
        if distinct <= 8:
            return 5                   # strong option, but one of several — not a single clear step
        return 2                       # buried in a cluttered mess
    if weak:
        return 3                       # a soft step only (subscribe / learn more)
    if passive or has_type:
        return 2                       # contact details or a stray button — not a real call to action
    return 0

def score_optin(r):
    """6a. OPT-IN FORM: a value exchange for the NOT-ready visitor (a freebie/guide, not just 'join my newsletter').
    MANDATORY, every homepage needs one, so no opt-in at all = 0. Magnet 8, newsletter/bare-optin 3, none 0."""
    text = " ".join([s(r.body_text), s(r.h2_headings), s(r.cta_text)]).lower()
    if any_kw(text, LEAD_MAGNET_KEYWORDS):               # a real freebie that solves a piece of their problem
        return 8
    if any(k in text for k in NEWSLETTER_KW) or s(r.optin_present) == "yes":
        return 3                                         # a bare newsletter/opt-in: value to the coach, not the buyer
    return 0

# A booking / enquiry cue in the copy. Coaches book 'reviews' and 'audits', not just 'calls'.
_BOOK_RE = re.compile(
    r"book (?:a |your |my |an )?(?:free |complimentary )?(?:call|consultation|discovery call|strategy (?:call|session)|"
    r"session|chat|appointment|review|audit|assessment|meeting)|schedule (?:a |your )?(?:free )?(?:call|consultation|"
    r"session|appointment|review|audit)|(?:free|complimentary) (?:consultation|discovery call|review|audit|assessment)", re.I)

def score_booking(r):
    """6b. BOOKING & ENQUIRY: the reach-out/commit step. OPTIONAL, so no booking or enquiry at all = None (N/A, excluded
    from the total). Free booking 9, paid booking 6, contact/enquiry form 4, application 3."""
    text = " ".join([s(r.body_text), s(r.h2_headings), s(r.cta_text)]).lower()
    m = _BOOK_RE.search(text)
    if m:
        win = text[max(0, m.start() - 45): m.end() + 20]
        return 9 if re.search(r"free|complimentary|no obligation|no cost|no charge", win) else 6
    if re.search(r"\bapply (?:below|now|here|to)\b|application form|fill (?:out|in) .{0,20}application", text):
        return 3
    if re.search(r"contact (?:us|me|form)|get in touch|send (?:us|me)? ?a message|enquir", text):
        return 4
    return None                                          # N/A: no booking or enquiry mechanism on the page

# Trust signals, split so we can weigh real credentials and reputation, not just keyword count.
CRED_WORDS = [
    "certified", "accredited", "qualified", "icf", "pcc", "acc", "mcc", "lcsw", "mba", "phd", "msc",
    "bsc", "diploma", "degree", "master practitioner", "nlp", "chartered", "registered", "licensed",
    "board certified", "years of experience", "trained in", "practitioner",
]
MEDIA_WORDS = [
    "as featured in", "as seen in", "as seen on", "as heard on", "featured in", "featured on", "featured",
    "forbes", "bbc", "tedx", "ted talk", "published in", "author of", "co-author", "author", "bestselling",
    "best-selling", "award", "award-winning", "speaker at", "keynote", "keynote speaker", "international speaker",
    "trusted by", "published", "podcast host", "columnist", "expert in", "the times", "guardian", "documentary",
]

# Cheap, gameable self-claims a buyer has learned to ignore. '#1 bestseller' can be an afternoon in a dead
# Amazon sub-category. Small credit only, because they're costless to fake.
SELF_CLAIM = [
    "award-winning", "award winning", "award", "as seen on", "as seen in", "as featured in", "as heard on",
    "featured in", "featured on", "featured", "bestselling", "best-selling", "best selling", "#1 bestseller",
    "number 1 bestseller", "trusted by thousands", "certified", "accredited", "keynote", "international speaker",
    "author of", "expert in", "guru",
]
# Costly, hard-to-fake, OTHER-people-said-it trust. This is what a buyer actually believes.
EXT_REVIEWS = [
    "trustpilot", "google review", "google reviews", "verified review", "verified reviews", "feefo",
    "reviews.io", "checkatrade", "★★★★", "5-star reviews", "5 star reviews", "out of 5", "rated 5",
]

def score_credibility(r):
    """7. Trust, judged the way a switched-on buyer reads it. A signal is only worth anything if it's costly to fake.
    Self-given badges (award-winning, '#1 bestseller') are cheap: on their own they CAN'T beat a 5. Only third-party
    reviews (Google, Facebook, Trustpilot) — other people's word, hard to fake — lift you into a pass.
    General across every site, not tuned to any one."""
    text = " ".join([s(r.h1), s(r.h2_headings), s(r.page_title), s(r.body_text)]).lower()
    self_claim = any_kw(text, SELF_CLAIM)                                   # cheap, gameable
    ext_reviews = any_kw(text, EXT_REVIEWS)                                  # third-party platforms, hard to fake
    contact = any(k in text for k in ["contact", "get in touch", "call us", "email us", "phone", "based in", " address"])
    biz = any(k in text for k in ["companies house", "registered in", "registered office", "vat ", "vat no",
                                  "reg no", "company no", "privacy policy", "terms of", "registered charity"])
    self_given = (2 if self_claim else 0) + (1 if contact else 0) + (2 if biz else 0)
    score = min(self_given, 5)                                              # self-given trust alone caps at 5
    if ext_reviews:
        score = max(score + 5, 7)                                          # real third-party proof = a clear pass
    return min(score, 10)

def score_story(r):
    """8. Story that connects to the CLIENT, not just the coach's CV. Me-only stories score low."""
    text = " ".join([s(r.h1), s(r.h2_headings), s(r.body_text)]).lower()
    strong = any(k in text for k in STRONG_STORY)       # an actual personal story
    weak = any(k in text for k in STORY_KEYWORDS)        # only a mention (a name, a 'founder' line)
    if not strong and not weak:
        return 0                                        # no human/story at all
    if not strong:
        return 2                                        # a passing mention, not a story a visitor can connect with
    connects = any(k in text for k in STORY_CONNECT)    # empathy: speaks to the reader's own experience
    return 8 if connects else 3                         # a connecting story, or one that's all about the coach

def score_pricing(r):
    """9. Pricing posture: shown vs hidden (a finding either way)."""
    return 10 if present(r.pricing_mentions) else 0

def score_technical(r):
    """10. Technical health (from captured data): SSL + content depth.
    Live speed/mobile deferred to an optional freshness pass."""
    score = 0
    if s(r.url).startswith("https"):
        score += 5
    wc = pd.to_numeric(r.word_count, errors="coerce")
    if pd.notna(wc):
        if wc >= 500:
            score += 5
        elif wc >= 300:
            score += 3
        elif wc >= 100:
            score += 1
    return score

CRITERIA = [
    ("clarity_5sec", score_clarity),
    ("specificity", score_specificity),
    ("offer_clarity", score_offer),
    ("proof", score_proof),
    ("clear_cta", score_cta),
    ("opt_in", score_optin),
    ("booking", score_booking),
    ("credibility", score_credibility),
    ("story", score_story),
    ("pricing_shown", score_pricing),
    ("technical_health", score_technical),
]

# Weight the score toward what actually convinces a COLD buyer (persuasion),
# not table-stakes mechanics (has a button, HTTPS). Persuasion counts more.
WEIGHTS = {
    "clarity_5sec": 2.0, "specificity": 2.0, "proof": 1.5, "offer_clarity": 1.5,
    "story": 1.0, "credibility": 1.0, "opt_in": 0.5, "booking": 0.5,   # old lead_capture (1.0) split across the two
    "clear_cta": 0.5, "pricing_shown": 0.2,
    # technical_health is deliberately NOT weighted. Almost every site passes the basics (market avg ~9), so counting
    # it just pads the overall and hands a freebie win. It's still scored + shown (via CRITERIA) and flagged if broken,
    # but the overall score is about how well the page speaks to a buyer, not the plumbing.
}

def weighted_total(scores):
    """Overall 0-100, weighting persuasion above mechanics. A criterion scored None (N/A, e.g. no booking on the page)
    is EXCLUDED from both the weighted sum and the weight denominator, so it neither drags the score down nor pads it."""
    num = wsum = 0.0
    for k, w in WEIGHTS.items():
        v = scores.get(k)
        if v is None:                 # N/A: not applicable to this page, drop it from the average entirely
            continue
        num += v * w; wsum += w
    return round(10 * num / wsum, 1) if wsum else 0.0

# ---------------------------------------------------------------- run
def main():
    print("Loading scrape:", os.path.normpath(SRC))
    df = pd.read_csv(SRC)
    # one row per domain — keep homepage rows, first per domain
    if "page_type" in df.columns:
        home = df[df["page_type"].astype(str).str.lower() == "homepage"].copy()
        if len(home) < 1000:            # fall back if page_type sparse
            home = df.copy()
    else:
        home = df.copy()
    home = home.drop_duplicates(subset="domain", keep="first").reset_index(drop=True)
    print(f"Scoring {len(home):,} unique coaching websites...\n")

    for name, fn in CRITERIA:
        home[name] = home.apply(fn, axis=1)

    crit_cols = [c for c, _ in CRITERIA]
    home["total_100"] = home.apply(lambda r: weighted_total({k: r[k] for k in crit_cols}), axis=1)
    home["score_10"] = (home["total_100"] / 10).round().astype(int)

    def tier(t):
        if t >= 80: return "strong"
        if t >= 60: return "decent"
        if t >= 40: return "weak"
        return "poor"
    home["tier"] = home["total_100"].apply(tier)

    keep = ["domain", "url", "score_10", "total_100", "tier"] + crit_cols
    scored = home[keep].sort_values("total_100", ascending=False).reset_index(drop=True)
    scored.to_csv(os.path.join(OUT, "scorecard_all_sites.csv"), index=False)

    # ---- benchmarks
    rows = []
    N = len(scored)
    rows.append(("sites_scored", N))
    rows.append(("avg_score_100", round(home["total_100"].mean(), 1)))
    rows.append(("avg_score_10", round(home["score_10"].mean(), 1)))
    rows.append(("median_score_100", int(home["total_100"].median())))
    for label, tval in [("top10pct_threshold", 0.9), ("top25pct_threshold", 0.75)]:
        rows.append((label + "_100", round(home["total_100"].quantile(tval), 1)))
    for c in crit_cols:
        rows.append((f"avg_{c}", round(home[c].mean(), 2)))
        rows.append((f"pct_scoring_zero_{c}", round((home[c] == 0).mean() * 100, 1)))
    bench = pd.DataFrame(rows, columns=["metric", "value"])
    bench.to_csv(os.path.join(OUT, "benchmarks.csv"), index=False)

    # ---- findings.md
    pct = lambda mask: round(mask.mean() * 100, 1)
    lines = []
    lines.append("# The Coaching Website Report Card — Headline Findings\n")
    lines.append(f"_Based on {N:,} real coaching websites, scored against 10 criteria._\n")
    lines.append(f"- **Average site scores {home['score_10'].mean():.1f}/10.** Half score {int(home['total_100'].median())}/100 or below.")
    lines.append(f"- **{pct(home['clarity_5sec'] < 7)}% fail the 5-second test** — you can't tell who they help or what you'd get.")
    lines.append(f"- **{pct(home['specificity'] < 5)}% aren't specific** about who they serve or what problem they solve.")
    lines.append(f"- **{pct(home['offer_clarity'] <= 1)}% have no discernible offer** — just a 'book a call' with nothing defined behind it.")
    lines.append(f"- **{pct(home['proof'] == 0)}% show no proof at all** — no testimonials, results, or numbers.")
    lines.append(f"- **{pct(home['opt_in'] == 0)}% have no opt-in** — no freebie, no lead magnet, so the ~97% not ready to buy just leave.")
    lines.append(f"- **{pct(home['credibility'] == 0)}% show no credibility markers** — no certs, media, or authority signals.")
    lines.append(f"- **{pct(home['story'] == 0)}% have no visible story** — no human, no 'why'.")
    lines.append(f"- **{pct(home['pricing_shown'] == 10)}% show any pricing;** {pct(home['pricing_shown'] == 0)}% hide it entirely.")
    lines.append(f"- **{pct(~home['url'].astype(str).str.startswith('https'))}% aren't even on HTTPS** — an instant trust red flag.")
    lines.append(f"\n**Tier split:** " + ", ".join(f"{k}={v}" for k, v in home['tier'].value_counts().items()))
    lines.append("\n## Average score per criterion (0-10)\n")
    for c in crit_cols:
        lines.append(f"- {c}: {home[c].mean():.1f}")
    with open(os.path.join(OUT, "findings.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    # ---- console summary
    print("=" * 60)
    print("DONE. Wrote 3 files to scorecard/output/")
    print("=" * 60)
    print(f"Sites scored      : {N:,}")
    print(f"Average score     : {home['score_10'].mean():.1f}/10  ({home['total_100'].mean():.1f}/100)")
    print(f"Median score      : {int(home['total_100'].median())}/100")
    print(f"Top 10% start at  : {home['total_100'].quantile(0.9):.0f}/100")
    print("\nTier split:")
    for k, v in home["tier"].value_counts().items():
        print(f"  {k:8s}: {v:6,d}  ({v/N*100:.1f}%)")
    print("\nAverage per criterion (0-10):")
    for c in crit_cols:
        print(f"  {c:18s}: {home[c].mean():.1f}")

if __name__ == "__main__":
    main()
