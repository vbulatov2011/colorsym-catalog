# Convert an entry's rendered PNGs to lossless WebP.
#
#   python tools/to_webp.py 632 "632/333[8]"      one entry
#   python tools/to_webp.py --all                 every entry in data/index.json
#   python tools/to_webp.py --dir 632/8/632-333-8/gen
#
#   --keep     leave the PNGs in place (default: delete after a good convert)
#   --verify   decode each result back and require the RGBA to match exactly
#   -z N       compression effort (default 6)
#
# The render job writes PNG because the browser's canvas WebP encoder is poor
# at lossless - it produced 64% of PNG where cwebp gives 12%, and made sparse
# layers larger than the PNG.  So the pipeline stays: run the job, convert
# here, then regenerate the page.
#
# Measured over the 178 images of the three built entries: PNG 17.29 MB ->
# lossless WebP 2.13 MB (12%), pixel identical, and decoding is ~0.7x the time
# of PNG.  Effort: -z 6 gives 35 KB in 163 ms where -z 9 gives 34 KB in 3.2 s.
#
# Encoder: the cwebp/dwebp command line tools when they can be found, else
# Pillow, whose WebP support is the same libwebp (1.6.0 on this machine).  -z N
# is libwebp's lossless preset N, i.e. a (method, quality) pair, and Pillow is
# given exactly that pair, so both paths run the same encoder configuration.
import os, sys, glob, json, subprocess, shutil
from concurrent.futures import ThreadPoolExecutor
from entry_names import entry_names

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_bin(name):
    """cwebp/dwebp from PATH, else the winget install location, else None"""
    found = shutil.which(name)
    if found:
        return found
    pat = os.path.join(os.path.expandvars('%LOCALAPPDATA%'), 'Microsoft', 'WinGet',
                       'Packages', 'Google.Libwebp*', 'libwebp-*', 'bin', name + '.exe')
    hits = sorted(glob.glob(pat))
    return hits[-1] if hits else None


def pillow_webp():
    """Pillow's PIL.Image when it was built with WebP support, else None"""
    try:
        from PIL import Image, features
        return Image if features.check('webp') else None
    except ImportError:
        return None


# libwebp's WebPConfigLosslessPreset: level -> (method, quality)
LOSSLESS_PRESET = [(0, 0), (1, 20), (2, 25), (3, 30), (3, 50),
                   (4, 50), (4, 75), (4, 90), (5, 90), (6, 100)]

CWEBP = find_bin('cwebp')
DWEBP = None          # resolved only when --verify is used
PIL_IMAGE = None if CWEBP else pillow_webp()
if not CWEBP and not PIL_IMAGE:
    sys.exit('no WebP encoder: install libwebp (winget install Google.Libwebp '
             '--scope user) or Pillow with WebP support (pip install pillow)')


def gen_dir_for(stem, entry_name):
    m = json.load(open(os.path.join(CAT, 'data', '%s.json' % stem), encoding='utf-8'))
    entry = next(s for s in m['subgroups'] if s['name'] == entry_name)
    return os.path.join(CAT, *entry_names(entry_name, entry['index'])['dir'].split('/'),
                        'gen')


def rgba_of_webp(path):
    out = path + '.pam'
    subprocess.run([DWEBP, '-quiet', '-pam', path, '-o', out], capture_output=True)
    data = open(out, 'rb').read()
    os.remove(out)
    return data


def rgba_of_png(path):
    """decode a PNG to the same raw form, by way of a throwaway lossless webp"""
    tmp = path + '.ref.webp'
    subprocess.run([CWEBP, '-quiet', '-lossless', '-z', '0', path, '-o', tmp],
                   capture_output=True)
    data = rgba_of_webp(tmp)
    os.remove(tmp)
    return data


def same_pixels_pillow(png, webp):
    """RGBA equal, except that a fully transparent pixel's colour is free - the
    cwebp path compares the same way, since lossless WebP without -exact may
    rewrite the RGB under alpha 0"""
    a = PIL_IMAGE.open(png).convert('RGBA').tobytes()
    b = PIL_IMAGE.open(webp).convert('RGBA').tobytes()
    if len(a) != len(b):
        return False
    if a == b:
        return True
    for i in range(0, len(a), 4):
        if a[i + 3] != b[i + 3]:
            return False
        if a[i + 3] and a[i:i + 3] != b[i:i + 3]:
            return False
    return True


def convert_pillow(png, effort, keep, verify):
    webp = png[:-4] + '.webp'
    method, quality = LOSSLESS_PRESET[effort]
    try:
        PIL_IMAGE.open(png).save(webp, 'WEBP', lossless=True,
                                 method=method, quality=quality)
    except Exception as e:
        return (png, None, 'Pillow failed: %s' % e)
    if verify and not same_pixels_pillow(png, webp):
        os.remove(webp)
        return (png, None, 'NOT pixel exact')
    before, after = os.path.getsize(png), os.path.getsize(webp)
    if not keep:
        os.remove(png)
    return (png, (before, after), None)


def convert(png, effort, keep, verify):
    if not CWEBP:
        return convert_pillow(png, effort, keep, verify)
    webp = png[:-4] + '.webp'
    r = subprocess.run([CWEBP, '-quiet', '-lossless', '-z', str(effort), png, '-o', webp],
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(webp):
        return (png, None, 'cwebp failed: ' + r.stderr.decode('utf-8', 'replace')[:120])
    if verify and rgba_of_webp(webp) != rgba_of_png(png):
        os.remove(webp)
        return (png, None, 'NOT pixel exact')
    before, after = os.path.getsize(png), os.path.getsize(webp)
    if not keep:
        os.remove(png)
    return (png, (before, after), None)


def main():
    args = sys.argv[1:]
    keep = '--keep' in args
    verify = '--verify' in args
    effort = 6
    if '-z' in args:
        effort = int(args[args.index('-z') + 1])
    positional = [a for i, a in enumerate(args)
                  if not a.startswith('-')
                  and not (i and args[i - 1] == '-z')]

    dirs = []
    if '--all' in args:
        index = json.load(open(os.path.join(CAT, 'data', 'index.json'), encoding='utf-8'))
        stems = index if isinstance(index, list) else index.get('groups', [])
        for st in stems:
            stem = st if isinstance(st, str) else st.get('stem') or st.get('name')
            try:
                m = json.load(open(os.path.join(CAT, 'data', '%s.json' % stem), encoding='utf-8'))
            except IOError:
                continue
            for sub in m['subgroups']:
                d = gen_dir_for(stem, sub['name'])
                if os.path.isdir(d):
                    dirs.append(d)
    elif '--dir' in args:
        dirs = [os.path.join(CAT, d) for d in positional]
    elif len(positional) >= 2:
        dirs = [gen_dir_for(positional[0], positional[1])]
    else:
        sys.exit(__doc__ or 'usage: to_webp.py <stem> "<entry>" | --all | --dir <path>')

    if verify and CWEBP:
        global DWEBP
        DWEBP = find_bin('dwebp')
        if not DWEBP:
            sys.exit('dwebp not found next to cwebp - needed for --verify')

    pngs = []
    for d in dirs:
        pngs += sorted(glob.glob(os.path.join(d, '*.png')))
    if not pngs:
        print('no PNGs to convert in:', ', '.join(dirs))
        return

    before = after = 0
    failures = []
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        for png, sizes, err in pool.map(lambda p: convert(p, effort, keep, verify), pngs):
            if err:
                failures.append((os.path.basename(png), err))
            else:
                before += sizes[0]
                after += sizes[1]

    MB = lambda b: round(b / 1048576.0, 2)
    print('converted %d/%d images in %d dir(s), -z %d, %s%s'
          % (len(pngs) - len(failures), len(pngs), len(dirs), effort,
             'cwebp' if CWEBP else 'Pillow (libwebp, method %d quality %d)'
             % LOSSLESS_PRESET[effort],
             ', verified pixel exact' if verify else ''))
    print('  %s MB PNG  ->  %s MB WebP  (%d%%)'
          % (MB(before), MB(after), round(100.0 * after / before) if before else 0))
    if not keep:
        print('  PNGs removed (they are intermediates; .gitignore skips **/gen/*.png)')
    for name, err in failures:
        print('  FAILED', name, '-', err)
    if failures:
        sys.exit(1)


if __name__ == '__main__':
    main()
