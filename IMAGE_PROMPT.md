# The Angelo image prompt

Paste block A and block B together into GPT. Block A never changes, so Angelo stays the same
bird every batch. Block B is the only part you rewrite, and it holds five scenarios.

Five sets of ready-made scenarios are at the bottom, one per blog cluster.

---

## Block A: the part you always paste

> You are generating illustrations for a blog. Every image must show the same character,
> drawn the same way, so that five images made today sit next to five made last month and
> look like one set.
>
> **The character.** Angelo is a plump cartoon bird, roughly pigeon-shaped, in flat medium
> blue (#2E75B6) with a paler blue belly. He has a thin white halo floating a little above
> his head, two small blue feathers sticking up at the back of his head, a large grey-and-
> white beak, and white eyes with small dark pupils and heavy black eyebrows that carry the
> expression. He wears a plain black necktie and nothing else. His feet are thin, pale,
> three-toed and bird-like. He is short and round, not tall, about three heads high.
>
> **The drawing style.** Flat 2D cartoon, cel-shaded, no gradients on the character. Thick
> confident black outlines on Angelo, thinner lines on everything behind him. Backgrounds
> are muted greys and off-whites, softly lit, drawn in less detail than Angelo so he reads
> first. Blue is the only saturated colour in the frame, and it belongs to Angelo and to
> one or two small background objects. No neon, no rainbow palettes, no lens flare, no
> photorealism, no 3D render, no anime.
>
> **The palette.** Angelo blue #2E75B6, deeper blue #1F5286, near-black lines #111111,
> background greys #F4F5F7 to #D8D8DC, white #FFFFFF. A single small red accent (#C8102E)
> is allowed in at most one of the five images, and only if a scenario calls for something
> going wrong.
>
> **The frame.** Landscape 3:2. Angelo occupies the middle third and is never cropped at
> the feet. Leave the top eighth of the frame quiet, with no important detail in it.
>
> **Hard rules.**
> - No readable text anywhere in the image. No signs, no captions, no headings, no logos,
>   no numbers on charts. Where a document or screen appears, show lines and blocks standing
>   in for writing, the way a comic does.
> - No other people or characters. Angelo is alone in every frame.
> - No speech bubbles and no thought bubbles.
> - Nothing that dates the picture: no phone models, no brand names, no year on anything.
> - Do not add a border, a frame, a drop shadow behind the whole image, or a background
>   colour outside the scene.
>
> **What to give me.** Five separate images, one per scenario below. Each one a different
> setting, a different posture and a different expression from the other four, so the five
> can sit in one article without repeating. Deliver them as five individual landscape 3:2
> images, not as a grid or a contact sheet.

---

## Block B: the part you rewrite

> **The five scenarios.**
>
> 1. …
> 2. …
> 3. …
> 4. …
> 5. …

Write each one as a situation, not a mood. "Angelo at a desk looking at two folders, one
thick and one thin" works. "Angelo feeling conflicted" does not, because the model has to
invent what that looks like and it invents something different every time.

One sentence each is enough. Say where he is, what he is doing with his hands, and what his
face is doing.

---

## Ready-made scenario sets

### Set 1: the niche posts

> 1. Angelo in an office corridor facing a long row of identical closed grey doors, one
>    wing half-raised, unsure which to open.
> 2. Angelo at a desk with a large map spread out, leaning close and pointing one wing-tip
>    at a single spot on it.
> 3. Angelo holding two folders, one thick and one thin, weighing them like scales, eyebrows
>    down.
> 4. Angelo standing in front of a wall of small filing drawers, one drawer pulled open, his
>    face pleased.
> 5. Angelo trying to carry four boxes at once, the top one sliding, his beak clenched.

### Set 2: the coaching website posts

> 1. Angelo holding a stopwatch in one wing and looking at a blank paper screen with the
>    other, eyebrows raised.
> 2. Angelo with a clipboard, ticking down a list, an unimpressed expression.
> 3. Angelo on a stepladder polishing the outside of an empty picture frame while the wall
>    behind him is bare.
> 4. Angelo peering through a magnifying glass at a sheet of paper held very close to his
>    beak.
> 5. Angelo asleep in a desk chair beside a telephone that is not ringing.

### Set 3: the getting clients posts

> 1. Angelo holding a door open and gesturing through it, hopeful, with an empty room beyond.
> 2. Angelo at a desk holding out an empty testimonial card, looking at it sideways.
> 3. Angelo behind a market stall with nothing on the counter, arms folded, waiting.
> 4. Angelo running after a paper aeroplane with both wings out, feet off the ground.
> 5. Angelo sitting calmly on a bench while a paper aeroplane lands neatly beside him.

### Set 4: the marketing posts

> 1. Angelo standing in front of a noticeboard covered in identical blank cards, one wing
>    scratching his head.
> 2. Angelo with a megaphone lowered to his side, looking at it rather than using it.
> 3. Angelo laying out a short row of stepping stones on the floor and standing on the first.
> 4. Angelo at a desk writing one short line on an otherwise empty sheet of paper, focused.
> 5. Angelo painting the outside of a plain wooden box a bright colour while the box is open
>    and empty.

### Set 5: spares, for whatever comes next

> 1. Angelo carrying a single heavy box up a staircase, determined.
> 2. Angelo sitting on the floor surrounded by loose paper, sorting it into two piles.
> 3. Angelo looking into a mirror and seeing his own back, confused.
> 4. Angelo holding a tape measure across a blank sheet of paper.
> 5. Angelo leaning on a closed laptop with a cup beside him, relaxed for once.

---

## After GPT gives you the files

1. Crop or resize to **1200 × 800**. Bigger than that is wasted; the prose column is 680px
   and the file is served at whatever size you upload.
2. Save as PNG with a name that describes the picture, not the post:
   `angelo-two-folders.png`, not `image1.png`. You will reuse these.
3. Drop them in `posts/images/`.
4. In the post, write `![Angelo weighing two folders, one thick and one thin](angelo-two-folders.png)`.
   The alt text is part of the syntax, so a picture cannot go out without one. Write what is
   in the picture, not what the post is about.
5. Push. The width and height go on the tag automatically, so nothing on the page jumps
   while the picture loads.

**Changing a picture means giving it a new filename.** Images are cached for a year, so
overwriting a file means nobody sees the new one.
