# The Coaching Website Audit — Rulebook

The single source of truth for how the tool scores, detects, and writes. Every rule here is
implemented in `audit.py` and mirrored in the QC panel's calibration (`audit-qc-panel-v2.js`).
If the code and this document ever disagree, that is a bug to fix, not a judgement call.

**North star:** a WRONG output is worse than a generic fallback. When in doubt, don't guess.
Only one person signs anything off: David.

---

## 0. Scope rules

- We read ONE page, and we say exactly which one. A bare domain = the homepage; a path
  (`/dating-coaching`) = that specific page. Never claim "homepage" when a subpage was audited.
- We read the TEXT and what's visible in the screenshot. We don't watch videos or visit inner pages.
- If the page scrape comes back near-empty (`scrape_thin`, under 200 chars of real text), we do NOT
  invent scores off nothing — that is flagged, not scored.

---

## 1. Scoring rules (each criterion 0–10)

### 5-second clarity
Does the RIGHT person (a cold visitor who HAS this problem) know the page is for them in 5 seconds?
- 9–10: instantly sees themselves AND senses the outcome.
- 7–8: sharply names their real situation/problem.
- 5–6: clear audience OR clear service, not sharp.
- 3–4: names a broad category, FIELD or topic (even a vague tagline like "Divorce Differently"), or a
  generic benefit. The reader isn't singled out.
- 0–2: a personal NAME, or field-less abstraction ("You Are Worthy") — no clue what field this even is.
- A problem-naming line that is one of the biggest lines on the page is PROMINENT — never "buried".
- Reader-first copy is CLEAR, never "abstract". A name headline is a real weakness even for the famous.

### Specificity (who + what problem)
- Judge the CLARITY of the problem, not narrowness. Breadth is not vagueness.
- A named shared problem scores high even for a broad audience.
- Do NOT re-punish the generic headline already docked in clarity.

### Offer clarity & value
- Two things: (1) can a cold buyer see the FIX/outcome, and (2) is there one clear thing to buy/start?
- NOT about price. But an explicit price present ("£20/month") floors this at 5.

### Proof & credibility (merged)
- Score the STRONGEST signal; do not average down.
- **Logo walls:** recognisable major brands under a "trusted by" heading = 6–7, WITH the caveat that a
  logo doesn't show relationship depth. Unrecognisable/unlabelled logos = ambiguous, middling at best.
- **Reviews:** a LIVE embedded Google/Trustpilot widget with a review count = 9–10. A screenshot of
  stars is a claim, not proof.
- **Testimonials:** video or a real review-card with name+photo = strong; plain text = weak. NEVER state
  the name-format ("first names only") unless you can actually see it.
- **Authority floor:** a verifiable professional licence, OR 2+ recognisable named media outlets, is
  strong checkable authority and floors proof at 7 even with no widget. Below 7 dock ONLY for missing
  CLIENT results (testimonials, case studies, numbers) — never for the mere absence of a review widget.
- A named award + a named founder-with-tenure floors proof at 4. Never call a named thing "unnamed".

### Clear CTA
- Collapse repeats first: the SAME "Learn More" six times = ONE job.
- 9–10: one strong action (book/apply), the only main thing, repeated.
- 4: multiple weak CTAs, no strong step — weak but not chaos.
- 3: three or four genuinely different competing asks.
- 2: a genuine priced SHOP or a wall of 3+ priced offers, each with a buy/book button.
- HARD RULE: no shop → the score cannot go below 4, however many soft buttons there are.
- The NOTE must name the real failure — overload ("cut to one"), never "no CTA" (that's absence).

### Lead capture
- Real on-page magnet, up top: 8.
- Buried magnet (low on the page): 4.
- Gated "free" resource (locked behind membership/purchase): 5.
- Email opt-in with a value hook: 5 (buried: 3).
- Newsletter: 3 (buried in the footer with no reason: 2).
- Contact form: 2. Application form: 2.
- A magnet keyword that only appears as a NAV-MENU link is NOT an on-page magnet — skip it.
- Nothing: 0.

### Story
- Does the copy connect to the READER's own situation, or is it the coach's CV? Reader-focused = high.

### Technical health
- Loads, safe, basics handled = 10. Dock for real technical weakness only.
- NOT part of the overall score. Almost every site passes it (market ~9), so counting it only pads the number.
  Still scored and shown (labelled "not counted"), and flagged if something is genuinely broken. The overall
  score is about how well the page speaks to a buyer, not the plumbing.

---

## 2. Detection rules

- **Niche:** label ONLY from identity text. An explicit self-stated coach title ("certified divorce
  coach") is authoritative even if the page lists related services. Related niches collapse to one
  family; 2+ unrelated families with no explicit title = None. A wrong label is worse than None.
- **Capture priority:** on-page magnet (not nav-link) → custom-named magnet behind a form → application
  form → contact form → email opt-in with hook → newsletter → email-form fallback → none.
- **Shop:** 2+ visible product tiles/add-to-cart, OR the platform wired up, OR 3+ distinct priced offers.
- **Logos:** read brand names from image ALT text (a downscaled screenshot can't); capture the heading
  over the strip so "trusted by [recognisable brands]" gets proper credit.
- **Scrape rescue:** if the HTML extractor under-captures, fall back to the rendered visible text.
- **Subpage:** audit the exact page the URL points to; don't strip to the homepage.

---

## 3. Voice & copy rules

- Blunt, plain, a twelve-year-old could read it. Short sentences. Say the thing, then stop.
- BANNED words/marks: land/lands, "the gap", quietly, guessing, drift, rescue, leverage, unlock,
  elevate, harness, delve, robust, foster, tapestry, testament, furthermore, moreover, em dashes.
- No vague grade-words: middling, moderate, decent, somewhat, reasonable.
- **No invented facts or entities:** never name a competitor, invent a rival's quote, cite a study, a
  statistic, or a source not in the copy. Example lines are your own generic illustration ("e.g. …"),
  never attributed to anyone.
- Anchor every fault to the COPY, not the person. Never scold. Never imply the coach doesn't know their
  own audience or is "guessing".
- Multi-service coach → offer a MENU headline, not a single-service one that throws the rest away.
- Say "we didn't spot X", never a flat "you have no X". Keep paragraphs short (≈55 words max).

---

## 4. Governance (proposed — for David's sign-off)

- **Reviewers of sites:** the expert table — Klaff, Hughes, Ogilvy, Columbo, Cialdini, Orwell,
  Sutherland, Solomon.
- **Arbiter of clashes:** Solomon rules; Sutherland argues for the status quo first to stop
  over-correction.
- **Implementation & QA:** a rule-audit pass checks every rule here is coded, non-contradictory, and
  fires correctly on test sites (see the session notes for the proposed workflow).
- **Final sign-off:** David. Nothing ships without it.
