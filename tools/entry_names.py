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


def group_motif(cat, name, stem):
    """The motif a group renders and the manifest its entries are built from.
    The preset is the one its thumbnail job renders (jobs/group_<stem>.json; a
    group can be tried on another preset), else presets/wpe/wpe-<name>.json.  The
    manifest follows that preset's domain: data/<stem>@<shape>.json for another
    domain shape, <stem>@...@dirichlet.json when it turns on a Dirichlet domain
    (make_manifest.mjs --domain / --dirichlet), whichever exists, else
    data/<stem>.json.  'stale': what is wrong with the manifest for this preset
    (a Dirichlet domain without its manifest, or one of another base or words),
    else None."""
    import json, os
    lib = 'O' if name == 'o' else name.replace('x', 'X')
    preset = 'presets/wpe/wpe-%s.json' % lib.replace('*', 's')
    gjob = os.path.join(cat, 'jobs', 'group_%s.json' % stem)
    if os.path.exists(gjob):
        preset = json.load(open(gjob, encoding='utf-8'))['preset'].replace('/catalog/', '', 1)
    sym = json.load(open(os.path.join(cat, *preset.split('/')), encoding='utf-8'))['params']['symmetry']
    shape = sym['group']['params'].get('domainShape', 'default')
    dc = sym.get('dirichlet') or {}
    dirichlet = dc if dc.get('enabled') else None
    sh = '@' + shape.replace('*', 's').replace(' ', '-')
    tries = ([stem + sh + '@dirichlet', stem + '@dirichlet'] if dirichlet else []) + [stem + sh, stem]
    mstem = next(t for t in tries if os.path.exists(os.path.join(cat, 'data', t + '.json')))
    stale = None
    if dirichlet:
        md = json.load(open(os.path.join(cat, 'data', mstem + '.json'), encoding='utf-8'))['group'].get('dirichlet')
        if not md:
            stale = 'no Dirichlet manifest: make_manifest.mjs --dirichlet %s' % preset
        elif [md['baseX'], md['baseY'], md['words']] != [dc['baseX'], dc['baseY'], dc['words']]:
            stale = 'data/%s.json was made for another Dirichlet domain' % mstem
    return dict(preset=preset, shape=shape, dirichlet=dirichlet, manifest=mstem, stale=stale)


def entry_names(entry_name, n):
    gsym, rest = entry_name.split('/')
    hsym = rest.split('[')[0]
    k = rest.split('#')[1] if '#' in rest else None
    tail = ('-%s' % k) if k else ''
    slug = ('%s-%s-%d%s' % (gsym, hsym, n, tail)).replace('*', 's')
    job_file = slug.replace('-', '_')
    out_dir = '%s/%d/%s' % (gsym.replace('*', 's'), n, slug)
    return {'gsym': gsym, 'hsym': hsym, 'k': k, 'slug': slug,
            'job_file': job_file, 'dir': out_dir}
