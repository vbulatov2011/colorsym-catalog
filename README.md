# Catalog of color groups of the wallpaper groups

A catalog of the **color groups** of the 17 wallpaper groups: for a group `G` and a
finite-index subgroup `H`, the colorings of `G`'s pattern whose color classes are the
cosets of `H` (one coloring per placement of `H` in `G`) or its orbits (always one).

Each entry is a generated page — artwork, group facts, and the full color partition —
rendered with [SymmHub](https://github.com/vbulatov2011/SymmHub).

## Notation

A color group is written `G/H[n]`, `n` = number of colors = index of `H`.

| suffix | meaning |
| --- | --- |
| `.o` | coloring **by orbits** — each `H`-orbit its own color; unique |
| `.1 .2 …` | coloring **by cosets**, one per *placement* of `H` in `G`; the count is `[G : N_G(H)]`, which is 1 exactly when `H` is normal (then all colorings coincide) |

**Composition is left to right**: `(a*b)(p) = b(a(p))`. Because the left/right coset
distinction flips between that convention and the geometric one, the pages say only
*cosets* and *orbits*, never "left coset" / "right coset".

A group here is its **fundamental domain plus the pairing transforms** that carry that
domain onto its neighbors; the images of the domain tile the plane. Every entry shows
the domain, tiling and symmetry centers of both `G` and `H`.

## The partition table

The heart of an entry. Cell `(row j, column i)` is the piece `f_i H g_j`:

- **columns** are the `N` cells `f_i` of `H`'s fundamental domain (its orbit
  representatives). A whole row unions to the entire pattern. Only `K = [G : N_G(H)]`
  columns give inequivalent colorings; those carry a blue frame, the rest repeat one of
  them with colors relabeled.
- **rows** are the color classes `H g_j` — one color each, `g_j` the coset transversal.
- the **right margin** shows the row as its `N` orbits in their own colors: the orbit
  coloring `.o` carried by that row's `g_j`.
- the **bottom margin** is the coloring by cosets of each column.

Each panel also carries its origin faded beneath it, plus toggleable context layers
(tilings, fundamental domains, symmetry axes) — the ☰ menu at the top right of a page
switches them. Every picture enlarges on click; arrow keys walk the table by row and
column.

Rotation axes are drawn as hurricane symbols whose arm count is the order, and
**inequivalent axis classes appear in different shades of the base color** — so `2222`
shows four shades of the 2-fold symbol, `333` three shades of the 3-fold one, matching
the orbifold symbol.

## Layout

```
<G>/<colors>/<G>-<H>-<n>/     entry: index.html + gen/ (its rendered images)
data/                          per-group manifests (subgroups, geometry, names)
jobs/                          declarative render jobs
tools/                         the generators (see below)
presets/                       SymmHub documents used as render templates
work/                          hand-drawn assets (axis_N.svg) and scratch art
css/entry.css                  entry page styles
```

## Building an entry

Requires a checkout of SymmHub next to this one and python 3 + node.

```bash
node tools/make_manifest.mjs               # data/<group>.json for all 17 groups
python tools/make_entry_job.py 632 "632/333[8]"    # -> jobs/632_333_8.json
```

Then run the job: start the two servers (`.claude/launch.json` defines them — `serve.mjs`
for the catalog, `tools/serve_symmhub.mjs` for SymmHub with a `/save` endpoint) and open

```
http://localhost:8125/apps/sympix/catalog_render.html?job=/catalog/jobs/632_333_8.json
```

which renders every image and POSTs it into the entry's `gen/`. Finally:

```bash
python tools/make_entry_page.py 632 "632/333[8]" "#f84848,#d808a8,..."   # index.html
python tools/make_sheet.py 632 "632/333[8]"                              # contact sheet
```

The palette is sampled from the rendered images, so it is passed per entry.

## Subgroup identity

Enumeration ids are not identity — the coset permutation string is. Subgroups are named
`G/H[n]#k`, where `#k` (omitted when unique) orders the `(type, index)` bucket by a
**geometric key**: a canonical frame computed from the isometries alone, plus the Hermite
basis of `H`'s translation lattice and its surviving rotation centers as exact fractions.
That key is invariant under a change of generating set, so the names survive the planned
alternative fundamental-domain variants. `data/gap_id_map.json` maps the older GAP-derived
ids onto it.
