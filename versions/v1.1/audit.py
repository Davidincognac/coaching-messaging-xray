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

# --- model for the audit: cheap on purpose (high-volume free tier ~1p/audit).
#     Bump to claude-opus-5 only for the paid Intelligence File. Override via env. ---
AUDIT_MODEL = os.getenv("AUDIT_MODEL", "claude-haiku-4-5")

# --- market benchmarks, from our full run of 10,954 live sites (strict scoring) ---
MARKET_AVG_10 = 3.7
TOP10_10 = 5.6
BENCH = {   # market average per criterion, 0-10
    "clarity_5sec": 4.5, "specificity": 4.4, "offer_clarity": 2.9, "proof": 1.5,
    "clear_cta": 5.6, "lead_capture": 4.6, "credibility": 2.7, "story": 2.5,
    "pricing_shown": 1.8, "technical_health": 9.0,
    "proof_cred": 2.6,   # merged proof+credibility (approx market avg; corpus still scores them separately)
}
LABELS = {
    "clarity_5sec": "5-second clarity", "specificity": "Specificity (who + what problem)",
    "offer_clarity": "Offer clarity & value", "proof": "Proof / social proof",
    "clear_cta": "One clear call-to-action", "lead_capture": "Lead capture",
    "credibility": "Credibility markers", "story": "Story / the human",
    "pricing_shown": "Pricing visible", "technical_health": "Technical health",
    "proof_cred": "Proof & credibility",
}

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
    try:  # add any newly-recorded domains from live audits
        with open(_DOMAINS_FILE) as f:
            for line in f:
                d = line.strip().lower()
                if d:
                    s.add(d)
    except FileNotFoundError:
        pass
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
        return len(_load_domains())

# ---------------------------------------------------------------- evidence ("we actually read your site")
def _clean(x):
    x = str(x or "").strip()
    return "" if x.lower() in ("", "nan", "none") else x

def _tidy_headline(t):
    t = _clean(t)
    t = re.sub(r"\s*[-|–,]\s*(home|homepage|welcome)\s*$", "", t, flags=re.I)
    t = re.sub(r"^\s*(home|homepage|welcome)\s*[-|–,]\s*", "", t, flags=re.I)
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
        return {"kind": "magnet", "desc": f"a free resource (‘{phrase}’)", "buried": buried, "gated": gated}
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
    # 4) A standalone newsletter / mailing-list sign-up. Word boundaries matter: bare "subscribe" as a substring
    #    matches "oversubscribed", so we require real words, not fragments.
    # A newsletter/mailing-list sign-up is weak lead capture, and weaker still if it sits at the very bottom with
    # no reason to sign up. body_text follows DOM order, so a sign-up cue past ~65% of the page is down in the footer.
    def _news_buried(cue):
        return bool(bt) and cue and low.find(cue.lower()) > 0.65 * len(bt)
    # A newsletter is only REAL if there's an actual email SIGN-UP (an email input / opt-in form), not just the word
    # 'subscribe' (a social link) or a printed email address. So we require optin_present, a genuine capture signal,
    # before we ever call it a newsletter. This kills the 'phantom newsletter' where a stray word invented a form.
    _has_optin = str(row.get("optin_present", "")).lower() == "yes"
    if news and _has_optin:
        return {"kind": "newsletter", "desc": f"a newsletter sign-up (‘{news.group(0)}’)", "buried": _news_buried(news.group(0))}
    nm = re.search(r"\bnewsletter\b|\bmailing list\b|\bjoin (?:my|our|the) list\b|"
                   r"\bsign up (?:for|to) (?:my |our |the )?(?:newsletter|updates|mailing list)\b", low)
    if nm and _has_optin:
        return {"kind": "newsletter", "desc": "a newsletter or mailing-list sign-up", "buried": _news_buried(nm.group(0))}
    # 5) The scraper saw an email input but NO newsletter/subscribe wording (the branches above didn't fire). Do NOT
    #    invent a newsletter that isn't there. An email field with a 'get in touch' / 'contact' context is a CONTACT
    #    form, not a sign-up; name it honestly. Only if there's genuinely nothing else do we call it a bare email form.
    if str(row.get("optin_present", "")).lower() == "yes":
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
    # PER-CANDIDATE pop-up reconcile, BEFORE choosing the best: an email opt-in whose form lives in a pop-up
    # (popup_optin, derived from a real email field + a pop-up/overlay signal) is thrown OVER the page on load, so it
    # is the OPPOSITE of 'buried' (its buried flag only came from the form sitting late in the DOM). Mark it and clear
    # buried so it wins on its true prominence (score 3/5, not the buried 2) and the note says the truth. Keyed on
    # popup_optin (an EMAIL pop-up), never bare has_popup, so a SEPARATE overlay can't un-bury an unrelated footer
    # form; and only newsletter/email_optin (the kinds popup_optin is derived from) are ever relabelled a pop-up, so a
    # community link or a magnet is never mislabelled. Done before max() so the un-buried opt-in can win the primary.
    if row.get("popup_optin"):
        for c in caps:
            if c.get("kind") in ("newsletter", "email_optin"):
                c["popup"] = True
                c["buried"] = False
    best = dict(max(caps, key=lead_capture_score))
    best["also"] = [c for c in caps if c is not None and c.get("desc") != best.get("desc")]
    return best

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
        "capture": build_capture(row),       # PRIMARY capture (best of possibly several) + 'also' for the rest
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
            pg.goto("https://" + domain, timeout=30000, wait_until="load")
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
            rendered_html = pg.content()
            final_url = pg.url
            try:
                vis = pg.evaluate(VISUAL_HEADLINE_JS)
            except Exception:
                vis = None
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
AI_SCORE_CRIT = ["clarity_5sec", "specificity", "offer_clarity", "proof_cred",
                 "clear_cta", "lead_capture", "story"]
_SCORE_FIELD = {"type": "object", "additionalProperties": False,
                # reason FIRST so the model thinks before it commits a number (steadier and more accurate than
                # picking a score cold then justifying it); score is 0-10, clamped in code (schema can't bound it).
                "properties": {"reason": {"type": "string"},
                               "score": {"type": "integer"}},
                "required": ["reason", "score"]}
AI_ANALYSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        # The AI reads the SCREENSHOT to identify the real headline (was a brittle biggest-font JS heuristic):
        "main_headline": {"type": "string"},     # the exact biggest headline a cold visitor reads first
        # Narrow VISION fact: is there a visible online STORE on the page? Used to floor the CTA score (only a real
        # shop can drag the CTA to 2-3 for chaos). Reason first so the boolean is judged, not guessed.
        "shop_reason": {"type": "string"},
        "has_visible_shop": {"type": "boolean"},
        "scores": {"type": "object", "additionalProperties": False,
                   "properties": {c: _SCORE_FIELD for c in AI_SCORE_CRIT}, "required": AI_SCORE_CRIT},
        "headline_problem": {"type": "string"},
        "why_it_costs_clients": {"type": "string"},
        "top_fixes": {"type": "array", "items": {"type": "string"}},
        "money_left_on_table": {"type": "string"},
    },
    "required": ["main_headline", "shop_reason", "has_visible_shop", "scores",
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

_AI_RUBRIC = {
    "clarity_5sec": "In 5 seconds, does the RIGHT person (a cold visitor who HAS this problem) know this page is for them, and sense what changes? A headline that names the reader's real SITUATION or PROBLEM in their words is strong reader-first copy, score it high, NEVER call that 'abstract' or dock it for being 'about the reader'. Grade on a SPECTRUM, not just sharp-vs-vague: 9-10 = the right person instantly sees themselves AND senses the outcome; 7-8 = sharply names their real situation/problem so they recognise themselves fast, even if the outcome/service isn't spelled out; 5-6 = names a clear audience OR a clear service/outcome but not sharply, a visitor gets the gist but doesn't feel 'that's exactly me'; a VAGUE / feel-good outcome ('build authentic connections', 'live your best life', 'find your purpose', 'transform your life', 'unlock your potential') does NOT count as a concrete outcome, so audience-named + fluffy-outcome caps at 5, it does NOT reach 7-8; only the reader's real SITUATION / PROBLEM or a CONCRETE specific outcome they'd recognise earns 7-8; 3-4 = names a broad CATEGORY, FIELD or TOPIC (even as a vague tagline, e.g. 'Divorce Differently' names the field divorce; 'leadership coaching'; or a generic benefit like 'live your best life'), so a cold visitor at least knows what area this is about, but the right person isn't singled out and doesn't feel 'that's exactly me'; 0-2 = gives NO clue what field or topic it's even about: just the coach's personal NAME, or pure field-less abstraction ('You Are Worthy', 'Reimagine what's possible'), so a cold visitor can't even tell what area you work in. RESERVE 0-2 for a name or a field-less abstraction ONLY; the moment the headline names the topic/field at all, it is at least a 3, never a 2. Judge the WHOLE above-fold, not just the single biggest line: if the hero has an 'I help [who] [do what]' line (e.g. 'I help entrepreneurs plan, start and grow businesses') OR any line that names the field or audience, clarity is AT LEAST 3, even when the biggest line is a name or a stats-brag ('Coached 1000+ entrepreneurs'). A 2 requires that NOTHING above the fold names the field or the audience.",
    "specificity": "Is it clear WHO it's for and WHAT problem it solves, in their words? Judge CLARITY of the problem, not narrowness. A coach can serve a BROAD audience (several related problems, e.g. all compulsive behaviours: drink, food, work) and still score HIGH if the SHARED problem is named clearly and concretely so each person recognises themselves. Breadth is fine; VAGUENESS is not. 10=who + problem unmistakable (a narrow niche OR a clearly-named shared problem); 5=one is clear; 1=could be anyone, no real problem named.",
    "offer_clarity": "TWO things: (1) can a cold buyer see what you actually FIX, the outcome/transformation and why it's worth it (the value); AND (2) is there one clear, defined thing to buy or an obvious way to start? Judge the VALUE and the OFFER, NOT the price, showing a price does not earn marks and hiding it does not lose them. 10=the fix/outcome is vivid AND there's a clear thing to buy; 5=one of the two; 0=neither, just a vague sense of 'coaching'.",
    "proof_cred": "MERGED proof + credibility: does a cold buyer get real reason to BELIEVE you, both that you get results and that you're legit? Judge by how COSTLY TO FAKE the signal is, and SCORE THE STRONGEST SIGNAL PRESENT, do NOT average down. A real third-party review-platform RATING (a Google / Facebook / Trustpilot star rating with a real review count, e.g. '5.0 from 58 reviews') is STRONG on its own = 8-9, it is costly to fake; if the page ALSO has plain text testimonials, those are a bonus and must NOT drag the score below what the Google/Trustpilot rating already earns. CLIENT TESTIMONIALS come in tiers by format: a VIDEO testimonial is STRONG (hard to fake); a SCREENSHOT of a real review showing the person's name AND their photo/face (a Google/Facebook/Trustpilot card, a LinkedIn recommendation) is STRONG; a neat copy-paste TEXT quote from an ordinary client, even with a first name and initial, is MIDDLING (it counts, it's not poor, but it's easy to type up, so on its own it is NOT strong, cap it around 4-6). This format rule is ONLY for ordinary-client testimonials. It does NOT weaken these, which stay STRONG (8-10) in any format including plain text or a logo: a named endorsement from a RECOGNISED AUTHORITY (a well-known bestselling author) is costly to fake because they'd object if it were invented; media features shown as logos you recognise (real TV networks, national publications); named institutional clients you recognise (companies, universities); real third-party review widgets; specific results/numbers; case studies. Several together = strong. LOGO WALLS, JUDGE BY WHETHER YOU RECOGNISE THE BRANDS (the logo names are given to you in the FACTS block as image alt text, because a downscaled screenshot can't read a logo strip): (a) RECOGNISABLE major / household brands (e.g. KPMG, BCG, Red Bull, John Deere, Google, a real TV network or national publication) under a 'trusted by' / 'our clients' claim ARE a real, costly-to-fake signal, because a coach claiming Fortune-tier clients would be exposed if they were lying; credit it and score the proof UP to 6-7. BUT hold ONE honest caveat and put it in the note: a logo does not reveal the DEPTH of the relationship, they might have run a single half-day workshop years ago, not a long-term engagement, so recognisable client logos on their own are a solid 6-7, NOT a 9-10. (b) UNRECOGNISABLE or unlabelled local / ordinary-org logos are AMBIGUOUS: they could be audiences he merely spoke in front of or events he attended, not clients, so score them middling at best, never strong. (c) LIVE THIRD-PARTY REVIEWS are the strongest tier: a LIVE embedded Google / Trustpilot widget feeding real stars AND a visible review count (e.g. '5.0 from 200+ reviews') = 9-10. A mere SCREENSHOT or static graphic of stars, or a bare 'we're 5 stars on Google', is a CLAIM not proof, credit it only a little and say in the note they should embed the LIVE Google widget with the real review count so a cold buyer can verify it. WEAK/self-stated (score low): things they say about themselves, awards, bare 'bestselling'/'as seen on' with no recognisable names, accreditation/membership badges (ICF, WBENC, 'certified coach'). A reachable real business is a small plus. 10=strong; 0=nothing. WHEN YOU WRITE THE ONE-LINE REASON FOR THIS SCORE, BE HONEST, DO NOT FLATTER: if the proof is real but SOFT (named text testimonials with no photo, an unlabelled logo wall, 'as seen in' with no outlet you recognise), do NOT call it 'solid' or 'strong'; say plainly what would make a cold buyer doubt it (no photo so they can't tell it's a real person, logos that could just be event audiences) and that the lift is cheap and easy (add the person's photo or a screenshot of the real review, label the logos, add a Google/Facebook rating). A soft 6 that could reach 8 with small changes should read like that, not like a pat on the back. NEVER use vague grading words in the note ('middling', 'moderate', 'decent', 'somewhat', 'reasonable', 'a mixed picture'), they tell the coach nothing; say CONCRETELY what is working, what specific thing is missing, and the exact change that would lift it (e.g. not 'middling proof' but 'real recognisable brands, but a cold buyer can't tell if they were clients or one-off audiences, and there's no photo on the testimonials, add a face and say what you did for them'). DO NOT state the NAME FORMAT of testimonials (do not say 'first names only', 'full names', or invent a name), you cannot reliably read that off a screenshot and getting it wrong is a factual error; instead describe what a cold buyer can VERIFY: say 'text testimonials with no photo and no third-party source (Google / Facebook / Trustpilot) to verify them', and focus on what's missing. CREDIT WHAT IS ACTUALLY THERE, do not undercount it: a NAMED award (a proper-noun award title, e.g. 'Absolutely Mama Awards 2025') is a real if minor third-party signal, NEVER describe a named award as 'unnamed' or as having 'no recognisable authority'; and a NAMED founder / expert with STATED years of experience (e.g. 'Heidi Skudder, founder, 18 years in childcare') is real, verifiable credibility a stranger can check. When a named award AND a named expert-with-tenure both appear on the page, proof is AT LEAST a 4 even if the testimonials are anonymous. MULTIPLE NAMED CLIENTS with SPECIFIC QUANTIFIED results ('grew revenue by $500k', 'went from 1-in-10 to 1-in-2 close rate', 'from $1.5M to $2M') are STRONG, concrete, costly-to-fabricate proof: two or more such hard-number cases set a base of 6-7 even as plain text, docked only for missing photos / third-party verification, NEVER scored a middling 5. Specific numbers beat vague praise, do not under-credit them. A VERIFIABLE PROFESSIONAL LICENCE / accreditation from a real body (a licensed therapist / counsellor / psychologist, chartered, registered with a named professional body) OR TWO OR MORE named RECOGNISABLE mainstream MEDIA outlets you actually recognise (e.g. the Today Show, BBC, Forbes, Huffington Post, Women's Health) is STRONG, checkable authority that is costly to fake, and it FLOORS proof_cred at 7 even with no review widget and no logo strip. Do NOT cap real, named, checkable authority at 5 just because there is no Google/Trustpilot widget, that purism makes the score useless for ranking. Below 7 you dock ONLY for what is genuinely missing, above all CLIENT RESULTS: testimonials, case studies, before/after, numbers. A page with strong authority but NO client proof of results is a 7 (say so plainly: 'strong credentials and real media, but no client testimonials or results to show it works for others'); a real third-party review widget / rating ON TOP of that pushes it to 8-9.",
    "clear_cta": "Is there ONE clear, STRONG next step toward becoming a client (book/apply), not just 'contact'/'subscribe', AND is it the obvious single thing to do? TWO different failures both score LOW. (a) No real step, or only 'contact'/'subscribe', is low. (b) DECISION OVERLOAD: the page throws many DIFFERENT competing actions at a cold visitor (e.g. book a call AND buy several priced packages / 'add to cart' AND download an ebook AND watch a wall of videos AND sponsor a child AND a contact form). When the actions pull in many different directions the visitor doesn't know which to pick and freezes, so they do nothing. That is NOT a strong CTA, it is a mess, score it DOWN (3-4); never reward a page for having 'lots of buttons'. HOW TO JUDGE OVERLOAD, use this test: count the number of DIFFERENT JOBS the page asks a visitor to do, book a call, buy priced package A, buy priced package B, 'add to cart', download an ebook, watch a wall of videos, donate/sponsor, fill a contact form. Each distinct job is a separate ask. 1 job (even if the button is repeated) = focused. 3 OR MORE different jobs = DECISION OVERLOAD, cap the score at 3-4 no matter how strong or repeated any single one is. CRUCIAL: repetition does NOT rescue an overloaded page. The 'repeated action = good' rule ONLY applies when that repeated action is essentially the ONLY job on the page; if the page ALSO sells multiple priced products / has 'add to cart' / pushes an ebook and videos and a donation, the repetition is drowned out and it is still a mess, score 3-4. Multiple priced packages with 'add to cart' on a coaching homepage is by itself a strong sign of overload. Distinguish this from the SAME single action repeated down an otherwise-clean page ('Book a Free Session' three times, nothing else competing), which is GOOD consistency and scores HIGH. SCORE VIA A LADDER, but FIRST collapse repeats BY DESTINATION, not by wording: buttons with DIFFERENT text that lead to the SAME next step ('BOOK A CALL', 'I'M READY TO SCALE', 'GET STARTED' all going to the same booking) are ONE action, NOT three, and repeating one action with varied wording is a STRENGTH that RAISES the score, never overload. 'Learn More' six times, 'Contact' in header and footer, likewise ONE job. Count only genuinely DIFFERENT destinations/asks (a booking vs a purchase vs a download vs a donation). A dominant single action repeated down the page, even with a secondary 'watch video' or a service description lower down, is NOT decision overload, it's a focused page, score it 7-9. THEN judge, and MIND THE DIFFERENCE between a WEAK page and a CHAOTIC page, they score differently: 9-10 = one strong action (book a call / apply), clearly the only main thing, repeated consistently; 7-8 = one clear strong step plus at most one secondary; 5-6 = a real strong step exists but it's one of two or three competing options; 4 = NO strong step, the page only offers soft actions ('Learn More', 'Contact', 'read the blog', 'join a workshop'), however many, and never a real 'book a call' / 'apply' / 'get this free thing', OR several different asks with no shop, so it's weak and scattered but not a chaotic store; 3 = a priced SHOP is present but small (two or three products) alongside other asks; 2 = a big priced SHOP (many products / 'add to cart') PLUS several other heavy asks (a video wall, a donation, downloads, multiple booking types), a cold visitor is totally lost; 0 = no real next step at all. HARD RULE, do not break it: if there is NO shop (no priced products, no 'add to cart') the score CANNOT go below 4, no matter how many soft 'Learn More' buttons there are, because weak-and-cluttered is a 4, not chaos. Only a genuine priced store drops a page to 3 or 2. A weak page and a chaotic shop are DIFFERENT failures. WRITE THE NOTE FOR THE RIGHT FAILURE: if the problem is OVERLOAD (several competing asks), the note must SAY it's overload, list the competing asks, and say 'pick ONE clear next step', NEVER say 'no clear next step stands out' or 'no call to action', that describes ABSENCE, the opposite problem, and tells the coach to ADD when they need to CUT. Only say a CTA is missing/absent when there genuinely isn't a real next step on the page.",
    "lead_capture": "A real free resource that solves a piece of their problem (a guide/checklist), not just a newsletter. 8+=genuine magnet; 3=newsletter only; 0=nothing.",
    "story": "Does the copy connect to the READER's own situation, in their words, not just the coach's CV? 9-10=deeply reader-focused, names their fear/situation; 5-6=some real reader connection; 3-4=mostly the coach's CV or story but a human is present; 2=a bare catalog / CV with only a token noun-gesture to the reader (e.g. 'entrepreneurs like you'); 0-1=RESERVED for a page with no human at all, or copy that talks DOWN to or alienates the reader. Do NOT give 0-1 to a page that is merely coach-focused, that is a 2-3. IMPORTANT: even ONE genuine reader-facing 'here's what changes for YOU' sentence inside a CV-heavy bio (e.g. 'I'm here to help you trust yourself, hear your own voice') is real connection and floors story at 3, not 2; reserve 2 for a bio with no such line at all.",
}

def ai_analyse(row, scores, score_10, ev=None):
    """ONE AI call: SCORE the 8 content criteria by READING the page, plus write the diagnosis. We deliberately
    do NOT show the AI the keyword numbers, they anchor it into just echoing a wrong score (the whole reason we
    added this layer was that the keyword story score was flatly wrong). It judges the real copy fresh against a
    tight rubric, at temperature 0 for stability. Returns None on no-key / failure / banned words, so the caller
    falls back to the pure rule-based path."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    ev = ev or {}
    rubric_txt = "\n".join(f"- {LABELS[k]} ({k}): {d}" for k, d in _AI_RUBRIC.items())
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
        "You are scoring and diagnosing ONE coach's HOMEPAGE (homepage only, so scope everything to 'your "
        "homepage', never 'your site'). Your job: read the ACTUAL page copy below and score each criterion 0-10 "
        "using the rubric, then write the diagnosis. Judge exactly what a cold buyer would perceive, be strict and "
        "honest, no benefit of the doubt for things that aren't there. Give a ONE-LINE reason for each score, "
        "grounded in their real wording or what's visible (quote a phrase where you can).\n"
        "EXPLAIN THE GAP TO A 10, ALWAYS: for ANY score below 10, the reason must not only say what earned the score, "
        "it must name the SPECIFIC thing that would take it HIGHER, the one concrete change that closes the gap. A "
        "coach who scores 8 needs to know what the missing 2 points are. E.g. clarity 8: 'You name who it's for and "
        "the problem clearly; to reach a 10, put the OUTCOME they get right in the headline too, not just the "
        "problem.' Never write a reason that only praises what's already good, that leaves a coach with a number and "
        "no idea how to improve it. The ONLY exception is a 10, where you say plainly there's nothing to add.\n"
        "You are given a FULL-PAGE SCREENSHOT of the homepage as well as the text. USE THE SCREENSHOT to judge "
        "anything visual, a client logo strip, an 'as seen on' media row (TV networks, big publications), named "
        "client logos (companies, universities), video testimonials, headshots, design and hierarchy. Read the "
        "logos and media names you can see and weigh them: recognised TV networks / national media / well-known "
        "companies or universities are STRONG credibility; a specific NAMED endorsement from a recognised authority "
        "(a well-known bestselling author) is STRONG, not 'just one quote', it is costly to fake. But an UNLABELLED "
        "wall of ordinary organisation logos is AMBIGUOUS, not automatic proof: those orgs could be audiences he "
        "spoke in front of, not clients or media, so treat it as middling unless you recognise the logos as media or "
        "the page labels them ('our clients', 'as seen in'). Do not score "
        "proof or credibility 0 when the screenshot plainly shows a logo wall, media features or testimonials. Use "
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
        f"CRITERIA + rubric:\n{rubric_txt}\n\n"
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
            resp = client.messages.create(
                model=AUDIT_MODEL, max_tokens=1800,
                temperature=0,   # scoring must be stable: the same homepage should get the same numbers every run
                system=[{"type": "text", "text": VOICE, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": content}],
                output_config={"format": {"type": "json_schema", "schema": AI_ANALYSE_SCHEMA}},
            )
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
    "specificity": "on your homepage, it isn't clear enough who you help or what problem you solve, a first-time visitor may not be able to tell whether you're the right coach for them",
    "proof": "we didn't spot testimonials, results, or numbers on your homepage, the kind of proof that makes a visitor believe you can actually help",
    "story": "we couldn't find a personal story or a human on your homepage, the thing that makes a visitor trust you over the next coach",
    "lead_capture": "your homepage doesn't give visitors who aren't ready to book yet a way to stay in touch, somewhere to make a serious enquiry, or to leave their details in exchange for something useful (a guide, a checklist, a free call). So the people who aren't ready today simply leave, and you never hear from them again",
    "credibility": "we didn't spot the kind of trust a cold buyer really believes on your homepage, reviews from other people, or a real business they can reach; badges you give yourself (awards, ‘bestselling’, ‘as seen on’) don't count for much with a stranger",
    "clarity_5sec": "in the first five seconds on your homepage, it's hard to tell who you help and what they'd get",
    "offer_clarity": "on your homepage there's no clearly defined offer, just a way to get in touch, with nothing specific behind it",
    "technical_health": "your homepage has some technical weak spots (loading, security, or very thin content)",
}

# Imperative ACTIONS, kept distinct from the problem descriptions so the diagnosis never repeats itself.
HOMEPAGE_FIXES = {
    "specificity": "Name the exact person you help and the exact problem, in their words. Not ‘ambitious people’, but the real situation they're stuck in.",
    "clarity_5sec": "Rewrite your headline so it passes the five-second test: who it's for, and what changes for them, in one line a stranger understands straight away.",
    "offer_clarity": "Spell out one clear thing to buy: what it is, who it's for, and roughly what it costs.",
    "proof": "Add real proof: two or three client results with actual numbers, and a testimonial that names the problem you solved.",
    "story": "Rewrite your story so it's about the reader, not your CV. Show them you've been where they are.",
    "lead_capture": "Offer something that solves a small piece of their problem, not ‘join my newsletter’.",
    "credibility": "Add proof other people gave you: a few Google, Facebook or Trustpilot reviews. Those beat any award or ‘bestselling’ badge you hand yourself.",
    "clear_cta": "Give one strong next step high on the page, book a call or apply, not just ‘contact’ or ‘subscribe’, and stop it competing with five other buttons.",
    "technical_health": "Sort the basics: secure the site and give it real, readable content.",
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
    # Exclude proof AND credibility (not just the merged proof_cred): in the AI path both hold the same merged value,
    # so leaving them in would let one weak proof bar take two of the three fix slots and crowd out a real weakness.
    ranked = [k for k, _ in sorted(((k, v) for k, v in scores.items()
                                    if k not in ("pricing_shown", "proof_cred", "proof", "credibility")),
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
    fixes = [HOMEPAGE_FIXES.get(k, f"Strengthen your {LABELS[k].lower()}.") for k in fix_keys]

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
    # PROOF or CREDIBILITY that's a click away: don't say "none", say "it's hidden, bring it forward".
    if key == "proof" and sc < 6 and proof_links:
        joined = _humanlist(proof_links)
        return (f"You've got proof, but it's a click away, you link out to {joined}. A cold visitor won't hunt for "
                "it in the first few seconds, so it isn't working in the moment they decide. Bring your strongest "
                "proof onto the homepage, where they see it without hunting.")
    if key == "credibility" and sc < 7 and ext_reviews:
        joined = _humanlist(ext_reviews)
        return (f"There's real credibility here, but it's a click away: you link out to {joined}, where other people "
                "vouch for you. A cold visitor won't click in the first few seconds. Pull a couple of those reviews "
                "onto the homepage, where a cold visitor sees them in the moment that matters.")
    if key == "lead_capture":
        # Name EXACTLY what's on the page (contact form vs newsletter vs magnet), never guess or mislabel.
        cap = ev.get("capture") or {}
        kind, desc = cap.get("kind"), cap.get("desc")
        def _primary_note():
            if kind == "magnet":
                if cap.get("gated"):
                    return (f"You call it {desc}, but it's locked behind a paid membership, so it isn't really free "
                            "and it can't catch the visitor who isn't ready to pay yet. Offer one genuinely free thing "
                            "that solves a small piece of their problem, no paid plan needed, so a cold visitor has a "
                            "real reason to leave their email before they leave.")
                # Only claim it's 'buried at the bottom' when there's NO pop-up on the page. With a pop-up present we
                # can't be sure this magnet is buried rather than delivered by the pop-up, so we critique the value
                # instead (always safe) and never contradict the separate pop-up note.
                if cap.get("buried") and not ev.get("has_popup"):
                    return (f"You offer {desc}, a real reason for someone not ready to book to leave their details. "
                            "But it's buried below everything else on the page, so most visitors never reach it. Move "
                            "it up near the top, and spell out exactly what they'll get from it, the specific things "
                            "they'll learn, not just a title and 'download'.")
                return (f"You offer {desc}. That gives someone who isn't ready to book a real reason to leave their "
                        "details, so you can stay in touch until they are. Good. One lift: spell out exactly what "
                        "they'll get from it, the specific wins, so more people hand over their details.")
            if kind == "email_optin":
                base = f"You offer {desc}, a real reason for someone not ready to book to leave their details. Good."
                if cap.get("popup"):
                    return (base + " It pops up on load, so it's hard to miss, though a cold visitor who hasn't read "
                            "a word yet may close it before the offer lands. Show it in the page too, and make sure "
                            "it solves one specific piece of their problem.")
                if cap.get("buried"):
                    return (base + " But it's buried well below the fold, where hardly anyone reaches it. Move it up, "
                            "or repeat it near the top, so cold visitors actually see it before they leave.")
                return base + " Even better would be a free resource that solves one specific piece of their problem."
            if kind == "consultation":
                return ("Right now the only way to catch a lead is a call booking. That IS lead capture, but it's a "
                        "big ask: it only catches people ready to commit to a call right now. The many who aren't "
                        "ready yet, and there are always far more of them, leave with no way to stay in touch, and you "
                        "never hear from them again. A low-commitment freebie (a short guide or checklist) alongside "
                        "the call would catch those people too, so you can warm them up until they're ready to book.")
            if kind == "application":
                return ("What you've got is an application form. That's a big ask for a cold visitor: it's for people "
                        "already sure they want to work with you, not a way to catch the many who are still deciding. "
                        "Offer one genuinely free thing that solves a small piece of their problem first, right there "
                        "on the page, so someone who isn't ready to apply still leaves their email.")
            if kind == "contact_form":
                return (f"What you've got is {desc}. That's a way for people who are already ready to reach out, not a "
                        "way to capture the many who aren't ready yet. A free guide or checklist that solves a piece "
                        "of their problem would give those people a reason to leave their details.")
            if kind in ("newsletter", "community"):
                if cap.get("popup"):
                    base = (f"You've got {desc} that pops up almost the moment someone lands, before they've read a "
                            "word. It's impossible to miss, but a cold visitor who hasn't decided you're worth it yet "
                            "usually just closes it, especially when the pitch is 'subscribe for our news and updates', "
                            "which is about you, not a reason for them to hand over their email.")
                else:
                    base = (f"You've got {desc}, but you're giving people no real reason to use it. 'Subscribe' asks for "
                            "their email and offers nothing back, so hardly anyone does.")
                    if cap.get("buried"):
                        base += " And it's stuck at the bottom of the page where almost no one even reaches it."
                return (base + " Give them something worth having, a short guide or checklist that fixes one piece of "
                        "their problem, and they'll happily hand over their email to get it.")
            return ("We didn't spot a way to stay in touch with the people who aren't ready to book today: no free "
                    "guide or checklist, no sign-up, nothing to capture them before they leave.")
        note = _primary_note()
        # A page can have MORE THAN ONE capture. Critique the secondary ones too, so a coach sees the full picture.
        for extra in (cap.get("also") or []):
            ek = extra.get("kind")
            if ek == "community":
                note += (" You also have a ‘join the community’ sign-up, but on its own it's weak: it gives people no "
                         "clear reason to join, so most won't. Say what they actually GET inside, or it just sits there.")
            elif ek == "newsletter":
                pop = " that pops up" if extra.get("popup") else ""
                note += (f" You also run a newsletter sign-up{pop}, which is better for catching the not-ready, but "
                         "only if it offers them something; right now it just asks them to subscribe with no reason to.")
            elif ek == "email_optin":
                pop = " that pops up" if extra.get("popup") else ""
                note += (f" You also have an email sign-up{pop} with a real hook, a genuine way to catch the not-ready; "
                         "just make sure the offer solves one specific piece of their problem.")
            elif ek == "consultation":
                note += " You also push a call booking, which only catches the people already ready to commit."
        return note
    if key == "story":
        if sc >= 6: return "Your story links to what the reader is going through."
        if sc >= 3: return "There's a story, but it reads as being about you, not the person you help."
        if sc >= 2: return "There's a mention of a person, but no real story a visitor can connect with."
        return "We couldn't find a personal story or a human here, so there's nothing for a visitor to connect with."
    if key == "clear_cta":
        if sc >= 9: return "One clear, strong next step: book a call, apply or talk to you. Nothing competes with it."
        if sc >= 5: return "You've got a strong option in there (like ‘Book a call’), but it's one of several buttons. That's not one clear call to action."
        # 2-4 in the current rubric means the steps COMPETE (too many / all soft), not that a CTA is missing. The note
        # must say cut back to one, never 'add a CTA', which is the opposite fix.
        if sc >= 2: return "The next steps here are soft and scattered: no single strong ‘book a call’ or ‘apply’, just competing ‘learn more’, ‘contact’ or ‘sign up’ options, so a cold visitor doesn't know which to pick and does nothing. Give them one clear, strong next step and let it lead."
        return "No real call to action at all. An interested visitor has nowhere obvious to go; contact details or a phone number aren't a next step, a ‘Book a call’ button is."
    if key == "offer_clarity":
        # Two things, neither of them price: (1) can a cold buyer see what you FIX (the outcome/value), and
        # (2) is there one clear thing to buy or an obvious way to start.
        if sc >= 8:
            return ("A cold buyer can see what you actually fix and the change it brings, and there's a clear thing "
                    "to buy or an obvious way to start.")
        if sc >= 5:
            return ("We look at two things here: can a cold buyer see what you actually fix (the outcome, and why "
                    "it's worth it), and is there one clear thing to buy or an obvious way to start? You've got one "
                    "of those, not both. The missing half is what costs you.")
        niche = ev.get("niche")
        lead = f"We can see your area is {niche}" if niche else "We can see you're a coach"
        return (f"{lead}, but two things a buyer needs are thin: what you actually fix (the outcome they'd get, and "
                "why it's worth it), and one clear thing to buy or an obvious way to start. This isn't about showing "
                "a price, it's about a stranger seeing the change you make and knowing what to do next.")
    if key == "proof_cred":
        if sc < 7 and (proof_links or ext_reviews):
            joined = _humanlist(list(proof_links) + list(ext_reviews))
            return (f"You've got proof or credibility, but it's a click away, you link out to {joined}. A cold "
                    "visitor won't hunt for it in the first few seconds, so it isn't working when they decide. "
                    "Bring your strongest proof onto the homepage, where they see it without hunting.")
        if sc >= 6:
            return ("A cold buyer gets real reason to believe you: results or testimonials that show you deliver, "
                    "plus names or reviews that show you're the real thing.")
        if sc >= 3:
            return ("There's some here, but it's the easy-to-fake kind. A neat text testimonial counts, but a cold "
                    "buyer half-assumes you wrote it yourself. What they really believe is a video testimonial, or a "
                    "screenshot of a real review with the person's name and face on it. Put one of those up and it "
                    "does far more work than a wall of typed quotes.")
        return ("We didn't spot the proof or credibility a cold buyer believes: client results, testimonials that "
                "name the problem you solved, real reviews, or names a stranger recognises. What you say about "
                "yourself (awards, ‘certified’, ‘as seen on’) a stranger discounts.")
    if key == "proof":
        if sc >= 6: return "There's real proof you can deliver: testimonials, results or numbers a stranger believes."
        if sc >= 3: return "There's a little proof here, but not enough to fully convince a cold stranger. Add a couple of client results with real numbers, or a testimonial that names the problem you solved."
        return "We didn't spot reviews, results or numbers, the kind of proof that makes a stranger believe you can deliver."
    if key == "credibility":
        if sc >= 7: return "Trust a buyer actually believes: real reviews from other people (Google, Facebook, Trustpilot), plus a real business they can reach, a name, a place, a way to get hold of you."
        if ev.get("has_logos"):
            return ("You've got a client or ‘worked with’ list, which is a start. But a logo only tells a stranger "
                    "someone hired you, not what changed for them. Put a one-line result or a review next to it, "
                    "and it turns into proof a cold buyer actually believes.")
        return ("A cold buyer trusts what other people say, not what you say about yourself. We didn't spot the strong "
                "signals a stranger looks for here: real reviews on Google, Facebook or Trustpilot, or a business "
                "they can easily reach.")
    good = {
        "clarity_5sec": "A stranger gets who you help and what they'd get, fast.",
        "specificity": "You name who you help and the exact problem.",
        "offer_clarity": "A cold buyer can see what you fix and there's a clear thing to buy.",
        "proof": "There's real proof you can deliver.",
        "proof_cred": "A cold buyer gets real reason to believe you: results, and trust from other people.",
        "pricing_shown": "Your pricing is easy to find.",
        "technical_health": "Safe and loads fine, the basics are handled.",
    }
    bad = {
        "clarity_5sec": "In five seconds, a stranger can't tell who this is for or what they'd get.",
        "specificity": "It could be for anyone. You don't name who you help or their exact problem.",
        "offer_clarity": "A cold buyer can't see what you actually fix, or there's no clear thing to buy.",
        "proof": "We didn't spot reviews, results or numbers, the kind of proof that makes a stranger believe you can deliver.",
        "proof_cred": "We didn't spot the proof or credibility a cold buyer believes: results, testimonials, real reviews or recognised names.",
        "pricing_shown": "No pricing shown. Often a deliberate choice, not always a problem.",
        "technical_health": "Some technical basics could be tighter, things like security, speed, or how much real content is on the page.",
    }
    thresh = 7 if key == "technical_health" else 6 if key != "specificity" else 5
    return good.get(key, "") if sc >= thresh else bad.get(key, "")

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
    # LEAD CAPTURE authority: the raw keyword scorer above naively scores any 'ebook' mention 8, even a nav-menu
    # link. detect_capture (via build_evidence) is the ONLY authority, and we apply it HERE, unconditionally, so a
    # nav-link magnet / application form / gated freebie / buried capture is scored right whether or not the AI runs.
    scores["lead_capture"] = lead_capture_score(ev.get("capture") or {})
    total_100 = S.weighted_total(scores); score_10 = round(total_100 / 10)

    # AI LAYER: one call re-scores the 8 content criteria by READING the page (keyword matching can't judge
    # whether a story connects or an offer is really clear) AND writes the diagnosis. The rule scores above are
    # the anchor; the AI only moves a number where the copy justifies it. technical_health stays rule-based
    # (it's factual). On no-key / failure / a banned word, ai_analyse returns None and we fall back to rules.
    ai = ai_analyse(row, scores, score_10, ev)
    ai_notes = {}
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
        # CTA FLOOR: the only thing that earns a 2 or 3 for the CTA is genuine priced-shop chaos (many products /
        # add-to-cart competing with everything else). A page with NO shop, however cluttered with soft 'Learn More'
        # buttons, is a WEAK CTA, not chaos, so it floors at 4. The AI won't reliably hold this line, so we enforce it
        # from a structural shop signal (add-to-cart / WooCommerce / Shopify) the AI can't argue with.
        # The CTA can only drop below 4 (to 2-3) when the page genuinely overwhelms with MANY competing PRICED asks:
        # a real add-to-cart shop, a shop the AI can see, OR a wall of 3+ distinct priced offers each with a buy/book
        # button (a booking menu overwhelms just like a shop). A page with no shop and few/no priced offers, however
        # many soft 'Learn More' buttons, is a WEAK CTA (floor 4), not chaos.
        # A crypto-token / 'invest' / crowdfunding CTA on a COACHING page is itself genuine chaos (a purchase CTA
        # AND a 'put your money in this asset' CTA pull in opposite directions), so it also lifts the floor.
        _fin_cta = bool(re.search(r"\btoken\b|crypto|cryptocurrency|\binvest\b|high-potential asset|crowdfund",
                                  (row.get("body_text") or ""), re.I))
        # COMPETING-ASK COUNT (panel's rule): count distinct top-level asks. 4+ different ones with no single dominant
        # button is genuine decision overload, so the floor lifts and the CTA can drop below 4.
        _cb = (row.get("body_text") or "")
        _asks = sum([
            bool(re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", _cb)),                      # a phone number to call/text
            bool(re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", _cb, re.I)),                       # an email address to write to
            (ev.get("capture") or {}).get("kind") not in (None, "none"),                    # a form / sign-up / booking
            bool(re.search(r"\blearn more\b|\bread more\b", _cb, re.I)),                     # 'learn more' style links
            bool(re.search(r"\bbook (?:a |your )?(?:call|session|consultation|appointment)\b", _cb, re.I)),  # a booking CTA
        ])
        # A real shop / a wall of priced offers / an invest-CTA is UNAMBIGUOUS chaos, so it can hard-cap the CTA at 3.
        # A bare 4+-ask count is softer (a focused page may still list a footer phone + email), so it only LIFTS the
        # floor, letting a genuinely-overloaded low AI score stand; the note-based consistency cap below pulls it to
        # <=3 when the AI itself says the asks compete. This keeps us from wrongly nuking a focused page to 3.
        _shop_chaos = bool(row.get("has_shop") or ai.get("has_visible_shop")
                           or row.get("priced_offer_count", 0) >= 3 or _fin_cta)
        _overload = bool(_shop_chaos or _asks >= 4)
        if _shop_chaos and scores.get("clear_cta", 10) > 3:
            scores["clear_cta"] = 3
        elif not _overload and scores.get("clear_cta", 10) < 4:
            scores["clear_cta"] = 4
        # SPECIFICITY can't outrun the OFFER: when the offer is sprawling/unclear (offer_clarity <= 2, e.g. ten things
        # to buy), naming a broad category isn't real specificity, so cap it at offer_clarity + 1 (Columbo's rule).
        if scores.get("offer_clarity", 10) <= 2 and scores.get("specificity", 0) > scores["offer_clarity"] + 1:
            scores["specificity"] = scores["offer_clarity"] + 1
        # The merged proof_cred is what the coach sees, but weighted_total still weighs the corpus keys proof +
        # credibility. Push the merged value onto both so the total reflects it (they now move together).
        if "proof_cred" in scores:
            scores["proof"] = scores["credibility"] = scores["proof_cred"]
        # lead_capture was already set once, from detect_capture, before this AI block (and the loop above skips it),
        # so there is nothing to re-apply here. Recompute the total off the AI-adjusted content scores.
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
        # The MODEL's own proof note, captured before any gate rebuilds it. The self-consistency gate reads THIS (not a
        # rebuilt fallback) so it grades what the model actually said, never the tool's own generated wording.
        _orig_proof_note = ai_notes.get("proof_cred", "")
        # Guard the diagnosis PER FIELD (each is its own labelled section in the report, so a mix reads fine): a
        # banned word in one part only swaps THAT part for the rule version. This stops one stray word wiping the
        # whole AI diagnosis, including the felt "what it's costing you" copy, back to the generic rule text.
        _rc = None
        _rule_keys = set()          # diagnosis parts that fell back to the rule text, so we can refresh them off FINAL scores
        _note_replaced = set()      # per-criterion notes the grounding gate rebuilt (rule text, safe to rebuild again)
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
                critique[k] = _rc[k]; _rule_keys.add(k)
        # GROUNDING GATE (fabrication guard): the AI must never assert a client name, testimonial or $-figure that
        # isn't on the page. Verify every note and diagnosis part against the actual copy; if a piece cites a name or
        # number the page doesn't contain, it's invented, so we drop that piece back to the safe rule wording. And if
        # the PROOF note was the fabrication, the cited proof isn't on the page at all, so cap proof_cred into the
        # honest "we didn't spot proof" band (<=2). The replacement note is then built from that score and they agree.
        _gcopy = " ".join([_clean(row.get("body_text")) or "", _clean(row.get("visible_text")) or "",
                           str(row.get("h1") or ""), str(row.get("page_title") or ""),
                           " ".join(row.get("big_texts") or []), " ".join(row.get("client_logos") or []),
                           str(row.get("logo_heading") or "")])
        # Cap proof FIRST when its note is fabricated, so the safe replacement note is built from the capped score. Cap
        # to 2 (not 5): a fabricated proof note means nothing verifiable is on the page, and only sc<3 yields the honest
        # "We didn't spot the proof..." note; sc 3-5 would still say "there's some here", contradicting the finding.
        if _ungrounded_claims(ai_notes.get("proof_cred", ""), _gcopy):
            scores["proof_cred"] = min(scores.get("proof_cred", 2), 2)
            scores["proof"] = scores["credibility"] = scores["proof_cred"]
        for k in list(ai_notes.keys()):
            if _ungrounded_claims(ai_notes[k], _gcopy):
                ai_notes[k] = criterion_note(k, scores.get(k, 0), ev); _note_replaced.add(k)
        # Names are proof claims anywhere; money in the diagnosis is only a fact-claim in the problem sections (top_fixes
        # / money_left_on_table use $-figures as hypothetical advice, so we don't strip those for a number).
        for k in ("headline_problem", "why_it_costs_clients", "top_fixes", "money_left_on_table"):
            _money = k in ("headline_problem", "why_it_costs_clients")
            blob = " ".join(critique[k]) if isinstance(critique.get(k), list) else (critique.get(k) or "")
            if _ungrounded_claims(blob, _gcopy, money=_money):
                if _rc is None:
                    _rc = rule_critique(row, scores, score_10, ev)
                critique[k] = _rc[k]; _rule_keys.add(k)
        # SELF-CONSISTENCY GATE (issue 5): a score can't contradict its OWN note. Read the MODEL's own note and, when it
        # plainly states a fault the rubric bands as low, cap the score. Record what we capped so its note + diagnosis
        # can be rebuilt off the FINAL score below (a cap paired with a pre-cap note is itself a contradiction).
        _capped = set()
        if _CTA_MANY_RE.search(ai_notes.get("clear_cta", "")) and scores.get("clear_cta", 0) > 3:
            scores["clear_cta"] = 3; _capped.add("clear_cta")          # note says the asks compete -> decision overload
        if _CLARITY_NOPROBLEM_RE.search(ai_notes.get("clarity_5sec", "")) and scores.get("clarity_5sec", 0) > 6:
            scores["clarity_5sec"] = 6; _capped.add("clarity_5sec")    # headline never names the problem -> not 'clear'
        if _PROOF_NONE_RE.search(_orig_proof_note):
            scores["proof_cred"] = min(scores.get("proof_cred", 0), 3); _capped.add("proof_cred")   # nothing to trust
        elif _PROOF_NOCLIENT_RE.search(_orig_proof_note):
            scores["proof_cred"] = min(scores.get("proof_cred", 0), 7); _capped.add("proof_cred")   # no client proof
        scores["proof"] = scores["credibility"] = scores["proof_cred"]
        if _STORY_BURIED_RE.search(ai_notes.get("story", "")) and scores.get("story", 0) > 5:
            scores["story"] = 5; _capped.add("story")                  # reader-facing story is buried low
        # A capped score whose note is a RULE fallback (grounding-replaced) is now stale: rebuild that note off the
        # final score. A capped score whose note is the MODEL's own words is left alone, those words triggered the cap,
        # so they already describe the fault and agree with the lower score.
        for k in _capped & _note_replaced:
            if k != "lead_capture":
                ai_notes[k] = criterion_note(k, scores.get(k, 0), ev)
        # The diagnosis ranks by lowest score, so a post-cap change can move the 'biggest problem'. Refresh any
        # rule-sourced diagnosis part off the FINAL scores so the prose matches the final bars.
        if _capped and _rule_keys:
            _rcf = rule_critique(row, scores, score_10, ev)
            for k in _rule_keys:
                critique[k] = _rcf[k]
        # Any cap above changes the content scores, so recompute the headline total off them.
        total_100 = S.weighted_total(scores); score_10 = round(total_100 / 10)
    else:
        critique = rule_critique(row, scores, score_10, ev)
    ai_powered = bool(ai)   # AI informed the scores, even where a note or two fell back to the rule wording
    # On the rules-only fallback there's no merged score, so build one from the stronger of proof/credibility.
    scores.setdefault("proof_cred", max(scores.get("proof", 0), scores.get("credibility", 0)))

    # The bars a coach sees. Proof and credibility are MERGED into proof_cred; pricing has NO display bar (it gets its
    # own balanced note) but is still weighted into total_100 for parity with the corpus curve; the separate proof/
    # credibility keys stay in `scores` only for the total math.
    DISPLAY_CRIT = ["clarity_5sec", "specificity", "offer_clarity", "proof_cred",
                    "clear_cta", "lead_capture", "story", "technical_health"]
    comparison = {
        k: {"you": scores[k], "market": BENCH[k], "gap": round(scores[k] - BENCH[k], 1)}
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
            ("Your homepage leads with video. We read the words on the page, not the video, and that's the point: "
             "search engines can't watch it, and plenty of visitors won't press play. If your reasons to buy live only "
             "in the video, plenty of people never actually get them.")
            if row.get("has_video") == "yes" else None
        ),
        "evidence": ev,
        "notes": {k: {"pass": (scores[k] >= (7 if k == "technical_health" else 5 if k == "specificity" else 6)),
                      "note": ai_notes.get(k) or criterion_note(k, scores[k], ev)} for k in DISPLAY_CRIT},
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
