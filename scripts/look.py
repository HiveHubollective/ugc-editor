#!/usr/bin/env python3
"""Eyes: contact sheets of every B-roll clip and product image in a job.

Usage:
    python3 look.py <job_dir>

Writes <job>/.work/look/<name>.jpg: one sheet per B-roll clip (a frame
every 0.5 s, each stamped with its time) and one sheet of all product images.
Open each sheet and note what happens when: where the pour/sip/reaction is,
where the creator looks at the camera or fumbles (avoid those), what is
blurry or shaky. B-roll "in" times in edit.json come from these stamps.
"""
import os, subprocess, sys
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


VIDEO = ('.mov', '.mp4', '.m4v', '.mkv', '.avi', '.webm')
IMAGE = ('.jpg', '.jpeg', '.png', '.webp', '.heic')


def duration(p):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def main():
    job = sys.argv[1]
    out = jpath(job, 'work', 'look')
    os.makedirs(out, exist_ok=True)
    tw, th = 180, 320
    bdir = jpath(job, 'broll')
    for f in sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []:
        if not f.lower().endswith(VIDEO):
            continue
        p = os.path.join(bdir, f)
        d = duration(p)
        n = max(1, int(d / 0.5))
        raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', p, '-vf',
                              f'fps=2,scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}',
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        frames = [np.frombuffer(raw[i * tw * th * 3:(i + 1) * tw * th * 3], np.uint8).reshape(th, tw, 3)
                  for i in range(len(raw) // (tw * th * 3))]
        cols = 10
        rows = (len(frames) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * tw, max(1, rows) * th))
        for i, fr in enumerate(frames):
            im = Image.fromarray(fr.copy())
            ImageDraw.Draw(im).text((5, 5), f"{i * 0.5:.1f}s", fill=(255, 40, 40))
            sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
        sp = os.path.join(out, f"{os.path.splitext(f)[0]}.jpg")
        sheet.save(sp, quality=82)
        print(f"{f}: {d:.1f}s -> {sp}")
    idir = jpath(job, 'images')
    imgs = [f for f in sorted(os.listdir(idir)) if f.lower().endswith(IMAGE)] if os.path.isdir(idir) else []
    if imgs:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            pass
        tiles = []
        for f in imgs:
            im = Image.open(os.path.join(idir, f)).convert('RGB')
            im.thumbnail((360, 360))
            tile = Image.new('RGB', (360, 380), 'white')
            tile.paste(im, ((360 - im.width) // 2, 0))
            ImageDraw.Draw(tile).text((5, 364), f, fill='black')
            tiles.append(tile)
        sheet = Image.new('RGB', (360 * min(5, len(tiles)), 380 * ((len(tiles) + 4) // 5)), 'white')
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 5) * 360, (i // 5) * 380))
        sp = os.path.join(out, 'images.jpg')
        sheet.save(sp, quality=85)
        print(f"images: {len(imgs)} -> {sp}")


if __name__ == '__main__':
    main()
