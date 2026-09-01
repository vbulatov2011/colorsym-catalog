/*
  make_gap_id_map.mjs — record how the GAP-era subgroup ids map to the ids
  sublib now produces.

  The ids are enumeration-order artefacts and do not survive the switch to
  computed tables: for the 17 wallpaper groups only 360 of 4847 ids still name
  the same subgroup.  The coset permutation string is the real identity, so this
  table is keyed by it and exists only so that an old reference can still be
  looked up.

      node tools/make_gap_id_map.mjs          ->  data/gap_id_map.json
*/
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SYMMHUB = 'D:/home/projects/00.docs/250125_symhub/repo_v2/SymmHub';
const { subgroupsData, findByPermutations } =
  await import('file:///' + SYMMHUB + '/lib/sublib/src/sublib.js');

const DIR = SYMMHUB + '/apps/sympix/color_groups/';
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'data');
const norm = s => String(s).trim().split(/\s+/).join(' ');

const families = { wallpaper: 'wallpaper:', klm: 'klm:', '*klm': 'sklm:' };
const out = { format: 'gap-to-sublib-subgroup-ids', version: 1,
              note: 'keyed by coset permutation string, which is the identity; ' +
                    'ids are enumeration order and are not stable',
              groups: {} };
let same = 0, renamed = 0, byRep = 0, missing = 0;

for (const [famDir, prefix] of Object.entries(
        { wallpaper: 'wallpaper:', klm: 'klm:', sklm: 'sklm:' })) {
  let manifest;
  try { manifest = JSON.parse(readFileSync(DIR + famDir + '/groups.json', 'utf8')); }
  catch { continue; }

  for (const g of manifest.groups) {
    const shipped = JSON.parse(readFileSync(DIR + famDir + '/' + g.file, 'utf8'));
    let live;
    try { live = subgroupsData({ preset: prefix + g.name, maxIndex: shipped.maxIndex }); }
    catch { continue; }

    const byCosets = new Map(live.subgroups.map(s => [norm(s.cosets), s.subgroup]));
    const entries = [];
    for (const s of shipped.subgroups) {
      const key = norm(s.cosets);
      let newId = byCosets.get(key), how = 'cosets';
      if (!newId) {
        const hit = findByPermutations(live, s.cosets, { upToConjugacy: true });
        if (hit) { newId = hit.subgroup; how = 'conjugate'; byRep++; }
        else { missing++; continue; }
      } else if (newId === s.subgroup) { same++; } else { renamed++; }
      entries.push({ gap: s.subgroup, sublib: newId, index: s.index,
                     cosets: key, ...(how === 'conjugate' ? { matchedUpToConjugacy: true } : {}) });
    }
    out.groups[famDir + '/' + g.name] = entries;
  }
}
out.stats = { idUnchanged: same, idRenamed: renamed,
              matchedUpToConjugacy: byRep, unmatched: missing };
mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, 'gap_id_map.json'), JSON.stringify(out));
console.log('groups mapped:', Object.keys(out.groups).length);
console.log(out.stats);
