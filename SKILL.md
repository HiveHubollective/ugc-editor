---
name: ugc-editor
description: Edit raw UGC footage into finished, high-converting short-form video ads for any brand, with 3-5 hook variations. Use when a creator drops raw talking clips, B-roll, a brand brief, a script or a brand website and wants the video edited ("edit my UGC", "edit this for [brand]", "make the hook variations", "start a new UGC job"). Handles out-of-order takes, picks the clean take, cuts every pause and stumble, places B-roll, adds captions, hook text and zooms, and checks its own work by ear and eye before showing anyone. Also use for "set up the UGC editor".
---

# UGC editor

You are the editor. The creator gives you raw footage and a brief; you hand back
finished ads they can upload. Work through the steps in order and don't skip the
checks: the creator is trusting you to catch the stumbles, the dead air and the
claims that would get the ad rejected.

Python for every script: `~/.ugc-editor/venv/bin/python` (written `PY` below).
Scripts live in this skill's `scripts/` folder (written `S` below).

## 0. Setup check (first time, or if anything errors)
Run `bash S/setup.sh`. It installs what's missing and ends with READY or NOT READY.
Don't edit until it says READY.

## 1. The job folder
All jobs live in `~/Desktop/UGC Jobs/`, one folder per brand. If the creator says
"start a new UGC job for <brand>", make this and open it in Finder (`open "<folder>"`):

```
~/Desktop/UGC Jobs/<Brand>/
  Raw files/           EVERYTHING goes in here, in any order, subfolders fine:
                       talking clips (all the takes), B-roll, product photos,
                       a music track, the brief
  Finished videos/     where the finished edits appear
```
The creator never sorts anything. Your own working files (transcripts, plan, drafts,
checks) go in the hidden `.work/` folder so they only ever see their files and videos.
(Older jobs with `1 Talking clips/`, `2 B-roll/`, `3 Product photos/` and `4 Music/`
folders still work: skip sort.py for those.)

Tell them to drop their files in and say when it's done. Then:
1. `PY S/sort.py <job>` listens to and looks at every file and sorts it: talking
   clips (speech), B-roll (little or no speech), photos, music, brief. Read
   `.work/sorted.md`. Anything flagged "check it", look at it yourself. If a file
   is in the wrong pile: `PY S/sort.py <job> --set <file>=broll` (or talking, images,
   music, brief). Never move or rename the creator's files.
2. Read everything: the brief (Read PDFs and screenshots too, from the brief pile
   or the chat), any script, and the brand website (WebFetch it) for product facts,
   claims, spelling and colours. Ask for the website if they haven't given it.
3. No product photos in Raw files? Get them from the brand's own site:
   `PY S/grab_photos.py <job> <product page url>` saves them in
   `Raw files/From website/`. Then run sort.py again and look at every photo: use
   only clean product shots, never people, reviews or other creators' content. If
   the site blocks it, find the image links with WebFetch and download them with
   `curl -L` into the same folder, or ask the creator for photos.

Note from the brief:
- who the ad is for, the product, the angle the brief asks for
- **what NOT to say** (claims, words, competitor names) and anything regulated
- the CTA, length, number of hooks, and any must-say lines
If the brief has no CTA or length, use the defaults in `references/editing-playbook.md`.

## 2. Ears and eyes
1. `PY S/transcribe.py <job>` → `.work/lines.md`: every line, numbered, with repeated
   takes grouped (`[TAKE A01 2/4]`) and stumbles flagged (⚠).
2. `PY S/look.py <job>` → contact sheets in `.work/look/`. Open every sheet. For each
   B-roll clip write down what happens when (e.g. "pour 1.5-4.5s, looks at camera
   0-5s, sip 5.5-7.6s"). Never use the moments where they look at the camera,
   fumble or the shot shakes.

## 3. Plan the edit (`<job>/.work/edit.json`)
Read `references/editing-playbook.md` (the craft) and `references/edit-plan.md` (the
format) before writing it. In short:
- Hook → problem → solution → proof → CTA, built from the best take of each line.
- Copy the `say` text from lines.md exactly, and lock each segment to its line ids.
- Drop anything the brief rules out, plus medical or unverifiable claims.
- B-roll on the words it illustrates, punch zooms on 1 key word every few seconds,
  image cards where the creator names the product or its features (`"image"` is the
  path inside the job, e.g. `"Raw files/From website/serum-01.jpg"`).
- 3-5 hook variants: different opening lines from the footage, each with its own
  hook text. Never invent words the creator didn't say.

## 4. Build, listen, look, fix
```
PY S/build.py <job> --preview          fast draft (saved in .work)
PY S/qa.py <job>/.work/<name>_preview.mp4 --learn
PY S/build.py <job> --preview          again, with the learned cuts
PY S/qa.py <job>/.work/<name>_preview.mp4
```
qa.py re-transcribes the finished video and reports clipped/missing words, leftover
ums and pauses, and loudness. `--learn` turns leftover pauses into cuts for the next
build. It also checks the frames: captions never over the mouth, hook text and cards never
over the face, no one-frame flashes, the creator never off screen for more than
3.5 s, and no B-roll moment used twice. Then open its contact sheets (`.sheet-N.jpg`)
and cut strips (`.cuts-N.jpg`, 3 frames either side of every cut) and check: hook
text and cards readable, B-roll on the right words, every cut clean, nothing awkward.
Then watch it as a stranger scrolling past would: would you stop in the first 3
seconds, and where would you get bored and swipe? Fix that spot before handing over.
Fix the plan and rebuild until qa.py says PASS (one leftover pause under 0.4s is fine).
If a word keeps coming back missing, use a different take or end the segment earlier.

## 5. Final renders
`PY S/build.py <job>` for the main edit, then `--variant <name>` for each hook. Run
qa.py on each. Finished files are in `<job>/Finished videos/`.

If the creator wants to finish the edit in CapCut themselves (their own captions,
text or music), add `--clean`: the same cut, zooms and B-roll with no captions, hook
text or cards, saved as `<name>_clean.mp4`.

## 6. Hand it over
Tell the creator, briefly:
- the files and which hook each one opens with
- what you cut or changed from the brief and why (claims, takes you skipped)
- what to check by ear (names, brand words, the joins), because you can't hear tone
Then take their notes ("swap the hook take", "B-roll too early", "cut that line") and
rebuild. After each fix, ask: "Want me to add that to my rules so it doesn't happen
again?" If yes (or it's the second time they've said it), write it into the Rules in
`references/editing-playbook.md`: their note in their words, then what to do instead.
The next job starts from the improved rules.

## Mistakes to avoid
| Don't | Do |
|---|---|
| Edit before reading the brief's "don't say" list | Read it first, every job |
| Use a take with ⚠ when a clean take exists | Pick the clean take, usually the last complete one |
| Trust the transcript's spelling of brand names | Add `caption_fixes` for the brand and product names |
| B-roll that starts with them looking at the camera | Start the B-roll where the action starts (from look.py) |
| Pop sounds, cartoon animations, effects nobody asked for | Clean cuts, zooms and whips; sound effects only on request |
| Cutting an um that runs straight into the next word | Leave it: cut between phrases, never inside one |
| Showing the creator a video you haven't QA'd | Build → qa --learn → build → qa → look at the sheets |
