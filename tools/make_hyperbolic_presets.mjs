/*
  make_hyperbolic_presets.mjs — generates SymmHub symdraw_klm presets
  (curved tileFromDomain + bold asymmetric black comma strictly inside FD) for
  all 16 hyperbolic groups in data/hyperbolic/family.json:
    - 5 klm   (237, 238, 245, 334, 335)
    - 5 *klm  (*237, *238, *245, *334, *335)
    - 3 klmn  (2223, 2225, 2233)
    - 3 *klmn (*2223, *2225, *2233)
  Output: presets/hyperbolic/hyp/hyp-<stem>.json

  Uses the swapped wpe2/fe 7-color palette (#ffe6a7, #cf8439, #632001,
  #a14b12, #cffaf6, #63b2ee, #0d4392), Poincaré disk framing (zoom 0.94,
  empty inversive.itrans), useMipmap: true, and no unused 'image' layer.
*/
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { CAT, SYMMHUB_URL, SYMMHUB_DIR } from './catalog_paths.mjs';

const { Group_KLM, Group_KLMN } = await import(SYMMHUB_URL + '/lib/grouplib/grouplib.js');
const { tileFromDomain } = await import(SYMMHUB_URL + '/lib/drawlib/Tiles.js');

const PALETTE_7 = {
  '0': '#ffe6a7', // warm cream
  '1': '#cf8439', // warm amber
  '2': '#632001', // deep espresso
  '3': '#a14b12', // terracotta
  '4': '#cffaf6', // pale aqua
  '5': '#63b2ee', // sky blue
  '6': '#0d4392', // deep cobalt
};

const STROKE_RGBA = [0.12549019607843137, 0.18823529411764706, 0.2901960784313726, 1]; // #20304a
const FILL_WHITE  = [1, 1, 1, 1];
const FILL_BLACK  = [0, 0, 0, 1];

const TEMPLATE_PATH = join(SYMMHUB_DIR, 'apps', 'symdraw', 'presets', 'klm', 'symdraw-237-drawing.json');
const TEMPLATE = JSON.parse(readFileSync(TEMPLATE_PATH, 'utf8'));

const SPECS = [
  // klm (n = 2..7)
  { name: '237',   stem: '237',   kind: 'klm',  s: false, K: 2, L: 3, M: 7, maxN: 7, angle: 0.25 },
  { name: '238',   stem: '238',   kind: 'klm',  s: false, K: 2, L: 3, M: 8, maxN: 7, angle: 0.30 },
  { name: '245',   stem: '245',   kind: 'klm',  s: false, K: 2, L: 4, M: 5, maxN: 7, angle: 0.25 },
  { name: '334',   stem: '334',   kind: 'klm',  s: false, K: 3, L: 3, M: 4, maxN: 7, angle: 0.20 },
  { name: '335',   stem: '335',   kind: 'klm',  s: false, K: 3, L: 3, M: 5, maxN: 7, angle: 0.20 },
  // *klm (n = 2..6)
  { name: '*237',  stem: 's237',  kind: 'klm',  s: true,  K: 2, L: 3, M: 7, maxN: 6, angle: 0.40 },
  { name: '*238',  stem: 's238',  kind: 'klm',  s: true,  K: 2, L: 3, M: 8, maxN: 6, angle: 0.40 },
  { name: '*245',  stem: 's245',  kind: 'klm',  s: true,  K: 2, L: 4, M: 5, maxN: 6, angle: 0.35 },
  { name: '*334',  stem: 's334',  kind: 'klm',  s: true,  K: 3, L: 3, M: 4, maxN: 6, angle: 0.35 },
  { name: '*335',  stem: 's335',  kind: 'klm',  s: true,  K: 3, L: 3, M: 5, maxN: 6, angle: 0.35 },
  // klmn (n = 2..4)
  { name: '2223',  stem: '2223',  kind: 'klmn', s: false, K: 2, L: 2, M: 2, N: 3, maxN: 4, angle: 0.35 },
  { name: '2225',  stem: '2225',  kind: 'klmn', s: false, K: 2, L: 2, M: 2, N: 5, maxN: 4, angle: 0.35 },
  { name: '2233',  stem: '2233',  kind: 'klmn', s: false, K: 2, L: 2, M: 3, N: 3, maxN: 4, angle: 0.35 },
  // *klmn (n = 2..4)
  { name: '*2223', stem: 's2223', kind: 'klmn', s: true,  K: 2, L: 2, M: 2, N: 3, maxN: 4, angle: 0.40 },
  { name: '*2225', stem: 's2225', kind: 'klmn', s: true,  K: 2, L: 2, M: 2, N: 5, maxN: 4, angle: 0.40 },
  { name: '*2233', stem: 's2233', kind: 'klmn', s: true,  K: 2, L: 2, M: 3, N: 3, maxN: 4, angle: 0.40 },
];

function inFD(group, x, y, eps = 1e-5) {
  for (const s of group.getFundDomain()) {
    const [a, b, , d] = s.v;
    let val;
    if (s.type === 2) {
      val = a * x + b * y - d;
    } else {
      const dist = Math.hypot(x - a, y - b);
      val = d > 0 ? (dist - d) : (-d - dist);
    }
    if (val > -eps) return false;
  }
  return true;
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

function poleOfInaccessibility(pts, group) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < pts.length; i += 2) {
    minX = Math.min(minX, pts[i]); maxX = Math.max(maxX, pts[i]);
    minY = Math.min(minY, pts[i + 1]); maxY = Math.max(maxY, pts[i + 1]);
  }
  let best = { x: 0, y: 0, r: -1 };
  const N = 48;
  for (let ix = 1; ix < N; ix++) {
    const x = minX + (maxX - minX) * ix / N;
    for (let iy = 1; iy < N; iy++) {
      const y = minY + (maxY - minY) * iy / N;
      if (!ptInPoly(x, y, pts) || !inFD(group, x, y)) continue;
      const d = minDistEdges(x, y, pts);
      if (d > best.r) best = { x, y, r: d };
    }
  }
  let step = Math.max(maxX - minX, maxY - minY) / N;
  for (let iter = 0; iter < 6; iter++) {
    step *= 0.5;
    for (let dx = -2; dx <= 2; dx++) {
      for (let dy = -2; dy <= 2; dy++) {
        const x = best.x + dx * step, y = best.y + dy * step;
        if (!ptInPoly(x, y, pts) || !inFD(group, x, y)) continue;
        const d = minDistEdges(x, y, pts);
        if (d > best.r) best = { x, y, r: d };
      }
    }
  }
  if (best.r <= 0) throw new Error('could not find interior point of fundamental domain');
  return best;
}

// Smooth 4-node closed cubic Bezier bold asymmetric comma, normalized inside |z| <= 0.88.
// Editable directly in SymmHub's path tool and unmistakably chiral under reflections & rotations.
function makeCommaPath(cx, cy, r, angle, strokeWidth) {
  const ca = Math.cos(angle), sa = Math.sin(angle);
  const toW = ([lx, ly]) => [cx + r * (lx * ca - ly * sa), cy + r * (lx * sa + ly * ca)];

  // Local nodes: [anchor, handleIn(h1), handleOut(h2), smooth]
  const localNodes = [
    // 0: inner belly pinch between head and tail
    { p: [-0.06, -0.02], h1: [-0.30, -0.10], h2: [-0.14, -0.36], smooth: false },
    // 1: sharp tapered tail tip curving down-left
    { p: [-0.42, -0.78], h1: [-0.16, -0.58], h2: [0.36, -0.58],  smooth: false },
    // 2: outer convex cheek on the right
    { p: [0.46, 0.22],   h1: [0.56, -0.22],  h2: [0.42, 0.68],   smooth: true },
    // 3: rounded bulbous top-left crown of the head
    { p: [-0.28, 0.56],  h1: [0.06, 0.78],   h2: [-0.52, 0.22],  smooth: true },
  ];

  const nodes = localNodes.map(n => ({
    p: toW(n.p),
    h1: toW(n.h1),
    h2: toW(n.h2),
    ...(n.smooth ? { smooth: true } : {}),
  }));

  // Sample each cubic Bezier segment densely for crisp rendering
  const points = [];
  const SEGS = 12;
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i], b = nodes[(i + 1) % nodes.length];
    const p0 = a.p, p1 = a.h2, p2 = b.h1, p3 = b.p;
    for (let s = 0; s < SEGS; s++) {
      const t = s / SEGS, u = 1 - t;
      const x = u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0];
      const y = u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1];
      points.push(x, y);
    }
  }

  return {
    type: 'path',
    id: 'orn_comma',
    closed: true,
    points,
    style: {
      stroke: { rgba: STROKE_RGBA },
      strokeWidth,
      lineCap: 'round',
      lineJoin: 'round',
      fill: { rgba: FILL_BLACK },
      opacity: 1,
    },
    pivot: [cx, cy],
    nodes,
  };
}

function buildPreset(sp) {
  const doc = JSON.parse(JSON.stringify(TEMPLATE));
  const presetName = `hyp-${sp.stem}`;
  doc.name = presetName;

  // Build group silently (SymmHub's Group_KLM logs debug lines)
  const origLog = console.log;
  console.log = () => {};
  let group, baseTile;
  try {
    let maker;
    if (sp.kind === 'klm') {
      maker = new Group_KLM();
      Object.assign(maker.params, { K: sp.K, L: sp.L, M: sp.M, s: sp.s, hasR: false });
    } else {
      maker = new Group_KLMN();
      Object.assign(maker.params, { K: sp.K, L: sp.L, M: sp.M, N: sp.N, s: sp.s, uhp: false, aspect: 0.5, twist: 0, shift: 0, bend: 0 });
    }
    group = maker.getGroup();
    const idMap = { map: (x, y) => [x, y] };
    // Compute preliminary tile to measure inradius for stroke scaling
    const probe = tileFromDomain(group, idMap, { fill: { rgba: FILL_WHITE }, stroke: { rgba: STROKE_RGBA }, strokeWidth: 0.005 }, null, true);
    if (!probe) throw new Error(`tileFromDomain returned null for ${sp.name}`);
    const pole = poleOfInaccessibility(probe.points, group);
    const strokeW = Math.max(0.0032, Math.min(0.0095, pole.r * 0.075));
    const baseStyle = {
      stroke: { rgba: STROKE_RGBA },
      strokeWidth: strokeW,
      lineCap: 'round',
      lineJoin: 'round',
      fill: { rgba: FILL_WHITE },
      opacity: 1,
    };
    baseTile = tileFromDomain(group, idMap, baseStyle, null, true);
    baseTile.id = 'tile_fd';

    const commaR = pole.r * 0.68;
    const comma = makeCommaPath(pole.x, pole.y, commaR, sp.angle, strokeW * 0.35);

    // Strictly verify every sampled point of the comma lies inside FD and tile polygon
    for (let i = 0; i < comma.points.length; i += 2) {
      const px = comma.points[i], py = comma.points[i + 1];
      if (!ptInPoly(px, py, baseTile.points) || !inFD(group, px, py)) {
        throw new Error(`${sp.name}: comma point (${px.toFixed(4)}, ${py.toFixed(4)}) outside FD`);
      }
    }

    const pp = doc.params.pattern.patternParams.params;
    pp.layer = 'layer1';
    pp.style.stroked = true;
    pp.style.stroke = '#20304a';
    pp.style.width = strokeW;
    pp.style.filled = true;
    pp.style.fill = '#000000';
    pp.style.curvedTiles = true;
    pp.layers.params.children = [{
      className: 'DrawingLayer',
      params: {
        id: 'layer1',
        enabled: true,
        locked: false,
        opacity: 1,
        items: [baseTile, comma],
      },
    }];

    doc.params.pattern.patternTransform = {
      centerX: 0, centerY: 0, scale: 1, angle: 0,
      pivotX: 0, pivotY: 0, bendX: 0, bendY: 0, geometric: true,
    };

    // Symmetry
    if (sp.kind === 'klm') {
      doc.params.symmetry.groupType = 'KLM';
      doc.params.symmetry.group = {
        className: 'Group_KLM',
        params: { s: sp.s, K: sp.K, L: sp.L, M: sp.M, hasR: false },
      };
    } else {
      doc.params.symmetry.groupType = 'KLMN';
      doc.params.symmetry.group = {
        className: 'Group_KLMN',
        params: { s: sp.s, K: sp.K, L: sp.L, M: sp.M, N: sp.N, aspect: 0.5, twist: 0, shift: 0, bend: 0, uhp: false },
      };
    }
    doc.params.symmetry.transform = { translationX: 0, translationY: 0, rotation: 0, scale: 1 };
    doc.params.symmetry.dirichlet.enabled = false;
    doc.params.symmetry.options.iterations = 120;

    // Visualization: strip unused 'image' layer, configure drawing & overlay
    const visLayersObj = doc.params.visualization.params.layers.params;
    visLayersObj.children = visLayersObj.children.filter(c => c.params?.id !== 'image');

    const drawingLayer = visLayersObj.children.find(c => c.params.id === 'drawing').params;
    drawingLayer.enabled = true;
    drawingLayer.useSymmetry = true;
    drawingLayer.permutations = '';
    drawingLayer.permIndex = 0;
    drawingLayer.useOrbit = false;
    drawingLayer.mask = '';
    drawingLayer.subgroups.params.maxIndex = sp.maxN;
    drawingLayer.subgroups.params.subgroup = '';
    drawingLayer.coloringType = 'mult';
    drawingLayer.colorTiles.params.count = 7;
    drawingLayer.colorTiles.params.palette = 'custom';
    drawingLayer.colorTiles.params.edited = { ...PALETTE_7 };
    drawingLayer.colorTiles.params.alphas = {};
    drawingLayer.useCrown = false;
    drawingLayer.useTilt = false;
    drawingLayer.patternTiltDirection = 0;
    drawingLayer.useMipmap = true;
    drawingLayer.interpolation = 'linear';

    const overlayLayer = visLayersObj.children.find(c => c.params.id === 'overlay').params;
    overlayLayer.enabled = false;
    for (const child of overlayLayer.overlays.params.children) {
      child.params.enabled = false;
    }

    // Poincare disk framing: unit disk fills ~94% of square frame with clean margin
    const tr = doc.params.tools.transform.params;
    tr.mode = 'euclidean';
    tr.spherical = { enabled: false };
    tr.inversive = { enabled: true, itrans: [] };
    tr.euclidean = { centerX: 0, centerY: 0, zoom: 0.94 };

    return { doc, pole, strokeW, commaR };
  } finally {
    console.log = origLog;
  }
}

const outDir = join(CAT, 'presets', 'hyperbolic', 'hyp');
mkdirSync(outDir, { recursive: true });

for (const sp of SPECS) {
  const { doc, pole, strokeW, commaR } = buildPreset(sp);
  const outPath = join(outDir, `${doc.name}.json`);
  writeFileSync(outPath, JSON.stringify(doc, null, 1) + '\n');
  console.log(
    `${sp.name.padEnd(6)} -> ${doc.name}.json  pole=(${pole.x.toFixed(3)}, ${pole.y.toFixed(3)}) ` +
    `inr=${pole.r.toFixed(4)} commaR=${commaR.toFixed(4)} stroke=${strokeW.toFixed(4)}`
  );
}
console.log(`wrote ${SPECS.length} hyperbolic presets to ${outDir}`);
