# The catalog's index pages, generated from the manifests and family.json:
#
#   ../index.html               (main version) landing page: all families & versions
#   index.html                  the family's groups: uncolored thumbnail and counts
#   <stem>/index.html           one group: thumbnail, facts, live link, count sections
#   <stem>/<N>/index.html       the color groups of that group with N colors
#   colors/<N>/index.html       all groups in the family with N colors
#
#   python tools/make_index_pages.py
#
# Styles & behavior: css/catalog.css, js/theme.js, js/catalog.js.
import glob, html, io, json, os, re, subprocess, sys

import catalog_paths as P
CAT = P.CAT

if '--all-families' in sys.argv:
    for _fid in P.FAMILIES:
        _env = dict(os.environ, CATALOG_FAMILY=_fid)
        subprocess.run([sys.executable, os.path.abspath(__file__)], check=True, env=_env)
    sys.exit(0)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entry_names import entry_names, group_motif, MIN_N, MAX_N

FMETA = P.family_meta()
FAM_TITLE = FMETA.get('title', 'Wallpaper groups')
FAM_SHORT = FMETA.get('shortTitle', FAM_TITLE)
FAM_PLURAL = FMETA.get('groupPlural', 'wallpaper groups')
ALT_LABEL = FMETA.get('altNamesLabel', 'Hermann\u2013Mauguin')
HM = FMETA.get('altNames', {})
LIVE_APP = FMETA.get('liveApp', {})
LIVE_SYMDRAW = LIVE_APP.get('symdraw', '/apps/symdraw/symdraw_wp.html')
LIVE_LAYER = LIVE_APP.get('layer', 'drawing')
_cr = FMETA.get('colorRange') or [MIN_N, MAX_N]
LO_N, HI_N = int(_cr[0]), int(_cr[1])

PLANNED_FAMILIES = [
    ('frieze', 'Frieze groups', '7 groups', '1D translational strip symmetries and their finite-index colorings.', '\u27df'),
    ('spherical', 'Spherical groups', 'Point & polyhedral', 'Finite symmetry groups of the sphere and polyhedra with colorings.', '\u25ce'),
    ('hyperbolic', 'Hyperbolic groups', 'Triangle & orbifold', 'Colorings of hyperbolic KLM and orbifold groups in the Poincar\u00e9 disk.', '\u2734'),
]


def disp(name):
    """orbifold symbol for display: the cross is x in file names, a sign here"""
    return html.escape(name.replace('x', '\u00d7'))


def colors(n):
    return '1 color' if n == 1 else '%d colors' % n


def plural(k, word):
    return '%d %s%s' % (k, word, '' if k == 1 else 's')


def write(rel, text, site=False):
    import time
    path = P.path(rel if site else P.fam(rel))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp.%d' % os.getpid()
    for _attempt in range(5):
        try:
            with io.open(tmp, 'w', encoding='utf-8', newline='\n') as _f:
                _f.write(text)
            os.replace(tmp, path)
            return
        except OSError:
            if _attempt == 4:
                raise
            time.sleep(0.05 * (_attempt + 1))


def name_key(name):
    m = re.match(r'(.*)\[(\d+)\](?:#(\d+))?$', name)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0)) if m else (name, 0, 0)


def section_id(n):
    return 'c%d' % n


def count_run(label, has, up, cur=None, link_cur=False, here=False):
    def href(n):
        return '#' + section_id(n) if here else '%s%d/index.html' % (up, n)

    def one(n):
        if n == cur and link_cur:
            return '<a class="now" href="%s" title="%s">%d</a>' % (href(n), colors(n), n)
        if n == cur:
            return '<span class="now" title="%s">%d</span>' % (colors(n), n)
        if has(n):
            return '<a href="%s" title="%s">%d</a>' % (href(n), colors(n), n)
        return '<span class="off" title="none">%d</span>' % n
    return ('<span class="count-run">%s with %s colors</span>'
            % (label, ''.join(one(n) for n in range(LO_N, HI_N + 1))))


def topnav(crumbs, actions=()):
    """sticky top bar with breadcrumb trail + right-side actions + theme toggle"""
    c_parts = []
    for i, (href, label) in enumerate(crumbs):
        if i:
            c_parts.append('<span class="sep" aria-hidden="true">&rsaquo;</span>')
        if href:
            cls = ' class="brand"' if i == 0 else ''
            c_parts.append('<a%s href="%s">%s</a>' % (cls, href, label))
        else:
            c_parts.append('<span class="cur">%s</span>' % label)
    a_parts = list(actions) + ['<button type="button" class="btn sm" data-theme-toggle>&#9728; Light</button>']
    return (
        '<nav class="topnav" aria-label="Catalog navigation">\n'
        '<div class="wrap topnav__inner">\n'
        '  <div class="crumbs">%s</div>\n'
        '  <div class="topnav__actions">%s</div>\n'
        '</div>\n</nav>\n' % ('\n    '.join(c_parts), '\n    '.join(a_parts))
    )


def site_footer(left_html='', right_html=''):
    return (
        '<footer class="site-foot">\n<div class="wrap foot-row">\n'
        '  <div class="foot-links">%s</div>\n'
        '  <div class="foot-links">%s</div>\n'
        '</div>\n</footer>\n' % (left_html, right_html)
    )


def _site(root, css_root):
    return root + P.up(P.FAMILY_DIR) if css_root is None else css_root


def page(title, root, h1, lede, body, nav_html='', foot_html='', kind='', css_root=None, cat_rel=''):
    sroot = _site(root, css_root)
    img_asp = FMETA.get('imageAspect') if css_root is None else None
    img_asp_num = FMETA.get('imageAspectNum', 1) if css_root is None else 1
    body_style = (' style="--panel-aspect:%s;--panel-aspect-num:%s"' % (img_asp, img_asp_num)) if img_asp else ''
    return '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="symmhub-base" content="%s">
<meta name="catalog-root" content="%s">
<meta name="catalog-family" content="%s">
<meta name="catalog-version" content="%s">
<meta name="catalog-is-main" content="%s">
<meta name="catalog-rel" content="%s">
<title>%s</title>
<link rel="stylesheet" href="%scss/catalog.css">
<script src="%sjs/theme.js"></script>
</head>
<body%s>
%s<header class="top%s"><div class="wrap">
<h1>%s</h1>
<p class="lede">%s</p>%s
</div></header>
<main class="wrap">
%s
</main>
%s<script src="%sjs/catalog.js" defer></script>
</body>
</html>
''' % (html.escape(P.SYMMHUB_URL), html.escape(sroot), html.escape(P.FAMILY or 'wp'),
       html.escape(P.VERSION or ''), '1' if P.is_main() else '0',
       html.escape(cat_rel), html.escape(title), sroot, sroot, body_style,
       nav_html, (' ' + kind) if kind else '', h1, lede,
       ('\n' + P.version_note(sroot)) if P.version_note('') else '',
       body, foot_html, sroot)


# ---- collect ---------------------------------------------------------------

index = json.load(open(P.data_file('index'), encoding='utf-8'))
groups = {}
for g in index['groups']:
    name, stem = g['name'], g['stem']
    mo = group_motif(CAT, name, stem)
    if mo['stale']:
        print('WARNING %s: %s' % (name, mo['stale']))
    preset, shape = mo['preset'], mo['shape']
    man = P.data_file(mo['manifest'])
    m = json.load(open(man, encoding='utf-8'))
    trivial = next((s['cosets'] for s in m['subgroups'] if s['index'] == 1), '')
    subs = []
    for s in m['subgroups']:
        if not LO_N <= s['index'] <= HI_N:
            continue
        nm = entry_names(s['name'], s['index'])
        built = os.path.exists(P.path(P.fam(nm['dir']), 'index.html'))
        pats = []
        for k in range(1, s['placements'] + 1):
            img = '%s/gen/%s.%d.webp' % (nm['dir'], nm['slug'], k)
            pats.append(img if built and os.path.exists(P.path(P.fam(img)))
                        else None)
        subs.append(dict(s, dir=nm['dir'], slug=nm['slug'], built=built, pats=pats,
                         gname=name, ghm=HM.get(name, '')))
    thumb = '%s/gen/group.webp' % stem
    groups[name] = dict(name=name, stem=stem, preset=preset, shape=shape, dirichlet=mo['dirichlet'],
                        manifest=os.path.basename(man), trivial=trivial, subs=subs,
                        thumb=thumb if os.path.exists(P.path(P.fam(thumb))) else None,
                        per_n={n: sorted((s for s in subs if s['index'] == n),
                                         key=lambda s: (name_key(s.get('affineClass') or s['name']),
                                                        name_key(s['name'])))
                               for n in range(LO_N, HI_N + 1)})

# Group sections and display ordering from family.json (fallback to index order)
if FMETA.get('sections'):
    SECTIONS = [(sec['title'], [nm for nm in sec['groups'] if nm in groups]) for sec in FMETA['sections']]
else:
    SECTIONS = [(FAM_TITLE, [g['name'] for g in index['groups'] if g['name'] in groups])]
ORDER = [name for _, names in SECTIONS for name in names]
for g in index['groups']:
    if g['name'] not in ORDER:
        ORDER.append(g['name'])

EVERY = [s for g in groups.values() for s in g['subs']]


def ntypes(subs):
    return len(set(s.get('affineClass') or s['name'] for s in subs))


def npatterns(subs):
    return sum(s['placements'] for s in subs)


def all_n(n):
    return [s for nm in ORDER for s in groups[nm]['per_n'][n]]


def counts_line(subs, bold=False):
    b = (lambda k: '<b>%d</b>' % k) if bold else str
    return ' &middot; '.join('%s %s%s' % (b(k), word, '' if k == 1 else 's')
                             for k, word in ((ntypes(subs), 'type'),
                                             (len(subs), 'color group'),
                                             (npatterns(subs), 'pattern')))


def count_table(g, root):
    head = ['<th>colors</th>']
    for n in range(LO_N, HI_N + 1):
        if g['per_n'][n]:
            head.append('<th><a href="%s%s/%d/index.html" title="%s">%d</a></th>'
                        % (root, g['stem'], n, colors(n), n))
        else:
            head.append('<th class="zero" title="no color group with %s">%d</th>'
                        % (colors(n), n))
    rows = ['<tr>%s</tr>' % ''.join(head)]
    for label, count in (('types', ntypes), ('color groups', len), ('patterns', npatterns)):
        cells = [('<td>%d</td>' % count(g['per_n'][n])) if g['per_n'][n]
                 else '<td class="zero">&ndash;</td>' for n in range(LO_N, HI_N + 1)]
        rows.append('<tr><th>%s</th>%s</tr>' % (label, ''.join(cells)))
    return '<table class="counts">%s</table>' % ''.join(rows)


def status(subs):
    b = sum(s['built'] for s in subs)
    if b == len(subs):
        return '<span class="badge on">rendered</span>'
    if b:
        return '<span class="badge on">%d of %d rendered</span>' % (b, len(subs))
    return '<span class="badge">not rendered</span>'


def cg_filter_bar(placeholder='Filter by symbol, subgroup H, or HM name\u2026'):
    return (
        '<div class="filterbar" id="cg-filter">\n'
        '  <input type="search" id="cg-q" placeholder="%s" aria-label="Filter color groups">\n'
        '  <select id="cg-h" aria-label="Filter by subgroup H"><option value="">All subgroups H</option></select>\n'
        '  <select id="cg-k" aria-label="Filter by placements">'
        '<option value="">Any placements</option>'
        '<option value="1">1 placement (normal)</option>'
        '<option value="2+">2+ placements</option>'
        '<option value="3+">3+ placements</option>'
        '</select>\n'
        '  <label class="chk"><input type="checkbox" id="cg-norm"> Normal only</label>\n'
        '  <button type="button" class="btn sm" id="cg-clear" hidden>Reset</button>\n'
        '  <span class="fcount" id="cg-count"></span>\n'
        '</div>' % html.escape(placeholder)
    )


def cg_box(s, root):
    href = '%s%s/index.html' % (root, s['dir'])
    K = s['placements']
    pats = []
    for k, img in enumerate(s['pats'], 1):
        tip = '%s.%d: coloring by cosets, placement %d of %d' % (disp(s['name']), k, k, K)
        chip = '<span class="pk">{%d}</span>' % k if K > 1 else ''
        if img:
            pats.append('<a class="pat" href="%s" title="%s"><img src="%s%s" alt="%s.%d" '
                        'loading="lazy" decoding="async">%s</a>' % (href, tip, root, img, disp(s['name']), k, chip))
        else:
            pats.append('<div class="pat none" title="%s">not rendered%s</div>' % (tip, chip))
    title = '<a href="%s">%s</a>' % (href, disp(s['name'])) if s['built'] else disp(s['name'])
    badge = '<span class="badge on">normal</span>' if s['normal'] else ''
    search_tokens = ' '.join(filter(None, [
        s['name'], s['name'].replace('x', '\u00d7'), s.get('type', ''), s.get('gname', ''),
        s.get('ghm', ''), HM.get(s.get('type', ''), ''), 'normal' if s['normal'] else ''
    ]))
    return ('<div class="cg" style="--k:%d" data-name="%s" data-h="%s" data-k="%d" '
            'data-normal="%d" data-search="%s">\n<div class="pats">%s</div>\n<div class="body">\n'
            '<div class="name">%s%s</div>\n</div>\n</div>'
            % (K, html.escape(s['name']), html.escape(s.get('type', '')), K,
               1 if s['normal'] else 0, html.escape(search_tokens),
               ''.join(pats), title, (' ' + badge) if badge else ''))


def type_frames(ss, root):
    frames, cur = [], None
    for s in ss:
        ac = s.get('affineClass') or s['name']
        if cur is None or ac != cur:
            cur = ac
            frames.append((ac, []))
        frames[-1][1].append(cg_box(s, root))
    tip = 'one type: color groups an affine symmetry of the group carries onto each other'
    parts = []
    for ac, boxes in frames:
        lbl = ('<div class="tframe-lbl"><span>Affine type <b>%s</b> &middot; %d color groups</span></div>\n'
               % (disp(ac), len(boxes))) if len(boxes) > 1 else ''
        parts.append('<div class="tframe" title="%s">\n%s<div class="tframe-row">\n%s\n</div>\n</div>'
                     % (tip, lbl, '\n'.join(boxes)))
    return '<div class="pgrid typed">\n%s\n</div>' % '\n'.join(parts)


# ---- family index: wp/index.html ---------------------------------------------

def by_count_nav(root, cur=None):
    tiles = []
    for n in range(LO_N, HI_N + 1):
        ss = all_n(n)
        syms = sum(1 for nm in ORDER if groups[nm]['per_n'][n])
        tiles.append('<a class="ntile%s" href="%scolors/%d/index.html"><b>%s</b>'
                     '<span>%s</span><span>%s</span><span>%s</span>'
                     '<span class="in">in %s</span></a>'
                     % (' cur' if n == cur else '', root, n, colors(n),
                        plural(ntypes(ss), 'type'), plural(len(ss), 'color group'),
                        plural(npatterns(ss), 'pattern'),
                        '%d %s' % (syms, 'symmetry' if syms == 1 else 'symmetries')))
    return '<nav class="ntiles">%s</nav>' % ''.join(tiles)


def group_count_nav(g):
    tiles = []
    for n in range(LO_N, HI_N + 1):
        ss = g['per_n'][n]
        if not ss:
            tiles.append('<div class="off" title="no color group with %s"><b>%s</b>'
                         '<span>no color group</span></div>' % (colors(n), colors(n)))
            continue
        built = sum(s['built'] for s in ss)
        tiles.append('<a href="#%s"><b>%s</b><span>%s</span><span>%s</span><span>%s</span>'
                     '<span class="in">%s</span></a>'
                     % (section_id(n), colors(n), plural(ntypes(ss), 'type'),
                        plural(len(ss), 'color group'), plural(npatterns(ss), 'pattern'),
                        'rendered' if built == len(ss) else
                        '%d of %d rendered' % (built, len(ss)) if built else 'not rendered'))
    return '<nav class="ntiles">%s</nav>' % ''.join(tiles)


body = [
    '<h2 class="sec">Browse all symmetries by number of colors</h2>',
    by_count_nav(''),
    '<div class="filterbar">'
    '<input type="search" id="fam-search" placeholder="Filter groups by orbifold or %s symbol (e.g. 632, p4m, *333)\u2026" aria-label="Filter groups">'
    '<span class="fcount" id="fam-count"></span></div>' % html.escape(ALT_LABEL),
]
for sec_title, names in SECTIONS:
    cards = []
    for name in names:
        g = groups[name]
        link = '%s/index.html' % g['stem']
        hm = HM.get(name, '')
        img = ('<a class="thumb" href="%s"><img src="%s" alt="%s" loading="lazy" decoding="async"></a>'
               % (link, g['thumb'], disp(name)) if g['thumb'] else
               '<a class="thumb none" href="%s">no thumbnail</a>' % link)
        stxt = ' '.join(filter(None, [name, name.replace('x', '\u00d7'), hm, sec_title]))
        cards.append('''<div class="card" data-search="%s">
%s
<div class="body">
<div class="name"><a href="%s">%s</a>%s</div>
<div class="meta">%s %s</div>
%s
</div>
</div>''' % (html.escape(stxt), img, link, disp(name),
             ('<span class="hm">%s</span>' % html.escape(hm)) if hm else '',
             counts_line(g['subs'], bold=True),
             status(g['subs']), count_table(g, '')))
    body.append('<section class="fam-sec">\n<h2 class="sec cnt">%s</h2>\n<div class="grid">\n%s\n</div>\n</section>'
                % (html.escape(sec_title), '\n'.join(cards)))

fam_site = P.up(P.FAMILY_DIR)
write('index.html', page(
    '%s - Color Groups Catalog' % FAM_TITLE, '',
    'Color groups of the %s' % html.escape(FAM_PLURAL),
    'The %d %s and their color groups with %d to %d colors, counted three '
    'ways, each finer than the one before. <b>Types</b> (%d) merge the color groups '
    'that an affine symmetry of G carries onto each other: the classical count, %d with '
    '2 colors. <b>Color groups</b> G/H[n] (%d) are the subgroups H of index n up to '
    'conjugacy in G. <b>Patterns</b> (%d) are the colorings by cosets, one for each '
    'placement of H in G. %d color groups are rendered so far; a thumbnail shows the '
    'pattern of the group in one color.'
    % (len(groups), html.escape(FAM_PLURAL), LO_N, HI_N, ntypes(EVERY), ntypes(all_n(2)),
       len(EVERY), npatterns(EVERY), sum(s['built'] for s in EVERY)),
    '\n'.join(body),
    topnav([(fam_site + 'index.html', 'Catalog'), (None, html.escape(FAM_TITLE))],
           [count_run('All symmetries', all_n, 'colors/'),
            '<a class="btn sm" href="%s">Compare versions</a>' % P.compare_link(fam_site)]),
    site_footer(
        '<span>Generated by <code>tools/make_index_pages.py</code> from <code>%s/*.json</code>.</span>' % P.DATA_DIR,
        '<a href="%sindex.html">Catalog home</a>' % fam_site
    ), cat_rel=P.join(P.TREE, 'index.html')))


# ---- landing page: index.html (main version only) ----------------------------

def _versions_section():
    reg = P.registry()
    cards = []
    for v, meta in reg['versions'].items():
        vcfg = P.version_config(v) or {}
        vfam = meta.get('family') or vcfg.get('family') or P.DEFAULT_FAMILY
        if vfam not in P.FAMILIES:
            continue
        vmeta = P.family_meta(vfam) or {}
        hero_name = vmeta.get('heroGroup') or '*632'
        hero_stem = hero_name.replace('\u221e', 'oo').replace('*', 's')
        fdir = P.family_dir(v, f=vfam)
        fi = P.join(fdir, 'index.html')
        thumb_rel = P.join(fdir, hero_stem, 'gen', 'group.webp')
        has_page = os.path.exists(P.path(fi))
        has_thumb = os.path.exists(P.path(thumb_rel))
        n_built = len(glob.glob(os.path.join(P.path(fdir), '*', '*', '*', 'index.html')))
        fam_main = P.main_version(vfam)
        is_m = (v == fam_main)
        fbadge = '<span class="badge">%s</span>' % html.escape(vmeta.get('shortTitle', vfam))
        vbadge = '<span class="badge on">main</span>' if is_m else ''
        thumb_html = ('<img class="vthumb" src="%s" alt="%s" loading="lazy">' % (thumb_rel, html.escape(v))) if has_thumb else ''
        acts = []
        if has_page:
            acts.append('<a class="btn sm primary" href="%s">Browse</a>' % fi)
        fam_vers = [vn for vn, vm in reg['versions'].items()
                    if (vm.get('family') or (P.version_config(vn) or {}).get('family') or P.DEFAULT_FAMILY) == vfam]
        if not is_m and fam_main:
            acts.append('<a class="btn sm" href="compare.html?a=%s&amp;b=%s">Compare with %s</a>'
                        % (html.escape(fam_main), html.escape(v), html.escape(fam_main)))
        elif is_m and len(fam_vers) > 1:
            acts.append('<a class="btn sm" href="compare.html?a=%s&amp;b=%s">Compare versions</a>'
                        % (html.escape(fam_main), html.escape(next(x for x in fam_vers if x != fam_main))))
        cards.append(
            '<div class="ver-card">%s<div class="vbody">'
            '<div class="vname">%s %s %s</div>'
            '<div class="vlabel">%s%s</div>'
            '<div class="vacts">%s</div>'
            '</div></div>'
            % (thumb_html, html.escape(v), fbadge, vbadge,
               html.escape(meta.get('label', '')),
               (' &middot; %d pages' % n_built) if n_built else '',
               ''.join(acts))
        )
    if len(cards) < 2:
        return ''
    return (
        '\n<h2 class="sec">Catalog versions <span class="note">different preset sets and palettes, '
        'side by side &middot; <a href="%s">open compare tool</a></span></h2>\n'
        '<div class="ver-grid">\n%s\n</div>' % (P.compare_link(''), '\n'.join(cards))
    )


def _family_summary(fid):
    """Collect landing-page card info for any registered family in catalog_paths.json."""
    if fid == P.FAMILY:
        hg = groups.get(FMETA.get('heroGroup', '*632')) or next(iter(groups.values()))
        return dict(
            id=fid,
            dir=P.FAMILY_DIR + '/',
            title=FAM_TITLE,
            desc=FMETA.get('description', ''),
            ngroups=len(groups),
            subs=EVERY,
            thumb=(P.FAMILY_DIR + '/' + hg['thumb']) if hg.get('thumb') else None,
        )
    fc = P.family_cfg(fid)
    fm = P.family_meta(fid)
    idx_path = P.path(fc['dataDir'], 'index.json')
    if not os.path.exists(idx_path):
        return None
    fdir = P.family_dir(v=P.main_version(fid), f=fid)
    cr = fm.get('colorRange') or [MIN_N, MAX_N]
    lo, hi = int(cr[0]), int(cr[1])
    f_groups = json.load(open(idx_path, encoding='utf-8')).get('groups', [])
    f_subs = []
    hero_name = fm.get('heroGroup')
    hero_thumb = None
    for fg in f_groups:
        mpath = P.path(fc['dataDir'], fg['file'])
        if not os.path.exists(mpath):
            continue
        mf = json.load(open(mpath, encoding='utf-8'))
        for s in mf.get('subgroups', []):
            if lo <= s['index'] <= hi:
                nm = entry_names(s['name'], s['index'])
                built = os.path.exists(P.path(fdir, nm['dir'], 'index.html'))
                f_subs.append(dict(s, built=built))
        t_rel = P.join(fdir, fg['stem'], 'gen', 'group.webp')
        if os.path.exists(P.path(t_rel)) and (hero_thumb is None or fg['name'] == hero_name):
            hero_thumb = t_rel
    return dict(
        id=fid,
        dir=fdir + '/',
        title=fm.get('title', fid),
        desc=fm.get('description', ''),
        ngroups=len(f_groups),
        subs=f_subs,
        thumb=hero_thumb,
    )


if P.is_main():
    fam_cards = []
    nav_fam_links = []
    for fid in P.FAMILIES:
        fs = _family_summary(fid)
        if not fs:
            continue
        nav_fam_links.append('<a class="btn sm" href="%sindex.html">%s</a>'
                             % (fs['dir'], html.escape(fs['title'])))
        thumb_html = ('<a class="thumb" href="%sindex.html"><img src="%s" alt="%s" loading="lazy"></a>'
                      % (fs['dir'], fs['thumb'], html.escape(fs['title']))) if fs['thumb'] else \
                     '<a class="thumb none" href="%sindex.html">no thumbnail</a>' % fs['dir']
        fam_cards.append('''<div class="card">
%s
<div class="body">
<div class="name"><a href="%sindex.html">%s</a><span class="hm">%d groups</span></div>
<p class="desc">%s</p>
<div class="meta">%s %s</div>
</div>
</div>''' % (thumb_html, fs['dir'], html.escape(fs['title']), fs['ngroups'],
             html.escape(fs['desc']), counts_line(fs['subs'], bold=True), status(fs['subs'])))

    for fid, ftitle, fsub, fdesc, fsym in PLANNED_FAMILIES:
        if fid in P.FAMILIES:
            continue
        fam_cards.append(
            '<div class="card planned">'
            '<div class="thumb planned-art" aria-hidden="true">%s</div>'
            '<div class="body">'
            '<div class="name">%s<span class="hm">%s</span></div>'
            '<p class="desc">%s</p>'
            '<div class="meta"><span class="badge">planned</span></div>'
            '</div></div>' % (fsym, html.escape(ftitle), html.escape(fsub), html.escape(fdesc))
        )
    write('index.html', page(
        'Color Groups Catalog', '',
        'Color groups catalog',
        'Color groups of symmetry groups, family by family. For a group G and a subgroup H '
        'of finite index n, G&rsquo;s pattern is colored with n colors by the cosets of H '
        '&mdash; once for each placement of H in G &mdash; and by its orbits.',
        '<h2 class="sec">Symmetry families</h2>\n<div class="grid families">\n%s\n</div>%s'
        % ('\n'.join(fam_cards), _versions_section()),
        topnav([(None, 'Catalog')],
               nav_fam_links + ['<a class="btn sm" href="compare.html">Compare versions</a>']),
        site_footer(
            '<span>Generated by <code>tools/make_index_pages.py</code> across %d registered %s.</span>'
            % (len(P.FAMILIES), 'family' if len(P.FAMILIES) == 1 else 'families'),
            '<a href="compare.html">Compare versions</a>'
        ),
        css_root=''), site=True)


# ---- group pages: <stem>/index.html -----------------------------------------

for name, g in groups.items():
    root = '../'
    sroot = _site(root, None)
    hm = HM.get(name, '')
    live_payload = json.dumps({
        'app': LIVE_SYMDRAW,
        'layer': LIVE_LAYER,
        'preset': g['preset'],
        'siteRoot': sroot,
        'name': name,
        'trivial': g['trivial'],
    }, ensure_ascii=False).replace('</', '<\\/')
    hero_img = ('<img src="gen/group.webp" alt="%s">' % disp(name)) if g['thumb'] else ''
    hero = (
        '<div class="hero-media">%s'
        '<div class="hero-live">'
        '<a class="btn sm primary" target="_blank" rel="noopener" data-live-group="simple" href="#">Explore in SymmHub &#8599;</a>'
        '<a class="btn sm" target="_blank" rel="noopener" data-live-group="studio" href="#">Studio &#8599;</a>'
        '</div></div>' % hero_img
    )
    hm_row = ('<dt>%s</dt><dd>%s</dd>\n' % (html.escape(ALT_LABEL), html.escape(hm))) if hm else ''
    facts = '''<dl class="facts">
<dt>Orbifold</dt><dd>%s</dd>
%s<dt>%d&ndash;%d colors</dt><dd>%s %s</dd>
<dt>Per count</dt><dd class="tbl">%s</dd>
<dt>Motif</dt><dd><code>%s</code></dd>
<dt>Domain</dt><dd>%s</dd>
<dt>Manifest</dt><dd><code>%s/%s</code></dd>
</dl>''' % (disp(name), hm_row, LO_N, HI_N, counts_line(g['subs']), status(g['subs']),
            count_table(g, root), html.escape(g['preset']),
            ('default' if g['shape'] == 'default' else html.escape(g['shape'])) +
            (' &middot; Dirichlet domain about (%g, %g)' % (g['dirichlet']['baseX'], g['dirichlet']['baseY'])
             if g['dirichlet'] else ''), P.DATA_DIR, html.escape(g['manifest']))

    secs = []
    for n in range(LO_N, HI_N + 1):
        ss = g['per_n'][n]
        if not ss:
            secs.append('<section class="cg-sec"><h2 class="sec cnt none" id="%s">%s '
                        '<span class="note">none</span></h2></section>'
                        % (section_id(n), colors(n)))
            continue
        secs.append('<section class="cg-sec"><h2 class="sec cnt" id="%s"><a href="%d/index.html">%s</a> '
                    '<span class="note">%s &middot; <a href="%d/index.html">on its own page</a></span></h2>\n%s\n</section>'
                    % (section_id(n), n, colors(n), counts_line(ss), n, type_frames(ss, root)))
    body = ('<div class="hero">%s<div>%s</div></div>\n'
            '<h2 class="sec">By number of colors<span class="note">a section each, '
            'below</span></h2>\n%s\n%s\n%s\n'
            '<script type="application/json" id="group-live-data">%s</script>'
            % (hero, facts, group_count_nav(g),
               cg_filter_bar('Filter color groups of %s by subgroup H or name\u2026' % name),
               '\n'.join(secs), live_payload))
    write('%s/index.html' % g['stem'], page(
        '%s - Color Groups Catalog' % name, root,
        '%s%s' % (disp(name), (' <span class="sub">%s</span>' % html.escape(hm)) if hm else ''),
        'The color groups of %s with %d to %d colors and the patterns they give, by '
        'number of colors. A frame holds the color groups of one type.'
        % (disp(name), LO_N, HI_N), body,
        topnav([(sroot + 'index.html', 'Catalog'),
                ('../index.html', html.escape(FAM_SHORT)),
                (None, disp(name))],
               [count_run('<b>%s</b>' % disp(name), lambda n: g['per_n'][n], '', here=True)]),
        site_footer(
            count_run('All symmetries', all_n, '../colors/'),
            '<a href="%s">Compare versions</a>' % P.compare_link(sroot)
        ),
        kind='group', cat_rel=P.join(P.TREE, g['stem'], 'index.html')))


# ---- count pages of one group: <stem>/<N>/index.html -------------------------

for name, g in groups.items():
    for n in range(LO_N, HI_N + 1):
        ss = g['per_n'][n]
        if not ss:
            continue
        root = '../../'
        sroot = _site(root, None)
        pager = []
        for k in range(LO_N, HI_N + 1):
            if k == n:
                pager.append('<span class="cur">%d</span>' % k)
            elif g['per_n'][k]:
                pager.append('<a href="../%d/index.html" title="%s">%d</a>' % (k, colors(k), k))
            else:
                pager.append('<span class="off" title="none">%d</span>' % k)
        pager.append('<a href="../../colors/%d/index.html">all symmetries with %s</a>'
                     % (n, colors(n)))
        body = ('<nav class="pager">%s</nav>\n%s\n'
                '<h2 class="sec">%s<span class="note">a picture per pattern; '
                'a frame holds the color groups of one type</span></h2>\n%s'
                % (''.join(pager),
                   cg_filter_bar('Filter %s color groups with %s\u2026' % (name, colors(n))),
                   counts_line(ss), type_frames(ss, root)))
        write('%s/%d/index.html' % (g['stem'], n), page(
            '%s, %s - Color Groups Catalog' % (name, colors(n)), root,
            '%s <span class="sub">with %s</span>' % (disp(name), colors(n)),
            'The color groups G/H[%d] of %s, H a subgroup of index %d, and their patterns: '
            'each placement of H in G colors the pattern by cosets in its own way.'
            % (n, disp(name), n), body,
            topnav([(sroot + 'index.html', 'Catalog'),
                    ('../../index.html', html.escape(FAM_SHORT)),
                    ('../index.html', disp(name)),
                    (None, colors(n))],
                   [count_run('<b>%s</b>' % disp(name), lambda k: g['per_n'][k], '../', cur=n)]),
            site_footer(
                count_run('All symmetries', all_n, '../../colors/', cur=n, link_cur=True),
                '<a href="%s">Compare versions</a>' % P.compare_link(sroot)
            ), cat_rel=P.join(P.TREE, g['stem'], str(n), 'index.html')))


# ---- count pages across all groups: colors/<N>/index.html ------------------

for n in range(LO_N, HI_N + 1):
    root = '../../'
    sroot = _site(root, None)
    jumps = []
    secs = []
    for name in ORDER:
        g = groups[name]
        ss = g['per_n'][n]
        hm = HM.get(name, '')
        if ss:
            jumps.append('<a href="#%s" title="%s (%s): %d color groups">%s</a>'
                         % (g['stem'], html.escape(name), html.escape(hm), len(ss), disp(name)))
        else:
            jumps.append('<span class="off" title="%s: none with %s">%s</span>'
                         % (html.escape(name), colors(n), disp(name)))
        head = ('<h2 class="sec cnt%s" id="%s"><a href="%s%s/index.html">%s</a> <span class="note">%s'
                % ('' if ss else ' none', g['stem'], root, g['stem'], disp(name),
                   (html.escape(hm) + ' &middot; ') if hm else ''))
        if not ss:
            secs.append('<section class="cg-sec">' + head + 'none</span></h2></section>')
            continue
        secs.append('<section class="cg-sec">' + head + '%s &middot; <a href="%s%s/%d/index.html">on its own '
                    'page</a></span></h2>\n%s\n</section>'
                    % (counts_line(ss), root, g['stem'], n, type_frames(ss, root)))
    ss = all_n(n)
    jump_nav = '<nav class="jump-chips" aria-label="Jump to symmetry group">%s</nav>' % ''.join(jumps)
    write('colors/%d/index.html' % n, page(
        'All groups, %s - Color Groups Catalog' % colors(n), root,
        'All symmetries <span class="sub">with %s</span>' % colors(n),
        '%s across the %d %s, with a picture of every pattern: one for each '
        'placement of H in G.' % (counts_line(ss), len(groups), html.escape(FAM_PLURAL)),
        by_count_nav(root, n) + '\n' + jump_nav + '\n'
        + cg_filter_bar('Filter all %s color groups (e.g. p6m, 333, normal)\u2026' % colors(n))
        + '\n' + '\n'.join(secs),
        topnav([(sroot + 'index.html', 'Catalog'),
                ('../../index.html', html.escape(FAM_SHORT)),
                (None, colors(n))],
               [count_run('All symmetries', all_n, '../', cur=n)]),
        site_footer(
            '<span>%s</span>' % counts_line(ss),
            '<a href="%s">Compare versions</a>' % P.compare_link(sroot)
        ), cat_rel=P.join(P.TREE, 'colors', str(n), 'index.html')))

# ---- global quick-jump search index (search_index.json) ---------------------
_sitems = []
for name in ORDER:
    g = groups[name]
    hm = HM.get(name, '')
    _sitems.append({
        'k': 'g', 'f': P.FAMILY, 'n': name, 'hm': hm,
        'info': plural(len(g['subs']), 'color group'),
        'u': P.fam(g['stem'], 'index.html'),
    })
    for n in range(LO_N, HI_N + 1):
        for s in g['per_n'][n]:
            if not s['built']:
                continue
            _sitems.append({
                'k': 'e', 'f': P.FAMILY, 'n': s['name'], 'hm': hm,
                'h': s['type'], 'c': s['index'], 'p': s['placements'],
                'norm': 1 if s['normal'] else 0,
                'u': P.fam(s['dir'], 'index.html'),
            })
_s_rel = P.join(P.version_root(), 'search_index.json')
_merged_items = _sitems
if P.is_main() and os.path.exists(P.path(_s_rel)):
    try:
        _prev = json.load(open(P.path(_s_rel), encoding='utf-8')).get('items', [])
        _other = [it for it in _prev if it.get('f') != P.FAMILY]
        _fam_order = {fid: i for i, fid in enumerate(P.FAMILIES)}
        _merged_items = sorted(_other + _sitems, key=lambda it: _fam_order.get(it.get('f'), 99))
    except Exception:
        pass
write(_s_rel, json.dumps({'version': P.VERSION, 'items': _merged_items}, separators=(',', ':'), ensure_ascii=False), site=True)

print('%d groups: %d types, %d color groups, %d patterns (%d color groups rendered); '
      'wrote index.html, %d group pages, %d count pages, %d all-symmetries pages'
      % (len(groups), ntypes(EVERY), len(EVERY), npatterns(EVERY),
         sum(s['built'] for s in EVERY), len(groups),
         sum(1 for g in groups.values() for n in g['per_n'] if g['per_n'][n]), HI_N - LO_N + 1))
