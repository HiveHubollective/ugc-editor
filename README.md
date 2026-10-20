# UGC Editor for Claude

A Claude Code skill that edits raw UGC footage into finished, captioned video ads
for any brand, with 3-5 hook variations.

Drop everything into one folder: talking clips (all takes, any order), B-roll,
photos, music, the brief. Give it the brand website. It sorts the files itself,
grabs product photos from the site if you have none, picks the clean takes, cuts
every pause and stumble, builds hook → problem → solution → proof → CTA, places
B-roll on the right words, adds zooms, whips, captions and hook text, then
re-listens to its own edit and fixes what it finds before you see it.

**Setup and how to use it: [GUIDE.md](GUIDE.md)**


## What's inside

```
SKILL.md                      the edit, step by step (Claude reads this)
references/editing-playbook.md   the craft: structure, takes, pacing, zooms, text, hooks
references/edit-plan.md       the edit plan format
styles/house.json             the default look (captions, hook box, motion, pacing)
scripts/setup.sh              installs and checks everything
scripts/sort.py               sorts Raw files: talking clips, B-roll, photos, music, brief
scripts/grab_photos.py        downloads product photos from the brand's website
scripts/transcribe.py         ears: every word timed, takes grouped, stumbles flagged
scripts/look.py               eyes: contact sheets of B-roll and product photos
scripts/build.py              renders the edit and every hook variation
scripts/qa.py                 re-listens and looks at the finished video, learns missed cuts,
                              checks captions stay off the mouth and every cut is clean
fonts/                        Fredoka and Rubik (SIL Open Font Licence)
```

## Licence

MIT (see LICENSE). Fonts: SIL Open Font Licence.
