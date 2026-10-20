#!/usr/bin/env python3
"""Download the brand's own product photos from their website.

Usage:
    python3 grab_photos.py <job_dir> <product page url> [more urls ...] [--max 12]

Saves into <job>/Raw files/From website/, where sort.py picks them up as photos.
Takes the page's share image, the product images (Shopify stores give a clean
list) and any other large images on the page. Skips icons, logos in the
header, tracking pixels and anything under 400 px. Look at every photo before
using it: only use real product shots, never someone else's content.
"""
import argparse, html, io, json, os, re, sys, urllib.parse, urllib.request
from PIL import Image

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 '
                    '(KHTML, like Gecko) Version/17.0 Safari/605.1.15'}
SKIP = re.compile(r'(icon|logo|sprite|favicon|pixel|badge|payment|flag|avatar|placeholder|spinner|loader)', re.I)


def get(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def candidates(url, page):
    found = []
    for m in re.finditer(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*>', page, re.I):
        c = re.search(r'content=["\']([^"\']+)', m.group(0))
        if c:
            found.append(c.group(1))
    # Shopify: /products/<handle>.json lists every product image at full size
    if '/products/' in url:
        try:
            js = json.loads(get(url.split('?')[0].rstrip('/') + '.json'))
            found += [im['src'] for im in js.get('product', {}).get('images', [])]
        except Exception:
            pass
    for m in re.finditer(r'<img[^>]+>', page, re.I):
        tag = m.group(0)
        src = re.search(r'data-src=["\']([^"\']+)', tag) or re.search(r'\ssrc=["\']([^"\']+)', tag)
        srcset = re.search(r'srcset=["\']([^"\']+)', tag)
        if srcset:   # take the biggest size offered
            src_url = srcset.group(1).split(',')[-1].strip().split(' ')[0]
        elif src:
            src_url = src.group(1)
        else:
            continue
        labels = ' '.join(re.findall(r'(?:class|alt|id)=["\']([^"\']*)', tag))
        if not SKIP.search(labels) and not SKIP.search(src_url.split('?')[0].rsplit('/', 1)[-1]):
            found.append(src_url)
    out, seen = [], set()
    for f in found:
        f = urllib.parse.urljoin(url, html.unescape(f))
        if f.startswith('//'):
            f = 'https:' + f
        key = re.sub(r'(_\d+x\d*|\?.*)', '', f)      # same photo at another size
        if f.startswith(('http', 'file')) and not f.lower().split('?')[0].endswith(('.svg', '.gif')) and key not in seen:
            seen.add(key)
            out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    ap.add_argument('urls', nargs='+')
    ap.add_argument('--max', type=int, default=12)
    args = ap.parse_args()
    dest = os.path.join(args.job, 'Raw files', 'From website')
    os.makedirs(dest, exist_ok=True)
    saved = 0
    for url in args.urls:
        try:
            page = get(url).decode('utf-8', 'replace')
        except Exception as e:
            print(f"couldn't open {url}: {e}")
            continue
        slug = re.sub(r'[^a-z0-9]+', '-', urllib.parse.urlparse(url).path.lower().split('/')[-1]).strip('-')[:40] or 'home'
        for i, src in enumerate(candidates(url, page)):
            if saved >= args.max:
                break
            try:
                im = Image.open(io.BytesIO(get(src)))
                im.load()
            except Exception:
                continue
            if min(im.size) < 400:
                continue
            p = os.path.join(dest, f"{slug}-{i + 1:02d}.{'png' if im.mode in ('RGBA', 'LA', 'P') else 'jpg'}")
            (im if p.endswith('.png') else im.convert('RGB')).save(p, quality=92)
            saved += 1
            print(f"saved {os.path.relpath(p, args.job)}  {im.size[0]}x{im.size[1]}")
    if not saved:
        sys.exit("no usable photos found: ask the creator to drop product photos into Raw files")
    print(f"{saved} photo(s) in {dest}. Run sort.py again, then look at them before using any.")


if __name__ == '__main__':
    main()
