# UGC Editor: how to set it up and use it

Give Claude your raw clips, the brand brief and the brand website. Get back a
finished, captioned ad plus 3-5 hook variations.

![How it works](docs/images/how-it-works.png)

## 1. Get Claude on your desktop
- You need a **Mac** and a **paid Claude plan** (Pro or Max).
- Download the app from **claude.ai/download**, open it and sign in.
- Click the **Code** tab. Above the message box, set **Environment** to **Local**
  (not Cloud), and pick your **Desktop** as the folder.

![Set these before your first message](docs/images/code-tab.png)

## 2. Give Claude the editor
Copy this, paste it into Claude and press Enter:

```
Install the UGC editor for me from https://github.com/HiveHubollective/ugc-editor
Put it in ~/.claude/skills/ugc-editor and run its scripts/setup.sh. Fix anything
that isn't ticked and run it again until it says READY. Then make a folder called
"UGC Jobs" on my Desktop. Explain each step in plain English, and tell me before
anything asks for my password.
```

Click **Allow** whenever Claude asks. If a Mac pop-up asks to install developer
tools, click **Install**. Claude may ask for your Mac password once to install its
tools: type it (nothing shows as you type) and press Enter. Done when you see
**READY**. You only do this once.

![What READY looks like](docs/images/ready.png)

## 3. Your UGC Jobs folder

![Where your files go](docs/images/where-your-files-go.png)

Say **"Start a new UGC job for [brand]"**. Claude makes a folder for that brand
inside **UGC Jobs** on your Desktop:

| Folder | What goes in it |
|---|---|
| **1 Talking clips** | every talking-to-camera clip, all the takes, mistakes and all |
| **2 B-roll** | your B-roll clips |
| **3 Product photos** | product photos for pop-ups (optional) |
| **4 Music** | a licence-free track, if you want music (optional) |
| **Finished videos** | your finished edits appear here |

AirDrop your clips from your phone and drag them into the right folder. Drop the
brief (PDF or screenshots) into the brand folder too, or paste it into the chat.

## 4. Ask for the edit, then changes
```
Files are in. Here's the website: [link]. Edit it with 4 hook variations.
```
Then watch every version with sound on and ask for changes in normal words:
"use a different take for the hook", "cut the line about X", "the B-roll comes in
too early", "make clean versions too" (no captions or text, to finish in CapCut).

---

**Stuck?** Tell Claude what happened in plain words and paste any error. It can
fix most things itself.
