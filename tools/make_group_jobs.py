# One job per wallpaper group rendering its UNCOLORED pattern, the thumbnail
# of the catalogue's top page and of the group's own page:
#
#   python tools/make_group_jobs.py            -> jobs/group_<stem>.json  (17)
#
# The motif is the group's symdraw preset, presets/wp/wp-<name>.json ('*' is
# written 's', and the presets spell the groups with capital X and O).  The
# view is framed on G's fundamental domain - the driver frames a view on a
# subgroup's domain, and G/G[1] is the subgroup whose domain is G's - taken
# from the manifest built on the preset's own domain shape:
# data/<stem>@<shape>.json when there is one, else data/<stem>.json.
#
# Run each at /apps/symdraw/catalog_render.html, then tools/to_webp.py --dir
# <stem>/gen.  Output: <stem>/gen/group.png (renders are not tracked in git).
import json, io, os

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE = 400              # a thumbnail; the pages show it at ~200-280 px
FILL = 0.3              # G's domain fills 30% of the height: the renderer tiles a
                        # finite patch, which smaller ratios show as a round blob


def preset_name(name):
    # manifest names are lower case ('o', 'xx', '*x', '22x'); the presets use
    # the library's own spelling ('O', 'XX', '*X', '22X')
    lib = 'O' if name == 'o' else name.replace('x', 'X')
    return 'wp-%s.json' % lib.replace('*', 's')


index = json.load(open(os.path.join(CAT, 'data', 'index.json'), encoding='utf-8'))
for g in index['groups']:
    name, stem = g['name'], g['stem']
    preset = '/catalog/presets/wp/' + preset_name(name)
    doc = json.load(open(os.path.join(CAT, preset[len('/catalog/'):].replace('/', os.sep)),
                         encoding='utf-8'))
    shape = doc['params']['symmetry']['group']['params'].get('domainShape', 'default')
    variant = os.path.join(CAT, 'data', '%s@%s.json' % (stem, shape.replace(' ', '-')))
    man_file = variant if os.path.exists(variant) else os.path.join(CAT, 'data', stem + '.json')
    m = json.load(open(man_file, encoding='utf-8'))
    trivial = next(s for s in m['subgroups'] if s['index'] == 1)['cosets']

    job = {
        "_comment": ["Uncolored pattern of %s for the index pages." % name,
                     "Preset %s (%s); view framed on G's domain from %s."
                     % (preset_name(name), shape, os.path.basename(man_file))],
        "outDir": stem + "/gen",
        "size": SIZE,
        "preset": preset,
        "autoView": {"subgroup": trivial, "fillRatio": FILL},
        "items": [{
            "file": "group.png",
            "layers": {"drawing": {"coloringType": "none", "useMipmap": True}},
            "enable": {"overlay": False},
        }],
    }
    out = os.path.join(CAT, 'jobs', 'group_%s.json' % stem)
    io.open(out, 'w', encoding='utf-8', newline='\n').write(json.dumps(job, indent=1))
    print('%-6s %-16s %-22s -> jobs/group_%s.json' % (name, preset_name(name), shape, stem))
