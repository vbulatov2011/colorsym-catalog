# Where the catalog keeps things - the Python tools' paths, from catalog_paths.json
# (tools/catalog_paths.mjs reads the same file for the node tools).
#
# A path here is relative to the catalog root CAT and '/'-separated:
#   path(rel)       its file on disk
#   url(rel)        its server URL (/catalog/...); from_url() goes back
#   fam(rel)        a path in the family's page tree, made root-relative - an
#                   entry's dir (entry_names) is family-relative: 632/3/632-632-3
#   up(rel_dir)     the '../' run from a root-relative folder back to the root,
#                   for a page's links to site-wide files (css/)
#   data_file(s)    the manifest data/<s>.json      job_file(j)  jobs/<j>.json
import json, os

CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CFG = json.load(open(os.path.join(CAT, 'tools', 'catalog_paths.json'), encoding='utf-8'))

URL_ROOT = _CFG['urlRoot']
FAMILY = _CFG['family']
FAMILY_DIR = _CFG['familyDir']
DATA_DIR = _CFG['dataDir']
JOBS_DIR = _CFG['jobsDir']
PRESETS_DIR = _CFG['presetsDir']


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


def fam(*rel):
    return join(FAMILY_DIR, *rel)


def up(rel_dir):
    return '../' * len(join(rel_dir).split('/')) if join(rel_dir) else ''


def data_file(stem):
    return path(DATA_DIR, stem + '.json')


def job_file(name):
    return path(JOBS_DIR, name + '.json')
