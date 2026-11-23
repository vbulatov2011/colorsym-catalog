# Versions of the catalog: renderings of the family from presets of their own,
# kept side by side to compare (catalog_paths.py says where a version's files are).
#
#   python tools/version.py list
#   python tools/version.py new <name> --set <set> [--preset <G>=<file>]... [--label <text>] [--main]
#   python tools/version.py build <name> [<stem>...] [--keep-presets]
#      ... render the list in SymmHub (build prints the URL) ...
#   python tools/version.py post <name> [<stem>...] [--sparse]
#   python tools/version.py pages <name>
#   python tools/version.py promote <name>
#   python tools/version.py compare [<a>] [<b>]
#
# new      versions/<name>/version.json: a preset for every group, taken from the
#          set presets/wp/<set>/ - its file <prefix>-<G>.json, G spelled as the
#          presets spell it (O, XX, 22X, s632; the newest if several match).
#          --preset overrides or fills in a group's: <G> its name (*632, o) or that
#          spelling (s632, O), <file> a name in the set or a path from the
#          catalog root.  --main makes it the main version, for the first one,
#          whose page tree and jobs are then the catalog's own (wp/, jobs/);
#          later ones become main by promote.
# build    copies the presets into versions/<name>/presets/ - the snapshot the
#          version renders, so a preset edited afterwards does not change it
#          (--keep-presets: leave the snapshot as it is) - and writes the group
#          jobs (make_group_jobs.py), the entry jobs (make_entry_job.py) of every
#          color group with MIN_N..MAX_N colors, and the render list
#          versions/<name>/render_list.json.  An entry's iterations are its own
#          job's, else the main version's job's, else the preset's.
# render   SymmHub's catalog_render.html?list=<render list>&done=<marker> (the
#          driver's catalog.runList); the marker versions/<name>/render_done.json
#          appears when the list is through.  Show the Browser pane meanwhile.
# post     after the render: verify_entry.py, WebP, the entry pages and contact
#          sheets, the index pages (and the main version's landing page, which
#          lists the versions), versions/<name>/entries.json for compare.html,
#          and two checks: H's domain inside the frame, and every entry of a
#          group showing the same uncolored pattern (one that differs was
#          disturbed while it rendered).  --sparse: verify without the coverage
#          check, for motifs with holes.
# pages    the pages, sheets, index pages and entries.json again, each entry
#          page with the palette it has (no render, no verify).
# promote  makes <name> the main version: the old main's page tree and jobs move
#          to versions/<old>/, <name>'s to wp/ and jobs/; then both versions'
#          jobs (their outDirs moved) and pages (the version note) are written
#          again.  git then sees the old main's pages replaced by <name>'s.
# compare  the compare page for two versions (default: the main one and the
#          newest other), and how many color groups each has rendered.
import datetime, glob, io, json, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog_paths as P
from entry_names import entry_names, group_motif, MIN_N, MAX_N

PY = sys.executable
TOOLS = os.path.join(P.CAT, 'tools')
RENDER_PAGE = P.SYMMHUB_URL + '/apps/symdraw/catalog_render.html'
CATALOG_SITE = 'http://localhost:8124/'          # serve.mjs: the catalog root
THREADS = 8


# ---- helpers ------------------------------------------------------------------

def groups():
    return json.load(open(P.data_file('index'), encoding='utf-8'))['groups']


def spelling(name):
    """the presets' spelling of a group: wp uses O, XX, 22X, s632; frieze uses s22oo, 22oo, ..."""
    if P.FAMILY == 'wp':
        return ('O' if name == 'o' else name.replace('x', 'X')).replace('*', 's')
    return name.replace('\u221e', 'oo').replace('*', 's')


def load(rel):
    return json.load(open(P.path(rel), encoding='utf-8'))


def save(rel, obj):
    f = P.path(rel)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    io.open(f, 'w', encoding='utf-8', newline='\n').write(json.dumps(obj, indent=1, ensure_ascii=False) + '\n')


def tool(v, script, *args, check=True):
    """a catalog tool run on version v (CATALOG_VERSION + CATALOG_FAMILY)"""
    env = dict(os.environ, CATALOG_VERSION=v, CATALOG_FAMILY=P.FAMILY)
    r = subprocess.run([PY, os.path.join(TOOLS, script)] + list(args), cwd=P.CAT, env=env,
                       capture_output=True, text=True, encoding='utf-8')
    if check and r.returncode:
        sys.exit('%s %s failed:\n%s' % (script, ' '.join(args), r.stderr[-3000:]))
    return r


def use(v):
    """the registry, with v's family and v made active"""
    reg = P.registry()
    if v not in reg['versions']:
        sys.exit('no version %r; the versions: %s' % (v, ', '.join(reg['versions']) or 'none'))
    vcfg = P.version_config(v)
    if vcfg and vcfg.get('family') and vcfg['family'] != P.FAMILY:
        P.use_family(vcfg['family'])
    P.use_version(v)
    return reg


def option(args, flag, default=None, many=False):
    vals = []
    while flag in args:
        i = args.index(flag)
        vals.append(args[i + 1])
        del args[i:i + 2]
    return vals if many else (vals[-1] if vals else default)


def switch(args, flag):
    if flag in args:
        args.remove(flag)
        return True
    return False


def entries_of(manifest):
    """the color groups of a manifest the catalog has: MIN_N..MAX_N colors"""
    m = json.load(open(P.data_file(manifest), encoding='utf-8'))
    return [s for s in m['subgroups'] if MIN_N <= s['index'] <= MAX_N]


def gen_dirs(stem):
    """a group's gen/ folders in the current version's tree: its own and its entries'"""
    base = P.path(P.fam(stem))
    return sorted(glob.glob(os.path.join(base, 'gen')) + glob.glob(os.path.join(base, '*', '*', 'gen')))


# ---- new ----------------------------------------------------------------------

def cmd_new(args):
    label = option(args, '--label', '')
    pset = option(args, '--set')
    overrides = option(args, '--preset', many=True)
    main = switch(args, '--main')
    if len(args) != 1 or not pset:
        sys.exit('usage: version.py new <name> --set <set> [--preset <G>=<file>]... [--label <text>] [--main]')
    name = args[0]
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', name):
        sys.exit('a version name is lower case letters, digits and _ . -: %r' % name)
    reg = P.registry()
    if name in reg['versions']:
        sys.exit('version %r exists' % name)
    cur_main = P.main_version(P.FAMILY)
    if main and cur_main:
        sys.exit('%r is the main version for %s; make %r main later with promote' % (cur_main, P.FAMILY, name))
    set_dir = P.join(P.PRESETS_DIR, pset)
    if not os.path.isdir(P.path(set_dir)):
        sys.exit('no preset set %s/' % set_dir)
    files = [f for f in os.listdir(P.path(set_dir)) if f.endswith('.json')]
    gs = groups()
    given = {}
    for o in overrides:
        g, _, f = o.partition('=')
        hit = [x['name'] for x in gs if g in (x['name'], spelling(x['name']), x['stem'])]
        if not hit or not f:
            sys.exit('--preset %r: not <group>=<file>' % o)
        rel = f if os.path.exists(P.path(f)) and '/' in f else P.join(set_dir, f)
        if not os.path.exists(P.path(rel)):
            sys.exit('--preset %r: no file %s' % (o, rel))
        given[hit[0]] = rel
    presets, missing = {}, []
    for g in gs:
        name_g = g['name']
        if name_g in given:
            presets[name_g] = given[name_g]
            continue
        pat = re.compile(r'[A-Za-z0-9]+-%s\.json' % re.escape(spelling(name_g)))
        hits = sorted((f for f in files if pat.fullmatch(f)),
                      key=lambda f: os.path.getmtime(P.path(set_dir, f)))
        if not hits:
            missing.append(name_g)
            continue
        if len(hits) > 1:
            print('  %s: %s match, the newest taken' % (name_g, ', '.join(hits)))
        presets[name_g] = P.join(set_dir, hits[-1])
    if missing:
        sys.exit('no preset in %s/ for %s; give one with --preset <G>=<file>'
                 % (set_dir, ', '.join(missing)))
    today = datetime.date.today().isoformat()
    save(P.join(P.version_dir(name), 'version.json'),
         {'name': name, 'label': label, 'created': today, 'family': P.FAMILY,
          'set': pset, 'presets': presets})
    reg['versions'][name] = {'label': label, 'created': today, 'family': P.FAMILY}
    if main:
        mbf = reg.setdefault('mainByFamily', {})
        if P.DEFAULT_FAMILY not in mbf and reg.get('main'):
            mbf[P.DEFAULT_FAMILY] = reg['main']
        mbf[P.FAMILY] = name
        if P.FAMILY == P.DEFAULT_FAMILY or not reg.get('main'):
            reg['main'] = name
    save(P.join(P.VERSIONS_DIR, 'index.json'), reg)
    for g in gs:
        print('  %-6s %s' % (g['name'], presets[g['name']]))
    print('version %s: %s%s' % (name, P.join(P.version_dir(name), 'version.json'),
                                ' - the main version' if main else ''))
    print('next: python tools/version.py build %s' % name)


# ---- build --------------------------------------------------------------------

def iterations(job, v, main):
    """the iterations an entry's job sets (make_entry_job.py --iterations), from the
    version's own job, else the main version's, else data/<family>/family.json's
    renderIterations (by group stem, then default)"""
    for d in [P.jobs_dir(v)] + ([P.jobs_dir(main)] if main and main != v else []):
        f = P.path(d, job + '.json')
        if os.path.exists(f):
            c = [x for x in json.load(open(f, encoding='utf-8'))['_comment']
                 if 'symmetry.options.iterations' in x]
            return re.search(r'= (\d+)', c[0]).group(1) if c else None
    ri = (P.family_meta() or {}).get('renderIterations') or {}
    stem = job.split('_')[0]
    val = ri.get(stem, ri.get('default'))
    return str(val) if val is not None else None


def write_jobs(v, stems=(), keep=False):
    """the snapshot, the group and entry jobs and the render list of version v"""
    reg = use(v)
    cfg = P.version_config(v)
    gs = [g for g in groups() if not stems or g['stem'] in stems]
    # 1. the presets' snapshot
    changed = []
    for g in gs:
        src = cfg['presets'][g['name']]
        dst = P.snapshot(src, v)
        if keep:
            if not os.path.exists(P.path(dst)):
                sys.exit('%s: no snapshot %s to keep' % (g['name'], dst))
            continue
        for ext in ('', '.png'):          # the preset and its thumbnail
            if os.path.exists(P.path(src + ext)):
                old = open(P.path(dst + ext), 'rb').read() if os.path.exists(P.path(dst + ext)) else None
                new = open(P.path(src + ext), 'rb').read()
                if old != new:
                    os.makedirs(os.path.dirname(P.path(dst + ext)), exist_ok=True)
                    open(P.path(dst + ext), 'wb').write(new)
                    if ext == '':
                        changed.append('%s (%s)' % (g['name'], 'new' if old is None else 'changed'))
    if changed:
        print('presets copied: %s' % ', '.join(changed))
    # 2. the group jobs
    os.makedirs(P.path(P.JOBS_DIR), exist_ok=True)
    tool(v, 'make_group_jobs.py', *[g['stem'] for g in gs])
    # 3. the entry jobs
    tasks, fails, per_group = [], [], {}
    for g in gs:
        gm = group_motif(P.CAT, g['name'], g['stem'])
        if gm['stale']:
            fails.append((g['name'], gm['stale']))
            continue
        url = P.url(gm['preset'])
        subs = entries_of(gm['manifest'])
        per_group[g['stem']] = (g['name'], os.path.basename(gm['preset']), gm['manifest'], [])
        for s in subs:
            job = entry_names(s['name'], s['index'])['job_file']
            it = iterations(job, v, P.main_version(P.FAMILY))
            tasks.append((g['stem'], s['name'], job,
                          [gm['manifest'], s['name'], '--preset', url, '--layer', 'drawing',
                           '--view', 'preset'] + (['--iterations', it] if it else [])))

    def run(t):
        return t, tool(v, 'make_entry_job.py', *t[3], check=False)
    with ThreadPoolExecutor(THREADS) as ex:
        for (stem, ename, job, _), r in ex.map(run, tasks):
            if r.returncode:
                fails.append((ename, (r.stderr.strip().splitlines() or ['?'])[-1]))
            else:
                per_group[stem][3].append(job)
    # 4. jobs of these groups the build did not write (a renamed entry) stay; say so
    written = {j for x in per_group.values() for j in x[3]}
    stale = [os.path.basename(f)[:-5] for stem in per_group
             for f in glob.glob(P.path(P.JOBS_DIR, '%s_*.json' % stem))
             if os.path.basename(f)[:-5] not in written]
    # 5. the render list: the group jobs, then the entries
    lst = ([P.url(P.JOBS_DIR, 'group_%s.json' % stem) for stem in per_group] +
           [P.url(P.JOBS_DIR, j + '.json') for x in per_group.values() for j in x[3]])
    vd = P.version_dir(v)
    save(P.join(vd, 'render_list.json'), lst)
    if os.path.exists(P.path(vd, 'render_done.json')):
        os.remove(P.path(vd, 'render_done.json'))
    for stem, (name, preset, man, jobs) in per_group.items():
        print('  %-6s %-20s %-26s %3d entry jobs' % (name, preset, man, len(jobs)))
    print('%s: %d group jobs + %d entry jobs in %s/, %d failed'
          % (v, len(per_group), len(written), P.JOBS_DIR, len(fails)))
    for x in fails:
        print('  FAIL %s: %s' % x)
    if stale:
        print('  not written by this build (left as they are): %s' % ' '.join(sorted(stale)))
    return lst, fails


def cmd_build(args):
    keep = switch(args, '--keep-presets')
    if not args:
        sys.exit('usage: version.py build <name> [<stem>...] [--keep-presets]')
    v, stems = args[0], set(args[1:])
    lst, fails = write_jobs(v, stems, keep)
    vd = P.version_dir(v)
    print('render list: %s (%d jobs)' % (P.join(vd, 'render_list.json'), len(lst)))
    print('render:  %s?list=%s&done=%s' % (RENDER_PAGE, P.url(vd, 'render_list.json'),
                                           P.join(vd, 'render_done.json')))
    print('then:    python tools/version.py post %s%s' % (v, ''.join(' ' + s for s in sorted(stems))))


# ---- post / pages ---------------------------------------------------------------

PAGE_LINE = re.compile(r'(\S+/\S+)\s+n=\d+ .*?(ok|FAIL)\s+((?:#[0-9a-f]{6},?)+)?\s*$')


def make_pages(v, palettes):
    """entry pages + contact sheets: palettes {(manifest, entry name): 'c0,c1,..'}"""
    def run(item):
        (man, name), pal = item
        tool(v, 'make_entry_page.py', man, name, pal)
        tool(v, 'make_sheet.py', man, name)
    with ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(run, sorted(palettes.items())))
    print('entry pages + sheets: %d' % len(palettes))


def index_pages(v):
    print(tool(v, 'make_index_pages.py').stdout.strip())
    main = P.main_version(P.FAMILY)
    if main and main != v:               # the landing page lists the versions
        tool(main, 'make_index_pages.py')
        print('  and the main version (%s) index pages, for the landing page' % main)


def write_entries(v):
    """versions/<v>/entries.json: what compare.html shows of the version"""
    use(v)
    out = {'version': v, 'family': P.FAMILY, 'label': (P.version_config(v) or {}).get('label', ''),
           'tree': P.family_dir(v), 'groups': []}
    n = 0
    for g in groups():
        gm = group_motif(P.CAT, g['name'], g['stem'])
        ents = []
        for s in entries_of(gm['manifest']):
            nm = entry_names(s['name'], s['index'])
            gen = P.path(P.fam(nm['dir']), 'gen')
            files = sorted(f for f in os.listdir(gen) if f.endswith('.webp')) if os.path.isdir(gen) else []
            if files:
                ents.append({'name': s['name'], 'n': s['index'], 'type': s.get('affineClass') or s['name'],
                             'dir': nm['dir'], 'slug': nm['slug'], 'files': files})
        thumb = P.join(g['stem'], 'gen', 'group.webp')
        out['groups'].append({'name': g['name'], 'stem': g['stem'], 'preset': gm['preset'],
                              'thumb': thumb if os.path.exists(P.path(P.fam(thumb))) else None,
                              'entries': ents})
        n += len(ents)
    save(P.join(P.version_dir(v), 'entries.json'), out)
    print('entries.json: %d rendered color groups' % n)


def checks(stems):
    """H's domain inside the frame; one uncolored pattern per group"""
    import numpy as np
    from PIL import Image
    unbounded_y = bool((P.family_meta() or {}).get('unboundedY'))
    off, odd = [], []
    for s in stems:
        pats = {}
        for d in gen_dirs(s):
            if os.path.basename(os.path.dirname(d)) == s:
                continue                 # the group's own gen/
            entry = os.path.basename(os.path.dirname(d))
            f = os.path.join(d, 'sub_domain.webp')
            if os.path.exists(f):
                a = np.asarray(Image.open(f).convert('RGBA'))[..., 3] > 20
                ys, xs = np.nonzero(a)
                h, w = a.shape
                bad_x = len(xs) and (xs.min() <= 1 or xs.max() >= w - 2)
                bad_y = (not unbounded_y) and len(ys) and (ys.min() <= 1 or ys.max() >= h - 2)
                if bad_x or bad_y:
                    off.append(entry)
            f = os.path.join(d, 'group_pattern.webp')
            if os.path.exists(f):
                pats[entry] = np.asarray(Image.open(f).convert('RGBA')).astype(np.int16)
        if pats:
            ref = np.median(np.stack(list(pats.values())[:15]), axis=0)
            for k, a in pats.items():
                bad = int((np.abs(a - ref).max(-1) > 40).sum())
                if bad > 200:
                    odd.append('%s (%d px)' % (k, bad))
    print('H domain off the frame: %d %s' % (len(off), ' '.join(off)))
    print('uncolored pattern unlike the group\'s others: %d %s' % (len(odd), ' '.join(odd)))


def cmd_post(args):
    sparse = switch(args, '--sparse')
    if not args:
        sys.exit('usage: version.py post <name> [<stem>...] [--sparse]')
    v, only = args[0], set(args[1:])
    use(v)
    if (P.family_meta() or {}).get('sparse'):
        sparse = True
    cfg = P.version_config(v)
    gs = [g for g in groups() if (not only or g['stem'] in only) and g['name'] in cfg['presets']]
    done = P.path(P.version_dir(v), 'render_done.json')
    if os.path.exists(done):
        d = json.load(open(done, encoding='utf-8'))
        print('render: %d/%d jobs, %d images, %s s, %d errors %s'
              % (d['done'], d['total'], d['images'], d['secs'], len(d['errors']), d['errors'][:3]))
    else:
        print('render: no %s - the run has not finished (or was not a list run)' % P.join(P.version_dir(v), 'render_done.json'))
    # 1. verify
    palettes, fails = {}, {}

    def verify(g):
        man = group_motif(P.CAT, g['name'], g['stem'])['manifest']
        return g, man, tool(v, 'verify_entry.py', man, '--all', *(['--sparse'] if sparse else []),
                            check=False).stdout
    with ThreadPoolExecutor(THREADS) as ex:
        for g, man, out in ex.map(verify, gs):
            cur = None
            for line in out.splitlines():
                m = PAGE_LINE.match(line)
                if m:
                    cur = m.group(1)
                    if m.group(3):
                        palettes[(man, cur)] = m.group(3)
                    if m.group(2) == 'FAIL':
                        fails[cur] = []
                elif cur in fails and line.strip():
                    fails[cur].append(line.strip())
            last = out.strip().splitlines()[-1] if out.strip() else '(no output)'
            print('  %-6s %s' % (g['name'], last))
    # 2. WebP
    dirs = [d for g in gs for d in gen_dirs(g['stem']) if glob.glob(os.path.join(d, '*.png'))]
    bad = [d for d in dirs
           if tool(v, 'to_webp.py', '--verify', '--dir', os.path.relpath(d, P.CAT).replace(os.sep, '/'),
                   check=False).returncode]
    print('WebP: %d folders, %d failed %s' % (len(dirs), len(bad), bad[:3]))
    # 3. pages, index pages, entries
    make_pages(v, palettes)
    index_pages(v)
    write_entries(v)
    # 4. checks
    checks([g['stem'] for g in gs])
    print('verify FAIL: %d' % len(fails))
    for k, lines in sorted(fails.items()):
        print('  %s | %s' % (k, ' / '.join(lines)[:300]))
    print('compare: python tools/version.py compare')


def page_palettes(v):
    """{(manifest, entry name): palette} of the entry pages the version has"""
    use(v)
    out = {}
    for g in groups():
        man = group_motif(P.CAT, g['name'], g['stem'])['manifest']
        for s in entries_of(man):
            page = P.path(P.fam(entry_names(s['name'], s['index'])['dir']), 'index.html')
            if os.path.exists(page):
                css = open(page, encoding='utf-8').read()
                pal = [c for _, c in sorted((int(k), c) for k, c in
                                            re.findall(r'\.sw(\d+) \{ background: (#[0-9a-fA-F]+); \}', css))]
                out[(man, s['name'])] = ','.join(pal)
    return out


def cmd_pages(args):
    if len(args) != 1:
        sys.exit('usage: version.py pages <name>')
    v = args[0]
    make_pages(v, page_palettes(v))
    index_pages(v)
    write_entries(v)


# ---- promote -------------------------------------------------------------------

def cmd_promote(args):
    if len(args) != 1:
        sys.exit('usage: version.py promote <name>')
    v = args[0]
    reg = use(v)
    old = reg['main']
    if old == v:
        sys.exit('%s is the main version already' % v)
    root = [P.TREE, P.JOBS]
    here = [P.join(P.VERSIONS_DIR, v, d) for d in root]
    if not all(os.path.isdir(P.path(d)) for d in here):
        sys.exit('%s has no page tree and jobs (%s): build and render it first' % (v, ', '.join(here)))
    if old:
        away = [P.join(P.VERSIONS_DIR, old, d) for d in root]
        for d in away:
            if os.path.exists(P.path(d)):
                sys.exit('%s is in the way' % d)
        for a, b in zip(root, away):
            if os.path.exists(P.path(a)):
                shutil.move(P.path(a), P.path(b))
    elif any(os.path.exists(P.path(d)) for d in root):
        sys.exit('wp/ and jobs/ are of no version: make them one first (version.py new <name> --main)')
    for a, b in zip(here, root):
        shutil.move(P.path(a), P.path(b))
    reg['main'] = v
    save(P.join(P.VERSIONS_DIR, 'index.json'), reg)
    print('main version: %s (was %s)' % (v, old))
    for w in [v] + ([old] if old else []):
        print('--- %s: jobs and pages again' % w)
        write_jobs(w, keep=True)
        make_pages(w, page_palettes(w))
        index_pages(w)
        write_entries(w)


# ---- list / compare ----------------------------------------------------------------

def built(v):
    tree = P.path(P.family_dir(v))
    return len(glob.glob(os.path.join(tree, '*', '*', '*', 'index.html')))


def cmd_list(args):
    reg = P.registry()
    if not reg['versions']:
        print('no versions (python tools/version.py new ...)')
    for v, meta in reg['versions'].items():
        cfg = P.version_config(v) or {}
        done = P.path(P.version_dir(v), 'render_done.json')
        d = json.load(open(done, encoding='utf-8')) if os.path.exists(done) else None
        print('%-4s %-12s %-10s set %-8s %3d entry pages in %-18s %s%s'
              % ('main' if v == reg['main'] else '', v, meta.get('created', ''), cfg.get('set', '?'),
                 built(v), P.family_dir(v) + '/',
                 ('last render %d/%d jobs, %d errors' % (d['done'], d['total'], len(d['errors']))) if d else '',
                 ('  - ' + meta['label']) if meta.get('label') else ''))


def cmd_compare(args):
    reg = P.registry()
    others = sorted((v for v in reg['versions'] if v != reg['main']),
                    key=lambda v: reg['versions'][v].get('created', ''))
    a = args[0] if len(args) > 0 else reg['main']
    b = args[1] if len(args) > 1 else (others[-1] if others else None)
    if not a or not b:
        sys.exit('need two versions to compare: %s' % ', '.join(reg['versions']))
    names = {}
    for v in (a, b):
        f = P.path(P.version_dir(v), 'entries.json')
        if not os.path.exists(f):
            sys.exit('%s has no entries.json: version.py post %s (or pages %s)' % (v, v, v))
        e = json.load(open(f, encoding='utf-8'))
        names[v] = {x['name'] for g in e['groups'] for x in g['entries']}
    print('%s: %d rendered color groups, %s: %d, both: %d'
          % (a, len(names[a]), b, len(names[b]), len(names[a] & names[b])))
    print('%scompare.html?a=%s&b=%s' % (CATALOG_SITE, a, b))


COMMANDS = {'new': cmd_new, 'build': cmd_build, 'post': cmd_post, 'pages': cmd_pages,
            'promote': cmd_promote, 'list': cmd_list, 'compare': cmd_compare}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit('usage: version.py %s ... (see the head of tools/version.py)' % '|'.join(COMMANDS))
    COMMANDS[sys.argv[1]](sys.argv[2:])
