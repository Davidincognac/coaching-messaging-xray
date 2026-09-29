# Content plan

Built from `coaching-longtail-keywords.xlsx` (Keyword Planner, UK + US + Canada, English,
Sep 2025 to Aug 2026) crossed against the data we already own. Working document, not copy.

## Read the volumes honestly first

151 keywords. 126 of them sit at 10-100 searches a month. Fourteen reach 100-1K. Ten are
under 10.

This is a small-volume market and pretending otherwise would set the wrong expectation. Two
hundred visits a month from search would be a good year-one outcome, not a failure. What
makes it worth doing is that the intent is sharp: somebody typing "list of life coaching
niches" is a coach deciding what to be, which is the exact moment the buying triggers page
is useful to them.

Planner also merges close variants and hides zero-volume long-tails. Every problem-aware
phrase we seeded ("why is my coaching website not converting", "coaching website mistakes")
came back with nothing, which does not mean nobody searches it. It means Planner will not
report it. Those still get written, they just get validated in Search Console later instead
of before.

## The rule that decides the order

We have three proprietary datasets. Each one maps onto one keyword theme. Where a theme has
no data behind it, we are writing opinion and competing on nothing.

| Cluster | Keywords | Low comp | The asset behind it |
|---|---|---|---|
| Niche | 33 | 9 | 117 niches, 918 subniches, each with buying psychology |
| Coaching websites | 37 | 7 | 10,954 sites scored on 11 criteria |
| Getting clients | 43 | 7 | The buying triggers research |
| Marketing for coaches | 27 | 15 | Positioning only, no dataset |

Marketing has the most low-competition keywords and the least evidence. It goes last, and
it goes last on purpose.

## Cluster 1: Niche (start here)

Nine low-competition keywords, zero at 100-1K, and `triggers_data.json` holds 117 niches and
918 subniches with LF8 drives, awareness level, sophistication and the job-to-be-done for
each. Nobody writing "list of coaching niches" has that. Most publish a list of thirty
guesses.

The intent match is also the cleanest in the whole set. Somebody searching for coaching
niches is deciding who to serve. The triggers page answers exactly that question.

**Pillar:** every coaching niche there is, and what each one's buyers actually want
Targets: `list of life coaching niches`, `coaching niches list`, `life coach niches`,
`niches in life coaching`, `coaching niche ideas`

**Spokes:**
1. The most profitable coaching niches, and why "profitable" is the wrong question
   → `most profitable coaching niches`, `most lucrative coaching niches`
2. How to pick a coaching niche when you are good at several things
   → `coaching niche ideas`, `how to choose a coaching niche`
3. Christian life coaching niches → `christian life coach niches` (small, specific, ours to take)
4. What a niche is not: the difference between a niche and an audience

## Cluster 2: Coaching websites

Eight keywords at 100-1K, and the scorecard is the only dataset of its kind.

Watch the intent here. "life coach website template" and "coach website design" are people
looking to build or buy a site, not to read research. They are High competition and the
searcher wants a product we do not sell yet. Take the low-competition ones first.

**Pillar:** what 10,954 coaching websites score, and where the marks go
Targets: `website design for life coaches` (100-1K, Low), `life coaching websites that work`

**Spokes:**
1. The five-second test, and why 83% fail it
2. Coaching website examples that actually convert → `beautiful coaching websites`,
   `life coach website ideas`
3. Health coach websites, scored → `health coach website design`, `health coach websites`
4. What to put on a coaching homepage, in the order it should appear

## Cluster 3: Getting clients

Biggest theme, highest commercial intent, and the head terms are Medium competition, so the
low-competition long-tails come first.

**Pillar:** how coaches actually get clients, according to 10,954 websites
Targets: `how to get coaching clients`, `how to get life coaching clients` (both 100-1K)

**Spokes:**
1. How to get your first coaching client → `how to get your first life coaching client`
2. Getting coaching clients without a website → `how to get coaching clients without a website`
3. What an ideal coaching client actually is → `ideal coaching client`
4. Attracting clients instead of chasing them → `how to attract life coaching clients`

## Cluster 4: Marketing for coaches

Written last, as planned. The line above about having no data was wrong, and worth recording
as wrong: `coach_site_research/linkedin/output/headline_scores.csv` holds 11,377 coaches'
LinkedIn headlines scored out of 10, which is a marketing dataset and nobody else has it.
The average headline is 2.56. 420 coaches have written "Executive Coach" and stopped.

That turned the cluster from positioning into evidence, and it lets the pillar do something
none of the others can: put all three datasets side by side and show they fail at the same
point. Websites average 9.03 on the build and 4.49 on clarity. Headlines average 2.56.
Buyers decide on proof in 92.9% of markets and 66.5% of sites show none. One failure,
three places.

**Pillar:** marketing for coaches, and what the counting says
Targets: `marketing for coaches` (100-1K, Low), `marketing for coaching business` (100-1K, Low)

**Spokes:**
1. Social media marketing for coaches → `social media marketing for coaches`, the home of the
   11,377 headlines
2. A life coach marketing plan → `life coach marketing plan`, `life coach marketing strategy`
3. Content marketing for coaches → `content marketing for coaches`, built on the awareness split
4. Branding a coaching business → `branding coaching business`

`marketing for health coaches` was the obvious fifth and was dropped: it would have competed
with the health coach websites post in cluster 2 for the same intent.

## Internal linking

Three rules, no exceptions:

1. Every spoke links up to its pillar, in the first two paragraphs, on a phrase that
   describes the pillar rather than on "click here".
2. Every pillar links down to all of its spokes.
3. Spokes link sideways only where a reader genuinely needs the other post. Two or three per
   post, not a footer full of them.

Across clusters, link once and only where it earns it. The niche pillar should link to the
websites pillar where it talks about saying the niche out loud on a homepage.

## Per-post checklist

- One target keyword, in the H1, naturally
- `summary` in front matter answers the question in one or two sentences, because that is
  the passage an AI will lift and the callout a reader sees first
- H2s phrased as questions where the query is a question
- The answer under each H2 arrives in the first sentence, then gets justified
- A number from our own data in the first third of the post
- `## FAQ` section, three or four real questions, which becomes FAQPage schema automatically
- Links up, down and sideways per the rules above
- The buying triggers CTA is automatic, do not hand-write another one

## Where this has got to

Twenty posts. All four clusters are written, each a pillar plus four spokes, and every
figure in them is asserted by `check_post_numbers.py`, which recomputes from the scorecard
CSV, `triggers_data.json` and the LinkedIn headline scores, and fails if a post and the data
ever disagree. 79 claims.

Cluster 3 leans on two datasets at once and cluster 4 on all three, which turned out to be
the strongest thing we can say: the psychology says proof decides the sale in 92.9% of
markets, and the corpus says 66.5% of coaching websites show none. The distance between
those two numbers is the argument, and the LinkedIn headlines say it a third time.

## What is not done yet

- Nothing in the plan. The four clusters are done and the keyword list is covered.
- No post carries an image. Support is built and `posts/images/` is empty apart from its
  README. The websites cluster wants a chart of where the marks go.
- Every post is dated 28 or 29 September 2026. Twenty posts in two days is honest and there
  is no ranking penalty for it, but changing the dates now is worse than leaving them, since
  Google has already seen them. Stagger the next cluster instead, if there is one.
- The problem-aware phrases Planner would not report on are still unvalidated. That needs
  Search Console impressions, not more writing.

Search Console: the Domain property `goingbeyondtheillusion.com` is the one to use, verified
by DNS TXT on 29 September 2026, sitemap read at 17 pages before this cluster went in. A new
property has no history, so the phrases Planner refused to report on get checked there in a
few weeks rather than now.
