#!/usr/bin/env python3
"""Build a finished UGC video from an edit plan.

Usage:
    python3 build.py <job_dir> [--plan edit.json] [--variant NAME] [--preview]

The plan (<job_dir>/edit.json) says WHAT to show; this script does the craft:
  * keeps only the spoken words of each segment and cuts every pause, um and
    breath between them (gap > pacing.max_gap)
  * frames every shot on the face (OpenCV face detection), alternates wide /
    tight framing on each real cut, slow push-in through each shot, snap zoom
    on "punch" words, and a zoom-out on the very first frame
  * lays B-roll full screen with a slow push and an optional whip transition
  * pops in image cards and the hook box, and burns in one-word captions
  * evens out the voice and normalises to -14 LUFS (B-roll is always muted)
  * when the plan has hook variants, the main edit saves the finished frames of
    everything after the hook (the core) in .work/core/, and each --variant build
    reuses them, so only the new hook is cut, zoomed and composited

See ../references/edit-plan.md for the plan format.
"""
import argparse, hashlib, json, os, re, subprocess, sys, tempfile
from difflib import SequenceMatcher
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont
try:
    from pillow_heif import register_heif_opener   # iPhone HEIC photos
    register_heif_opener()
except ImportError:
    pass

W, H = 1080, 1920
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Job folder layout: everything in 'Raw files' (sorted by sort.py into .work/sorted),
# or the older numbered folders / raw/... names
FOLDERS = {'talking': ['1 Talking clips', '.work/sorted/talking', 'raw/talking'],
           'broll': ['2 B-roll', '.work/sorted/broll', 'raw/broll'],
           'images': ['3 Product photos', '.work/sorted/images', 'raw/images'],
           'out': ['Finished videos', 'out'],
           'music': ['4 Music', '.work/sorted/music', 'raw/music'],
           'work': ['.work', 'work']}


def jpath(job, kind, *rest):
    """Path to one of the job's folders, preferring the plain-English name."""
    for name in FOLDERS[kind]:
        p = os.path.join(job, name)
        if os.path.isdir(p):
            return os.path.join(p, *rest)
    return os.path.join(job, FOLDERS[kind][0], *rest)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"command failed: {' '.join(map(str, cmd))[:400]}\n{r.stderr[-2000:]}")
    return r


def norm(t):
    return re.sub(r"[^a-z0-9%.' ]", '', t.lower().replace('-', ' ')).split()


def deep_merge(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


# ------------------------------------------------------------------ ears

_rms = {}
def rms_track(path):
    if path not in _rms:
        raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1',
                              '-ar', '16000', '-'], capture_output=True).stdout
        a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        n = len(a) // 160
        r = np.sqrt((a[:n * 160].reshape(n, 160) ** 2).mean(1))
        _rms[path] = (r, 0.25 * np.percentile(r, 95))
    return _rms[path]


def find_words(words, say, near=None):
    """Find the run of transcript words that best matches `say`."""
    target = norm(say)
    toks = [norm(w[0]) for w in words]
    flat, owner = [], []
    for i, t in enumerate(toks):
        for x in t:
            flat.append(x); owner.append(i)
    n = len(target)
    best, best_i = 0, None
    lo, hi = 0, len(flat)
    if near is not None:
        lo = max(0, next((k for k, o in enumerate(owner) if words[o][1] >= near[0] - 1), 0))
        hi = next((k for k, o in enumerate(owner) if words[o][1] > near[1] + 1), len(flat))
    for i in range(lo, max(lo + 1, hi - n + 1)):
        for m in (n - 1, n, n + 1):
            cand = flat[i:i + m]
            r = SequenceMatcher(None, cand, target).ratio()
            if r > best:
                best, best_i = r, (i, i + m)
    if best_i is None or best < 0.75:
        sys.exit(f"could not find the words: \"{say}\" (best match {best:.2f}). Check lines.md for the exact wording.")
    a, b = owner[best_i[0]], owner[min(best_i[1], len(owner)) - 1]
    return list(range(a, b + 1)), best


def island(r, thr, t, before=0.8):
    """The run of continuous sound at or just before time t (gaps < 0.1 s)."""
    i = min(int(t * 100), len(r) - 1)
    j = i
    while j > i - before * 100 and j > 0 and r[j] < thr:   # step back onto the sound
        j -= 1
    if r[j] < thr:
        return None
    a = j
    while a > 0 and (r[max(0, a - 10):a] > thr).any():
        a -= 1
    b = j
    while b < len(r) - 1 and (r[b:b + 10] > thr).any():
        b += 1
    return a / 100, b / 100


def speech_spans(path, wl, pacing):
    """Turn a segment's words into the stretches of audio to keep.

    Word timings from the transcriber drift, so they only set where the line
    starts and ends. Inside the line, cuts happen only where the audio is
    actually silent for longer than max_gap. Soft starts and endings are
    followed until the sound really stops, so no consonant is clipped."""
    r, thr = rms_track(path)
    fixed = []
    for i, (w, s, e) in enumerate(wl):
        mid = int((s + e) / 2 * 100)
        if e - s < 0.1 and r[min(mid, len(r) - 1)] < thr * 0.5:
            # impossibly short AND sitting in silence: it was really said just before
            isl = island(r, thr, e, before=0.7)
            prev = fixed[-1][2] if fixed else s - 0.7
            if isl and isl[1] > prev:
                s, e = max(isl[0], prev, s - 0.7), min(isl[1], e)
        fixed.append((w, s, e))
    if fixed:   # sentence endings trail off softly: give the last word a tail
        w, s, e = fixed[-1]
        fixed[-1] = (w, s, e + pacing.get('end_tail', 0.1))
    # one span from the first word to the last, ending when the sound stops
    if not fixed:
        return [], fixed
    e = fixed[-1][2]
    k, lim = int(e * 100), min(len(r) - 1, int(e * 100) + 15)
    while k < lim and r[k] > thr * 0.6:
        k += 1
    s = fixed[0][1]
    j = int(s * 100)
    while j > int((s - 0.25) * 100) and j > 0 and r[j - 1] > thr * 0.3:   # soft onset just before
        j -= 1
    spans = [[j / 100, max(e, k / 100)]]
    # cut silence still hiding inside spans (words stretched over a pause)
    q = pacing['max_gap'] + 0.06
    split = []
    for s, e in spans:
        edge = r[int(s * 100):int(e * 100)] > thr * 0.3
        idx = np.nonzero(edge)[0]
        if not len(idx):
            continue
        s, e = s + idx[0] / 100, s + (idx[-1] + 1) / 100      # trim dead air at the ends
        loud = r[int(s * 100):int(e * 100)] > thr * 0.5
        cur, k = s, 0
        while k < len(loud):
            if loud[k]:
                k += 1
                continue
            k2 = k
            while k2 < len(loud) and not loud[k2]:
                k2 += 1
            if (k2 - k) / 100 >= q:
                split.append([cur, s + k / 100]); cur = s + k2 / 100
            k = k2
        split.append([cur, e])
    spans = [x for x in split if x[1] - x[0] > 0.05]
    out = []
    for i, (s, e) in enumerate(spans):
        s0 = s - pacing['pad_start']
        e0 = e + pacing['pad_end']
        if out and s0 < out[-1][1]:
            s0 = out[-1][1]
        out.append([max(0, s0), e0])
    return out, fixed


# ------------------------------------------------------------------ eyes

_face = {}
def face_centre(path, t):
    """Where to zoom: the face if one is found, else upper-middle of frame."""
    key = (path, round(t))
    if key in _face:
        return _face[key]
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', path, '-frames:v', '1',
                          '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}',
                          '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    c = (W / 2, H * 0.38)
    if len(raw) == W * H:
        g = np.frombuffer(raw, np.uint8).reshape(H, W)
        det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = det.detectMultiScale(cv2.resize(g, (W // 4, H // 4)), 1.1, 5, minSize=(30, 30))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3]) * 4
            c = (x + w / 2, y + h * 0.45)
    _face[key] = c
    return c


def frames(path, start, n, fps):
    """Yield n BGR frames from `path` starting at `start`, filling 1080x1920."""
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'quiet', '-ss', f'{start:.4f}', '-i', path, '-frames:v', str(n),
                          '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}',
                          '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    last = None
    try:
        for _ in range(n):
            buf = p.stdout.read(W * H * 3)
            if len(buf) == W * H * 3:
                last = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
            yield last if last is not None else np.zeros((H, W, 3), np.uint8)
    finally:            # also runs when the caller stops early: don't leave ffmpeg waiting
        p.stdout.close(); p.wait()


def zoom(img, z, cx, cy, dx=0.0):
    if abs(z - 1) < 1e-3 and abs(dx) < 0.5:
        return img
    M = np.float32([[z, 0, cx * (1 - z) + dx], [0, z, cy * (1 - z)]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def motion_blur(img, k):
    k = int(k)
    if k < 3:
        return img
    ker = np.zeros((1, k), np.float32); ker[0, :] = 1 / k
    return cv2.filter2D(img, -1, ker)


def ease(x):
    x = min(1, max(0, x))
    return 1 - (1 - x) ** 3


# ------------------------------------------------------------------ overlays

def font(path, size):
    p = path if os.path.isabs(path) else os.path.join(SKILL, path)
    return ImageFont.truetype(p, size)


def hook_sprite(lines, st):
    f = font(st['font_file'], st['size'])
    d0 = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    if st.get('case', 'upper') == 'upper':
        lines = [l.upper() for l in lines]
    widths = [d0.textlength(l, font=f) for l in lines]
    asc, desc = f.getmetrics()
    lh = int(asc * 1.02)
    bw, bh = int(max(widths) + st['pad_x'] * 2), lh * len(lines) + st['pad_y'] * 2
    im = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], st['radius'], fill=st['box_colour'])
    for i, (l, w) in enumerate(zip(lines, widths)):
        d.text(((bw - w) / 2, st['pad_y'] + i * lh - int(asc * 0.08)), l, font=f, fill=st['text_colour'])
    return np.array(im)


def image_sprite(path, width, border=10, radius=30, crop=None):
    im = Image.open(path).convert('RGBA')
    if crop:   # [left, top, right, bottom] as fractions of the photo
        im = im.crop((int(crop[0] * im.width), int(crop[1] * im.height),
                      int(crop[2] * im.width), int(crop[3] * im.height)))
    h = int(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    card = Image.new('RGBA', (width + border * 2, h + border * 2), (255, 255, 255, 255))
    card.alpha_composite(im, (border, border))
    m = Image.new('L', card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius, fill=255)
    card.putalpha(m)
    pad = 40
    out = Image.new('RGBA', (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new('L', out.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 10, pad + card.width, pad + card.height + 10], radius, fill=120)
    out.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(16)))
    out.alpha_composite(card, (pad, pad))
    return np.array(out)


def list_sprite(title, rows, st):
    """White rounded card: title, then ticked rows, in the hook's font and colour."""
    f = font(st['font_file'], 58)
    ft = font(st['font_file'], 44)
    d0 = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    rows = [r.upper() for r in rows]
    w = int(max([d0.textlength(title.upper(), font=f)] + [d0.textlength(r, font=ft) + 70 for r in rows]) + 80)
    h = 40 + 70 + 62 * len(rows) + 30
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], st['radius'], fill=st['box_colour'])
    d.text((40, 30), title.upper(), font=f, fill=st['text_colour'])
    for i, r in enumerate(rows):
        y = 40 + 80 + i * 62
        d.rounded_rectangle([40, y + 4, 80, y + 44], 8, fill=st['text_colour'])
        d.line([(48, y + 24), (57, y + 34), (73, y + 14)], fill=st['box_colour'], width=6)
        d.text((98, y), r, font=ft, fill='#202020')
    return np.array(im)


def pop_scale(t, dur):
    """0.55 -> 1.06 -> 1.0 pop in, quick shrink out."""
    if t < 0.12:
        return 0.55 + 0.51 * ease(t / 0.12)
    if t < 0.22:
        return 1.06 - 0.06 * ((t - 0.12) / 0.1)
    if t > dur - 0.12:
        return max(0.01, (dur - t) / 0.12)
    return 1.0


def paste(frame, sprite, cx, cy, s=1.0):
    if s < 0.02:
        return
    sp = sprite
    if abs(s - 1) > 1e-3:
        sp = cv2.resize(sprite, (max(1, int(sprite.shape[1] * s)), max(1, int(sprite.shape[0] * s))),
                        interpolation=cv2.INTER_LINEAR)
    h, w = sp.shape[:2]
    full_h, full_w = sprite.shape[:2]          # keep the whole card on screen
    cx = min(max(cx, full_w / 2 - 30), W - full_w / 2 + 30)
    cy = min(max(cy, full_h / 2 - 30), H - full_h / 2 + 30)
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xa >= xb or ya >= yb:
        return
    s_ = sp[ya - y0:yb - y0, xa - x0:xb - x0]
    a = s_[:, :, 3:4].astype(np.float32) / 255
    rgb = s_[:, :, 2::-1].astype(np.float32)   # RGBA -> BGR
    roi = frame[ya:yb, xa:xb].astype(np.float32)
    frame[ya:yb, xa:xb] = (rgb * a + roi * (1 - a)).astype(np.uint8)


def ass_time(t):
    cs = int(round(max(t, 0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_col(hexs):
    h = hexs.lstrip('#')
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def write_captions(words, st, path):
    c = st
    y = int(H * c['y'])
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
             "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
             "MarginL, MarginR, MarginV, Encoding",
             f"Style: Cap,{c['family']},{c['size']},{ass_col(c['colour'])},{ass_col(c['colour'])},"
             f"{ass_col(c['outline_colour'])},&H90000000,{-1 if c.get('bold', True) else 0},0,0,0,100,100,0,0,1,"
             f"{c['outline']},{c.get('shadow', 1)},5,60,60,0,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    pop = r"{\fscx85\fscy85\t(0,70,\fscx100\fscy100)}" if c.get('pop', True) else ''
    lead = c.get('lead', 0.066)     # show each word 2 frames early so it never lags the voice
    prev = 0
    for i, (w, s, e) in enumerate(words):
        s = max(prev, s - lead)
        nxt = words[i + 1][1] - lead if i + 1 < len(words) else e + 0.3
        end = max(min(nxt, e + 0.25), s + 0.1)
        prev = end
        txt = w.strip()
        if c.get('strip_punctuation', False):
            txt = txt.strip(',.')
        lines.append(f"Dialogue: 1,{ass_time(s)},{ass_time(end)},Cap,,0,0,0,,{{\\pos(540,{y})}}{pop}{txt}")
    open(path, 'w').write('\n'.join(lines) + '\n')


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    ap.add_argument('--plan', default=None, help='default: .work/edit.json')
    ap.add_argument('--variant')
    ap.add_argument('--preview', action='store_true', help='fast low-quality render')
    ap.add_argument('--clean', action='store_true',
                    help='no captions, hook text or cards: the same cut, ready to finish in CapCut')
    ap.add_argument('--fresh', action='store_true',
                    help="render a variant in full instead of reusing the main edit's core")
    args = ap.parse_args()
    job = os.path.abspath(args.job)
    plan_path = (os.path.join(job, args.plan) if args.plan else
                 next((p for p in (jpath(job, 'work', 'edit.json'), os.path.join(job, 'edit.json'))
                       if os.path.exists(p)), jpath(job, 'work', 'edit.json')))
    plan = json.load(open(plan_path))
    style = json.load(open(os.path.join(SKILL, 'styles', plan.get('style', 'house') + '.json')))
    style = deep_merge(style, plan.get('style_overrides', {}))
    pacing, motion = style['pacing'], style['motion']
    fps = plan.get('fps', 30)
    segs = list(plan['segments'])
    hook = plan.get('hook', {})
    name = plan.get('name', 'edit')
    # the core: the segments every variant shares (everything after the longest hook)
    variants = plan.get('variants', [])
    core_seg = max((x.get('replace_first', 1) for x in variants), default=0)
    if args.variant:
        v = next(x for x in plan['variants'] if x['name'] == args.variant)
        # anchors in the plan count segments of the main edit; shift them past the new opening
        seg_shift = len(v['segments']) - v.get('replace_first', 1)
        segs = v['segments'] + segs[v.get('replace_first', 1):]
        hook = deep_merge(hook, v.get('hook', {}))
        name = f"{name}_{args.variant}"
        core_seg += seg_shift
    core_name = plan.get('name', 'edit') + ('_clean' if args.clean else '')
    if args.clean:
        hook = {}
        plan = dict(plan, cards=[])
        name = f"{name}_clean"

    words = {}
    for f in os.listdir(jpath(job, 'work', 'words')):
        d = json.load(open(jpath(job, 'work', 'words', f)))
        words[d['key']] = d
    src = lambda k: jpath(job, 'talking', words[k]['clip'])
    lines = {L['id']: L for L in json.load(open(jpath(job, 'work', 'lines.json')))}
    fixes = {k.lower(): v for k, v in plan.get('caption_fixes', {}).items()}
    skp = jpath(job, 'work', 'auto_skips.json')
    auto_skips = json.load(open(skp)) if os.path.exists(skp) else []

    def near_of(sg):
        if not sg.get('lines'):
            return None
        ids = sg['lines'].split('-')
        return (lines[ids[0]]['start'], lines[ids[-1]]['end'])

    # 1. segments -> kept words -> tight spans
    parts, cap_words, seg_words = [], [], []
    t_out = 0.0
    for si, sg in enumerate(segs):
        wl_all = words[sg['clip']]['words']
        idx, score = find_words(wl_all, sg['say'], near_of(sg))
        wl = [wl_all[i] for i in idx]
        if score < 0.9:
            print(f"  note: segment {si} matched at {score:.2f}: \"{' '.join(w[0] for w in wl)}\"")
        spans, wl = speech_spans(src(sg['clip']), wl, pacing)
        learned = [(x['a'], x['b']) for x in auto_skips if x['clip'] == sg['clip']]
        for sa, sb in sg.get('skip', []) + learned:
            cut = []
            for x, y in spans:
                if sb <= x or sa >= y:
                    cut.append([x, y]); continue
                if sa > x: cut.append([x, sa])
                if sb < y: cut.append([sb, y])
            spans = [c for c in cut if c[1] - c[0] > 0.05]
        seg_start = t_out
        entries = []
        for k, (a, b) in enumerate(spans):
            a, b = round(a * fps) / fps, round(b * fps) / fps
            if b - a < 1 / fps:
                continue
            new_shot = k == 0 or (a - parts[-1]['b'] > motion['reframe_gap'] if parts else True)
            parts.append({'clip': sg['clip'], 'a': a, 'b': b, 'at': t_out, 'seg': si, 'new_shot': new_shot})
            t_out += b - a
        mine = [p for p in parts if p['seg'] == si]
        for w, s, e in wl:
            # the cut this word overlaps most (or the nearest one)
            p = max(mine, key=lambda p: (min(e, p['b']) - max(s, p['a']), -abs(s - p['a'])))
            ts = p['at'] + min(max(0, s - p['a']), p['b'] - p['a'] - 0.05)
            te = max(ts + 0.05, p['at'] + min(e, p['b']) - p['a'])
            core = re.sub(r"[^\w']", '', w).lower()
            if core in fixes:
                w = re.sub(r"[\w']+", fixes[core], w, count=1)
            entries.append([w, ts, te])
        seg_words.append(entries)
        for w in entries:
            if cap_words and w[0][:1] in ".%-'" and w[1] - cap_words[-1][2] < 0.6:
                cap_words[-1][0] += w[0]; cap_words[-1][2] = w[2]
            else:
                cap_words.append(list(w))
        sg['_start'], sg['_end'] = seg_start, t_out
    total = t_out
    nframes = int(round(total * fps))

    def at_time(spec, plan_index=True):
        si = spec.get('seg', 0)
        if plan_index and args.variant and si >= next(x for x in plan['variants'] if x['name'] == args.variant).get('replace_first', 1):
            si += seg_shift
        if 'word' in spec:
            tgt = norm(spec['word'])
            for w, s, e in seg_words[si]:
                if norm(w) == tgt or (tgt and norm(w) and norm(w)[0].startswith(tgt[0])):
                    return s + spec.get('offset', 0)
            sys.exit(f"anchor word '{spec['word']}' not found in segment {si}")
        return segs[si]['_start'] + spec.get('offset', 0)

    # zoom plan per output frame
    punches = []
    for si, sg in enumerate(segs):
        for pw in sg.get('punch', []):
            punches.append(at_time({'seg': si, 'word': pw}, plan_index=False))
    # wide / tight alternate on every real cut. With hook variants the count starts from the
    # core's first shot (always tight), so the core is framed the same whichever hook opens
    # the video, and a one-shot hook still opens wide
    starts = [p for p in parts if p['new_shot']]
    anchor = next((i for i, p in enumerate(starts) if p['seg'] >= core_seg), 0)
    shot_of_frame = np.zeros(nframes, int)
    base = np.ones(nframes)
    shot_start, shot_id = 0, -1
    shots = []
    for p in parts:
        f0, f1 = int(round(p['at'] * fps)), int(round((p['at'] + p['b'] - p['a']) * fps))
        if p['new_shot']:
            shot_id += 1
            tight = (shot_id - anchor) % 2 == (0 if core_seg else 1)
            shots.append([f0, f1, tight])
        else:
            shots[-1][1] = f1
        base[f0:f1] = motion['zoom_tight'] if tight else 1.0
    zf = base.copy()
    for f0, f1, _ in shots:
        n = max(1, f1 - f0)
        zf[f0:f1] *= 1 + motion['push'] * np.arange(n)[:f1 - f0] / n
    for tp in punches:
        for fi in range(int(tp * fps), min(nframes, int((tp + 0.9) * fps))):
            x = fi / fps - tp
            amt = ease(x / 0.08) if x < 0.08 else (1 - ease((x - 0.6) / 0.3) if x > 0.6 else 1)
            zf[fi] *= 1 + motion['punch'] * amt
    for fi in range(min(nframes, int(motion['open_dur'] * fps))):
        zf[fi] *= 1 + (motion['open_zoom'] - 1) * (1 - ease(fi / (motion['open_dur'] * fps)))

    # overlays start and end on whole frames, so each one lands on the same frame in every variant
    on_frame = lambda t: round(t * fps) / fps

    # B-roll timeline
    broll = []
    for b in plan.get('broll', []):
        t0 = on_frame(at_time(b['at']))
        broll.append({**b, 't0': t0, 't1': on_frame(min(total, t0 + b['dur'])),
                      'path': jpath(job, 'broll', b['clip'])})
    cards = []
    for c in plan.get('cards', []):
        t0 = on_frame(at_time(c['at']))
        if 'image' in c:
            sp = image_sprite(os.path.join(job, c['image']), int(W * c.get('w', 0.6)), crop=c.get('crop'))
        else:
            sp = list_sprite(c['title'], c['rows'], style['hook'])
        cards.append({**c, 't0': t0, 't1': on_frame(t0 + c['dur']), 'sprite': sp})
    hook_sp, hook_end = None, 0
    if hook.get('text'):
        hook_sp = hook_sprite(hook['text'], style['hook'])
        hook_end = hook.get('dur') or segs[0]['_end']
        if hook.get('until_seg') is not None:
            hook_end = segs[hook['until_seg']]['_end']
        hook_end = on_frame(hook_end)

    tmp = tempfile.mkdtemp()
    # 2. audio: exact-length parts, joined sample-accurately
    ins, fc = [], []
    for i, p in enumerate(parts):
        n = int(round((p['b'] - p['a']) * fps))
        d = n / fps
        ins += ['-ss', f"{p['a']:.4f}", '-t', f"{d + 0.1:.4f}", '-i', src(p['clip'])]
        fc.append(f"[{i}:a]aresample=48000,atrim=0:{d:.5f},apad=whole_dur={d:.5f},"
                  f"afade=t=in:d=0.008,afade=t=out:st={max(0, d - 0.01):.5f}:d=0.01[a{i}]")
    fc.append(''.join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1,"
              "highpass=f=75,acompressor=threshold=0.12:ratio=2.5:attack=6:release=120:makeup=1.4[out]")
    voice = os.path.join(tmp, 'voice.wav')
    run(['ffmpeg', '-y', '-loglevel', 'error'] + ins + ['-filter_complex', ';'.join(fc), '-map', '[out]',
         '-ac', '2', '-ar', '48000', voice])
    meas = subprocess.run(['ffmpeg', '-hide_banner', '-i', voice, '-af',
                           f"loudnorm=I={style['audio']['lufs']}:TP=-1.5:LRA=11:print_format=json", '-f', 'null', '-'],
                          capture_output=True, text=True).stderr
    m = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    audio = os.path.join(tmp, 'audio.wav')
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', voice, '-af',
         f"loudnorm=I={style['audio']['lufs']}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
         '-ar', '48000', audio])

    # optional music bed: quiet, faded, and dipping under the voice whenever it speaks
    mus = plan.get('music')
    if mus and mus.get('file'):
        mixed = os.path.join(tmp, 'mixed.wav')
        vol = mus.get('volume', 0.2)
        run(['ffmpeg', '-y', '-loglevel', 'error', '-i', audio, '-stream_loop', '-1', '-i', jpath(job, 'music', mus['file']),
             '-filter_complex',
             f"[0:a]asplit[v1][v2];[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},"
             f"atrim=0:{total:.3f},afade=t=in:d=0.6,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[m];"
             f"[m][v2]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[md];"
             f"[v1][md]amix=inputs=2:normalize=0,alimiter=limit=0.89[o]",
             '-map', '[o]', '-t', f"{total:.3f}", '-ar', '48000', mixed])
        audio = mixed

    # 3. video, frame by frame
    capf = os.path.join(tmp, 'cap.ass')
    write_captions([] if args.clean else cap_words, style['caption'], capf)
    out_dir = jpath(job, 'work') if args.preview else jpath(job, 'out')   # drafts stay hidden
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{name}{'_preview' if args.preview else ''}.mp4")
    fontsdir = os.path.join(SKILL, 'fonts')
    enc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                            '-s', f'{W}x{H}', '-r', str(fps), '-i', '-', '-i', audio,
                            '-vf', f"ass={capf}:fontsdir={fontsdir}", '-map', '0:v', '-map', '1:a',
                            '-c:v', 'libx264', '-preset', 'veryfast' if args.preview else 'slow',
                            '-crf', '26' if args.preview else '17', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                            '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', out],
                           stdin=subprocess.PIPE)
    # The core cache. The main edit saves the core's finished frames (captions are added
    # later by the encoder, so they're not in them) plus a fingerprint of how each frame
    # was made. A variant reads back the run of frames at the end whose fingerprints match.
    stamp = {}
    look = json.dumps([W, H, fps, motion, style['hook']], sort_keys=True)
    def fingerprint(fi, p, k, cx, cy):
        t = fi / fps
        if p['clip'] not in stamp:
            st = os.stat(src(p['clip']))
            stamp[p['clip']] = f"{st.st_size}:{st.st_mtime_ns}"
        bits = [look, p['clip'], stamp[p['clip']], f"{p['a']:.4f}", k, f"{zf[fi]:.5f}", f"{cx:.0f},{cy:.0f}"]
        for b in broll:
            if b['t0'] <= t < b['t1']:
                bits += ['b', b['clip'], b['in'], round((t - b['t0']) * fps), round((b['t1'] - b['t0']) * fps),
                         b.get('transition', 'whip')]
        for c in cards:
            if c['t0'] <= t < c['t1']:
                bits += ['c', {k_: v for k_, v in c.items() if k_ not in ('at', 't0', 't1', 'sprite')},
                         round((t - c['t0']) * fps)]
        if hook_sp is not None and t < hook_end:
            bits += ['h', fi, hook['text'], f"{hook_end:.3f}"]
        return hashlib.md5(json.dumps(bits, default=str).encode()).hexdigest()[:16]

    keys = []
    for p in parts:
        cx, cy = face_centre(src(p['clip']), p['a'] + 0.3)
        for k in range(int(round((p['b'] - p['a']) * fps))):
            keys.append(fingerprint(len(keys), p, k, cx, cy))
    core_dir = jpath(job, 'work', 'core')
    core_mp4 = os.path.join(core_dir, core_name + '.mp4')
    core_json = os.path.join(core_dir, core_name + '.json')
    core_f0 = int(round(segs[core_seg]['_start'] * fps)) if 0 < core_seg < len(segs) else None
    reuse = None            # (first frame to read from the cache, where it sits in the cache)
    if args.variant and core_f0 is not None and not args.fresh and os.path.exists(core_json) \
            and os.path.exists(core_mp4):
        saved = json.load(open(core_json))
        m = 0
        while m < min(len(saved), len(keys)) and saved[-1 - m] == keys[-1 - m]:
            m += 1
        if m >= fps:
            reuse = (len(keys) - m, len(saved) - m)
            print(f"  reusing {m / fps:.1f}s of the main edit's core; rendering {(len(keys) - m) / fps:.1f}s")
        else:
            print("  note: the core changed since the main edit was built, so this variant is rendered in full")
    cache = None
    if not args.variant and core_f0 is not None:
        os.makedirs(core_dir, exist_ok=True)
        cache = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
                                  '-s', f'{W}x{H}', '-r', str(fps), '-i', '-', '-c:v', 'libx264',
                                  '-preset', 'ultrafast', '-crf', '12', '-pix_fmt', 'yuv444p',
                                  core_mp4 + '.part.mp4'], stdin=subprocess.PIPE)

    brf = {}
    fi = 0
    whip = motion.get('whip_dur', 0.2)
    for p in parts:
        if reuse and fi >= reuse[0]:
            break
        n = int(round((p['b'] - p['a']) * fps))
        cx, cy = face_centre(src(p['clip']), p['a'] + 0.3)
        for frame in frames(src(p['clip']), p['a'], n, fps):
            if reuse and fi >= reuse[0]:
                break
            t = fi / fps
            img = zoom(frame, zf[fi], cx, cy)
            for b in broll:
                if b['t0'] <= t < b['t1']:
                    key = id(b)
                    if key not in brf:
                        nb = int(round((b['t1'] - b['t0']) * fps)) + 2
                        brf[key] = frames(b['path'], b['in'], nb, fps)
                    bf = next(brf[key])
                    bt = t - b['t0']
                    bz = 1 + motion['broll_push'] * bt / max(0.1, b['t1'] - b['t0'])
                    bimg = zoom(bf, bz, W / 2, H / 2)
                    if b.get('transition', 'whip') == 'whip' and bt < whip:
                        x = ease(bt / whip)
                        off = (1 - x) * W
                        speed = W / (whip * fps) * (1 - x) * 3
                        slid = np.where(np.arange(W)[None, :, None] >= off,
                                        zoom(bimg, 1, 0, 0, dx=off), zoom(img, 1, 0, 0, dx=off - W))
                        img = motion_blur(slid, speed)
                    else:
                        img = bimg
                elif t >= b['t1'] and id(b) in brf:
                    brf.pop(id(b)).close()      # stop its decoder now so it doesn't sit in memory
            for c in cards:
                if c['t0'] <= t < c['t1']:
                    paste(img, c['sprite'], W * c.get('x', 0.5), H * c.get('y', 0.2), pop_scale(t - c['t0'], c['dur']))
            if hook_sp is not None and t < hook_end:
                paste(img, hook_sp, W / 2, style['hook']['y'] + hook_sp.shape[0] / 2,
                      pop_scale(t - 0.03, hook_end - 0.03) if t >= 0.03 else 0)
            buf = np.ascontiguousarray(img).tobytes()
            enc.stdin.write(buf)
            if cache and fi >= core_f0:
                cache.stdin.write(buf)
            fi += 1
    for g in brf.values():
        g.close()
    if reuse:
        for frame in frames(core_mp4, reuse[1] / fps, len(keys) - reuse[0], fps):
            enc.stdin.write(frame.tobytes())
    enc.stdin.close(); enc.wait()
    if cache:
        cache.stdin.close(); cache.wait()
        if cache.returncode == 0:
            if os.path.exists(core_json):
                os.remove(core_json)
            os.replace(core_mp4 + '.part.mp4', core_mp4)
            json.dump(keys[core_f0:], open(core_json, 'w'))
    json.dump({'segments': [{'say': s['say'], 'start': s['_start'], 'end': s['_end']} for s in segs],
               'words': cap_words, 'total': total, 'cuts': len(parts), 'shots': len(shots),
               'parts': [{k: p[k] for k in ('clip', 'a', 'b', 'at', 'seg')} for p in parts],
               # where the overlays sit, so qa.py can check faces, mouths and B-roll reuse
               'broll': [{'clip': b['clip'], 'in': b['in'], 't0': b['t0'], 't1': b['t1']} for b in broll],
               'cards': [{'t0': c['t0'], 't1': c['t1'], 'y0': H * c.get('y', 0.2) - c['sprite'].shape[0] / 2,
                          'y1': H * c.get('y', 0.2) + c['sprite'].shape[0] / 2} for c in cards],
               'hook': ({'t1': hook_end, 'y0': style['hook']['y'], 'y1': style['hook']['y'] + hook_sp.shape[0]}
                        if hook_sp is not None else None),
               'caption': None if args.clean else {'y': H * style['caption']['y'], 'size': style['caption']['size']}},
              open(jpath(job, 'work', os.path.basename(out).replace('.mp4', '.timeline.json')), 'w'))
    print(f"done: {out}  ({total:.1f}s, {len(parts)} cuts, {len(shots)} shots)")


if __name__ == '__main__':
    main()
