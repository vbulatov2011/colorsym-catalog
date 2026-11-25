/*
  make_manifest.mjs — T2 of the catalog toolchain.

  Enumerates the subgroups of a wallpaper group, classifies each one, runs the
  SubgroupDomain builder (T1, SymmHub) for the canonical cells / transversal /
  pairing generators, and writes one JSON manifest per group:

      node tools/make_manifest.mjs [group] [maxIndex] [--domain "<shape>"]
                                   [--dirichlet <preset.json>]
      node tools/make_manifest.mjs 632 6
      node tools/make_manifest.mjs 632 8 --domain "6-2-3-2 kite"
      node tools/make_manifest.mjs 333 7 --dirichlet presets/wp/wpe/wpe-333-3.json

  --domain builds G on that fundamental domain (WallpaperDomainShapes) and
  derives the presentation from its geometry (GroupPresentation.js) instead
  of taking sublib's catalogue preset: other generators, other coset tables,
  other f/g words - but the same names, since a name is keyed by the
  conjugacy class.  It writes data/wp/<stem>@<shape>.json ('6-2-3-2 kite' ->
  632@6-2-3-2-kite.json) and leaves data/wp/<stem>.json and index.json alone.

  --dirichlet takes the Dirichlet domain the preset turns on (its
  symmetry.dirichlet: base point and side words; tools/render/dirichlet_group.mjs
  builds it as the renderer does) as the cell H's domain is made of.  The
  presentation, the coset tables, the names and keys stay those of G's own
  domain; the cells, the f/g words, H's generators and side counts come from the
  Dirichlet cells, their words written back in G's generators.  It writes
  data/wp/<stem>@dirichlet.json (632@...-kite@dirichlet.json with --domain too),
  the base and words recorded under group.dirichlet.

  output:  data/wp/<stem>.json     (stem: '*632' -> 's632')
           data/wp/index.json      (list of generated manifests)

  Group theory comes from sublib (the standalone copy, which carries
  subgroupStructure); geometry comes from SymmHub's grouplib + SubgroupDomain.
  Words follow the project convention: composition left to right,
  uppercase = inverse.  Terminology: cosets and orbits, never left/right.

  Names G/H[n]#k: the ordinal #k orders the (type, index) bucket by the
  geometric key of the conjugacy class (SymmHub's subgroupClassKey: the least
  key over the conjugates of H, the stabilizers of the cosets).  The key of
  the representative alone (subgroupKey, used until 2026-09-05) changes with
  the fundamental domain, because another presentation enumerates another
  conjugate of the same class; the class key does not, so the names are the
  same for every domain shape (SymmHub: tests/subgroups/catalog_names.mjs).
*/

import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CAT, DATA_DIR, FAMILY, FAMILIES, SUBLIB_URL, SYMMHUB_URL } from './catalog_paths.mjs';

const SUBLIB = SUBLIB_URL;
const SYMMHUB = SYMMHUB_URL;

const { subgroupsData, subgroupStructure, permStringToArrays, WALLPAPER_NAMES,
        getPreset, fileStem } = await import(SUBLIB);
const { iWallpaperGroup, resolveWallpaperDomainShape } =
  await import(SYMMHUB + '/lib/grouplib/WallpaperGroups.js');
const { Group_Frieze, Group_Spherical, Group_KLM, Group_KLMN } =
  await import(SYMMHUB + '/lib/grouplib/grouplib.js');
const { Group, ITransform, iPoint } = await import(SYMMHUB + '/lib/invlib/invlib.js');
const { buildSubgroupDomain, classifyEuclidean, isometryToString, sameTransform } =
  await import(SYMMHUB + '/lib/grouplib/SubgroupDomain.js');
const { reidemeisterSchreier } = await import('./reidemeister.mjs');
const { computeFrame, subgroupClassKey } =
  await import(SYMMHUB + '/lib/grouplib/SubgroupKey.js');
const { groupPresentation } = await import(SYMMHUB + '/lib/grouplib/GroupPresentation.js');
const { affineClasses, affineCounts } = await import('./affine_classes.mjs');
const dirichletLib = { ...(await import(SYMMHUB + '/lib/grouplib/DirichletDomain.js')),
                       ...(await import(SYMMHUB + '/lib/grouplib/Permutations.js')) };
const { dirichletGroup, sideCosets, sourceWord } = await import('./render/dirichlet_group.mjs');

const OUT_DIR = DATA_DIR;             // the family's manifests (tools/catalog_paths.json)

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

function makeGens(group, presentation){
  const names = presentation ? presentation.gens.split(/\s+/) : group.getGenNames();
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
  const gens = makeGens(group, presentation);
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
// coset numbering with the placement representatives first
//
// Offsets i, i' give the same placement iff their point stabilizers in the
// group the coset permutations generate coincide.  The pages show the
// colourings .1 .. .K as offsets 0 .. K-1, so those must be one offset per
// class.  Coset numbering is free except for coset 0 (= H), and another
// presentation (another domain shape) numbers them differently - the 632
// kite gives 632/333[8] the representatives 0,2,3,6.  So renumber: each
// class's least coset first, in order, then the rest in their old order.
// Done BEFORE anything is derived, so cells, transversal, colour action and
// key all follow from the renumbered table.  Identity when already in order.
// ---------------------------------------------------------------------------

function placementOrder(cosets){
  const gens = permStringToArrays(cosets);
  const n = gens[0].length;
  const key = q => q.join(',');
  const id = [...Array(n).keys()];
  const seen = new Map([[key(id), id]]);
  const queue = [id];
  while(queue.length){
    const q0 = queue.pop();
    for(const g of gens){
      const q = q0.map(x => g[x]);
      if(!seen.has(key(q))){ seen.set(key(q), q); queue.push(q); }
    }
  }
  const classes = new Map();
  for(let i = 0; i < n; i++){
    const stab = [...seen.values()].filter(q => q[i] === i).map(key).sort().join('|');
    if(!classes.has(stab)) classes.set(stab, []);
    classes.get(stab).push(i);
  }
  const reps = [...classes.values()].map(c => c[0]).sort((a, b) => a - b);
  const rest = id.filter(i => !reps.includes(i));
  return reps.concat(rest);          // order[newIndex] = oldIndex
}

function renumberCosets(cosets, order){
  const back = [];
  order.forEach((old, k) => { back[old] = k; });
  const letters = 'abcdefghijklmnopqrstuvwxyz';
  return permStringToArrays(cosets)
    .map(p => order.map(old => letters[back[p[old]]]).join(''))
    .join(' ');
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
// multi-family helpers (frieze, spherical, klm/hyperbolic)
// ---------------------------------------------------------------------------

const FRIEZE_ALIASES = {
  '*22oo': '*22∞', '22oo': '22∞', '2*oo': '2*∞', 'oo*': '∞*',
  '*oooo': '*∞∞',  'oox': '∞x',   'oooo': '∞∞',
};

function familyStem(fam, name){
  if(fam === 'wp') return fileStem(name);
  return String(name).replace(/∞/g, 'oo').replace(/\*/g, 's').replace(/[^A-Za-z0-9_-]+/g, '');
}

function friezeAffineClasses(group, presentation, subgroups, maxIndex){
  // Compute exact affine equivalence classes of subgroups of a frieze group G:
  // check candidate strip-preserving Euclidean normalizers (x -> ex*x + tx, y -> ey*y)
  // for ex, ey in {+1, -1} and tx in {0, a/2, a, 3a/2}. Any candidate that maps every
  // generator of G back into G induces an automorphism of G; subgroups carried onto
  // each other (up to coset relabeling in S_n) share one affineClass.
  const genNames = presentation.gens.split(/\s+/);
  const gens = group.transforms.map((t, k) => ({ name: genNames[k], it: new ITransform(t.slice(), genNames[k]) }));
  const steps = gens.concat(gens.map(g => ({ name: g.name.toUpperCase(), it: g.it.getInverse() })));
  const apply2 = (it, p) => { const q = it.transform(iPoint([p[0], p[1], 0, 0])).v; return [q[0], q[1]]; };
  const P0 = [0.12345, 0.06789], P1 = [-0.07211, 0.16183];
  const sig = (q0, q1) => [q0[0], q0[1], q1[0], q1[1]].map(v => (Math.abs(v) < 1e-9 ? 0 : v).toFixed(5)).join(',');

  // Short BFS in G to map isometries back to generator words
  const bySig = new Map([[sig(P0, P1), { word: '', it: IDENTITY }]]);
  let frontier = [{ word: '', it: IDENTITY }];
  for(let d = 0; d < 5 && bySig.size < 200; d++){
    const next = [];
    for(const cur of frontier) for(const s of steps){
      const it = cur.it.getCopy().concat(s.it);
      const k = sig(apply2(it, P0), apply2(it, P1));
      if(!bySig.has(k)){
        const rec = { word: cur.word + s.name, it };
        bySig.set(k, rec); next.push(rec);
      }
    }
    frontier = next;
  }

  // Find all generator automorphisms induced by candidate strip normalizers
  const autos = [];
  for(const ex of [1, -1]) for(const ey of [1, -1]) for(const k of [0, 1, 2, 3]){
    const tx = k * GEOMETRY_A / 2;
    const fwd = p => [ex * p[0] + tx, ey * p[1]];
    const inv = p => [ex * (p[0] - tx), ey * p[1]];
    const words = [];
    let ok = true;
    for(const g of gens){
      // Conjugate A^-1 g A (left-to-right: first A^-1, then g, then A)
      const q0 = fwd(apply2(g.it, inv(P0)));
      const q1 = fwd(apply2(g.it, inv(P1)));
      const hit = bySig.get(sig(q0, q1));
      if(!hit){ ok = false; break; }
      words.push(hit.word);
    }
    if(ok) autos.push(words);
  }

  // Evaluate word in coset permutations (left-to-right, uppercase = inverse)
  const invPerm = p => { const r = new Array(p.length); for(let i = 0; i < p.length; i++) r[p[i]] = i; return r; };
  const evalWord = (perms, word) => {
    const n = perms[0].length;
    let cur = Array.from({ length: n }, (_, i) => i);
    for(const ch of word){
      const lower = ch.toLowerCase();
      const gi = genNames.indexOf(lower);
      const p = ch === lower ? perms[gi] : invPerm(perms[gi]);
      cur = cur.map(x => p[x]);
    }
    return cur;
  };
  const sameAction = (P, Q) => {
    const n = P[0].length;
    for(let t0 = 0; t0 < n; t0++){
      const phi = new Array(n).fill(-1);
      phi[0] = t0;
      const q = [0];
      let ok = true;
      while(q.length && ok){
        const x = q.pop(), px = phi[x];
        for(let g = 0; g < P.length; g++){
          const nx = P[g][x], ny = Q[g][px];
          if(phi[nx] === -1){ phi[nx] = ny; q.push(nx); }
          else if(phi[nx] !== ny){ ok = false; break; }
        }
      }
      if(ok) return true;
    }
    return false;
  };

  // Union-find across subgroups of the same (index, type)
  const parent = subgroups.map((_, i) => i);
  const find = i => { while(parent[i] !== i){ parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  const permsOf = subgroups.map(s => permStringToArrays(s.cosets));
  for(let i = 0; i < subgroups.length; i++){
    for(const words of autos){
      const img = words.map(w => evalWord(permsOf[i], w));
      for(let j = i + 1; j < subgroups.length; j++){
        if(subgroups[j].index !== subgroups[i].index || subgroups[j].type !== subgroups[i].type) continue;
        if(sameAction(img, permsOf[j])){
          const a = find(i), b = find(j);
          if(a !== b) parent[Math.max(a, b)] = Math.min(a, b);
        }
      }
    }
  }
  const byRoot = new Map();
  subgroups.forEach((s, i) => {
    const r = find(i);
    if(!byRoot.has(r)) byRoot.set(r, []);
    byRoot.get(r).push(s);
  });
  const classOf = new Map();
  const perIdx = new Array(maxIndex + 1).fill(0);
  for(const members of byRoot.values()){
    members.sort((a, b) => a.name < b.name ? -1 : 1);
    const rep = members[0].name;
    for(const s of members) classOf.set(s.name, rep);
    if(members[0].index <= maxIndex) perIdx[members[0].index]++;
  }
  const affineCountPerIndex = perIdx.map((count, index) => ({ index, count })).filter(c => c.count);
  return { classOf, affineCountPerIndex };
}

function classifyFriezeSubgroup(domain){
  // Walk short products of H's pairing generators and inspect their Euclidean
  // isometry types: the 7 frieze groups have pairwise distinct geometric signatures.
  const gens = domain.generators.map(gi => domain.pairings[gi].itrans);
  const steps = gens.concat(gens.map(g => g.getInverse()));
  const keyOf = t => {
    const a = t.transform(TEST_POINTS[0]).v, b = t.transform(TEST_POINTS[1]).v;
    return [a[0], a[1], b[0], b[1]].map(v => v.toFixed(4)).join(',');
  };
  let frontier = [IDENTITY];
  const seen = new Map([[keyOf(IDENTITY), IDENTITY]]);
  for(let d = 0; d < 4 && seen.size < 250; d++){
    const next = [];
    for(const cur of frontier) for(const g of steps){
      const c = cur.getCopy().concat(g);
      const k = keyOf(c);
      if(!seen.has(k)){ seen.set(k, c); next.push(c); }
    }
    frontier = next;
  }
  let hasRot2 = false, hasHMirror = false, hasVMirror = false, hasGlide = false;
  for(const t of seen.values()){
    const cls = classifyEuclidean(t);
    if(cls.type === 'rotation') hasRot2 = true;
    else if(cls.type === 'reflection'){
      if(Math.abs(cls.axis.dir[1]) < 1e-3) hasHMirror = true;
      else if(Math.abs(cls.axis.dir[0]) < 1e-3) hasVMirror = true;
    } else if(cls.type === 'glide') hasGlide = true;
  }
  if(hasHMirror && hasVMirror) return '*22∞';
  if(hasHMirror) return '∞*';
  if(hasVMirror && hasRot2) return '2*∞';
  if(hasVMirror) return '*∞∞';
  if(hasRot2) return '22∞';
  if(hasGlide) return '∞x';
  return '∞∞';
}

function stereoInv(u, v){
  if(!Number.isFinite(u) || !Number.isFinite(v)) return [0, 0, -1];
  const r2 = u*u + v*v;
  if(r2 > 1e12) return [0, 0, -1];
  const d = 1 + r2;
  return [2*u/d, 2*v/d, (1 - r2)/d];
}

function itransToO3(it){
  const applyS2 = p => {
    const q = it.transform(iPoint([p[0], p[1], 0, 0])).v;
    return stereoInv(q[0], q[1]);
  };
  const c1 = applyS2([1, 0]), c2 = applyS2([0, 1]), c3 = applyS2([0, 0]);
  return [
    [c1[0], c2[0], c3[0]],
    [c1[1], c2[1], c3[1]],
    [c1[2], c2[2], c3[2]],
  ];
}

function matMul3(A, B){
  const C = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  for(let i = 0; i < 3; i++) for(let j = 0; j < 3; j++)
    C[i][j] = A[i][0]*B[0][j] + A[i][1]*B[1][j] + A[i][2]*B[2][j];
  return C;
}

function matTrans3(A){
  return [
    [A[0][0], A[1][0], A[2][0]],
    [A[0][1], A[1][1], A[2][1]],
    [A[0][2], A[1][2], A[2][2]],
  ];
}

function det3(M){
  return M[0][0]*(M[1][1]*M[2][2] - M[1][2]*M[2][1])
       - M[0][1]*(M[1][0]*M[2][2] - M[1][2]*M[2][0])
       + M[0][2]*(M[1][0]*M[2][1] - M[1][1]*M[2][0]);
}

function trace3(M){ return M[0][0] + M[1][1] + M[2][2]; }

function matKey3(M){
  return M.flat().map(v => (Math.abs(v) < 1e-4 ? 0 : v).toFixed(3)).join(',');
}

function rotAngle3(M){
  const c = Math.max(-1, Math.min(1, (trace3(M) - 1) / 2));
  return Math.acos(c);
}

function matOrder3(M){
  let cur = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  for(let k = 1; k <= 60; k++){
    cur = matMul3(M, cur);
    if(Math.abs(cur[0][0] - 1) < 1e-3 && Math.abs(cur[1][1] - 1) < 1e-3 && Math.abs(cur[2][2] - 1) < 1e-3
       && Math.abs(cur[0][1]) < 1e-3 && Math.abs(cur[0][2]) < 1e-3 && Math.abs(cur[1][2]) < 1e-3)
      return k;
  }
  return 0;
}

function fmtPiAngle(rad){
  const f = rad / Math.PI;
  if(Math.abs(f - 1) < 1e-3) return '1*PI';
  for(const q of [2, 3, 4, 5, 6, 8, 10, 12, 16]){
    const p = Math.round(f * q);
    if(p > 0 && Math.abs(f - p / q) < 1e-3) return `${p}/${q}*PI`;
  }
  return `${f.toFixed(4)}*PI`;
}

function describeSphericalIsometry(it){
  const M = itransToO3(it);
  const d = det3(M);
  const tr = trace3(M);
  if(d > 0){
    if(Math.abs(tr - 3) < 1e-3) return { text: 'identity' };
    const ang = rotAngle3(M);
    const ord = matOrder3(M);
    return { text: `rotation ${fmtPiAngle(ang)}` + (ord ? ` (order ${ord})` : '') };
  }
  if(Math.abs(tr + 3) < 1e-3) return { text: 'central inversion' };
  if(Math.abs(tr - 1) < 1e-3) return { text: 'reflection' };
  const negM = M.map(r => r.map(v => -v));
  const ang = rotAngle3(negM);
  const ord = matOrder3(M);
  return { text: `rotoreflection ${fmtPiAngle(Math.PI - ang)}` + (ord ? ` (order ${ord})` : '') };
}

function generateO3Group(genMats){
  const ID3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const steps = genMats.concat(genMats.map(matTrans3));
  const seen = new Map([[matKey3(ID3), ID3]]);
  const queue = [ID3];
  while(queue.length && seen.size < 250){
    const cur = queue.shift();
    for(const g of steps){
      const nxt = matMul3(g, cur);
      const k = matKey3(nxt);
      if(!seen.has(k)){ seen.set(k, nxt); queue.push(nxt); }
    }
  }
  return [...seen.values()];
}

function classifySphericalSubgroup(domain){
  // Exact classification of every finite subgroup H <= O(3) from its exact 3x3
  // matrix closure (|H| <= 120).  Returns Conway orbifold notation:
  //   polyhedral: 332, 3*2, *332, 432, *432, 532, *532
  //   dihedral:   22n, 2*n, *22n  (n >= 2)
  //   cyclic:     nn, *nn, n*, nx (n >= 2)
  //   small:      1 (C1), * (Cs), x (Ci)
  const genMats = domain.generators.map(gi => itransToO3(domain.pairings[gi].itrans));
  const elems = generateO3Group(genMats);
  const N = elems.length;
  const pos = elems.filter(M => det3(M) > 0);
  const Npos = pos.length;
  const refls = elems.filter(M => det3(M) < 0 && Math.abs(trace3(M) - 1) < 1e-3).length;
  const hasInv = elems.some(M => det3(M) < 0 && Math.abs(trace3(M) + 3) < 1e-3);

  const orderCounts = new Map();
  let maxOrd = 1;
  for(const M of pos){
    const o = matOrder3(M);
    orderCounts.set(o, (orderCounts.get(o) || 0) + 1);
    if(o > maxOrd) maxOrd = o;
  }
  const c2 = orderCounts.get(2) || 0;
  const c3 = orderCounts.get(3) || 0;

  // Polyhedral groups (more than one axis of order >= 3 -> c3 >= 8)
  if(c3 >= 8){
    if(Npos === 60) return N === 120 ? '*532' : '532';
    if(Npos === 24) return N === 48 ? '*432' : '432';
    if(Npos === 12){
      if(N === 12) return '332';
      return hasInv ? '3*2' : '*332';
    }
    throw new Error(`unexpected polyhedral subgroup N=${N} N+=${Npos}`);
  }

  // Order-1 orientation-preserving part (H+ = {I})
  if(Npos === 1){
    if(N === 1) return '1';
    if(refls === 1) return '*';
    if(hasInv) return 'x';
    throw new Error(`unexpected N+ = 1 subgroup N=${N}`);
  }

  // Dihedral H+ = D_n (either n=2 with N+=4, c2=3; or n>=3 with N+=2*maxOrd)
  const isDihedral = (Npos === 4 && c2 === 3) || (maxOrd >= 3 && Npos === 2 * maxOrd);
  if(isDihedral){
    const n = Npos / 2;
    if(N === Npos) return `22${n}`;
    if(refls === n + 1) return `*22${n}`;
    if(refls === n) return `2*${n}`;
    throw new Error(`unexpected dihedral subgroup N=${N} N+=${Npos} refls=${refls}`);
  }

  // Cyclic H+ = C_n (n = N+ >= 2)
  const n = Npos;
  if(N === n) return `${n}${n}`;
  if(refls === n) return `*${n}${n}`;
  if(refls === 1) return `${n}*`;
  if(refls === 0) return `${n}x`;
  throw new Error(`unexpected cyclic subgroup N=${N} N+=${Npos} refls=${refls}`);
}

function sphericalAffineClasses(group, presentation, subgroups, maxIndex, spec){
  // Exact geometric equivalence classes of subgroups of a spherical/polyhedral
  // group G under conjugation by its normalizer N_{O(3)}(G).
  const genNames = presentation.gens.split(/\s+/);
  const gens = group.transforms.map((t, k) => ({
    name: genNames[k],
    M: itransToO3(new ITransform(t.slice(), genNames[k])),
  }));
  const steps = gens.concat(gens.map(g => ({ name: g.name.toUpperCase(), M: matTrans3(g.M) })));
  const ID3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

  // Full BFS in finite group G (|G| <= 120): left-to-right word w -> matrix M(w)
  // Remember: (a*b)(p) = b(a(p)) => M(a*b) = M(b) * M(a).
  const byKey = new Map([[matKey3(ID3), { word: '', M: ID3 }]]);
  const queue = [{ word: '', M: ID3 }];
  while(queue.length && byKey.size < 250){
    const cur = queue.shift();
    for(const s of steps){
      const M = matMul3(s.M, cur.M);
      const k = matKey3(M);
      if(!byKey.has(k)){
        const rec = { word: cur.word + s.name, M };
        byKey.set(k, rec); queue.push(rec);
      }
    }
  }

  // Build candidate O(3) normalizer elements A
  const cands = [];
  const rotZ = th => [[Math.cos(th), -Math.sin(th), 0], [Math.sin(th), Math.cos(th), 0], [0, 0, 1]];
  const reflX = [[-1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const reflZ = [[1, 0, 0], [0, 1, 0], [0, 0, -1]];
  const isPoly = ['332', '3*2', '*332', '432', '*432', '532', '*532'].includes(spec.type);
  if(isPoly){
    // For tetrahedral/octahedral groups, N_{O(3)}(G) <= O_h sharing G's axes;
    // collect G plus -I plus 90-deg rotations around every 2-fold axis of G.
    const seeds = gens.map(g => g.M);
    seeds.push([[-1, 0, 0], [0, -1, 0], [0, 0, -1]]);
    for(const rec of byKey.values()){
      const M = rec.M;
      if(det3(M) > 0 && matOrder3(M) === 2){
        // unit axis u of half-turn satisfies (M + I) has rank 1 -> largest column
        const cols = [0, 1, 2].map(j => [M[0][j] + (j === 0 ? 1 : 0), M[1][j] + (j === 1 ? 1 : 0), M[2][j] + (j === 2 ? 1 : 0)]);
        cols.sort((a, b) => (b[0]*b[0]+b[1]*b[1]+b[2]*b[2]) - (a[0]*a[0]+a[1]*a[1]+a[2]*a[2]));
        const u = cols[0];
        const len = Math.hypot(u[0], u[1], u[2]);
        if(len > 1e-3){
          const ux = u[0]/len, uy = u[1]/len, uz = u[2]/len;
          // 90-degree rotation around u: R = u u^T + [u]_x
          seeds.push([
            [ux*ux,        ux*uy - uz, ux*uz + uy],
            [uy*ux + uz,   uy*uy,      uy*uz - ux],
            [uz*ux - uy,   uz*uy + ux, uz*uz     ],
          ]);
        }
      }
    }
    cands.push(...generateO3Group(seeds));
  } else {
    const n = spec.n;
    const seeds = [rotZ(Math.PI / (2 * n)), reflX, reflZ];
    if(n === 2){
      // Also allow full O_h axis permutations for D_2 / D_{2h} / D_{2d} / C_{2v} / C_{2h}
      seeds.push([[0, 1, 0], [0, 0, 1], [1, 0, 0]], [[0, 1, 0], [1, 0, 0], [0, 0, 1]]);
    }
    cands.push(...generateO3Group(seeds));
  }

  // Keep only A in N_{O(3)}(G), recording induced generator words A * M(g) * A^-1
  const autos = [];
  const autoSeen = new Set();
  for(const A of cands){
    const Ainv = matTrans3(A);
    const words = [];
    let ok = true;
    for(const g of gens){
      const conj = matMul3(A, matMul3(g.M, Ainv));
      const hit = byKey.get(matKey3(conj));
      if(!hit){ ok = false; break; }
      words.push(hit.word);
    }
    if(ok){
      const key = words.join('|');
      if(!autoSeen.has(key)){ autoSeen.add(key); autos.push(words); }
    }
  }

  const invPerm = p => { const r = new Array(p.length); for(let i = 0; i < p.length; i++) r[p[i]] = i; return r; };
  const evalWord = (perms, word) => {
    const n = perms[0].length;
    let cur = Array.from({ length: n }, (_, i) => i);
    for(const ch of word){
      const lower = ch.toLowerCase();
      const gi = genNames.indexOf(lower);
      const p = ch === lower ? perms[gi] : invPerm(perms[gi]);
      cur = cur.map(x => p[x]);
    }
    return cur;
  };
  const sameAction = (P, Q) => {
    const n = P[0].length;
    for(let t0 = 0; t0 < n; t0++){
      const phi = new Array(n).fill(-1);
      phi[0] = t0;
      const q = [0];
      let ok = true;
      while(q.length && ok){
        const x = q.pop(), px = phi[x];
        for(let g = 0; g < P.length; g++){
          const nx = P[g][x], ny = Q[g][px];
          if(phi[nx] === -1){ phi[nx] = ny; q.push(nx); }
          else if(phi[nx] !== ny){ ok = false; break; }
        }
      }
      if(ok) return true;
    }
    return false;
  };

  const parent = subgroups.map((_, i) => i);
  const find = i => { while(parent[i] !== i){ parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  const permsOf = subgroups.map(s => permStringToArrays(s.cosets));
  for(let i = 0; i < subgroups.length; i++){
    for(const words of autos){
      const img = words.map(w => evalWord(permsOf[i], w));
      for(let j = i + 1; j < subgroups.length; j++){
        if(subgroups[j].index !== subgroups[i].index || subgroups[j].type !== subgroups[i].type) continue;
        if(sameAction(img, permsOf[j])){
          const a = find(i), b = find(j);
          if(a !== b) parent[Math.max(a, b)] = Math.min(a, b);
        }
      }
    }
  }
  const byRoot = new Map();
  subgroups.forEach((s, i) => {
    const r = find(i);
    if(!byRoot.has(r)) byRoot.set(r, []);
    byRoot.get(r).push(s);
  });
  const classOf = new Map();
  const perIdx = new Array(maxIndex + 1).fill(0);
  for(const members of byRoot.values()){
    members.sort((a, b) => a.name < b.name ? -1 : 1);
    const rep = members[0].name;
    for(const s of members) classOf.set(s.name, rep);
    if(members[0].index <= maxIndex) perIdx[members[0].index]++;
  }
  const affineCountPerIndex = perIdx.map((count, index) => ({ index, count })).filter(c => c.count);
  return { classOf, affineCountPerIndex };
}

function parseSphericalSpec(name){
  const fixed = new Set(['*332', '332', '3*2', '*432', '432', '*532', '532']);
  if(fixed.has(name)) return { type: name, n: 2 };
  let m;
  if((m = name.match(/^\*22(\d+)$/))) return { type: '*22n', n: Number(m[1]) };
  if((m = name.match(/^2\*(\d+)$/)))  return { type: '2*n',  n: Number(m[1]) };
  if((m = name.match(/^22(\d+)$/)))   return { type: '22n',  n: Number(m[1]) };
  if((m = name.match(/^\*(\d+)\1$/))) return { type: '*nn',  n: Number(m[1]) };
  if((m = name.match(/^(\d+)\1$/)))   return { type: 'nn',   n: Number(m[1]) };
  if((m = name.match(/^(\d+)\*$/)))   return { type: 'n*',   n: Number(m[1]) };
  if((m = name.match(/^(\d+)x$/)))    return { type: 'nx',   n: Number(m[1]) };
  throw new Error(`unrecognized spherical group '${name}' (e.g. *532, 432, *224, 3*)`);
}

function parseHyperbolicSpec(name){
  const s = name.startsWith('*');
  const raw = s ? name.slice(1) : name;
  const parts = raw.includes('-') ? raw.split('-').map(Number)
              : (/^\d{3,4}$/.test(raw) ? [...raw].map(Number) : null);
  if(!parts || (parts.length !== 3 && parts.length !== 4) || parts.some(x => !Number.isInteger(x) || x < 2))
    throw new Error(`unrecognized hyperbolic group '${name}' (e.g. 237, *238, 2223, *2233)`);
  if(parts.length === 3) return { kind: 'klm', s, K: parts[0], L: parts[1], M: parts[2] };
  return { kind: 'klmn', s, K: parts[0], L: parts[1], M: parts[2], N: parts[3] };
}

function canonCycle(arr){
  if(arr.length <= 1) return arr.slice();
  const cands = [];
  for(const seq of [arr, arr.slice().reverse()])
    for(let s = 0; s < seq.length; s++) cands.push(seq.slice(s).concat(seq.slice(0, s)));
  cands.sort((a, b) => { for(let i = 0; i < a.length; i++) if(a[i] !== b[i]) return a[i] - b[i]; return 0; });
  return cands[0];
}

function fmtOrbOrders(arr){
  return arr.every(x => x < 10) ? arr.join('') : arr.join('-');
}

// Exact Conway orbifold signature for any finite-index subgroup H of klm, *klm, klmn, or *klmn,
// computed directly from the coset action and cross-checked by Riemann-Hurwitz.
function classifyHyperbolicOrbifold(hSpec, cosetsStr){
  const perms = permStringToArrays(cosetsStr);
  const n = perms[0].length;
  const compP = (p, q) => p.map(x => q[x]);

  if(!hSpec.s){
    const corners = hSpec.kind === 'klm' ? [hSpec.K, hSpec.L, hSpec.M] : [hSpec.K, hSpec.L, hSpec.M, hSpec.N];
    const cPerms = hSpec.kind === 'klm'
      ? [perms[0], perms[1], compP(perms[0], perms[3])]
      : [perms[1], compP(perms[3], perms[1]), perms[5], compP(perms[3], perms[5])];
    const chiG = 2 - corners.reduce((a, m) => a + (1 - 1 / m), 0);
    const cones = [];
    for(let ci = 0; ci < corners.length; ci++){
      const m = corners[ci], p = cPerms[ci], vis = new Uint8Array(n);
      for(let i = 0; i < n; i++){
        if(vis[i]) continue;
        let len = 0, x = i;
        while(!vis[x]){ vis[x] = 1; x = p[x]; len++; }
        if(m % len !== 0) throw new Error(`orbifold cycle ${len} does not divide ${m}`);
        if(m / len >= 2) cones.push(m / len);
      }
    }
    const twoG = Math.round(2 - n * chiG - cones.reduce((a, c) => a + (1 - 1 / c), 0));
    if(Math.abs((2 - n * chiG - cones.reduce((a, c) => a + (1 - 1 / c), 0)) - twoG) > 1e-6 || twoG < 0 || twoG % 2 !== 0)
      throw new Error(`Riemann-Hurwitz failed (2g=${twoG})`);
    cones.sort((a, b) => a - b);
    return (cones.length ? fmtOrbOrders(cones) : '') + 'o'.repeat(twoG / 2) || '1';
  }

  const sides = hSpec.kind === 'klm' ? [0, 1, 2] : [0, 2, 1, 3];
  const cornerOrders = hSpec.kind === 'klm' ? [hSpec.K, hSpec.M, hSpec.L] : [hSpec.L, hSpec.K, hSpec.M, hSpec.N];
  const L = sides.length;
  const r = sides.map(si => perms[si]);
  const chiG = 1 - 0.5 * cornerOrders.reduce((a, m) => a + (1 - 1 / m), 0);

  const color = new Int8Array(n);
  let orientable = true;
  for(let i = 0; i < n; i++){
    if(color[i]) continue;
    color[i] = 1; const q = [i];
    while(q.length){
      const u = q.pop();
      for(let s = 0; s < L; s++){
        const v = r[s][u]; if(v === u) continue;
        if(!color[v]){ color[v] = -color[u]; q.push(v); }
        else if(color[v] === color[u]) orientable = false;
      }
    }
  }

  const cones = [], hop = new Map();
  for(let j = 0; j < L; j++){
    const sA = j, sB = (j + 1) % L, m = cornerOrders[j], vis = new Uint8Array(n);
    for(let c0 = 0; c0 < n; c0++){
      if(vis[c0]) continue;
      const orb = [], q = [c0]; vis[c0] = 1;
      while(q.length){
        const u = q.pop(); orb.push(u);
        for(const s of [sA, sB]){ const v = r[s][u]; if(!vis[v]){ vis[v] = 1; q.push(v); } }
      }
      const ends = [];
      for(const u of orb){
        if(r[sA][u] === u) ends.push([u, sA]);
        if(r[sB][u] === u) ends.push([u, sB]);
      }
      const d = orb.length;
      if(ends.length === 0){
        if((2 * m) % d !== 0) throw new Error(`interior vertex d=${d} !| ${2 * m}`);
        if((2 * m) / d >= 2) cones.push((2 * m) / d);
      } else if(ends.length === 2){
        if(m % d !== 0) throw new Error(`boundary vertex d=${d} !| ${m}`);
        const [c1, s1] = ends[0], [c2, s2] = ends[1];
        hop.set(`${c1},${s1},${j}`, { c: c2, s: s2, ord: m / d });
        hop.set(`${c2},${s2},${j}`, { c: c1, s: s1, ord: m / d });
      } else {
        throw new Error(`unexpected boundary ends ${ends.length}`);
      }
    }
  }

  const visitedEdge = new Set(), mirrors = [];
  for(let c0 = 0; c0 < n; c0++){
    for(let s0 = 0; s0 < L; s0++){
      if(r[s0][c0] !== c0 || visitedEdge.has(`${c0},${s0}`)) continue;
      const cyc = []; let c = c0, s = s0, corner = s0;
      while(true){
        visitedEdge.add(`${c},${s}`);
        const h = hop.get(`${c},${s},${corner}`);
        if(h.ord >= 2) cyc.push(h.ord);
        const other = (corner === h.s) ? (h.s - 1 + L) % L : h.s;
        c = h.c; s = h.s; corner = other;
        if(c === c0 && s === s0 && corner === s0) break;
      }
      mirrors.push(canonCycle(cyc));
    }
  }

  const rem = 2 - n * chiG - cones.reduce((a, p) => a + (1 - 1 / p), 0)
            - mirrors.reduce((a, cyc) => a + 1 + 0.5 * cyc.reduce((x, k) => x + (1 - 1 / k), 0), 0);
  const remInt = Math.round(rem);
  if(Math.abs(rem - remInt) > 1e-6 || remInt < 0) throw new Error(`bad RH remainder ${rem}`);
  const tail = orientable ? 'o'.repeat(remInt / 2) : 'x'.repeat(remInt);
  cones.sort((a, b) => a - b);
  mirrors.sort((a, b) => b.length - a.length || a.reduce((d, x, i) => d || (x - b[i]), 0));
  return ((cones.length ? fmtOrbOrders(cones) : '') + mirrors.map(c => '*' + (c.length ? fmtOrbOrders(c) : '')).join('') + tail) || '1';
}

function describeHyperbolicIsometry(itrans){
  if(!itrans || !itrans.ref || itrans.ref.length === 0) return { text: 'identity' };
  const odd = (itrans.ref.length % 2) === 1;
  // Detect small finite order (reflection / rotation) by iterating on two interior test points
  const pts = [iPoint([0.11, 0.07, 0, 0]), iPoint([-0.09, 0.13, 0, 0])];
  const same = (a, b) => Math.hypot(a.v[0] - b.v[0], a.v[1] - b.v[1]) < 1e-5;
  let cur = pts;
  for(let k = 1; k <= 12; k++){
    cur = cur.map(p => itrans.transform(p));
    if(same(cur[0], pts[0]) && same(cur[1], pts[1])){
      if(k === 1) return { text: 'identity' };
      if(odd && k === 2) return { text: 'reflection' };
      if(!odd) return { text: `rotation (order ${k})` };
    }
  }
  return { text: odd ? 'glide reflection' : 'hyperbolic translation' };
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

const _argv = process.argv.slice(2);
const _optFlag = (flag, takesVal = true) => {
  const i = _argv.indexOf(flag);
  if(i < 0) return takesVal ? null : false;
  return takesVal ? _argv.splice(i, 2)[1] : (_argv.splice(i, 1), true);
};
const familyArg = (_optFlag('--family') || FAMILY || 'wp').toLowerCase();
const famKey = familyArg === 'wallpaper' ? 'wp'
             : familyArg === 'klm' ? 'hyperbolic' : familyArg;
const domainShape = _optFlag('--domain');
const dirichletPreset = _optFlag('--dirichlet');
const customOut = _optFlag('--out');
const dryRun = _optFlag('--dry-run', false);
const rawGroupName = _argv[0] || (famKey === 'frieze' ? '*22∞' : (famKey === 'axial' || famKey === 'spherical') ? '*224' : famKey === 'polyhedral' ? '*432' : famKey === 'hyperbolic' ? '*238' : '632');
const groupName = famKey === 'frieze' ? (FRIEZE_ALIASES[rawGroupName] || rawGroupName) : rawGroupName;
const maxIndex = Number(_argv[1] || 6);

const isWallpaper = famKey === 'wp';
const isEuclidean = famKey === 'wp' || famKey === 'frieze';
const isSpherical = famKey === 'axial' || famKey === 'spherical' || famKey === 'polyhedral';
const isHyperbolic = famKey === 'hyperbolic';
const outDir = customOut ? customOut
             : (FAMILIES[famKey] ? join(CAT, ...FAMILIES[famKey].dataDir.split('/'))
                                 : join(CAT, 'data', famKey));

let presentation, data, group, sphericalSpec = null, hyperbolicSpec = null;
if(isWallpaper){
  if(domainShape){
    // the presentation of THIS domain: its pairing transforms are the generators
    group = new Group(iWallpaperGroup({ name: groupName, a: GEOMETRY_A, domainShape }));
    const p = groupPresentation(group);
    presentation = { name: groupName, gens: p.gens, relators: p.relators };
    data = subgroupsData({ name: groupName, gens: p.gens, relators: p.relators,
                           maxIndex, generators: 'none' });
  } else {
    presentation = getPreset('wallpaper:' + groupName);
    data = subgroupsData({ preset: 'wallpaper:' + groupName, maxIndex, generators: 'none' });
    group = new Group(iWallpaperGroup({ name: groupName, a: GEOMETRY_A }));
  }
} else if(famKey === 'frieze'){
  const maker = new Group_Frieze({ type: groupName, a: GEOMETRY_A });
  group = maker.getGroup();
  presentation = maker.getPresentation();
  data = subgroupsData({ name: groupName, gens: presentation.gens, relators: presentation.relators,
                         maxIndex, generators: 'none' });
} else if(isSpherical){
  sphericalSpec = parseSphericalSpec(groupName);
  const maker = new Group_Spherical(sphericalSpec);
  group = maker.getGroup();
  presentation = maker.getPresentation();
  data = subgroupsData({ name: groupName, gens: presentation.gens, relators: presentation.relators,
                         maxIndex, generators: 'none' });
} else if(isHyperbolic){
  hyperbolicSpec = parseHyperbolicSpec(groupName);
  let maker;
  if(hyperbolicSpec.kind === 'klm'){
    maker = new Group_KLM();
    Object.assign(maker.params, { K: hyperbolicSpec.K, L: hyperbolicSpec.L, M: hyperbolicSpec.M, s: hyperbolicSpec.s, hasR: false });
  } else {
    maker = new Group_KLMN();
    Object.assign(maker.params, { K: hyperbolicSpec.K, L: hyperbolicSpec.L, M: hyperbolicSpec.M, N: hyperbolicSpec.N, s: hyperbolicSpec.s, uhp: false, aspect: 0.5, twist: 0, bend: 0 });
  }
  group = maker.getGroup();
  presentation = maker.getPresentation();
  data = subgroupsData({ name: groupName, gens: presentation.gens, relators: presentation.relators,
                         maxIndex, generators: 'none' });
} else {
  throw new Error(`unsupported family '${famKey}' (expected wp, frieze, axial, polyhedral, hyperbolic)`);
}

const genCountMatch = group.getFundDomain().length === presentation.gens.split(/\s+/).length;
const corr = genCountMatch ? checkCorrespondence(group, presentation)
                           : { ok: false, badRelators: ['generator count mismatch'] };
if(!corr.ok)
  console.warn(`WARNING ${groupName}: geometry does not satisfy the presentation ` +
               `(${corr.badRelators.join(', ')}) - geometric fields omitted`);

// G on the preset's Dirichlet domain (wallpaper)
let DG = null, dirichletInfo = null;
if(dirichletPreset){
  if(!isWallpaper) throw new Error('--dirichlet is currently supported for wallpaper groups only');
  const sym = JSON.parse(readFileSync(dirichletPreset, 'utf8')).params.symmetry;
  const gp = sym.group.params;
  const shapeOf = sh => resolveWallpaperDomainShape(groupName, sh || 'default');
  if(gp.type !== groupName.replace(/x/g, 'X').replace(/^o$/, 'O'))
    throw new Error(`${dirichletPreset} is a preset of ${gp.type}, not ${groupName}`);
  if(shapeOf(gp.domainShape) !== shapeOf(domainShape))
    throw new Error(`${dirichletPreset} is on the domain '${gp.domainShape}': pass --domain "${gp.domainShape}"`);
  if(!(sym.dirichlet && sym.dirichlet.enabled))
    throw new Error(`${dirichletPreset} has no Dirichlet domain turned on`);
  const G0 = new Group(iWallpaperGroup({
    name: groupName, a: gp.a, b: gp.b, c: gp.c,
    angle_a: (gp.angle_a || 0) * Math.PI / 180,
    angle_b: (gp.angle_b === undefined ? 90 : gp.angle_b) * Math.PI / 180,
    ...(domainShape ? { domainShape } : {}) }));
  const c0 = checkCorrespondence(G0, presentation);
  if(!c0.ok) throw new Error(`the preset's geometry does not satisfy the presentation (${c0.badRelators.join(', ')})`);
  DG = dirichletGroup(dirichletLib, G0, sym.dirichlet);
  dirichletInfo = { preset: dirichletPreset.replace(/\\/g, '/'), baseX: sym.dirichlet.baseX,
                    baseY: sym.dirichlet.baseY, words: sym.dirichlet.words,
                    sideWords: DG.dirichletWords,
                    geometry: { a: gp.a, b: gp.b, c: gp.c, angle_a: gp.angle_a, angle_b: gp.angle_b } };
}

const refFingerprints = isWallpaper ? makeReferenceFingerprints() : null;
const frame = (isWallpaper && corr.ok) ? computeFrame(group) : null;
const expandedRelators = String(presentation.relators).split(',').filter(Boolean).map(r => expandRelator(r));

const subgroups = [];
for(const sub of data.subgroups){

  const st = subgroupStructure(data, sub.subgroup,
    (isWallpaper && domainShape) ? { dimension: 2 } : (!isWallpaper ? { abelianization: true } : {}));
  const order = placementOrder(sub.cosets);
  const renumbered = order.some((old, k) => old !== k);
  const cosets = renumbered ? renumberCosets(sub.cosets, order) : sub.cosets;
  const perms = permStringToArrays(cosets);
  const placements = countPlacements(cosets);

  let domain = null;
  if(corr.ok){
    try {
      domain = DG ? buildSubgroupDomain({ group: DG, cosets: sideCosets(dirichletLib, DG, cosets),
                                          testPoints: TEST_POINTS })
                  : buildSubgroupDomain({ group, cosets, testPoints: TEST_POINTS });
    } catch(e){
      console.warn(`WARNING ${sub.subgroup}: buildSubgroupDomain failed (${e.message})`);
    }
  }
  const gWord = w => (DG ? sourceWord(dirichletLib, DG, w) : w) || 'e';

  const cls = isWallpaper
    ? classifySubgroupType(perms, expandedRelators, st, refFingerprints)
    : (famKey === 'frieze' && domain
       ? { type: classifyFriezeSubgroup(domain) }
       : (isSpherical && domain
          ? { type: classifySphericalSubgroup(domain) }
          : (isHyperbolic && hyperbolicSpec
             ? { type: classifyHyperbolicOrbifold(hyperbolicSpec, cosets) }
             : { type: sub.index === 1 ? groupName : 'sub' })));

  const entry = {
    id: sub.subgroup,                    // sublib id: stable only within this file
    index: sub.index,
    type: cls.type,
    ...(cls.note ? { typeNote: cls.note } : {}),
    normal: placements === 1,
    placements,
    cosets,
    ...(renumbered ? { sublibCosets: sub.cosets, cosetOrder: order } : {}),
    orders: st.orders,
    ...(st.abelianization ? { abelianization: st.abelianization.text } : {}),
    colorAction: presentation.gens.split(/\s+/).map((g, k) => ({
      generator: g,
      perm: perms[k],
      cycles: cyclesOf(perms[k]),
    })),
  };

  if(frame){
    try {
      const gk = subgroupClassKey({ group, frame, cosets });
      entry.geoKey = gk.key;
      entry.keyCoset = gk.coset;
      entry.representativeKey = gk.keys.get(0).key;
      entry.latticeHNF = gk.hnf;
      entry.latticeIndex = gk.latticeIndex;
      entry.pointIndex = gk.pointIndex;
    } catch(e){
      console.warn(`WARNING ${sub.subgroup}: no geometric key (${e.message})`);
    }
  }

  if(domain){
    const describeIso = itrans => isEuclidean
      ? { isometry: classifyEuclidean(itrans), text: isometryToString(classifyEuclidean(itrans)) }
      : (isSpherical ? describeSphericalIsometry(itrans)
         : (isHyperbolic ? describeHyperbolicIsometry(itrans) : { text: itrans.word || 'e' }));
    entry.orbitReps = domain.cells.map(c => ({ word: gWord(c.word), ...describeIso(c.itrans) }));
    entry.transversal = domain.cosetTransversal.map(t => ({ word: gWord(t.word), ...describeIso(t.itrans) }));
    entry.simplyConnected = domain.simplyConnected;
    entry.hGenerators = domain.generators.map(gi => ({
      word: DG ? gWord(domain.pairings[gi].word) : domain.pairings[gi].word,
      ...(isEuclidean
          ? { isometry: domain.pairings[gi].isometry, text: isometryToString(domain.pairings[gi].isometry) }
          : (isSpherical ? describeSphericalIsometry(domain.pairings[gi].itrans)
             : (isHyperbolic ? describeHyperbolicIsometry(domain.pairings[gi].itrans) : { text: domain.pairings[gi].word }))),
    }));
    entry.sideCounts = {
      boundary: domain.sides.filter(s => s.kind === 'boundary').length,
      interior: domain.sides.filter(s => s.kind === 'interior').length,
    };
  }

  subgroups.push(entry);
}

// display names: G/H[n]#k
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

let affineCountPerIndex = null;
if(frame){
  const { classOf } = affineClasses({ group, frame, subgroups });
  for(const s of subgroups) s.affineClass = classOf.get(s.name);
  affineCountPerIndex = affineCounts(subgroups, classOf, maxIndex)
    .map((count, i) => ({ index: i + 1, count })).filter(c => c.count);
} else if(famKey === 'frieze' && corr.ok){
  const res = friezeAffineClasses(group, presentation, subgroups, maxIndex);
  for(const s of subgroups) s.affineClass = res.classOf.get(s.name);
  affineCountPerIndex = res.affineCountPerIndex;
} else if(isSpherical && corr.ok){
  const res = sphericalAffineClasses(group, presentation, subgroups, maxIndex, sphericalSpec);
  for(const s of subgroups) s.affineClass = res.classOf.get(s.name);
  affineCountPerIndex = res.affineCountPerIndex;
}

const stemOut = familyStem(famKey, groupName);
const manifest = {
  format: 'colorsym-catalog-manifest',
  version: 3,            // 3: geoKey is the key of the conjugacy class; keyCoset and representativeKey added
  group: {
    name: groupName,
    stem: stemOut,
    family: isWallpaper ? 'wallpaper' : famKey,
    gens: presentation.gens,
    relators: presentation.relators,
    geometry: isEuclidean ? { a: GEOMETRY_A } : {},
    ...(domainShape ? { domainShape } : {}),
    ...(dirichletInfo ? { dirichlet: dirichletInfo } : {}),
    geometryVerified: corr.ok,
    ...(frame ? { frame: { origin: frame.origin, t1: frame.t1, t2: frame.t2,
                           maxOrder: frame.maxOrder } } : {}),
  },
  maxIndex,
  totalCount: data.totalCount,
  countPerIndex: data.countPerIndex,
  ...(affineCountPerIndex ? { affineCountPerIndex } : {}),
  subgroups,
};

const outStem = stemOut +
                (domainShape ? '@' + domainShape.replace(/\*/g, 's').replace(/\s+/g, '-') : '') +
                (DG ? '@dirichlet' : '');
const outFile = join(outDir, outStem + '.json');

if(!dryRun){
  mkdirSync(outDir, { recursive: true });
  writeFileSync(outFile, JSON.stringify(manifest, null, 1));

  if(!domainShape && !DG){
    const indexFile = join(outDir, 'index.json');
    const index = existsSync(indexFile) ? JSON.parse(readFileSync(indexFile, 'utf8'))
                                        : { format: 'colorsym-catalog-index', groups: [] };
    const rec = { name: groupName, stem: stemOut, file: stemOut + '.json',
                  maxIndex, totalCount: data.totalCount };
    const at = index.groups.findIndex(g => g.name === groupName);
    if(at >= 0) index.groups[at] = rec; else index.groups.push(rec);
    writeFileSync(indexFile, JSON.stringify(index, null, 1));
  }
}

console.log(`${groupName} (${famKey}): ${subgroups.length} subgroups to index ${maxIndex}${dryRun ? ' [dry-run]' : ' -> ' + outFile}`);
for(const s of subgroups){
  console.log(`  ${(s.name || s.id).padEnd(20)} placements ${s.placements}` +
              `${s.normal ? ' (normal)' : ''}  (${s.id})`);
}
