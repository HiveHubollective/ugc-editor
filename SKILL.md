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
Each job is one folder (default `~/UGC Jobs/<brand-name>/`). If the creator says
"start a new UGC job", make it with this layout and open it in Finder (`open <folder>`):

```
<job>/
  brief.md            the brand brief (paste text, or drop the PDF / screenshots next to it)
  raw/talking/        every talking-to-camera clip, any order, all the takes
  raw/broll/          B-roll clips
  raw/images/         product photos / screenshots to pop up on screen (optional)
  script.md           the script, if there was one (optional - most UGC is natural)
```
Ask them to drop files in and tell you when it's done. Then read everything in
the folder: the brief (Read PDFs and screenshots too), the script, and the brand
website (WebFetch it) for product facts, claims, spelling and colours. Note:
- who the ad is for, the product, the angle the brief asks for
- **what NOT to say** (claims, words, competitor names) and anything regulated
- the CTA, length, number of hooks, and any must-say lines
If the brief has no CTA or length, use the defaults in `references/editing-playbook.md`.

## 2. Ears and eyes
1. `PY S/transcribe.py <job>` → `work/lines.md`: every line, numbered, with repeated
   takes grouped (`[TAKE A01 2/4]`) and stumbles flagged (⚠).
2. `PY S/look.py <job>` → contact sheets in `work/look/`. Open every sheet. For each
   B-roll clip write down what happens when (e.g. "pour 1.5-4.5s, looks at camera
   0-5s, sip 5.5-7.6s"). Never use the moments where they look at the camera,
   fumble or the shot shakes.

## 3. Plan the edit (`<job>/edit.json`)
Read `references/editing-playbook.md` (the craft) and `references/edit-plan.md` (the
format) before writing it. In short:
- Hook → problem → solution → proof → CTA, built from the best take of each line.
- Copy the `say` text from lines.md exactly, and lock each segment to its line ids.
- Drop anything the brief rules out, plus medical or unverifiable claims.
- B-roll on the words it illustrates, punch zooms on 1 key word every few seconds,
  image cards where the creator names the product or its features.
- 3-5 hook variants: different opening lines from the footage, each with its own
  hook text. Never invent words the creator didn't say.

## 4. Build, listen, look, fix
```
PY S/build.py <job> --preview          fast draft
PY S/qa.py <job>/out/<name>_preview.mp4 --learn
PY S/build.py <job> --preview          again, with the learned cuts
PY S/qa.py <job>/out/<name>_preview.mp4
```
qa.py re-transcribes the finished video and reports clipped/missing words, leftover
ums and pauses, and loudness. `--learn` turns leftover pauses into cuts for the next
build. Then open its contact sheets and check: hook text and cards readable and not
covering the face, captions on screen, B-roll on the right words, nothing awkward.
Fix the plan and rebuild until qa.py says PASS (one leftover pause under 0.4s is fine).
If a word keeps coming back missing, use a different take or end the segment earlier.

## 5. Final renders
`PY S/build.py <job>` for the main edit, then `--variant <name>` for each hook. Run
qa.py on each. Finished files are in `<job>/out/`.

## 6. Hand it over
Tell the creator, briefly:
- the files and which hook each one opens with
- what you cut or changed from the brief and why (claims, takes you skipped)
- what to check by ear (names, brand words, the joins), because you can't hear tone
Then take their notes ("swap the hook take", "B-roll too early", "cut that line") and
rebuild. Add anything they correct twice to the Rules in `references/editing-playbook.md`.

## Mistakes to avoid
| Don't | Do |
|---|---|
| Edit before reading the brief's "don't say" list | Read it first, every job |
| Use a take with ⚠ when a clean take exists | Pick the clean take, usually the last complete one |
| Trust the transcript's spelling of brand names | Add `caption_fixes` for the brand and product names |
| B-roll that starts with them looking at the camera | Start the B-roll where the action starts (from look.py) |
| Pop sounds, cartoon animations, effects nobody asked for | Clean cuts, zooms and whips; sound effects only on request |
| Showing the creator a video you haven't QA'd | Build → qa --learn → build → qa → look at the sheets |
