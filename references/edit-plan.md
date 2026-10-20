# edit.json format

One file per job, at `<job>/.work/edit.json`. `build.py` reads it.

```json
{
  "name": "glowco-serum",
  "style": "house",
  "style_overrides": {"caption": {"colour": "#FF6E00"}},
  "fps": 30,
  "caption_fixes": {"glow co": "GlowCo", "colors": "colours"},
  "hook": {"text": ["Dull skin", "every morning?"]},

  "segments": [
    {"beat": "hook", "clip": "B", "lines": "B01",
     "say": "I wake up and my skin just looks tired, every single day.", "punch": ["tired"]},
    {"beat": "solution", "clip": "B", "lines": "B07-B08",
     "say": "That's why I got so excited when I found this serum."}
  ],

  "broll": [
    {"clip": "applying.mov", "in": 1.5, "dur": 2.5,
     "at": {"seg": 3, "word": "apply"}, "transition": "whip"}
  ],

  "cards": [
    {"image": "Raw files/From website/range-01.jpg", "w": 0.62, "at": {"seg": 6, "word": "three"}, "dur": 4.2, "x": 0.5, "y": 0.17},
    {"title": "Key ingredients", "rows": ["Vitamin C", "Niacinamide", "Hyaluronic acid"], "at": {"seg": 4, "word": "vitamin"}, "dur": 2.6, "y": 0.16}
  ],

  "variants": [
    {"name": "hook2_makeup", "replace_first": 2, "hook": {"text": ["Makeup won't", "sit right?"]},
     "segments": [ {"clip": "B", "lines": "B04", "say": "..."}, {"clip": "B", "lines": "B01", "say": "..."} ]}
  ]
}
```

## Fields

**name** file name for the outputs (`Finished videos/<name>.mp4`, `Finished videos/<name>_<variant>.mp4`).

**style** a file in `styles/` (default `house`). **style_overrides** changes any part of
it for this brand, e.g. caption colour to the brand colour, if it reads well on video.

**caption_fixes** transcription spellings → correct spelling, lowercase keys. Always
add the brand and product names here.

**hook.text** 1-3 short lines for the hook box. Shown until the end of the first
segment (or set `"dur"` in seconds).

**segments** in story order. Each one:
- `clip` the letter from lines.md (A, B, ...)
- `lines` the line id or range it comes from (`"B07"`, `"B07-B08"`). Locks the search
  to that take, so a repeated take elsewhere is never picked by accident.
- `say` the exact words to keep, copied from lines.md. You can start or end mid-line
  (drop a swallowed "because", stop before a rambling tail).
- `punch` words that get a snap zoom (0-2 per segment).
- `skip` optional `[[start, end], ...]` source seconds to cut inside the segment
  (a stray um qa.py keeps finding).
- `beat` hook / problem / solution / proof / cta (for your own reading).

**broll** each one: `clip` (the file name, as listed under broll in `.work/sorted.md`), `in` (start second inside the
clip, from look.py), `dur` (1.5-3 s), `at` (`{"seg": n, "word": "..."}` the word it
starts on, optional `"offset"` in seconds), `transition` `"whip"` or `"cut"`.

**cards** `image` (path inside the job) or `title` + `rows` for a list card; `at`, `dur`,
`x`/`y` centre as a fraction of the frame, `w` width as a fraction, `crop` optional
`[left, top, right, bottom]` fractions of the photo to show only the product. Always crop
phone photos to the product: a full portrait photo is too tall for a card.

**music** optional `{"file": "track.mp3", "volume": 0.2}`: a track from the music pile in `.work/sorted.md`, looped
or trimmed to length, faded in and out, and ducked under the voice. 0.15-0.25 is a good
background level.

**variants** each one replaces the first `replace_first` segments with its own
`segments` and gets its own `hook.text`. Everything after stays the same.
