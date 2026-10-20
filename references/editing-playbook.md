# Editing playbook

How a high-converting UGC ad gets cut. Brand look changes per job; this doesn't.

## Structure (DTC direct response)

| Beat | Time | What it does |
|---|---|---|
| Hook | 0-3 s | Stops the scroll. The most specific, relatable line in the footage. Hook text box on screen. |
| Problem | 3-10 s | The pain in the creator's own words. Relatable, never shaming. |
| Solution | 10-25 s | Product enters: what it is, how it's used, what changed. |
| Proof | 25-40 s | Features with a reason (ingredients, numbers from the pack), routine, taste, honest opinion. |
| CTA | last 3-5 s | One clear action from the brief. If the brief has none: "go to [brand] website and try them". |

**The first 3 seconds decide everything.** Before locking the hook, ask: would a
stranger scrolling past stop, and want to see how this ends? The hook has to raise a
question or a feeling the rest of the ad actually answers. A hook the footage can't
pay off is clickbait, and brands notice. No intro, logo or pause before the first word.

Default length 30-50 s unless the brief says otherwise. End on the CTA or, if the
creator asks, on the strongest relatable line.

## Picking takes
- Same line said several times → use the **last complete, clean take** unless an
  earlier one is clearly better worded.
- ⚠ lines are stumbles or cut-offs. Use them only if there's no other take.
- Keep whole sentences. Don't splice half a sentence from one take onto another.
- A soft or swallowed first word ("because", "so") can be dropped if the sentence
  still reads well without it.
- Never put words in the creator's mouth. Every word comes from the footage.
- **Cut between phrases, not inside them.** A phrase is what they say in one breath.
  An um that runs straight into the next word stays: cutting it clips the word
  beside it. A slightly longer ad with every word whole beats a tight one with a
  clipped word.
- Never speed up the voice to save time.

## Compliance (every job)
- Nothing on the brief's "don't say" list.
- No medical conditions or cures (e.g. "it fixed my eczema"), no before/after if the
  brief bans it, no weight or body talk unless the brief allows it.
- Personal experience is fine ("I've noticed fewer headaches") if the brief lists
  that benefit; flag it in the handover so the creator can decide.
- Numbers must match the pack or website (e.g. "15% vitamin C", not "lots of vitamin C" or a rounded number).
- Spell the brand and product the way the brand does, via `caption_fixes`.

## Pacing
- Every pause, um, breath and false start is cut. The build does this from the
  audio; qa.py `--learn` catches the rest.
- One idea per segment. If a segment runs over ~8 s, add B-roll or a card in it.

## Visual rhythm (the "cool edits")
- Something changes every 2-3 s: a cut, a zoom, B-roll, a card.
- The build alternates wide / tight framing on every real cut and pushes in slowly
  through each shot, so jump cuts feel deliberate.
- `punch` 1 key word every 3-5 s: the strongest word in the line (the pain, the
  product name, a number). Snap zoom in, hold, ease out. Don't punch filler words.
- First frame zooms out from close, so the video opens with movement.
- The creator's face is the trust. Never leave them off screen for more than about
  3.5 s; break a long B-roll run with a cut back to them.
- B-roll enters with a whip (fast blurred slide) on energetic beats, a straight cut
  on calm ones. 1.5-3 s each. Show what is being said, the moment it's said:
  product named → product on screen; "I make one up" → the pour; "taste" → the sip.
- Each B-roll moment is used once per ad. A second use needs a different moment
  from the clip, not the same pour again.
- Cards: product photo when the product or its range is named; a list card when
  ingredients or features are listed. Keep them in the top third, off the face.

## On-screen text
- Hook text: 2 lines, ≤ 14 characters a line, uppercase, a question or a sharp
  statement that matches the spoken hook ("DULL SKIN EVERY MORNING?").
- Captions: one word at a time, as spoken, in the lower-middle of the frame. Each
  word appears 2 frames early so it never lags the voice.
- **Never over the mouth or chin**, and hook text or cards never over the face,
  above all in the first second, when the viewer is deciding if this is a real
  person worth listening to. qa.py checks this on every render.
- Everything stays inside the safe zone: away from the top 10%, bottom 20% and
  right edge where the app buttons sit.

## Hook variations
Make 3-5. Each opens with a different line from the footage (a different pain, a
different angle, the taste/opinion line, the most surprising line) and has its own
hook text. The body after the hook stays the same. Name the files by the angle:
`<brand>_hook2_makeup.mp4`.

## Sound
- Voice evened out and normalised to -14 LUFS. B-roll audio always muted.
- No sound effects. Music only when the creator drops a track in Raw files or asks:
  set `"music"` in the plan, it sits quietly under the voice and dips when they speak.
- Never let the music fade or duck the last spoken word.
- Never use a popular or trending song in an ad for a brand: the brand needs music it's
  licensed to run as an ad. Free option: Pixabay Music (commercial use, no credit
  needed, check each track). Many brands prefer no music so they can add their own.

## Brand assets
- Logos and product shots come from the brand: their brief, their website, or the
  creator's own photos. Never redraw, trace or generate a logo, and never generate
  a product shot. If there's no real asset, use the brand name as plain text.

## Rules (learned from creators, add new ones here)
Every note a creator gives twice becomes a rule here, written as: the note in their
words, then what to do instead. That way nobody gives the same note three times.

- Cut every dead space, not just the long ones.
- B-roll never starts on the creator looking at the camera.
- No pop sounds or cartoon animations by default.
- No invented B-roll or AI footage of the product.
