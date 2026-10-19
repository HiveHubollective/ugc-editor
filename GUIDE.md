# UGC Editor: setup and how to use it

Hand Claude your raw clips, B-roll, the brand brief and the brand website. Get back
a finished, captioned ad plus 3-5 hook variations, ready to upload.

It finds your best take of every line, cuts every pause and stumble, adds B-roll on
the right words, zooms, captions and hook text, then checks its own work by
re-listening to the finished video before it shows you anything.

---

## What you need

- **A Mac.** Windows works with a few extra steps (see the end) but is less tested.
- **A paid Claude plan** (Pro or Max). The editor runs in Claude Code, which is
  included in paid plans.
- **About 10 GB of free space**, and decent internet for the first setup.
- About 20 minutes for setup, once.

You don't need HyperFrames, CapCut, or any editing software installed. Setup
installs the few free tools the editor needs.

---

## Step 1: Open Claude Code

1. Download the Claude desktop app from **claude.ai/download** and sign in.
2. Switch to **Code** in the app.
3. When it asks for a folder to work in, pick your **Documents** folder (any
   folder is fine, the editor keeps its own files tidy).

Already use Claude Code in Terminal? That works too.

## Step 2: Paste the setup prompt

Copy this whole prompt, paste it into Claude Code and press enter:

```
Set up the UGC editor for me, step by step, in plain English.

1. Install the skill: if ~/.claude/skills/ugc-editor already exists, update it with
   git pull. If not, run:
   git clone https://github.com/HiveHubollective/ugc-editor ~/.claude/skills/ugc-editor
2. Run: bash ~/.claude/skills/ugc-editor/scripts/setup.sh
   If it says Homebrew is missing, install Homebrew first. Tell me before anything
   asks for my Mac password, and tell me exactly what to type or click.
3. Fix anything setup.sh marks with ❌ and run it again until it says READY.
4. Make a folder called "UGC Jobs" in my home folder.
5. Tell me it's ready and how to start my first job.
```

Claude will ask permission before running commands. Read what it's about to do,
then allow it. When Homebrew installs, Terminal asks for your **Mac login password**:
type it (nothing shows while you type, that's normal) and press enter.

Setup downloads a speech model (about 460 MB) the first time. Leave it running.

When you see **READY**, you're done. You never have to do this again.

## Step 3: Start a job

In Claude Code, type:

```
Start a new UGC job for [brand name]
```

Claude makes a folder for the job and opens it. Drop your files into it:

| Folder | What goes in it |
|---|---|
| `raw/talking/` | Every talking-to-camera clip. All the takes, any order, mistakes and all. |
| `raw/broll/` | Your B-roll clips. |
| `raw/images/` | Product photos or screenshots you want popping up on screen (optional). |
| `brief.md` | Paste the brief in, or drop the brief PDF or screenshots into the folder. Add the brand website link. |
| `script.md` | Your script, if you had one (optional). |

Then tell Claude:

```
Files are in. Edit it with 4 hook variations.
```

Add anything specific: "keep it under 40 seconds", "end on the CTA", "use the take
where I laugh for the hook".

It takes roughly 10-20 minutes depending on how much footage there is. Finished
videos land in the job's `out/` folder.

## Step 4: Review and give notes

Watch every version with the **sound on**. Claude checks its work by re-listening to
the video, but it can't judge tone, energy or whether a take feels right.

Give notes in plain words, with rough times if you can:
- "Swap the hook to the take where I say it slower"
- "The sip B-roll comes in too early"
- "Cut the line about headaches"
- "Make the captions the brand's blue"

Claude rebuilds in a few minutes.

**Want to add your own captions or text in CapCut?** Ask for a clean version: "Make me
clean versions too". You get the same edit with no captions or text on it, ready to
finish in CapCut.

---

## Filming tips that make the edit better

- **Film vertical** (9:16), in natural light, phone at eye level.
- **Say each line 2-3 times.** Pause for a second before you restart, so the
  editor can find the clean take.
- **Keep going after a mistake.** Just restart the sentence. The editor cuts the
  stumble.
- **Film B-roll from the brief's list**, a few seconds each: product in hand, the
  pour or application, first use, reaction, the product in your real life. Start
  recording before the action and stop after it.
- **Don't look at the camera during B-roll** unless that's the point of the shot.
- Take a few clean **product photos** (front of pack, range laid out) for pop-ups.

---

## What it can't do (yet)

- Judge which take *feels* best. It picks the cleanest. Tell it if you prefer another.
- Add trending music. Add that in TikTok or Instagram when you post.
- Invent footage. If a shot's missing, film 10 seconds of it.
- Multi-person or multi-camera interviews.

---

## Troubleshooting

**"command not found: git"** Your Mac asks to install developer tools. Click Install,
wait, then paste the setup prompt again.

**Setup stops at the speech model.** Usually a slow connection. Run setup again; it
picks up where it left off.

**"Permission denied" or a file it can't read.** Make sure the job folder is in your
home folder (not iCloud-only or an external drive that's disconnected).

**Windows.** Ask Claude: "Set up the UGC editor on Windows: install ffmpeg and uv with
winget, then follow scripts/setup.sh by hand." The editor itself works the same.

**Anything else.** Tell Claude what happened in plain words, and paste the error.
It can read the setup script and fix most things itself.
