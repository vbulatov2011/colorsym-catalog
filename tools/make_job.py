# Generates catalog/jobs/632_632_3.json — full layer set for 632/632[3],
# with subgroup geometry drawn as vectors (reduce-with-G design), motion
# glyphs, shared auto framing, and a non-convex rendering proof.
import json, io, copy

CAT = 'D:/home/projects/00.docs/250117_colorsym/catalog'

m = json.load(open(CAT + '/data/632.json', encoding='utf-8'))
entry = next(s for s in m['subgroups'] if s['name'] == '632/632[3]')
COS = entry['cosets']
N = entry['index']
g_words = [t['word'] for t in entry['transversal']]      # coset transversal
f_words = [t['word'] for t in entry['orbitReps']]        # orbit reps (domain cells)

nonconvex = next(s for s in m['subgroups'] if s['name'] == '632/632[4]')

OFF = {"buffer": {"outline": {"enabled": False}, "fill": {"enabled": False}},
       "generators": {"enabled": False},
       "tiling": {"outline": {"enabled": False}},
       "fundDomain": {"fill": {"enabled": False}, "outline": {"enabled": False}}}

def ov(**kw):
    o = copy.deepcopy(OFF); o.update(kw); return o

FD_ON = {"fill": {"enabled": True}, "outline": {"enabled": True}}
TILE_ON = {"outline": {"enabled": True}}

def motif(**arrows):
    a = {"useOrbit": False, "mask": ""}; a.update(arrows)
    return {"layers": {"arrows": a}, "enable": {"overlay": False}}

def blank():
    return {"enable": {"arrows": False, "overlay": False}}

def mask_for(j):
    return "".join("1" if k == j else "0" for k in range(N))

F_STYLE = {"color": "#c02020", "width": 3.5}
G_STYLE = {"color": "#2040c0", "width": 3.5}

items = []

# ---- colorings ----------------------------------------------------------
for i in range(N):
    items.append({"file": "632-632-3.%d.png" % (i + 1), **motif(permIndex=i)})
items.append({"file": "632-632-3.o.png", **motif(permIndex=0, useOrbit=True)})

# ---- the nine pieces and their unions -----------------------------------
for i in range(N):
    for j in range(N):
        items.append({"file": "%d%d.png" % (i, j), "_note": "f_%d H g_%d" % (i, j),
                      **motif(permIndex=i, mask=mask_for(j))})
for j in range(N):
    items.append({"file": "012_%d.png" % j, "_note": "all orbits of H g_%d" % j,
                  "compose": [motif(permIndex=i, mask=mask_for(j)) for i in range(N)]})

# ---- uncolored pattern --------------------------------------------------
items.append({"file": "group_pattern.png", **motif(permIndex=0, coloringType="none")})

# ---- structure of G (GPU overlay: G is convex, reduction is safe) -------
def gstruct(overlay):
    return {"subgroup": None, "enable": {"arrows": False, "overlay": True},
            "layers": {"overlay": overlay}}

items.append({"file": "group_domain.png", **gstruct(ov(fundDomain=FD_ON))})
items.append({"file": "group_tiling.png", **gstruct(ov(tiling=TILE_ON))})
items.append({"file": "group_gens.png", **gstruct(ov(fundDomain=FD_ON)),
              "markers": {"subgroup": None}})

# ---- structure of H (vector drawing: no reduction with H ever) ----------
items.append({"file": "sub_domain.png",
              "_note": "H's domain as a union of G cells, internal walls shown",
              **blank(),
              "draw": {"subgroup": COS, "fill": True, "cells": True, "outline": True}})
items.append({"file": "sub_tiling.png",
              "_note": "tiling by H's domain over G's tiling",
              "compose": [ {**gstruct(ov(tiling=TILE_ON)), "opacity": 0.3} ],
              "draw": {"subgroup": COS, "tiling": True}})
items.append({"file": "sub_gens.png",
              **blank(),
              "draw": {"subgroup": COS, "fill": True, "outline": True},
              "markers": {"subgroup": COS}})

# ---- f / g motion glyph layers ------------------------------------------
for k in range(1, N):
    items.append({"file": "f%d.png" % k, "_note": "motion f_%d = %s" % (k, f_words[k]),
                  **blank(),
                  "glyphs": {"subgroup": COS, "kind": "cell",
                             "list": [{"word": f_words[k], "style": F_STYLE}]}})
    items.append({"file": "g%d.png" % k, "_note": "motion g_%d = %s" % (k, g_words[k]),
                  **blank(),
                  "glyphs": {"subgroup": COS, "kind": "coset",
                             "list": [{"word": g_words[k], "style": G_STYLE}]}})

# ---- non convex proof: 632/632[4], drawn with the same machinery --------
items.append({"file": "test_nonconvex_domain.png",
              "_note": nonconvex['name'] + " - the union of 4 cells is NOT convex",
              **blank(),
              "draw": {"subgroup": nonconvex['cosets'],
                       "fill": True, "cells": True, "outline": True}})
items.append({"file": "test_nonconvex_tiling.png",
              "_note": nonconvex['name'] + " - tiling by a non convex tile",
              "compose": [ {**gstruct(ov(tiling=TILE_ON)), "opacity": 0.25} ],
              "draw": {"subgroup": nonconvex['cosets'], "tiling": True}})

job = {
 "_comment": [
  "Layer set for " + entry['name'] + ". Template: wp_632_632_3.1.",
  "All images share one view, derived from H's domain (autoView).",
  "Subgroup geometry is DRAWN, never reduced with: G stays the group, the",
  "domain of H is the union of the transversal cells, its tiling the",
  "H-translates of that union. Non convex domains render the same way -",
  "see the two test_nonconvex images (632/632[4]).",
  "f_k are motions to the domain cells (" + " ".join(f_words) + "); g_k the coset transversal (" + " ".join(g_words) + ")."],
 "outDir": "632/3/632-632-3/gen",
 "size": 800,
 "preset": "/catalog/presets/wp_632_632_3.1.json",
 "autoView": {"subgroup": COS, "fillRatio": 0.24},
 "items": items,
}
io.open(CAT + '/jobs/632_632_3.json', 'w', encoding='utf-8').write(json.dumps(job, indent=1))
print('job written:', len(items), 'items')
