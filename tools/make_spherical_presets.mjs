/*
  make_spherical_presets.mjs — generates SymmHub symdraw_spherical presets
  (curved tileFromDomain / centered wedge tiles + subtle asymmetric inner ornament) for:
    - all 7 polyhedral groups -> presets/polyhedral/ph/ph-<stem>.json
    - all 49 axial groups (n = 2..8) -> presets/axial/ax/ax-<stem>.json

  Uses the swapped wpe2/fe palette for colors 0..6 (#ffe6a7, #cf8439, #632001,
  #a14b12, #cffaf6, #63b2ee, #0d4392) extended harmoniously to 12 colors for
  polyhedral groups.
*/
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { CAT, SYMMHUB_URL, SYMMHUB_DIR } from './catalog_paths.mjs';

const { Group_Spherical } = await import(SYMMHUB_URL + '/lib/grouplib/grouplib.js');
const { tileFromDomain } = await import(SYMMHUB_URL + '/lib/drawlib/Tiles.js');
const { iPlane, iSphere, iFactorizeU4 } = await import(SYMMHUB_URL + '/lib/invlib/invlib.js');

// Swapped wpe2/fe palette (0..6) + 5 harmonious colors (7..11) for up to 12 colors
const PALETTE_12 = {
  '0':  '#ffe6a7', // warm cream
  '1':  '#cf8439', // warm amber (soft contrast vs cream on 2-color patterns)
  '2':  '#632001', // deep espresso
  '3':  '#a14b12', // terracotta
  '4':  '#cffaf6', // pale aqua
  '5':  '#63b2ee', // sky blue
  '6':  '#0d4392', // deep cobalt
  '7':  '#8db87a', // sage green
  '8':  '#3a6f47', // forest green
  '9':  '#d67a8a', // dusty rose
  '10': '#8e3b5c', // plum
  '11': '#e8c55a', // ochre gold
};

const STROKE_RGBA = [0.12549019607843137, 0.18823529411764706, 0.2901960784313726, 1]; // #20304a
const FILL_WHITE  = [1, 1, 1, 1];
const FILL_TINT   = [0.80, 0.78, 0.75, 1]; // subtle warm shade for inner asymmetric ornament
const FILL_DOT    = [0.22, 0.26, 0.34, 1]; // crisp dark-slate accent dot

const TEMPLATE_PATH = join(SYMMHUB_DIR, 'apps', 'symdraw', 'presets', 'spherical', 'symdraw-spherical-s432.json');
const TEMPLATE = JSON.parse(readFileSync(TEMPLATE_PATH, 'utf8'));

// Great-circle reflection in plane normal to unit vector (a, b, c) on S^2
function greatCircleSplane(n) {
  const len = Math.hypot(n[0], n[1], n[2]);
  const a = n[0] / len, b = n[1] / len, c = n[2] / len;
  if (Math.abs(c) < 1e-9) return iPlane([a, b, 0, 0]);
  return iSphere([a / c, b / c, 0, 1 / Math.abs(c)]);
}

// Two great-circle reflections giving a right-handed rotation by `angle` about `axis`
function axisAngleSplanes(axis, angle) {
  const len = Math.hypot(axis[0], axis[1], axis[2]);
  const u = [axis[0] / len, axis[1] / len, axis[2] / len];
  const ref = Math.abs(u[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
  // v1 = normalize(u x ref)
  let v1 = [u[1]*ref[2] - u[2]*ref[1], u[2]*ref[0] - u[0]*ref[2], u[0]*ref[1] - u[1]*ref[0]];
  const l1 = Math.hypot(v1[0], v1[1], v1[2]);
  v1 = [v1[0]/l1, v1[1]/l1, v1[2]/l1];
  // w = u x v1
  const w = [u[1]*v1[2] - u[2]*v1[1], u[2]*v1[0] - u[0]*v1[2], u[0]*v1[1] - u[1]*v1[0]];
  const ha = angle / 2;
  const v2 = [
    v1[0]*Math.cos(ha) + w[0]*Math.sin(ha),
    v1[1]*Math.cos(ha) + w[1]*Math.sin(ha),
    v1[2]*Math.cos(ha) + w[2]*Math.sin(ha),
  ];
  return [greatCircleSplane(v1), greatCircleSplane(v2)];
}

function composeSphereRotations(rotList) {
  const splanes = [];
  for (const [axis, deg] of rotList) {
    splanes.push(...axisAngleSplanes(axis, deg * Math.PI / 180));
  }
  const factored = iFactorizeU4(splanes);
  return JSON.parse(JSON.stringify(factored));
}

// Compute polygon centroid & approximate inradius (min distance from centroid to edges)
function polygonCenterAndRadius(flatPts) {
  const m = flatPts.length / 2;
  let cx = 0, cy = 0;
  for (let i = 0; i < m; i++) { cx += flatPts[2*i]; cy += flatPts[2*i + 1]; }
  cx /= m; cy /= m;
  let minD = Infinity;
  let maxD = 0;
  for (let i = 0; i < m; i++) {
    const x0 = flatPts[2*i], y0 = flatPts[2*i + 1];
    const x1 = flatPts[2*((i + 1) % m)], y1 = flatPts[2*((i + 1) % m) + 1];
    maxD = Math.max(maxD, Math.hypot(x0 - cx, y0 - cy));
    const dx = x1 - x0, dy = y1 - y0;
    const len2 = dx*dx + dy*dy;
    const t = len2 > 1e-12 ? Math.max(0, Math.min(1, ((cx - x0)*dx + (cy - y0)*dy) / len2)) : 0;
    const px = x0 + t*dx, py = y0 + t*dy;
    minD = Math.min(minD, Math.hypot(cx - px, cy - py));
  }
  return { cx, cy, inr: minD, outr: maxD };
}

// Build an asymmetric teardrop + small dot strictly inside disk (cx, cy, r)
function makeInnerOrnament(cx, cy, r, angle = 0.45, strokeWidth = 0.008) {
  const ca = Math.cos(angle), sa = Math.sin(angle);
  const toWorld = (lx, ly) => [cx + r*(lx*ca - ly*sa), cy + r*(lx*sa + ly*ca)];

  // Asymmetric curved teardrop (slightly bent so reflection is visibly chiral)
  const leafPts = [];
  const N = 28;
  for (let i = 0; i < N; i++) {
    const t = (2 * Math.PI * i) / N;
    // tear profile + slight asymmetry bend
    const u = 0.62 * Math.cos(t) - 0.14;
    const v = 0.34 * Math.sin(t) * (0.65 - 0.35 * Math.cos(t)) + 0.10 * (u + 0.3)*(u + 0.3);
    leafPts.push(...toWorld(u, v));
  }
  const leaf = {
    type: 'polyline',
    id: 'orn_leaf',
    closed: true,
    points: leafPts,
    style: {
      stroke: { rgba: STROKE_RGBA },
      strokeWidth,
      lineCap: 'round',
      lineJoin: 'round',
      fill: { rgba: FILL_TINT },
      opacity: 1,
    },
  };

  // Small off-center dot next to the teardrop's curve
  const dotCenter = toWorld(0.28, -0.34);
  const dotR = r * 0.14;
  const dotPts = [];
  for (let i = 0; i < 16; i++) {
    const t = (2 * Math.PI * i) / 16;
    dotPts.push(dotCenter[0] + dotR * Math.cos(t), dotCenter[1] + dotR * Math.sin(t));
  }
  const dot = {
    type: 'polyline',
    id: 'orn_dot',
    closed: true,
    points: dotPts,
    style: {
      stroke: { rgba: STROKE_RGBA },
      strokeWidth: strokeWidth * 0.7,
      lineCap: 'round',
      lineJoin: 'round',
      fill: { rgba: FILL_DOT },
      opacity: 1,
    },
  };
  return [leaf, dot];
}

// Build an unstroked pure-white closed circular/annular sector in [rMin, rMax], [a0, a1]
function makeSectorFill(id, rMin, rMax, a0, a1, steps = 36) {
  const pts = [];
  if (rMin <= 0) {
    pts.push(0, 0);
    for (let k = 0; k <= steps; k++) {
      const a = a0 + (a1 - a0) * (k / steps);
      pts.push(rMax * Math.cos(a), rMax * Math.sin(a));
    }
  } else {
    for (let k = 0; k <= steps; k++) {
      const a = a0 + (a1 - a0) * (k / steps);
      pts.push(rMax * Math.cos(a), rMax * Math.sin(a));
    }
    for (let k = steps; k >= 0; k--) {
      const a = a0 + (a1 - a0) * (k / steps);
      pts.push(rMin * Math.cos(a), rMin * Math.sin(a));
    }
  }
  return {
    type: 'polyline',
    id,
    closed: true,
    points: pts,
    style: {
      stroke: null,
      strokeWidth: 0,
      fill: { rgba: FILL_WHITE },
      opacity: 1,
    },
  };
}

// Build an open stroked radial ray from (0, 0) to radius rMax at angle a
function makeRadialSeam(id, a, rMax, strokeWidth) {
  return {
    type: 'polyline',
    id,
    closed: false,
    points: [0, 0, rMax * Math.cos(a), rMax * Math.sin(a)],
    style: {
      stroke: { rgba: STROKE_RGBA },
      strokeWidth,
      lineCap: 'round',
      lineJoin: 'round',
      fill: null,
      opacity: 1,
    },
  };
}

// Unbounded wedge items for centered nn, nx, *nn (pole at (0, 0), no inversive.itrans).
// Splits the white fill into three overlapping logarithmic rings so every sprite keeps
// high texel density and nx (which inverts r -> 1/r in odd wedges) fills seamlessly all
// the way to < 1 px of the origin with no stroked outer arc.
function makeCenteredWedgeItems(type, n, strokeWidth) {
  const a0 = (type === 'nn') ? -Math.PI / n : 0;
  const a1 = Math.PI / n;
  const items = [
    makeSectorFill('tile_wedge',     0,    4.2, a0, a1, 36),
    makeSectorFill('tile_wedge_mid', 3.5, 25.0, a0, a1, 36),
    makeSectorFill('tile_wedge_far', 20.0, 200.0, a0, a1, 36),
  ];
  if (type === 'nx') {
    // Under sc (r -> 1/r), each [0, 1.05] ray maps onto [0.95, inf] on the neighboring ray,
    // covering every radial divider seamlessly with conformal stroke weight and 4x sprite DPI.
    items.push(
      makeRadialSeam('tile_seam_a', a0, 1.05, strokeWidth),
      makeRadialSeam('tile_seam_b', a1, 1.05, strokeWidth),
    );
  } else if (type === 'nn') {
    // Rotation by 2*pi/n maps ray a0 onto ray a1, so one ray generates all n dividers.
    items.push(makeRadialSeam('tile_seam_a', a0, 4.2, strokeWidth));
  } else {
    // *nn: a0 and a1 are distinct mirror rays; draw both.
    items.push(
      makeRadialSeam('tile_seam_a', a0, 4.2, strokeWidth),
      makeRadialSeam('tile_seam_b', a1, 4.2, strokeWidth),
    );
  }
  return items;
}

function buildPreset({ presetName, type, n, centered, colorCount, cameraRots, zoom = 0.42, ornamentAngle }) {
  const doc = JSON.parse(JSON.stringify(TEMPLATE));
  doc.name = presetName;

  const maker = new Group_Spherical({ type, n, subtype: 0, centered });
  const group = maker.getGroup();

  const idMap = { map: (x, y) => [x, y] };
  const isWedge = ['nn', 'nx', '*nn'].includes(type);
  const isBoundedAxial = ['n*', '22n', '2*n', '*22n'].includes(type);
  const isAxial = isWedge || isBoundedAxial;
  const strokeW = isWedge ? Math.max(0.008, Math.min(0.020, 0.042 / Math.sqrt(n)))
                          : (type.includes('532') ? 0.007
                           : type.includes('432') ? 0.009
                           : type.includes('332') || type === '3*2' ? 0.011
                           : Math.max(0.008, Math.min(0.020, 0.040 / Math.sqrt(n))));

  const baseStyle = {
    stroke: { rgba: STROKE_RGBA },
    strokeWidth: strokeW,
    lineCap: 'round',
    lineJoin: 'round',
    fill: { rgba: FILL_WHITE },
    opacity: 1,
  };

  let tileItems;
  if (isWedge) {
    tileItems = makeCenteredWedgeItems(type, n, strokeW);
  } else {
    const baseTile = tileFromDomain(group, idMap, baseStyle, null, true);
    if (!baseTile) throw new Error(`tileFromDomain returned null for ${presetName}`);
    baseTile.id = 'tile_fd';
    tileItems = [baseTile];
  }

  let cx, cy, inr;
  if (isAxial) {
    // Exact sector incenter inside the unit disk so both the inner hemisphere (r < 1,
    // also the visible front of the 3D sphere) and any equatorial image (1/r) stay
    // comfortably unclipped inside the stereographic frame [-2.63, 2.63].
    const fullWedge = (type === 'nn' || type === 'n*' || type === '22n');
    const alpha = fullWedge ? (Math.PI / n) : (Math.PI / (2 * n));
    const thetaMid = fullWedge ? 0 : alpha;
    const d = Math.max(0.58, 1 / (1 + Math.sin(alpha)));
    inr = Math.min(1 - d, d * Math.sin(alpha));
    cx = d * Math.cos(thetaMid);
    cy = d * Math.sin(thetaMid);
  } else {
    ({ cx, cy, inr } = polygonCenterAndRadius(tileItems[0].points));
  }
  // Keep ornament comfortably inside the domain incircle so it never crosses walls
  const ornR = Math.max(0.025, Math.min(isAxial ? 0.24 : 0.30, inr * 0.64));
  const ornItems = makeInnerOrnament(cx, cy, ornR, ornamentAngle, strokeW * 0.75);

  const pp = doc.params.pattern.patternParams.params;
  pp.style.stroked = true;
  pp.style.stroke = '#20304a';
  pp.style.width = strokeW;
  pp.style.filled = true;
  pp.style.fill = '#ffffff';
  pp.style.curvedTiles = true;
  pp.layers.params.children[0].params.items = [...tileItems, ...ornItems];

  doc.params.pattern.patternTransform = {
    centerX: 0, centerY: 0, scale: 1, angle: 0,
    pivotX: 0, pivotY: 0, bendX: 0, bendY: 0, geometric: true,
  };

  // Symmetry
  doc.params.symmetry.group.params = { type, n, subtype: 0, centered };
  doc.params.symmetry.options.iterations = 40;

  // ColorTiles palette (drop unused 'image' layer from template and enable mipmaps)
  const visLayersObj = doc.params.visualization.params.layers.params;
  visLayersObj.children = visLayersObj.children.filter(c => c.params?.id !== 'image');
  const drawingLayer = visLayersObj.children.find(c => c.params.id === 'drawing').params;
  drawingLayer.useMipmap = true;
  drawingLayer.coloringType = 'mult';
  drawingLayer.colorTiles.params.count = colorCount;
  drawingLayer.colorTiles.params.edited = Object.fromEntries(
    Object.entries(PALETTE_12).slice(0, Math.max(7, colorCount))
  );

  // Conformal stereographic projection (spherical disabled); shows the whole
  // sphere (both hemispheres inside and outside the unit equator circle).
  // Live Preview offers a Stereographic / Sphere switch to toggle spherical.enabled.
  const tr = doc.params.tools.transform.params;
  tr.mode = 'spherical';
  tr.spherical = { enabled: false };
  tr.inversive = { enabled: true, itrans: cameraRots.length ? composeSphereRotations(cameraRots) : [] };
  tr.euclidean = { centerX: 0, centerY: 0, zoom };

  return doc;
}

// 1. All 7 polyhedral presets -> presets/polyhedral/ph/
const polyDir = join(CAT, 'presets', 'polyhedral', 'ph');
mkdirSync(polyDir, { recursive: true });
const POLY_GROUPS = ['332', '3*2', '*332', '432', '*432', '532', '*532'];
for (let i = 0; i < POLY_GROUPS.length; i++) {
  const g = POLY_GROUPS[i];
  const stem = g.replace(/\*/g, 's');
  const presetName = `ph-${stem}`;
  // Centered on the group's primary symmetry axis in stereographic projection;
  // zoom frames both the inner hemisphere (r <= 1) and outer hemisphere cleanly.
  const zoom = g.includes('532') ? 0.42 : g.includes('432') ? 0.38 : 0.34;
  const doc = buildPreset({
    presetName, type: g, n: 2, centered: true, colorCount: 12,
    cameraRots: [],
    zoom,
    ornamentAngle: 0.35 + i * 0.25,
  });
  writeFileSync(join(polyDir, `${presetName}.json`), JSON.stringify(doc, null, 1) + '\n');
}
console.log(`wrote ${POLY_GROUPS.length} polyhedral presets to ${polyDir}`);

// 2. All 49 axial presets (n = 2..8) -> presets/axial/ax/
const axDir = join(CAT, 'presets', 'axial', 'ax');
mkdirSync(axDir, { recursive: true });
const AXIAL_TYPES = ['nn', 'nx', '*nn', 'n*', '22n', '2*n', '*22n'];
let nAx = 0;
for (let n = 2; n <= 8; n++) {
  for (let ti = 0; ti < AXIAL_TYPES.length; ti++) {
    const t = AXIAL_TYPES[ti];
    const g = t.replace(/n/g, String(n));
    const stem = g.replace(/\*/g, 's');
    const presetName = `ax-${stem}`;
    // centered=true puts the n-fold symmetry pole at world (0, 0) and the equator on
    // the unit circle r = 1, so inversive.itrans stays empty (identity) and editing
    // shapes near the origin in stereographic projection feels Euclidean and distortion-free.
    const doc = buildPreset({
      presetName, type: t, n, centered: true, colorCount: 6,
      cameraRots: [],
      zoom: 0.38,
      ornamentAngle: 0.4 + ti * 0.2,
    });
    writeFileSync(join(axDir, `${presetName}.json`), JSON.stringify(doc, null, 1) + '\n');
    nAx++;
  }
}
console.log(`wrote ${nAx} axial presets to ${axDir}`);
