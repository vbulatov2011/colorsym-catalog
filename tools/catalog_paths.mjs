// Where the catalog keeps things - the node tools' paths, from catalog_paths.json
// (tools/catalog_paths.py reads the same file for the Python tools).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const CAT = join(dirname(fileURLToPath(import.meta.url)), '..');
const cfg = JSON.parse(readFileSync(join(CAT, 'tools', 'catalog_paths.json'), 'utf8'));

export const FAMILY = cfg.family;
// the family's manifests (data/<stem>.json, index.json, gap_id_map.json)
export const DATA_DIR = join(CAT, ...cfg.dataDir.split('/'));
