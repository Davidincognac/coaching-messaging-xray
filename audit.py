"""
Coaching Website Audit, the free lead-magnet engine.

Give it one URL. It:
  1. Scrapes the homepage        (reuses the validated research scraper)
  2. Scores it on 10 criteria    (reuses the validated research scorer)
  3. Benchmarks it vs 10,954 real coaching sites
  4. Writes a specific, named diagnosis in David's voice   (Claude, optional)

The score + benchmark ALWAYS work (pure Python, free, no API key).
The AI critique switches on automatically once ANTHROPIC_API_KEY is set;
until then it falls back to a solid rule-based diagnosis, so the endpoint
NEVER returns nothing to a prospect.

CLI test:  python3 audit.py https://somecoach.com
"""

import os
import re
import sys
import csv
import json
import types
import bisect
import threading
import datetime as _dt

# --- load local secrets (ANTHROPIC_API_KEY, AUDIT_MODEL) from a private .env if not already in the env ---
_ENVF = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENVF):
    for _line in open(_ENVF, encoding="utf-8"):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# --- reuse the validated research code (scraper + scorer) ---
HERE = os.path.dirname(os.path.abspath(__file__))
SCORECARD = os.path.normpath(os.path.join(HERE, "..", "coach_site_research", "scorecard"))
sys.path.insert(0, SCORECARD)
import scrape_missing as sm      # fetch() + extract()
import score_all as S           # CRITERIA + helpers

# --- model for the audit: Sonnet 4.6. Haiku was cheaper but scored the SAME page differently every run (clarity
#     6/6/9, proof 4/6/7); Sonnet holds a steady, sensible opinion. ~3c/audit. Bump to claude-opus-5 for the paid
#     Intelligence File. Override via env AUDIT_MODEL. ---
AUDIT_MODEL = os.getenv("AUDIT_MODEL", "claude-sonnet-4-6")

# --- market benchmarks, from our full run of 10,954 live sites (strict scoring) ---
MARKET_AVG_10 = 3.7
TOP10_10 = 5.6
BENCH = {
    "clarity_5sec": 4.5, "specificity": 4.4, "symptom_resonance": 3.2,
    "proof_cred": 2.6, "offer_relevance": 3.0, "intent_flow": 3.8,
    "perceived_friction": 4.5, "risk_reversal": 2.5,
}
LABELS = {
    "clarity_5sec": "Fast Grab (5-Second Hook)",
    "specificity": "Laser Target (The Who)",
    "symptom_resonance": "Mind Reading (The Problem)",
    "proof_cred": "Hard Proof (The Trust)",
    "offer_relevance": "The Perfect Cure (The Offer)",
    "intent_flow": "One Clear Path (The Clarity)",
    "perceived_friction": "Easy Start (The Effort)",
    "risk_reversal": "Safety Net (The Shield)",
}
# A short 'what we check' line shown under each bar, so a coach knows EXACTLY what each score measures and never
# confuses two that sound alike. Carries the scope David asked for.
DEFINITIONS = {
    "clarity_5sec": "In 5 seconds, does the right person see this is for them?",
    "specificity": "Is the page focused on ONE clear audience and ONE clear problem?",
    "symptom_resonance": "Does the copy describe the buyer's daily pain in their own words — raw and situational — not generic coaching platitudes?",
    "proof_cred": "Does a cold buyer get real, costly-to-fake reasons to believe you can deliver?",
    "offer_relevance": "Is there one clear, defined thing to buy or a vivid outcome the buyer can picture?",
    "intent_flow": "Is the whole page aimed at ONE next step, or scattered across competing asks?",
    "perceived_friction": "How much psychological effort does a cold visitor need to take the next step?",
    "risk_reversal": "Does anything on the page lower the risk of saying yes — a guarantee, a safety net, or a clear trial option?",
}
# The order the bars READ in (grouped by theme, not sorted by gap).
DISPLAY_CRIT = [
    "clarity_5sec",
    "specificity",
    "symptom_resonance",
    "proof_cred",
    "offer_relevance",
    "intent_flow",
    "perceived_friction",
    "risk_reversal",
]

# --- real percentile curve, loaded from the 10,954-site results (for "better than X%") ---
_PCTL = []
try:
    with open(os.path.join(SCORECARD, "output", "scorecard_FULL.csv")) as _f:
        _PCTL = sorted(int(float(r["total_100"])) for r in csv.DictReader(_f))
except Exception:
    _PCTL = []

def percentile(total_100):
    """% of real coaching sites this site beats."""
    if _PCTL:
        return round(bisect.bisect_left(_PCTL, total_100) / len(_PCTL) * 100)
    pts = [(0, 0), (40, 19), (54, 50), (60, 64), (63, 75), (72, 90), (80, 97), (100, 100)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if total_100 <= x2:
            return round(y1 + (y2 - y1) * (total_100 - x1) / max(x2 - x1, 1))
    return 100

# --- living count of UNIQUE coaching websites read. Seeds from the 10,954 corpus, grows on new domains only. ---
_DOMAINS_FILE = os.path.join(HERE, "analysed_domains.txt")   # only stores domains NEW since the corpus
_domain_lock = threading.Lock()
_domain_set = None

def _load_domains():
    global _domain_set
    if _domain_set is not None:
        return _domain_set
    s = set()
    try:  # seed from the benchmark corpus (the 10,954)
        with open(os.path.join(SCORECARD, "output", "scorecard_FULL.csv")) as f:
            for row in csv.DictReader(f):
                d = str(row.get("domain", "")).strip().lower()
                if d:
                    s.add(d)
    except Exception:
        pass
    # Read the live-audit domains file; deduplicate it in place if it has accumulated duplicate lines
    # (can happen after crashes or concurrent writes) so we never append a domain that's already there.
    file_lines = []
    try:
        with open(_DOMAINS_FILE, encoding="utf-8") as f:
            file_lines = [ln.strip().lower() for ln in f if ln.strip()]
    except FileNotFoundError:
        pass
    unique_lines = list(dict.fromkeys(file_lines))   # preserves insertion order, removes duplicates
    if len(unique_lines) < len(file_lines):          # file had duplicates — rewrite it clean
        try:
            with open(_DOMAINS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(unique_lines) + ("\n" if unique_lines else ""))
        except Exception:
            pass
    for d in unique_lines:
        s.add(d)
    _domain_set = s
    return s

def record_domain(domain):
    """Add a domain to the corpus if it's genuinely new (re-checks don't count)."""
    d = (domain or "").strip().lower()
    if not d:
        return
    with _domain_lock:
        s = _load_domains()
        if d not in s:
            s.add(d)
            try:
                with open(_DOMAINS_FILE, "a") as f:
                    f.write(d + "\n")
            except Exception:
                pass

def websites_read_count():
    with _domain_lock:
        return 11008 + len(_load_domains())

# ---------------------------------------------------------------- evidence ("we actually read your site")
def _clean(x):
    x = str(x or "").strip()
    return "" if x.lower() in ("", "nan", "none") else x

def _tidy_headline(t):
    t = _clean(t)
    t = re.sub(r"\s*[-|–,]\s*(home|homepage|welcome)\s*$", "", t, flags=re.I)
    t = re.sub(r"^\s*(home|homepage|welcome)\s*[-|–,]\s*", "", t, flags=re.I)
    t = re.sub(r"\s+([,\.!?;:])", r"\1", t)   # "word ," -> "word,"
    return t.strip()

# markers we're confident actually indicate a testimonials/reviews section (avoids false "none found")
TESTIMONIAL_MARKERS = [
    "testimonial", "what our clients say", "what clients say", "what our customers", "success stor",
    "client stories", "kind words", "5-star", "5 star", "★", "⭐", "google review", "trustpilot",
    "here's what", "raving fans", "reviews",
]

# The coach's actual area, so notes can say "leadership coaching" not a generic "coaching" — proof we read it.
NICHE_MAP = [
    ("leadership", "leadership"), ("leader", "leadership"), ("executive", "executive"), ("business coach", "business"),
    ("career", "career"), ("life coach", "life"), ("wellness", "wellness"), ("well-being", "wellbeing"),
    ("wellbeing", "wellbeing"), ("mindset", "mindset"), ("relationship", "relationship"),
    ("communication", "communication"), ("confidence", "confidence"), ("fitness", "fitness"),
    ("nutrition", "nutrition"), ("spiritual", "spiritual"), ("financial", "financial"),
    ("parenting", "parenting"), ("weight loss", "weight-loss"), ("divorce", "divorce"),
    ("public speaking", "public-speaking"), ("productivity", "productivity"), ("burnout", "burnout"),
    ("sales ", "sales"), ("health", "health"),
    # Specific niches the corpus names in plain language, added so they get their real label instead of null or a
    # too-broad 'wellness'. Synonyms share a label so they dedupe to one area (no spurious 2-family None). Kept
    # unambiguous on purpose, a stray keyword must not be able to mislabel a coach.
    ("grief", "grief"), ("bereavement", "grief"),
    ("trauma", "trauma"), ("ptsd", "trauma"),
    ("anxiety", "anxiety"),
    ("adhd", "neurodivergent"), ("neurodivergen", "neurodivergent"), ("neurodiversity", "neurodivergent"),
    ("autism", "neurodivergent"), ("autistic", "neurodivergent"),
    ("addiction", "recovery"), ("sobriety", "recovery"),
    ("menopause", "menopause"),
    ("fertility", "fertility"),
    ("maternity", "motherhood"), ("motherhood", "motherhood"), ("postpartum", "motherhood"),
    ("postnatal", "motherhood"), ("matrescence", "motherhood"),
    ("chiropract", "chiropractic"),
    ("dating", "dating"),
]
# A client/logo/"worked with" section — a start, but logos alone don't tell a stranger what changed for them.
LOGO_PHRASES = [
    "trusted by", "as seen in", "as seen on", "as featured in", "featured in", "our clients",
    "clients include", "brands i", "brands we", "companies i", "companies we", "in partnership with",
    "worked with", "clients we", "who we work with", "our partners", "some of our clients",
]

# Related niches collapse into ONE family, so 'leadership + executive' reads as one focus, not two.
_NICHE_FAMILY = {
    "leadership": "leadership", "executive": "leadership", "business": "leadership",
    "health": "health", "wellness": "health", "wellbeing": "health", "fitness": "health",
    "nutrition": "health", "weight-loss": "health", "burnout": "health",
    "relationship": "relationship", "divorce": "relationship",
    "confidence": "mindset", "mindset": "mindset",
    "financial": "money", "sales": "money",
}

def detect_niche(focus, full=None):
    """Label the coach's niche ONLY from their IDENTITY text (headline/title/subheadings), and only when it's
    unambiguous, a WRONG label ('you're a career coach' to a compulsion coach who mentions 'work' once) is worse
    than a generic fallback. An incidental niche word buried in the body must NOT set the label."""
    f = (focus or "").lower()
    # Mine an EXPLICIT self-identification from the body ('I'm a certified life coach', 'certified divorce coach').
    # A stated title is genuine IDENTITY, not an incidental mention. We require the first-person / 'certified'
    # framing, so a stray niche word buried in body copy (the false-positive this guards against) can't set the label.
    self_id = ""
    if full:
        low = full.lower()
        for pat in (r"(?:i'?m|i am|we are|she'?s|he'?s|as)\s+(?:a|an|your)?\s*([a-z][a-z\s,'/-]{0,45}?coach(?:ing)?)\b",
                    r"(?:certified|qualified|accredited|registered|professional|trained)\s+([a-z][a-z\s,'/-]{0,35}?coach(?:ing)?)\b"):
            for m in re.finditer(pat, low):
                self_id += " " + m.group(1)
        f += " " + self_id
    # An EXPLICIT self-stated coach TITLE is AUTHORITATIVE: 'certified divorce coach' means divorce, even when the
    # page also lists co-parenting or other related services (which would otherwise collapse to a 2-family None).
    # If the stated title names exactly ONE niche, take it straight.
    if self_id:
        title_areas = list(dict.fromkeys(label for kw, label in NICHE_MAP if kw in self_id))
        if len(title_areas) == 1:
            return title_areas[0]
    if "life coach" in f or "life coaching" in f:
        return "life"
    areas = list(dict.fromkeys(label for kw, label in NICHE_MAP if kw in f))
    if not areas:
        return None                                     # identity names no niche: don't guess from body mentions
    fams = list(dict.fromkeys(_NICHE_FAMILY.get(a, a) for a in areas))
    if len(fams) >= 2:
        return None                                     # identity spans unrelated niches = broad coach
    return areas[0]                                     # one clear niche family -> label it

_NEWS_SIGNUP_RE = re.compile(
    r"(subscribe to (?:my|our|the) newsletter|join (?:my|our|the) (?:mailing list|newsletter|list)|"
    r"sign up (?:for|to) (?:my|our|the) (?:newsletter|updates|mailing list|list)|newsletter sign[- ]?up)", re.I)
# A real lead MAGNET needs a free resource, not just the word 'ebook' sitting in a story or a nav menu. Require
# either a "free <thing>" phrase, or a download/get-your cue right next to the thing. ('free call/consultation/
# session' is a booking CTA, not a magnet, so those nouns are left out here.)
_MAGNET_NOUN = (r"(guide|download|training|masterclass|webinar|ebook|e-book|workshop|assessment|checklist|"
                r"cheat ?sheet|workbook|toolkit|quiz|template|worksheet|pdf|free video|free chapter)")
_MAGNET_RE = re.compile(
    r"(free\s+" + _MAGNET_NOUN + r")"
    r"|((?:download|get your|get the|get my|grab|claim your|access your|get instant access to)\s+"
    r"(?:my |your |the |our )?(?:free )?" + _MAGNET_NOUN + r")", re.I)
# A CUSTOM-NAMED lead magnet: 'Get my Permission Slips', 'Grab your Clarity Kit', 'Download the Money Map'. The
# freebie's NAME isn't a standard noun, so _MAGNET_RE misses it, we recognise it by the get/grab/download cue + an
# actual opt-in form. Booking-type objects ('get my free call') are excluded below so this doesn't over-fire.
_MAGNET_CTA_RE = re.compile(
    r"\b(?:get|grab|download|send me|i want|claim|snag|yes[,! ]+send me)\s+(?:my|your|the|our)\s+"
    r"(free\s+)?([A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*){0,3})", re.I)
_NOT_MAGNET_OBJ = re.compile(
    r"^(?:call|consultation|session|sessions|spot|spots|seat|seats|place|places|appointment|quote|demo|"
    r"started|touch|results?|coaching|coached|discovery|audit|price|prices|copy|slice|way|hands|head)$", re.I)
# A branded freebie is Title Case ('Permission Slips') OR names a resource type. Stops 'get your messy ...' etc.
_MAGNET_RESOURCE = re.compile(
    r"\b(?:kit|guide|map|pack|bundle|checklist|planner|workbook|worksheet|tracker|framework|blueprint|roadmap|"
    r"toolkit|template|cheat ?sheet|playbook|starter|formula|system|method|masterclass|challenge|series|slips|"
    r"scripts?|course|ebook|report|handbook|journal|manual|guide|swipe|prompts?|hacks?|secrets?)\b", re.I)

# An email opt-in with a VALUE HOOK ('free weekly tips', 'four tips to transform your life') even without the word
# 'newsletter'. We were scoring these 0 by missing them.
_OPTIN_VALUE_RE = re.compile(
    r"free weekly|weekly (?:tips|updates|emails|coaching|newsletter|insights|lessons)|"
    r"(?:get|grab|receive|sign up for) (?:my |your |the |our )?free|"
    r"free (?:tips|training|updates|series|course|video|lessons|coaching)|"
    # A free NAMED resource offered for an email ('complimentary 10 Steps to Transform Your Life Program'): the word
    # complimentary/free followed within a few words by a resource noun. Not 'complimentary consultation' (a booking).
    r"(?:complimentary|free) (?:\w+ ){0,4}(?:e-?book|program|programme|masterclass|training|challenge|workbook|"
    r"checklist|toolkit|guide|course|series|mini-?course|cheat ?sheet|steps|blueprint|roadmap|kit|audio|video)\b|"
    r"\d+ (?:steps|ways|tips|keys|secrets) to (?:transform|change|improve|fix|build)", re.I)

# A crypto-token / crowdfunding / 'collect tips and get discounts' / invest pitch is NOT an email opt-in, even when
# it happens to contain 'free tips' or 'discounts'. These words disqualify a value-hook sentence from being read as
# email capture (the visitor is being sold a token or asked to tip, not to leave their address).
_NOT_OPTIN_RE = re.compile(
    r"\btoken\b|crypto|cryptocurrency|crowdfund|blockchain|\binvest\b|high-potential asset|"
    r"collect (?:commission-free )?tips|get discounts", re.I)

# A "free" resource that is actually LOCKED behind a paid membership / purchase is NOT lead capture: a cold visitor
# who isn't ready to pay can't get it, and it may not exist ungated at all. We spot the free-resource word followed
# in the SAME sentence by a gating phrase ('free guides ... with platform membership').
_GATED_FREEBIE_RE = re.compile(
    r"free[^.]{0,70}?(?:guide|guides|download|downloadable|pdf|pdfs|resource|resources|content|ebook|e-book)"
    r"[^.]{0,70}?(?:with|through|via|requires?|only (?:available )?with|once you (?:join|subscribe|become))\s+"
    r"(?:our |a |the |platform |paid )*(?:member|membership|subscri|premium|paid plan)", re.I)

# An EMBEDDED email-capture form from a known provider (HubSpot, Mailchimp, ConvertKit/Kit, MailerLite, Klaviyo,
# Flodesk, etc.). The fields sit INSIDE the provider's <iframe>/widget, so the main-DOM input scan (optin_present)
# can't see them and we'd score a real opt-in 0. The embed's markers in the page HTML are the tell. Very common
# coach setup — we treat the embed as a real email form, like optin_present.
_EMAIL_EMBED_RE = re.compile(
    r"hs-form-iframe|hbspt|js\.hsforms|/hsforms\.|mc-embedded-subscribe|mc4wp-form|list-manage\.com/subscribe|"
    r"convertkit|ck\.page|formkit-form|mailerlite|ml-form-embed|klaviyo-form|klaviyo_form|flodesk|emailoctopus|"
    r"email-octopus|substack\.com/embed|beehiiv|mailerlite\.com", re.I)

# A COMMUNITY / list / 'inner circle' sign-up, even without the word 'newsletter'. 'Join the Inner Circle',
# 'get first access', 'be the first to know', 'join our community / club / VIP list / waitlist'. Backed by a real
# form (an on-page email input OR a provider embed), this is an opt-in, not nothing. We were scoring these 0.
_COMMUNITY_SIGNUP_RE = re.compile(
    r"join (?:the |my |our |us(?: in)?(?: the| my| our)? )?[\w'&]*(?: [\w'&]+){0,4}?\s*"
    # 'membership' is deliberately NOT here: 'join our X membership' is usually a PAID program, not a free email list.
    r"(?:inner circle|community|club|mailing list|the list|tribe|crew|insiders?|vip(?:\s+list)?|waitlist)\b|"
    r"(?:get|be|want) (?:the )?first (?:access|to know|in line)|be the first to (?:know|hear)|"
    r"sign up (?:for |to )?(?:get |receive )?(?:updates|the latest|exclusive|first access|my emails)|"
    r"don'?t miss (?:a beat|out on)", re.I)
_OPTIN_HOOK_WORDS_RE = re.compile(
    r"first access|be the first|exclusive|expert tips|insider|early access|special (?:offers|events)|"
    r"weekly|monthly|free (?:tips|guide|training|updates)|latest news", re.I)

# Words that cluster in a NAV MENU. A magnet keyword ('free ebook') surrounded by these is a menu LINK to another
# page, not an on-page lead magnet, so it must never be scored like a real on-page opt-in.
_NAV_WORDS_RE = re.compile(
    r"\b(home|about|contact|services?|books?|articles?|blog|social|shop|store|menu|login|log in|sign in|faq|"
    r"press|media|testimonials?|portfolio|gallery|resources?|podcast|programs?|courses?|events?)\b", re.I)

def _is_nav_context(low, phrase):
    """True if EVERY occurrence of phrase sits inside a run of nav-menu words (a menu link, not on-page content).
    False the moment one occurrence appears somewhere without 2+ surrounding nav words (a real on-page magnet)."""
    ph = phrase.lower()
    occ = [mm.start() for mm in re.finditer(re.escape(ph), low)]
    if not occ:
        return False
    for p in occ:
        window = low[max(0, p - 55):p + len(ph) + 55]
        navs = {w.lower() for w in _NAV_WORDS_RE.findall(window)}
        if len(navs) < 2:
            return False          # this occurrence is real content, treat the magnet as genuine
    return True                    # every occurrence is buried in a menu

# A page whose main form is an APPLICATION (many fields, 'fill out the application', 'apply below') is a high-friction
# capture for people ready to commit, NOT a low-friction way to catch the many who aren't ready. Score it low.
_APPLICATION_RE = re.compile(
    r"\bapply (?:below|now|here|today|to work)\b|fill (?:out|in) (?:the |your |an )?application|"
    r"\bapplication form\b|complete (?:the |your |an )?application|submit (?:your |an )?application", re.I)

# A 'book a call / consultation / discovery call' is a HIGH-COMMITMENT capture: it catches people ready to TALK now,
# not the many who aren't ready yet, so it's weak lead capture (even if it's a strong CTA). Scored low, not zero, and
# the note spells out the commitment difference.
_CONSULT_RE = re.compile(
    r"book (?:a |your |an )?(?:free |complimentary )?(?:consultation|discovery call|strategy (?:call|session)|"
    r"intro(?:ductory)? call|clarity call|call|session|chat|appointment)|"
    r"(?:free|complimentary) (?:consultation|discovery call|strategy (?:call|session)|intro call|clarity call)|"
    r"schedule (?:a |your )?(?:free )?(?:call|consultation|session|appointment)", re.I)

def _has_real_optin(rl):
    """True only when the page gives a visitor a real place to ENTER an email: an <input type=email>, an input
    named/labelled for email, or a known email-service form embed (Mailchimp/ConvertKit/Klaviyo/etc. whose input
    often sits in an iframe we can't see into, so we accept the embed only alongside an actual <form>). It is NEVER
    true for a bare 'subscribe' word, a social link or a printed/mailto address, the things that used to mint a
    phantom newsletter. `rl` is the rendered HTML lowercased."""
    if not rl:
        return False
    tag = bool(re.search(r"<input[^>]+type=[\"']?email", rl) or
               re.search(r"<input[^>]+name=[\"']?(?:email|e-?mail|your-email|user_email|mce-email|em)[\"'\s/>]", rl) or
               re.search(r"<input[^>]+(?:placeholder|aria-label)=[\"'][^\"']*e-?mail", rl))
    # cdn-cgi/l/email is Cloudflare OBFUSCATING a printed address (the opposite of a sign-up), so it's excluded.
    esp = bool(re.search(r"list-manage\.com|mailchimp|convertkit|ck\.page|klaviyo|mailerlite|aweber|activecampaign|"
                         r"getresponse|substack\.com/subscribe|kit\.com|flodesk|beehiiv|mailpoet", rl)) and "<form" in rl
    return tag or esp

def detect_capture(row):
    """Classify and NAME what a page offers to capture a visitor, so the note always says EXACTLY what's there and
    never calls a contact form a newsletter. Returns {'kind': magnet|contact_form|newsletter|none, 'desc': text}."""
    bt = _clean(row.get("body_text")) or ""
    low = bt.lower()
    # A real email-capture form is present if the DOM scan saw an email input OR a provider EMBED (HubSpot/Mailchimp/
    # ConvertKit/etc.) whose fields sit inside an iframe we can't read. Both count as 'there's a real form here'.
    _has_optin = str(row.get("optin_present", "")).lower() == "yes" or bool(row.get("has_email_embed"))
    # 1) A real free resource (the gold standard) — a genuine "free X" or a download/get cue, not a bare keyword.
    m = _MAGNET_RE.search(row.get("clean_text") or "") or _MAGNET_RE.search(bt)
    if m and not _is_nav_context(low, re.sub(r"\s+", " ", m.group(0)).strip()):
        # ...but NOT when the only sign of the magnet is a nav-menu link ('FREE EBOOK' between BOOKS and SERVICES):
        # that's a link to another page, not an on-page opt-in, so it must not be scored as a real magnet.
        phrase = re.sub(r"\s+", " ", m.group(0)).strip()
        # body_text follows DOM order, so a magnet whose trigger sits past ~55% of the page is buried low down,
        # lost under everything above it, where most visitors never reach it. A real magnet nobody can find is
        # not the same as one up top, so we flag it and the caller docks the score.
        buried = bool(bt) and low.find(phrase.lower()) > 0.55 * len(bt)
        gated = bool(_GATED_FREEBIE_RE.search(bt))
        return {"kind": "magnet", "desc": f"a free resource (‘{phrase}’)", "buried": buried, "gated": gated,
                "inline_above_fold": bool(row.get("optin_inline_above_fold"))}   # DOM proof of a seamless inline form
    # 1b) A CUSTOM-NAMED magnet ('Get my Permission Slips') behind an actual opt-in form. Requires the form so a
    #     stray 'get your results' in body copy can't fake a magnet; skips booking-type objects.
    if str(row.get("optin_present", "")).lower() == "yes":
        for mm in _MAGNET_CTA_RE.finditer(bt):
            name = re.sub(r"\s+", " ", mm.group(2)).strip()
            branded = bool(re.match(r"[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)+$", name))   # Title-Case multi-word name
            if len(name) > 3 and not _NOT_MAGNET_OBJ.match(name) and (branded or _MAGNET_RESOURCE.search(name)):
                free = "free " if mm.group(1) else ""
                buried = bool(bt) and low.find(name.lower()) > 0.55 * len(bt)
                return {"kind": "magnet", "desc": f"a {free}‘{name}’", "buried": buried}
    # 1c) An APPLICATION form ('fill out the application below', 'apply now') behind a real form. High-friction, for
    #     people ready to commit, so it's a weak capture, NOT a lead magnet and NOT a low-friction opt-in.
    if _APPLICATION_RE.search(bt) and str(row.get("optin_present", "")).lower() == "yes":
        return {"kind": "application", "desc": "an application form"}
    # 2) A contact / enquiry form, named by the fields it actually shows. This is for people ready to reach out,
    #    NOT a way to capture the not-ready-yet, so it must never be called a newsletter or a lead magnet.
    fields = [f for f in ["name", "email", "phone", "subject", "message"]
              if re.search(r"\b" + f + r"\b\s*\*?", bt, re.I)]
    news = _NEWS_SIGNUP_RE.search(bt)
    if len(fields) >= 3 and ("message" in fields or "subject" in fields):
        pretty = ", ".join(f.capitalize() for f in fields)
        extra = f" with a ‘{news.group(0)}’ checkbox" if news else ""
        return {"kind": "contact_form", "desc": f"a contact form ({pretty}){extra}"}
    # 3) An EMAIL OPT-IN with a value hook (e.g. 'Free weekly life coaching and four tips to transform your life')
    #    even when it never says the word 'newsletter'. This is a real lead-capture we were scoring 0 by missing it.
    #    But a crypto-token / crowdfunding / 'collect tips and get discounts' pitch is NOT an email opt-in even when it
    #    says 'free tips' or 'discounts' (email capture = give your ADDRESS, not buy a token). Require a clean hook
    #    SENTENCE that isn't one of those; if the only match is a token/tips pitch, fall through to the newsletter.
    hook = ""
    for cand in re.split(r"(?<=[.!?])\s+", bt):
        if _OPTIN_VALUE_RE.search(cand) and 8 < len(cand) < 130 and not _NOT_OPTIN_RE.search(cand):
            hook = re.sub(r"\s+", " ", cand).strip(); break
    if hook:
        # body_text follows DOM order, so a hook past ~60% of the text is low down / below the fold.
        buried = bool(bt) and low.find(hook.lower()) > 0.6 * len(bt)
        return {"kind": "email_optin", "desc": f"a free email sign-up: ‘{hook}’", "buried": buried}
    # 3b) A COMMUNITY / 'inner circle' / list sign-up ('Join the Inner Circle', 'get first access to expert tips'),
    #     backed by a real form — an on-page email input OR a provider EMBED (HubSpot etc.) whose fields sit in an
    #     iframe the DOM scan can't reach. We were scoring these real opt-ins 0 (embedded form + non-'newsletter'
    #     wording). A genuine value hook (first access, expert tips, exclusive) makes it a proper email opt-in;
    #     otherwise it's a plain list sign-up (community).
    if _has_optin:
        cmy = _COMMUNITY_SIGNUP_RE.search(bt)
        if cmy:
            phrase = re.sub(r"\s+", " ", cmy.group(0)).strip()
            buried = bool(bt) and low.find(phrase.lower()) > 0.65 * len(bt)
            if _OPTIN_HOOK_WORDS_RE.search(bt):
                return {"kind": "email_optin", "desc": f"a free email sign-up (‘{phrase}’)", "buried": buried}
            return {"kind": "community", "desc": f"an email sign-up (‘{phrase}’)", "buried": buried}
    # 4) A standalone newsletter / mailing-list sign-up. Word boundaries matter: bare "subscribe" as a substring
    #    matches "oversubscribed", so we require real words, not fragments.
    # A newsletter/mailing-list sign-up is weak lead capture, and weaker still if it sits at the very bottom with
    # no reason to sign up. body_text follows DOM order, so a sign-up cue past ~65% of the page is down in the footer.
    def _news_buried(cue):
        return bool(bt) and cue and low.find(cue.lower()) > 0.65 * len(bt)
    # A newsletter is only REAL if there's an actual email SIGN-UP (an email input / opt-in form), not just the word
    # 'subscribe' (a social link) or a printed email address. So we require optin_present, a genuine capture signal,
    # before we ever call it a newsletter. This kills the 'phantom newsletter' where a stray word invented a form.
    if news and _has_optin:
        return {"kind": "newsletter", "desc": f"a newsletter sign-up (‘{news.group(0)}’)", "buried": _news_buried(news.group(0))}
    nm = re.search(r"\bnewsletter\b|\bmailing list\b|\bjoin (?:my|our|the) list\b|"
                   r"\bsign up (?:for|to) (?:my |our |the )?(?:newsletter|updates|mailing list)\b", low)
    if nm and _has_optin:
        return {"kind": "newsletter", "desc": "a newsletter or mailing-list sign-up", "buried": _news_buried(nm.group(0))}
    # 5) The scraper saw an email input but NO newsletter/subscribe wording (the branches above didn't fire). Do NOT
    #    invent a newsletter that isn't there. An email field with a 'get in touch' / 'contact' context is a CONTACT
    #    form, not a sign-up; name it honestly. Only if there's genuinely nothing else do we call it a bare email form.
    if _has_optin:
        if re.search(r"get in touch|contact us|contact me|\benquir|send (?:us |me )?a message|"
                     r"drop (?:us |me )?a (?:line|message)", low):
            return {"kind": "contact_form", "desc": "a ‘get in touch’ contact form"}
        return {"kind": "newsletter", "desc": "an email sign-up form", "buried": True}
    # 6) A 'book a consultation / call' booking. It IS lead capture, but HIGH-COMMITMENT: it catches people ready to
    #    talk now, not the many who aren't ready yet, so it scores low (not zero). Placed last so a real magnet /
    #    opt-in / form always wins; this is what a page whose only capture is a booking gets.
    cm = _CONSULT_RE.search(bt)
    if cm:
        phrase = re.sub(r"\s+", " ", cm.group(0)).strip()
        return {"kind": "consultation", "desc": f"a ‘{phrase}’ booking"}
    return {"kind": "none", "desc": ""}

def lead_capture_score(cap):
    """THE single source of truth for the lead_capture score, driven ONLY by what detect_capture found. Applied
    UNCONDITIONALLY (not just when the AI runs), so nav-link magnets, gated freebies, application forms and buried
    captures always win over the raw keyword scorer, which naively scores any 'ebook' mention 8. If this and the
    note ever disagree, that's the bug."""
    cap = cap or {}
    kind = cap.get("kind")
    if kind == "email_optin":
        return 3 if cap.get("buried") else 5
    if kind == "magnet":
        if cap.get("gated"):
            return 5
        return 4 if cap.get("buried") else 8
    if kind in ("newsletter", "community"):
        return 2 if cap.get("buried") else 3   # low-commitment (catches the not-ready) but weak without a real hook
    # A booking (book a call/consultation) IS capture, but high-commitment: it catches the ready-to-talk, not the
    # not-ready, so it scores low (2), same tier as a contact/application form. Not zero, because it's a real capture.
    return {"contact_form": 2, "application": 2, "consultation": 2}.get(kind, 0)

def build_capture(row):
    """A page can have MORE THAN ONE capture (a booking AND a pop-up newsletter AND a community signup). Detect them
    all, score each by its lead-capture value, return the BEST as the primary with the rest listed in 'also', so we
    never score off just the first one we happen to find, and the note can critique each."""
    caps = [detect_capture(row)]
    kinds = {c.get("kind") for c in caps}
    # a newsletter / opt-in the on-page text scan missed, usually a DELAYED POP-UP whose form is in the DOM at scrape
    if not (kinds & {"newsletter", "email_optin", "magnet"}):
        if row.get("popup_optin"):
            caps.append({"kind": "newsletter", "desc": "a newsletter sign-up", "popup": True})
        elif row.get("html_optin"):
            caps.append({"kind": "newsletter", "desc": "a newsletter sign-up"})
    if "community" not in kinds and row.get("html_community"):
        caps.append({"kind": "community", "desc": "a ‘join the community’ sign-up"})
    caps = [c for c in caps if c.get("kind") != "none"] or [{"kind": "none", "desc": ""}]
    best = dict(max(caps, key=lead_capture_score))
    # A pop-up capture is thrown OVER the page the moment someone lands, so it is the OPPOSITE of 'buried'. When the
    # page fires a marketing pop-up and the best capture is its newsletter/opt-in, mark it a pop-up and CLEAR the
    # buried flag (which came from the form sitting late in the DOM), so we never tell a coach their in-your-face
    # pop-up is 'stuck at the bottom where no one reaches it', the mistake that reads as a broken tool.
    if (row.get("has_popup") or row.get("popup_optin")) and best.get("kind") in ("newsletter", "email_optin", "community"):
        best["popup"] = True
        best["buried"] = False
    best["also"] = [c for c in caps if c is not None and c.get("desc") != best.get("desc")]
    return best

# ---- OPT-IN FORM vs BOOKING & ENQUIRY (David's split of the old 'lead capture') ----
# Opt-in form = value a NOT-ready visitor gets without a call (mandatory, none = 0). Booking & enquiry = the reach-out
# step for the READY (optional, none = N/A). A page can have BOTH, so we detect and score them separately.
_OPTIN_KINDS = {"magnet", "email_optin", "newsletter", "community"}

def opt_in_score(cap):
    """OPT-IN / LEAD CAPTURE score. MANDATORY: no form at all = 0.
    Any email input or capture box (including newsletter/footer) floors at 4.
    A named, above-the-fold lead magnet (free audio, checklist, micro-course) reaches 7-8;
    the tech+copy marriage gate in the merge layer can lift inline magnets to 10."""
    if not cap:
        return 0
    k = cap.get("kind")
    if k == "magnet":
        if cap.get("gated"):
            return 5                                  # magnet behind a paywall: weak
        if cap.get("buried"):
            return 6                                  # real magnet but hidden below the fold
        if cap.get("inline_above_fold"):
            return 8                                  # above-fold inline magnet: strong (gate can lift to 10)
        return 7                                      # magnet present, accessible, not inline above fold
    if k == "email_optin":
        return 5 if not cap.get("buried") else 4     # real email form: meets the floor, slightly above if prominent
    if k in ("newsletter", "community"):
        return 4                                      # any form = floor 4, regardless of position
    return 0

# Broader than _CONSULT_RE: coaches book 'reviews', 'audits', 'assessments', not only 'calls'.
_BOOKING_RE = re.compile(
    r"book (?:a |your |my |an )?(?:free |complimentary )?(?:call|consultation|discovery call|strategy (?:call|session)|"
    r"intro(?:ductory)? call|clarity call|session|chat|appointment|review|audit|assessment|meeting)|"
    r"schedule (?:a |your )?(?:free )?(?:call|consultation|session|appointment|review|audit)|"
    r"(?:free|complimentary) (?:consultation|discovery call|strategy (?:call|session)|review|audit|assessment)", re.I)

# A booking is often just a "Book" button wired to a scheduler (Calendly, Acuity, GoHighLevel, etc.) whose text alone
# says nothing. So we ALSO read where buttons LINK, not only the words. Known scheduler hosts + booking-path URLs are a
# definitive signal, robust to button wording. We match REAL schedulers only, so a 'Book' that goes to a shop checkout
# is never miscounted. Hosts are anchored to a domain boundary so short ones (cal.com) don't match inside other domains.
_BOOKING_HOST_RE = re.compile(
    r"(?:^|//|\.)(?:calendly\.com|acuityscheduling\.com|squarespacescheduling\.com|savvycal\.com|tidycal\.com|"
    r"youcanbook\.me|cal\.com|setmore\.com|simplybook\.[a-z]+|koalendar\.com|zcal\.co|appointlet\.com|10to8\.com|"
    r"vcita\.com|picktime\.com|book\.squareup\.com|paperbell\.com|satoriapp\.com|coachaccountable\.com|"
    r"practicebetter\.io|honeybook\.com|dubsado\.com|leadconnectorhq\.com|msgsndr\.com|oncehub\.com|bookwhen\.com|"
    r"checkfront\.com|timetap\.com|meetings\.hubspot\.com)", re.I)
_BOOKING_PATH_RE = re.compile(
    r"/widget/bookings?/|/book-a-(?:call|consult|session|discovery)|/book-now\b|/bookings?\b|/appointments?\b|"
    r"/schedule-a-(?:call|consult|session)|/discovery-call\b|/free-(?:call|consultation)\b|squareup\.com/appointments",
    re.I)
# A NATIVELY EMBEDDED LIVE CALENDAR (an <iframe> scheduler, or a Calendly/GoHighLevel inline widget) lets a visitor
# pick a time WITHOUT leaving the page -- the strongest possible next step. booking_links() reads href= only, so a
# pure inline embed (iframe src, no 'Book' link) was previously MISSED (scored N/A). This catches it off the raw HTML.
_BOOKING_EMBED_RE = re.compile(
    r'<iframe[^>]+src=["\'][^"\']*(?:calendly\.com|acuityscheduling\.com|app\.squarespacescheduling\.com|'
    r'book\.squareup\.com|leadconnectorhq\.com|msgsndr\.com|youcanbook\.me|tidycal\.com|savvycal\.com|'
    r'appointlet\.com|oncehub\.com|meetings\.hubspot\.com|cal\.com/)'
    r'|calendly-inline-widget|data-url=["\'][^"\']*calendly\.com|/widget/booking/', re.I)

def booking_links(html):
    """Distinct scheduler/booking URLs on the page (known host or booking-path). Robust to button wording. Used both to
    DETECT a booking AND to judge whether it's LOST among many competing session options (a wall of 'Book' buttons)."""
    found = set()
    for u in re.findall(r'href=["\']([^"\']+)["\']', html or "", re.I):
        lu = u.lower()
        if _BOOKING_HOST_RE.search(lu) or _BOOKING_PATH_RE.search(lu):
            found.add(lu.split("#")[0].split("?")[0].rstrip("/"))   # dedupe a repeated 'Book' button by its destination
    return found

def detect_booking_link(html):
    """True if any button/link points at a REAL scheduler. Robust to button text, so a bare 'Book' button still counts."""
    return len(booking_links(html)) > 0

def detect_booking(row):
    """BOOKING & ENQUIRY: the reach-out/commit step. Returns a cap dict (naming the kind) or None (N/A). We score by the
    TYPE of step, not free vs paid (a call is a commitment either way; whether there's a free way in is the Opt-in
    criterion's job). A booking is a scheduler LINK (strongest, robust to wording) OR booking WORDS in the copy."""
    bt = _clean(row.get("body_text")) or ""
    if row.get("has_booking_embed"):                            # STRONGEST: a live calendar embedded ON the page (pick a time without leaving)
        return {"kind": "booking_live", "desc": "a live booking calendar embedded right on the page"}
    if row.get("has_booking_link"):                              # strong: a button wired to a real scheduler
        return {"kind": "booking", "desc": "a booking a visitor can make straight off the page"}
    m = _BOOKING_RE.search(bt)                                   # backup: booking words (inline / on-page, no widget)
    if m:
        phrase = re.sub(r"\s+", " ", m.group(0)).strip()
        return {"kind": "booking", "desc": f"a ‘{phrase}’ booking"}
    if _APPLICATION_RE.search(bt):
        return {"kind": "application", "desc": "an application form"}
    fields = [f for f in ["name", "email", "phone", "subject", "message"] if re.search(r"\b" + f + r"\b", bt, re.I)]
    if len(fields) >= 3 and ("message" in fields or "subject" in fields):
        return {"kind": "contact_form", "desc": "a contact / enquiry form"}
    return None

def booking_score(cap):
    """LOW-FRICTION DISCOVERY STEP score by the TYPE of step, or None for N/A.
    A live embedded scheduler (Calendly iframe on the page) starts at 8; the tech+copy marriage gate can lift to 10.
    A button linking OUT to an external scheduler page is high-friction: starts at 5.
    Contact form = 4. Application = 3."""
    if not cap:
        return None
    return {"booking_live": 8, "booking": 5, "contact_form": 4, "application": 3}.get(cap.get("kind"))

def build_captures(row):
    """Split capture: {'opt_in': best opt-in cap or None, 'booking': booking cap or None}. A page can have BOTH."""
    cap = build_capture(row)
    all_caps = [cap] + (cap.get("also") or [])
    optins = [c for c in all_caps if c.get("kind") in _OPTIN_KINDS]
    opt = dict(max(optins, key=opt_in_score)) if optins else None
    return {"opt_in": opt, "booking": detect_booking(row)}

def build_evidence(row):
    h1 = _tidy_headline(row.get("h1"))
    h2s = [p.strip() for p in _clean(row.get("h2_headings")).split("|") if len(p.strip()) > 2][:4]
    ctas = [p.strip() for p in _clean(row.get("cta_text")).split("|") if p.strip()]
    bodyraw = _clean(row.get("body_text"))
    body = bodyraw.lower()
    testi = bool(_clean(row.get("testimonial_text"))) or any(m in body for m in TESTIMONIAL_MARKERS)
    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w][\w.-]+", bodyraw))
    has_phone = bool(re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", bodyraw))
    has_reg = any(k in body for k in
                  ["companies house", "company no", "company number", "registered in", "registered office",
                   "vat ", "vat no", "reg no", "privacy policy", "terms of", "registered charity"])
    wc = row.get("word_count")
    try:
        wc = int(float(wc))
    except (TypeError, ValueError):
        wc = 0
    # Quote the actual lead-capture line back to them ("show them what we see").
    _news_kw = ["subscribe", "newsletter", "sign up", "mailing list", "join our list", "news and tips",
                "enews", "e-news", "join my list", "weekly email", "stay in the loop", "join the list"]
    capture_line = ""
    for cand in ([ctas[0] if ctas else ""] + h2s + re.split(r"(?<=[.!?])\s+", bodyraw)):
        c = cand.strip()
        if 6 < len(c) < 95 and any(k in c.lower() for k in _news_kw):
            capture_line = c
            break
    h1_tag = _tidy_headline(row.get("h1_tag") if row.get("h1_tag") is not None else row.get("h1"))
    visual = _tidy_headline(row.get("visual_headline"))
    # The headline we analyse/quote = what a cold visitor reads first (largest font), falling back to the
    # h1 tag, then the page title. The h1 tag is kept separately for the SEO angle (what Google reads).
    display_headline = visual or h1 or _tidy_headline(row.get("page_title"))
    return {
        "domain": row.get("domain"),
        "headline": display_headline,
        "headline_is_h1": bool(h1),          # if False, we couldn't find a real H1 (itself a finding)
        "h1_tag": h1_tag,                    # the literal <h1> element — what Google reads
        "headline_differs_from_h1": bool(visual and h1_tag and visual.lower() != h1_tag.lower()),
        "page_title": _tidy_headline(row.get("page_title")),
        "niche": detect_niche(" ".join([h1_tag or "", " ".join(h2s),
                                        _tidy_headline(row.get("page_title")) or ""]), full=body),
        "has_logos": any(p in body for p in LOGO_PHRASES),
        "capture_line": capture_line,
        "capture": build_capture(row),       # PRIMARY capture (kept for the CTA ask-count + pop-up note)
        "captures": build_captures(row),     # SPLIT: {'opt_in': cap-or-None, 'booking': cap-or-None} for the two scores
        "subheadings": h2s,
        "main_cta": ctas[0] if ctas else "",
        "testimonials_found": testi,
        "pricing_found": bool(_clean(row.get("pricing_mentions"))),
        "optin": str(row.get("optin_present", "")).lower() == "yes",
        "booking": str(row.get("booking_link_present", "")).lower() == "yes",
        "contact_details": has_email or has_phone,
        "business_details": has_reg,
        "word_count": wc,
        "secure": str(row.get("url", "")).startswith("https"),
        "proof_links": row.get("proof_link_labels") or [],           # proof linked but not ON the page
        "external_reviews": row.get("proof_external_reviews") or [],  # Amazon / Trustpilot etc.
        "has_popup": bool(row.get("has_popup")),
    }

# --- pricing is often a deliberate choice, never scold; give a balanced note instead ---
PRICING_NOTE = (
    "We noticed your homepage doesn't show pricing. Plenty of coaching businesses choose this on purpose, and it "
    "can be the right call, pricing is a personal, strategic decision. Just be aware it cuts both ways: some "
    "visitors hesitate when they can't tell what they're getting into, a few assume it's out of their "
    "range, and others won't reach out because the uncertainty feels risky. Worth testing either way."
)

# --- "whose words are these?", coach/expert language vs the buyer's own concrete words ---
# Abstract outcomes a coach values and names (buyers rarely type these into Google):
COACH_WORDS = [
    "clarity", "confidence", "empower", "empowerment", "transformation", "transform", "potential",
    "authentic", "alignment", "aligned", "mindset", "breakthrough", "growth", "purpose", "fulfil",
    "fulfill", "self-belief", "limiting belief", "holistic", "thrive", "unlock", "elevate", "best self",
    "best version", "inner ", "wellbeing", "well-being", "resilience", "self-awareness", "mindful",
    "abundance", "vision", "values", "self-worth", "self-doubt", "personal development", "empowered",
    "flourish", "wholeness", "presence", "intentional",
]
# Concrete situations/symptoms in the buyer's own voice (how the pain actually feels):
BUYER_MARKERS = [
    "can't", "cant", "can’t", "struggling", "struggle", "stuck", "tired of", "overwhelmed", "overwhelm",
    "dread", "worried", "afraid", "scared", "stressed", "burnt out", "burnout", "burned out", "no time",
    "exhausted", "failing", "passed over", "can't sleep", "anxious", "anxiety", "lonely", "arguing",
    "debt", "redundan", "divorce", "promotion", "overlooked", "undervalued", "imposter", "not good enough",
    "second-guess", "people-pleas", "procrastinat", "plateau", "every time", "i feel", "you feel",
    "hate my", "sick of", "fed up", "breaking point", "keep getting", "keep putting", "why can",
]

def analyse_voice(row):
    text = " ".join([_clean(row.get("h1")), _clean(row.get("h2_headings")),
                     _clean(row.get("outcome_claim")), _clean(row.get("problem_statement")),
                     _clean(row.get("body_text"))[:2800]]).lower()
    coach = sorted({w.strip() for w in COACH_WORDS if w in text})
    buyer = sorted({w for w in BUYER_MARKERS if w in text})
    c, b = len(coach), len(buyer)
    # "mixed" must only fire when she genuinely uses BOTH. No buyer words at all = she talks like the coach.
    if b == 0:
        leaning = "expert"       # no buyer language on the page at all
    elif c == 0 or b > c * 1.5:
        leaning = "customer"     # talks in the buyer's own words
    elif c > b * 1.5:
        leaning = "expert"       # leans on coach language over the buyer's
    else:
        leaning = "mixed"        # genuinely some of each
    return {"coach_terms": coach[:6], "buyer_terms": buyer[:6], "leaning": leaning}

def tech_strength(row, scores):
    """Only ever praise TECHNICAL foundations, safe to compliment, never undercuts the marketing critique."""
    secure = str(row.get("url", "")).startswith("https")
    if secure and scores.get("technical_health", 0) >= 8:
        return ("Your homepage is secure (HTTPS) and loads cleanly with real content, the technical "
                "foundations are solid. That's the easy part already handled; the marketing is where the work is.")
    if secure:
        return "Your homepage is secure (HTTPS), a basic trust signal a surprising number of coaches still miss."
    return None

# Find the text a COLD VISITOR actually reads first: the biggest, most prominent words near the top of
# the page. That is often NOT the <h1> tag (personal-brand sites put their name in the h1). We capture
# both — the visual headline (what a human reads) and the h1 tag (what Google reads) — they matter for
# different reasons.
VISUAL_HEADLINE_JS = r"""
() => {
  const vh = window.innerHeight || 750;
  const vw = window.innerWidth || 1200;
  // Is this element inside a pop-up / modal / overlay? If so it must NEVER be mistaken for the headline.
  const inPopup = (el) => {
    let n = el;
    for (let i = 0; n && i < 8; i++, n = n.parentElement) {
      if (!n.getAttribute) continue;
      const role = n.getAttribute('role') || '';
      if (role === 'dialog' || n.getAttribute('aria-modal') === 'true') return true;
      const cls = ((typeof n.className === 'string' ? n.className : '') + ' ' + (n.id || '')).toLowerCase();
      // NOT 'overlay': hero/banner sections routinely use it for a background tint and are NOT pop-ups (it was
      // hiding real headlines and flagging phantom pop-ups). A genuine overlay is caught by the fixed-layer test below.
      if (cls.includes('modal') || cls.includes('popup') || cls.includes('pop-up') ||
          cls.includes('lightbox')) return true;
      const st = getComputedStyle(n);
      if (st.position === 'fixed' && (parseInt(st.zIndex) || 0) >= 100) {
        const r = n.getBoundingClientRect();
        if (r.width > vw * 0.5 && r.height > vh * 0.4) return true;   // a big fixed layer covering the page
      }
    }
    return false;
  };
  const seen = new Set();
  const cands = [];
  const bigAll = [];                                        // generous pool of prominent lines for the AI to pick from
  const bseen = new Set();
  let hasPopup = false;
  const els = document.querySelectorAll('h1,h2,h3,h4,p,span,div,strong,a,li');
  for (const el of els) {
    let txt = '';
    for (const n of el.childNodes) { if (n.nodeType === 3) txt += n.textContent; }
    txt = txt.replace(/\s+/g, ' ').trim();
    if (txt.length < 6 || txt.length > 160) continue;
    if (!/[a-z]/i.test(txt)) continue;                     // skip pure numbers/symbols
    const rect = el.getBoundingClientRect();
    if (rect.top < 0 || rect.top > vh) continue;           // must be above the fold
    if (rect.width < 40 || rect.height < 12) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || parseFloat(st.opacity || '1') < 0.1) continue;
    const fs = parseFloat(st.fontSize) || 0;
    if (fs < 18) continue;                                  // ignore body-size text
    // FULL line (recovered from the nearest heading/container so split spans read whole) into the AI pool. This
    // pool is NOT filtered by inPopup, the AI judges visually which line is the real headline.
    let full = txt;
    const cont = el.closest('h1,h2,h3,h4,h5,h6') || el.parentElement;
    if (cont) { const f = (cont.innerText || cont.textContent || '').replace(/\s+/g, ' ').trim();
                if (f.length > full.length && f.length <= 180) full = f; }
    const fk = full.toLowerCase();
    if (!bseen.has(fk)) { bseen.add(fk); bigAll.push({ txt: full, fs: fs }); }
    if (inPopup(el)) continue;                              // a pop-up is never the headline
    const key = txt.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    cands.push({ txt: txt, fs: fs, top: rect.top, el: el });
  }
  cands.sort((a, b) => (b.fs - a.fs) || (a.top - b.top));   // biggest font, then highest up
  bigAll.sort((a, b) => b.fs - a.fs);
  const bigTexts = bigAll.slice(0, 12).map(function (x) { return x.txt; });
  let hero = '';
  if (cands.length) {
    const win = cands[0];
    hero = win.txt;
    // Headlines are often split across styled spans (e.g. 'Reignite Your Ca'|'reer'). Recover the FULL
    // line from the nearest heading / short container so we never quote a truncated fragment.
    const container = win.el.closest('h1,h2,h3,h4,h5,h6') || win.el.parentElement;
    if (container) {
      const full = (container.innerText || container.textContent || '').replace(/\s+/g, ' ').trim();
      if (full.length > hero.length && full.length <= 180) hero = full;
    }
  }
  const h1el = document.querySelector('h1');
  const h1 = h1el ? h1el.textContent.replace(/\s+/g, ' ').trim() : '';
  // Clean subheadings from the RENDERED page (innerText), so span-split text like 'Ca reer' reads 'Career'.
  const headings = [];
  const hseen = new Set();
  document.querySelectorAll('h1,h2,h3,h4').forEach(function (h) {
    if (inPopup(h)) return;
    const t = (h.innerText || h.textContent || '').replace(/\s+/g, ' ').trim();
    const k = t.toLowerCase();
    if (t.length >= 3 && t.length <= 160 && !hseen.has(k)) { hseen.add(k); headings.push(t); }
  });
  // Dedicated pop-up detector: a fixed/absolute overlay covering a real chunk of the page ON LOAD, that is NOT a
  // cookie/consent/privacy banner (those are compliance, not a marketing pop-up thrown at cold traffic).
  document.querySelectorAll('div,section,aside,dialog').forEach(function (n) {
    if (hasPopup) return;
    const st = getComputedStyle(n);
    if (st.position !== 'fixed' && st.position !== 'absolute') return;
    if ((parseInt(st.zIndex) || 0) < 100) return;
    if (st.visibility === 'hidden' || st.display === 'none' || parseFloat(st.opacity || '1') < 0.1) return;
    const r = n.getBoundingClientRect();
    if (!(r.width > vw * 0.45 && r.height > vh * 0.3 && r.top < vh && r.left < vw)) return;   // covers real area, on screen
    const t = (n.innerText || '').toLowerCase();
    if (t.replace(/\s/g, '').length < 15) return;   // a dim BACKDROP layer has no text; the real pop-up box does
    if (/cookie|consent|gdpr|privacy|we use|manage preferences|accept all|your privacy/.test(t)) return;  // cookie banner, not a pop-up
    const cls = ((typeof n.className === 'string' ? n.className : '') + ' ' + (n.id || '')).toLowerCase();
    const looksModal = cls.includes('modal') || cls.includes('popup') || cls.includes('pop-up') ||
                       cls.includes('lightbox') || n.getAttribute('role') === 'dialog' ||
                       n.getAttribute('aria-modal') === 'true';
    if (looksModal || (r.width > vw * 0.5 && r.height > vh * 0.4)) hasPopup = true;
  });
  // CLIENT / TRUST LOGOS: brand names live in image ALT text. A full-page screenshot is downscaled for the
  // vision API, so a logo strip becomes an unreadable blur and the AI wrongly calls real brands 'unrecognisable'.
  // We grab the alt text of images sitting under a 'trusted by / our clients / partners' heading, so the AI can
  // judge whether they are recognisable major brands (costly to fake) or unknown local logos (ambiguous).
  const clientLogos = [];
  const logoSeen = new Set();
  let logoHeading = '';
  const TRUST_RE = /trusted by|our clients|\bclients\b|as seen|featured in|our partners|brands we|worked with|client logos/i;
  const trustEls = document.querySelectorAll('h1,h2,h3,h4,h5,p,span,strong,div');
  for (const h of trustEls) {
    if (clientLogos.length >= 30) break;
    const t = (h.innerText || h.textContent || '').replace(/\s+/g, ' ').trim();
    if (t.length < 4 || t.length > 60 || !TRUST_RE.test(t)) continue;
    if (!logoHeading) logoHeading = t;
    let scope = h.closest('section,div,header,footer') || h.parentElement;
    let hops = 0;
    while (scope && hops < 3 && scope.querySelectorAll('img').length === 0) { scope = scope.parentElement; hops++; }
    if (!scope) continue;
    for (const im of scope.querySelectorAll('img')) {
      let a = (im.alt || '').replace(/\s+/g, ' ').trim();
      if (!a) continue;
      a = a.replace(/[\s_-]*(logo|logos|icon|image|img)$/i, '').trim();
      const k = a.toLowerCase();
      if (a.length >= 2 && a.length <= 40 && !logoSeen.has(k)) { logoSeen.add(k); clientLogos.push(a); }
    }
  }
  return { hero: hero, h1: h1, hasPopup: hasPopup, headings: headings, bigTexts: bigTexts, clientLogos: clientLogos, logoHeading: logoHeading };
}
"""

# Proof and credibility often live OFF the homepage, one click away (a testimonials page, an Amazon book
# page with hundreds of reviews). A cold buyer won't click in the first few seconds, so it doesn't work in
# the moment that matters, but it's WRONG to say "no proof" when it's really just hidden. We spot the LINK,
# and never visit it (homepage-only scope stays intact).
EXT_REVIEW_HOSTS = {"amazon.": "Amazon", "goodreads.": "Goodreads", "trustpilot.": "Trustpilot",
                    "feefo.": "Feefo", "reviews.io": "Reviews.io"}
# STRICT: needs a real <a href> whose PATH is a proof page, OR anchor link TEXT that is exactly a proof label.
# A stray word like "review" in body copy or a URL param must NOT trigger this.
PROOF_PAGE_RE = re.compile(
    r'href=["\'][^"\']*/(testimonials?|reviews?|case-stud(?:y|ies)|success-stor(?:y|ies)|'
    r'praise|kind-words|client-results)(?:[/"\'?#]|["\'])', re.I)
PROOF_TEXT_RE = re.compile(
    r'<a\b[^>]*>\s*(testimonials?|reviews|success stories|case studies|praise|kind words|'
    r'what clients say|what people say)\s*</a>', re.I)

def strip_chrome(html):
    """Remove nav / menus / dropdowns / footer / scripts / styles so we judge only the PROMINENT content a
    cold visitor actually sees, not links buried in a hamburger menu or words hiding in CSS/schema JSON.
    Falls back to the raw html only if the whole parse fails."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        targets = list(soup.find_all(["nav", "footer", "script", "style", "noscript", "template"]))
        targets += list(soup.find_all(attrs={"role": ["navigation", "menu", "menubar"]}))
        for el in soup.find_all(class_=True):
            cls = " ".join(el.get("class", [])).lower()
            if any(w in cls for w in ["menu", "dropdown", "submenu", "navbar", "mobile_nav", "mobile-nav",
                                      "site-nav", "main-nav", "nav_", "_nav", "footer"]):
                targets.append(el)
        for el in targets:
            try:
                el.decompose()          # per-element guard: a detached child must not abort the whole strip
            except Exception:
                pass
        return str(soup)
    except Exception:
        return html

def clean_main_text(html):
    """The visible text of the MAIN content only (nav/menu/footer/script/style removed). Used to sanity-check
    detections so a word hiding in a menu, CSS class or schema JSON can't fake a signal."""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(strip_chrome(html), "html.parser").get_text(" ", strip=True).lower()
    except Exception:
        return ""

def detect_proof_links(html):
    """Return human labels for proof that's linked but not on the homepage. We never fetch these pages.
    Deliberately strict: only a genuine link to a proof PAGE, in the MAIN content (not a nav menu), counts."""
    html = strip_chrome(html)
    h = html.lower()
    ext, internal = [], False
    for host, label in EXT_REVIEW_HOSTS.items():
        if re.search(r'href=["\'][^"\']*' + re.escape(host), h) and label not in ext:
            ext.append(label)
    if PROOF_PAGE_RE.search(html) or PROOF_TEXT_RE.search(html):
        internal = True
    labels = []
    if internal:
        labels.append("a testimonials or reviews page")
    for e in ext:
        labels.append(f"an {e} page" if e[0] in "AEIOU" else f"a {e} page")
    return {"labels": labels, "external_reviews": ext}

# Hide pop-ups / cookie banners / dim backdrops BEFORE the vision screenshot, so the AI sees the real page under
# them (a pop-up covering the hero/logos would otherwise hide proof from vision). Gated on position fixed/absolute
# + z-index >= 100, so it can NEVER touch an in-flow hero section (those are static/relative, low z).
OVERLAY_STRIP_JS = r"""
() => {
  const vh = window.innerHeight || 750, vw = window.innerWidth || 1200;
  document.querySelectorAll('div,section,aside,dialog,ins,iframe').forEach(function (n) {
    const st = getComputedStyle(n);
    if (st.position !== 'fixed' && st.position !== 'absolute') return;
    if ((parseInt(st.zIndex) || 0) < 100) return;
    const r = n.getBoundingClientRect();
    const t = (n.innerText || '').toLowerCase();
    const cls = ((typeof n.className === 'string' ? n.className : '') + ' ' + (n.id || '')).toLowerCase();
    const big = r.width > vw * 0.4 && r.height > vh * 0.25;                                  // a modal / pop-up box
    const backdrop = r.width > vw * 0.7 && r.height > vh * 0.6 && t.replace(/\s/g, '').length < 15;  // dim layer
    const cookie = /cookie|consent|gdpr|privacy|we use|manage preferences|accept all/.test(t);
    const modalCls = cls.includes('modal') || cls.includes('popup') || cls.includes('pop-up') ||
                     cls.includes('overlay') || cls.includes('lightbox') || cls.includes('cookie') ||
                     cls.includes('consent') || n.getAttribute('role') === 'dialog' ||
                     n.getAttribute('aria-modal') === 'true';
    if (big || backdrop || cookie || (modalCls && r.height > vh * 0.12)) {
      n.style.setProperty('display', 'none', 'important');
    }
  });
  document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';  // undo pop-up scroll-lock
  return true;
}
"""

def render_and_extract(domain):
    """Load the homepage in a REAL browser (runs JavaScript, catches sliders/carousels the fast
    scraper misses) and, in the same pass, grab the thumbnail. Returns (row, thumbnail_data_uri).
    Returns (None, None) on any failure so the caller can fall back to the fast static scrape."""
    try:
        import base64
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1200, "height": 750})
            try:
                pg.goto("https://" + domain, timeout=30000, wait_until="load")
            except Exception:
                # Some sites ONLY serve on www: the bare domain refuses the connection or has no redirect
                # (yourjoyfulsolutions.com closes the connection; www.yourjoyfulsolutions.com is fine). Retry with a
                # www. prefix so a working site isn't reported 'dead' purely over the www split. The failed navigation
                # leaves the page unusable, so the retry needs a FRESH page.
                if domain.startswith("www."):
                    raise
                pg.close()
                pg = b.new_page(viewport={"width": 1200, "height": 750})
                pg.goto("https://www." + domain, timeout=30000, wait_until="load")
            pg.wait_for_timeout(1500)          # let JS sliders/animations paint their first slide
            # Scroll the whole page so LAZY-LOADED below-the-fold content actually loads (product shops, proof
            # strips, testimonials, magnets often sit low and never render until scrolled into view). Then return to
            # the top so the thumbnail/screenshot start clean. Capped so a giant page can't scroll forever.
            try:
                pg.evaluate("""async () => {
                  const vh = window.innerHeight || 750;
                  const pause = (ms) => new Promise(r => setTimeout(r, ms));
                  for (let i = 0; i < 40; i++) {
                    window.scrollBy(0, vh);
                    await pause(180);
                    if ((window.innerHeight + window.scrollY) >= document.body.scrollHeight - 2) break;
                  }
                  window.scrollTo(0, 0);
                  await pause(300);
                }""")
                pg.wait_for_timeout(500)
            except Exception:
                pass
            # Async widgets (booking calendars + priced-package embeds — GoHighLevel, Calendly, Acuity, etc.) can still
            # be loading after the scroll pass. A fixed-timer capture sometimes grabs the page before they finish, so the
            # priced offers / booking links read as absent and the score wobbles run-to-run (booking flipping 5<->8, CTA
            # 3<->7, pricing seen<->not). Wait for the network to go quiet first so late content is in. Capped at 4s so a
            # page with chatty analytics / websockets / video can't hang the audit; on a quiet page it returns at once.
            try:
                pg.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
            # networkidle CUTS OFF EARLY on iframe-heavy funnel platforms (HubSpot embeds, custom landing builders): the
            # outer page goes quiet while the embed is still fetching its own form/widget. So after networkidle we hold a
            # mandatory 3.5s for those third-party embeds to finish, THEN scroll to the very bottom and back to the top so
            # every lazy-loaded / on-scroll asset fires the SAME way on every run, THEN capture. This is what stops the
            # funnel-page scores wobbling; cost is ~4.5s added to every audit, which we accept for run-to-run stability.
            pg.wait_for_timeout(3500)
            try:
                pg.evaluate("""() => new Promise((res) => {
                  window.scrollTo(0, document.body.scrollHeight);
                  setTimeout(() => { window.scrollTo(0, 0); res(true); }, 700);
                })""")
                pg.wait_for_timeout(600)
            except Exception:
                pass
            rendered_html = pg.content()
            final_url = pg.url
            try:
                vis = pg.evaluate(VISUAL_HEADLINE_JS)
            except Exception:
                vis = None
            # OPT-IN 10 SIGNAL: is there a REAL email input INLINE and ABOVE THE FOLD (top viewport, not inside a
            # modal/popup)? That is the DOM proof of a seamless inline capture form (the strongest opt-in). Wrapped so
            # ANY JS failure -> False, which falls straight back to the 8-cap magnet rules. pg is still open here.
            try:
                _optin_af = bool(pg.evaluate(r"""() => {
                  const el = document.querySelector('input[type=email], input[name*="email" i], input[placeholder*="email" i]');
                  if (!el) return false;
                  const r = el.getBoundingClientRect();
                  const inModal = !!el.closest('[role=dialog], .modal, .popup, [class*="modal"], [class*="popup"], [class*="overlay"]');
                  return r.top >= 0 && r.top < (window.innerHeight || 800) && !inModal && r.width > 0 && r.height > 0;
                }"""))
            except Exception:
                _optin_af = False
            # A REAL on-page shop = visible product tiles / add-to-cart BUTTONS actually rendered on the homepage,
            # NOT merely WooCommerce being installed (its scripts ship 'add_to_cart' strings on every WP site that has
            # the plugin, even when no products show). Count only VISIBLE shop elements so an installed-but-hidden
            # store doesn't wrongly read as shop chaos.
            try:
                shop_ct = pg.evaluate(r"""() => {
                  const sel = 'a.add_to_cart_button, .single_add_to_cart_button, button[name=\"add-to-cart\"], li.product, ul.products > li';
                  const visible = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
                    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity || '1') > 0.1; };
                  let n = 0;
                  document.querySelectorAll(sel).forEach(e => { if (visible(e)) n++; });
                  document.querySelectorAll('a,button').forEach(e => {
                    const t = (e.textContent || '').trim().toLowerCase();
                    if ((t === 'add to cart' || t === 'add to basket') && visible(e)) n++;
                  });
                  return n;
                }""")
            except Exception:
                shop_ct = 0
            # PRICED-OFFER OVERLOAD: a wall of priced offers each with a buy / book button overwhelms a cold visitor
            # whether it's an add-to-cart shop OR a booking list. Count DISTINCT price amounts in the visible text
            # (read after the scroll, so prices low on the page are captured). Used with the shop signal to decide
            # whether the CTA is allowed to score below 4: many priced offers = genuine overload, so it can.
            try:
                priced_offers = pg.evaluate(r"""() => {
                  const t = document.body.innerText || '';
                  const m = t.match(/(?:A|US|AU|NZ|C)?[£$€]\s?\d[\d,]*(?:\.\d{2})?/g) || [];
                  return new Set(m.map(x => x.replace(/\s/g, ''))).size;
                }""")
            except Exception:
                priced_offers = 0
            # The RENDERED visible text, as a rescue: some builders (Wix, certain SPAs) defeat the HTML extractor and
            # it returns almost nothing, so we'd score proof/story/copy off an empty string. innerText is what a human
            # actually sees; we fall back to it below when the extractor clearly under-captured.
            try:
                visible_text = pg.evaluate("document.body.innerText") or ""
            except Exception:
                visible_text = ""
            # Force the page BACK TO THE TOP right before the thumbnail: the scroll-to-load pass and any sticky header
            # / re-scroll can leave the viewport partway down, so the thumbnail showed the 2nd fold instead of the hero.
            try:
                pg.evaluate("window.scrollTo(0, 0)")
                pg.wait_for_timeout(350)
            except Exception:
                pass
            png = pg.screenshot(clip={"x": 0, "y": 0, "width": 1200, "height": 750})   # above-fold thumbnail: kept
            #                                                       WITH the pop-up (honest "here's your actual page")
            png_full = None
            if os.getenv("AUDIT_VISION", "on").lower() not in ("off", "0", "no", "false"):
                try:
                    pg.evaluate(OVERLAY_STRIP_JS)   # clear pop-ups / cookie banners so VISION sees the real page under them
                except Exception:
                    pass
                try:
                    # WHOLE page so the AI SEES logos/media/video proof, but the vision API rejects any image over
                    # 8000px on a side, so on a very long homepage clip to the top 7800px instead of full_page.
                    ph = int(pg.evaluate("document.documentElement.scrollHeight") or 0)
                    if ph and ph > 7800:
                        png_full = pg.screenshot(clip={"x": 0, "y": 0, "width": 1200, "height": 7800})
                    else:
                        png_full = pg.screenshot(full_page=True)
                except Exception:
                    png_full = None
            b.close()
        row = sm.extract(rendered_html, final_url, domain)   # same extractor, richer input
        # RESCUE an under-captured extraction: if the HTML extractor returned almost nothing but the page clearly has
        # rendered text (Wix / some SPAs defeat the extractor), fall back to the visible innerText so we never score
        # proof / story / copy off an empty string. The 68-char-vs-24k-char case is exactly this.
        _bt = row.get("body_text") or ""
        _vt = re.sub(r"[ \t]+", " ", re.sub(r"\n{2,}", "\n", (visible_text or ""))).strip()
        if len(_vt) > max(400, 2 * len(_bt)):
            row["body_text"] = _vt
        row["scrape_thin"] = bool(len(row.get("body_text") or "") < 200)   # content gate: too little to score honestly
        # A CONTENT video (a YouTube/Vimeo embed, or a <video> with controls) is one a visitor presses play on, so
        # 'reasons to buy' can hide inside it, that's what the media note is about. A silent AUTOPLAY-MUTED-LOOP
        # background video is just decoration, has no spoken reasons, and must NOT trigger the note.
        _has_embed = bool(re.search(r"youtube\.com/embed|youtu\.be|player\.vimeo|vimeo\.com/video|wistia|loom\.com/embed",
                                    rendered_html, re.I))
        _vid_tags = re.findall(r"<video\b[^>]*>", rendered_html, re.I)
        _content_vid = any(("controls" in v.lower()) or not ("muted" in v.lower() and "autoplay" in v.lower())
                           for v in _vid_tags)
        row["has_video"] = "yes" if (_has_embed or _content_vid) else "no"
        row["bg_video_only"] = bool(_vid_tags and not _has_embed and not _content_vid)   # decorative background video
        # A genuine priced online shop. We accept it if EITHER two-plus VISIBLE product tiles / add-to-cart buttons
        # rendered on the page (standard commerce markup), OR the store platform is present AND actually wired up with
        # add-to-cart markup (WooCommerce/Shopify with real product buttons, which catches custom-styled shops whose
        # products lazy-load below every capture cutoff). A plain price mention or a booking button is NOT a shop.
        # Used to floor the CTA: only a real store drops the CTA to 2-3 for chaos; a shopless page floors at 4.
        row["has_shop"] = bool(shop_ct and shop_ct >= 2)
        row["priced_offer_count"] = int(priced_offers or 0)
        # Capture the visual headline (biggest text) for DISPLAY + the hero critique. We do NOT overwrite the
        # <h1> used for scoring: clarity/specificity must judge the page's real content (same as the corpus),
        # not just the biggest word, or a site that explains itself lower down gets unfairly marked down.
        row["h1_tag"] = row.get("h1")
        if vis and vis.get("hero"):
            row["visual_headline"] = vis["hero"].strip()
        row["has_popup"] = bool(vis and vis.get("hasPopup"))          # rule-based fallback; AI vision overrides it
        # SECONDARY captures live in the FULL html, including a delayed pop-up whose form is in the DOM before it
        # shows (so the visible-text scrape misses it). Detect a newsletter/opt-in form and a community signup here,
        # so a page can have MORE THAN ONE capture and we don't score off just the first one we happened to find.
        _rl = rendered_html.lower()
        # A REAL opt-in needs an actual place to ENTER an email, an <input type=email>, an input named/labelled for
        # email, or a known email-service form embed (Mailchimp/ConvertKit/Klaviyo/etc., whose input often sits in an
        # iframe we can't see into). The word 'subscribe' or a printed address is NOT a form. This is the signal that
        # separates a genuine newsletter sign-up from a phantom one, so the score only ever credits capture that exists.
        _real_email_input = _has_real_optin(_rl)
        # optin_present is the corpus column detect_capture reads; the live render must set it too or the newsletter /
        # magnet-form / application branches never fire. Drive it off the real field, never off a bare keyword.
        row["optin_present"] = "yes" if _real_email_input else ""
        row["has_email_embed"] = bool(_EMAIL_EMBED_RE.search(rendered_html))  # provider form embed (HubSpot/Mailchimp/etc.): fields sit in an iframe the DOM input scan can't reach
        _optin_words = bool(re.search(
            r"newsletter|subscribe|mailchimp|convertkit|klaviyo|mailerlite|mailpoet|email[- ]?sign[- ]?up|"
            r"sign[- ]?up form|join (?:my|our|the) (?:list|mailing|newsletter)|get (?:my|the) (?:free )?updates", _rl))
        # The newsletter FALLBACK (build_capture) needs the wording AND a real field, so a stray 'subscribe' link or a
        # printed address can never mint a phantom newsletter the page doesn't actually have.
        row["html_optin"] = bool(_optin_words and _real_email_input)
        row["html_community"] = bool(re.search(
            r"join (?:the |our |my )?(?:community|group|tribe|circle|membership|facebook group|private group)", _rl))
        # A DELAYED / exit-intent newsletter POP-UP is a modal whose overlay markup loads with the page but only
        # animates in seconds LATER, after our snapshot, so the visible-geometry pop-up detector (hasPopup, from the
        # screenshot moment) misses it and we wrongly treat the late-in-DOM form as 'buried at the bottom'. Catch it
        # from the MARKUP: a known pop-up/overlay builder container. Paired with a real email field it IS a pop-up.
        _popup_markup = bool(re.search(
            r"sqs-popup|popup-overlay|overlay-popup|newsletter-?popup|optin-?(?:popup|modal|overlay)|exit-?intent|"
            r"optinmonster|mailmunch|sumome|privy-|convertbox|getsitecontrol|hello-?bar|popmake|popup-maker|"
            r"pum-overlay|elementor-popup|om-holder|poptin|wisepops|justuno", _rl))
        row["popup_optin"] = bool((row["has_popup"] or _popup_markup) and row["html_optin"])
        if row["popup_optin"]:
            row["has_popup"] = True     # a pop-up the geometry pass missed is still a pop-up thrown at cold visitors
        row["big_texts"] = (vis or {}).get("bigTexts") or []          # candidate lines the AI picks the headline from
        row["client_logos"] = (vis or {}).get("clientLogos") or []    # brand names from logo ALT text (screenshot can't read them)
        row["logo_heading"] = (vis or {}).get("logoHeading") or ""     # the heading over the logo strip ('Trusted by industry leaders')
        if vis and vis.get("headings"):                      # clean rendered headings replace the span-split ones
            row["h2_headings"] = " | ".join(vis["headings"][:8])
        row["clean_text"] = clean_main_text(rendered_html)   # main content only, for the prominence sanity-checks
        _blinks = booking_links(rendered_html)
        row["has_booking_link"] = bool(_blinks)              # a 'Book' button wired to a real scheduler = a booking
        row["booking_link_count"] = len(_blinks)             # many distinct session links = booking lost among options
        row["has_booking_embed"] = bool(_BOOKING_EMBED_RE.search(rendered_html))   # a LIVE inline calendar on the page
        row["optin_inline_above_fold"] = _optin_af           # a real email input, inline + above the fold, not a popup
        proof = detect_proof_links(rendered_html)
        row["proof_link_labels"] = proof["labels"]
        row["proof_external_reviews"] = proof["external_reviews"]
        thumb = "data:image/png;base64," + base64.b64encode(png).decode()
        # Full-page shot for the vision scoring call. Only keep it if it's under Anthropic's ~5MB/image limit;
        # a giant page falls back to text-only scoring rather than erroring the whole audit.
        if png_full:
            b64_full = base64.b64encode(png_full).decode()
            if len(b64_full) < 4_800_000:
                row["screenshot_b64"] = b64_full
        return row, thumb
    except Exception:
        return None, None

# ---------------------------------------------------------------- scoring
def score_site(row):
    """Run the 10 validated criteria against a scraped row (persuasion-weighted total)."""
    r = types.SimpleNamespace(**row)
    scores = {name: fn(r) for name, fn in S.CRITERIA}
    total = S.weighted_total(scores)
    return scores, total, round(total / 10)

def tier(total_100):
    if total_100 >= 80: return "strong"
    if total_100 >= 60: return "decent"
    if total_100 >= 40: return "weak"
    return "poor"

# ---------------------------------------------------------------- AI critique (optional layer)
CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline_problem": {"type": "string"},
        "why_it_costs_clients": {"type": "string"},
        "top_fixes": {"type": "array", "items": {"type": "string"}},
        "money_left_on_table": {"type": "string"},
    },
    "required": ["headline_problem", "why_it_costs_clients", "top_fixes", "money_left_on_table"],
    "additionalProperties": False,
}

# The AI re-scores these CONTENT criteria by reading the page (technical_health stays rule-based, it's factual).
# proof_cred is the MERGED proof+credibility criterion; the corpus scorer still keeps them separate for its stats.
# ---- FLAG-JUDGE: specificity + clarity are no longer scored by the AI (a vibe number that drifts). The AI emits
# structured FLAGS; these PURE, DETERMINISTIC Python judges turn the flags into a score. Same flags -> same score,
# every run, and every gate is auditable. Every lookup is .get()-defaulted and type-coerced so a missing key, a null,
# a string 'true'/'false', or a non-dict payload can NEVER raise. (Safeguard 1: malformed-JSON fail-safe.)
def _flag(v):
    """Coerce ANY JSON value to a strict bool. Handles real bools, numbers, and string variants. NOTE: a naive
    bool('false') is True in Python, so we must test the string explicitly — this is the whole point of the helper."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "y")
    return False

def _as_int(v, default=0):
    """Coerce ANY JSON value to a strict int, safely ('3', 3.0, None, junk all handled)."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default

def judge_specificity(f):
    """IMMUTABLE JUDGE -> 0-10 from specificity flags. Breadth cap and generic gate are hard-wired, not felt."""
    f = f if isinstance(f, dict) else {}
    demo = _flag(f.get("specific_demographic"))
    pain = _flag(f.get("concrete_pain"))
    mech = _flag(f.get("unique_mechanism"))
    breadth = _as_int(f.get("distinct_audiences_or_problems"), 1)
    # UNRELATED SERVICE GATE (runs FIRST, no exemption): a page selling genuinely DIFFERENT delivery categories or
    # buyer groups (e.g. couples counselling + in-person kink/rope experiences + online corporate mentorship) is a
    # positioning failure, full stop. These are NOT facets of one niche, so the demo+pain facet exemption below must
    # NOT rescue them -- a page can name a sharp audience and a real pain for EACH separate business and still leave a
    # cold visitor unable to tell what this site is. Hard floor 3.
    if _flag(f.get("unrelated_service_categories")):
        return 3
    # BREADTH HARD CAP: several genuinely DIFFERENT audiences/problems land for no one -> cap 3. EXEMPTION: a page that
    # has BOTH a specific demographic AND a concrete pain is a focused niche described in facets, not real breadth, so
    # a facet miscount can never nuke it -- it skips the cap and is judged on its merits below.
    if breadth >= 2 and not (demo and pain):
        return 3
    if demo and pain and mech:
        return 9                                    # focused audience + concrete pain + a real 'how'
    if demo and pain:
        return 7                                    # focused audience + concrete pain, no differentiated how
    if demo or pain:
        return 5                                    # exactly one is concrete, the other generic
    named = bool(f.get("generic_tokens")) or bool(f.get("demographic_quote")) or bool(f.get("pain_quote"))
    return 3 if named else 1                        # named-but-generic -> 3; nothing named -> 1

def judge_clarity(f):
    """IMMUTABLE JUDGE -> 0-10 from first-screen clarity flags."""
    f = f if isinstance(f, dict) else {}
    demo = _flag(f.get("hero_specific_audience"))
    prob = _flag(f.get("hero_concrete_problem_or_outcome"))
    if demo and prob:
        return 9                                    # right person sees themselves AND the change
    if demo or prob:
        return 7                                    # one specific element, recognises themselves fast
    if _flag(f.get("hero_is_broad_everyone_appeal")):
        return 3
    if _flag(f.get("hero_is_metaphor_or_feeling_only")):
        return 4
    if _flag(f.get("hero_names_field_or_category")):
        return 4                                    # names the area, not the person
    return 2                                        # no field/topic clue at all

def judge_symptom_resonance(f):
    f = f if isinstance(f, dict) else {}
    if f.get("generic_tokens_found") and not _flag(f.get("uses_situational_symptoms")):
        return 3
    if _flag(f.get("uses_situational_symptoms")) and f.get("pain_quote"):
        return 7
    return 4

def judge_perceived_friction(f):
    f = f if isinstance(f, dict) else {}
    if _flag(f.get("requires_immediate_live_call")):
        return 3
    if _flag(f.get("is_micro_commitment")):
        return 8
    return 5

def judge_risk_reversal(f):
    f = f if isinstance(f, dict) else {}
    if _flag(f.get("guarantee_present")) and f.get("safety_net_quote"):
        return 8
    return 3

def judge_proof_cred(f):
    f = f if isinstance(f, dict) else {}
    if _flag(f.get("has_verified_platform_screenshots")):
        return 8
    return 3

def judge_offer_relevance(f):
    f = f if isinstance(f, dict) else {}
    if _flag(f.get("offer_matches_stated_pain")) and f.get("core_offer_statement"):
        return 8
    if f.get("core_offer_statement") and not _flag(f.get("offer_matches_stated_pain")):
        return 5
    return 2

def judge_intent_flow(f):
    f = f if isinstance(f, dict) else {}
    count = _as_int(f.get("competing_paths_count"), default=0)
    if _flag(f.get("action_overload_detected")) or count >= 3:
        return 3
    if count <= 1:
        return 8
    return 5

# All 8 criteria are now flag-judged; AI_SCORE_CRIT is empty (no AI-scored criteria).
AI_SCORE_CRIT = []
FLAG_CRIT = {
    "clarity_5sec": ("clarity_flags", judge_clarity),
    "specificity": ("specificity_flags", judge_specificity),
    "symptom_resonance": ("symptom_resonance_flags", judge_symptom_resonance),
    "proof_cred": ("proof_cred_flags", judge_proof_cred),
    "offer_relevance": ("offer_relevance_flags", judge_offer_relevance),
    "intent_flow": ("intent_flow_flags", judge_intent_flow),
    "perceived_friction": ("perceived_friction_flags", judge_perceived_friction),
    "risk_reversal": ("risk_reversal_flags", judge_risk_reversal),
}
# The AI EXTRACTS these flags (it does not score) for all 8 criteria. Pure Python judges turn the flags into scores.
# Every boolean carries its grounding QUOTE so a 'true' is evidenced and auditable.
_SPECIFICITY_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "specific_demographic": {"type": "boolean"}, "demographic_quote": {"type": "string"},
    "concrete_pain": {"type": "boolean"}, "pain_quote": {"type": "string"},
    "unique_mechanism": {"type": "boolean"}, "mechanism_quote": {"type": "string"},
    "generic_tokens": {"type": "array", "items": {"type": "string"}},
    "distinct_audiences_or_problems": {"type": "integer"},
    # UNRELATED SERVICE GATE: separate from the breadth count on purpose. Breadth counts audiences/problems and is
    # exempted when demo+pain are both true (a focused niche described in facets). THIS flag is about the page
    # selling genuinely DIFFERENT delivery categories or buyer groups, which no facet exemption may excuse.
    "unrelated_service_categories": {"type": "boolean"},
    "unrelated_categories_list": {"type": "array", "items": {"type": "string"}}},
    "required": ["specific_demographic", "demographic_quote", "concrete_pain", "pain_quote", "unique_mechanism",
                 "mechanism_quote", "generic_tokens", "distinct_audiences_or_problems",
                 "unrelated_service_categories", "unrelated_categories_list"]}
_CLARITY_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "hero_quote": {"type": "string"}, "hero_specific_audience": {"type": "boolean"},
    "hero_concrete_problem_or_outcome": {"type": "boolean"}, "hero_names_field_or_category": {"type": "boolean"},
    "hero_is_metaphor_or_feeling_only": {"type": "boolean"}, "hero_is_broad_everyone_appeal": {"type": "boolean"}},
    "required": ["hero_quote", "hero_specific_audience", "hero_concrete_problem_or_outcome",
                 "hero_names_field_or_category", "hero_is_metaphor_or_feeling_only", "hero_is_broad_everyone_appeal"]}

_SYMPTOM_RESONANCE_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "pain_quote": {"type": "string"},
    "uses_situational_symptoms": {"type": "boolean"},
    "generic_tokens_found": {"type": "array", "items": {"type": "string"}}},
    "required": ["pain_quote", "uses_situational_symptoms", "generic_tokens_found"]}

_PROOF_CRED_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "has_verified_platform_screenshots": {"type": "boolean"}},
    "required": ["has_verified_platform_screenshots"]}

_OFFER_RELEVANCE_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "core_offer_statement": {"type": "string"},
    "offer_matches_stated_pain": {"type": "boolean"}},
    "required": ["core_offer_statement", "offer_matches_stated_pain"]}

_INTENT_FLOW_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "action_overload_detected": {"type": "boolean"},
    "competing_paths_count": {"type": "integer"}},
    "required": ["action_overload_detected", "competing_paths_count"]}

_PERCEIVED_FRICTION_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "is_micro_commitment": {"type": "boolean"},
    "requires_immediate_live_call": {"type": "boolean"}},
    "required": ["is_micro_commitment", "requires_immediate_live_call"]}

_RISK_REVERSAL_FLAGS = {"type": "object", "additionalProperties": False, "properties": {
    "guarantee_present": {"type": "boolean"},
    "safety_net_quote": {"type": "string"}},
    "required": ["guarantee_present", "safety_net_quote"]}

AI_ANALYSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        # The AI reads the SCREENSHOT to identify the real headline (was a brittle biggest-font JS heuristic):
        "main_headline": {"type": "string"},     # the exact biggest headline a cold visitor reads first
        # Narrow VISION fact: is there a visible online STORE on the page?
        "shop_reason": {"type": "string"},
        "has_visible_shop": {"type": "boolean"},
        "specificity_flags": _SPECIFICITY_FLAGS,           # AI extracts, judge_specificity scores
        "clarity_flags": _CLARITY_FLAGS,                   # AI extracts, judge_clarity scores
        "symptom_resonance_flags": _SYMPTOM_RESONANCE_FLAGS,
        "proof_cred_flags": _PROOF_CRED_FLAGS,
        "offer_relevance_flags": _OFFER_RELEVANCE_FLAGS,
        "intent_flow_flags": _INTENT_FLOW_FLAGS,
        "perceived_friction_flags": _PERCEIVED_FRICTION_FLAGS,
        "risk_reversal_flags": _RISK_REVERSAL_FLAGS,
        "headline_problem": {"type": "string"},
        "why_it_costs_clients": {"type": "string"},
        "top_fixes": {"type": "array", "items": {"type": "string"}},
        "money_left_on_table": {"type": "string"},
    },
    "required": ["main_headline", "shop_reason", "has_visible_shop",
                 "specificity_flags", "clarity_flags",
                 "symptom_resonance_flags", "proof_cred_flags",
                 "offer_relevance_flags", "intent_flow_flags",
                 "perceived_friction_flags", "risk_reversal_flags",
                 "headline_problem", "why_it_costs_clients", "top_fixes", "money_left_on_table"],
}

VOICE = (
    "You are the diagnostic voice of David Poole, who has read 10,955 coaching websites. "
    "Write blunt, warm, plain-spoken, like a straight-talking friend who knows marketing. Use plain everyday "
    "words a 12-year-old would understand. It's about WORD CHOICE, not sentence length, keep a natural length "
    "and do NOT chop everything into tiny sentences. Be obvious, never clever, you are NOT writing for the "
    "Guardian. Talk to the coach directly as 'you'. Be specific to THEIR site, quote their actual headline and "
    "wording. Diagnose like a doctor, not a cheerleader.\n"
    "PITCH RULE (important): never hand the coach a finished headline or line to copy. If you show an example to "
    "illustrate the SHAPE of a better headline, say plainly it is for illustration only, and that the real words "
    "have to come from researching what their buyer actually says, not from a guess, because marketing must be "
    "built on evidence, not estimation. Do NOT tell the coach they are 'guessing', and avoid the word 'guessing' "
    "about anyone.\n"
    "ACCURACY RULE: never invent numbers or percentages you cannot actually measure (e.g. 'you're losing 60% of "
    "visitors', 'this costs you thousands'). We are built on accuracy, not estimation. Describe what happens in "
    "plain words, not made-up stats. Only use numbers we actually gave you (the scores, the market averages).\n"
    "HARD RULES. Never use em dashes. Never use these words or phrases, they read as AI slop and are banned: "
    "'land'/'lands'/'landed' (a visitor 'arrives' or 'comes to your page', NEVER 'lands'), 'quietly', 'the gap', "
    "'that's the gap', 'that's where the clients go', "
    "'coaches who win', 'you're too close to it', 'that spot is open', 'shallow end', 'drift', 'rescue', "
    "'different job same page', 'here's the harder truth', 'delve', 'leverage', 'robust', 'navigate', 'unlock', "
    "'elevate', 'harness', 'foster', 'realm', 'tapestry', 'testament', 'in today's world', 'furthermore', "
    "'moreover', 'additionally', 'ultimately', \"it's not just X, it's Y\". No neat bow endings that restate "
    "everything. If a 12-year-old would not instantly get a word, use a simpler one."
)

# Belt-and-braces: if the AI slips a banned word or an em dash, fall back to the safe rule-based critique.
_BANNED_RE = re.compile(
    r"\b(lands?|landed|quietly|drift(?:s|ed|ing)?|rescue[sd]?|guessing|leverage[sd]?|unlock(?:s|ed|ing)?|"
    r"elevat(?:e|es|ed|ing)|harness(?:es|ed|ing)?|delve[sd]?|robust|tapestry|testament|furthermore|moreover)\b"
    r"|the gap|shallow end|—", re.I)

def ai_critique(row, scores, score_10):
    """Claude-written diagnosis. Returns None if no key / call fails (caller falls back)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None

    weakest = sorted(scores.items(), key=lambda kv: kv[1])[:4]
    weak_txt = "\n".join(f"- {LABELS[k]}: {v}/10 (market avg {BENCH[k]})" for k, v in weakest)
    facts = (
        f"Biggest headline a visitor reads first (largest text on the page): {row.get('visual_headline') or row.get('h1') or '(none)'}\n"
        f"H1 tag (what Google reads, can differ or be missing): {row.get('h1_tag') or row.get('h1') or '(none found)'}\n"
        f"Page title: {row.get('page_title')}\n"
        f"Sub-headings: {str(row.get('h2_headings'))[:400]}\n"
        f"Main CTA text: {row.get('cta_text') or '(none)'}\n"
        f"Testimonials ON the homepage: {'yes' if row.get('testimonial_text') else 'no'}\n"
        f"Proof linked off-page (a testimonials/reviews page we spotted but did NOT visit): {row.get('proof_link_labels') or 'none'}\n"
        f"Shows pricing: {'yes' if row.get('pricing_mentions') else 'no'}\n"
        f"Captures emails (opt-in): {row.get('optin_present')}\n"
        f"Throws a pop-up at cold visitors: {'yes' if row.get('has_popup') else 'no'}\n"
        f"Word count: {row.get('word_count')}\n"
        f"Overall score: {score_10}/10 (market average {MARKET_AVG_10}, top 10% score {TOP10_10}+)\n"
        f"Weakest areas:\n{weak_txt}"
    )
    prompt = (
        "Here is the automated analysis of one coach's HOMEPAGE. We only looked at their homepage, not their "
        "whole website, so scope everything to 'your homepage', never 'your site'. Diagnose it.\n\n"
        f"{facts}\n\n"
        "Give me: (1) the single most damaging homepage problem, named specifically; "
        "(2) why it's costing them clients; (3) 2-3 concrete fixes they could make this week; "
        "(4) a sharp line about the money walking out the door.\n"
        "Frame EVERYTHING as how a potential BUYER perceives them, whether, in the first few seconds, a visitor sees "
        "this coach as the answer to THEIR problem. This is marketing and buyer psychology, NOT a website-quality "
        "checklist. Make clear the surface issue is a symptom of a deeper problem: they don't understand their buyer "
        "well enough. Write plainly, like a 12-year-old could follow it. Plain everyday words, natural length (NOT "
        "chopped into tiny sentences). No jargon, no buzzwords, no em dashes. We are built on accuracy, not guesswork. "
        "You may cite our data: of 10,955 coaching sites, the average homepage scores just 3.7/10, 86% fail the "
        "five-second test, and only about 1 in 8 speak their buyer's language (the rest talk expert-to-expert). "
        "Rules: Quote their actual headline or wording back at least once so they know you really read their page. "
        "Only claim what the analysis supports, if a signal is 'none found', say 'we didn't spot X on your homepage', "
        "never a flat 'you have no X' (it might be elsewhere on the site). Do NOT treat hidden pricing as a mistake, "
        "many coaches choose that deliberately; if you mention it, be balanced. If you praise something, keep it to "
        "the technical foundations (secure, loads well), not their content."
    )
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=AUDIT_MODEL,
        max_tokens=1200,
        system=[{"type": "text", "text": VOICE, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": CRITIQUE_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    result = json.loads(text)
    if _BANNED_RE.search(json.dumps(result)):
        return None      # a banned word slipped through: use the safe rule-based critique instead
    return result

# NOTE: rubric_txt below is built ONLY from AI_SCORE_CRIT. Since AI_SCORE_CRIT = [], rubric_txt is always empty.
# The entries here are kept for reference only — all 8 criteria are now flag-judged, not rubric-scored.
_AI_RUBRIC = {
    "clarity_5sec": "In 5 seconds, does the RIGHT person (a cold visitor who HAS this problem) know this page is for them, and sense what changes? A headline that names the reader's real SITUATION or PROBLEM in their words is strong reader-first copy, score it high, NEVER call that 'abstract' or dock it for being 'about the reader'. Grade on a SPECTRUM, not just sharp-vs-vague: 9-10 = the right person instantly sees themselves AND senses the outcome; 7-8 = sharply names their real situation/problem so they recognise themselves fast, even if the outcome/service isn't spelled out; 5-6 = names a clear audience OR a clear service/outcome but not sharply, a visitor gets the gist but doesn't feel 'that's exactly me'. A clever METAPHOR or evocative line that only gestures at a FEELING ('you can't read the label from inside the jar', 'you're stuck', 'something feels off', 'reclaim your spark') WITHOUT naming a specific audience OR a concrete problem in plain words is a 3-4, NOT a 5-6, no matter how relatable it sounds, because a cold visitor still can't tell if it's for THEM or what you actually fix. A VAGUE / feel-good outcome ('build authentic connections', 'live your best life', 'find your purpose', 'transform your life', 'unlock your potential') does NOT count as a concrete outcome, so audience-named + fluffy-outcome caps at 5, it does NOT reach 7-8; only the reader's real SITUATION / PROBLEM or a CONCRETE specific outcome they'd recognise earns 7-8. A hero with BROAD, everyone-welcome appeal, general all-purpose life coaching (no single person or problem signalled), or one juggling several DIFFERENT audiences or problems at once, caps at 3, because a cold visitor can't tell in five seconds it is aimed at THEM specifically; 3-4 = names a broad CATEGORY, FIELD or TOPIC (even as a vague tagline, e.g. 'Divorce Differently' names the field divorce; 'leadership coaching'; or a generic benefit like 'live your best life'), so a cold visitor at least knows what area this is about, but the right person isn't singled out and doesn't feel 'that's exactly me'; 0-2 = gives NO clue what field or topic it's even about: just the coach's personal NAME, or pure field-less abstraction ('You Are Worthy', 'Reimagine what's possible'), so a cold visitor can't even tell what area you work in. RESERVE 0-2 for a name or a field-less abstraction ONLY; the moment the headline names the topic/field at all, it is at least a 3, never a 2. Judge the WHOLE above-fold, not just the single biggest line: if the hero has an 'I help [who] [do what]' line (e.g. 'I help entrepreneurs plan, start and grow businesses') OR any line that names the field or audience, clarity is AT LEAST 3, even when the biggest line is a name or a stats-brag ('Coached 1000+ entrepreneurs'). A 2 requires that NOTHING above the fold names the field or the audience.",
    "specificity": "Is the page FOCUSED on ONE clear audience and ONE clear problem, in their words? Here NARROWNESS is the whole point: focus scores high, breadth scores low. HARD CAP AT 3: broad appeal ('for anyone ready to grow', 'helping people live their best life'), general all-purpose life coaching with no named niche, OR a page that spreads across SEVERAL different audiences or problems at once (e.g. 'career change, redundancy, mid-life, identity shift' or 'career AND relationships AND health') is trying to be for everyone, so it lands for no one. Naming five problems clearly is STILL five problems, that is BREADTH not specificity, and it caps at 3 no matter how cleanly each separate item is written. To score high a page must NARROW: 8-10 = a laser-focused, singular target audience (e.g. 'executive women in tech leadership', 'newly-qualified therapists', 'founders who can't switch off after work') AND ONE clear problem stated in the buyer's own words. 6-7 = a single clear audience and one problem, but with some blur (a second audience creeping in, or the problem drawn a little broadly). 4-5 = a real single problem OR a single clear audience, but not both, and no scatter. 1-3 = broad appeal / general life coaching / several audiences or problems at once. 0 = could be literally anyone, nothing named. Judge FOCUS, not merely how clearly each separate thing is written.",
}

def ai_analyse(row, scores, score_10, ev=None):
    """ONE AI call: EXTRACT structured flags for all 8 criteria by READING the page, plus write the diagnosis.
    Pure Python judges (FLAG_CRIT) convert the flags to scores. Returns None on no-key / failure / banned words,
    so the caller falls back to the pure rule-based path."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    ev = ev or {}
    # Only the AI-SCORED criteria go in the rubric-to-score list. specificity + clarity are extracted as FLAGS instead.
    rubric_txt = "\n".join(f"- {LABELS[k]} ({k}): {_AI_RUBRIC[k]}" for k in AI_SCORE_CRIT)
    # Copy the AI reads. clean_text strips nav/menu noise, but on some markup it over-strips and leaves almost
    # nothing (e.g. one site collapsed to just "pri leadership"). So use clean_text ONLY when it actually kept the
    # bulk of the page; otherwise fall back to the full body_text, a little nav noise beats scoring an empty page.
    body = _clean(row.get("body_text")) or ""
    clean = row.get("clean_text") or ""
    # 8000 chars, not 3200: the proof section (testimonials, client logos, "since 2006", the business address) often
    # sits low on a long homepage. Cutting at 3200 hid it, and the AI then scored proof/credibility as if it were 0.
    copy = (clean if len(clean) >= max(200, 0.5 * len(body)) else body)[:8000]
    # We read TEXT. A lot of real proof/credibility is IMAGES or video (a logo strip, an "as seen on" media row,
    # video testimonials) that never reach the copy above. Detect the SIGNS so the AI credits them instead of
    # calling them zero. Run these over the FULL body_text, not the truncated copy.
    import re as _re
    full = body
    has_logos = bool(ev.get("has_logos"))
    testi_section = bool(_re.search(r"what (they|our clients|people|clients)('?re| are| ?re)? saying|"
                                    r"testimonial|success stor|case stud|our clients|as seen (on|in)|"
                                    r"featured (on|in)|as featured", full, _re.I))
    reachable = bool(_re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", full)   # a phone number
                     or _re.search(r"[A-Za-z0-9.\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", full)  # an email
                     or _re.search(r"\b\d{4,6}\b.{0,40}(street|st\.|ave|road|rd\.|parkway|suite|#\d)", full, _re.I))
    # The exact on-page text lines (biggest first). The AI picks WHICH one is the headline from the SCREENSHOT, but
    # returns the exact wording, so we never mis-transcribe a quote.
    cand_lines = row.get("big_texts") or []
    cand_txt = "\n".join(f"  - {c}" for c in cand_lines[:12]) or "  (none captured)"
    facts = (
        f"H1 tag (what Google reads): {row.get('h1_tag') or row.get('h1') or '(none found)'}\n"
        f"Sub-headings: {str(row.get('h2_headings'))[:400]}\n"
        f"Main CTA text: {row.get('cta_text') or '(none)'}\n"
        f"Testimonials ON the homepage: {'yes' if row.get('testimonial_text') else 'no'}\n"
        f"Proof linked off-page (spotted, not visited): {row.get('proof_link_labels') or 'none'}\n"
        f"Client/'worked with' logo strip detected on the page: {'yes' if has_logos else 'no'}\n"
        f"The logo strip is headed: {row.get('logo_heading') or '(no heading captured)'} "
        f"(a 'trusted by' / 'our clients' style heading DOES count as claiming these as clients).\n"
        f"Brand names READ FROM THE LOGO STRIP (image alt text, i.e. what the logos actually are, which a "
        f"downscaled screenshot can't show you): {', '.join((row.get('client_logos') or [])[:20]) or '(none detected)'}. "
        f"Judge for YOURSELF whether you recognise these as major/household brands; if you do, a 'trusted by' claim "
        f"naming them is a real, costly-to-fake signal, not an unrecognisable logo wall.\n"
        f"A testimonials / clients / 'as seen on' section is present on the page: {'yes' if testi_section else 'no'}\n"
        f"A reachable business (address, phone or email) is on the page: {'yes' if reachable else 'no'}\n"
        f"Lead-capture element detected: {ev.get('capture', {}).get('desc') or 'none'} "
        f"(a contact form is for people ready to reach out, NOT lead capture; only a FREE resource / guide / "
        f"checklist is a real magnet; a newsletter alone is weak). Do not call it anything other than what's here.\n"
        f"Shows pricing: {'yes' if row.get('pricing_mentions') else 'no'}\n"
        f"Has a genuine priced online SHOP on the page (add-to-cart / WooCommerce / Shopify): {'yes' if row.get('has_shop') else 'no'} "
        f"(the CTA can only score 2-3 for 'shop chaos' when this is YES; with NO shop, cluttered soft CTAs are a 4, never lower).\n"
        f"For context, across {websites_read_count():,} coaching homepages the average score is {MARKET_AVG_10}/10 "
        f"and the top 10% score {TOP10_10}+. Score THIS page on its own merits, not relative to that."
    )
    prompt = (
        "You are diagnosing ONE coach's HOMEPAGE (homepage only, so scope everything to 'your "
        "homepage', never 'your site'). Your job: extract structured flags for all 8 criteria by reading the ACTUAL "
        "page copy below, then write the diagnosis. Judge exactly what a cold buyer would perceive, be strict and "
        "honest, no benefit of the doubt for things that aren't there.\n"
        "You are given a FULL-PAGE SCREENSHOT of the homepage as well as the text. USE THE SCREENSHOT to judge "
        "anything visual, a client logo strip, an 'as seen on' media row (TV networks, big publications), named "
        "client logos (companies, universities), video testimonials, headshots, design and hierarchy. Read the "
        "logos and media names you can see and weigh them: recognised TV networks / national media / well-known "
        "companies or universities are STRONG credibility; a specific NAMED endorsement from a recognised authority "
        "(a well-known bestselling author) is STRONG, not 'just one quote', it is costly to fake. But an UNLABELLED "
        "wall of ordinary organisation logos is AMBIGUOUS, not automatic proof: those orgs could be audiences he "
        "spoke in front of, not clients or media, so treat it as middling unless you recognise the logos as media or "
        "the page labels them ('our clients', 'as seen in'). Use "
        "the TEXT for wording, story, clarity and offer. (If no screenshot is provided, judge from the text and the "
        "FACTS block, and lean on the FACTS flags for logo strips / testimonials / a reachable business.)\n"
        "READ THE HEADLINE STRAIGHT OFF THE SCREENSHOT:\n"
        "has_visible_shop: look at the SCREENSHOT and answer true/false in shop_reason then has_visible_shop: does "
        "the page visibly show an online STORE, i.e. TWO OR MORE products each with a price AND a buy / add-to-cart "
        "button? A single 'buy my book' link, a booking button, or a shop plugin with no visible products = false. "
        "Only a genuine multi-product store shown on the page = true.\n"
        "main_headline: the single biggest headline a cold visitor reads FIRST (the largest text near the top, the "
        "hero line, not a nav link or a button, and NOT a cookie-consent pop-up). Return its EXACT wording. It will "
        "almost always be one of the ON-PAGE LINES listed below, copy that line verbatim; only if the headline "
        "genuinely isn't in that list, read it exactly off the screenshot. Never return the browser-tab/site name.\n\n"
        "EXTRACT FLAGS FOR ALL 8 CRITERIA (they are all judged in code, not by a score from you). Read as a harsh, "
        "skeptical stranger: assume GENERIC until the page proves SPECIFIC.\n"
        "GENERIC AUDIENCE tokens (a bare category, do NOT count as a specific audience): people, professionals, "
        "individuals, entrepreneurs, business owners, leaders, executives, managers, women, men, high-achievers, "
        "'ambitious X', anyone, everyone.\n"
        "GENERIC PROBLEM/OUTCOME tokens (a fluffy state, do NOT count as a concrete problem): confidence, clarity, "
        "mindset, alignment, purpose, potential, growth, transformation, balance, fulfilment, overwhelm, stuck, "
        "thrive, authentic, best self, next level, breakthrough, limiting beliefs, success, freedom, happiness.\n"
        "Judge each element AS A WHOLE: a generic word INSIDE a concrete phrase still counts as concrete ('no "
        "confidence to speak up in board meetings' = a concrete situation). A token only fails when the element is "
        "expressed SOLELY via generic tokens.\n"
        "specificity_flags: specific_demographic = a REAL role+context (not a bare category), with demographic_quote; "
        "concrete_pain = a REAL situation in the buyer's words (not a fluffy state), with pain_quote; unique_mechanism "
        "= a NAMED method or a CONCRETE measurable outcome (not 'coaching/support'), with mechanism_quote; "
        "generic_tokens = the fluff words the page leans on; distinct_audiences_or_problems = how many GENUINELY "
        "DIFFERENT, UNRELATED audiences or problems it serves. Count SEPARATE audiences ('entrepreneurs AND stay-at-home "
        "mums AND retirees' = 3) or unrelated problems ('career change, weight loss, grief' = 3). Do NOT count MULTIPLE "
        "FACETS OF ONE niche as separate: 'women with late-diagnosed ADHD navigating their career' is ONE audience "
        "described by facets (women + ADHD + career + late diagnosis), so count 1, not 4. If the facets all describe the "
        "SAME person, the count is 1.\n"
        "THE UNRELATED SERVICE GATE (a MULTI-OFFER CONFUSION TRAP, judge this HARSHLY and separately from the facet "
        "rule above): unrelated_service_categories = TRUE when the page sells genuinely DIFFERENT DELIVERY CATEGORIES "
        "or genuinely DIFFERENT BUYER GROUPS side by side. This is an AUTOMATIC POSITIONING FAILURE and it is NOT "
        "excused by the page naming a sharp audience or a real pain, because it can do that for EACH separate "
        "business and a cold visitor STILL cannot tell what this site is for. Set it TRUE when the page mixes things "
        "like: couples/relationship work AND individual corporate or executive mentorship (different buyer entirely, "
        "a couple is not a solo professional); IN-PERSON PHYSICAL or intimate/kink experiences (rope, Shibari, tantra, "
        "bodywork, retreats) AND online/digital consulting, courses or mentorship (different delivery category, "
        "different risk, different buyer); therapy or healing AND business/revenue coaching; done-for-you services AND "
        "teaching/courses. Ask yourself plainly: would ONE buyer plausibly want ALL of these, or has this coach "
        "stacked several separate businesses onto one homepage? If it is several businesses, set it TRUE. When it is "
        "TRUE you MUST also list each separate category in unrelated_categories_list (e.g. ['couples relationship "
        "sessions', 'in-person rope/Shibari experiences', 'online mentorship for corporate high-achievers']) and you "
        "MUST set distinct_audiences_or_problems to at least the number of categories you listed (2+). Only set it "
        "FALSE when every offer on the page is the SAME kind of help, delivered the SAME way, to the SAME buyer.\n"
        "clarity_flags (the FIRST SCREEN / biggest text only): hero_quote = the headline verbatim; "
        "hero_specific_audience = names a SPECIFIC audience (not generic); hero_concrete_problem_or_outcome = a "
        "CONCRETE situation/outcome (not fluffy); hero_names_field_or_category = at least names the topic/area; "
        "hero_is_metaphor_or_feeling_only = gestures at a feeling, names no person/problem; "
        "hero_is_broad_everyone_appeal = 'for anyone' / general all-purpose life coaching.\n\n"
        "ADDITIONAL FLAG CRITERIA — extract these from the FULL PAGE COPY:\n"
        "symptom_resonance_flags: pain_quote = verbatim line from the copy that best describes the buyer's daily pain "
        "(empty string if none); uses_situational_symptoms = true if the copy describes concrete, situational daily "
        "pain (not generic tokens like 'mindset', 'clarity', 'overwhelm', 'transform', 'best self'); "
        "generic_tokens_found = list of generic coaching platitude words found on the page.\n"
        "proof_cred_flags: has_verified_platform_screenshots = true ONLY if you can visually identify in the "
        "screenshot that testimonials are shown as screenshots of real Google/Facebook/Trustpilot review cards "
        "(identifiable by native platform UI: star icons, profile circles, local guide labels, or relative timestamps "
        "like '3 days ago'). A static star graphic or text claim alone = false.\n"
        "offer_relevance_flags: core_offer_statement = the clearest offer description on the page (empty string if "
        "none); offer_matches_stated_pain = true if the core offer directly addresses the specific pain described in "
        "symptom_resonance_flags.\n"
        "intent_flow_flags: action_overload_detected = true if there are 3+ genuinely different jobs a cold visitor "
        "is asked to do (book a call AND buy a product AND download something AND listen to podcast = 4 different "
        "jobs = overload); competing_paths_count = exact count of distinct next-step actions.\n"
        "perceived_friction_flags: requires_immediate_live_call = true if the ONLY clear next step for a cold "
        "visitor is a sales call or consultation (no free resource, no low-commitment option, no email capture); "
        "is_micro_commitment = true if there is a clearly visible low-friction first step (a free resource to "
        "download, a quiz, a checklist, a short video series they can start without booking a call).\n"
        "risk_reversal_flags: guarantee_present = true if any money-back guarantee, refund policy, or explicit risk "
        "reversal is mentioned on the homepage; safety_net_quote = verbatim quote of the guarantee or risk-reversal "
        "language (empty string if none).\n\n"
        f"THE PAGE'S ON-PAGE TEXT LINES (biggest first, pick the headline from here):\n{cand_txt}\n\n"
        f"FACTS:\n{facts}\n\n"
        f"THE ACTUAL PAGE COPY (judge story/specificity/offer/proof from THIS):\n\"\"\"\n{copy}\n\"\"\"\n\n"
        "For the diagnosis give: (1) the single biggest thing in the way, named specifically and quoting their "
        "wording; (2) what it's costing them, and make this one FELT and present-tense, a real person who needs "
        "exactly what they do arriving, feeling nothing, and leaving for someone else, not an abstract explanation "
        "(still no invented numbers); (3) 2-3 concrete fixes; "
        "(4) a sharp bottom line. Frame everything as how a cold BUYER perceives them in the first few seconds, "
        "this is marketing and buyer psychology, not a website-quality checklist. The deeper problem is almost "
        "always the same: they don't understand their buyer well enough. Only claim what the copy supports; if a "
        "signal is missing say 'we didn't spot X on your homepage', never a flat 'you have no X'.\n"
        "DO NOT INVENT DETAILS YOU CAN'T VERIFY (two specific traps): (1) TESTIMONIAL ATTRIBUTION, describe only what "
        "is actually there. If a testimonial shows NO name, say 'anonymous, no name attached', do NOT claim 'first "
        "names only' or 'full names' or 'with photos' unless you can actually see them; getting this wrong is a "
        "factual error the coach will catch. (2) PROMINENCE, the ON-PAGE LINES listed below are the BIGGEST lines on "
        "the page (the hero / top area). If a problem-naming line is IN that list, it is PROMINENT, so NEVER describe "
        "it as 'buried below the fold' or 'hidden lower down'. A line can only be called buried if it is NOT among "
        "those biggest lines. Also keep any COUNT you state (e.g. how many packages/offers) CONSISTENT across every "
        "note and the diagnosis, do not say 'eight' in one place and 'six' in another.\n"
        "BROAD vs NARROW: if the coach clearly serves SEVERAL related problems (e.g. all compulsive behaviours: "
        "drink, food, work), do NOT tell them to niche down to one, they'll rightly say 'but I serve all of them'. "
        "The fix is to name the SHARED problem plainly and concretely, and where it helps list a few examples "
        "(e.g. 'whether it's drink, food, or work') so each person instantly recognises themselves. Clarity of the "
        "shared problem is the goal, not narrowness.\n"
        "NAME AS HEADLINE: if the biggest headline is just the coach's own name, that IS a real weakness even if "
        "they're well known, so flag it, but argue it with PROOF rather than a flat rule. The most famous coaches "
        "alive, Tony Robbins, Mel Robbins, Jay Shetty, Marie Forleo, Brene Brown, do NOT lead with their name, they "
        "lead with what they do for the reader. So: 'if even they don't rely on their name, a cold stranger won't "
        "stay for yours'. A name is not a reason to stay; the problem you solve is. (Their strong proof and copy "
        "lower down is then wasted on the visitors who already left.) Do not soften this because they look "
        "established, hold the line: a name headline fails the five-second test.\n"
        "LENGTH: keep every one of those paragraphs SHORT, 3 to 4 sentences, about 55 words MAX. A wall of text "
        "doesn't get read. Make your point and stop. Same for each fix, one crisp sentence.\n"
        "NEVER use the word 'guessing' about anyone, not the coach and not the visitor. Plainly: a visitor 'has no "
        "way to tell'. Say 'badges' not 'credentials'. No em dashes, no banned words.\n"
        "ANCHOR EVERY FAULT TO THE COPY, NOT THE PERSON: never scold the coach or imply she doesn't understand her "
        "own clients (lines like 'it's about you, not their struggle' read as a telling-off). She knows her people; "
        "the COPY just doesn't show it yet. Point at the headline / the words, e.g. 'you know these parents cold, the "
        "headline just doesn't show it', not at her.\n"
        "MULTI-SERVICE HEADLINE: if the coach clearly offers SEVERAL real services or problems (e.g. sleep, feeding, "
        "behaviour, weaning), do NOT hand them a single-service example headline ('Sleep training for exhausted "
        "parents') that quietly throws the rest away. Offer the fix as a MENU of the real problems they solve (e.g. "
        "'sleep, feeding, behaviour or overwhelm') so the headline still covers what they actually do.\n"
        "DON'T TELL THEM TO SHOW PROOF THEY DON'T HAVE: if there are no reviews/testimonials on the page, do NOT say "
        "'add a screenshot of your Google review' or 'show your Trustpilot rating', that implies the asset already "
        "exists. Say the true version: 'ask a happy client to post a Google or Facebook review, then show it on the "
        "page.' Only reference a review/rating as existing if one is actually in the copy.\n"
        "NEVER INVENT AN ENTITY OR A QUOTE: do not name a competitor, invent a rival's headline, quote a real-sounding "
        "source, cite a statistic, a study, a company, or any fact that is NOT in the page copy above. Do NOT write "
        "things like 'they click away to a competitor who says X' with an invented X, that is fabrication. If you show "
        "an EXAMPLE headline or line, present it as your own generic illustration ('a headline like…', 'e.g. …') and "
        "NEVER attribute it to a competitor, a customer, the media, or any named source. Only real names/quotes that "
        "actually appear in the copy may be repeated.\n"
        "PROOF MUST BE GROUNDED WORD-FOR-WORD: never state a client or testimonial NAME (e.g. 'a testimonial from "
        "Jaimee Carson'), a specific MONEY figure ('$500k in extra revenue'), an award title, a media outlet, or a "
        "client company unless those exact words are in the page copy above. A downscaled screenshot is NOT permission "
        "to guess a name or a number: if you cannot read it in the copy, it does not exist, describe the proof by its "
        "FORMAT instead ('text testimonials with no photo', 'a logo strip'). Inventing one specific name or number "
        "destroys the coach's trust in the whole report."
    )
    # Show the AI the full-page screenshot so it scores what a cold buyer actually SEES (logos, media, video proof),
    # not just the text. Falls back to text-only when we couldn't grab a shot.
    content = [{"type": "text", "text": prompt}]
    shot = row.get("screenshot_b64")
    if shot:
        content.insert(0, {"type": "image",
                           "source": {"type": "base64", "media_type": "image/png", "data": shot}})
    # ANY failure here (a bad/oversized image, an API error, a timeout, malformed JSON) must fall back to the
    # rule-based path, NEVER crash the audit and blank the page. On an image error, retry once WITHOUT the image.
    for attempt in range(2):
        try:
            client = anthropic.Anthropic()
            _kw = dict(
                model=AUDIT_MODEL, max_tokens=1800,
                system=[{"type": "text", "text": VOICE, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": content}],
                output_config={"format": {"type": "json_schema", "schema": AI_ANALYSE_SCHEMA}},
            )
            # Only Haiku / older 3.x models accept an explicit temperature; Sonnet 4.6 and Opus 4.x REJECT it (400
            # 'temperature is deprecated for this model'). The newer models are stable at their default, so omit it.
            if "haiku" in AUDIT_MODEL or "claude-3" in AUDIT_MODEL:
                _kw["temperature"] = 0
            resp = client.messages.create(**_kw)
            text = next((b.text for b in resp.content if b.type == "text"), "")
            return json.loads(text)   # banned-word handling is per-field in the caller
        except Exception as e:
            # If the screenshot was the problem (too big, bad format), drop it and try once more text-only.
            if attempt == 0 and len(content) > 1 and ("image" in str(e).lower() or "size" in str(e).lower()):
                content = [c for c in content if c.get("type") != "image"]
                continue
            return None

# Every line scoped to the HOMEPAGE (that's all we looked at) and softened where detection is heuristic.
HOMEPAGE_PROBLEMS = {
    "clarity_5sec": "in the first five seconds on your homepage, it’s hard to tell who you help and what they’d get",
    "specificity": "on your homepage, it isn’t clear enough who you help or what problem you solve, a first-time visitor may not be able to tell whether you’re the right coach for them",
    "symptom_resonance": "the copy on your homepage describes coaching outcomes in abstract terms rather than the raw, daily pain your buyer actually feels",
    "proof_cred": "we didn’t spot the proof or credibility a cold buyer believes on your homepage, results, testimonials, and real reviews that show you deliver",
    "offer_relevance": "on your homepage there’s no clearly defined offer that connects to the problem you’re solving, just a vague sense of what you do",
    "intent_flow": "the page scatters a visitor across competing asks instead of pointing at one clear next step",
    "perceived_friction": "the first step your homepage asks for is too big a commitment for a cold stranger who just found you",
    "risk_reversal": "nothing on your homepage lowers the risk of saying yes, so sceptical visitors stay sceptical and leave",
}

# Imperative ACTIONS, kept distinct from the problem descriptions so the diagnosis never repeats itself.
HOMEPAGE_FIXES = {
    "clarity_5sec": "Rewrite your headline so it passes the five-second test: who it’s for, and what changes for them, in one line a stranger understands straight away.",
    "specificity": "Name the exact person you help and the exact problem, in their words. Not ‘ambitious people’, but the real situation they’re stuck in.",
    "symptom_resonance": "Replace the coaching platitudes with the buyer’s own words. Describe the physical, daily situation they’re stuck in, not the abstract outcome they’ll eventually get.",
    "proof_cred": "Add real proof: two or three client results with actual numbers, and a testimonial that names the problem you solved, ideally as a screenshot of a real review.",
    "offer_relevance": "Spell out one clear thing you fix: what it is, who it’s for, and what changes for the buyer once you’ve done it.",
    "intent_flow": "Pick one clear next step and make it the only strong action on the page. Cut or demote anything competing with it.",
    "perceived_friction": "Add a low-commitment first step, a free resource, a quiz, or a short video series, so a curious visitor can start without booking a call.",
    "risk_reversal": "Give a clear safety net: a guarantee, a refund window, or a free trial, so saying yes feels less like a gamble.",
}

def rule_critique(row, scores, score_10, ev):
    """Deterministic fallback so a prospect always gets a real, homepage-scoped diagnosis.
    Pricing is deliberately excluded here, it gets its own balanced note (see PRICING_NOTE)."""
    # Rank by PERSUASION COST, not raw score: weight (how much it moves a buyer) × how far below par it is.
    # So a weak headline ("who is this for and why") outranks missing proof — proof only matters once a
    # stranger knows the page is for them. This is what makes the "biggest thing" the right thing.
    W = getattr(S, "WEIGHTS", {})
    def _cost(k, v):
        return W.get(k, 1.0) * max(0, 7 - v)
    ranked = [k for k, _ in sorted(((k, v) for k, v in scores.items()
                                    if v is not None and k in DISPLAY_CRIT),
                                    key=lambda kv: _cost(kv[0], kv[1]), reverse=True)]
    worst_key = ranked[0]

    # Personalise the headline problem with THEIR actual wording, so it never reads like a template.
    hl = ev.get("headline", "")
    if worst_key in ("specificity", "clarity_5sec") and hl:
        problem = (f'Your headline reads “{hl}”. It doesn’t say clearly who it’s for or what changes for them, so a '
                   f'stranger can’t tell in a few seconds whether you’re for them. A headline that works names the '
                   f'person and the change they want, in their own words. We’re not going to hand you a line to copy, '
                   f'that would just be our guess, and marketing has to be built on what your buyer actually says, '
                   f'not estimation. But that’s the shape to aim for.')
    else:
        problem = HOMEPAGE_PROBLEMS.get(worst_key, "").capitalize() + "."

    # Build fixes as actions; collapse the clarity/specificity pair (same root) into one.
    fix_keys, seen_who = [], False
    for k in ranked:
        if k in ("specificity", "clarity_5sec"):
            if seen_who:
                continue
            seen_who = True
        fix_keys.append(k)
        if len(fix_keys) >= 3:
            break
    fixes = [HOMEPAGE_FIXES.get(k, f"Strengthen your {LABELS.get(k, k).lower()}.") for k in fix_keys]

    return {
        "headline_problem": problem,
        "why_it_costs_clients": (
            "A visitor makes up their mind in seconds. If your page doesn't quickly show you can fix their problem, "
            "they click away and try another coach. The average coaching homepage we scored is just 3.7 out of 10, and "
            "86% fail this basic five-second test. That's where you lose clients, before a single enquiry ever "
            "comes in."
        ),
        "top_fixes": fixes,
        "money_left_on_table": (
            "This was never really about your website. A nicer page won't fix a message that misses your buyer. "
            "The coaches with a steady stream of enquiries every month, the ones who never worry where the next "
            "client is coming from, aren't the ones with the prettiest sites. They're the ones who understand their "
            "buyer better than anyone else in their space. That's what we do. Not websites. Understanding."
        ),
    }

# A plain one-line "why" for each score, so a coach understands every number.
def _humanlist(items):
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]

def criterion_note(key, sc, ev=None):
    ev = ev or {}
    proof_links = ev.get("proof_links") or []
    ext_reviews = ev.get("external_reviews") or []
    if key == "proof_cred":
        if sc < 7 and (proof_links or ext_reviews):
            joined = _humanlist(list(proof_links) + list(ext_reviews))
            return (f"You’ve got proof or credibility, but it’s a click away, you link out to {joined}. A cold "
                    "visitor won’t hunt for it in the first few seconds, so it isn’t working when they decide. "
                    "Bring your strongest proof onto the homepage, where they see it without hunting.")
        if sc >= 6:
            return ("A cold buyer gets real reason to believe you: results or testimonials that show you deliver, "
                    "plus names or reviews that show you’re the real thing.")
        if sc >= 3:
            return ("There’s some here, but it’s the easy-to-fake kind. A neat text testimonial counts, but a cold "
                    "buyer half-assumes you wrote it yourself. What they really believe is a video testimonial, or a "
                    "screenshot of a real review with the person’s name and face on it. Put one of those up and it "
                    "does far more work than a wall of typed quotes.")
        return ("We didn’t spot the proof or credibility a cold buyer believes: client results, testimonials that "
                "name the problem you solved, real reviews, or names a stranger recognises. What you say about "
                "yourself (awards, ‘certified’, ‘as seen on’) a stranger discounts.")
    if key == "symptom_resonance":
        if sc >= 7:
            return ("Your copy describes the buyer’s daily pain in their own words, not coaching platitudes. "
                    "That’s the kind of copy that makes a cold visitor feel seen.")
        if sc >= 5:
            return ("There’s some real pain language here, but it sits alongside generic coaching words. "
                    "The more you describe the specific, physical, daily situation, the faster the right person "
                    "will recognise themselves.")
        return ("The copy leans on generic coaching platitudes like ‘mindset’, ‘clarity’, or ‘overwhelm’. "
                "These words don’t describe a real, felt pain — they describe a category. Replace them with "
                "the raw, specific daily situation your buyer is actually stuck in.")
    if key == "offer_relevance":
        if sc >= 7:
            return ("A cold buyer can see what you actually fix, and the offer connects directly to that pain. "
                    "That’s the clearest path from ‘I have this problem’ to ‘this person can fix it’.")
        if sc >= 4:
            return ("There’s an offer here, but it doesn’t clearly connect to the problem you say you solve. "
                    "A cold buyer needs to see the bridge: ‘I have THIS pain, you fix THAT pain, I’ll buy THIS.’")
        return ("We didn’t spot a clear offer that connects to a specific problem. A cold buyer needs to see "
                "exactly what you fix and one clear thing to start with.")
    if key == "intent_flow":
        if sc >= 7:
            return ("The page points at one clear next step. A cold visitor knows exactly what to do without having "
                    "to decide between competing options.")
        if sc >= 4:
            return ("There’s a clear next step, but it competes with one or two other asks. The more you cut, "
                    "the more the right action stands out.")
        return ("The page asks a cold visitor to do several different things at once. When someone has to choose "
                "between competing options, they usually choose none of them. Pick one next step and make it obvious.")
    if key == "perceived_friction":
        if sc >= 7:
            return ("The first step is low-commitment enough that a curious visitor will take it without needing "
                    "to be fully convinced yet. That’s how you catch people before they’re ready to buy.")
        if sc >= 4:
            return ("There’s a way in, but it still asks for more than a cold stranger is ready to give. "
                    "A free resource, a quiz, or a short video series lowers the bar and catches more people.")
        return ("The only clear next step is a sales call or consultation. That requires massive trust. "
                "Most new visitors are not ready to get on a phone call yet, so they leave. "
                "You must build a smaller first step.")
    if key == "risk_reversal":
        if sc >= 7:
            return ("You’ve given a cold buyer a reason to say yes without feeling like they’re taking a risk. "
                    "A guarantee or safety net removes the last objection.")
        return ("Nothing on the page lowers the risk of saying yes. A sceptical visitor stays sceptical. "
                "A clear guarantee, a refund window, or a free trial makes saying yes feel safer.")
    good = {
        "clarity_5sec": "A stranger gets who you help and what they'd get, fast.",
        "specificity": "You name who you help and their exact problem, which most coaches don't.",
        "symptom_resonance": "Your copy describes real, daily pain in the buyer's own words.",
        "proof_cred": "A cold buyer gets real reason to believe you: results and third-party trust.",
        "offer_relevance": "A cold buyer can see what you fix and there's one clear thing to start.",
        "intent_flow": "The page points at one clear next step, nothing competing with it.",
        "perceived_friction": "The first step is low-commitment enough that a curious visitor will take it.",
        "risk_reversal": "You lower the risk of saying yes, making it easier to commit.",
    }
    bad = {
        "clarity_5sec": "In five seconds, a stranger can't tell who this is for or what they'd get.",
        "specificity": "It could be for anyone. You don't name who you help or their exact problem.",
        "symptom_resonance": "The copy leans on generic coaching words that don't describe a real, felt pain.",
        "proof_cred": "We didn't spot the proof or credibility a cold buyer believes: results, testimonials, real reviews.",
        "offer_relevance": "A cold buyer can't see what you actually fix, or there's no clear thing to buy.",
        "intent_flow": "The page scatters a visitor across competing asks instead of one clear next step.",
        "perceived_friction": "The first step asks for too much commitment from someone who just found you.",
        "risk_reversal": "Nothing lowers the risk of saying yes, so sceptical visitors stay sceptical.",
    }
    thresh = 5 if key == "specificity" else 6
    return good.get(key, "") if sc >= thresh else bad.get(key, "")


def _mi_close(note, key, score):
    """Append a score-conditional MI File closing line after the bar's diagnosis."""
    if score is None:
        return note
    thresh = 5 if key == "specificity" else 6
    if score >= thresh:
        tail = (
            f"A score of {score} here means your instincts are ahead of most coaches. "
            "The question is whether that intuition matches thousands of real buyers out there, "
            "or just the small group of clients you have already met. "
            "The Market Intelligence (MI) File tells you which."
        )
    else:
        tail = (
            "Your words aren't working because you lack real-world facts. "
            "You cannot guess what a stressed buyer wants. "
            "The Market Intelligence (MI) File gives you the exact phrases they use "
            "when they are ready to buy."
        )
    return f"{note} {tail}" if note else tail


# ---------------------------------------------------------------- main entry
# A bot-challenge / security-verification wall (Cloudflare 'verify you are human', a browser check, a CAPTCHA gate)
# is NOT the coach's page. We must NEVER score it (it would invent numbers off a security screen) and never count it.
# We refuse honestly with the screenshot. We do NOT try to bypass it: defeating a site's bot check is off-limits and
# unreliable. Gated on SHORT content so a legitimate page that merely names Cloudflare in its footer isn't caught.
_BLOCKED_RE = re.compile(
    r"performing security verification|verify you are human|checking your browser before|"
    r"attention required.{0,20}cloudflare|enable javascript and cookies to continue|just a moment\.\.\.|"
    r"ddos protection by|this website uses a security service to protect|needs to review the security of your connection",
    re.I)

def _is_blocked(row):
    body = _clean(row.get("body_text")) or ""
    blob = " ".join([body, str(row.get("h1") or ""), " ".join(row.get("big_texts") or [])])
    return bool(_BLOCKED_RE.search(blob)) and len(body) < 1500   # challenge pages are short

# A random / non-coaching site (someone testing the tool with Amazon, a restaurant, a SaaS) must NOT be scored against
# the coaching benchmark or counted in the corpus, it would pollute the recorded results. We require at least ONE
# coaching / therapy signal. Deliberately BROAD so we never reject a real coach: almost every coaching/therapy page
# says at least one of these somewhere.
_COACHING_RE = re.compile(
    r"\bcoach(?:ing|es|ed)?\b|\btherap(?:y|ist|ists|ies|eutic)\b|\bcounsell?(?:or|ors|ing|er|ers)\b|"
    r"\bmentor(?:ing|ship|s)?\b|life coach|wellness|well[- ]?being|\bmindset\b|self[- ]?(?:development|growth|help)|"
    r"personal (?:growth|development)|\bhealing\b|hypnotherapy|psychotherapy|\bNLP\b|spiritual|holistic|"
    r"\btransformation\b|\bclarity coach\b|\bintuitive\b|\bcounselling\b|\bcounseling\b", re.I)

def _looks_like_coaching(row):
    body = _clean(row.get("body_text")) or ""
    blob = " ".join([body, str(row.get("h1") or ""), str(row.get("page_title") or ""),
                     " ".join(row.get("big_texts") or [])])
    return bool(_COACHING_RE.search(blob))

# POLICY-PAGE INPUT GATE (issue 10): if what we captured is a cookie/privacy/legal page (a consent wall that covered
# the site, or a policy URL submitted by mistake), we must NOT hallucinate a homepage from it. Detect it and refuse
# honestly, no score, no record. Deliberately conservative: a normal homepage with a cookie BANNER never trips this.
_POLICY_MARK = [
    "we use cookies", "cookie policy", "cookies policy", "privacy policy", "privacy notice", "gdpr",
    "data controller", "data protection", "personal data", "personal information", "third party cookies",
    "third-party cookies", "necessary cookies", "marketing cookies", "analytics cookies", "essential cookies",
    "legitimate interest", "manage preferences", "manage consent", "accept all cookies", "your consent",
    "processing of your", "opt out of", "reject all", "cookie settings", "your privacy choices",
]
_POLICY_HEAD_RE = re.compile(r"\b(privacy|cookies?)\s+(policy|notice)\b|\bcookie settings\b|\bterms (?:of|and)\b|\bgdpr\b", re.I)
_CONSENT_ACTION = ["accept all", "manage preferences", "manage consent", "reject all", "necessary cookies",
                   "your privacy choices", "cookie settings"]

def _looks_like_policy(row):
    low = ((_clean(row.get("body_text")) or "") + " " + (_clean(row.get("visible_text")) or "")).lower()
    if not low.strip():
        return False
    n = sum(1 for m in _POLICY_MARK if m in low)
    if n < 3:
        return False                                          # a page can mention cookies once or twice and be fine
    head = " ".join([str(row.get("h1") or ""), str(row.get("page_title") or ""),
                     str(row.get("visual_headline") or "")])
    if _POLICY_HEAD_RE.search(head):
        return True                                           # the page's own title says it's a policy/consent page
    compact = re.sub(r"\s+", " ", low)
    if len(compact) < 1400 and any(w in low for w in _CONSENT_ACTION):
        return True                                           # a short consent-wall capture, not the real page
    return n >= 6                                             # a wall dominated by legal/cookie language

# GROUNDING GATE: the tool must never assert a client name, testimonial, or money figure that isn't on the page. Any
# such token in a note/diagnosis that can't be found in the copy is a fabrication (invented 'Jaimee Carson', '$500k')
# and gets the whole piece dropped for the safe rule version. Terms that aren't client-proof are exempted.
_GROUND_EXEMPT = re.compile(
    r"google|facebook|trustpilot|linkedin|yelp|instagram|youtube|twitter|\btv\b|"
    r"career development|professional certified|life coach|discovery call|human design|social media|"
    r"mental health|treasure valley|new york|los angeles|united states|united kingdom|"
    r"free consultation|free call|book now|learn more|contact us|privacy policy", re.I)
# Common Capitalised words that get glued onto a real first name (sentence-starters, role/marketing nouns). We strip
# them off the ends of a Capitalised run before judging, so 'Client Ash Aives' resolves to 'Ash Aives' (not 'Client
# Ash') and 'Read Mark Jones' to 'Mark Jones' (no false strip when Mark Jones IS on the page).
_NAME_STOP = frozenset((
    "the their they them this that these those there here a an and but so or if when while with for from into onto off "
    "out up down read book free add show tell give one two her his its our your my client clients coach coaches "
    "coaching mentor therapist counsellor counselor testimonial testimonials review reviews named name strong real "
    "really glowing solid clear vague proof credibility story offer headline capture transform steps she he it we you "
    "i me says said claims cites shows call learn contact get got join sign download discovery consultation session "
    "program programme course guide masterclass ebook webinar life health career business mindset wellness holistic "
    "spiritual new old more most best top over about above below inside within january february march april may june "
    "july august september october november december monday tuesday wednesday thursday friday saturday sunday"
).split())

def _ungrounded_claims(text, copy, money=True):
    """Return the person-NAMES (always) and MONEY figures (when money=True) a note asserts that do NOT appear in the
    copy, i.e. fabrications. money=False for advice copy where a $-figure is a hypothetical, not a claimed on-page fact."""
    if not text or not copy:
        return []
    low = copy.lower(); low_digits = re.sub(r"[^\d]", "", low)
    bad = []
    if money:
        for m in re.findall(r"[£$€]\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?", text):     # a money figure claimed as proof
            digits = re.sub(r"[^\d]", "", m)
            if digits and digits not in low_digits:
                bad.append(m.strip())
    for run in re.findall(r"(?:[A-Z][A-Za-z'’]+\s+){1,}[A-Z][A-Za-z'’]+", text):   # a run of 2+ Capitalised words
        words = run.split()
        while words and words[0].lower() in _NAME_STOP: words.pop(0)    # strip glued sentence/role words off the ends
        while words and words[-1].lower() in _NAME_STOP: words.pop()
        if len(words) < 2:
            continue
        name = " ".join(words[:2])                                      # the surviving Firstname Lastname
        if name.lower() in low or _GROUND_EXEMPT.search(name):
            continue
        bad.append(name)
    return bad

# SELF-CONSISTENCY (issue 5): a score must not contradict its OWN note. When a note plainly states a fault the rubric
# bands as low, the score can't sit above that band. Each regex is deliberately narrow, keyed off the AI's own words,
# so it only fires on a genuine self-contradiction (a CTA scored 9 whose note says 'four competing asks').
_CTA_MANY_RE = re.compile(
    r"(?:four|five|six|seven|eight|nine|ten|\b[4-9]\b|\b1[0-9]\b|several|multiple|many|too many|a (?:wall|host|range) "
    r"of)\s+(?:competing |different |separate |distinct )?(?:asks|ctas|call[- ]?to[- ]?actions?|actions|buttons|"
    r"links|options|choices|offers)|competing (?:asks|ctas|actions|buttons|links|offers)|"
    r"pull(?:s|ing)? (?:the reader |a visitor )?in (?:different|opposite) directions|decision overload|"
    r"(?:overwhelm|overwhelms|overwhelming) (?:the |a )?(?:reader|visitor|cold)", re.I)
_CLARITY_NOPROBLEM_RE = re.compile(
    r"do(?:es)?n'?t (?:name|state|say|call out|spell out) (?:the |a )?(?:problem|pain|struggle)|"
    r"no (?:clear |real )?problem (?:named|stated|here)|lead(?:s|ing)? with (?:the )?"
    r"(?:destination|outcome|solution|result|benefit|method)s? (?:not|instead of|rather than|over)|"
    r"names? only (?:a|the) (?:field|topic|category|niche|service)|"
    r"(?:the |a )?(?:field|topic|category) (?:not|without|instead of) (?:naming )?(?:a |the )?(?:problem|pain)", re.I)
# 'No client results/testimonials' is honest and, per the rubric, can co-exist with a 7 (strong credentials, no client
# proof), so it only bars the 8-10 STRONG band. Total absence ('no proof or credibility at all') bars everything above 3.
_PROOF_NONE_RE = re.compile(
    r"no (?:real )?proof (?:or|and) credibility|nothing (?:here )?to (?:build|establish|show) (?:trust|belief|"
    r"credibility)|we didn'?t spot (?:any|the) (?:proof|credibility)|zero (?:proof|credibility)|"
    r"no (?:trust|credibility) signals? (?:at all|whatsoever)", re.I)
_PROOF_NOCLIENT_RE = re.compile(
    r"no (?:client )?(?:testimonials?|reviews?|results?|case stud(?:y|ies)|social proof)|"
    r"(?:testimonials?|reviews?|client results?) (?:are )?(?:missing|absent|nowhere)", re.I)
# STORY placement (issue 9): reader-facing language that only appears deep in the page can't earn a high story score,
# the hero opened about the coach. When the story note itself says the reader content is buried/low, cap story at 5.
_STORY_BURIED_RE = re.compile(
    r"buried|further down|lower (?:down|on the page)|down the page|below the fold|mid-?page|near the bottom|"
    r"(?:two|three|four|several) sections? (?:down|in|deep)|only (?:in|appears?) .{0,25}(?:lower|further|bottom|"
    r"later|deeper|section)|not (?:until|in|near) the (?:hero|top|opening|first)", re.I)

CLIFFHANGER_SYMPTOM = (
    '<h3>THE COPYWRITING BLINDSPOT:</h3>'
    '<p>Your homepage copy relies heavily on generic platitudes like ‘mindset,’ ‘clarity,’ or ‘overwhelm.’ '
    'In direct-response conversion psychology, consumers do not buy intellectual states. They buy solutions to raw, '
    'physical, burning symptoms. If you cannot describe their exact daily pain better than they can describe it '
    'themselves, they will click away instantly.</p>'
    '<h4>The Market Intelligence Gap:</h4>'
    '<p>You are currently estimating how your audience feels. To fix your conversion rate, you need real-world data, '
    'not an estimate. Our <b>Market Intelligence (MI) File</b> maps the exact raw, internal dialogue your market '
    'whispers to themselves at 3 AM so you can deploy copy that hooks their soul.</p>'
)

CLIFFHANGER_FRICTION = (
    '<h3>THE CONVERSION WALL:</h3>'
    '<p>Human inertia means people naturally avoid immediate mental or physical effort. By forcing a cold stranger '
    'who just discovered your name to immediately commit to a ‘45-minute sales consultation’ without any '
    'psychological safety nets or risk reversals, your friction is too high. You are asking for marriage on the '
    'first date. The psychological resistance is too high.</p>'
    '<h4>The Market Intelligence Gap:</h4>'
    '<p>You cannot lower consumer resistance unless you know their exact skepticism. Our <b>Market Intelligence (MI) File</b> '
    'tracks your audience’s deepest hidden buying objections and fears, showing you exactly what low-friction '
    'value slopes and safety shields you need to build to capture cold traffic seamlessly.</p>'
)

def audit_url(url):
    domain = sm.norm_domain(url)
    if not domain:
        return {"ok": False, "error": "That doesn't look like a valid website address."}
    # KEEP THE FULL PATH for rendering: if the user gives a specific page (…/dating-coaching), audit THAT page, not
    # the homepage. norm_domain strips the path (right for corpus de-dup), so we build a path-preserving target here.
    target = re.sub(r"^https?://", "", str(url).strip(), flags=re.I)
    target = re.sub(r"^www\.", "", target, flags=re.I).rstrip("/") or domain
    # For the DISPLAY: say exactly which page we read. A bare domain = the homepage; a path = that specific page,
    # so we never claim 'homepage' when the user audited /dating-coaching.
    _tpath = target.split("/", 1)[1].strip("/") if "/" in target else ""
    is_home = (_tpath == "")
    disp_url = "https://" + target
    # Prefer the real-browser render (catches JS sliders/carousels); fall back to the fast scrape.
    row, thumb = render_and_extract(target)
    if row is None:
        row = sm.fetch(target)
        thumb = None
    if row.get("status") == "dead":
        return {"ok": True, "domain": domain, "status": "dead", "page_display": target,
                "message": "We couldn't load this website at all, it appears to be down or broken. "
                           "For a coach, that's the most expensive problem of all: an invisible business."}
    # A bot-challenge / 'verify you are human' wall: refuse honestly, keep the screenshot, DON'T score or count it.
    if _is_blocked(row):
        return {"ok": True, "domain": domain, "status": "blocked", "page_display": target, "thumbnail": thumb,
                "analysed_on": _dt.datetime.now().strftime("%d %B %Y"),
                "message": "We're sorry, we couldn't read this website. It sits behind a security check, a "
                           "'verify you are human' bot screen (this one from Cloudflare), which stops our reader "
                           "before it can see the real page. We won't guess, so there's no score. Worth knowing: some "
                           "genuine visitors, anyone the check flags, hit this same wall before they ever reach your "
                           "site. The screenshot below is exactly what we saw. Try again shortly, or check your "
                           "security settings so real people aren't turned away."}
    # NON-COACHING GUARD: if the page shows no coaching/therapy signal at all, it's a random site being tested against
    # our tool. Don't score it (the coaching benchmark would be meaningless) and don't count it in the corpus.
    if not _looks_like_coaching(row):
        return {"ok": True, "domain": domain, "status": "not_coaching", "page_display": target, "thumbnail": thumb,
                "analysed_on": _dt.datetime.now().strftime("%d %B %Y"),
                "message": "This doesn't look like a coaching or therapy website, so we haven't scored it. Our "
                           "benchmark is built from thousands of real coaching homepages, and those checks wouldn't "
                           "be fair or meaningful on a different kind of site. If this IS a coaching business, the "
                           "words a cold buyer looks for, what you do and who it's for, may not be on the page yet, "
                           "which is itself the first thing worth fixing."}
    # POLICY-PAGE GATE: if we captured a cookie/privacy/legal page (a consent wall, or a policy URL), refuse honestly
    # rather than inventing a homepage from legal boilerplate. No score, no record.
    if _looks_like_policy(row):
        return {"ok": True, "domain": domain, "status": "policy_page", "page_display": target, "thumbnail": thumb,
                "analysed_on": _dt.datetime.now().strftime("%d %B %Y"),
                "message": "We landed on a cookie or privacy page here, not the real homepage, so there's nothing for "
                           "us to score, and we won't guess what your homepage says. This usually means one of two "
                           "things: the link points at a policy page, or a cookie/consent wall is covering the site "
                           "before the real content loads (which your first-time visitors hit too). The screenshot "
                           "below is what we saw. Check the link, or that a cold visitor reaches your page, and try "
                           "again."}
    record_domain(domain)   # only count a page we ACTUALLY read (real coaching, not dead / blocked / off-topic)

    scores, total_100, score_10 = score_site(row)
    ev = build_evidence(row)
    _caps = ev.get("captures") or {}
    total_100 = S.weighted_total(scores); score_10 = round(total_100 / 10)

    # AI LAYER: one call re-scores the 8 content criteria by READING the page (keyword matching can't judge
    # whether a story connects or an offer is really clear) AND writes the diagnosis. The rule scores above are
    # the anchor; the AI only moves a number where the copy justifies it. technical_health stays rule-based
    # (it's factual). On no-key / failure / a banned word, ai_analyse returns None and we fall back to rules.
    ai = ai_analyse(row, scores, score_10, ev)
    ai_notes = {}
    _generic_tokens = []
    if ai:
        # VISION picks the HEADLINE from the screenshot (much better than the biggest-font JS heuristic that broke on
        # sliders/hero-overlays). Pop-up detection stays in the DOM: vision can't reliably tell a cookie-consent
        # modal from a marketing pop-up, but the cookie-aware DOM detector can.
        mh = (ai.get("main_headline") or "").strip()
        if mh:
            cands = row.get("big_texts") or []
            exact = next((c for c in cands if c.strip().lower() == mh.lower()), None)   # snap to exact on-page text
            ev["headline"] = exact or mh
            h1t = ev.get("h1_tag") or ""
            ev["headline_differs_from_h1"] = bool(h1t and ev["headline"].strip().lower() != h1t.strip().lower())
        _generic_tokens = (ai.get("pain_flags") or {}).get("generic_tokens_found") or []
        # Scores are clean integers, always take them. Recompute the weighted total off the AI-adjusted scores.
        # lead_capture is NOT taken from the AI: it's already been set deterministically from detect_capture above
        # (the AI's lead_capture wobbled 8/2/8 and contradicted the note), so we skip it here and never let the AI
        # overwrite the authoritative value.
        for k in AI_SCORE_CRIT:
            if k == "lead_capture":
                continue
            s = ai["scores"].get(k)
            if s:
                scores[k] = max(0, min(10, int(s["score"])))
        # FLAG-JUDGE (safeguard — global integration fail-safe): all 8 criteria come from the AI's FLAGS
        # via the pure Python judges. Wrapped so an empty / missing / malformed flag payload can
        # NEVER crash the audit — on ANY problem we simply leave the deterministic proxy score already in `scores`
        # (set from S.CRITERIA at the top of audit_url), so the page always renders a real number, never a 500.
        for _crit, (_flagkey, _judge) in FLAG_CRIT.items():
            try:
                _flags = ai.get(_flagkey)
                if isinstance(_flags, dict) and _flags:
                    scores[_crit] = max(0, min(10, int(_judge(_flags))))
                # else: no / empty flags -> keep the deterministic proxy already in scores (silent, safe fallback)
            except Exception:
                pass   # any error whatsoever -> keep the proxy; never blank the page
        # Recompute the total off the flag-judged scores.
        total_100 = S.weighted_total(scores); score_10 = round(total_100 / 10)
        # Notes are guarded PER FIELD: a banned word in one note only drops that one to the rule note, the other
        # seven AI notes still show. This is what stops a stray word wiping the whole specific diagnosis.
        for k in AI_SCORE_CRIT:
            s = ai["scores"].get(k)
            reason = (s.get("reason") or "") if s else ""
            if reason and not _BANNED_RE.search(reason):
                ai_notes[k] = reason
        # Lead capture MUST name exactly what's on the page (form vs newsletter vs magnet). The AI can mislabel a
        # contact form as a newsletter, so we always use the deterministic, detector-driven note for it.
        ai_notes.pop("lead_capture", None)
        # Guard the diagnosis PER FIELD (each is its own labelled section in the report, so a mix reads fine): a
        # banned word in one part only swaps THAT part for the rule version. This stops one stray word wiping the
        # whole AI diagnosis, including the felt "what it's costing you" copy, back to the generic rule text.
        _rc = None
        critique = {}
        for k in ("headline_problem", "why_it_costs_clients", "top_fixes", "money_left_on_table"):
            v = ai.get(k)
            # Search the RAW text, not json.dumps: json.dumps escapes an em dash to "—", which the regex
            # (looking for the literal — character) would never catch, letting em dashes slip through.
            blob = " ".join(v) if isinstance(v, list) else (v or "")
            if v is not None and not _BANNED_RE.search(blob):
                critique[k] = v
            else:
                if _rc is None:
                    _rc = rule_critique(row, scores, score_10, ev)
                critique[k] = _rc[k]
        # GROUNDING GATE (fabrication guard): the AI must never assert a client name, testimonial or $-figure that
        # isn't on the page. Verify every note and diagnosis part against the actual copy; if a piece cites a name or
        # number the page doesn't contain, it's invented, so we drop that piece back to the safe rule wording. And if
        # the PROOF note was the fabrication, the score it justified was propped up by nothing, so cap proof_cred to a
        # middling 5 (honest "we couldn't verify strong proof"), never letting a hallucinated testimonial mint a 7-9.
        _gcopy = " ".join([_clean(row.get("body_text")) or "", _clean(row.get("visible_text")) or "",
                           str(row.get("h1") or ""), str(row.get("page_title") or ""),
                           " ".join(row.get("big_texts") or []), " ".join(row.get("client_logos") or []),
                           str(row.get("logo_heading") or "")])
        # Cap proof FIRST when its note is fabricated (the score it justified was propped up by nothing), so the safe
        # replacement note is then built from the capped score and the two agree.
        if _ungrounded_claims(ai_notes.get("proof_cred", ""), _gcopy):
            scores["proof_cred"] = min(scores.get("proof_cred", 5), 5)
        for k in list(ai_notes.keys()):
            if _ungrounded_claims(ai_notes[k], _gcopy):
                ai_notes[k] = criterion_note(k, scores.get(k, 0), ev)
        # Names are proof claims anywhere; money in the diagnosis is only a fact-claim in the problem sections (top_fixes
        # / money_left_on_table use $-figures as hypothetical advice, so we don't strip those for a number).
        for k in ("headline_problem", "why_it_costs_clients", "top_fixes", "money_left_on_table"):
            _money = k in ("headline_problem", "why_it_costs_clients")
            blob = " ".join(critique[k]) if isinstance(critique.get(k), list) else (critique.get(k) or "")
            if _ungrounded_claims(blob, _gcopy, money=_money):
                if _rc is None:
                    _rc = rule_critique(row, scores, score_10, ev)
                critique[k] = _rc[k]
        # SELF-CONSISTENCY GATE: a score can't contradict its OWN note. Read each finalised note and, when it
        # plainly states a fault the rubric bands as low, cap the score to that band. Narrow, own-words triggers only.
        _pnote = ai_notes.get("proof_cred", "")
        if _PROOF_NONE_RE.search(_pnote):
            scores["proof_cred"] = min(scores.get("proof_cred", 0), 3)    # note says NOTHING to trust -> weak (<=3)
        elif _PROOF_NOCLIENT_RE.search(_pnote):
            scores["proof_cred"] = min(scores.get("proof_cred", 0), 7)    # no client proof -> can't be STRONG (8-10)
        # UNRELATED SERVICE GATE, THE NOTE: the generic sub-5 specificity note says "you don't name who you help", which
        # is FALSE for a page caught by this gate. These pages usually name their buyer WELL, once per business, and
        # that is the whole problem. Telling a coach she named nobody when she named three people is the kind of wrong
        # output the rulebook ranks below a generic fallback, so we write the honest reason instead. Set LAST, after the
        # grounding + self-consistency gates, so nothing downstream can swap it back for the false line. We deliberately
        # do NOT print the AI's category descriptions here: they are model prose, not page quotes, so naming them would
        # risk asserting an offer the page doesn't have.
        _sflags = ai.get("specificity_flags")
        if isinstance(_sflags, dict) and _flag(_sflags.get("unrelated_service_categories")):
            ai_notes["specificity"] = (
                "You do name who you help, and you do it well for each thing you sell. That part is working. The "
                "problem is this one page sells several different services to several different groups of people at "
                "once, and they don't overlap. A stranger has to work out which part is meant for her, and most won't "
                "stay to do that. Pick the one buyer you most want, and build this page for her alone. The other "
                "services can have their own pages."
            )
        # Any cap above changes the content scores, so recompute the headline total off them.
        total_100 = S.weighted_total(scores); score_10 = round(total_100 / 10)
    else:
        critique = rule_critique(row, scores, score_10, ev)
    ai_powered = bool(ai)   # AI informed the scores, even where a note or two fell back to the rule wording

    # The bars a coach sees, in the module-level DISPLAY_CRIT order (grouped by theme). Proof and credibility are
    # MERGED into proof_cred; the separate proof/credibility keys stay in `scores` only for the total math.
    # booking can be None (N/A). Keep it None all the way through so the display shows 'N/A', never a 0 or a crash.
    comparison = {
        k: {"you": scores.get(k), "market": BENCH.get(k),
            "gap": (None if scores.get(k) is None else round(scores.get(k, 0) - BENCH.get(k, 0), 1))}
        for k in DISPLAY_CRIT
    }
    return {
        "ok": True, "domain": domain, "page_display": target, "is_home": is_home, "status": "ok",
        "score_10": score_10, "score_10_display": round(total_100 / 10, 1),
        "total_100": total_100, "tier": tier(total_100),
        "market_avg_10": MARKET_AVG_10, "top10_10": TOP10_10,
        "gap_to_top": max(round(TOP10_10 - score_10, 1), 0),
        "in_top_tier": score_10 >= TOP10_10,
        "analysed_on": _dt.datetime.now().strftime("%d %B %Y"),
        "pages_read": 1,
        "corpus_count": websites_read_count(),
        "analysed_headline": (
            f"We read {'the homepage of ' + domain if is_home else 'the page ' + disp_url} and measured it on the "
            f"same 10 checks we ran across {websites_read_count():,} real coaching websites, so you can see how you "
            f"compare. Here's what we found."
        ),
        "scope_note": (
            f"We read {'your homepage only' if is_home else 'this one page only'}, {disp_url}, "
            f"not your whole website."
        ),
        "media_note": (
            ("You've got video on your homepage. We read the words on the page, not the video, and that's the point: "
             "search engines can't watch it, and plenty of visitors won't press play. If your reasons to buy live only "
             "in the video, plenty of people never actually get them.")
            if row.get("has_video") == "yes" else None
        ),
        "evidence": ev,
        "notes": {k: {"pass": (None if scores.get(k) is None else
                               scores.get(k, 0) >= (5 if k == "specificity" else 6)),
                      "note": _mi_close(
                          ai_notes.get(k) or criterion_note(k, scores.get(k), ev),
                          k, scores.get(k))} for k in DISPLAY_CRIT},
        "voice": analyse_voice(row),
        "thumbnail": thumb,
        "strength": tech_strength(row, scores),
        "pricing_note": (None if ev["pricing_found"] else PRICING_NOTE),
        "popup_note": (
            "Your homepage throws a pop-up at a cold visitor before they've read a word. For someone who "
            "hasn't decided you're worth it yet, that usually backfires, they close the tab, not the pop-up."
            if ev.get("has_popup") else None
        ),
        "scores": scores, "comparison": comparison,
        "critique": critique,
        "ai_powered": ai_powered,
        "hero_quote": ev.get("headline", ""),
        "generic_tokens_found": _generic_tokens,
        "global_score": round(total_100 / 10, 1),
        "cliffhanger": {
            "symptom": CLIFFHANGER_SYMPTOM if scores.get("symptom_resonance", 10) <= 4 else None,
            "friction": CLIFFHANGER_FRICTION if (scores.get("perceived_friction", 10) <= 4 or scores.get("risk_reversal", 10) <= 4) else None,
        },
    }

# ---------------------------------------------------------------- human-readable printout
def format_result(res):
    if not res.get("ok"):
        return "⚠️  " + res.get("error", "Something went wrong.")
    if res.get("status") == "dead":
        return f"\n{res['domain']}\n{res['message']}\n"
    L = []
    L.append(f"\n{'='*58}\n  COACHING WEBSITE REPORT CARD, {res['domain']}\n{'='*58}")
    L.append(f"  Your score:   {res['score_10']}/10   ({res['tier'].upper()})")
    L.append(f"  Market avg:   {res['market_avg_10']}/10     Top 10%: {res['top10_10']}+")
    L.append(f"\n  Scorecard (you vs the market):")
    for k, c in sorted(res["comparison"].items(), key=lambda kv: kv[1]["gap"]):
        arrow = "▲" if c["gap"] >= 0 else "▼"
        L.append(f"   {LABELS[k]:30s} {c['you']:>2}/10  (mkt {c['market']}) {arrow}")
    cr = res["critique"]
    L.append(f"\n  ── Diagnosis {'(AI)' if res['ai_powered'] else '(rule-based, add API key for AI)'} ──")
    L.append(f"  ▶ Biggest problem: {cr['headline_problem']}")
    L.append(f"  ▶ Why it matters:  {cr['why_it_costs_clients']}")
    L.append(f"  ▶ Fix this week:")
    for f in cr["top_fixes"]:
        L.append(f"      • {f}")
    L.append(f"  ▶ Bottom line:     {cr['money_left_on_table']}")
    L.append("=" * 58)
    return "\n".join(L)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 audit.py https://somecoachwebsite.com")
        sys.exit(1)
    result = audit_url(sys.argv[1])
    print(format_result(result))
