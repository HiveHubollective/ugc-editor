---
name: ugc-editor
description: Edit raw UGC footage into finished, high-converting short-form video ads for any brand, with 3-5 hook variations. Use when a creator drops raw talking clips, B-roll, a brand brief, a script or a brand website and wants the video edited ("edit my UGC", "edit this for [brand]", "make the hook variations", "start a new UGC job"). Handles out-of-order takes, picks the clean take, cuts every pause and stumble, places B-roll, adds captions, hook text and zooms, and checks its own work by ear and eye before showing anyone. Also use for "set up the UGC editor".
---

# UGC editor

You are the editor. The creator gives you raw footage and a brief; you hand back
finished ads they can upload. Work through the steps in order and don't skip the
checks: the creator is trusting you to catch the stumbles, the dead air and the
claims that would get the ad rejected.

Run every script with `nice -n 10 ~/.ugc-editor/venv/bin/python` (written `PY` below):
`nice` lets the Mac keep up with everything else while it renders.
Scripts live in this skill's `scripts/` folder (written `S` below).

## Your rules
The creator's own rules live in `~/Desktop/UGC Jobs/My editing rules.md`, a plain
file they can open, read and edit themselves. It sits outside this skill folder, so
updating the editor never touches it. Read it at the start of every job; where it
disagrees with the playbook or the house style, it wins (put look changes like
caption colour or size into the plan's `style_overrides`).

**When the creator asks the editor to work differently** ("always make captions
bigger", "never use whips", "end every ad on the product"), write it into that rules
file straight away, tell them you've saved it, and follow it from then on. Don't edit
the files in this skill folder to do it: they're replaced when the editor updates.

In a web (cloud) session the computer is wiped when it ends, so there keep the rules
in `My editing rules.md` at the top of the session's repo and commit and push after
adding one.

## Updating the editor
Only when the creator asks ("update the UGC editor"): `git -C ~/.claude/skills/ugc-editor
pull`, then run `scripts/setup.sh` again. If the pull complains about local changes,
`git -C ~/.claude/skills/ugc-editor stash` first (their rules file isn't in there, so
nothing of theirs is lost). Tell them in one or two lines what's new (`git log`).

## Web (cloud) sessions
If you're running in a cloud session rather than on the creator's Mac, the footage
comes as a Google Drive link (shared "anyone with the link"). Make the job folder
as usual, then download every file into `Raw files/`: `uv pip install --python
~/.ugc-editor/venv/bin/python gdown` and `~/.ugc-editor/venv/bin/gdown --folder
"<link>" -O "<job>/Raw files"`, or list the folder with the Google Drive connector
and `curl -L` each file from `https://drive.usercontent.google.com/download?id=<id>&export=download&confirm=t`.
If a download is blocked, tell them to set the environment's Network access to Full.
Hand finished videos back as files in the chat, one per message, since the
session's computer is wiped when it ends.

## 0. Setup check (first time, or if anything errors)
Run `bash S/setup.sh`. It installs what's missing and ends with READY or NOT READY.
Don't edit until it says READY. If it says LOW-MEMORY MODE (8 GB or less), follow
"One heavy job at a time" in step 4 strictly, and tell the creator to close CapCut,
Photos and spare browser tabs while you edit.

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
Read `references/editing-playbook.md` (the craft), the creator's rules file, and
`references/edit-plan.md` (the format) before writing it. In short:
- Hook → problem → solution → proof → CTA, built from the best take of each line.
- Copy the `say` text from lines.md exactly, and lock each segment to its line ids.
- Drop anything the brief rules out, plus medical or unverifiable claims.
- B-roll on the words it illustrates, punch zooms on 1 key word every few seconds,
  image cards where the creator names the product or its features (`"image"` is the
  path inside the job, e.g. `"Raw files/From website/serum-01.jpg"`).
- 3-5 hook variants: different opening lines from the footage, each with its own
  hook text. Never invent words the creator didn't say.

## 4. Build, listen, look, fix
**One heavy job at a time.** Rendering (build.py), transcribing, qa.py and any
cut-out or segmentation step each use a lot of memory. Run them one after another and
wait for each to finish: never two builds at once, never a build running in the
background while you start another heavy step, never parallel agents rendering. On an
8 GB Mac two at once is enough to crash Claude and lose the session. To check the
Mac: `sysctl -n hw.memsize` (8589934592 or less is 8 GB).

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
`PY S/build.py <job>` for the main edit first. It also saves the core (everything
after the hook) in `.work/core/`. Then `--variant <name>` for each hook, strictly one
at a time: build it, run qa.py on it, then start the next. Each variant reuses the saved
core, so only its new hook is rendered (it prints "reusing 24.1s of the main edit's
core"). If you change anything after the hook, build the main edit again before the
variants, or each one renders the changed part again (correct, just slower). `--fresh`
renders a variant in full. Finished files are in `<job>/Finished videos/`.

If the creator wants to finish the edit in CapCut themselves (their own captions,
text or music), add `--clean`: the same cut, zooms and B-roll with no captions, hook
text or cards, saved as `<name>_clean.mp4`.

## 6. Hand it over
Tell the creator, briefly:
- the files and which hook each one opens with
- what you cut or changed from the brief and why (claims, takes you skipped)
- what to check by ear (names, brand words, the joins), because you can't hear tone

**Review page (optional).** Notes are quicker on the video than in chat. If you have
the Artifact tool, publish a private review page each round:
1. Make a small copy of each version for the page, one at a time, into
   `<job>/.work/review/`, named `<id>-r<round>.mp4` (`<id>` is `main` or the variant name):
   `nice -n 10 ffmpeg -y -i "<video>" -vf scale=720:-2 -c:v libx264 -crf 28 -preset veryfast -c:a aac -b:a 96k -movflags +faststart "<copy>"`.
   Each must be under 15 MB (use `-crf 32` if one isn't).
2. Copy `references/review-page.html` to `<job>/.work/review/review.html`. Set its
   `<title>` to "<Brand> ad review" and fill in the `review-config` block: the brand,
   the round, and one entry per version (`id`, a `label` in the creator's words like
   "Hook 2: makeup", and `src`, the copy's file name).
3. Publish it with the Artifact tool: `file_path` the review.html, `files` mapping each
   copy's file name to its path, `capabilities: {"db": {}}`, icon `video`. Give the
   creator the link: "Play each version with sound on, pause where something's off, pick
   Cut, B-roll, Caption or Other and write a note. Tell me when you're done."
4. When they're done, read the notes: ArtifactData `list` on the `notes` collection
   (each has `video`, `t` in seconds, `type`, `text`, `status`, `round`). Fix every open
   note, rebuild and check it as in steps 4 and 5.
5. Mark each one: ArtifactData `update` on collection `notes`, the note's id, with its
   `version` from the list as `if_version` and `{"status": "fixed", "fix": "<what you
   changed, in plain words>", "fixed_round": <the new round>}`. If you can't
   fix one (the footage doesn't have it), leave it open and put why in `fix`.
6. Make the next round: new copies named `-r<round>`, raise `round` and each `src` in
   review.html, and publish the same file again (same `file_path` in this chat; in a new
   chat, pass the page's `url`). In `files`, add the new copies and set the old ones to
   `null`. The notes stay on the page with what you changed, so the creator checks the fixes.

No Artifact tool, or the page says notes can't be saved? Do it in chat: ask for notes
as a time and what to change ("Hook 2, 0:12, cut the pause before 'honestly'"), and
after each round reply with the same list, each marked fixed with what you changed.

Then take their notes ("swap the hook take", "B-roll too early", "cut that line") and
rebuild. After each fix, ask: "Want me to add that to my rules so it doesn't happen
again?" If yes (or it's the second time they've said it), add it to `My editing rules.md` (see
Your rules, above): their note in their words, then what to do instead. The next job
starts from the improved rules.

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
| Two renders at once, or one left running in the background | One heavy job at a time: wait for each to finish |
