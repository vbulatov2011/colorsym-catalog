# Generates a catalog entry page from the manifest and the generated images.
#
#   python tools/make_entry_page.py 632 "632/333[8]" "#f84848,#d808a8,..."
#
# Reads  data/<stem>.json  (the manifest) and expects the images produced by
# the render job in  <G>/<n>/<G>-<H>-<n>/gen/.  Writes index.html next to gen/.
# The design follows the hand built 632/632[3] page: hero with the orbit
# coloring, the placement colorings, facts, the color action table, the f/g
# definitions, the fundamental domains, and the partition table with margins.
# Every picture is click-to-enlarge with arrow key navigation.
import json, io, os, re, sys
from entry_names import entry_names, MIN_N

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

stem = sys.argv[1]
entry_name = sys.argv[2]
palette = sys.argv[3].split(',') if len(sys.argv) > 3 else []

m = json.load(open(os.path.join(CAT, 'data', '%s.json' % stem), encoding='utf-8'))
entry = next(s for s in m['subgroups'] if s['name'] == entry_name)

G = m['group']['name']
N = entry['index']
K = entry['placements']
_nm = entry_names(entry_name, N)
gsym, hsym, slug = _nm['gsym'], _nm['hsym'], _nm['slug']
out_dir = os.path.join(CAT, *_nm['dir'].split('/'))
union_stem = ''.join(str(i) for i in range(N))

# placement classes: offsets i, i' are equivalent iff their point stabilizers
# in the image of G -> S_N coincide (same conjugate g_i^-1 H g_i).  The first
# member of each class is its representative; the job renders the colorings of
# offsets 0..K-1, so those must be exactly the representatives.
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

# The union column: row r's union in ORBIT colors is the .o image carried by
# the motion g_r.  The renderer's orbit mode with offset j produces one of
# these carries, but j is NOT r in general: mirror the app's wordToPerm
# exactly (composePerms(outer, inner) = outer o inner; coset mode appends the
# step, orbit mode prepends it; lowercase letters apply the cos perm) over
# the reachable (coset_perm, orbit_perm) pairs, and pick for each row the
# offset whose per-column colors equal .o's own - the carried coloring.
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

orbit_off = orbit_offsets_for_rows(entry['cosets'], N)
assert orbit_off[0] == 0

classes = placement_classes(entry['cosets'], N)
reps = [c[0] for c in classes]
rep_of = {i: c[0] for c in classes for i in c}
assert len(classes) == K, 'placement count mismatch: %d classes, manifest says %d' % (len(classes), K)
assert reps == list(range(K)), ('placement representatives %r are not offsets 0..%d - '
    'the rendered colorings .1..%d would not be the inequivalent ones' % (reps, K - 1, K))
mark = K < N

f_words = [t['word'] for t in entry['orbitReps']]
f_texts = [t['text'] for t in entry['orbitReps']]
g_words = [t['word'] for t in entry['transversal']]
g_texts = [t['text'] for t in entry['transversal']]
h_gens = entry.get('hGenerators', [])

E = lambda s: s.replace('*', '&lowast;')

def stack(layers, cap):
    out = []
    for l in layers:
        if isinstance(l, tuple):
            out.append("      <img src='%s' class='%s'>" % l)
        else:
            out.append("      <img src='%s'>" % l)
    return ("    <div class='stack'>\n      <div class='cap'>%s</div>\n%s\n    </div>"
            % (cap, "\n".join(out)))

GEN = 'gen/'
# The render job writes PNG; tools/to_webp.py converts each entry to lossless
# WebP (same pixels, 12% of the size, and faster to decode - which matters on
# a page holding a few hundred image layers).  Every image path goes through
# sub(), so naming them is a single place.
IMG_EXT = '.webp'
sub = lambda i: '%s%s' % (GEN, i[:-4] + IMG_EXT if i.endswith('.png') else i)

# ---- swatch css for n colours -------------------------------------------
sw_css = "\n".join(".sw%d { background: %s; }" % (j, palette[j] if j < len(palette) else '#ccc')
                   for j in range(N))
cell_px = max(70, min(235, 720 // N))

# ---- hero ----------------------------------------------------------------
hero_one = "\n".join([
    " <figure>",
    stack([sub('group_pattern.png')], 'G'),
    "  <figcaption><b>G = %s</b> &mdash; the uncolored pattern: one orbit of the motif "
    "<code>p</code>.</figcaption>" % E(G),
    " </figure>",
    " <figure>",
    stack([sub('%s.o.png' % slug)], '%s.o' % E(entry_name)),
    "  <figcaption><b class='name'>%s.o</b> &mdash; coloring by orbits: one color per "
    "H-orbit. There is only ever one such coloring.</figcaption>" % E(entry_name),
    " </figure>",
])

hero_row = "\n".join(
    " <figure>\n%s\n  <figcaption><b class='name'>%s.%d</b> &mdash; coloring by cosets, "
    "placement %d.</figcaption>\n </figure>"
    % (stack([sub('%s.%d.png' % (slug, i + 1))], '%s.%d' % (E(entry_name), i + 1)), E(entry_name), i + 1, i + 1)
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
    tds = "".join("<td><span class='sw sw%d'></span></td>" % a['perm'][j] for j in range(N))
    rows.append(" <tr><th class='gen'>%s</th>%s<td class='cyc'>%s</td></tr>"
                % (a['generator'], tds, a.get('cycles') or cycles_of(a['perm'])))
head = "".join("<th><span class='sw sw%d'></span></th>" % j for j in range(N))
action_table = ("<table class='action'>\n <tr><th>generator</th>%s<th>cycles</th></tr>\n%s\n</table>"
                % (head, "\n".join(rows)))

# ---- f/g fact boxes ------------------------------------------------------
f_list = ", ".join("<code>f<sub>%d</sub>=%s</code>" % (k, f_words[k]) for k in range(1, N))
g_list = ", ".join("<code>g<sub>%d</sub>=%s</code>" % (k, g_words[k]) for k in range(1, N))

# the motions section: a range f_1 .. f_{N-1} needs N >= 3; with N = 2 there is
# a single motion of each kind, and with N = 1 (H = G) there are none at all
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
# the manifest describes a generator in decimals ('rotation by -0.3333*PI about
# (0,0.433)'): written exactly here, 'rotation by −π/3 about (0, √3/4)'.  The
# decimals are rounded to 4 places; every number in the 17 manifests is p/q,
# p√3/q or p√2/q with q dividing 16 or 12, and a number that is none of them
# stays as it is
_MINUS = '−'
def _exact_num(s):
    v = float(s)
    if abs(v) < 6e-5:
        return '0'
    sign, a = (_MINUS if v < 0 else ''), abs(v)
    for root, rs in ((1, ''), (3, '√3'), (2, '√2')):
        for q in (1, 2, 3, 4, 6, 8, 12, 16):          # the smallest q first: p/q is reduced
            p = round(a * q / root ** .5)
            if p and abs(a - p * root ** .5 / q) < 6e-5:
                num = (str(p) if p > 1 or not rs else '') + rs
                return sign + num + ('/%d' % q if q > 1 else '')
    return s

def _exact_angle(m):
    # a multiple of π; a half turn is π either way round
    v = float(m.group(1))
    if abs(abs(v) - 1) < 6e-5:
        return 'π'
    for q in (2, 3, 4, 6, 8, 12):
        p = round(abs(v) * q)
        if p and abs(abs(v) - p / q) < 6e-5:
            return (_MINUS if v < 0 else '') + (str(p) if p > 1 else '') + 'π/%d' % q
    return m.group(0).replace('PI', 'π')

def _exact_point(m):
    parts = [x.strip() for x in m.group(1).split(',')]
    try:
        return '(' + ', '.join(_exact_num(x) for x in parts) + ')'
    except ValueError:
        return m.group(0)

def exact(text):
    text = re.sub(r'(-?\d+(?:\.\d+)?)\*PI', _exact_angle, text)
    return re.sub(r'\(([^()]*)\)', _exact_point, text)

# one generator a line: 'a: rotation by −π/3 about (0, √3/4)'
hgens_list = ''.join('\n      <li><code>%s</code>: %s</li>' % (h['word'], exact(h['text']))
                     for h in h_gens)

# ---- domains panels: a 2 x 3 table (G / H  x  domain, tiling, symmetries) -
def geo_td(img, cap, note):
    return ("   <td>\n%s\n    <div class='cellcap'>%s</div>\n   </td>"
            % (stack([sub(img)], cap), note))
geo = "\n".join([
    "<table class='geo'>",
    "  <tr>\n   <th></th>\n   <th class='col'>domain</th>\n   <th class='col'>tiling</th>"
    "\n   <th class='col'>symmetries</th>\n  </tr>",
    "  <tr>\n   <th class='row'>G</th>",
    geo_td('group_domain.png', 'G domain', 'the fundamental domain of %s' % E(G) +
           (' &mdash; the %s' % E(m['group']['domainShape']) if m['group'].get('domainShape') else '')),
    geo_td('group_tiling.png', 'G tiling', 'the plane tiled by images of G&rsquo;s domain'),
    geo_td('group_gens.png', 'G symmetries', 'every symmetry element of G: rotation '
           'centers (the hurricane&rsquo;s arm count = the order), mirrors (solid red) and '
           'glide axes (dashed red)'),
    "  </tr>",
    "  <tr>\n   <th class='row'>H</th>",
    geo_td('sub_domain.png', 'H domain', 'the fundamental domain of H: a union of %d '
           'cells of G, internal walls shown' % N if N > 1 else
           'the fundamental domain of H: the single cell of G, as H = G'),
    geo_td('sub_tiling.png', 'H tiling', 'the plane tiled by H&rsquo;s domain, over '
           'G&rsquo;s finer tiling'),
    geo_td('sub_gens.png', 'H symmetries', 'every symmetry element of H = %s: rotation '
           'centers, inequivalent ones in shades of the base color; mirrors solid, glide '
           'axes dashed' % E(entry['type'])),
    "  </tr>",
    "</table>",
])

# ---- partition table -----------------------------------------------------
# A panel's layers, bottom to top: the pattern (the piece, or the row's orbits
# in the margin) and its faded origin, then the decorations - tilings and
# fundamental domains, symmetry centres, the f/g glyphs - so that the opaque
# pattern hides none of them.  Each is toggled by a checkbox in the hamburger
# menu, the pattern ('pat') too.
DECOR_GEO = [(sub('group_tiling.png'), 'gtil'),
             (sub('sub_til.png'), 'htil'),
             (sub('group_domain.png'), 'gfd'),
             (sub('sub_domain.png'), 'hfd')]
DECOR_SYM = [(sub('group_marks.png'), 'gsym'),
             (sub('sub_marks.png'), 'hsym')]
# columns = ALL N cells f_i of H's domain (a row unions to the whole pattern);
# the K placement-representative columns are marked when K < N.
rep_td = lambda i: ' rep' if mark and i in reps else ''
trows = []
for j in range(N):
    tds = []
    for i in range(N):
        layers = [(sub('%d%d.png' % (i, j)), 'pat')]
        if i > 0:   layers.append((sub('0%d.png' % j), 'ghost'))  # origin H g_j
        elif j > 0: layers.append((sub('00.png'), 'ghost'))       # origin H
        layers += DECOR_GEO + DECOR_SYM
        if j == 0 and i > 0: layers.append((sub('f%d.png' % i), 'fglyph'))
        if j > 0: layers.append((sub('g%d.png' % j), 'gglyph'))
        lab = ('f<sub>%d</sub> ' % i if i > 0 else '') + ('H' if j == 0 else 'H g<sub>%d</sub>' % j)
        tds.append("   <td class='cell%s'>\n%s\n   </td>" % (rep_td(i), stack(layers, lab)))
    uimg = sub('%s.o.png' % slug) if orbit_off[j] == 0 else sub('%s.o%d.png' % (slug, orbit_off[j]))
    ulayers = [(uimg, 'pat')] + DECOR_GEO + DECOR_SYM
    if j > 0: ulayers.append((sub('g%d.png' % j), 'gglyph'))
    tds.append("   <td class='cell marg'>\n%s\n   </td>"
               % stack(ulayers,
                       'all orbits of %s' % ('H' if j == 0 else 'H g<sub>%d</sub>' % j)))
    trows.append("  <tr>\n   <th class='row'><span class='sw sw%d'></span> orbits of %s</th>\n%s\n  </tr>"
                 % (j, 'H' if j == 0 else 'H g<sub>%d</sub>' % j, "\n".join(tds)))
# the bottom margin: each column's coloring by cosets, with the same layers as
# the panels above it - and the column's f_i, as the right margin has its g_j
def blayers(img, i):
    layers = [(sub(img), 'pat')] + DECOR_GEO + DECOR_SYM
    if i > 0: layers.append((sub('f%d.png' % i), 'fglyph'))
    return layers
tds = []
for i in range(N):
    if i in reps:
        k = reps.index(i) + 1
        tds.append("   <td class='cell marg%s'>\n%s\n   </td>"
                   % (rep_td(i), stack(blayers('%s.%d.png' % (slug, k), i), '%s.%d' % (E(entry_name), k))))
    else:
        k = reps.index(rep_of[i]) + 1
        tds.append("   <td class='cell marg'>\n%s\n   </td>"
                   % stack(blayers('%s.%d.png' % (slug, i + 1), i), '&equiv; .%d' % k))
tds.append("   <td class='cell marg'></td>")
trows.append("  <tr>\n   <th class='row'>all colors<span class='hint'>coloring by cosets</span></th>\n%s\n  </tr>"
             % "\n".join(tds))
def col_th(i):
    if i in reps:
        return ("   <th class='col%s'>f<sub>%d</sub><span class='hint'>.%d</span></th>"
                % (rep_td(i), i, reps.index(i) + 1))
    return ("   <th class='col'>f<sub>%d</sub><span class='hint'>&equiv; .%d</span></th>"
            % (i, reps.index(rep_of[i]) + 1))
thead = ("  <tr>\n   <th></th>\n"
         + "\n".join(col_th(i) for i in range(N))
         + "\n   <th class='col marg'>&#8746;<span class='hint'>all orbits</span></th>\n  </tr>")
table = "<table class='grid' style='--cell:%dpx'>\n%s\n%s\n</table>" % (cell_px, thead, "\n".join(trows))

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

# the bar's run of G's count pages, '632 with 1 2 3 4 6 colors': this entry's
# count dark (still a link - the page is the entry, not the count page), a
# count with no color group dashed; from MIN_N (2) on
_have = {s['index'] for s in m['subgroups']}
def _count_link(k):
    if k not in _have:
        return '<span class="off" title="none">%d</span>' % k
    return ('<a%s href="../../%d/index.html" title="%d color%s">%d</a>'
            % (' class="now"' if k == N else '', k, k, '' if k == 1 else 's', k))
count_run = ('<span class="grp"><b>%s</b> with %s colors</span>'
             % (E(G), ''.join(_count_link(k) for k in range(MIN_N, m['maxIndex'] + 1))))

# ---- page ----------------------------------------------------------------
page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<link rel="stylesheet" href="../../../css/entry.css">
<style>
%(sw_css)s
table.action th, table.action td { padding: .25rem .35rem; }
table.grid td.rep .stack { border-bottom: 4px solid #2040c0; }
table.grid th.col.rep { border-bottom: 4px solid #2040c0; }
.stack img.ghost { opacity: .3; }
table.geo { border-collapse: collapse; }
table.geo td { padding: .35rem; vertical-align: top; }
table.geo th.row { padding: .35rem .7rem; font-size: 1.15rem; vertical-align: middle; }
table.geo th.col { font-weight: 600; padding: .2rem .35rem; text-align: left; }
table.geo .stack { width: min(250px, 28vw); }
table.geo .cellcap { font-size: .85rem; color: #556; margin-top: .3rem; max-width: min(250px, 28vw); }
.stack img.gtil { opacity: .15; }
.stack img.htil { opacity: .3; }
.stack img.gfd, .stack img.hfd { opacity: .35; }
.stack img.gsym, .stack img.hsym { opacity: .75; }
body.off-pat img.pat, body.off-ghost img.ghost, body.off-gfd img.gfd, body.off-hfd img.hfd,
body.off-gtil img.gtil, body.off-htil img.htil,
body.off-gsym img.gsym, body.off-hsym img.hsym,
body.off-f img.fglyph, body.off-g img.gglyph { display: none; }
#deco { position: fixed; top: .8rem; right: .9rem; z-index: 60; font-size: .9rem; }
#deco-btn { font-size: 1.15rem; line-height: 1; padding: .35rem .55rem; cursor: pointer;
  background: #fff; border: 1px solid #bbb; border-radius: 6px; }
#deco-panel { position: absolute; right: 0; margin-top: .3rem; background: #fff;
  border: 1px solid #bbb; border-radius: 8px; padding: .5rem .8rem;
  box-shadow: 0 4px 14px rgba(0,0,0,.14); white-space: nowrap; }
#deco-panel label { display: block; padding: .18rem 0; cursor: pointer; }
#deco-panel input { margin-right: .45rem; }
#deco-panel hr { border: 0; border-top: 1px solid #ddd; margin: .3rem 0; }
</style>
</head>
<body class="with-bar">

<div id="deco">
 <button id="deco-btn" aria-label="display options" title="display options">&#9776;</button>
 <div id="deco-panel" hidden>
  <label><input type="checkbox" data-k="pat" checked> pattern</label>
  <label><input type="checkbox" data-k="ghost" checked> ghost H</label>
  <hr>
  <label><input type="checkbox" data-k="gfd" checked> G fd</label>
  <label><input type="checkbox" data-k="hfd" checked> H fd</label>
  <label><input type="checkbox" data-k="gtil" checked> G tiling</label>
  <label><input type="checkbox" data-k="htil" checked> H tiling</label>
  <hr>
  <label><input type="checkbox" data-k="gsym"> G symmetries</label>
  <label><input type="checkbox" data-k="hsym"> H symmetries</label>
  <hr>
  <label><input type="checkbox" data-k="g" checked> g-transforms</label>
  <label><input type="checkbox" data-k="f" checked> f-transforms</label>
 </div>
</div>
<script>
// the menu's choices, kept in localStorage for every entry page; applied here,
// before the panels, so a page opens as it was left
(function () {
  var KEY = 'colorsym-catalog.entry.layers', saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) {}
  var btn = document.getElementById('deco-btn'),
      panel = document.getElementById('deco-panel'),
      boxes = [].slice.call(panel.querySelectorAll('input[data-k]'));
  function apply(cb) {
    document.body.classList.toggle('off-' + cb.getAttribute('data-k'), !cb.checked);
  }
  boxes.forEach(function (cb) {
    var k = cb.getAttribute('data-k');
    if (typeof saved[k] === 'boolean') cb.checked = saved[k];
    apply(cb);
  });
  btn.addEventListener('click', function () { panel.hidden = !panel.hidden; });
  panel.addEventListener('change', function (e) {
    var k = e.target.getAttribute('data-k');
    if (!k) return;
    apply(e.target);
    saved[k] = e.target.checked;
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
  });
})();
</script>

<header class="entry">
<div class="wrap">
<h1>%(hG)s/%(hH)s<span class="sub">[%(n)d]%(hK)s</span></h1>
<p class="lede">A %(n)d-coloring of the wallpaper group %(hG)s from its index-%(n)d subgroup of
type %(hH)s. %(lede_place)s</p>
</div>
</header>

<div class="wrap">

<div class="hero-one">
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
    <dd>%(hG)s <span class="note"><code>&lang; %(gens)s | %(rels)s &rang;</code></span></dd>
  </div>
  <div class="fact">
    <dt>subgroup H</dt>
    <dd>%(hH)s <span class="note">index %(n)d &nbsp;&middot;&nbsp; generators</span>
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
</dl>

<h2 class="sec">how G permutes the colors</h2>
%(action_table)s
<p class="legend"><b>Words act left to right</b>: <code>(a*b)(p) = b(a(p))</code>.</p>

<h2 class="sec">the two families of motions</h2>
%(motions)s
<h2 class="sec">fundamental domains and pairing transforms</h2>
%(geo)s

<h2 class="sec">color partitioning</h2>
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
with its colors relabeled (titled <code>&equiv;</code> its marked twin). Over every
panel sit faded context layers &mdash; the tilings, fundamental domains and symmetry
centers of G and H; the <b>&#9776; menu</b> at the top right toggles each of them and
the pattern itself, and remembers the choice.</p>

</div>

<footer class="bar">
<div class="wrap">
<nav class="up">
 <a href="../../../index.html">Catalog</a>
 <a href="../../index.html">All color groups of <b>%(hG)s</b></a>
 %(count_run)s
 <a href="../../../colors/%(n)d/index.html">All symmetries with <b>%(ncolors)s</b></a>
</nav>
<div class="meta" title="generated from the manifest and the render job">%(id)s &middot;
<a href="gen/sheet.html">contact sheet</a></div>
</div>
</footer>

<div id="lb" hidden>
 <div>
  <div class="stack" id="lb-stack"></div>
  <div id="lb-hint">click anywhere or press Esc to close &middot; arrow keys to move</div>
 </div>
</div>

<script>
(function () {
  // arrows navigate the partition table as a 2d grid, clamped at its edges;
  // a picture outside the table pages left/right through the others only.
  var lb = document.getElementById('lb'),
      box = document.getElementById('lb-stack'),
      stacks = [].slice.call(document.querySelectorAll('.wrap .stack')),
      idx = -1, pos = [], cellAt = {}, flow = [];
  stacks.forEach(function (s, i) {
    var td = s.closest('table.grid td');
    if (td) {
      var r = td.parentNode.rowIndex - 1, c = td.cellIndex - 1; // header row, label col
      pos[i] = [r, c]; cellAt[r + ',' + c] = i;
    } else {
      pos[i] = null; flow.push(i);
    }
  });
  function show(i) {
    if (i === undefined || i < 0 || i >= stacks.length) return;
    idx = i; box.innerHTML = stacks[i].innerHTML; lb.hidden = false;
  }
  function hide() { lb.hidden = true; box.innerHTML = ''; idx = -1; }
  stacks.forEach(function (s, i) {
    s.tabIndex = 0; s.setAttribute('role', 'button');
    s.addEventListener('click', function () { show(i); });
    s.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(i); }
    });
  });
  lb.addEventListener('click', hide);
  document.addEventListener('keydown', function (e) {
    if (lb.hidden) return;
    if (e.key === 'Escape') { hide(); return; }
    var d = { ArrowRight: [0, 1], ArrowLeft: [0, -1],
              ArrowDown: [1, 0], ArrowUp: [-1, 0] }[e.key];
    if (!d) return;
    e.preventDefault();
    var p = pos[idx];
    if (p) {
      show(cellAt[(p[0] + d[0]) + ',' + (p[1] + d[1])]);   // off the table: no-op
    } else if (!d[0]) {
      var k = flow.indexOf(idx) + d[1];
      if (k >= 0 && k < flow.length) show(flow[k]);
    }
  });
})();
</script>

</body>
</html>
""" % {
    'title': E(entry_name), 'hG': E(G), 'hH': E(entry['type']), 'n': N, 'k': K,
    # '#k' tells apart subgroups sharing G/H[n] - without it two pages share a heading
    'hK': ('#' + E(entry_name.split('#')[1])) if '#' in entry_name else '',
    'nm1': N - 1,
    'sw_css': sw_css,
    'hero_one': hero_one, 'hero_row': hero_row,
    'gens': m['group']['gens'].replace(' ', ', '),
    'rels': E(str(m['group']['relators'])),
    'hgens': hgens_list or '\n      <li>&mdash;</li>',
    'normalnote': '' if K > 1 else ' &mdash; H is normal',
    'action_table': action_table,
    'f_list': f_list, 'g_list': g_list, 'motions': motions,
    'geo': geo, 'table': table, 'place_sent': place_sent,
    'lede_place': lede_place, 'coset_legend': coset_legend,
    'id': entry['id'],
    'ncolors': '%d color%s' % (N, '' if N == 1 else 's'),
    'count_run': count_run,
}

out = os.path.join(out_dir, 'index.html')
io.open(out, 'w', encoding='utf-8', newline='\n').write(page)
print('wrote', out)
