#!/usr/bin/env python3
"""Check a finished video before a human sees it: ears, eyes and levels.

Usage:
    python3 qa.py <video.mp4> [--learn]

--learn  turns every leftover pause / um it hears into a cut in the raw
         footage (work/auto_skips.json); build again to apply it.

Needs the timeline build.py writes in the job's .work folder.
  ears   re-transcribes the finished video and compares it with the words the
         plan asked for: clipped or missing words, leftover ums / repeats, and
         any pause still longer than 0.35 s
  eyes   saves contact sheets (<video>.sheet-N.jpg) with a frame at every
         segment start, so Claude can look at framing, captions and overlays
  levels integrated loudness (target -14 LUFS) and true peak
  face   captions never over the mouth, hook text and cards never over the
         face (checked closely in the first 3 s, when people decide to stay)
  cuts   frame strips either side of every cut (<video>.cuts-N.jpg) plus an
         automatic check for one-frame flashes
  b-roll the creator is never off screen for more than 3.5 s, and no B-roll
         moment is used twice
Prints PASS or a list of things to fix.
"""
import glob, json, os, re, subprocess, sys
from difflib import SequenceMatcher
import numpy as np
from PIL import Image, ImageDraw


# Job folder layout (plain-English names; the old raw/... names still work)
FOLDERS = {'talking': ['1 Talking clips', 'raw/talking'], 'broll': ['2 B-roll', 'raw/broll'],
           'images': ['3 Product photos', 'raw/images'], 'out': ['Finished videos', 'out'],
           'work': ['.work', 'work']}


def jpath(job, kind, *rest):
    """Path to one of the job's folders, preferring the plain-English name."""
    for name in FOLDERS[kind]:
        p = os.path.join(job, name)
        if os.path.isdir(p):
            return os.path.join(p, *rest)
    return os.path.join(job, FOLDERS[kind][0], *rest)


def norm(t):
    return [x for x in re.sub(r"[^a-z0-9' ]", ' ', t.lower().replace('%', ' percent ')).split() if x]


def spans(ts, gap):
    """Group sorted times into (start, end) runs."""
    out = []
    for t in ts:
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def broll_checks(tl):
    problems = []
    runs = []
    for b in sorted(tl.get('broll', []), key=lambda b: b['t0']):
        if runs and b['t0'] - runs[-1][1] < 0.15:
            runs[-1][1] = max(runs[-1][1], b['t1'])
        else:
            runs.append([b['t0'], b['t1']])
    for a, b in runs:
        if b - a > 3.5:
            problems.append(f"{a:5.1f}s  creator off screen for {b - a:.1f}s (keep B-roll runs under 3.5s)")
    bs = tl.get('broll', [])
    for i, x in enumerate(bs):
        for y in bs[i + 1:]:
            if x['clip'] == y['clip']:
                o = min(x['in'] + x['t1'] - x['t0'], y['in'] + y['t1'] - y['t0']) - max(x['in'], y['in'])
                if o > 0.3:
                    problems.append(f"{y['t0']:5.1f}s  same B-roll moment used twice ({x['clip']} at "
                                    f"{x['t0']:.1f}s and {y['t0']:.1f}s): pick a different moment")
    return problems


def frame_checks(video, tl, job, base):
    """Captions off the mouth, text off the face, no one-frame flashes, strips at every cut."""
    import cv2
    W, H, fps = 1080, 1920, 30
    w, h = W // 2, H // 2                       # decode at half size: plenty for faces
    k = 2
    det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cuts = sorted({p['at'] for p in tl.get('parts', [])[1:]} |
                  {t for b in tl.get('broll', []) for t in (b['t0'], b['t1']) if 0.1 < t < tl['total'] - 0.1})
    cut_f = {int(round(t * fps)): t for t in cuts}
    want_strip = {f + d: f for f in cut_f for d in range(-3, 3)}
    strips, means = {}, []
    in_broll = lambda t: any(b['t0'] <= t < b['t1'] for b in tl.get('broll', []))
    words = tl.get('words', [])
    cap = tl.get('caption')
    mouth, face_cov = [], []
    proc = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', video, '-vf', f'scale={w}:{h},fps={fps}',
                             '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    fi = 0
    while True:
        buf = proc.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        img = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        means.append(float(img.mean()))
        if fi in want_strip:
            strips[fi] = Image.fromarray(img).resize((135, 240))
        t = fi / fps
        step = 4 if t < 3 else 15                 # every 0.13 s in the first 3 s, then every 0.5 s
        if fi % step == 0 and not in_broll(t):
            g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            faces = det.detectMultiScale(g, 1.1, 6, minSize=(w // 8, w // 8))
            if len(faces):
                x, y, fw, fh = [v * k for v in max(faces, key=lambda f: f[2] * f[3])]
                bands = []
                if cap and any(s - 0.07 <= t < e + 0.2 for _, s, e in words):
                    bands.append(('caption', cap['y'] - cap['size'] * 0.55, cap['y'] + cap['size'] * 0.55,
                                  y + fh * 0.62, y + fh * 1.15))       # mouth and chin
                hk = tl.get('hook')
                if hk and t < hk['t1']:
                    bands.append(('hook text', hk['y0'], hk['y1'], y + fh * 0.1, y + fh))
                for c in tl.get('cards', []):
                    if c['t0'] <= t < c['t1']:
                        bands.append(('card', c['y0'], c['y1'], y + fh * 0.1, y + fh))
                for name, b0, b1, z0, z1 in bands:
                    if min(b1, z1) - max(b0, z0) > 12:
                        (mouth if name == 'caption' else face_cov).append((t, name))
        fi += 1
    proc.wait()
    problems = []
    for name, hits in (('caption over the mouth', mouth), ('covering the face', face_cov)):
        for kind in sorted({n for _, n in hits}):
            for a, b in spans(sorted(t for t, n in hits if n == kind), 0.6):
                what = name if kind == 'caption' else f"{kind} {name}"
                problems.append(f"{a:5.1f}s  {what}" + (f" until {b:.1f}s" if b - a > 0.05 else '') +
                                (" (first 3 s: fix this first)" if a < 3 else ''))
    for i in range(1, len(means) - 1):
        if abs(means[i] - means[i - 1]) > 35 and abs(means[i] - means[i + 1]) > 35 and \
                abs(means[i - 1] - means[i + 1]) < 12:
            problems.append(f"{i / fps:5.1f}s  one-frame flash (a single frame that doesn't match its neighbours)")
    rows = []
    for f, t in sorted(cut_f.items()):
        tiles = [strips.get(f + d) for d in range(-3, 3)]
        if all(tiles):
            row = Image.new('RGB', (135 * 6, 240))
            for i, im in enumerate(tiles):
                row.paste(im, (i * 135, 0))
            ImageDraw.Draw(row).text((4, 4), f"cut {t:.2f}s", fill=(255, 0, 0))
            rows.append(row)
    for old in glob.glob(jpath(job, 'work', f'{base}.cuts-*.jpg')):
        os.remove(old)
    for n in range(0, len(rows), 8):
        grp = rows[n:n + 8]
        sh = Image.new('RGB', (135 * 6, 240 * len(grp)))
        for i, r in enumerate(grp):
            sh.paste(r, (0, i * 240))
        sh.save(jpath(job, 'work', f'{base}.cuts-{n // 8 + 1}.jpg'), quality=85)
    return problems


def main():
    video = sys.argv[1]
    job = os.path.dirname(os.path.dirname(os.path.abspath(video)))
    base = os.path.basename(video).replace('.mp4', '')
    tl = json.load(open(jpath(job, 'work', base + '.timeline.json')))
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
        f = jpath(job, 'work', 'auto_skips.json')
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

    # face, cuts and flashes: one pass over the finished frames
    problems += frame_checks(video, tl, job, base)
    problems += broll_checks(tl)

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
        p = jpath(job, 'work', f'{base}.sheet-{k // 8 + 1}.jpg')
        sh.save(p, quality=85)
        sheets.append(p)

    print(f"length {tl['total']:.1f}s · {tl['cuts']} cuts · {tl['shots']} shots · {I:.1f} LUFS · peak {peak:.1f} dBFS")
    print("look at:", *sheets, *sorted(glob.glob(jpath(job, 'work', f'{base}.cuts-*.jpg'))), sep='\n  ')
    if problems:
        print("FIX:")
        for p in problems:
            print("  " + p)
    else:
        print("PASS (still watch it once with sound on)")


if __name__ == '__main__':
    main()
