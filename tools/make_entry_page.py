# Generates a catalog entry page from the manifest and the generated images.
#
#   python tools/make_entry_page.py 632 "632/333[8]" "#f84848,#d808a8,..."
#
# Reads data/<family>/<stem>.json (the manifest) and expects the images produced by
# the render job in <familyDir>/<G>/<n>/<G>-<H>-<n>/gen/. Writes index.html next
# to gen/. Shared styles and interactions live in css/entry.css, js/theme.js, and
# js/entry.js.
import html as _html, json, io, os, re, sys
from entry_names import entry_names, group_motif, MIN_N, MAX_N
import catalog_paths as P

stem = sys.argv[1]
entry_name = sys.argv[2]
palette = sys.argv[3].split(',') if len(sys.argv) > 3 and sys.argv[3] else []

m = json.load(open(P.data_file(stem), encoding='utf-8'))
entry = next(s for s in m['subgroups'] if s['name'] == entry_name)

fmeta = P.family_meta()
fam_title = fmeta.get('title', 'Wallpaper groups')
fam_short = fmeta.get('shortTitle', fam_title)
fam_singular = fmeta.get('groupSingular', 'wallpaper group')
space_noun = fmeta.get('spaceNoun', 'the plane')
live_app = fmeta.get('liveApp', {})
live_symdraw = live_app.get('symdraw', '/apps/symdraw/symdraw_wp.html')
live_layer = live_app.get('layer', 'drawing')
color_range = fmeta.get('colorRange') or [MIN_N, MAX_N]
lo_n, hi_n = int(color_range[0]), int(color_range[1])

G = m['group']['name']
G_stem = m['group'].get('stem') or G.replace('*', 's')
N = entry['index']
K = entry['placements']
_nm = entry_names(entry_name, N)
gsym, hsym, slug = _nm['gsym'], _nm['hsym'], _nm['slug']
out_dir = P.path(P.fam(_nm['dir']))
site = P.up(P.fam(_nm['dir']))

# Known groups in this family (for cross-linking subgroup H to its own group page)
_idx_path = P.data_file('index')
_family_stems = {}
if os.path.exists(_idx_path):
    for _g in json.load(open(_idx_path, encoding='utf-8')).get('groups', []):
        _family_stems[_g['name']] = _g['stem']


def name_key(name):
    mm = re.match(r'(.*)\[(\d+)\](?:#(\d+))?$', name)
    return (mm.group(1), int(mm.group(2)), int(mm.group(3) or 0)) if mm else (name, 0, 0)


# Sibling order within G (matching make_index_pages.py: color count, affineClass, name)
_all_subs = sorted(
    (s for s in m['subgroups'] if lo_n <= s['index'] <= hi_n),
    key=lambda s: (s['index'], name_key(s.get('affineClass') or s['name']), name_key(s['name']))
)
_pos = next((i for i, s in enumerate(_all_subs) if s['name'] == entry_name), -1)
_prev_s = _all_subs[_pos - 1] if _pos > 0 else None
_next_s = _all_subs[_pos + 1] if 0 <= _pos < len(_all_subs) - 1 else None


def _rel_entry_href(other):
    onm = entry_names(other['name'], other['index'])
    # From <G>/<N>/<slug>/index.html -> ../../<N2>/<slug2>/index.html
    return '../../%d/%s/index.html' % (other['index'], onm['slug'])


# Siblings in the same affine equivalence class
_aff = entry.get('affineClass')
_aff_sibs = [s for s in _all_subs if _aff and s.get('affineClass') == _aff and s['name'] != entry_name]


def _subgroup_contained(sub_cosets, sup_cosets):
    """True iff H_sub is contained in a conjugate of H_sup inside G
    (exact G-equivariant surjection cosets(H_sub) -> cosets(H_sup))."""
    p1 = [[ord(c) - 97 for c in w] for w in sub_cosets.split()]
    p2 = [[ord(c) - 97 for c in w] for w in sup_cosets.split()]
    n1, n2 = len(p1[0]), len(p2[0])
    if n1 <= n2 or n1 % n2 != 0:
        return False
    for target0 in range(n2):
        phi = [-1] * n1
        phi[0] = target0
        q = [0]
        ok = True
        while q and ok:
            x = q.pop()
            px = phi[x]
            for g1, g2 in zip(p1, p2):
                nx, ny = g1[x], g2[px]
                if phi[nx] == -1:
                    phi[nx] = ny
                    q.append(nx)
                elif phi[nx] != ny:
                    ok = False
                    break
        if ok:
            return True
    return False


_supergroups = [s for s in _all_subs if s['index'] < N and _subgroup_contained(entry['cosets'], s['cosets'])]
_subgroups_below = [s for s in _all_subs if s['index'] > N and _subgroup_contained(s['cosets'], entry['cosets'])]
_same_h_others = [s for s in _all_subs if s['type'] == entry['type'] and s['name'] != entry_name]

# Preset & iterations metadata for live SymmHub deep links
_preset_rel = None
try:
    _preset_rel = group_motif(P.CAT, G, G_stem)['preset']
except Exception:
    _preset_rel = P.version_preset(G)

_iterations = None
_job_path = P.job_file(_nm['job_file'])
if os.path.exists(_job_path):
    try:
        _jdoc = json.load(open(_job_path, encoding='utf-8'))
        for _c in _jdoc.get('_comment', []):
            if 'symmetry.options.iterations' in _c:
                _mm = re.search(r'= (\d+)', _c)
                if _mm:
                    _iterations = int(_mm.group(1))
    except Exception:
        pass


def invert_word(w):
    out = [None] * len(w)
    for i, ch in enumerate(w):
        out[ord(ch) - 97] = chr(97 + i)
    return ''.join(out)


COS = entry['cosets']
INVCOS = ' '.join(invert_word(w) for w in COS.split())
ONE = ' '.join('a' for _ in COS.split())


# placement classes: offsets i, i' are equivalent iff their point stabilizers
# in the image of G -> S_N coincide (same conjugate g_i^-1 H g_i).
def placement_classes(cosets, n):
    gens = [[ord(c) - 97 for c in w] for w in cosets.split()]
    idp = tuple(range(n))
    seen = {idp}; queue = [idp]
    while queue:
        q0 = queue.pop()
        for g in gens:
            q = tuple(g[x] for x in q0)
            if q not in seen: seen.add(q); queue.append(q)
    stab = {}
    for i in range(n):
        key = frozenset(q for q in seen if q[i] == i)
        stab.setdefault(key, []).append(i)
    return sorted(stab.values())


def orbit_offsets_for_rows(cosets, n):
    t = [[ord(c) - 97 for c in w] for w in cosets.split()]
    tinv = [[0] * n for _ in t]
    for gi, perm in enumerate(t):
        for i, v in enumerate(perm): tinv[gi][v] = i
    steps = [tuple(x) for x in t + tinv]
    comp = lambda outer, inner: tuple(outer[x] for x in inner)
    ident = tuple(range(n))
    seen = {(ident, ident)}
    queue = [(ident, ident)]
    while queue:
        C, B = queue.pop()
        for st in steps:
            nxt = (comp(C, st), comp(st, B))
            if nxt not in seen: seen.add(nxt); queue.append(nxt)
    def color_map(r, j):
        phi = [None] * n
        for C, B in seen:
            for i in range(n):
                if C[i] == r:
                    if phi[i] is None: phi[i] = B[j]
                    elif phi[i] != B[j]: return None
        return phi
    phi0 = color_map(0, 0)
    out = []
    for r in range(n):
        js = [j for j in range(n) if color_map(r, j) == phi0]
        assert js, 'no orbit offset colors row %d like .o' % r
        out.append(r if r in js else js[0])
    return out


orbit_off = orbit_offsets_for_rows(COS, N)
assert orbit_off[0] == 0

classes = placement_classes(COS, N)
reps = [c[0] for c in classes]
rep_of = {i: c[0] for c in classes for i in c}
assert len(classes) == K, 'placement count mismatch: %d classes, manifest says %d' % (len(classes), K)
assert reps == list(range(K)), ('placement representatives %r are not offsets 0..%d - '
    'the rendered colorings .1..%d would not be the inequivalent ones' % (reps, K - 1, K))
mark = K < N

f_words = [t['word'] for t in entry['orbitReps']]
g_words = [t['word'] for t in entry['transversal']]
h_gens = entry.get('hGenerators', [])

E = lambda s: _html.escape(s).replace('*', '&lowast;').replace('x', '&times;')
E_raw = lambda s: _html.escape(s).replace('*', '&lowast;')


DEFERRED_LAYERS = {'gsym', 'hsym'}


def stack(layers, cap, lazy=False, live_kind=None, live_perm=None):
    out = []
    la = " loading='lazy' decoding='async'" if lazy else " decoding='async'"
    for l in layers:
        if isinstance(l, tuple):
            src_attr = 'data-src' if l[1] in DEFERRED_LAYERS else 'src'
            out.append("      <img %s='%s' class='%s'%s>" % (src_attr, l[0], l[1], la))
        else:
            out.append("      <img src='%s'%s>" % (l, la))
    extra = ''
    if live_kind:
        extra += " data-live-kind='%s'" % live_kind
        if live_perm is not None:
            extra += " data-live-perm='%d'" % live_perm
    return ("    <div class='stack'%s>\n      <div class='cap'>%s</div>\n%s\n    </div>"
            % (extra, cap, "\n".join(out)))


GEN = 'gen/'
IMG_EXT = '.webp'
sub = lambda i: '%s%s' % (GEN, i[:-4] + IMG_EXT if i.endswith('.png') else i)

# ---- swatch css for n colours -------------------------------------------
sw_css = "\n".join(".sw%d { background: %s; }" % (j, palette[j] if j < len(palette) else '#ccc')
                   for j in range(N))
cell_px = max(76, min(235, 720 // N))


def live_btns(kind, perm=0):
    if not _preset_rel:
        return ''
    return (
        "  <div class='fig-live'>"
        "<button type='button' class='btn sm subtle' data-live-preview='1' data-live-kind='%s' data-live-perm='%d' "
        "title='Open inline interactive preview on this page'>&#9654; Live</button>"
        "<a class='btn sm subtle' target='_blank' rel='noopener' data-live-kind='%s' data-live-perm='%d' "
        "data-live-ui='simple' href='#' title='Open interactively in SymmHub (viewer mode)'>Explore &#8599;</a>"
        "<a class='btn sm subtle' target='_blank' rel='noopener' data-live-kind='%s' data-live-perm='%d' "
        "data-live-ui='' href='#' title='Open in SymmHub Studio editor'>Studio &#8599;</a>"
        "</div>" % (kind, perm, kind, perm, kind, perm)
    )


# ---- hero ----------------------------------------------------------------
hero_one = "\n".join([
    " <figure>",
    stack([sub('group_pattern.png')], 'G', live_kind='group', live_perm=0),
    "  <figcaption><b>G = %s</b> &mdash; the pattern in one color: one orbit of the motif "
    "<code>p</code>.</figcaption>" % E(G),
    live_btns('group', 0),
    " </figure>",
    " <figure>",
    stack([sub('%s.o.png' % slug)], '%s.o' % E(entry_name), live_kind='orbit', live_perm=0),
    "  <figcaption><b class='name'>%s.o</b> &mdash; coloring by orbits: one color per "
    "H-orbit. There is only ever one such coloring.</figcaption>" % E(entry_name),
    live_btns('orbit', 0),
    " </figure>",
])

hero_row = "\n".join(
    " <figure>\n%s\n  <figcaption><b class='name'>%s.%d</b> &mdash; coloring by cosets, "
    "placement %d.</figcaption>\n%s\n </figure>"
    % (stack([sub('%s.%d.png' % (slug, i + 1))], '%s.%d' % (E(entry_name), i + 1),
             live_kind='coset', live_perm=i),
       E(entry_name), i + 1, i + 1, live_btns('coset', i))
    for i in range(K))


# ---- color action table --------------------------------------------------
def cycles_of(perm):
    seen = [False] * len(perm); parts = []
    for i in range(len(perm)):
        if seen[i]: continue
        c = []; j = i
        while not seen[j]:
            seen[j] = True; c.append(j); j = perm[j]
        if len(c) > 1: parts.append('(' + ' '.join(map(str, c)) + ')')
    return ''.join(parts) or 'e'


rows = []
for a in entry['colorAction']:
    tds = "".join("<td><span class='sw sw%d' data-color-idx='%d' title='color %d'></span></td>"
                  % (a['perm'][j], a['perm'][j], a['perm'][j]) for j in range(N))
    rows.append(" <tr><th class='gen'>%s</th>%s<td class='cyc'>%s</td></tr>"
                % (_html.escape(a['generator']), tds, _html.escape(a.get('cycles') or cycles_of(a['perm']))))
head = "".join("<th><span class='sw sw%d' data-color-idx='%d' title='color %d'></span></th>"
               % (j, j, j) for j in range(N))
action_table = ("<table class='action'>\n <tr><th>generator</th>%s<th>cycles</th></tr>\n%s\n</table>"
                % (head, "\n".join(rows)))

# ---- f/g fact boxes ------------------------------------------------------
f_list = ", ".join("<code>f<sub>%d</sub>=%s</code>" % (k, _html.escape(f_words[k])) for k in range(1, N))
g_list = ", ".join("<code>g<sub>%d</sub>=%s</code>" % (k, _html.escape(g_words[k])) for k in range(1, N))


def _rng(x):
    if N == 2: return '%s<sub>1</sub>' % x
    return '%s<sub>1</sub> &hellip; %s<sub>%d</sub>' % (x, x, N - 1)


if N == 1:
    motions = """<dl class="facts">
  <div class="fact">
    <dt class="plain">no motions f or g</dt>
    <dd class="small">H = G: H&rsquo;s domain is G&rsquo;s single cell and there is one
        coset, so nothing carries the motif to another cell and nothing makes a
        second color.</dd>
  </div>
</dl>
"""
else:
    motions = """<dl class="facts">
  <div class="fact">
    <dt class="plain">%s &mdash; where the motif starts</dt>
    <dd class="small">The motions carrying the motif to the other cells of H&rsquo;s
        domain (one cell per H-orbit): %s.</dd>
  </div>
  <div class="fact">
    <dt class="plain">%s &mdash; what makes the colors</dt>
    <dd class="small">The coset transversal: <code>g<sub>j</sub></code> carries H onto
        coset j, and the sets <code>H&thinsp;g<sub>j</sub></code> are the color classes:
        %s.</dd>
  </div>
</dl>
""" % (_rng('f'), f_list, _rng('g'), g_list)

_MINUS = '\u2212'


def _exact_num(s):
    v = float(s)
    if abs(v) < 6e-5:
        return '0'
    sign, a = (_MINUS if v < 0 else ''), abs(v)
    for root, rs in ((1, ''), (3, '\u221a3'), (2, '\u221a2')):
        for q in (1, 2, 3, 4, 6, 8, 12, 16):
            p = round(a * q / root ** .5)
            if p and abs(a - p * root ** .5 / q) < 6e-5:
                num = (str(p) if p > 1 or not rs else '') + rs
                return sign + num + ('/%d' % q if q > 1 else '')
    return s


def _exact_angle(mm):
    v = float(mm.group(1))
    if abs(abs(v) - 1) < 6e-5:
        return '\u03c0'
    for q in (2, 3, 4, 6, 8, 12):
        p = round(abs(v) * q)
        if p and abs(abs(v) - p / q) < 6e-5:
            return (_MINUS if v < 0 else '') + (str(p) if p > 1 else '') + '\u03c0/%d' % q
    return mm.group(0).replace('PI', '\u03c0')


def _exact_point(mm):
    parts = [x.strip() for x in mm.group(1).split(',')]
    try:
        return '(' + ', '.join(_exact_num(x) for x in parts) + ')'
    except ValueError:
        return mm.group(0)


def exact(text):
    text = re.sub(r'(-?\d+(?:\.\d+)?)\*PI', _exact_angle, text)
    return re.sub(r'\(([^()]*)\)', _exact_point, text)


hgens_list = ''.join('\n      <li><code>%s</code>: %s</li>' % (_html.escape(h['word']), _html.escape(exact(h['text'])))
                     for h in h_gens)

# ---- domains panels: a 2 x 3 table (G / H  x  domain, tiling, symmetries) -
def geo_td(img, cap, note):
    return ("   <td>\n%s\n    <div class='cellcap'>%s</div>\n   </td>"
            % (stack([sub(img)], cap, lazy=True), note))


geo = "\n".join([
    "<div class='geo-wrap'><table class='geo'>",
    "  <tr>\n   <th></th>\n   <th class='col'>domain</th>\n   <th class='col'>tiling</th>"
    "\n   <th class='col'>symmetries</th>\n  </tr>",
    "  <tr>\n   <th class='row'>G</th>",
    geo_td('group_domain.png', 'G domain', 'the fundamental domain of %s' % E(G) +
           (' &mdash; the %s' % E_raw(m['group']['domainShape']) if m['group'].get('domainShape') else '')),
    geo_td('group_tiling.png', 'G tiling', '%s tiled by images of G&rsquo;s domain' % space_noun),
    geo_td('group_gens.png', 'G symmetries', 'every symmetry element of G: rotation '
           'centers (the hurricane&rsquo;s arm count = the order), mirrors (solid red) and '
           'glide axes (dashed red)'),
    "  </tr>",
    "  <tr>\n   <th class='row'>H</th>",
    geo_td('sub_domain.png', 'H domain', 'the fundamental domain of H: a union of %d '
           'cells of G, internal walls shown' % N if N > 1 else
           'the fundamental domain of H: the single cell of G, as H = G'),
    geo_td('sub_tiling.png', 'H tiling', '%s tiled by H&rsquo;s domain, over '
           'G&rsquo;s finer tiling' % space_noun),
    geo_td('sub_gens.png', 'H symmetries', 'every symmetry element of H = %s: rotation '
           'centers, inequivalent ones in shades of the base color; mirrors solid, glide '
           'axes dashed' % E(entry['type'])),
    "  </tr>",
    "</table></div>",
])

# ---- partition table -----------------------------------------------------
DECOR_GEO = [(sub('group_tiling.png'), 'gtil'),
             (sub('sub_til.png'), 'htil'),
             (sub('group_domain.png'), 'gfd'),
             (sub('sub_domain.png'), 'hfd')]
DECOR_SYM = [(sub('group_marks.png'), 'gsym'),
             (sub('sub_marks.png'), 'hsym')]
rep_td = lambda i: ' rep' if mark and i in reps else ''
trows = []
for j in range(N):
    tds = []
    for i in range(N):
        layers = [(sub('%d%d.png' % (i, j)), 'pat')]
        if i > 0:   layers.append((sub('0%d.png' % j), 'ghost'))
        elif j > 0: layers.append((sub('00.png'), 'ghost'))
        layers += DECOR_GEO + DECOR_SYM
        if j == 0 and i > 0: layers.append((sub('f%d.png' % i), 'fglyph'))
        if j > 0: layers.append((sub('g%d.png' % j), 'gglyph'))
        lab = ('f<sub>%d</sub> ' % i if i > 0 else '') + ('H' if j == 0 else 'H g<sub>%d</sub>' % j)
        tds.append("   <td class='cell%s'>\n%s\n   </td>" % (rep_td(i), stack(layers, lab, lazy=True)))
    uimg = sub('%s.o.png' % slug) if orbit_off[j] == 0 else sub('%s.o%d.png' % (slug, orbit_off[j]))
    ulayers = [(uimg, 'pat')] + DECOR_GEO + DECOR_SYM
    if j > 0: ulayers.append((sub('g%d.png' % j), 'gglyph'))
    tds.append("   <td class='cell marg'>\n%s\n   </td>"
               % stack(ulayers,
                       'all orbits of %s' % ('H' if j == 0 else 'H g<sub>%d</sub>' % j),
                       lazy=True, live_kind='orbit', live_perm=orbit_off[j]))
    trows.append("  <tr>\n   <th class='row'><span class='sw sw%d'></span> orbits of %s</th>\n%s\n  </tr>"
                 % (j, 'H' if j == 0 else 'H g<sub>%d</sub>' % j, "\n".join(tds)))


def blayers(img, i):
    layers = [(sub(img), 'pat')] + DECOR_GEO + DECOR_SYM
    if i > 0: layers.append((sub('f%d.png' % i), 'fglyph'))
    return layers


tds = []
for i in range(N):
    if i in reps:
        k = reps.index(i) + 1
        tds.append("   <td class='cell marg%s'>\n%s\n   </td>"
                   % (rep_td(i), stack(blayers('%s.%d.png' % (slug, k), i), '%s.%d' % (E(entry_name), k),
                                       lazy=True, live_kind='coset', live_perm=i)))
    else:
        k = reps.index(rep_of[i]) + 1
        tds.append("   <td class='cell marg'>\n%s\n   </td>"
                   % stack(blayers('%s.%d.png' % (slug, i + 1), i), '&equiv; .%d' % k,
                           lazy=True, live_kind='coset', live_perm=i))
tds.append("   <td class='cell marg'></td>")
trows.append("  <tr>\n   <th class='row'>all colors<span class='hint'>coloring by cosets</span></th>\n%s\n  </tr>"
             % "\n".join(tds))


def col_th(i):
    if i in reps:
        return ("   <th class='col%s'>f<sub>%d</sub><span class='hint'>.%d</span></th>"
                % (rep_td(i), i, reps.index(i) + 1))
    return ("   <th class='col' data-rep-col='%d'>f<sub>%d</sub><span class='hint'>&equiv; .%d</span></th>"
            % (rep_of[i], i, reps.index(rep_of[i]) + 1))


thead = ("  <tr>\n   <th></th>\n"
         + "\n".join(col_th(i) for i in range(N))
         + "\n   <th class='col marg'>&#8746;<span class='hint'>all orbits</span></th>\n  </tr>")
table = ("<table class='grid' style='--cell:%dpx'>\n<thead>\n%s\n</thead>\n<tbody>\n%s\n</tbody>\n</table>"
         % (cell_px, thead, "\n".join(trows)))

pairs_txt = ", ".join("f<sub>%d</sub>&thinsp;&equiv;&thinsp;.%d" % (i, reps.index(rep_of[i]) + 1)
                      for i in range(N) if i not in reps)
if not mark:
    place_sent = "All %d columns carry inequivalent colorings &mdash; the %d placements." % (N, K)
elif K == 1:
    place_sent = ("H is normal, so every column carries the <b>same</b> coloring &mdash; the "
                  "one marked by the <b>blue frame</b>; the others repeat it with colors "
                  "relabeled: %s." % pairs_txt)
else:
    place_sent = ("Only the %d columns marked by the <b>blue frame</b> carry inequivalent "
                  "colorings &mdash; the placements; the others repeat a marked one: %s."
                  % (K, pairs_txt))

if K == 1:
    lede_place = ("H is <b>normal</b> in G: it sits inside G in a single way, so there is "
                  "one coloring by cosets and one by orbits &mdash; and they define the "
                  "same partition.")
    coset_legend = ("<b class='name'>.1</b> &mdash; <b>coloring by cosets</b>: H is normal, "
                    "so there is a single placement and a single coset coloring, and it "
                    "partitions the pattern exactly as the orbit coloring does.")
else:
    lede_place = ("H sits inside G in %d inequivalent ways, so there are %d colorings by "
                  "cosets &mdash; and one by orbits." % (K, K))
    coset_legend = ("<b class='name'>.1&hellip;.%d</b> &mdash; <b>coloring by cosets</b> "
                    "depends on where the motif is placed among the %d copies of "
                    "G&rsquo;s domain inside H&rsquo;s; the %d placements give %d distinct "
                    "colorings of the same uncolored pattern." % (K, N, K, K))

# Count run pill in footer
_have = {s['index'] for s in m['subgroups']}


def _count_link(k):
    if k not in _have:
        return '<span class="off" title="none">%d</span>' % k
    return ('<a%s href="../../%d/index.html" title="%d color%s">%d</a>'
            % (' class="now"' if k == N else '', k, k, '' if k == 1 else 's', k))


count_run = ('<span class="count-run"><b>%s</b> with %s colors</span>'
             % (E(G), ''.join(_count_link(k) for k in range(lo_n, m['maxIndex'] + 1))))

# Cross-links: subgroup H link and affine type fact
_h_type = entry['type']
_h_stem = _family_stems.get(_h_type)
h_link = ('<a href="../../../%s/index.html" title="Open %s symmetry group page">%s</a>'
          % (_h_stem, _html.escape(_h_type), E(_h_type))) if _h_stem else E(_h_type)

if _aff:
    if _aff_sibs:
        _sib_links = ''.join(
            '<a class="btn sm subtle" href="%s">%s</a>' % (_rel_entry_href(s), E(s['name']))
            for s in _aff_sibs
        )
        affine_fact = (
            '  <div class="fact">\n'
            '    <dt>affine type</dt>\n'
            '    <dd><span class="name">%s</span>'
            ' <span class="note">equivalent under an affine symmetry of G to:</span>'
            '<div class="sibs">%s</div></dd>\n'
            '  </div>' % (E(_aff), _sib_links)
        )
    else:
        affine_fact = (
            '  <div class="fact">\n'
            '    <dt>affine type</dt>\n'
            '    <dd><span class="name">%s</span>'
            ' <span class="note">sole color group in its affine equivalence class</span></dd>\n'
            '  </div>' % E(_aff)
        )
else:
    affine_fact = ''

# Prev / Next controls for sticky top bar
prev_btn = ('<a class="btn sm" rel="prev" href="%s" title="Previous color group ([): %s">&larr; %s</a>'
            % (_rel_entry_href(_prev_s), _html.escape(_prev_s['name']), E(_prev_s['name']))) if _prev_s else \
           '<span class="btn sm disabled">&larr; Prev</span>'
next_btn = ('<a class="btn sm" rel="next" href="%s" title="Next color group (]): %s">%s &rarr;</a>'
            % (_rel_entry_href(_next_s), _html.escape(_next_s['name']), E(_next_s['name']))) if _next_s else \
           '<span class="btn sm disabled">Next &rarr;</span>'

# Copyable coset permutations & related subgroup links
_copy_inv = (
    '<div class="copy-row"><code class="copy-code">%s</code>'
    '<button type="button" class="btn sm subtle copy-btn" data-copy="%s">Copy orbit</button></div>'
    % (_html.escape(INVCOS), _html.escape(INVCOS))
) if INVCOS != COS else ''
cosets_fact = (
    '  <div class="fact">\n'
    '    <dt>coset permutations</dt>\n'
    '    <dd><div class="copy-row"><code class="copy-code">%s</code>'
    '<button type="button" class="btn sm subtle copy-btn" data-copy="%s">Copy</button></div>%s'
    '<span class="note">paste into SymmHub&rsquo;s Color Symmetry permutations field</span></dd>\n'
    '  </div>' % (_html.escape(COS), _html.escape(COS), _copy_inv)
)

_rel_blocks = []
if _supergroups:
    _rel_blocks.append(
        '<div class="rel-group"><span class="rel-lbl">Contained in (H &sub; H&prime;):</span><div class="sibs">%s</div></div>'
        % ''.join('<a class="btn sm subtle" href="%s">%s</a>' % (_rel_entry_href(s), E(s['name'])) for s in _supergroups)
    )
if _subgroups_below:
    _rel_blocks.append(
        '<div class="rel-group"><span class="rel-lbl">Contains (H&prime; &sub; H):</span><div class="sibs">%s</div></div>'
        % ''.join('<a class="btn sm subtle" href="%s">%s</a>' % (_rel_entry_href(s), E(s['name'])) for s in _subgroups_below[:12])
    )
if _same_h_others:
    _rel_blocks.append(
        '<div class="rel-group"><span class="rel-lbl">Other %s/%s color groups:</span><div class="sibs">%s</div></div>'
        % (E(G), E(entry['type']),
           ''.join('<a class="btn sm subtle" href="%s">%s</a>' % (_rel_entry_href(s), E(s['name'])) for s in _same_h_others[:10]))
    )
related_fact = (
    '  <div class="fact">\n'
    '    <dt>subgroup relations</dt>\n'
    '    <dd>%s</dd>\n'
    '  </div>' % ''.join(_rel_blocks)
) if _rel_blocks else ''

# Header live CTA buttons + inline live preview drawer
header_live = ''
live_drawer = ''
if _preset_rel:
    header_live = (
        '<div class="entry-live-bar">\n'
        '  <button type="button" id="hdr-live-btn" class="btn primary" data-live-preview="1" '
        'data-live-kind="coset" data-live-perm="0" title="Toggle inline interactive SymmHub preview">&#9654; Live preview</button>\n'
        '  <a class="btn" target="_blank" rel="noopener" data-live-kind="coset" data-live-perm="0" '
        'data-live-ui="simple" href="#" title="Open this color group in a new SymmHub tab">Explore &#8599;</a>\n'
        '  <a class="btn" target="_blank" rel="noopener" data-live-kind="coset" data-live-perm="0" '
        'data-live-ui="" href="#" title="Open in SymmHub Studio editor">Studio &#8599;</a>\n'
        '  <label class="sync-ov-lbl" title="Pass checked G/H domain, tiling and symmetry overlays into SymmHub">'
        '<input type="checkbox" data-sync-overlays> Sync overlays</label>\n'
        '</div>'
    )
    _dtabs = [
        '<button type="button" class="seg-btn" data-drawer-tab="1" data-drawer-kind="coset" data-drawer-perm="%d">.%d</button>' % (i, i + 1)
        for i in range(K)
    ] + [
        '<button type="button" class="seg-btn" data-drawer-tab="1" data-drawer-kind="orbit" data-drawer-perm="0">.o</button>',
        '<button type="button" class="seg-btn" data-drawer-tab="1" data-drawer-kind="group" data-drawer-perm="0">G</button>',
    ]
    live_drawer = (
        '<section id="live-drawer" hidden aria-label="Interactive SymmHub preview">\n'
        '  <div class="live-head">\n'
        '    <div class="live-tabs"><span class="lt-lbl">Coloring</span>%s</div>\n'
        '    <div class="live-acts">\n'
        '      <label class="sync-ov-lbl"><input type="checkbox" data-sync-overlays> Sync overlays</label>\n'
        '      <button type="button" class="btn sm" id="live-tall">Tall</button>\n'
        '      <a class="btn sm" id="live-newtab" target="_blank" rel="noopener" href="#">New tab &#8599;</a>\n'
        '      <a class="btn sm" id="live-studiotab" target="_blank" rel="noopener" href="#">Studio &#8599;</a>\n'
        '      <button type="button" class="btn sm" id="live-close" aria-label="Close live preview">&times; Close</button>\n'
        '    </div>\n'
        '  </div>\n'
        '  <div class="live-frame-wrap"><iframe id="live-iframe" title="Interactive SymmHub view" src="about:blank" allow="fullscreen"></iframe></div>\n'
        '  <div class="live-foot"><span>Drag to pan &middot; scroll to zoom &middot; powered by SymmHub</span>'
        '<span>Change SymmHub URL in top-right <b>&#9881;</b> settings</span></div>\n'
        '</section>\n' % ''.join(_dtabs)
    )

# Embedded live metadata JSON for js/entry.js
live_json = json.dumps({
    'app': live_symdraw,
    'layer': live_layer,
    'preset': _preset_rel,
    'siteRoot': site,
    'group': G,
    'name': entry_name,
    'n': N,
    'cosets': COS,
    'invcos': INVCOS,
    'one': ONE,
    **({'iterations': _iterations} if _iterations else {}),
}, ensure_ascii=False)

# ---- page ----------------------------------------------------------------
page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="symmhub-base" content="%(symmhub_url)s">
<meta name="catalog-root" content="%(site)s">
<meta name="catalog-version" content="%(ver_name)s">
<meta name="catalog-is-main" content="%(ver_is_main)s">
<meta name="catalog-rel" content="%(cat_rel)s">
<title>%(title)s</title>
<link rel="stylesheet" href="%(site)scss/entry.css">
<script src="%(site)sjs/theme.js"></script>
<style>
%(sw_css)s
</style>
</head>
<body>

<nav class="topnav" aria-label="Catalog navigation">
<div class="wrap topnav__inner">
  <div class="crumbs">
    <a class="brand" href="%(site)sindex.html">Catalog</a>
    <span class="sep" aria-hidden="true">&rsaquo;</span>
    <a href="../../../index.html">%(fam_short)s</a>
    <span class="sep" aria-hidden="true">&rsaquo;</span>
    <a href="../../index.html">%(hG)s</a>
    <span class="sep" aria-hidden="true">&rsaquo;</span>
    <a href="../index.html">%(ncolors)s</a>
    <span class="sep" aria-hidden="true">&rsaquo;</span>
    <span class="cur">%(hG)s/%(hH)s[%(n)d]%(hK)s</span>
  </div>
  <div class="topnav__actions">
    %(prev_btn)s
    %(next_btn)s
    <button type="button" class="btn sm" data-theme-toggle>&#9728; Light</button>
  </div>
</div>
</nav>

<header class="entry">
<div class="wrap">
<div class="entry-head">
  <div>
    <h1>%(hG)s/%(hH)s<span class="sub">[%(n)d]%(hK)s</span></h1>
    <p class="lede">A %(n)d-coloring of the %(fam_singular)s %(hG)s from its index-%(n)d subgroup of
    type %(hH)s. %(lede_place)s</p>
  </div>
  %(header_live)s
</div>%(version_note)s
</div>
</header>

<main class="wrap page-main">

%(live_drawer)s<div class="hero-one">
%(hero_one)s
</div>

<div class="hero-row">
%(hero_row)s
</div>

<p class="legend"><b class="name">.o</b> &mdash; <b>coloring by orbits</b> gives each
H-orbit its own color; it is unique. %(coset_legend)s <b>Any picture enlarges on
click.</b></p>

<h2 class="sec">the color group</h2>
<dl class="facts">
  <div class="fact">
    <dt>group G</dt>
    <dd><a href="../../index.html">%(hG)s</a>
    <div class="copy-row"><code class="copy-code">&lang; %(gens)s | %(rels)s &rang;</code><button type="button" class="btn sm subtle copy-btn" data-copy="%(pres_copy)s">Copy</button></div></dd>
  </div>
  <div class="fact">
    <dt>subgroup H</dt>
    <dd>%(h_link)s <span class="note">index %(n)d &nbsp;&middot;&nbsp; generators</span>
    <ul class="gens">%(hgens)s
    </ul></dd>
  </div>
  <div class="fact">
    <dt>colors</dt>
    <dd>%(n)d <span class="note">one per coset of H, equivalently one per orbit</span></dd>
  </div>
  <div class="fact">
    <dt>placements</dt>
    <dd>%(k)d <span class="note">the conjugates of H, <code>[G : N<sub>G</sub>(H)]</code>%(normalnote)s</span></dd>
  </div>
%(affine_fact)s
%(cosets_fact)s
%(related_fact)s
</dl>

<h2 class="sec">how G permutes the colors</h2>
%(action_table)s
<p class="legend"><b>Words act left to right</b>: <code>(a*b)(p) = b(a(p))</code>. Hover a swatch to highlight its row in the partition table below.</p>

<h2 class="sec">the two families of motions</h2>
%(motions)s
<h2 class="sec">fundamental domains and pairing transforms</h2>
%(geo)s

<h2 class="sec">color partitioning</h2>
<div class="layer-bar" aria-label="Partition table display options">
  <div class="layer-group">
    <span class="lg-lbl">Presets</span>
    <button type="button" class="seg-btn" data-layer-preset="clean">Clean</button>
    <button type="button" class="seg-btn" data-layer-preset="domains">Domains</button>
    <button type="button" class="seg-btn" data-layer-preset="syms">Symmetries</button>
    <button type="button" class="seg-btn" data-layer-preset="all">All</button>
  </div>
  <div class="layer-group">
    <label><input type="checkbox" data-k="pat" checked> pattern</label>
    <label><input type="checkbox" data-k="ghost" checked> ghost H</label>
    <label><input type="checkbox" data-k="gfd" checked> G fd</label>
    <label><input type="checkbox" data-k="hfd" checked> H fd</label>
    <label><input type="checkbox" data-k="gtil" checked> G tiling</label>
    <label><input type="checkbox" data-k="htil" checked> H tiling</label>
    <label><input type="checkbox" data-k="gsym"> G sym</label>
    <label><input type="checkbox" data-k="hsym"> H sym</label>
    <label><input type="checkbox" data-k="g" checked> g</label>
    <label><input type="checkbox" data-k="f" checked> f</label>
  </div>
  <div class="layer-group">
    <span class="lg-lbl">Bg</span>
    <button type="button" class="seg-btn" data-backdrop="light">Light</button>
    <button type="button" class="seg-btn" data-backdrop="checker">Checker</button>
    <button type="button" class="seg-btn" data-backdrop="dark">Dark</button>
  </div>
</div>

<div class="cosets">
%(table)s
</div>
<p class="legend">Each panel is <code>f<sub>i</sub> H g<sub>j</sub></code>: <b>columns</b>
are the %(n)d cells of H&rsquo;s domain, <b>rows</b> the %(n)d orbit classes &mdash; one
color per row, and a full row together is the whole pattern: the <b>right margin</b>
shows it as the composition of its %(n)d orbits, each in its own color &mdash; the
coloring by orbits <b class='name'>.o</b> carried by that row&rsquo;s
<code>g<sub>j</sub></code>.
%(place_sent)s Every panel except <code>H</code> also shows, <b>faded</b>, the set it
comes from: <code>H&thinsp;g<sub>j</sub></code> panels show <code>H</code>, and
<code>f<sub>i</sub>&hellip;</code> panels show their row&rsquo;s <code>H&thinsp;g<sub>j</sub></code>.
The <b>bottom margin</b> is the coloring by cosets of every column &mdash; under a marked
column the pictures from the top of the page, under a repeated column the same partition
with its colors relabeled (titled <code>&equiv;</code> its marked twin). Use the toolbar
above the table (or inside the lightbox) to toggle context layers and panel backdrop; choices
are remembered across entry pages.</p>

</main>

<footer class="site-foot">
<div class="wrap foot-row">
  <div class="foot-links">
    %(count_run)s
    <a class="btn sm" href="../../../colors/%(n)d/index.html">All symmetries with <b>%(ncolors)s</b></a>
  </div>
  <div class="foot-links" title="generated from the manifest and the render job">
    <span>%(id)s</span>
    <span>&middot;</span>
    <a href="gen/sheet.html">contact sheet</a>
    <span>&middot;</span>
    <a href="%(compare)s">compare versions</a>
  </div>
</div>
</footer>

<div id="lb" hidden role="dialog" aria-modal="true" aria-label="Enlarged figure">
  <div class="lb-bar">
    <div class="lb-bar-title">
      <span id="lb-title"></span>
      <span id="lb-meta"></span>
    </div>
    <div class="lb-bar-actions">
      <button type="button" id="lb-live-inline" class="btn sm primary" hidden>&#9654; Live</button>
      <a id="lb-live" class="btn sm" target="_blank" rel="noopener" href="#" hidden>Explore &#8599;</a>
      <a id="lb-live-studio" class="btn sm" target="_blank" rel="noopener" href="#" hidden>Studio &#8599;</a>
      <button type="button" id="lb-close" class="btn sm" aria-label="Close lightbox">&times; Close</button>
    </div>
  </div>
  <div class="lb-stage">
    <button type="button" id="lb-lt" class="lb-arrow" aria-label="Previous column">&#8592;</button>
    <div class="lb-nav-v">
      <button type="button" id="lb-up" class="lb-arrow" aria-label="Previous row">&#8593;</button>
      <div class="stack" id="lb-stack"></div>
      <button type="button" id="lb-dn" class="lb-arrow" aria-label="Next row">&#8595;</button>
    </div>
    <button type="button" id="lb-rt" class="lb-arrow" aria-label="Next column">&#8594;</button>
  </div>
  <div id="lb-layers" hidden>
    <label><input type="checkbox" data-k="pat" checked> pattern</label>
    <label><input type="checkbox" data-k="ghost" checked> ghost H</label>
    <label><input type="checkbox" data-k="gfd" checked> G fd</label>
    <label><input type="checkbox" data-k="hfd" checked> H fd</label>
    <label><input type="checkbox" data-k="gtil" checked> G tiling</label>
    <label><input type="checkbox" data-k="htil" checked> H tiling</label>
    <label><input type="checkbox" data-k="gsym"> G sym</label>
    <label><input type="checkbox" data-k="hsym"> H sym</label>
    <label><input type="checkbox" data-k="g" checked> g</label>
    <label><input type="checkbox" data-k="f" checked> f</label>
  </div>
  <div id="lb-hint">click backdrop or press Esc to close &middot; arrow keys move through panels</div>
</div>

<script type="application/json" id="entry-live-data">%(live_json)s</script>
<script src="%(site)sjs/entry.js" defer></script>
</body>
</html>
""" % {
    'symmhub_url': _html.escape(P.SYMMHUB_URL),
    'ver_name': _html.escape(P.VERSION or ''),
    'ver_is_main': '1' if P.is_main() else '0',
    'cat_rel': _html.escape(P.join(P.TREE, _nm['dir'], 'index.html')),
    'title': _html.escape(entry_name.replace('x', '\u00d7')) + ' - Color Groups Catalog',
    'fam_short': _html.escape(fam_short),
    'fam_singular': _html.escape(fam_singular),
    'hG': E(G), 'hH': E(entry['type']), 'n': N, 'k': K,
    'h_link': h_link,
    'affine_fact': affine_fact,
    'cosets_fact': cosets_fact,
    'related_fact': related_fact,
    'live_drawer': live_drawer,
    'pres_copy': _html.escape('< %s | %s >' % (m['group']['gens'].replace(' ', ', '), m['group']['relators'])),
    'site': site,
    'version_note': ('\n' + P.version_note(site)) if P.version_note('') else '',
    'compare': P.compare_link(site, entry_name),
    'hK': ('#' + _html.escape(entry_name.split('#')[1])) if '#' in entry_name else '',
    'sw_css': sw_css,
    'prev_btn': prev_btn,
    'next_btn': next_btn,
    'header_live': header_live,
    'hero_one': hero_one, 'hero_row': hero_row,
    'gens': _html.escape(m['group']['gens'].replace(' ', ', ')),
    'rels': E_raw(str(m['group']['relators'])),
    'hgens': hgens_list or '\n      <li>&mdash;</li>',
    'normalnote': '' if K > 1 else ' &mdash; H is normal',
    'action_table': action_table,
    'motions': motions,
    'geo': geo, 'table': table, 'place_sent': place_sent,
    'lede_place': lede_place, 'coset_legend': coset_legend,
    'id': _html.escape(entry['id']),
    'ncolors': '%d color%s' % (N, '' if N == 1 else 's'),
    'count_run': count_run,
    'live_json': live_json.replace('</', '<\\/'),
}

out = os.path.join(out_dir, 'index.html')
import time
tmp = out + '.tmp.%d' % os.getpid()
for _attempt in range(5):
    try:
        with io.open(tmp, 'w', encoding='utf-8', newline='\n') as _f:
            _f.write(page)
        os.replace(tmp, out)
        break
    except OSError:
        if _attempt == 4:
            raise
        time.sleep(0.05 * (_attempt + 1))
print('wrote', out)
