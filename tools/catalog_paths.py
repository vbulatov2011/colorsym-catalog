# Where the catalog keeps things - the Python tools' paths, from catalog_paths.json
# (tools/catalog_paths.mjs reads the same file for the node tools).
#
# A path here is relative to the catalog root CAT and '/'-separated:
#   path(rel)       its file on disk
#   url(rel)        its server URL (/catalog/...); from_url() goes back
#   fam(rel)        a path in the family's page tree, made root-relative - an
#                   entry's dir (entry_names) is family-relative: 632/3/632-632-3
#   up(rel_dir)     the '../' run from a root-relative folder back to the root,
#                   for a page's links to site-wide files (css/, compare.html)
#   data_file(s)    the manifest data/<family>/<s>.json   job_file(j)  <jobs>/<j>.json
#
# Families.  catalog_paths.json lists each family under "families" (wp now;
# frieze, spherical, hyperbolic later).  CATALOG_FAMILY selects one; use_family()
# switches.  Each family keeps its UI/group metadata in data/<family>/family.json.
#
# Versions.  A version is one complete rendering of the family from presets of
# its own: versions/<name>/version.json says which preset each group takes,
# and the build copies them into versions/<name>/presets/ (a snapshot), which
# the version's jobs render.  versions/index.json lists the versions and names
# the main one.  The main version's pages and jobs are the catalog's own -
# <familyDir>/ and <jobsDir>/ at the root; any other version keeps them under
# versions/<name>/.  The tools work on one version: CATALOG_VERSION in the
# environment, else the main one; use_version() switches.
import html, json, os

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG = json.load(open(os.path.join(CAT, 'tools', 'catalog_paths.json'), encoding='utf-8'))

URL_ROOT = _CFG['urlRoot']
VERSIONS_DIR = _CFG['versionsDir']

_EXT = _CFG.get('external', {})
SYMMHUB_DIR = os.environ.get('SYMMHUB_DIR') or _EXT.get('symmhubDir') or 'D:/home/projects/00.docs/250125_symhub/repo_v2/SymmHub'
SUBLIB_PATH = os.environ.get('SUBLIB_PATH') or _EXT.get('sublibPath') or (SYMMHUB_DIR.rstrip('/') + '/lib/sublib/src/sublib.js')
SYMMHUB_URL = (os.environ.get('SYMMHUB_URL') or _EXT.get('symmhubUrl') or 'http://localhost:8125').rstrip('/')

FAMILIES = _CFG.get('families') or {
    _CFG['family']: {
        'familyDir': _CFG['familyDir'],
        'dataDir': _CFG['dataDir'],
        'jobsDir': _CFG['jobsDir'],
        'presetsDir': _CFG['presetsDir'],
    }
}
DEFAULT_FAMILY = _CFG.get('defaultFamily') or _CFG['family']


def join(*parts):
    """'/'-join of root-relative parts; empty ones ('' = the root) drop out"""
    return '/'.join(p.strip('/') for p in parts if p and p.strip('/'))


def path(*rel):
    return os.path.join(CAT, *join(*rel).split('/'))


def url(*rel):
    return URL_ROOT + '/' + join(*rel)


def from_url(u):
    assert u.startswith(URL_ROOT + '/'), 'not a catalog URL (%s/...): %r' % (URL_ROOT, u)
    return u[len(URL_ROOT) + 1:]


def up(rel_dir):
    return '../' * len(join(rel_dir).split('/')) if join(rel_dir) else ''


# ---- families ----------------------------------------------------------------

FAMILY = None
TREE = None
JOBS = None
DATA_DIR = None
PRESETS_DIR = None
META_FILE = None


def family_cfg(f=None):
    f = f or FAMILY or DEFAULT_FAMILY
    return FAMILIES[f]


def family_meta(f=None):
    """load data/<family>/family.json if present, else {}"""
    fc = family_cfg(f)
    mf = fc.get('metaFile') or join(fc['dataDir'], 'family.json')
    p = path(mf)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def use_family(f):
    global FAMILY, TREE, JOBS, DATA_DIR, PRESETS_DIR, META_FILE
    if f not in FAMILIES:
        raise KeyError('unknown catalog family %r (known: %s)' % (f, ', '.join(FAMILIES)))
    fc = FAMILIES[f]
    FAMILY = f
    TREE = fc['familyDir']
    JOBS = fc['jobsDir']
    DATA_DIR = fc['dataDir']
    PRESETS_DIR = fc['presetsDir']
    META_FILE = fc.get('metaFile') or join(DATA_DIR, 'family.json')
    cur = VERSION
    if cur is not None:
        vcfg = version_config(cur)
        if vcfg and (vcfg.get('family') or DEFAULT_FAMILY) != f:
            cur = main_version(f)
    else:
        cur = main_version(f)
    use_version(cur)


# ---- versions ----------------------------------------------------------------

def registry():
    """versions/index.json: {"main": name, "mainByFamily": {...}, "versions": {name: {"label": ..}}}"""
    f = path(VERSIONS_DIR, 'index.json')
    return (json.load(open(f, encoding='utf-8')) if os.path.exists(f)
            else {'main': None, 'versions': {}})


def main_version(f=None):
    """the main version name for family f (default: active FAMILY)"""
    fam = f or FAMILY or DEFAULT_FAMILY
    reg = registry()
    mbf = reg.get('mainByFamily') or {}
    if fam in mbf:
        return mbf[fam]
    return reg.get('main') if fam == DEFAULT_FAMILY else None


def is_main(v=None, f=None):
    v = v or VERSION
    mv = main_version(f)
    return v is None or v == mv


def version_root(v=None, f=None):
    """the folder holding a version's page tree and jobs: the root for the main one"""
    v = v or VERSION
    return '' if is_main(v, f) else join(VERSIONS_DIR, v)


def family_dir(v=None, f=None):
    """a version's page tree: <familyDir>/ for the main one, versions/<name>/<familyDir>/ else"""
    tree = family_cfg(f)['familyDir'] if f else TREE
    return join(version_root(v, f), tree)


def jobs_dir(v=None, f=None):
    jobs = family_cfg(f)['jobsDir'] if f else JOBS
    return join(version_root(v, f), jobs)


def version_dir(v=None):
    """versions/<name>/: the version's config, preset snapshot, render list"""
    return join(VERSIONS_DIR, v or VERSION)


def version_config(v=None):
    v = v or VERSION
    f = path(version_dir(v), 'version.json') if v else None
    return json.load(open(f, encoding='utf-8')) if f and os.path.exists(f) else None


def snapshot(src, v=None):
    """a preset's copy in the version: presets/wp/wpe/x.json -> versions/<v>/presets/wp/wpe/x.json"""
    return join(version_dir(v), src)


def version_preset(name, v=None):
    """the snapshot of the preset group `name` renders in the version, or None"""
    cfg = version_config(v)
    if not cfg or (cfg.get('family') or DEFAULT_FAMILY) != (FAMILY or DEFAULT_FAMILY):
        return None
    src = cfg['presets'].get(name)
    return snapshot(src, v) if src else None


def use_version(v):
    global VERSION, FAMILY_DIR, JOBS_DIR
    VERSION = v
    FAMILY_DIR = family_dir(v)
    JOBS_DIR = jobs_dir(v)


VERSION = None
use_family(os.environ.get('CATALOG_FAMILY') or DEFAULT_FAMILY)
if os.environ.get('CATALOG_VERSION'):
    use_version(os.environ['CATALOG_VERSION'])


def version_note(site):
    """the note heading a page of a version other than the main one, '' on the
    main version's pages; site: the way up from the page to the catalog root"""
    if is_main():
        return ''
    label = (version_config() or {}).get('label')
    return ('<p class="version">Version <b>%s</b>%s &mdash; a rendering to compare, not the '
            'main catalog. <a href="%scompare.html?b=%s">Compare with the main version</a> '
            '&middot; <a href="%sindex.html">Main catalog</a></p>'
            % (html.escape(VERSION), ' (%s)' % html.escape(label) if label else '',
               site, VERSION, site))


def compare_link(site, entry=None):
    """the compare page (compare.html) on this version and the main one, at an entry"""
    from urllib.parse import quote
    q = ['entry=' + quote(entry, safe='')] if entry else []
    if not is_main():
        q.append('b=' + VERSION)
    return site + 'compare.html' + ('?' + '&amp;'.join(q) if q else '')


# ---- the version's files ------------------------------------------------------

def fam(*rel):
    return join(FAMILY_DIR, *rel)


def data_file(stem):
    return path(DATA_DIR, stem + '.json')


def job_file(name):
    return path(JOBS_DIR, name + '.json')
