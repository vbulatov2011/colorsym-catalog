"""
Pack and optimize rendered catalog WebP assets for lean static deployment.

What it does (idempotently — never double-compresses already-lossy WebPs):
  1. Deduplicates the 5 group_*.webp files per symmetry group into
     <family>/<G_stem>/gen/group_*.webp (keeping thin overlays lossless and
     encoding group_pattern.webp and group.webp as lossy WebP q=90), removing
     redundant copies from every entry's gen/ directory.
  2. Bundles each entry's N x N coset piece images (piece_file(i, j, N)) into
     a single tiled sprite sheet gen/cosets.webp (col=i, row=j; 320x320 or
     320x160 tiles — exact multiples of 16 and <= 3840 px even for N=12;
     lossy WebP q=88) and removes the individual piece files.
  3. Removes gen/sheet.html and the sheet-only union images (union_file(j, N),
     e.g. 0123_0.webp / u12_00.webp), which are unused by public entry pages.
  4. Deduplicates pixel-identical <slug>.o*.webp and <slug>.<k>.webp files
     within each entry (recording aliases in versions/<v>/pack_meta.json).
  5. Re-encodes full-color 800x800 / 800x400 pattern images (<slug>.<k>.webp,
     <slug>.o*.webp) from lossless WebP to lossy WebP q=90 while keeping all
     transparent line-art overlays (sub_*, group_domain/tiling/gens/marks,
     f*, g*) lossless.

Usage:
  python tools/pack_assets.py                 # current CATALOG_FAMILY / version
  python tools/pack_assets.py <stem>...       # selected group stems only
  python tools/pack_assets.py --all-families  # all registered main families
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_paths as P
from entry_names import entry_names, piece_file, union_file

if '--all-families' in sys.argv:
    for _fid in P.FAMILIES:
        _env = dict(os.environ, CATALOG_FAMILY=_fid)
        _env.pop('CATALOG_VERSION', None)
        subprocess.run([sys.executable, os.path.abspath(__file__)], check=True, env=_env)
    sys.exit(0)

THREADS = min(16, os.cpu_count() or 8)
GROUP_OVERLAYS = ('group_domain.webp', 'group_tiling.webp', 'group_gens.webp', 'group_marks.webp')
GROUP_SHARED = GROUP_OVERLAYS + ('group_pattern.webp',)
LOSSY_PATTERN_Q = 90
LOSSY_ATLAS_Q = 88
WEBP_METHOD = 4


def is_lossy_webp(path):
    """Return True iff path is a WebP file encoded with lossy VP8 (not lossless VP8L)."""
    try:
        with open(path, 'rb') as f:
            hdr = f.read(64)
    except OSError:
        return False
    if len(hdr) < 16 or hdr[:4] != b'RIFF' or hdr[8:12] != b'WEBP':
        return False
    fourcc = hdr[12:16]
    if fourcc == b'VP8 ':
        return True
    if fourcc == b'VP8L':
        return False
    if fourcc == b'VP8X':
        # Scan RIFF sub-chunks starting at offset 12 + 8 + 10 = 30
        with open(path, 'rb') as f:
            f.seek(12)
            while True:
                ch = f.read(8)
                if len(ch) < 8:
                    break
                cid = ch[:4]
                csz = int.from_bytes(ch[4:8], 'little')
                if cid == b'VP8 ':
                    return True
                if cid == b'VP8L':
                    return False
                f.seek(csz + (csz & 1), 1)
    return False


def encode_lossy_webp(src_path, dst_path=None, quality=LOSSY_PATTERN_Q, force_overwrite=False):
    """Encode image at src_path as lossy WebP. Returns (saved_bytes, converted)."""
    dst = dst_path or src_path
    if dst == src_path and is_lossy_webp(src_path) and not force_overwrite:
        return 0, False
    old_sz = os.path.getsize(src_path)
    tmp = dst + f'.tmp.{os.getpid()}'
    try:
        with Image.open(src_path) as im:
            # Preserve alpha if present; RGB saves a bit extra when opaque
            if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
                out_im = im.convert('RGBA')
            else:
                out_im = im.convert('RGB')
            out_im.save(tmp, 'WEBP', quality=quality, method=WEBP_METHOD)
        new_sz = os.path.getsize(tmp)
        # Verify decodable
        with Image.open(tmp) as chk:
            chk.load()
        if dst == src_path and new_sz >= old_sz and not force_overwrite:
            os.remove(tmp)
            return 0, False
        os.replace(tmp, dst)
        return (old_sz - new_sz) if dst == src_path else 0, True
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def tile_dims(w, h, n):
    """Choose multiple-of-16 tile dimensions keeping N*max(tw, th) <= 3840."""
    if w == 400 and h == 400:
        tw, th = 320, 320
    elif w == 400 and h == 200:
        tw, th = 320, 160
    else:
        scale = min(0.8, 3840.0 / max(1, n * max(w, h)))
        tw = max(16, int(round((w * scale) / 16.0)) * 16)
        th = max(16, int(round((h * scale) / 16.0)) * 16)
    while n * max(tw, th) > 3840 and tw > 32 and th > 32:
        tw = max(16, (tw - 16))
        th = max(16, int(round(tw * (h / float(w)) / 16.0)) * 16)
    return tw, th


def pack_group_shared(gstem):
    """Move shared group_*.webp into <fam>/<gstem>/gen/ and remove entry duplicates."""
    stats = {'files_removed': 0, 'bytes_saved': 0}
    group_gen = P.path(P.fam(gstem, 'gen'))
    os.makedirs(group_gen, exist_ok=True)
    entry_gens = sorted(glob.glob(P.path(P.fam(gstem, '*', '*', 'gen'))))

    for fn in GROUP_SHARED:
        dst = os.path.join(group_gen, fn)
        src_copies = [os.path.join(eg, fn) for eg in entry_gens if os.path.exists(os.path.join(eg, fn))]
        if src_copies:
            first = src_copies[0]
            if fn == 'group_pattern.webp':
                encode_lossy_webp(first, dst, quality=LOSSY_PATTERN_Q, force_overwrite=True)
            else:
                tmp = dst + f'.tmp.{os.getpid()}'
                shutil.copy2(first, tmp)
                os.replace(tmp, dst)
            # Remove all redundant entry copies now that shared copy is safely in place
            assert os.path.exists(dst) and os.path.getsize(dst) > 0
            for cp in src_copies:
                stats['bytes_saved'] += os.path.getsize(cp)
                os.remove(cp)
                stats['files_removed'] += 1
            # Subtract size of the newly created shared file from net bytes_saved
            stats['bytes_saved'] -= os.path.getsize(dst)
            stats['files_removed'] -= 1
        elif fn == 'group_pattern.webp' and os.path.exists(dst):
            saved, _ = encode_lossy_webp(dst, quality=LOSSY_PATTERN_Q)
            stats['bytes_saved'] += saved

    # Also lossy-compress group.webp thumbnail
    gthumb = os.path.join(group_gen, 'group.webp')
    if os.path.exists(gthumb):
        saved, _ = encode_lossy_webp(gthumb, quality=LOSSY_PATTERN_Q)
        stats['bytes_saved'] += saved

    return stats


def pack_entry(task):
    """Optimize one entry's gen/ folder. Returns (entry_dir, aliases_dict, stats)."""
    gstem, entry_name, n, old_aliases = task
    nm = entry_names(entry_name, n)
    entry_dir = nm['dir']
    slug = nm['slug']
    gen = P.path(P.fam(entry_dir, 'gen'))
    stats = {'files_removed': 0, 'bytes_saved': 0, 'atlases': 0, 'dedup': 0, 'unions_rm': 0, 'lossy': 0}

    if not os.path.isdir(gen):
        return entry_dir, old_aliases, stats

    # 1. Bundle N x N coset grid pieces into gen/cosets.webp
    piece_names = [piece_file(i, j, n)[:-4] + '.webp' for j in range(n) for i in range(n)]
    piece_paths = [os.path.join(gen, fn) for fn in piece_names]
    if all(os.path.exists(p) for p in piece_paths):
        old_piece_bytes = sum(os.path.getsize(p) for p in piece_paths)
        with Image.open(piece_paths[0]) as im0:
            w0, h0 = im0.size
        tw, th = tile_dims(w0, h0, n)
        atlas = Image.new('RGBA', (n * tw, n * th), (0, 0, 0, 0))
        for j in range(n):
            for i in range(n):
                p = piece_paths[j * n + i]
                with Image.open(p) as im:
                    tile = im.convert('RGBA')
                    if tile.size != (tw, th):
                        tile = tile.resize((tw, th), Image.LANCZOS)
                    atlas.paste(tile, (i * tw, j * th))
        atlas_path = os.path.join(gen, 'cosets.webp')
        tmp = atlas_path + f'.tmp.{os.getpid()}'
        atlas.save(tmp, 'WEBP', quality=LOSSY_ATLAS_Q, method=WEBP_METHOD)
        with Image.open(tmp) as chk:
            assert chk.size == (n * tw, n * th), f'atlas size mismatch: {chk.size}'
        os.replace(tmp, atlas_path)
        atlas_bytes = os.path.getsize(atlas_path)
        for p in piece_paths:
            os.remove(p)
        stats['files_removed'] += len(piece_paths) - 1
        stats['bytes_saved'] += old_piece_bytes - atlas_bytes
        stats['atlases'] += 1

    # 2. Remove sheet.html-only union files (union_file(j, N)) and gen/sheet.html
    for j in range(n):
        up = os.path.join(gen, union_file(j, n)[:-4] + '.webp')
        if os.path.exists(up):
            stats['bytes_saved'] += os.path.getsize(up)
            os.remove(up)
            stats['files_removed'] += 1
            stats['unions_rm'] += 1
    sht = os.path.join(gen, 'sheet.html')
    if os.path.exists(sht):
        stats['bytes_saved'] += os.path.getsize(sht)
        os.remove(sht)
        stats['files_removed'] += 1

    # 3. Deduplicate pixel-identical <slug>.<k>.webp and <slug>.o*.webp BEFORE lossy encode
    # Canonical priority: .1, .2, ..., .N, then .o, .o1, ..., .o(N-1)
    cands = []
    for fn in sorted(os.listdir(gen)):
        if not (fn.startswith(slug + '.') and fn.endswith('.webp')):
            continue
        tail = fn[len(slug) + 1:-5]
        if tail.isdigit():
            prio = (0, int(tail))
        elif tail == 'o':
            prio = (1, 0)
        elif tail.startswith('o') and tail[1:].isdigit():
            prio = (1, int(tail[1:]))
        else:
            continue
        cands.append((prio, fn))
    cands.sort()

    # Keep valid prior aliases for files that were already deduplicated in a previous run
    aliases = {}
    for k, v in (old_aliases or {}).items():
        if not os.path.exists(os.path.join(gen, k)) and os.path.exists(os.path.join(gen, v)):
            aliases[k] = v

    # Only compute pixel hashes when at least one candidate is still lossless (fresh render)
    # or when multiple files exist and could be exact duplicates
    seen_hash = {}
    remaining = []
    for _, fn in cands:
        p = os.path.join(gen, fn)
        with Image.open(p) as im:
            h = hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest()
        if h in seen_hash:
            aliases[fn] = seen_hash[h]
            stats['bytes_saved'] += os.path.getsize(p)
            os.remove(p)
            stats['files_removed'] += 1
            stats['dedup'] += 1
        else:
            seen_hash[h] = fn
            remaining.append(fn)

    # Collapse any transitive alias chains (a -> b -> c => a -> c)
    for k in list(aliases.keys()):
        v = aliases[k]
        while v in aliases:
            v = aliases[v]
        aliases[k] = v

    # 4. Lossy q=90 WebP on remaining full-color <slug>.<k>.webp and <slug>.o*.webp
    for fn in remaining:
        p = os.path.join(gen, fn)
        saved, conv = encode_lossy_webp(p, quality=LOSSY_PATTERN_Q)
        if conv:
            stats['bytes_saved'] += saved
            stats['lossy'] += 1

    return entry_dir, aliases, stats


def pack_meta_path():
    v = P.VERSION or P.main_version(P.FAMILY)
    if v:
        return P.path(P.version_dir(v), 'pack_meta.json')
    return P.path(P.DATA_DIR, 'pack_meta.json')


def main():
    only = {a for a in sys.argv[1:] if not a.startswith('-')}
    idx = json.load(open(P.data_file('index'), encoding='utf-8'))
    fmeta = P.family_meta() or {}
    lo, hi = (int(fmeta['colorRange'][0]), int(fmeta['colorRange'][1])) if fmeta.get('colorRange') else (2, 7)

    meta_file = pack_meta_path()
    meta = json.load(open(meta_file, encoding='utf-8')) if os.path.exists(meta_file) else {'aliases': {}}
    all_aliases = meta.setdefault('aliases', {})

    gs = [g for g in idx['groups'] if not only or g['stem'] in only]
    tot = {'files_removed': 0, 'bytes_saved': 0, 'atlases': 0, 'dedup': 0, 'unions_rm': 0, 'lossy': 0}

    # 1. Group-level shared group_*.webp deduplication
    with ThreadPoolExecutor(THREADS) as ex:
        for st in ex.map(pack_group_shared, [g['stem'] for g in gs]):
            tot['files_removed'] += st['files_removed']
            tot['bytes_saved'] += st['bytes_saved']

    # 2. Per-entry packing (atlas, union removal, dedup, lossy pattern re-encode)
    tasks = []
    for g in gs:
        m = json.load(open(P.data_file(g['stem']), encoding='utf-8'))
        for s in m.get('subgroups', []):
            n = s['index']
            if lo <= n <= hi:
                edir = entry_names(s['name'], n)['dir']
                tasks.append((g['stem'], s['name'], n, all_aliases.get(edir, {})))

    with ThreadPoolExecutor(THREADS) as ex:
        for edir, aliases, st in ex.map(pack_entry, tasks):
            if aliases:
                all_aliases[edir] = aliases
            elif edir in all_aliases:
                del all_aliases[edir]
            for k in tot:
                tot[k] += st[k]

    os.makedirs(os.path.dirname(meta_file), exist_ok=True)
    tmp = meta_file + f'.tmp.{os.getpid()}'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(meta, f, indent=1, sort_keys=True)
        f.write('\n')
    os.replace(tmp, meta_file)

    print(
        f'pack_assets [{P.FAMILY}]: {len(gs)} groups, {len(tasks)} entries -> '
        f'{tot["atlases"]} atlases, {tot["unions_rm"]} unions removed, '
        f'{tot["dedup"]} dup colorings removed, {tot["lossy"]} patterns -> lossy q={LOSSY_PATTERN_Q}; '
        f'net {tot["files_removed"]:+d} files removed, {tot["bytes_saved"]/1024/1024:+.2f} MB saved'
    )


if __name__ == '__main__':
    main()
