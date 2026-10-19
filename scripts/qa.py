#!/usr/bin/env python3
"""Check a finished video before a human sees it: ears, eyes and levels.

Usage:
    python3 qa.py <video.mp4> [--learn]

--learn  turns every leftover pause / um it hears into a cut in the raw
         footage (work/auto_skips.json); build again to apply it.

Needs the <video>.timeline.json that build.py writes next to the video.
  ears   re-transcribes the finished video and compares it with the words the
         plan asked for: clipped or missing words, leftover ums / repeats, and
         any pause still longer than 0.35 s
  eyes   saves contact sheets (<video>.sheet-N.jpg) with a frame at every
         segment start, so Claude can look at framing, captions and overlays
  levels integrated loudness (target -14 LUFS) and true peak
Prints PASS or a list of things to fix.
"""
import json, re, subprocess, sys
from difflib import SequenceMatcher
import numpy as np
from PIL import Image, ImageDraw


def norm(t):
    return [x for x in re.sub(r"[^a-z0-9' ]", ' ', t.lower().replace('%', ' percent ')).split() if x]


def main():
    video = sys.argv[1]
    tl = json.load(open(video.replace('.mp4', '.timeline.json')))
    problems = []

    # ears
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', video, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = len(a) // 160
    r_out = np.sqrt((a[:n * 160].reshape(n, 160) ** 2).mean(1))
    thr_out = 0.25 * np.percentile(r_out, 95)
    from faster_whisper import WhisperModel
    m = WhisperModel('small.en', device='cpu', compute_type='int8')
    segs, _ = m.transcribe(a, word_timestamps=True, beam_size=5)
    heard = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]
    want = ' '.join(w[0] for w in tl['words'])
    W_, H_ = norm(want), []
    owner = []
    for i, (w, s, e) in enumerate(heard):
        for x in norm(w):
            H_.append(x); owner.append(i)
    sm = SequenceMatcher(None, W_, H_, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            continue
        t = heard[owner[j1]][1] if j1 < len(owner) else tl['total']
        if op == 'delete':
            problems.append(f"{t:5.1f}s  missing or clipped: \"{' '.join(W_[i1:i2])}\"")
        elif op == 'insert':
            problems.append(f"{t:5.1f}s  extra sound heard: \"{' '.join(H_[j1:j2])}\" (leftover um / repeat?)")
        elif i2 - i1 <= 2 and j2 - j1 <= 2 and SequenceMatcher(None, ' '.join(W_[i1:i2]), ' '.join(H_[j1:j2])).ratio() > 0.6:
            continue   # transcription spelling noise, not a real problem
        else:
            problems.append(f"{t:5.1f}s  wanted \"{' '.join(W_[i1:i2])}\" but heard \"{' '.join(H_[j1:j2])}\"")
    learned = []
    for (w1, s1, e1), (w2, s2, e2) in zip(heard, heard[1:]):
        if s2 - e1 > 0.35:
            problems.append(f"{e1:5.1f}s  pause of {s2 - e1:.2f}s still in the edit")
            # shrink the cut until both edges sit in quiet, so no word is clipped
            t1, t2 = e1 + 0.05, s2 - 0.05
            while t1 < t2 and r_out[min(int(t1 * 100), len(r_out) - 1)] > thr_out * 0.5:
                t1 += 0.01
            while t2 > t1 and r_out[min(int(t2 * 100), len(r_out) - 1)] > thr_out * 0.5:
                t2 -= 0.01
            t1, t2 = t1 + 0.04, t2 - 0.04
            if t2 - t1 < 0.12:
                continue
            for p in tl.get('parts', []):          # map back to the raw footage
                o0, o1 = p['at'], p['at'] + p['b'] - p['a']
                x0, x1 = max(t1, o0), min(t2, o1)
                if x1 - x0 > 0.08:
                    learned.append({'clip': p['clip'], 'a': round(p['a'] + x0 - o0, 3),
                                    'b': round(p['a'] + x1 - o0, 3)})
    if '--learn' in sys.argv and learned:
        import os
        job = os.path.dirname(os.path.dirname(os.path.abspath(video)))
        f = os.path.join(job, 'work', 'auto_skips.json')
        old = json.load(open(f)) if os.path.exists(f) else []
        json.dump(old + learned, open(f, 'w'), indent=1)
        print(f"learned {len(learned)} cut(s) -> {f}; build again to apply")

    # levels
    err = subprocess.run(['ffmpeg', '-hide_banner', '-i', video, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
    if abs(I + 14) > 1.5:
        problems.append(f"loudness {I:.1f} LUFS (target -14)")
    if peak > -0.5:
        problems.append(f"true peak {peak:.1f} dBFS (clipping risk)")

    # eyes
    times = [0.5] + [s['start'] + 0.35 for s in tl['segments'][1:]] + [tl['total'] - 0.3]
    tiles = []
    for t in times:
        img = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', video, '-frames:v', '1',
                              '-vf', 'scale=270:480', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                             capture_output=True).stdout
        if len(img) == 270 * 480 * 3:
            im = Image.fromarray(np.frombuffer(img, np.uint8).reshape(480, 270, 3).copy())
            ImageDraw.Draw(im).text((6, 6), f"{t:.1f}s", fill=(255, 0, 0))
            tiles.append(im)
    sheets = []
    for k in range(0, len(tiles), 8):
        row = tiles[k:k + 8]
        sh = Image.new('RGB', (270 * len(row), 480))
        for i, im in enumerate(row):
            sh.paste(im, (i * 270, 0))
        p = video.replace('.mp4', f'.sheet-{k // 8 + 1}.jpg')
        sh.save(p, quality=85)
        sheets.append(p)

    print(f"length {tl['total']:.1f}s · {tl['cuts']} cuts · {tl['shots']} shots · {I:.1f} LUFS · peak {peak:.1f} dBFS")
    print("look at:", *sheets, sep='\n  ')
    if problems:
        print("FIX:")
        for p in problems:
            print("  " + p)
    else:
        print("PASS (still watch it once with sound on)")


if __name__ == '__main__':
    main()
