# Master Issue List — Coaching Site Audit Tool
## Pre-Code-Rewrite Review Document

---

## SYSTEMIC ISSUES (Deduplicated & Ranked Worst-First)

---

### ISSUE 1 — Proof Note Fabricates Non-Existent Testimonials, Names, and Numbers

**What's wrong:** The tool invents named client testimonials, specific revenue figures, and case study details that do not exist anywhere in the page copy, then uses these fabrications to justify inflated proof scores.

**Root cause:** The LLM is hallucinating "expected" proof elements for a coaching page rather than grounding strictly in the provided copy. No hard constraint prevents the model from generating plausible-sounding names and numbers when the copy is sparse.

**Frequency:** 11 of 39 sites
**Examples:** `theclosingcoach.com` (Andy $500k, Austin close-rate, Lacey $30k–$80k — none exist), `thematernitycoach.com` (NHS/Premier Foods logo strip, four testimonials — none exist), `resourcequeen.us` (Alexandria Neri, Jaimee Carson — neither appears in copy)

**Priority: 10/10**
*(Severity 10 × near-universal in sparse-copy cases)*

**Action required:** Add a hard pre-generation constraint: the model must quote the exact string from the copy for every testimonial name, number, or award it cites. If no quotable string exists, the field must return null and the score must reflect absence. Zero-tolerance rule: any name, number, or award not verbatim in the copy is a disqualifying hallucination.

---

### ISSUE 2 — Lead Capture Type Fabricated (Newsletter Detected Where None Exists)

**What's wrong:** The tool repeatedly detects and scores a "newsletter sign-up" capture mechanism on pages that contain no email subscription form, no opt-in field, and no magnet — only a printed email address, a contact link, or nothing at all.

**Root cause:** The model infers a newsletter exists from navigation labels ("Resources & Newsletter," "RCBM Newsletters") or from the general expectation that coaching sites have newsletters, without verifying that an actual form with an email entry field is present in the copy.

**Frequency:** 14 of 39 sites
**Examples:** `whatwouldjennsay.com` (only a printed Gmail address), `spearsstrong.com` (no form visible), `sunnydays.com` (only a contact link), `rcbm.net` (newsletter link = archive viewer, not signup)

**Priority: 9/10**
*(Severity 8 × very high frequency)*

**Action required:** Require the model to identify a literal form field (email input, subscribe button, or equivalent markup signal) before classifying capture kind as "newsletter." A navigation link to a newsletter archive or a printed email address must never be classified as a capture mechanism. Add a validation rule: `capture.kind = 'newsletter'` requires evidence of an actual subscription form in the copy.

---

### ISSUE 3 — Proof Score Inflated When Fabricated or Absent Evidence Is Cited

**What's wrong:** The tool assigns proof scores of 5–8 on pages with zero verifiable client testimonials, zero media mentions, and zero third-party validation, because it either fabricates evidence (Issue 1) or treats unverifiable self-claims as proof.

**Root cause:** The scoring rubric is not enforced as a hard gate. The model can award a high proof score without a corresponding verified evidence string from the copy. Self-claims ("award-winning," "100% retention rate," "thousands helped") are treated as equivalent to third-party proof.

**Frequency:** 13 of 39 sites
**Examples:** `theclosingcoach.com` (proof=7, zero testimonials in copy), `thematernitycoach.com` (proof=5, zero testimonials), `alanpbrown.com` (proof=5, testimonial section headers with no content beneath them)

**Priority: 9/10**
*(Severity 9 × high frequency)*

**Action required:** Implement a proof score ceiling rule: if zero named client testimonials with specifics are quotable from the copy AND zero recognisable third-party media/brand names appear, proof score must not exceed 3. Self-claims without a verifiable source cap at 2. The model must cite the exact copy string that justifies each proof point.

---

### ISSUE 4 — Inspirational/Author Quotes Miscounted as Client Testimonials

**What's wrong:** The tool counts third-party inspirational quotes (from named authors, sailors, or public figures) placed in a testimonials section as genuine client testimonials, inflating the proof count and misleading the coach about the strength of their social proof.

**Root cause:** The model identifies any quoted text in a testimonials section as a client testimonial without checking whether the attribution is a coaching client or a public figure. The existing rule ("a third-party INSPIRATIONAL author quote is NOT a client testimonial") is not being enforced at inference time.

**Frequency:** 4 of 39 sites
**Examples:** `harmonylifecoach.net` ("Ash AIves" motivational quote counted as client testimonial), `tracypruzanroy.com` (Jessica Watson sailor quote in testimonials section), `the-entourage.com` (Matthew Jacques quote references "The Entourage," a different program)

**Priority: 8/10**
*(Severity 8 × moderate frequency, direct misinformation to coach)*

**Action required:** Add a classification step before counting testimonials: does the quote reference the coach by name, a specific coaching engagement, or a measurable personal outcome? If not, it must be flagged as "non-client quote" and excluded from the testimonial count. The model must also check whether the attributed name is a recognisable public figure.

---

### ISSUE 5 — Scores Contradict the Tool's Own Detected Findings (Internal Inconsistency)

**What's wrong:** The tool assigns a score in one field, then writes notes or a diagnosis that directly contradict that score — e.g., scoring `clear_cta=9` while noting "four competing asks," or scoring `clarity_5sec=8` while diagnosing "the headline doesn't name the problem."

**Root cause:** Scores and notes are generated in separate passes (or the scoring rubric is applied loosely), so the model can produce a high score and then write a critical diagnosis without reconciling the two. There is no post-generation consistency check.

**Frequency:** 16 of 39 sites
**Examples:** `daivergent.com` (clear_cta=9, notes say multiple competing CTAs), `the-entourage.com` (clarity_5sec=8, notes say "headline leads with destination not pain"), `abbeylouie.com` (clear_cta=5, notes identify four competing asks which per rules = 2–3), `sunnydays.com` (clear_cta=4, notes say "four competing actions" which per rules = 2–3)

**Priority: 8/10**
*(Severity 7 × very high frequency)*

**Action required:** Implement a post-scoring validation pass: for each scored field, the model must check that the score is consistent with the rubric band implied by its own notes. Specifically: if notes identify 4+ competing CTAs, `clear_cta` must be ≤ 3; if notes say "headline doesn't name the problem," `clarity_5sec` must be ≤ 6; if notes say "no testimonials," `proof` must be ≤ 3. These are mechanical rules that can be enforced programmatically.

---

### ISSUE 6 — Lead Capture Score Misapplied to Wrong Rubric Band

**What's wrong:** The tool detects a capture type correctly (e.g., buried email opt-in) but then applies the score for a different capture category (e.g., newsletter score of 3 instead of buried opt-in score of 4), or scores a booking/contact form as 0 when it should be 2.

**Root cause:** The scoring rubric has distinct bands (contact/booking=2, newsletter=3, buried opt-in=4, gated=5, on-page up top=8) but the model does not reliably map its own detection to the correct band. The `capture.kind` field and the `lead_capture` score are generated independently without a lookup enforcement.

**Frequency:** 10 of 39 sites
**Examples:** `harmonylifecoach.net` (buried=false detected, scored 3 instead of 5+), `abbeylouie.com` (buried email opt-in detected, scored 3 instead of 4), `centreiamcoaching.com` (booking capture present, scored 0 instead of 2)

**Priority: 7/10**
*(Severity 6 × high frequency)*

**Action required:** Make the `lead_capture` score a deterministic lookup from `capture.kind` + `capture.buried` + `capture.gated`, not a free-form LLM judgment. The mapping table already exists in the rubric; enforce it as code, not as a prompt instruction.

---

### ISSUE 7 — Niche Field Returns Null When Niche Is Explicitly Named in Copy

**What's wrong:** The tool outputs `niche: null` on pages where the target audience is clearly and repeatedly stated in the copy (e.g., "neurodivergent teens and adults," "new and transitioning leaders," "coaches and solopreneurs").

**Root cause:** The niche detection step appears to require a specific format or keyword match rather than semantic extraction. Pages that describe their niche in plain language without a single-word label cause the field to fail silently.

**Frequency:** 7 of 39 sites
**Examples:** `daivergent.com` ("people with disabilities, neurodivergent teens and adults"), `truestart.us` ("new leaders, expats, first-time managers"), `alanpbrown.com` ("coaches and doing-it-all-myself solopreneurs")

**Priority: 6/10**
*(Severity 5 × moderate frequency)*

**Action required:** Replace keyword-match niche detection with a semantic extraction prompt: "In one short phrase, what specific audience does this page serve? If the copy names a group, use their language." Null should only be returned if the copy contains genuinely no audience signal whatsoever.

---

### ISSUE 8 — Niche Classified Too Broadly (e.g., "Wellness" for a Chiropractor or Grief Coach)

**What's wrong:** The tool assigns a generic niche label ("wellness") to pages that explicitly name a specific service type (chiropractic care, grief coaching, women's life coaching), losing the specificity that makes the diagnosis useful.

**Root cause:** The niche extraction defaults to a high-level category when the copy doesn't use a single clean label, rather than extracting the most specific accurate descriptor from the copy.

**Frequency:** 5 of 39 sites
**Examples:** `alignwc.com` (niche="wellness," page is a chiropractic clinic), `harmonylifecoach.net` (niche="wellness," page is "Women's Life Coach"), `good-grief.co.uk` (grief coaching classified generically)

**Priority: 5/10**
*(Severity 4 × moderate frequency)*

**Action required:** Add a specificity instruction to niche extraction: prefer the most specific accurate label over a broad category. If the copy says "chiropractor," the niche is "chiropractic care," not "wellness." Test against a set of known-specific niches.

---

### ISSUE 9 — Story Score Inflated When Reader-Facing Content Is Buried, Not Front-Loaded

**What's wrong:** The tool awards high story scores (7–9) when reader-facing language exists somewhere on the page, even when it is buried three sections down and the headline/opening is entirely coach- or company-focused. Per the tool's own rules, buried reader language should floor the story score, not elevate it.

**Root cause:** The model evaluates whether reader-facing language exists anywhere in the copy rather than where it appears. Placement (headline vs. deep body) is not weighted in the scoring.

**Frequency:** 6 of 39 sites
**Examples:** `the-entourage.com` (story=9, pain point "buried three sections down" per tool's own notes), `spearsstrong.com` (story=7, reader language only in lower "Learning about YOU first" section), `good-grief.co.uk` (coach story mid-page, not in hero)

**Priority: 5/10**
*(Severity 5 × moderate frequency)*

**Action required:** Add a placement modifier to story scoring: if the first reader-facing line appears below the second major content block, apply a score ceiling of 5 regardless of how strong the language is lower on the page. The rubric rule "one reader-facing line floors at 3" should be paired with "reader-facing language only in deep body caps at 5."

---

### ISSUE 10 — Wrong Source Material Processed (Cookie Policy Instead of Homepage)

**What's wrong:** On at least one site, the tool received and scored a cookie/privacy policy page instead of the homepage, then fabricated an entire homepage analysis including headline quotes, CTA labels, and faculty descriptions that do not exist in the provided text.

**Root cause:** No input validation step checks that the provided copy is actually a homepage (or the intended page type) before running the analysis. The model proceeds to hallucinate expected homepage content when the input is clearly wrong.

**Frequency:** 1 confirmed of 39 sites, but likely underdetected
**Examples:** `speakeasyinc.com` (entire copy is cookie boilerplate; tool fabricated headline "WE HELP YOU FIND YOUR VOICE," "Enroll Now," "Browse Courses," faculty descriptions)

**Priority: 5/10**
*(Severity 10 × low confirmed frequency, but catastrophic when it occurs)*

**Action required:** Add an input validation gate: before scoring, check that the copy contains at least one of: a headline, a CTA, a service description, or a named person. If the copy appears to be a legal/policy page (keywords: "cookie," "GDPR," "data controller," "consent"), reject the input and return an error rather than proceeding to score.

---

### ISSUE 11 — Parser Failures Silently Drop Sites (Unterminated String Errors)

**What's wrong:** 12 of 39 sites returned a `finder_error` with "Unterminated string" JSON parse failures, producing zero usable output. These sites were silently skipped with no partial result, no fallback, and no user-facing explanation.

**Root cause:** The tool's output serialisation is not validating or sanitising the JSON before returning it. A single unescaped character in the copy (likely a quote or special character in scraped page text) breaks the entire JSON object.

**Frequency:** 12 of 39 sites (31%)
**Examples:** `problemio.com`, `howtobecomemore.com`, `awleadershipadvisory.com`, `fivecapitals.net`, `futurepathworld.com`, `tlrnation.com`, `eqstrategist.com`, `nexpathcoaching.com`, `flowerstreetstrategies.com`, `leadershipcommunicationgroup.com`, `hyphensandspaces.com`, `firebirdmethod.com`, `laurenmiura.com`

**Priority: 5/10**
*(Severity 5 × very high frequency — 31% failure rate is a reliability crisis)*

**Action required:** Sanitise all scraped copy before it enters the prompt (escape quotes, strip control characters). Wrap the JSON serialisation in a try/catch with a fallback partial-result schema. Return a structured error object with the domain and error type rather than a silent failure. This is a pure engineering fix, not a prompt fix.

---

### ISSUE 12 — Unverifiable Claims Treated as Verified Proof (Self-Assertions Accepted at Face Value)

**What's wrong:** The tool accepts unverifiable self-claims ("award-winning," "100% retention rate," "thousands helped," "leader in diagnosing ADHD") as legitimate proof signals and scores them as if they were third-party verified, without flagging them as unsubstantiated.

**Root cause:** The model has no instruction to distinguish between a self-claim and a third-party-verified claim. Both are treated as "proof present" in the scoring logic.

**Frequency:** 6 of 39 sites
**Examples:** `capeableconsulting.com` ("100% return and retention rate" — no case study), `alanpbrown.com` ("award-winning ADD Crusher" — no award named), `rcbm.net` ("leader in diagnosing ADHD" — no media link)

**Priority: