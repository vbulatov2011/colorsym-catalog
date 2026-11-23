// Where the catalog keeps things - the node tools' paths, from catalog_paths.json
// (tools/catalog_paths.py reads the same file for the Python tools).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const CAT = join(dirname(fileURLToPath(import.meta.url)), '..');
const cfg = JSON.parse(readFileSync(join(CAT, 'tools', 'catalog_paths.json'), 'utf8'));

export const FAMILIES = cfg.families || {
  [cfg.family]: {
    familyDir: cfg.familyDir,
    dataDir: cfg.dataDir,
    jobsDir: cfg.jobsDir,
    presetsDir: cfg.presetsDir,
  },
};

export const FAMILY = process.env.CATALOG_FAMILY || cfg.defaultFamily || cfg.family;
const famCfg = FAMILIES[FAMILY] || {
  familyDir: cfg.familyDir,
  dataDir: cfg.dataDir,
  jobsDir: cfg.jobsDir,
  presetsDir: cfg.presetsDir,
};

// the family's manifests (data/<family>/<stem>.json, index.json, gap_id_map.json)
export const DATA_DIR = join(CAT, ...famCfg.dataDir.split('/'));
export const PRESETS_DIR = join(CAT, ...famCfg.presetsDir.split('/'));

const ext = cfg.external || {};
export const SYMMHUB_DIR = process.env.SYMMHUB_DIR || ext.symmhubDir
  || 'D:/home/projects/00.docs/250125_symhub/repo_v2/SymmHub';
export const SYMMHUB_URL = pathToFileURL(SYMMHUB_DIR).href.replace(/\/$/, '');
export const SUBLIB_PATH = process.env.SUBLIB_PATH || ext.sublibPath
  || join(SYMMHUB_DIR, 'lib', 'sublib', 'src', 'sublib.js');
export const SUBLIB_URL = pathToFileURL(SUBLIB_PATH).href;
