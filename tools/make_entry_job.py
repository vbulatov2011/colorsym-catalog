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
# e.g.  python make_entry_job.py 333 "333/o[6]" #           --preset /catalog/presets/wp/wp-333.json --layer drawing
# A symdraw job runs at /apps/symdraw/catalog_render.html?job=..., a sympix
# one at /apps/sympix/catalog_render.html?job=...
#
# Builds catalog/jobs/<slug>.json rendering the full layer set for one entry,
# using the wp_632_632_3.1 preset as the motif template and overriding the
# subgroup permutations, colour count, placements and framing from the manifest.
import json, io, copy, sys
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
# the sympix template already colours by multiplying ('mult'); a document
# that does not - a symdraw drawing starts with 'none' - needs it set, or the
# colorings come out uncoloured.  Set only for a non-default template, so the
# default jobs stay byte for byte what they were.
MOTIF_EXTRA = {} if TEMPLATE.endswith('/wp_632_632_3.1.json') else {"coloringType": "mult"}

stem = _args[0] if len(_args) > 0 else '632'
entry_name = _args[1] if len(_args) > 1 else '632/632[3]'

m = json.load(open(CAT + '/data/%s.json' % stem, encoding='utf-8'))
entry = next(s for s in m['subgroups'] if s['name'] == entry_name)

COS = entry['cosets']
N = entry['index']
K = entry['placements']
g_words = [t['word'] for t in entry['transversal']]
f_words = [t['word'] for t in entry['orbitReps']]

# the app feeds invcos into the layer's permutations
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

OFF = {"buffer": {"outline": {"enabled": False}, "fill": {"enabled": False}},
       "generators": {"enabled": False},
       "tiling": {"outline": {"enabled": False}},
       "fundDomain": {"fill": {"enabled": False}, "outline": {"enabled": False}}}
def ov(**kw):
    o = copy.deepcopy(OFF); o.update(kw); return o
FD_ON = {"fill": {"enabled": True}, "outline": {"enabled": True}}
TILE_ON = {"outline": {"enabled": True}}

def motif(**arrows):
    # useMipmap: the motif texture is minified at this framing, so without
    # mipmaps its edges alias into hard stair steps.  The presets ship with it
    # off, hence the override here - it applies to every motif image: the
    # colorings, the pieces and the uncolored pattern.
    a = {"useOrbit": False, "mask": "", "permutations": INVCOS,
         "useMipmap": True, "colorTiles": {"count": N}, **MOTIF_EXTRA}
    a.update(arrows)
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

items.append({"file": "group_pattern.png", **motif(permIndex=0, coloringType="none")})
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

job = {
 "_comment": [
  "Layer set for %s (%s), %d colours, %d placements." % (entry_name, entry['id'], N, K),
  "Template: %s; permutations overridden to this subgroup's invcos." % TEMPLATE.split('/')[-1][:-5],
  "f words: %s" % ' '.join(f_words),
  "g words: %s" % ' '.join(g_words)],
 "outDir": out_dir,
 "size": 800,
 "preset": TEMPLATE,
 "autoView": {"subgroup": COS, "fillRatio": 0.24},
 "items": items,
}
path = CAT + '/jobs/%s.json' % job_file
io.open(path, 'w', encoding='utf-8', newline='\n').write(json.dumps(job, indent=1))
print('job written:', path, len(items), 'items ->', out_dir)
print('simplyConnected:', entry.get('simplyConnected'), ' f:', ' '.join(f_words), ' g:', ' '.join(g_words))
