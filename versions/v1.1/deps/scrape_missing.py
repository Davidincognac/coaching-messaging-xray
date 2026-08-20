"""
Unattended scraper for the coaching-website research.

Fetches the homepage of every site on the master list that hasn't been scraped
yet, extracts the same columns as the existing dataset (so score_all.py works
unchanged), and appends results incrementally so the run is resumable and
crash-safe.

COSTS ZERO CLAUDE TOKENS — plain Python + requests + BeautifulSoup, runs locally.

Run:  python3 scrape_missing.py
Resumable: just run it again; it skips domains already in the output file.
"""

import os
import re
import csv
import time
import signal
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER_XLSX = "/Users/davidpoole/Downloads/Full Sheet submit 10k+.xlsx"
EXISTING = os.path.join(HERE, "..", "output", "website_copy_dataset_corrected.csv")
OUT = os.path.join(HERE, "output", "new_sites_scrape.csv")
LOG = os.path.join(HERE, "output", "scrape_progress.log")

WORKERS = 24
TIMEOUT = 12
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"}

COLUMNS = ["domain", "page_type", "url", "page_title", "h1", "h2_headings",
           "cta_text", "testimonial_text", "pricing_mentions", "body_text",
           "word_count", "audience_statement", "problem_statement",
           "outcome_claim", "mechanism_claim", "proof_present", "cta_type",
           "optin_present", "booking_link_present", "status"]

# ---------------------------------------------------------------- utils
def clean(t):
    return re.sub(r"\s+", " ", str(t)).strip() if t else ""

def norm_domain(url):
    u = str(url).strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("/")[0].split("?")[0]
    return u.strip()

CTA_WORDS = ["book", "call", "apply", "join", "start", "get started", "contact",
             "register", "schedule", "subscribe", "work with me", "download",
             "learn more", "free", "quiz", "assessment", "enroll", "sign up"]
MONEY_RE = re.compile(r"[£$€]\s?\d[\d,]*(?:\.\d+)?")
BOOKING_HINTS = ["calendly", "acuity", "youcanbook", "book a call", "schedule a call",
                 "book now", "booking", "scheduleonce", "tidycal"]
# NOTE: bare "email" was removed. It matched any page that merely PRINTS a contact
# address ("Email: hello@site.com"), falsely flagging a newsletter sign-up where there
# was none. A real <input type="email"> form is still detected via the DOM check below;
# these are opt-in PHRASES that genuinely mean a sign-up, not the word "email" on its own.
OPTIN_HINTS = ["subscribe to", "join the list", "join our newsletter", "join my newsletter",
               "join our mailing", "join my mailing", "sign up for", "free guide",
               "mailing list"]

def detect_cta_type(t):
    t = t.lower()
    if not t: return ""
    if any(x in t for x in ["book", "schedule", "call", "consult"]): return "book_call"
    if "apply" in t: return "apply"
    if "join" in t: return "join"
    if "register" in t or "enroll" in t: return "register"
    if any(x in t for x in ["download", "free", "guide", "quiz", "assessment"]): return "lead_magnet"
    if "buy" in t or "purchase" in t or "checkout" in t: return "buy_now"
    if "subscribe" in t: return "subscribe"
    return "other"

WHO_RE = re.compile(r"\b(for|help(?:ing)?)\s+(coaches|entrepreneurs|executives|leaders|founders|women|men|parents|managers|therapists|consultants|professionals|teams|business owners|couples|moms|dads|ceos)\b", re.I)
PROBLEM_RE = re.compile(r"\b(struggl\w+|overwhelm\w+|stuck|frustrat\w+|anxious|burnout|stress\w*|tired of|can't|cannot|failing)\b", re.I)

def extract(html, final_url, domain):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = clean(soup.title.get_text()) if soup.title else ""
    h1 = clean(soup.h1.get_text(" ", strip=True)) if soup.h1 else ""
    h2s = " | ".join(clean(h.get_text(" ", strip=True)) for h in soup.find_all(["h2", "h3"])[:12] if clean(h.get_text()))

    # CTAs
    ctas = []
    for tag in soup.find_all(["a", "button", "input"]):
        txt = tag.get("value", "") if tag.name == "input" else tag.get_text(" ", strip=True)
        txt = clean(txt)
        if txt and any(x in txt.lower() for x in CTA_WORDS):
            ctas.append(txt)
    cta_text = " | ".join(dict.fromkeys(ctas[:8]))

    # testimonials — quotes / blockquotes
    quotes = [clean(b.get_text(" ", strip=True)) for b in soup.find_all("blockquote")]
    quotes = [q for q in quotes if len(q) > 30][:3]
    testimonial_text = " || ".join(quotes)

    body_text = clean(soup.get_text(" ", strip=True))
    word_count = len(body_text.split())
    lower_body = body_text.lower()
    lower_html = html.lower()

    pricing = " | ".join(dict.fromkeys(MONEY_RE.findall(body_text)[:8]))

    proof = "yes" if (testimonial_text or re.search(r"\b\d+\+?\s*(clients?|students?|people|years)\b", lower_body) or "testimonial" in lower_html) else "no"
    booking = "yes" if any(h in lower_html for h in BOOKING_HINTS) else "no"
    optin = "yes" if (soup.find("input", {"type": "email"}) or any(h in lower_body for h in OPTIN_HINTS)) else "no"
    cta_type = detect_cta_type(cta_text)

    who = WHO_RE.search(body_text[:1500])
    audience = clean(who.group(0)) if who else ""
    prob = PROBLEM_RE.search(body_text[:2000])
    problem = clean(body_text[max(0, prob.start()-40):prob.end()+40]) if prob else ""

    return {
        "domain": domain, "page_type": "homepage", "url": final_url,
        "page_title": title, "h1": h1, "h2_headings": h2s, "cta_text": cta_text,
        "testimonial_text": testimonial_text, "pricing_mentions": pricing,
        "body_text": body_text[:8000], "word_count": word_count,
        "audience_statement": audience, "problem_statement": problem,
        "outcome_claim": h1, "mechanism_claim": "", "proof_present": proof,
        "cta_type": cta_type, "optin_present": optin,
        "booking_link_present": booking, "status": "ok",
    }

def blank_row(domain, url, status):
    r = {c: "" for c in COLUMNS}
    r.update({"domain": domain, "page_type": "homepage", "url": url,
              "word_count": 0, "status": status})
    return r

def fetch(domain):
    for scheme in ("https://", "http://"):
        try:
            r = requests.get(scheme + domain, headers=HEADERS, timeout=TIMEOUT,
                             allow_redirects=True)
            if r.status_code < 400 and r.text:
                return extract(r.text, r.url, domain)
        except Exception:
            continue
    return blank_row(domain, "https://" + domain, "dead")

# ---------------------------------------------------------------- main
def main():
    master = pd.read_excel(MASTER_XLSX)
    all_domains = sorted({norm_domain(w) for w in master["Website"].dropna() if norm_domain(w)})

    done = set()
    if os.path.exists(EXISTING):
        done |= set(pd.read_csv(EXISTING)["domain"].dropna().map(norm_domain))
    if os.path.exists(OUT):
        done |= set(pd.read_csv(OUT)["domain"].dropna().map(norm_domain))

    todo = [d for d in all_domains if d not in done]
    total = len(todo)
    print(f"Master list: {len(all_domains):,} unique domains")
    print(f"Already have: {len(done):,}")
    print(f"To scrape   : {total:,}\n", flush=True)

    if total == 0:
        print("Nothing to scrape. Done.")
        return

    new_file = not os.path.exists(OUT)
    f = open(OUT, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
    if new_file:
        writer.writeheader()
        f.flush()

    done_count = 0
    dead_count = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(fetch, d): d for d in todo}
        for fut in as_completed(futures):
            row = fut.result()
            writer.writerow(row)
            done_count += 1
            if row["status"] == "dead":
                dead_count += 1
            if done_count % 50 == 0:
                f.flush()
                rate = done_count / (time.time() - t0)
                eta = (total - done_count) / rate / 60 if rate else 0
                msg = f"{done_count:,}/{total:,}  dead={dead_count:,}  {rate:.1f}/s  ETA {eta:.0f} min"
                print(msg, flush=True)
                with open(LOG, "w") as lg:
                    lg.write(msg + "\n")
    f.close()
    print(f"\nDONE. Scraped {done_count:,} sites ({dead_count:,} dead) in {(time.time()-t0)/60:.1f} min")
    print("Output:", OUT)

if __name__ == "__main__":
    main()
