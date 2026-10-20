#!/usr/bin/env python3
"""Ears: transcribe every talking clip with a timestamp on every word.

Usage:
    python3 transcribe.py <job_dir> [--model small.en]

Reads every talking clip (sorted from Raw files by sort.py), writes (in the hidden .work folder):
    .work/words/<clip>.json   word list [[word, start, end], ...]
    .work/lines.md            numbered lines to choose from, with
                                       repeated takes grouped and stumbles flagged

Line ids look like A07 = clip A, line 7. The edit plan (edit.json) picks lines by id.
"""
import argparse, json, os, re, subprocess, sys
from difflib import SequenceMatcher
import numpy as np

# Job folder layout: everything in 'Raw files' (sorted by sort.py into .work/sorted),
# or the older numbered folders / raw/... names
FOLDERS = {'talking': ['1 Talking clips', '.work/sorted/talking', 'raw/talking'],
           'broll': ['2 B-roll', '.work/sorted/broll', 'raw/broll'],
           'images': ['3 Product photos', '.work/sorted/images', 'raw/images'],
           'out': ['Finished videos', 'out'],
           'work': ['.work', 'work']}


def jpath(job, kind, *rest):
    """Path to one of the job's folders, preferring the plain-English name."""
    for name in FOLDERS[kind]:
        p = os.path.join(job, name)
        if os.path.isdir(p):
            return os.path.join(p, *rest)
    return os.path.join(job, FOLDERS[kind][0], *rest)


VIDEO = ('.mov', '.mp4', '.m4v', '.mkv', '.avi', '.webm')


def load_audio(path, sr=16000):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1',
                          '-ar', str(sr), '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def rms_10ms(a):
    n = len(a) // 160
    return np.sqrt((a[:n * 160].reshape(n, 160) ** 2).mean(1))


def tighten_word(w, s, e, r, thr):
    """Whisper sometimes stretches a word over the silence or 'um' before it.
    Pull a long word's start in to where the sound actually begins."""
    if e - s <= 0.55:
        return s, e
    i, j = int(s * 100), min(int(e * 100), len(r) - 1)
    k = j
    while k > i and (r[k - 8:k] > thr).any():   # walk back through continuous sound
        k -= 1
    return max(s, k / 100 - 0.04), e


def norm(text):
    return re.sub(r"[^a-z0-9' ]", '', text.lower()).split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    ap.add_argument('--model', default='small.en')
    args = ap.parse_args()
    from faster_whisper import WhisperModel
    talk = jpath(args.job, 'talking')
    clips = sorted(f for f in os.listdir(talk) if f.lower().endswith(VIDEO))
    if not clips:
        sys.exit(f"no videos in {talk}")
    os.makedirs(jpath(args.job, 'work', 'words'), exist_ok=True)
    model = WhisperModel(args.model, device='cpu', compute_type='int8')
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    clipmap, all_lines = {}, []
    for ci, clip in enumerate(clips):
        key = letters[ci]
        path = os.path.join(talk, clip)
        clipmap[key] = clip
        a = load_audio(path)
        r = rms_10ms(a)
        thr = 0.25 * np.percentile(r, 95)
        segs, _ = model.transcribe(a, word_timestamps=True, beam_size=5,
                                   initial_prompt="Okay, so, um, I mean, like, you know.")
        words = []
        for sg in segs:
            for w in sg.words:
                t = w.word.strip()
                if not t:
                    continue
                s, e = tighten_word(t, w.start, w.end, r, thr)
                words.append([t, round(s, 2), round(e, 2)])
        json.dump({'clip': clip, 'key': key, 'words': words},
                  open(jpath(args.job, 'work', 'words', f'{key}.json'), 'w'))
        # split into lines at sentence ends or pauses
        line, n = [], 0
        for i, w in enumerate(words):
            line.append(w)
            gap = words[i + 1][1] - w[2] if i + 1 < len(words) else 9
            if w[0][-1:] in '.?!' or gap > 0.6:
                n += 1
                all_lines.append({'id': f'{key}{n:02d}', 'clip': key, 'start': line[0][1], 'end': line[-1][2],
                                  'text': ' '.join(x[0] for x in line), 'words': len(line)})
                line = []
        print(f"{key} = {clip}: {len(words)} words, {n} lines", flush=True)

    # group repeated takes of the same line, flag stumbles
    group = {}
    for i, L in enumerate(all_lines):
        if L['id'] in group:
            continue
        group[L['id']] = L['id']
        for M in all_lines[i + 1:]:
            if M['id'] in group:
                continue
            ratio = SequenceMatcher(None, norm(L['text']), norm(M['text'])).ratio()
            if ratio >= 0.55 or (len(norm(L['text'])) >= 3 and ' '.join(norm(L['text'])[:3]) ==
                                 ' '.join(norm(M['text'])[:3])):
                group[M['id']] = L['id']
    takes = {}
    for L in all_lines:
        takes.setdefault(group[L['id']], []).append(L['id'])
    out = ["# Lines", "",
           "Pick lines by id for edit.json. Lines with the same TAKE label are repeats of the same idea:",
           "use the cleanest one (usually the last complete take). ⚠ = likely stumble or cut-off.", "",
           "Clips: " + ', '.join(f"{k} = {v}" for k, v in clipmap.items()), ""]
    for L in all_lines:
        g = group[L['id']]
        n_takes = len(takes[g])
        flag = ''
        if not L['text'].rstrip().endswith(('.', '?', '!')) and n_takes > 1 and takes[g][-1] != L['id']:
            flag = ' ⚠'
        if L['text'].rstrip().endswith(('-', '...')) or L['words'] <= 2 and n_takes > 1:
            flag = ' ⚠'
        tag = f"  [TAKE {g} {takes[g].index(L['id']) + 1}/{n_takes}]" if n_takes > 1 else ''
        out.append(f"{L['id']}  {L['start']:7.2f}-{L['end']:7.2f}  {L['text']}{tag}{flag}")
    open(jpath(args.job, 'work', 'lines.md'), 'w').write('\n'.join(out) + '\n')
    json.dump(all_lines, open(jpath(args.job, 'work', 'lines.json'), 'w'))
    print(f"wrote {jpath(args.job, 'work', 'lines.md')}")


if __name__ == '__main__':
    main()
