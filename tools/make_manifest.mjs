/*
  make_manifest.mjs — T2 of the catalog toolchain.

  Enumerates the subgroups of a wallpaper group, classifies each one, runs the
  SubgroupDomain builder (T1, SymmHub) for the canonical cells / transversal /
  pairing generators, and writes one JSON manifest per group:

      node tools/make_manifest.mjs [group] [maxIndex]
      node tools/make_manifest.mjs 632 6

  output:  data/<stem>.json        (stem: '*632' -> 's632')
           data/index.json         (list of generated manifests)

  Group theory comes from sublib (the standalone copy, which carries
  subgroupStructure); geometry comes from SymmHub's grouplib + SubgroupDomain.
  Words follow the project convention: composition left to right,
  uppercase = inverse.  Terminology: cosets and orbits, never left/right.
*/

import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SUBLIB = 'file:///D:/home/projects/00.docs/250117_colorsym/wieting/sublib/src/sublib.js';
const SYMMHUB = 'file:///D:/home/projects/00.docs/250125_symhub/repo_v2/SymmHub';

const { subgroupsData, subgroupStructure, permStringToArrays, WALLPAPER_NAMES,
        getPreset, fileStem } = await import(SUBLIB);
const { iWallpaperGroup } = await import(SYMMHUB + '/lib/grouplib/WallpaperGroups.js');
const { Group, ITransform, iPoint } = await import(SYMMHUB + '/lib/invlib/invlib.js');
const { buildSubgroupDomain, classifyEuclidean, isometryToString, sameTransform } =
  await import(SYMMHUB + '/lib/grouplib/SubgroupDomain.js');
const { reidemeisterSchreier } = await import('./reidemeister.mjs');
const { computeFrame, subgroupKey } =
  await import(SYMMHUB + '/lib/grouplib/SubgroupKey.js');

const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'data');

// the five orientation preserving wallpaper types (rotations only)
const DIRECT_TYPES = new Set(['o', '2222', '442', '333', '632']);

// geometry parameter used for all groups (matches the app's Group_WP default)
const GEOMETRY_A = 0.5;

const TEST_POINTS = [iPoint([0.12345, 0.06789, 0, 0]), iPoint([-0.07211, 0.16183, 0, 0])];
const IDENTITY = new ITransform([], '');

// ---------------------------------------------------------------------------
// relator expansion: 'a^2, b^3, (a*b)^6, b*c'  ->  ['aa','bbb','ababab...','bc']
// ---------------------------------------------------------------------------

function expandRelator(rel){
  // strip whitespace, split off  (...)^k  and  x^k  pieces, drop '*'
  let s = rel.replace(/\s+/g, '');
  let out = '';
  while(s.length > 0){
    let m;
    if((m = s.match(/^\(([^)]*)\)\^(\d+)/))){
      out += expandRelator(m[1]).repeat(Number(m[2]));
      s = s.slice(m[0].length);
    } else if((m = s.match(/^\(([^)]*)\)/))){
      out += expandRelator(m[1]);
      s = s.slice(m[0].length);
    } else if((m = s.match(/^([a-zA-Z])\^(\d+)/))){
      out += m[1].repeat(Number(m[2]));
      s = s.slice(m[0].length);
    } else if(s[0] === '*'){
      s = s.slice(1);
    } else if(/[a-zA-Z]/.test(s[0])){
      out += s[0];
      s = s.slice(1);
    } else {
      throw new Error(`cannot parse relator '${rel}' at '${s}'`);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// words as geometry
// ---------------------------------------------------------------------------

function makeGens(group){
  const names = group.getGenNames();
  const gens = {};
  names.forEach((name, i) => {
    gens[name] = new ITransform(group.transforms[i].slice(), name);
  });
  return gens;
}

function wordToITransform(gens, word){
  let t = new ITransform([], '');
  for(const ch of word){
    const lower = ch.toLowerCase();
    t = t.concat(ch === lower ? gens[ch] : gens[lower].getInverse());
  }
  return t;
}

/** verify that the geometric generators satisfy the presentation's relators */
function checkCorrespondence(group, presentation){
  const gens = makeGens(group);
  const relators = String(presentation.relators).split(',').map(r => expandRelator(r));
  const bad = relators.filter(r => !sameTransform(wordToITransform(gens, r), IDENTITY, TEST_POINTS));
  return { ok: bad.length === 0, badRelators: bad };
}

// ---------------------------------------------------------------------------
// classification of the subgroup's own wallpaper type
// ---------------------------------------------------------------------------

/**
  primary decomposition of a torsion list: [6] and [2,3] both become [2,3],
  so differently spelled but isomorphic homology gives the same key
*/
function primaryTorsion(torsion){
  const out = [];
  for(let t of torsion){
    for(let p = 2; p * p <= t; p++){
      while(t % p === 0){
        let q = p;
        while(t % (q * p) === 0) q *= p;
        out.push(q);
        t /= q;
      }
    }
    if(t > 1) out.push(t);
  }
  return out.sort((x, y) => x - y);
}

/*
  H's own wallpaper type is identified by an isomorphism invariant fingerprint:

    - subgroup growth: how many conjugacy classes of subgroups H has at each
      index 1..GROWTH_DEPTH, computed from a Reidemeister-Schreier
      presentation of H (presentation independent by construction)
    - first homology: rank and primary torsion

  Growth to depth 6 leaves three ambiguous pairs; homology splits two of them
  (** vs 22*, *x vs 22x) and depth 7 splits the last (3*3 vs 632: zero vs two
  subgroups of index 7).  Depth 8 is used for margin, and the references are
  checked to be pairwise distinct at startup.
*/
const GROWTH_DEPTH = 8;

function growthVector(d){
  const v = new Array(GROWTH_DEPTH).fill(0);
  for(const e of d.countPerIndex) if(e.index <= GROWTH_DEPTH) v[e.index - 1] = e.count;
  return v;
}

function makeReferenceFingerprints(){
  const ref = new Map();
  for(const name of WALLPAPER_NAMES){
    const d = subgroupsData({ preset: 'wallpaper:' + name, maxIndex: GROWTH_DEPTH, generators: 'none' });
    const st = subgroupStructure(d, d.subgroups[0].subgroup);
    const key = JSON.stringify([growthVector(d), st.abelianization.rank,
                                primaryTorsion(st.abelianization.torsion)]);
    if(ref.has(key))
      throw new Error(`reference fingerprints collide: ${ref.get(key)} vs ${name}`);
    ref.set(key, name);
  }
  return ref;
}

/** identify the wallpaper type of the subgroup with the given coset table */
function classifySubgroupType(perms, expandedRelators, st, refFingerprints){
  let rs;
  try {
    rs = reidemeisterSchreier({ perms, relators: expandedRelators });
  } catch(e){
    return { type: null, note: 'reidemeister: ' + e.message };
  }
  const sd = subgroupsData({ name: 'h', gens: rs.gens, relators: rs.relators,
                             maxIndex: GROWTH_DEPTH, generators: 'none' });
  const key = JSON.stringify([growthVector(sd), st.abelianization.rank,
                              primaryTorsion(st.abelianization.torsion)]);
  const type = refFingerprints.get(key);
  return type ? { type } : { type: null, note: 'fingerprint not recognized: ' + key };
}

// ---------------------------------------------------------------------------
// placements: [G : N_G(H)] = n / |centralizer of the coset action|
// ---------------------------------------------------------------------------

function countPlacements(cosets){
  const perms = permStringToArrays(cosets);
  const n = perms[0].length;
  let central = 0;
  for(let target = 0; target < n; target++){
    const s = new Array(n).fill(-1);
    s[0] = target;
    const queue = [0];
    let ok = true;
    while(queue.length && ok){
      const i = queue.shift();
      for(const p of perms){
        const gi = p[i], gs = p[s[i]];
        if(s[gi] === -1){ s[gi] = gs; queue.push(gi); }
        else if(s[gi] !== gs){ ok = false; break; }
      }
    }
    if(ok && s.every(v => v !== -1) && new Set(s).size === n) central++;
  }
  return n / central;
}

// ---------------------------------------------------------------------------
// cycle notation of a permutation, for the color action table
// ---------------------------------------------------------------------------

function cyclesOf(perm){
  const seen = new Array(perm.length).fill(false);
  const cycles = [];
  for(let i = 0; i < perm.length; i++){
    if(seen[i]) continue;
    const cyc = [];
    let j = i;
    while(!seen[j]){ seen[j] = true; cyc.push(j); j = perm[j]; }
    if(cyc.length > 1) cycles.push(cyc);
  }
  return cycles.length === 0 ? 'e'
       : cycles.map(c => '(' + c.join(' ') + ')').join('');
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

const groupName = process.argv[2] || '632';
const maxIndex = Number(process.argv[3] || 6);

const presentation = getPreset('wallpaper:' + groupName);
const data = subgroupsData({ preset: 'wallpaper:' + groupName, maxIndex, generators: 'none' });

const group = new Group(iWallpaperGroup({ name: groupName, a: GEOMETRY_A }));
const genCountMatch = group.getFundDomain().length === presentation.gens.split(/\s+/).length;
const corr = genCountMatch ? checkCorrespondence(group, presentation)
                           : { ok: false, badRelators: ['generator count mismatch'] };
if(!corr.ok)
  console.warn(`WARNING ${groupName}: geometry does not satisfy the presentation ` +
               `(${corr.badRelators.join(', ')}) - geometric fields omitted`);

const refFingerprints = makeReferenceFingerprints();
const frame = corr.ok ? computeFrame(group) : null;
const expandedRelators = String(presentation.relators).split(',').map(r => expandRelator(r));

const subgroups = [];
for(const sub of data.subgroups){

  const st = subgroupStructure(data, sub.subgroup);
  const perms = permStringToArrays(sub.cosets);
  const placements = countPlacements(sub.cosets);

  let domain = null;
  if(corr.ok){
    domain = buildSubgroupDomain({ group, cosets: sub.cosets, testPoints: TEST_POINTS });
  }

  const cls = classifySubgroupType(perms, expandedRelators, st, refFingerprints);

  const entry = {
    id: sub.subgroup,                    // sublib id: stable only within this file
    index: sub.index,
    type: cls.type,
    ...(cls.note ? { typeNote: cls.note } : {}),
    normal: placements === 1,
    placements,
    cosets: sub.cosets,
    orders: st.orders,
    abelianization: st.abelianization.text,
    colorAction: presentation.gens.split(/\s+/).map((g, k) => ({
      generator: g,
      perm: perms[k],
      cycles: cyclesOf(perms[k]),
    })),
  };

  if(frame){
    try {
      const gk = subgroupKey({ group, frame, cosets: sub.cosets });
      entry.geoKey = gk.key;
      entry.latticeHNF = gk.hnf;
      entry.latticeIndex = gk.latticeIndex;
      entry.pointIndex = gk.pointIndex;
    } catch(e){
      console.warn(`WARNING ${sub.subgroup}: no geometric key (${e.message})`);
    }
  }

  if(domain){
    // f_i: the domain's cells, one per orbit class; g_j: the coset transversal
    entry.orbitReps = domain.cells.map(c => ({
      word: c.word === '' ? 'e' : c.word,
      isometry: classifyEuclidean(c.itrans),
      text: isometryToString(classifyEuclidean(c.itrans)),
    }));
    entry.transversal = domain.cosetTransversal.map(t => ({
      word: t.word === '' ? 'e' : t.word,
      isometry: classifyEuclidean(t.itrans),
      text: isometryToString(classifyEuclidean(t.itrans)),
    }));
    entry.simplyConnected = domain.simplyConnected;
    entry.hGenerators = domain.generators.map(gi => ({
      word: domain.pairings[gi].word,
      isometry: domain.pairings[gi].isometry,
      text: isometryToString(domain.pairings[gi].isometry),
    }));
    entry.sideCounts = {
      boundary: domain.sides.filter(s => s.kind === 'boundary').length,
      interior: domain.sides.filter(s => s.kind === 'interior').length,
    };
  }

  subgroups.push(entry);
}

// display names: G/H[n]#k — the ordinal k comes from sorting each
// (type, index) bucket by the geometric key, so it is reproducible and
// survives a change of the group's fundamental domain
{
  const buckets = new Map();
  for(const s of subgroups){
    const b = `${s.type}[${s.index}]`;
    if(!buckets.has(b)) buckets.set(b, []);
    buckets.get(b).push(s);
  }
  for(const [b, arr] of buckets){
    arr.sort((p, q) => (p.geoKey || p.cosets) < (q.geoKey || q.cosets) ? -1 : 1);
    arr.forEach((s, i) => {
      s.name = `${groupName}/${s.type}[${s.index}]` + (arr.length > 1 ? '#' + (i + 1) : '');
    });
  }
}

const manifest = {
  format: 'colorsym-catalog-manifest',
  version: 2,
  group: {
    name: groupName,
    stem: fileStem(groupName),
    family: 'wallpaper',
    gens: presentation.gens,
    relators: presentation.relators,
    geometry: { a: GEOMETRY_A },
    geometryVerified: corr.ok,
    ...(frame ? { frame: { origin: frame.origin, t1: frame.t1, t2: frame.t2,
                           maxOrder: frame.maxOrder } } : {}),
  },
  maxIndex,
  totalCount: data.totalCount,
  countPerIndex: data.countPerIndex,
  subgroups,
};

mkdirSync(OUT_DIR, { recursive: true });
const outFile = join(OUT_DIR, fileStem(groupName) + '.json');
writeFileSync(outFile, JSON.stringify(manifest, null, 1));

// keep data/index.json current
const indexFile = join(OUT_DIR, 'index.json');
const index = existsSync(indexFile) ? JSON.parse(readFileSync(indexFile, 'utf8'))
                                    : { format: 'colorsym-catalog-index', groups: [] };
const rec = { name: groupName, stem: fileStem(groupName), file: fileStem(groupName) + '.json',
              maxIndex, totalCount: data.totalCount };
const at = index.groups.findIndex(g => g.name === groupName);
if(at >= 0) index.groups[at] = rec; else index.groups.push(rec);
writeFileSync(indexFile, JSON.stringify(index, null, 1));

console.log(`${groupName}: ${subgroups.length} subgroups to index ${maxIndex} -> ${outFile}`);
for(const s of subgroups){
  console.log(`  ${(s.name || s.id).padEnd(16)} placements ${s.placements}` +
              `${s.normal ? ' (normal)' : ''}  (${s.id})`);
}
