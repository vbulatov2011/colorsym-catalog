# The catalog's index pages, generated from the manifests:
#
#   index.html                  the 17 wallpaper groups: uncolored thumbnail and
#                               the counts for 1..6 colors
#   <stem>/index.html           one group: thumbnail, facts, a section per color
#                               count with a picture of every pattern
#   <stem>/<N>/index.html       the color groups of that group with N colors, each
#                               with a picture of every pattern it gives
#   colors/<N>/index.html       the same for all 17 groups on one page
#
#   python tools/make_index_pages.py
#
# Three counts, each refining the one before:
#   types         classes of color groups under the affine normalizer of G
#                 (affineClass, from tools/affine_classes.mjs): the classical
#                 count, 46 with 2 colors
#   color groups  the manifest entries G/H[n]#k: subgroups H up to conjugacy in G
#   patterns      the colorings by cosets, one per placement of H in G - the
#                 entry's .1 ... .K images, K distinct colorings of the same
#                 uncolored pattern.  The coloring by orbits (.o) is the same
#                 pattern for every placement and is not counted.
#
# Pictures: <stem>/gen/group.webp (tools/make_group_jobs.py) for a group, the
# entry's <slug>.<k>.webp for placement k.  A color group whose entry has not
# been built is listed with placeholders and without a link.
# Styles: css/catalog.css.
import json, io, os, html, re, sys

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_N = 6

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entry_names import entry_names

# Hermann-Mauguin names, and families by the highest rotation order
HM = {'o': 'p1', '2222': 'p2', '**': 'pm', 'xx': 'pg', '*x': 'cm', '*2222': 'pmm',
      '22*': 'pmg', '22x': 'pgg', '2*22': 'cmm', '442': 'p4', '*442': 'p4m',
      '4*2': 'p4g', '333': 'p3', '*333': 'p3m1', '3*3': 'p31m', '632': 'p6',
      '*632': 'p6m'}
FAMILIES = [
    ('No rotations', ['o', 'xx', '**', '*x']),
    ('Half turns', ['2222', '22x', '22*', '*2222', '2*22']),
    ('Third turns', ['333', '3*3', '*333']),
    ('Quarter turns', ['442', '4*2', '*442']),
    ('Sixth turns', ['632', '*632']),
]
ORDER = [name for fam, names in FAMILIES for name in names]


def disp(name):
    """orbifold symbol for display: the cross is x in file names, a sign here"""
    return html.escape(name.replace('x', '×'))


def colors(n):
    return '1 color' if n == 1 else '%d colors' % n


def plural(k, word):
    return '%d %s%s' % (k, word, '' if k == 1 else 's')


def write(rel, text):
    path = os.path.join(CAT, *rel.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(text)


def name_key(name):
    """sort key of a color group name G/H[n]#k: the ordinal k as a number, so
    #2 comes before #10; G/H stays a string (orbifold symbols are no numbers)"""
    m = re.match(r'(.*)\[(\d+)\](?:#(\d+))?$', name)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 0)) if m else (name, 0, 0)


def section_id(n):
    """the anchor of a count's section on a group page"""
    return 'c%d' % n


def count_run(label, has, up, cur=None, link_cur=False, here=False):
    """the bar's run of count links, '632 with 1 2 3 4 6 colors' or 'All
    symmetries with 1 2 3 4 5 6 colors': a count n with no color group
    (has(n) false) is dashed, the page's own count dark; up = the path from
    the page to the folder of the count pages.  link_cur: the dark count is
    still a link - the run leads to other pages with the same count (a
    group's count page to the all-symmetries page).  here: the counts are
    sections of this page (a group page) instead of pages"""
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
    return ('<span class="grp">%s with %s colors</span>'
            % (label, ''.join(one(n) for n in range(1, MAX_N + 1))))


def bar(items):
    """the bar's links: (href, label) pairs, href None for the page itself;
    a plain string is put in as it is"""
    links = ''.join('\n ' + it if isinstance(it, str) else
                    '\n <a href="%s">%s</a>' % it if it[0] else
                    '\n <span class="cur">%s</span>' % it[1] for it in items)
    return ('<footer class="bar">\n<div class="wrap">\n<nav class="up">%s\n</nav>\n'
            '</div>\n</footer>\n' % links)


def page(title, root, crumbs, h1, lede, body, foot=''):
    nav = ''
    if crumbs:
        parts = ['<a href="%s">%s</a>' % (href, text) for href, text in crumbs[:-1]]
        parts.append('<span>%s</span>' % crumbs[-1][1])
        nav = '<nav class="crumbs">%s</nav>\n' % '<span class="sep">/</span>'.join(parts)
    return '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<link rel="stylesheet" href="%scss/catalog.css">
</head>
<body%s>
<header class="top"><div class="wrap">
%s<h1>%s</h1>
<p class="lede">%s</p>
</div></header>
<main class="wrap">
%s
<footer>Generated by <code>tools/make_index_pages.py</code> from <code>data/*.json</code>.</footer>
</main>
%s</body>
</html>
''' % (html.escape(title), root, ' class="with-bar"' if foot else '', nav, h1, lede, body, foot)


# ---- collect ---------------------------------------------------------------

index = json.load(open(os.path.join(CAT, 'data', 'index.json'), encoding='utf-8'))
groups = {}
for g in index['groups']:
    name, stem = g['name'], g['stem']
    lib = 'O' if name == 'o' else name.replace('x', 'X')
    preset = 'wp-%s.json' % lib.replace('*', 's')
    doc = json.load(open(os.path.join(CAT, 'presets', 'wp', preset), encoding='utf-8'))
    shape = doc['params']['symmetry']['group']['params'].get('domainShape', 'default')
    variant = os.path.join(CAT, 'data', '%s@%s.json' % (stem, shape.replace(' ', '-')))
    man = variant if os.path.exists(variant) else os.path.join(CAT, 'data', stem + '.json')
    m = json.load(open(man, encoding='utf-8'))
    subs = []
    for s in m['subgroups']:
        if s['index'] > MAX_N:
            continue
        nm = entry_names(s['name'], s['index'])
        built = os.path.exists(os.path.join(CAT, *nm['dir'].split('/'), 'index.html'))
        pats = []                          # placement k -> its coloring by cosets
        for k in range(1, s['placements'] + 1):
            img = '%s/gen/%s.%d.webp' % (nm['dir'], nm['slug'], k)
            pats.append(img if built and os.path.exists(os.path.join(CAT, *img.split('/')))
                        else None)
        subs.append(dict(s, dir=nm['dir'], slug=nm['slug'], built=built, pats=pats))
    thumb = '%s/gen/group.webp' % stem
    groups[name] = dict(name=name, stem=stem, preset=preset, shape=shape,
                        manifest=os.path.basename(man), subs=subs,
                        thumb=thumb if os.path.exists(os.path.join(CAT, thumb)) else None,
                        # color groups of one type side by side, #2 before #10
                        per_n={n: sorted((s for s in subs if s['index'] == n),
                                         key=lambda s: (name_key(s['affineClass']),
                                                        name_key(s['name'])))
                               for n in range(1, MAX_N + 1)})

EVERY = [s for g in groups.values() for s in g['subs']]
CLASS_SIZE = {}
for s in EVERY:
    CLASS_SIZE[s['affineClass']] = CLASS_SIZE.get(s['affineClass'], 0) + 1


def ntypes(subs):
    return len(set(s['affineClass'] for s in subs))


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
    """types / color groups / patterns for 1..MAX_N colors; a column head links
    to that count's page"""
    head = ['<th>colors</th>']
    for n in range(1, MAX_N + 1):
        if g['per_n'][n]:
            head.append('<th><a href="%s%s/%d/index.html" title="%s">%d</a></th>'
                        % (root, g['stem'], n, colors(n), n))
        else:
            head.append('<th class="zero" title="no color group with %s">%d</th>'
                        % (colors(n), n))
    rows = ['<tr>%s</tr>' % ''.join(head)]
    for label, count in (('types', ntypes), ('color groups', len), ('patterns', npatterns)):
        cells = [('<td>%d</td>' % count(g['per_n'][n])) if g['per_n'][n]
                 else '<td class="zero">–</td>' for n in range(1, MAX_N + 1)]
        rows.append('<tr><th>%s</th>%s</tr>' % (label, ''.join(cells)))
    return '<table class="counts">%s</table>' % ''.join(rows)


def status(subs):
    b = sum(s['built'] for s in subs)
    if b == len(subs):
        return '<span class="badge on">rendered</span>'
    if b:
        return '<span class="badge on">%d of %d rendered</span>' % (b, len(subs))
    return '<span class="badge">not rendered</span>'


def type_line(s):
    size = CLASS_SIZE[s['affineClass']]
    if size == 1:
        return 'a type of its own'
    if s['affineClass'] == s['name']:
        return 'type of %d color groups' % size
    return 'same type as %s' % disp(s['affineClass'])


def cg_box(s, root):
    """a color group with a picture of each of its patterns, one per placement;
    paths relative to the catalog root.  A pattern's chip reads {k} for
    placement k (the tooltip spells it out)"""
    href = '%s%s/index.html' % (root, s['dir'])
    K = s['placements']
    pats = []
    for k, img in enumerate(s['pats'], 1):
        tip = '%s.%d: coloring by cosets, placement %d of %d' % (disp(s['name']), k, k, K)
        chip = '<span class="pk">{%d}</span>' % k if K > 1 else ''
        if img:
            pats.append('<a class="pat" href="%s" title="%s"><img src="%s%s" alt="%s.%d" '
                        'loading="lazy">%s</a>' % (href, tip, root, img, disp(s['name']), k, chip))
        else:
            pats.append('<div class="pat none" title="%s">not rendered%s</div>' % (tip, chip))
    title = '<a href="%s">%s</a>' % (href, disp(s['name'])) if s['built'] else disp(s['name'])
    badge = ('<span class="badge">the uncolored group</span>' if s['index'] == 1 else
             '<span class="badge on">normal</span>' if s['normal'] else '')
    return ('<div class="cg" style="--k:%d">\n<div class="pats">%s</div>\n<div class="body">\n'
            '<div class="name">%s</div>\n'
            '<div class="meta">H = %s &middot; %s</div>\n'
            '<div class="meta">%s</div>\n<div>%s</div>\n</div>\n</div>'
            % (K, ''.join(pats), title, disp(s['type']), plural(K, 'placement'),
               type_line(s), badge))


# ---- top page ----------------------------------------------------------------

def by_count_nav(root, cur=None):
    """the six 'all symmetries with N colors' pages, one tile each"""
    tiles = []
    for n in range(1, MAX_N + 1):
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
    """a group page's six counts, one tile each, as by_count_nav: a jump to
    that count's section of the page"""
    tiles = []
    for n in range(1, MAX_N + 1):
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


body = ['<h2 class="sec">By number of colors<span class="note">every symmetry '
        'on one page</span></h2>\n' + by_count_nav('')]
for fam, names in FAMILIES:
    cards = []
    for name in names:
        g = groups[name]
        link = '%s/index.html' % g['stem']
        img = ('<a class="thumb" href="%s"><img src="%s" alt="%s" loading="lazy"></a>'
               % (link, g['thumb'], disp(name)) if g['thumb'] else
               '<a class="thumb none" href="%s">no thumbnail</a>' % link)
        cards.append('''<div class="card">
%s
<div class="body">
<div class="name"><a href="%s">%s</a><span class="hm">%s</span></div>
<div class="meta">%s %s</div>
%s
</div>
</div>''' % (img, link, disp(name), HM[name], counts_line(g['subs'], bold=True),
             status(g['subs']), count_table(g, '')))
    body.append('<h2 class="sec">%s</h2>\n<div class="grid">\n%s\n</div>' % (fam, '\n'.join(cards)))

write('index.html', page(
    'Color Groups Catalog', '', None,
    'Color groups of the wallpaper groups',
    'The 17 wallpaper groups and their color groups with 1 to %d colors, counted three '
    'ways, each finer than the one before. <b>Types</b> (%d) merge the color groups '
    'that an affine symmetry of G carries onto each other: the classical count, 46 with '
    '2 colors. <b>Color groups</b> G/H[n] (%d) are the subgroups H of index n up to '
    'conjugacy in G. <b>Patterns</b> (%d) are the colorings by cosets, one for each '
    'placement of H in G. %d color groups are rendered so far; a thumbnail shows the '
    'uncolored pattern.'
    % (MAX_N, ntypes(EVERY), len(EVERY), npatterns(EVERY), sum(s['built'] for s in EVERY)),
    '\n'.join(body)))


# ---- group pages -------------------------------------------------------------

for name, g in groups.items():
    root = '../'
    crumbs = [('../index.html', 'Catalog'), (None, disp(name))]
    hero = ('<img src="gen/group.webp" alt="%s">' % disp(name)) if g['thumb'] else ''
    facts = '''<dl class="facts">
<dt>Orbifold</dt><dd>%s</dd>
<dt>Hermann&ndash;Mauguin</dt><dd>%s</dd>
<dt>1&ndash;%d colors</dt><dd>%s %s</dd>
<dt>Per count</dt><dd class="tbl">%s</dd>
<dt>Motif</dt><dd><code>presets/wp/%s</code></dd>
<dt>Domain</dt><dd>%s</dd>
<dt>Manifest</dt><dd><code>data/%s</code></dd>
</dl>''' % (disp(name), HM[name], MAX_N, counts_line(g['subs']), status(g['subs']),
            count_table(g, root), g['preset'],
            'default' if g['shape'] == 'default' else html.escape(g['shape']), g['manifest'])
    # a section per count, its color groups as on the count pages: a full-size
    # picture of every pattern; the tiles and the bar jump to the sections
    secs = []
    for n in range(1, MAX_N + 1):
        ss = g['per_n'][n]
        if not ss:
            secs.append('<h2 class="sec" id="%s">%s <span class="note">none</span></h2>'
                        % (section_id(n), colors(n)))
            continue
        secs.append('<h2 class="sec" id="%s"><a href="%d/index.html">%s</a> <span class="note">%s '
                    '&middot; <a href="%d/index.html">on its own page</a></span></h2>\n'
                    '<div class="pgrid">\n%s\n</div>'
                    % (section_id(n), n, colors(n), counts_line(ss), n,
                       '\n'.join(cg_box(s, root) for s in ss)))
    body = ('<div class="hero">%s<div>%s</div></div>\n'
            '<h2 class="sec">By number of colors<span class="note">a section each, '
            'below</span></h2>\n%s\n%s'
            % (hero, facts, group_count_nav(g), '\n'.join(secs)))
    write('%s/index.html' % g['stem'], page(
        '%s - Color Groups Catalog' % name, root, crumbs,
        '%s <span class="sub">%s</span>' % (disp(name), HM[name]),
        'The color groups of %s with 1 to %d colors and the patterns they give, by '
        'number of colors.' % (disp(name), MAX_N), body,
        bar([('../index.html', 'Catalog'),
             (None, 'All color groups of <b>%s</b>' % disp(name)),
             count_run('<b>%s</b>' % disp(name), lambda n: g['per_n'][n], '', here=True),
             count_run('All symmetries', all_n, '../colors/')])))


# ---- count pages of one group: <stem>/<N>/index.html -------------------------

for name, g in groups.items():
    for n in range(1, MAX_N + 1):
        ss = g['per_n'][n]
        if not ss:
            continue
        root = '../../'
        crumbs = [('../../index.html', 'Catalog'), ('../index.html', disp(name)),
                  (None, colors(n))]
        pager = []
        for k in range(1, MAX_N + 1):
            if k == n:
                pager.append('<span class="cur">%d</span>' % k)
            elif g['per_n'][k]:
                pager.append('<a href="../%d/index.html" title="%s">%d</a>' % (k, colors(k), k))
            else:
                pager.append('<span class="off" title="none">%d</span>' % k)
        pager.append('<a href="../../colors/%d/index.html">all symmetries with %s</a>'
                     % (n, colors(n)))
        body = ('<nav class="pager">%s</nav>\n<h2 class="sec">%s<span class="note">a '
                'picture per pattern; color groups of one type side by side</span></h2>\n'
                '<div class="pgrid">\n%s\n</div>'
                % (''.join(pager), counts_line(ss), '\n'.join(cg_box(s, root) for s in ss)))
        write('%s/%d/index.html' % (g['stem'], n), page(
            '%s, %s - Color Groups Catalog' % (name, colors(n)), root, crumbs,
            '%s <span class="sub">with %s</span>' % (disp(name), colors(n)),
            'The color groups G/H[%d] of %s, H a subgroup of index %d, and their patterns: '
            'each placement of H in G colors the pattern by cosets in its own way.'
            % (n, disp(name), n), body,
            bar([('../../index.html', 'Catalog'),
                 ('../index.html', 'All color groups of <b>%s</b>' % disp(name)),
                 count_run('<b>%s</b>' % disp(name), lambda k: g['per_n'][k], '../', cur=n),
                 count_run('All symmetries', all_n, '../../colors/', cur=n, link_cur=True)])))


# ---- count pages across all groups: colors/<N>/index.html ------------------

for n in range(1, MAX_N + 1):
    root = '../../'
    secs = []
    for name in ORDER:
        g = groups[name]
        ss = g['per_n'][n]
        head = ('<h2 class="sec"><a href="%s%s/index.html">%s</a> <span class="note">%s'
                % (root, g['stem'], disp(name), HM[name]))
        if not ss:
            secs.append(head + ' &middot; none</span></h2>')
            continue
        secs.append(head + ' &middot; %s &middot; <a href="%s%s/%d/index.html">on its own '
                    'page</a></span></h2>\n<div class="pgrid">\n%s\n</div>'
                    % (counts_line(ss), root, g['stem'], n,
                       '\n'.join(cg_box(s, root) for s in ss)))
    ss = all_n(n)
    write('colors/%d/index.html' % n, page(
        'All groups, %s - Color Groups Catalog' % colors(n), root,
        [('../../index.html', 'Catalog'), (None, 'All symmetries with %s' % colors(n))],
        'All symmetries <span class="sub">with %s</span>' % colors(n),
        '%s across the 17 wallpaper groups, with a picture of every pattern: one for each '
        'placement of H in G.' % counts_line(ss),
        by_count_nav(root, n) + '\n' + '\n'.join(secs),
        bar([('../../index.html', 'Catalog'),
             count_run('All symmetries', all_n, '../', cur=n)])))

print('%d groups: %d types, %d color groups, %d patterns (%d color groups rendered); '
      'wrote index.html, %d group pages, %d count pages, %d all-symmetries pages'
      % (len(groups), ntypes(EVERY), len(EVERY), npatterns(EVERY),
         sum(s['built'] for s in EVERY), len(groups),
         sum(1 for g in groups.values() for n in g['per_n'] if g['per_n'][n]), MAX_N))
