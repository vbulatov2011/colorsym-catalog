/*
  fix_preset_motifs.mjs — audits all SymDraw presets under catalog/presets/ for
  visible non-tile motif items placed outside the preset's base colored tile
  (e.g. drawn on a symmetry copy g(tile) instead of the canonical tile, which
  looks fine in the full pattern but detaches from its colored cell in coset
  partition images).

  For each misplaced item, finds the shortest exact group isometry g in G that
  maps 100% of the item's points strictly into the base tile polygon, and
  transforms points, Bezier nodes (p, h1, h2), pivot, and axes by g so the full
  tiled pattern stays identical while every coset cell carries its own motif.

  Usage:
    node catalog/tools/fix_preset_motifs.mjs            # dry-run audit
    node catalog/tools/fix_preset_motifs.mjs --write    # apply fixes in place
*/
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { CAT, SYMMHUB_URL } from './catalog_paths.mjs';

const { iWallpaperGroup } = await import(SYMMHUB_URL + '/lib/grouplib/WallpaperGroups.js');
const { Group_Frieze, Group_Spherical, Group_KLM, Group_KLMN } =
  await import(SYMMHUB_URL + '/lib/grouplib/grouplib.js');
const { Group, ITransform, iPoint } = await import(SYMMHUB_URL + '/lib/invlib/invlib.js');

const WRITE = process.argv.includes('--write');

function walk(dir) {
  let out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (name.endsWith('.json')) out.push(p);
  }
  return out;
}

function ptInPoly(x, y, pts) {
  let inside = false;
  const m = pts.length / 2;
  for (let i = 0, j = m - 1; i < m; j = i++) {
    const xi = pts[2 * i], yi = pts[2 * i + 1];
    const xj = pts[2 * j], yj = pts[2 * j + 1];
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}

function minDistEdges(x, y, pts) {
  let d = Infinity;
  const m = pts.length / 2;
  for (let i = 0; i < m; i++) {
    const x0 = pts[2 * i], y0 = pts[2 * i + 1];
    const x1 = pts[2 * ((i + 1) % m)], y1 = pts[2 * ((i + 1) % m) + 1];
    const dx = x1 - x0, dy = y1 - y0, l2 = dx * dx + dy * dy;
    const t = l2 > 1e-12 ? Math.max(0, Math.min(1, ((x - x0) * dx + (y - y0) * dy) / l2)) : 0;
    d = Math.min(d, Math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)));
  }
  return d;
}

function isWhiteTile(it) {
  if (it.visible === false) return false;
  const f = it.style?.fill?.rgba;
  return f && f[0] > 0.9 && f[1] > 0.9 && f[2] > 0.9 && it.closed !== false && (it.points?.length || 0) >= 6;
}

function applyT(T, x, y) {
  const q = T.transform(iPoint([x, y, 0, 0]));
  return [q.v[0], q.v[1]];
}

// Local Jacobian J_T(x, y) applied to offset (dx, dy) — exact for Euclidean
// affine isometries AND accurate first-order conformal tangent map for Mobius
// inversions (e.g. axial 228).
function mapHandle(T, px, py, hx, hy, isConformal) {
  if (!isConformal) return applyT(T, hx, hy);
  const eps = 1e-6;
  const p0 = applyT(T, px, py);
  const pxp = applyT(T, px + eps, py);
  const pyp = applyT(T, px, py + eps);
  const j00 = (pxp[0] - p0[0]) / eps, j10 = (pxp[1] - p0[1]) / eps;
  const j01 = (pyp[0] - p0[0]) / eps, j11 = (pyp[1] - p0[1]) / eps;
  const dx = hx - px, dy = hy - py;
  return [p0[0] + j00 * dx + j01 * dy, p0[1] + j10 * dx + j11 * dy];
}

function mapDir(T, ox, oy, vx, vy) {
  const eps = 1e-6;
  const p0 = applyT(T, ox, oy);
  const pxp = applyT(T, ox + eps, oy);
  const pyp = applyT(T, ox, oy + eps);
  const j00 = (pxp[0] - p0[0]) / eps, j10 = (pxp[1] - p0[1]) / eps;
  const j01 = (pyp[0] - p0[0]) / eps, j11 = (pyp[1] - p0[1]) / eps;
  const rx = j00 * vx + j01 * vy, ry = j10 * vx + j11 * vy;
  const len = Math.hypot(rx, ry);
  return len > 1e-12 ? [rx / len, ry / len] : [vx, vy];
}

function buildGroup(sym) {
  const gt = sym.groupType || '';
  const cls = sym.group?.className || '';
  const gp = sym.group?.params || {};
  const origLog = console.log;
  console.log = () => {};
  try {
    if (gt === 'Wallpaper' || cls === 'Group_WP') {
      return {
        group: new Group(iWallpaperGroup({
          name: gp.type, a: gp.a, b: gp.b, c: gp.c,
          angle_a: (gp.angle_a || 0) * Math.PI / 180,
          angle_b: (gp.angle_b === undefined ? 90 : gp.angle_b) * Math.PI / 180,
          domainShape: gp.domainShape,
        })),
        conformal: false,
      };
    }
    if (gt === 'Frieze' || cls === 'Group_Frieze') {
      return { group: new Group_Frieze({ type: gp.type, a: gp.a }).getGroup(), conformal: false };
    }
    if (gt === 'Spherical' || cls === 'Group_Spherical') {
      return {
        group: new Group_Spherical({
          type: gp.type, n: gp.n, subtype: gp.subtype,
          ...(gp.centered !== undefined ? { centered: gp.centered } : {}),
        }).getGroup(),
        conformal: true,
      };
    }
    if (gt === 'KLM' || cls === 'Group_KLM') {
      const m = new Group_KLM();
      Object.assign(m.params, { K: gp.K, L: gp.L, M: gp.M, s: gp.s, hasR: gp.hasR });
      return { group: m.getGroup(), conformal: true };
    }
    if (gt === 'KLMN' || cls === 'Group_KLMN') {
      const m = new Group_KLMN();
      Object.assign(m.params, {
        K: gp.K, L: gp.L, M: gp.M, N: gp.N, s: gp.s,
        aspect: gp.aspect, twist: gp.twist, shift: gp.shift, bend: gp.bend, uhp: gp.uhp,
      });
      return { group: m.getGroup(), conformal: true };
    }
  } finally {
    console.log = origLog;
  }
  return null;
}

function enumerateGroup(group, maxDepth = 10, maxElems = 1600) {
  const gens = [];
  for (let i = 0; i < group.transforms.length; i++) {
    const t = new ITransform(group.transforms[i].slice(), group.getGenNames()[i]);
    gens.push(t);
    gens.push(t.getInverse());
  }
  const pA = [0.137, 0.291], pB = [-0.213, 0.173];
  const keyOf = T => {
    const a = applyT(T, pA[0], pA[1]), b = applyT(T, pB[0], pB[1]);
    return `${a[0].toFixed(4)},${a[1].toFixed(4)}|${b[0].toFixed(4)},${b[1].toFixed(4)}`;
  };
  const id = new ITransform([], '');
  const seen = new Map([[keyOf(id), { T: id, word: 'e', depth: 0 }]]);
  let frontier = [{ T: id, word: '', depth: 0 }];
  for (let d = 1; d <= maxDepth && seen.size < maxElems; d++) {
    const next = [];
    for (const cur of frontier) {
      for (const g of gens) {
        const T = cur.T.getCopy().concat(g);
        const k = keyOf(T);
        if (!seen.has(k)) {
          const rec = { T, word: cur.word + g.word, depth: d };
          seen.set(k, rec);
          next.push(rec);
          if (seen.size >= maxElems) break;
        }
      }
      if (seen.size >= maxElems) break;
    }
    frontier = next;
    if (!frontier.length) break;
  }
  return [...seen.values()];
}

function transformItem(it, T, conformal) {
  const newPts = [];
  for (let i = 0; i < it.points.length; i += 2) {
    const [nx, ny] = applyT(T, it.points[i], it.points[i + 1]);
    newPts.push(nx, ny);
  }
  it.points = newPts;

  if (Array.isArray(it.nodes)) {
    it.nodes = it.nodes.map(nd => {
      const [px, py] = nd.p;
      const np = applyT(T, px, py);
      const out = { ...nd, p: np };
      if (nd.h1) out.h1 = mapHandle(T, px, py, nd.h1[0], nd.h1[1], conformal);
      if (nd.h2) out.h2 = mapHandle(T, px, py, nd.h2[0], nd.h2[1], conformal);
      return out;
    });
  }

  let pivOrig = null;
  if (Array.isArray(it.pivot) && it.pivot.length === 2) {
    pivOrig = it.pivot.slice();
    it.pivot = applyT(T, pivOrig[0], pivOrig[1]);
  }
  if (Array.isArray(it.axes) && it.axes.length === 4) {
    const ox = pivOrig ? pivOrig[0] : 0;
    const oy = pivOrig ? pivOrig[1] : 0;
    const u = mapDir(T, ox, oy, it.axes[0], it.axes[1]);
    const v = mapDir(T, ox, oy, it.axes[2], it.axes[3]);
    it.axes = [u[0], u[1], v[0], v[1]];
  }
}

const files = walk(join(CAT, 'presets'));
let fixedFiles = 0, fixedItems = 0, failedItems = 0;

for (const f of files) {
  let doc;
  try { doc = JSON.parse(readFileSync(f, 'utf8')); } catch { continue; }
  const layers = doc?.params?.pattern?.patternParams?.params?.layers?.params?.children;
  if (!Array.isArray(layers)) continue;
  const enabledLayers = layers.filter(l => l.params.enabled !== false);
  const allItems = enabledLayers.flatMap(l => l.params.items || []).filter(it => it.visible !== false);
  const tiles = allItems.filter(isWhiteTile);
  if (!tiles.length) continue;

  const misplaced = [];
  for (const it of allItems) {
    if (isWhiteTile(it)) continue;
    if (it.closed === false && !it.style?.fill && String(it.id || '').startsWith('tile_seam')) continue;
    const pts = it.points || [];
    const n = pts.length / 2;
    if (n < 2) continue;
    let inside = 0;
    for (let i = 0; i < n; i++) {
      if (tiles.some(t => ptInPoly(pts[2 * i], pts[2 * i + 1], t.points))) inside++;
    }
    if (inside / n < 0.95) misplaced.push({ it, inside, n });
  }
  if (!misplaced.length) continue;

  const built = buildGroup(doc.params.symmetry);
  if (!built) {
    console.warn(`SKIP ${relative(CAT, f)}: unsupported group`);
    failedItems += misplaced.length;
    continue;
  }
  const elems = enumerateGroup(built.group);
  let fileChanged = false;
  const rel = relative(CAT, f).replace(/\\/g, '/');

  for (const { it, inside, n } of misplaced) {
    let best = null;
    for (const el of elems) {
      let ok = 0, minM = Infinity;
      for (let i = 0; i < n; i++) {
        const [nx, ny] = applyT(el.T, it.points[2 * i], it.points[2 * i + 1]);
        let inAny = false;
        for (const t of tiles) {
          if (ptInPoly(nx, ny, t.points)) {
            inAny = true;
            minM = Math.min(minM, minDistEdges(nx, ny, t.points));
            break;
          }
        }
        if (inAny) ok++;
      }
      if (ok > (best?.ok ?? -1) || (ok === best?.ok && el.depth < best.depth)) {
        best = { ...el, ok, minM };
      }
    }
    if (!best || best.ok < n) {
      console.warn(`FAIL ${rel} item=${it.id}: best match only ${best?.ok ?? 0}/${n}`);
      failedItems++;
      continue;
    }
    console.log(
      `${WRITE ? 'FIX ' : 'PLAN'} ${rel.padEnd(44)} item=${String(it.id).padEnd(5)} ` +
      `word=${best.word.padEnd(8)} (${inside}/${n} -> ${best.ok}/${n}, margin=${best.minM.toFixed(4)})`
    );
    if (WRITE) {
      transformItem(it, best.T, built.conformal);
      fileChanged = true;
    }
    fixedItems++;
  }

  if (WRITE && fileChanged) {
    writeFileSync(f, JSON.stringify(doc, null, 4) + '\n');
    fixedFiles++;
  }
}

console.log(
  `\n${WRITE ? 'Applied' : 'Planned'}: ${fixedItems} items across ${WRITE ? fixedFiles : 'matching'} files` +
  ` (${failedItems} failed).`
);
if (failedItems) process.exit(1);
