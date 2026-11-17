# Generalized job generator: python make_entry_job.py <manifestStem> <entryName>
# e.g.  python make_entry_job.py 632 "632/333[8]"
#
# Options:
#   --preset <url>  the motif document (default the sympix wp_632_632_3.1);
#                   it also brings the group, which must be <manifestStem>'s
#   --layer <id>    the preset's colour-symmetry layer (default 'arrows', the
#                   sympix one; a symdraw document's is 'drawing')
#   --piece-size <px>  pixel size of the N x N pieces f_i H g_j (default 400,
#                   half the job's 800: they are only seen as table thumbnails,
#                   and as the N^2 term they would otherwise be most of the bytes)
#   --iterations <n>  the renderer's folding steps (symmetry.options.iterations),
#                   patched into every item: a view zoomed out onto a large H
#                   domain needs more steps than a preset saved for drawing may
#                   have (wp-442 was saved with 10; the far cells then stay
#                   unrendered - transparent, with flat color blocks)
#   --view preset|auto  the framing every image of the entry shares.
#                   preset: the preset's own navigator view (centerX, centerY,
#                   zoom), so the entry shows the motif exactly as the preset
#                   and its .json.png thumbnail do - the default for --preset.
#                   It is read from the preset file and written into the job
#                   as "view": the driver draws its overlays (H's domain and
#                   tiling, motions, markers) in the job's view, and without
#                   one it falls back to reading the app's params - whose
#                   symdraw form (tools.transform.params.euclidean) it misses,
#                   drawing at zoom 1 over a renderer at the preset's zoom.
#                   auto: centred on H's fundamental domain, zoomed so that the
#                   domain fills 24% of the height (the view then differs per
#                   entry) - the default for the sympix template, whose jobs
#                   stay byte for byte what they were
# e.g.  python make_entry_job.py 333 "333/o[6]" #           --preset /catalog/presets/wp/wp-333.json --layer drawing
# A symdraw job runs at /apps/symdraw/catalog_render.html?job=..., a sympix
# one at /apps/sympix/catalog_render.html?job=...
#
# Builds catalog/jobs/<slug>.json rendering the full layer set for one entry,
# using the wp_632_632_3.1 preset as the motif template and overriding the
# subgroup permutations, colour count, placements and framing from the manifest.
# G's structure images switch the items of the preset's overlay layer by id,
# every item stated: {"overlays": {"tiling": {"enabled": true}, ...}}.
import json, io, copy, sys, subprocess
from entry_names import entry_names

CAT = 'D:/home/projects/00.docs/250117_colorsym/catalog'
TEMPLATE = '/catalog/presets/wp_632_632_3.1.json'
LAYER = 'arrows'

_args = sys.argv[1:]
def _opt(flag, default):
    if flag in _args:
        i = _args.index(flag); v = _args[i + 1]; del _args[i:i + 2]; return v
    return default
TEMPLATE = _opt('--preset', TEMPLATE)
# a server URL such as /catalog/presets/..; Git Bash rewrites a leading '/'
# into a Windows path (C:/Program Files/Git/catalog/..) unless the call is
# prefixed with MSYS_NO_PATHCONV=1 - catch that here, not in the browser
assert TEMPLATE.startswith('/') and ':' not in TEMPLATE, (
    '--preset must be a server URL like /catalog/presets/wp/wp-333.json, got %r'
    ' (from Git Bash, prefix the command with MSYS_NO_PATHCONV=1)' % TEMPLATE)
LAYER = _opt('--layer', LAYER)
PIECE_SIZE = int(_opt('--piece-size', '400'))
ITERATIONS = _opt('--iterations', None)
VIEW = _opt('--view', 'auto' if TEMPLATE.endswith('/wp_632_632_3.1.json') else 'preset')
assert VIEW in ('preset', 'auto'), '--view must be preset or auto, got %r' % VIEW
PRESET_VIEW = None
if VIEW == 'preset':
    # the navigator view saved in the preset (/catalog/... is this folder)
    _doc = json.load(open(CAT + TEMPLATE[len('/catalog'):], encoding='utf-8'))
    _e = _doc['params']['tools']['transform']['params']['euclidean']
    _zoom = _e['zoom'][0] if isinstance(_e['zoom'], list) else _e['zoom']
    # the driver maps world to pixels by centre and zoom only
    assert not _e.get('angle'), 'preset view is rotated (angle %r): not supported' % _e['angle']
    # since 2026-11-16 the view is the document's frame (SymmHub DocumentView.js):
    # 2/zoom wide, aspect * 2/zoom high - the square images show it whole only
    # when it is square (a preset saved before it has no aspect: square).  A frame
    # sized by hand is square only nearly (wpe/wpe-4s2: 1.0001): within 0.1% the
    # square image shows its width and cuts under a pixel off its height
    assert abs(_e.get('aspect', 1) - 1) < 1e-3, \
        'preset frame is not square (aspect %r): the catalog images are' % _e['aspect']
    PRESET_VIEW = {"zoom": _zoom, "centerX": _e.get('centerX', 0), "centerY": _e.get('centerY', 0)}
# the sympix template already colours by multiplying ('mult'); a document
# that does not - a symdraw drawing starts with 'none' - needs it set, or the
# colorings come out uncoloured.  Set only for a non-default template, so the
# default jobs stay byte for byte what they were.
MOTIF_EXTRA = {} if TEMPLATE.endswith('/wp_632_632_3.1.json') else {"coloringType": "mult"}

SYMMHUB = 'D:/home/projects/00.docs/250125_symhub/repo_v2/SymmHub'

def overlay_item_ids(url):
    """Ids of the items of the preset's overlay layer, in their order.  A
    document saved before the item list (the sympix template) gets them the
    way SymmHub's document load does: VisualizationOverlayUpgradeData.js,
    pure data mapping, run by node as is."""
    doc = json.load(open(CAT + url[len('/catalog'):], encoding='utf-8'))
    layers = doc['params']['visualization']['params']['layers']['params']['children']
    ov = next(c['params'] for c in layers if c['className'] == 'VisualizationOverlay')
    if 'overlays' not in ov:
        js = ("import {upgradeOverlayParams} from 'file:///%s/lib/symhublib/VisualizationOverlayUpgradeData.js';"
              "let s = ''; process.stdin.on('data', d => s += d).on('end', () =>"
              " process.stdout.write(JSON.stringify(upgradeOverlayParams(JSON.parse(s)))));" % SYMMHUB)
        r = subprocess.run(['node', '--input-type=module', '-e', js], input=json.dumps(ov),
                           capture_output=True, text=True, check=True)
        ov = json.loads(r.stdout)
    ids = [c['params']['id'] for c in ov['overlays']['params']['children']]
    # an overlay never touched loads with the items of a fresh one
    return ids or ['tiling', 'fundDomain', 'generators']

stem = _args[0] if len(_args) > 0 else '632'
entry_name = _args[1] if len(_args) > 1 else '632/632[3]'

m = json.load(open(CAT + '/data/%s.json' % stem, encoding='utf-8'))
entry = next(s for s in m['subgroups'] if s['name'] == entry_name)

COS = entry['cosets']
N = entry['index']
K = entry['placements']
g_words = [t['word'] for t in entry['transversal']]
f_words = [t['word'] for t in entry['orbitReps']]

# the layer's permutations, per mode.  A fold across sides s1, s2, ... composes
# the side permutations in one order without useOrbit and in the other with it
# (SymmHub SubgroupTable.checkPermutations), and the manifest's cosets are the
# action read left to right.  So:
#   useOrbit:  invcos -> the orbits of H                       (.o, .oN)
#   cosets:    cosets -> the cosets of H                       (.1 .. .N, pieces)
# invcos without useOrbit is NOT the cosets of H: it is the action with every
# generator inverted, i.e. the cosets of iota(H) (iota: g -> g^-1 on the
# generators; a mirror for 2222, 632, ...).  Harmless only when every generator
# acts as an involution; 2222/o[6]#2 and #3 showed it - .1 of one was .o of the
# other (2026-11-14).
def invert_word(w):
    out = [None] * len(w)
    for i, ch in enumerate(w):
        out[ord(ch) - 97] = chr(97 + i)
    return ''.join(out)
INVCOS = ' '.join(invert_word(w) for w in COS.split())

# check the colorings we render (offsets 0..K-1) are the placement reps:
# offsets are equivalent iff their point stabilizers in <coset perms> coincide
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

_classes = placement_classes(COS, N)
assert [c[0] for c in _classes] == list(range(K)), (
    'placement representatives %r are not offsets 0..%d' % ([c[0] for c in _classes], K - 1))

# G / H / n from the name, for file names:  632/333[8] -> 632-333-8
_nm = entry_names(entry_name, N)
gsym, hsym, slug_flat, job_file = _nm['gsym'], _nm['hsym'], _nm['slug'], _nm['job_file']
out_dir = _nm['dir'] + '/gen'

OVERLAY_IDS = overlay_item_ids(TEMPLATE)
def ov(**on):
    # a patch of the overlay layer's item list, by item id: the items named
    # are switched on with their params, every other item of the preset off
    for k in on:
        assert k in OVERLAY_IDS, 'the preset has no overlay item %r (it has %s)' % (k, OVERLAY_IDS)
    return {"overlays": {i: copy.deepcopy(on.get(i, {"enabled": False})) for i in OVERLAY_IDS}}
FD_ON = {"enabled": True, "fill": {"enabled": True}, "outline": {"enabled": True}}
TILE_ON = {"enabled": True}

def motif(**arrows):
    # useMipmap: the motif texture is minified at this framing, so without
    # mipmaps its edges alias into hard stair steps.  The presets ship with it
    # off, hence the override here - it applies to every motif image: the
    # colorings, the pieces and the uncolored pattern.
    a = {"useOrbit": False, "mask": "", "permutations": COS,
         "useMipmap": True, "colorTiles": {"count": N}, **MOTIF_EXTRA}
    a.update(arrows)
    if a["useOrbit"]:
        a["permutations"] = INVCOS
    return {"layers": {LAYER: a}, "enable": {"overlay": False}}

def blank():
    return {"enable": {LAYER: False, "overlay": False}}

def gstruct(overlay):
    return {"subgroup": None, "enable": {LAYER: False, "overlay": True},
            "layers": {"overlay": overlay}}

def mask_for(j):
    return "".join("1" if q == j else "0" for q in range(N))

F_STYLE = {"color": "#c02020", "width": 3.5}
G_STYLE = {"color": "#2040c0", "width": 3.5}

items = []
# colorings for ALL N offsets: .1...K are the placement reps; the rest are the
# same partitions with relabeled colors (offset i ~ rep _rep_of[i]).
_rep_of = {i: c[0] for c in _classes for i in c}
for i in range(N):
    it = {"file": "%s.%d.png" % (slug_flat, i + 1), **motif(permIndex=i)}
    if i >= K:
        it["_note"] = "same placement as .%d - colors relabeled" % (_rep_of[i] + 1)
    items.append(it)
items.append({"file": "%s.o.png" % slug_flat, **motif(permIndex=0, useOrbit=True)})
# orbit-coloring translates: offset j in orbit mode = the .o image carried by
# g_j - each piece f_i H g_j in orbit color i.  Fills the union column.
for j in range(1, N):
    items.append({"file": "%s.o%d.png" % (slug_flat, j),
                  "_note": "orbit coloring carried by g_%d" % j,
                  **motif(permIndex=j, useOrbit=True)})

# the full partition table is N x N: rows = cosets H g_j, columns = ALL N domain
# cells f_i (piece ij = f_i H g_j, rendered as offset i + mask j).  Only K of the
# N columns give inequivalent colorings, but a row needs all N pieces to union to
# the whole pattern:  U_i f_i H g_j = G g_j.
for i in range(N):
    for j in range(N):
        items.append({"file": "%d%d.png" % (i, j), "_note": "f_%d H g_%d" % (i, j),
                      "size": PIECE_SIZE,
                      **motif(permIndex=i, mask=mask_for(j))})
union_stem = ''.join(str(i) for i in range(N))
for j in range(N):
    items.append({"file": "%s_%d.png" % (union_stem, j),
                  "_note": "all orbits of H g_%d - the whole pattern in color %d" % (j, j),
                  "compose": [motif(permIndex=i, mask=mask_for(j)) for i in range(N)]})

# G's own pattern: the preset's colouring with ONE colour, every shape in the
# palette's first colour (the coloring of G/G[1]: each generator fixes the coset)
ONE = ' '.join('a' for _ in COS.split())
items.append({"file": "group_pattern.png",
              **motif(permIndex=0, permutations=ONE, colorTiles={"count": 1})})
items.append({"file": "group_domain.png", **gstruct(ov(fundDomain=FD_ON))})
items.append({"file": "group_tiling.png", **gstruct(ov(tiling=TILE_ON))})
items.append({"file": "group_gens.png", **gstruct(ov(fundDomain=FD_ON)),
              "markers": {"subgroup": None}})

items.append({"file": "sub_domain.png",
              "_note": "H's domain as a union of %d G cells" % N,
              **blank(),
              "draw": {"subgroup": COS, "fill": True, "cells": True, "outline": True}})
items.append({"file": "sub_tiling.png",
              "compose": [{**gstruct(ov(tiling=TILE_ON)), "opacity": 0.3}],
              "draw": {"subgroup": COS, "tiling": True}})
items.append({"file": "sub_gens.png", **blank(),
              "draw": {"subgroup": COS, "fill": True, "outline": True},
              "markers": {"subgroup": COS}})

# pure single-purpose layers for the entry page's toggles
items.append({"file": "sub_til.png", "_note": "H tiling lines only",
              **blank(), "draw": {"subgroup": COS, "tiling": True}})
items.append({"file": "group_marks.png", "_note": "G rotation centres only",
              **blank(), "markers": {"subgroup": None}})
items.append({"file": "sub_marks.png", "_note": "H rotation centres only",
              **blank(), "markers": {"subgroup": COS}})

for k in range(1, N):
    items.append({"file": "f%d.png" % k, "_note": "f_%d = %s" % (k, f_words[k]),
                  **blank(),
                  "glyphs": {"subgroup": COS, "kind": "cell",
                             "list": [{"word": f_words[k], "style": F_STYLE}]}})
for k in range(1, N):
    items.append({"file": "g%d.png" % k, "_note": "g_%d = %s" % (k, g_words[k]),
                  **blank(),
                  "glyphs": {"subgroup": COS, "kind": "coset",
                             "list": [{"word": g_words[k], "style": G_STYLE}]}})

if ITERATIONS is not None:
    # a plain item applies its own params, a composed one each part's
    for it in items:
        for cfg in it.get("compose", [it]):
            assert "params" not in cfg, cfg
            cfg["params"] = {"symmetry": {"options": {"iterations": int(ITERATIONS)}}}

job = {
 "_comment": [
  "Layer set for %s (%s), %d colours, %d placements." % (entry_name, entry['id'], N, K),
  "Template: %s; permutations overridden to this subgroup's cosets (invcos for the orbit images)." % TEMPLATE.split('/')[-1][:-5],
  "f words: %s" % ' '.join(f_words),
  "g words: %s" % ' '.join(g_words)]
  + (["Every item sets symmetry.options.iterations = %s." % ITERATIONS] if ITERATIONS else [])
  + (["View: the preset's own (centre and zoom), shared by every item."] if VIEW == 'preset' else []),
 "outDir": out_dir,
 "size": 800,
 "preset": TEMPLATE,
 # the view every item renders and draws its overlays in
 **({"view": PRESET_VIEW} if VIEW == 'preset' else
    {"autoView": {"subgroup": COS, "fillRatio": 0.24}}),
 "items": items,
}
path = CAT + '/jobs/%s.json' % job_file
io.open(path, 'w', encoding='utf-8', newline='\n').write(json.dumps(job, indent=1))
print('job written:', path, len(items), 'items ->', out_dir)
print('simplyConnected:', entry.get('simplyConnected'), ' f:', ' '.join(f_words), ' g:', ' '.join(g_words))
