# Contact sheet for one entry's generated images, from its job file.
#
#   python tools/make_sheet.py 632 "632/333[8]"
#
# Reads data/wp/<stem>.json + jobs/<slug>.json and writes gen/sheet.html listing
# every image of the job, grouped: colorings, the N x N pieces, the row
# unions, structure, motion glyphs.
import json, io, os, re, sys
from entry_names import entry_names, piece_file, union_file

import catalog_paths as P

stem = sys.argv[1]
entry_name = sys.argv[2]

m = json.load(open(P.data_file(stem), encoding='utf-8'))
entry = next(s for s in m['subgroups'] if s['name'] == entry_name)
N = entry['index']
K = entry['placements']

_nm = entry_names(entry_name, N)
gsym, hsym, slug, job_file = _nm['gsym'], _nm['hsym'], _nm['slug'], _nm['job_file']
job = json.load(open(P.job_file(job_file), encoding='utf-8'))
out_dir = P.path(job['outDir'])        # a job's outDir is root-relative

files = [it['file'] for it in job['items']]
piece_set = {piece_file(i, j, N) for i in range(N) for j in range(N)}
union_set = {union_file(j, N) for j in range(N)}
pieces = [f for f in files if f in piece_set]
unions = [f for f in files if f in union_set]
colorings = [f for f in files if f.startswith(slug + '.')]
glyphs = [f for f in files if re.fullmatch(r'[fg]\d+\.png', f)]
rest_files = [f for f in files if f not in piece_set and f not in union_set and f not in colorings and f not in glyphs]

# job items name PNGs; the entry ships the converted WebP (see tools/to_webp.py)
IMG_EXT = '.webp'
img_of = lambda f: f[:-4] + IMG_EXT if f.endswith('.png') else f
fig = lambda f, cap=None: ("<figure><img src='%s'><figcaption>%s</figcaption></figure>"
                           % (img_of(f), cap if cap is not None else img_of(f)))
grid = lambda cls, figs: "<div class='g %s'>\n%s\n</div>" % (cls, "\n".join(figs))

parts = []
parts.append("<h3>colorings: .o + %d placements</h3>" % K)
parts.append(grid('g5', [fig(f) for f in colorings]))
parts.append("<h3>pieces f<sub>i</sub> H g<sub>j</sub>: rows = cells f<sub>0</sub>..f<sub>%d</sub>, "
             "cols = cosets 0..%d (first %d rows = the placement reps)</h3>" % (N - 1, N - 1, K))
for i in range(N):
    parts.append(grid('g8', [fig(piece_file(i, j, N), '%d,%d' % (i, j) if N >= 10 else '%d%d' % (i, j)) for j in range(N)]))
parts.append("<h3>row unions (whole pattern in one color)</h3>")
parts.append(grid('g8', [fig(f) for f in unions]))
parts.append("<h3>structure</h3>")
parts.append(grid('g4', [fig(f) for f in rest_files]))
if glyphs:
    parts.append("<h3>motion glyphs</h3>")
    parts.append(grid('g8', [fig(f) for f in glyphs]))

page = """<!doctype html><html><head><meta charset="utf-8"><title>%s generated</title>
<style>body{font:13px system-ui;background:#f4f4f4;margin:1rem}
.g{display:grid;gap:.45rem;margin-bottom:.7rem}
.g5{grid-template-columns:repeat(5,152px)}.g8{grid-template-columns:repeat(8,96px)}
.g4{grid-template-columns:repeat(4,190px)}
img{width:100%%;aspect-ratio:%s;border:1px solid #999;background:#fff;display:block}
figure{margin:0}figcaption{font-size:10.5px;color:#333}
h3{margin:.7rem 0 .3rem;font-size:.78rem;text-transform:uppercase;color:#666}</style></head><body>
<h2>%s &mdash; %d colors, %d placements (%d images)</h2>
%s
</body></html>
""" % (entry_name, (P.family_meta() or {}).get('imageAspect', '1'), entry_name, N, K, len(files), "\n".join(parts))

out = os.path.join(out_dir, 'sheet.html')
io.open(out, 'w', encoding='utf-8', newline='\n').write(page)
print('wrote', out, '-', len(files), 'images')
