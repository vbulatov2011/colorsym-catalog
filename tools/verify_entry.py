# Verify rendered catalog entries from their images - the job's PNGs, or the
# lossless WebPs after tools/to_webp.py (pixel identical):
#
#   python tools/verify_entry.py 442 "442/442[4]#1" "442/o[4]"
#   python tools/verify_entry.py 442 --all       every entry of data/wp/442.json with a gen/ dir
#   python tools/verify_entry.py 632@6-2-3-2-kite --all
#
# Checks, pixel exact (a footprint is alpha > 0):
#   files       every image the entry's job lists is there
#   coverage    at most 1% of the uncolored pattern is fully transparent: a
#               motif that fills the plane leaves none, unless the renderer ran
#               out of folding steps (make_entry_job.py --iterations); skip
#               with --sparse for a motif that leaves gaps
#   unions      each 'all orbits of H g_j' image covers exactly the uncolored pattern
#   pieces      the N x N pieces f_i H g_j: every row and every column unions to
#               the same footprint
#   placements  the rows of pieces, as sets of footprints, fall into exactly K
#               classes - the placements - and rows 0..K-1 are pairwise distinct
#   colors      each coloring .1 ... .N and .o shows every palette color on more
#               than 2% of its opaque pixels; palette color j is the dominant
#               color of union image j
#   relabel     coloring .k is the partition of its placement's representative
#   normal      .o and .1 are the same partition exactly when H is normal
#   identity    color 0 is the same set of pixels in .1 and in .o: the motif
#               copies of the coset H and of the orbit H(F), for any H.  A job
#               that feeds invcos to the cosets colors by iota(H) instead
#               (make_entry_job.py) and fails here.
# Partitions are compared on the pixels whose color is a palette color in both
# images: the same partition means the colors correspond one to one there.
#
# Prints the sampled palette per entry, the argument make_entry_page.py takes.
# Exit status 1 when any check fails.
import json, os, sys
import numpy as np
from PIL import Image
from entry_names import entry_names

import catalog_paths as P


def find(gen, name):
    """an image by its job file name, as PNG or as the WebP that replaced it"""
    base = os.path.join(gen, name[:-4])
    for ext in ('.png', '.webp'):
        if os.path.exists(base + ext):
            return base + ext
    return None


def rgba(path):
    return np.asarray(Image.open(path).convert('RGBA'))


def footprint(path):
    return rgba(path)[..., 3] > 0


def dominant(img):
    """the most frequent color among the opaque pixels"""
    px = img[img[..., 3] == 255][:, :3]
    keys = (px[:, 0].astype(np.int64) << 16) | (px[:, 1].astype(np.int64) << 8) | px[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    k = int(vals[counts.argmax()])
    return (k >> 16) & 255, (k >> 8) & 255, k & 255


def color_index(img, palette):
    """per pixel: the palette index of an opaque pixel of exactly that color, else -1"""
    out = np.full(img.shape[:2], -1, dtype=np.int8)
    opaque = img[..., 3] == 255
    for j, c in enumerate(palette):
        out[opaque & np.all(img[..., :3] == c, axis=-1)] = j
    return out


def same_partition(a, b, palette):
    """(same?, pixels compared, conflicting pixels): the colors of a and b must
    correspond one to one on the pixels where both show a palette color"""
    ia, ib = color_index(a, palette), color_index(b, palette)
    both = (ia >= 0) & (ib >= 0)
    pairs = ia[both].astype(np.int64) * 64 + ib[both]
    vals, counts = np.unique(pairs, return_counts=True)
    best_a, best_b = {}, {}                       # each color's majority partner
    for v, c in zip(vals, counts):
        x, y = divmod(int(v), 64)
        if c > best_a.get(x, (None, 0))[1]:
            best_a[x] = (y, c)
        if c > best_b.get(y, (None, 0))[1]:
            best_b[y] = (x, c)
    conflicts = 0
    for v, c in zip(vals, counts):
        x, y = divmod(int(v), 64)
        if best_a[x][0] != y or best_b[y][0] != x:
            conflicts += int(c)
    return conflicts == 0, int(both.sum()), conflicts


SPARSE = '--sparse' in sys.argv


def verify(stem, entry):
    n, K = entry['index'], entry['placements']
    names = entry_names(entry['name'], n)
    gen = P.path(P.fam(names['dir'], 'gen'))
    job = json.load(open(P.job_file(names['job_file']), encoding='utf-8'))
    files = [it['file'] for it in job['items']]
    fails = []

    missing = [f for f in files if not find(gen, f)]
    if missing:
        return None, ['files: %d missing, e.g. %s' % (len(missing), missing[:3])]

    pattern = footprint(find(gen, 'group_pattern.png'))
    gap = 1.0 - float(pattern.mean())
    if not SPARSE and gap > 0.01:
        fails.append('coverage: %.1f%% of the uncolored pattern is transparent' % (100 * gap))
    union_files = [f for f in files if f.startswith(''.join(map(str, range(n))) + '_')]
    unions = [rgba(find(gen, f)) for f in union_files]
    off = [int((u[..., 3] > 0).__xor__(pattern).sum()) for u in unions]
    if any(off):
        fails.append('unions: %s px off the pattern' % off)
    palette = [dominant(u) for u in unions]
    if len(set(palette)) != n:
        fails.append('palette: %d distinct colors for %d unions' % (len(set(palette)), n))

    piece = [[footprint(find(gen, '%d%d.png' % (i, j))) for j in range(n)] for i in range(n)]
    rows = [np.logical_or.reduce(piece[i]) for i in range(n)]
    cols = [np.logical_or.reduce([piece[i][j] for i in range(n)]) for j in range(n)]
    ref = rows[0]
    off = [int((u ^ ref).sum()) for u in rows + cols]
    if any(off):
        fails.append('pieces: row/column unions differ by %s px' % off)

    sig = [frozenset(p.tobytes() for p in piece[i]) for i in range(n)]
    classes = {}
    for i, s in enumerate(sig):
        classes.setdefault(s, []).append(i)
    rep = {i: min(c) for c in classes.values() for i in c}
    if len(classes) != K or sorted(set(rep.values())) != list(range(K)):
        fails.append('placements: rows fall into %d classes %s, manifest K=%d'
                     % (len(classes), sorted(classes.values()), K))

    slug = names['slug']
    col = {k: rgba(find(gen, '%s.%s.png' % (slug, k))) for k in [str(i) for i in range(1, n + 1)] + ['o']}
    for k, img in col.items():
        opaque = img[..., 3] == 255
        idx = color_index(img, palette)
        share = [float((idx == j).sum()) / max(1, opaque.sum()) for j in range(n)]
        if min(share) <= 0.02:
            fails.append('colors: .%s shows palette shares %s' % (k, ['%.3f' % s for s in share]))
    for i in range(K, n):
        same, cmp_px, bad = same_partition(col[str(i + 1)], col[str(rep[i] + 1)], palette)
        if not same:
            fails.append('relabel: .%d vs its representative .%d: %d of %d px conflict'
                         % (i + 1, rep[i] + 1, bad, cmp_px))
    same, cmp_px, bad = same_partition(col['o'], col['1'], palette)
    if same != entry['normal']:
        fails.append('normal: H %s normal but .o and .1 are %s the same partition (%d of %d px conflict)'
                     % ('is' if entry['normal'] else 'is not', '' if same else 'not',
                        bad, cmp_px))
    i1, io = color_index(col['1'], palette), color_index(col['o'], palette)
    both = (i1 >= 0) & (io >= 0)
    a, b = both & (i1 == 0), both & (io == 0)
    if (a ^ b).any():
        fails.append('identity: color 0 of .1 and of .o differ on %d of %d px'
                     % (int((a ^ b).sum()), int((a | b).sum())))
    return palette, fails


def main():
    args = sys.argv[1:]
    stem = args[0]
    m = json.load(open(P.data_file(stem), encoding='utf-8'))
    args = [a for a in args if a != '--sparse']
    if '--all' in args:
        entries = [s for s in m['subgroups']
                   if os.path.isdir(P.path(P.fam(entry_names(s['name'], s['index'])['dir'], 'gen')))]
    else:
        entries = [next(s for s in m['subgroups'] if s['name'] == a) for a in args[1:]]
    bad = 0
    for e in entries:
        palette, fails = verify(stem, e)
        pal = ','.join('#%02x%02x%02x' % c for c in palette) if palette else '-'
        print('%-16s n=%d K=%d %-6s %s  %s' % (e['name'], e['index'], e['placements'],
              'normal' if e['normal'] else '', 'ok  ' if not fails else 'FAIL', pal))
        for f in fails:
            print('    ' + f)
        bad += bool(fails)
    print('%d of %d entries pass' % (len(entries) - bad, len(entries)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
