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
#   data_file(s)    the manifest data/wp/<s>.json   job_file(j)  <jobs>/<j>.json
#
# Versions.  A version is one complete rendering of the family from presets of
# its own: versions/<name>/version.json says which preset each group takes,
# and the build copies them into versions/<name>/presets/ (a snapshot), which
# the version's jobs render.  versions/index.json lists the versions and names
# the main one.  The main version's pages and jobs are the catalog's own -
# <familyDir>/ and <jobsDir>/ at the root; any other version keeps them under
# versions/<name>/.  The tools work on one version: CATALOG_VERSION in the
# environment, else the main one; use_version() switches.  Before any version
# exists the paths are the root's, as they were.
import html, json, os

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG = json.load(open(os.path.join(CAT, 'tools', 'catalog_paths.json'), encoding='utf-8'))

URL_ROOT = _CFG['urlRoot']
FAMILY = _CFG['family']
DATA_DIR = _CFG['dataDir']
PRESETS_DIR = _CFG['presetsDir']
VERSIONS_DIR = _CFG['versionsDir']


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


# ---- versions ----------------------------------------------------------------

def registry():
    """versions/index.json: {"main": name, "versions": {name: {"label": ..}}}"""
    f = path(VERSIONS_DIR, 'index.json')
    return (json.load(open(f, encoding='utf-8')) if os.path.exists(f)
            else {'main': None, 'versions': {}})


def is_main(v=None):
    v = v or VERSION
    return v is None or v == registry()['main']


def version_root(v=None):
    """the folder holding a version's page tree and jobs: the root for the main one"""
    v = v or VERSION
    return '' if is_main(v) else join(VERSIONS_DIR, v)


TREE, JOBS = _CFG['familyDir'], _CFG['jobsDir']     # their names, in any version's root


def family_dir(v=None):
    """a version's page tree: wp/ for the main one, versions/<name>/wp/ else"""
    return join(version_root(v), TREE)


def jobs_dir(v=None):
    return join(version_root(v), JOBS)


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
    src = cfg and cfg['presets'].get(name)
    return snapshot(src, v) if src else None


def use_version(v):
    global VERSION, FAMILY_DIR, JOBS_DIR
    VERSION = v
    FAMILY_DIR = family_dir(v)
    JOBS_DIR = jobs_dir(v)


VERSION = None
use_version(os.environ.get('CATALOG_VERSION') or registry()['main'])


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
