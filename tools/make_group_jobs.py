# One job per wallpaper group rendering its pattern in ONE colour (the
# palette's first: colorTiles count 1, every generator fixing the one coset),
# the thumbnail of the catalogue's top page and of the group's own page:
#
#   python tools/make_group_jobs.py            -> jobs/group_<stem>.json  (17)
#   python tools/make_group_jobs.py 632 s632   -> only those groups (by stem)
#   --view preset|auto                          default preset
#
# The motif is the group's symdraw preset: the one the catalog's version gives
# it (catalog_paths.version_preset: CATALOG_VERSION, else the main version),
# else presets/wp/wpe/wpe-<name>.json ('*' is written 's', and the presets spell
# the groups with capital X and O).
# View 'preset': the preset's own centre and zoom, as its .json.png thumbnail
# and the entries (make_entry_job.py) show it.  View 'auto': framed on G's
# fundamental domain - the driver frames a view on a subgroup's domain, and
# G/G[1] is the subgroup whose domain is G's - taken from the manifest built on
# the preset's own domain shape: data/wp/<stem>@<shape>.json when there is one,
# else data/wp/<stem>.json.
#
# Run each at /apps/symdraw/catalog_render.html, then tools/to_webp.py --dir
# wp/<stem>/gen.  Output: wp/<stem>/gen/group.png (renders are not tracked in git).
import json, io, os, sys

import catalog_paths as P
CAT = P.CAT
SIZE = 400              # a thumbnail; the pages show it at ~200-280 px
FILL = 0.3              # view auto: G's domain fills 30% of the height - the
                        # renderer tiles a finite patch, which smaller ratios
                        # show as a round blob

ARGS = sys.argv[1:]
VIEW = 'preset'
if '--view' in ARGS:
    i = ARGS.index('--view'); VIEW = ARGS[i + 1]; del ARGS[i:i + 2]
assert VIEW in ('preset', 'auto'), '--view must be preset or auto, got %r' % VIEW
ONLY = set(ARGS)        # stems; empty = all 17


def preset_name(name):
    # manifest names are lower case ('o', 'xx', '*x', '22x'); the presets use
    # the library's own spelling ('O', 'XX', '*X', '22X')
    lib = 'O' if name == 'o' else name.replace('x', 'X')
    return 'wpe-%s.json' % lib.replace('*', 's')


index = json.load(open(P.data_file('index'), encoding='utf-8'))
for g in index['groups']:
    name, stem = g['name'], g['stem']
    if ONLY and stem not in ONLY:
        continue
    preset = P.url(P.version_preset(name) or P.join(P.PRESETS_DIR, 'wpe', preset_name(name)))
    pname = preset.rsplit('/', 1)[1]
    doc = json.load(open(P.path(P.from_url(preset)),
                         encoding='utf-8'))
    shape = doc['params']['symmetry']['group']['params'].get('domainShape', 'default')
    variant = P.data_file('%s@%s' % (stem, shape.replace('*', 's').replace(' ', '-')))
    man_file = variant if os.path.exists(variant) else P.data_file(stem)
    m = json.load(open(man_file, encoding='utf-8'))
    trivial = next(s for s in m['subgroups'] if s['index'] == 1)['cosets']

    job = {
        "_comment": ["Pattern of %s in one colour (the palette's first) for the index pages." % name,
                     ("Preset %s (%s); view framed on G's domain from %s."
                      % (pname, shape, os.path.basename(man_file))
                      if VIEW == 'auto' else
                      "Preset %s (%s); the preset's own view (centre and zoom)."
                      % (pname, shape))],
        "outDir": P.fam(stem, "gen"),
        "size": SIZE,
        "preset": preset,
        **({"autoView": {"subgroup": trivial, "fillRatio": FILL}} if VIEW == 'auto' else {}),
        "items": [{
            "file": "group.png",
            "layers": {"drawing": {"coloringType": "mult", "colorTiles": {"count": 1},
                                   "permutations": trivial, "permIndex": 0,
                                   "useOrbit": False, "mask": "", "useMipmap": True}},
            "enable": {"overlay": False},
        }],
    }
    out = P.job_file('group_%s' % stem)
    io.open(out, 'w', encoding='utf-8', newline='\n').write(json.dumps(job, indent=1))
    print('%-6s %-16s %-22s -> %s/group_%s.json' % (name, pname, shape, P.JOBS_DIR, stem))
