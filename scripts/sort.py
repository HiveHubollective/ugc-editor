#!/usr/bin/env python3
"""Sort the creator's Raw files folder so they never have to.

Usage:
    python3 sort.py <job_dir> [--set clip.mov=broll ...]

The creator drops everything into <job>/Raw files/ (subfolders are fine):
talking clips, B-roll, photos, music, the brief. This listens to and looks at
every file and decides what it is:
    talking  a video with someone talking (speech, and usually a face)
    broll    a video with little or no speech
    images   photos and screenshots (.jpg .png .heic .webp)
    music    audio files (.mp3 .wav .m4a .aac)
    brief    documents (.pdf .docx .txt .md .pages)
Nothing is moved. It writes links in .work/sorted/<kind>/ that the other
scripts read, and a summary in .work/sorted.md. If it gets one wrong, run it
again with --set <file>=<kind>; that choice is remembered.
"""
import argparse, json, os, shutil, subprocess, sys
import numpy as np

VIDEO = ('.mov', '.mp4', '.m4v', '.mkv', '.avi', '.webm')
IMAGE = ('.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp')
AUDIO = ('.mp3', '.wav', '.m4a', '.aac', '.aiff', '.flac', '.ogg')
DOC = ('.pdf', '.docx', '.doc', '.txt', '.md', '.pages', '.rtf')
KINDS = ('talking', 'broll', 'images', 'music', 'brief')


def has_face(path, dur):
    import cv2
    det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    for t in (dur * 0.3, dur * 0.6):
        raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', path, '-frames:v', '1',
                              '-vf', 'scale=360:-2', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                             capture_output=True).stdout
        if not raw:
            continue
        g = np.frombuffer(raw, np.uint8).reshape(-1, 360)
        if len(det.detectMultiScale(g, 1.1, 5, minSize=(40, 40))):
            return True
    return False


def duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                       capture_output=True, text=True).stdout.strip()
    try:
        return float(r)
    except ValueError:
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    ap.add_argument('--set', nargs='*', default=[], help='override: file=talking|broll|images|music|brief')
    args = ap.parse_args()
    raw_dir = os.path.join(args.job, 'Raw files')
    if not os.path.isdir(raw_dir):
        sys.exit(f"no 'Raw files' folder in {args.job}")
    work = os.path.join(args.job, '.work')
    os.makedirs(work, exist_ok=True)
    ov_path = os.path.join(work, 'sort_overrides.json')
    overrides = json.load(open(ov_path)) if os.path.exists(ov_path) else {}
    for s in args.set:
        f, _, k = s.partition('=')
        if k not in KINDS:
            sys.exit(f"--set {s}: kind must be one of {', '.join(KINDS)}")
        overrides[os.path.basename(f)] = k
    json.dump(overrides, open(ov_path, 'w'), indent=1)

    files = []
    for root, dirs, names in os.walk(raw_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files += [os.path.join(root, n) for n in sorted(names) if not n.startswith('.')]
    cache_path = os.path.join(work, 'sort_cache.json')
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    model = None
    result = []
    for p in files:
        name = os.path.basename(p)
        ext = os.path.splitext(name)[1].lower()
        note = ''
        if ext in VIDEO:
            key = f"{p}|{os.path.getsize(p)}"
            if key not in cache:
                dur = duration(p)
                if model is None:
                    from faster_whisper import WhisperModel
                    model = WhisperModel('small.en', device='cpu', compute_type='int8')
                a = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', p, '-t', '40', '-f', 's16le', '-ac', '1',
                                    '-ar', '16000', '-'], capture_output=True).stdout
                a = np.frombuffer(a, np.int16).astype(np.float32) / 32768
                n_words = 0
                if len(a):
                    segs, _ = model.transcribe(a, vad_filter=True, beam_size=1)
                    n_words = sum(len(s.text.split()) for s in segs)
                cache[key] = {'dur': dur, 'words': n_words, 'face': has_face(p, dur)}
                json.dump(cache, open(cache_path, 'w'))
            c = cache[key]
            rate = c['words'] / max(1.0, min(c['dur'], 40))
            kind = 'talking' if c['words'] >= 5 and rate >= 0.7 else 'broll'
            note = f"{c['dur']:.0f}s, {c['words']} words heard, {'face' if c['face'] else 'no face'}"
            if kind == 'talking' and not c['face']:
                note += ' (talking but no face found: voiceover? check it)'
            if kind == 'broll' and c['words'] >= 5:
                note += ' (some talking: check it is B-roll)'
        elif ext in IMAGE:
            kind = 'images'
        elif ext in AUDIO:
            kind = 'music'
        elif ext in DOC:
            kind = 'brief'
        else:
            result.append((name, None, p, 'not used (unknown file type)'))
            continue
        if name in overrides:
            kind, note = overrides[name], note + ' (set by hand)'
        result.append((name, kind, p, note))

    sorted_dir = os.path.join(work, 'sorted')
    shutil.rmtree(sorted_dir, ignore_errors=True)
    for k in KINDS:
        os.makedirs(os.path.join(sorted_dir, k))
    for name, kind, p, _ in result:
        if kind:
            link = os.path.join(sorted_dir, kind, name)
            if os.path.lexists(link):     # same file name in two subfolders
                link = os.path.join(sorted_dir, kind, os.path.basename(os.path.dirname(p)) + ' - ' + name)
            os.symlink(os.path.abspath(p), link)

    out = ["# Sorted raw files", "",
           "Check this. If something is in the wrong pile, run sort.py again with --set <file>=<kind>.", ""]
    for k in KINDS + (None,):
        rows = [r for r in result if r[1] == k]
        if rows:
            out.append(f"## {k or 'not used'}")
            out += [f"- {os.path.relpath(p, args.job)}" + (f"  ({note})" if note else '') for _, _, p, note in rows]
            out.append('')
    open(os.path.join(work, 'sorted.md'), 'w').write('\n'.join(out))
    print('\n'.join(out))


if __name__ == '__main__':
    main()
