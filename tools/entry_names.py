# File and folder names of a catalog entry, from its display name G/H[n]#k.
#
#   632/333[8]     -> slug 632-333-8      job 632_333_8      dir 632/8/632-333-8
#   333/333[3]#2   -> slug 333-333-3-2    job 333_333_3_2    dir 333/3/333-333-3-2
#   *632/*333[2]   -> slug s632-s333-2    ...                ('*' is written 's')
#
# '#k' tells apart subgroups that share G/H[n] (see catalog-layout: names are
# G/H[n]#k, #k omitted when unique); it becomes a trailing '-k' because '#'
# would start a URL fragment.  Shared by make_entry_job.py, make_entry_page.py
# and make_sheet.py so the three always agree.

# The catalog's counts of colors start at MIN_N: the 1-color group G/G[1]
# (H = G, one color: the uncolored pattern itself) is no coloring and is left
# out (2026-11-16) - no entry, job or page.  make_index_pages.py and
# make_entry_page.py both run their counts from here.
MIN_N = 2
MAX_N = 7               # ... and run up to MAX_N
MAX_GRID_N = 4          # N x N coset/orbit partition table is only rendered for N <= MAX_GRID_N


def placement_classes(cosets, n):
    """Partition 0..n-1 into equivalence classes of cosets sharing a point
    stabilizer in the monodromy group P = <cosets> <= S_n.

    Uses the centralizer C_{S_n}(P) (O(n^2 * |gens|)) rather than enumerating P
    (which blows up for high-index non-abelian subgroups like 237 at n >= 14).
    """
    perms = [[ord(c) - 97 for c in w] for w in cosets.split()]
    central = []
    for target in range(n):
        s = [-1] * n
        s[0] = target
        q = [0]
        ok = True
        while q and ok:
            i = q.pop()
            si = s[i]
            for p in perms:
                gi, gs = p[i], p[si]
                if s[gi] == -1:
                    s[gi] = gs
                    q.append(gi)
                elif s[gi] != gs:
                    ok = False
                    break
        if ok and all(v != -1 for v in s) and len(set(s)) == n:
            central.append(s)
    seen = [False] * n
    classes = []
    for i in range(n):
        if seen[i]:
            continue
        orb = sorted({s[i] for s in central})
        for j in orb:
            seen[j] = True
        classes.append(orb)
    return sorted(classes)


def group_motif(cat, name, stem):
    """The motif a group renders and the manifest its entries are built from.
    The preset is the version's (catalog_paths: the snapshot of the preset its
    versions/<v>/version.json gives the group), else the one its thumbnail job
    renders (<jobs>/group_<stem>.json), else presets/wp/wpe/wpe-<name>.json.  The
    manifest follows that preset's domain: data/wp/<stem>@<shape>.json for another
    domain shape, <stem>@...@dirichlet.json when it turns on a Dirichlet domain
    (make_manifest.mjs --domain / --dirichlet), whichever exists, else
    data/wp/<stem>.json.  'stale': what is wrong with the manifest for this preset
    (a Dirichlet domain without its manifest, or one of another base or words),
    else None."""
    import json, os
    import catalog_paths as P
    fm = P.family_meta() or {}
    pset = fm.get('defaultPresetSet') or 'wpe'
    ppre = fm.get('defaultPresetPrefix') or 'wpe-'
    if P.FAMILY == 'wp':
        lib = ('O' if name == 'o' else name.replace('x', 'X')).replace('*', 's')
    else:
        lib = name.replace('\u221e', 'oo').replace('*', 's')
    preset = P.join(P.PRESETS_DIR, pset, '%s%s.json' % (ppre, lib))
    gjob = os.path.join(cat, *P.JOBS_DIR.split('/'), 'group_%s.json' % stem)
    if P.version_preset(name):
        preset = P.version_preset(name)
    elif os.path.exists(gjob):
        preset = P.from_url(json.load(open(gjob, encoding='utf-8'))['preset'])
    if not os.path.exists(os.path.join(cat, *preset.split('/'))):
        return dict(preset=None, shape='default', dirichlet=None, manifest=stem, stale=None)
    sym = json.load(open(os.path.join(cat, *preset.split('/')), encoding='utf-8'))['params']['symmetry']
    shape = sym['group']['params'].get('domainShape', 'default')
    dc = sym.get('dirichlet') or {}
    dirichlet = dc if dc.get('enabled') else None
    sh = '@' + shape.replace('*', 's').replace(' ', '-')
    tries = ([stem + sh + '@dirichlet', stem + '@dirichlet'] if dirichlet else []) + [stem + sh, stem]
    data = os.path.join(cat, *P.DATA_DIR.split('/'))
    mstem = next(t for t in tries if os.path.exists(os.path.join(data, t + '.json')))
    stale = None
    if dirichlet:
        md = json.load(open(os.path.join(data, mstem + '.json'), encoding='utf-8'))['group'].get('dirichlet')
        if not md:
            stale = 'no Dirichlet manifest: make_manifest.mjs --dirichlet %s' % preset
        elif [md['baseX'], md['baseY'], md['words']] != [dc['baseX'], dc['baseY'], dc['words']]:
            stale = 'data/%s.json was made for another Dirichlet domain' % mstem
    return dict(preset=preset, shape=shape, dirichlet=dirichlet, manifest=mstem, stale=stale)


def _safe_sym(s):
    return s.replace('\u221e', 'oo').replace('*', 's')


def piece_file(i, j, n):
    """Filename of partition piece f_i H g_j: '%d%d.png' for n <= 9, 'p%02d_%02d.png' for n >= 10."""
    return '%d%d.png' % (i, j) if n <= 9 else 'p%02d_%02d.png' % (i, j)


def union_file(j, n):
    """Filename of row-union image j: '012..._j.png' for n <= 9, 'u%d_%02d.png' for n >= 10."""
    return ('%s_%d.png' % (''.join(str(k) for k in range(n)), j)) if n <= 9 else ('u%d_%02d.png' % (n, j))


def entry_names(entry_name, n):
    gsym, rest = entry_name.split('/')
    hsym = rest.split('[')[0]
    k = rest.split('#')[1] if '#' in rest else None
    tail = ('-%s' % k) if k else ''
    slug = _safe_sym('%s-%s-%d%s' % (gsym, hsym, n, tail))
    job_file = slug.replace('-', '_')
    out_dir = '%s/%d/%s' % (_safe_sym(gsym), n, slug)
    return {'gsym': gsym, 'hsym': hsym, 'k': k, 'slug': slug,
            'job_file': job_file, 'dir': out_dir}
